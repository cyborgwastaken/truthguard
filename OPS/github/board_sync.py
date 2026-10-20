#!/usr/bin/env python3
"""Keep the "Virtusa TruthGuard" board in step with what happens on GitHub.

Run by .github/workflows/board-automation.yml; it reads the GitHub event from the environment.

  branch for a ticket is created (tNN-...)    ticket -> In progress
  PR opened / reopened / ready for review     ticket -> In review   (a draft PR keeps it In progress)
  PR converted back to draft                  ticket -> In progress
  PR closed without merging                   ticket -> In progress
  PR merged                                   ticket -> Done, and every ticket it unblocks -> Ready
  hourly / manual run                         repair: closed ticket -> Done, PR state, unblocked -> Ready

A PR belongs to a ticket only through a closing keyword in its description ("Closes #7"). "Refs #6"
never moves a card, so follow-up PRs for a finished ticket leave it alone.

Local use (read-only preview, nothing is changed):
  python3 OPS/github/board_sync.py --dry-run --event-name pull_request_target --event-file event.json
  python3 OPS/github/board_sync.py --dry-run --reconcile

Tokens: GH_TOKEN reads issues and PRs and posts comments. PROJECT_TOKEN (a classic personal access
token with only the `project` scope) writes to the user-owned project, which GITHUB_TOKEN cannot do.
Without GITHUB_ACTIONS set, both fall back to your own `gh` login.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Dict, List, Optional, Set

REPO = "cyborgwastaken/truthguard"
# "@me" = the user the token belongs to. Looking the owner up by name also queries organizations, which
# fails with "unknown owner type" for a token that only has the `project` scope.
OWNER = "@me"
PROJECT = "3"
STATUS_FIELD = "PVTSSF_lAHOCDU-7c4BnxxizhmUzuQ"
OPTIONS = {
    "Backlog": "f75ad846",
    "Ready": "61e4505c",
    "In progress": "47fc9ee4",
    "In review": "df73e18b",
    "Done": "98236657",
}

CLOSING = re.compile(r"(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b:?\s+#(\d+)")
BRANCH = re.compile(r"^t(\d{2})-")
TICKET_TITLE = re.compile(r"^(T\d{2}):")
DEPENDS = re.compile(r"#(\d+) \(T\d{2}\)")
PRIMARY = re.compile(r"\*\*Primary:\*\* @(\S+)")

OPEN_STATES = {"Backlog", "Ready", "In progress"}  # work not yet in review
NOT_DONE = {"Backlog", "Ready", "In progress", "In review"}


class Ticket:
    def __init__(self, number: int, tid: str, deps: List[int], primary: Optional[str], state: str,
                 status: str, item_id: Optional[str] = None):
        self.number, self.tid, self.deps, self.primary = number, tid, deps, primary
        self.state, self.status, self.item_id = state, status, item_id


class Board:
    """In-memory board. GitHubBoard persists changes; tests use this class directly."""

    def __init__(self, tickets: List[Ticket]):
        self.tickets: Dict[int, Ticket] = {t.number: t for t in tickets}
        self.log: List[str] = []

    def set_status(self, ticket: Ticket, new: str, why: str) -> None:
        self.log.append("%s #%d: %s -> %s (%s)" % (ticket.tid, ticket.number, ticket.status, new, why))
        ticket.status = new

    def comment(self, ticket: Ticket, text: str) -> None:
        self.log.append("%s #%d: comment posted" % (ticket.tid, ticket.number))

    def by_tid(self, tid: str) -> Optional[Ticket]:
        return next((t for t in self.tickets.values() if t.tid == tid), None)


def closing_issues(body: Optional[str]) -> List[int]:
    """Issue numbers a PR description closes ("Closes #7", "fixes #7", "Resolved #7")."""
    return sorted({int(n) for n in CLOSING.findall(body or "")})


def move(board: Board, ticket: Ticket, new: str, allowed_from: Set[str], why: str) -> bool:
    if ticket.status == new or ticket.status not in allowed_from:
        return False
    board.set_status(ticket, new, why)
    return True


def unlock(board: Board) -> List[Ticket]:
    """Backlog tickets whose dependencies are all Done become Ready. Tickets without dependencies
    (the post-hackathon ones) are never started automatically."""
    moved = []
    for ticket in sorted(board.tickets.values(), key=lambda t: t.tid):
        if ticket.status != "Backlog" or not ticket.deps:
            continue
        deps = [board.tickets.get(n) for n in ticket.deps]
        if all(d is not None and d.status == "Done" for d in deps):
            board.set_status(ticket, "Ready", "all dependencies are done: " + ", ".join(d.tid for d in deps))
            names = ", ".join("%s (#%d)" % (d.tid, d.number) for d in deps)
            who = "@%s, " % ticket.primary if ticket.primary else ""
            board.comment(ticket, "**Ready to start.** Everything this ticket depends on is merged: %s.\n\n"
                                  "%sbranch from an up-to-date `main` and name it `%s-<few-words>`." % (
                                      names, who, ticket.tid.lower()))
            moved.append(ticket)
    return moved


def on_branch_created(board: Board, ref: str, ref_type: str) -> None:
    if ref_type != "branch":
        return
    match = BRANCH.match(ref)
    ticket = board.by_tid("T" + match.group(1)) if match else None
    if ticket:
        move(board, ticket, "In progress", {"Backlog", "Ready"}, "branch %s created" % ref)


def on_pull_request(board: Board, action: str, pr: dict) -> None:
    tickets = [board.tickets[n] for n in closing_issues(pr.get("body")) if n in board.tickets]
    number = pr.get("number")
    merged = False
    for ticket in tickets:
        if action in ("opened", "reopened"):
            if pr.get("draft"):
                move(board, ticket, "In progress", {"Backlog", "Ready"}, "draft PR #%s" % number)
            else:
                move(board, ticket, "In review", OPEN_STATES, "PR #%s opened" % number)
        elif action == "ready_for_review":
            move(board, ticket, "In review", OPEN_STATES, "PR #%s ready for review" % number)
        elif action == "converted_to_draft":
            move(board, ticket, "In progress", {"In review"}, "PR #%s back to draft" % number)
        elif action == "closed":
            if pr.get("merged"):
                move(board, ticket, "Done", NOT_DONE, "PR #%s merged" % number)
                merged = True
            else:
                move(board, ticket, "In progress", {"In review"}, "PR #%s closed without merging" % number)
    if merged:
        # Always unlock, even if the card was already Done: the board's built-in "Pull request merged"
        # workflow usually sets Done before this script runs. unlock() only moves Backlog tickets whose
        # dependencies are all Done, so repeating it is harmless.
        unlock(board)


def reconcile(board: Board, open_prs: List[dict]) -> None:
    """Repair pass: derive each card from the real state. Safe to run any time."""
    referenced: Set[int] = set()
    for pr in open_prs:
        for number in closing_issues(pr.get("body")):
            ticket = board.tickets.get(number)
            if ticket is None:
                continue
            referenced.add(number)
            if pr.get("isDraft"):
                move(board, ticket, "In progress", {"Backlog", "Ready"}, "open draft PR #%s" % pr.get("number"))
            else:
                move(board, ticket, "In review", OPEN_STATES, "open PR #%s" % pr.get("number"))
    for ticket in sorted(board.tickets.values(), key=lambda t: t.tid):
        if ticket.state == "CLOSED":
            move(board, ticket, "Done", NOT_DONE, "issue is closed")
        elif ticket.status == "In review" and ticket.number not in referenced:
            board.set_status(ticket, "In progress", "no open PR for it")
    unlock(board)


# ---- GitHub access -------------------------------------------------------------------------------

def gh(*args: str, project: bool = False) -> str:
    env = dict(os.environ)
    token = os.environ.get("PROJECT_TOKEN") if project else None
    if token:
        env["GH_TOKEN"] = token
    result = subprocess.run(["gh", *args], capture_output=True, text=True, env=env)
    if result.returncode != 0:
        sys.exit("gh %s failed: %s" % (" ".join(args[:3]), result.stderr.strip()))
    return result.stdout


class GitHubBoard(Board):
    def __init__(self, dry_run: bool):
        if os.environ.get("GITHUB_ACTIONS") and not os.environ.get("PROJECT_TOKEN"):
            sys.exit("PROJECT_TOKEN is not set. Create a classic personal access token with only the "
                     "`project` scope and store it: gh secret set PROJECT_TOKEN -R %s" % REPO)
        self.dry_run = dry_run
        issues = json.loads(gh("issue", "list", "-R", REPO, "--state", "all", "--limit", "300",
                               "--json", "number,title,body,state"))
        items = json.loads(gh("project", "item-list", PROJECT, "--owner", OWNER, "--limit", "300",
                              "--format", "json", project=True))["items"]
        by_number = {i["content"]["number"]: i for i in items if i.get("content")}
        tickets = []
        for issue in issues:
            title = TICKET_TITLE.match(issue["title"])
            item = by_number.get(issue["number"])
            if not title or item is None:
                continue
            body = issue["body"] or ""
            primary = PRIMARY.search(body)
            tickets.append(Ticket(issue["number"], title.group(1), [int(n) for n in DEPENDS.findall(body)],
                                  primary.group(1) if primary else None, issue["state"],
                                  item.get("status") or "Backlog", item["id"]))
        super().__init__(tickets)
        self.project_id = gh("project", "view", PROJECT, "--owner", OWNER, "--format", "json", "--jq", ".id",
                             project=True).strip()

    def set_status(self, ticket: Ticket, new: str, why: str) -> None:
        super().set_status(ticket, new, why)  # logs and updates the in-memory ticket
        if not self.dry_run:
            gh("project", "item-edit", "--id", ticket.item_id, "--project-id", self.project_id,
               "--field-id", STATUS_FIELD, "--single-select-option-id", OPTIONS[new], project=True)

    def comment(self, ticket: Ticket, text: str) -> None:
        super().comment(ticket, text)
        if not self.dry_run:
            gh("issue", "comment", str(ticket.number), "-R", REPO, "--body", text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="print what would change, change nothing")
    parser.add_argument("--event-name", help="override GITHUB_EVENT_NAME")
    parser.add_argument("--event-file", help="override GITHUB_EVENT_PATH")
    parser.add_argument("--reconcile", action="store_true", help="run the repair pass")
    args = parser.parse_args()

    name = "reconcile" if args.reconcile else (args.event_name or os.environ.get("GITHUB_EVENT_NAME", ""))
    event_path = args.event_file or os.environ.get("GITHUB_EVENT_PATH")
    event = {}
    if event_path and name not in ("schedule", "workflow_dispatch", "reconcile"):
        with open(event_path) as handle:
            event = json.load(handle)

    if name not in ("create", "pull_request_target", "pull_request", "schedule", "workflow_dispatch", "reconcile"):
        print("ignoring event %r" % name)
        return 0
    if name == "create" and event.get("ref_type") != "branch":
        print("ignoring: not a branch")
        return 0

    board = GitHubBoard(args.dry_run)
    if name == "create":
        on_branch_created(board, event.get("ref", ""), event.get("ref_type", ""))
    elif name in ("pull_request_target", "pull_request"):
        on_pull_request(board, event.get("action", ""), event.get("pull_request", {}))
    else:
        open_prs = json.loads(gh("pr", "list", "-R", REPO, "--state", "open", "--limit", "100",
                                 "--json", "number,body,isDraft"))
        reconcile(board, open_prs)

    prefix = "[dry-run] " if args.dry_run else ""
    lines = [prefix + line for line in board.log] or [prefix + "no board changes needed"]
    print("\n".join(lines))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as handle:
            handle.write("### Board automation\n\n" + "\n".join("- " + line for line in lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
