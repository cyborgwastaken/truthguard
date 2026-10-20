#!/usr/bin/env python3
"""Regenerate the status section of DOCS/progress.md from the GitHub board.

Usage (from the repo root, after a merge):
  python3 OPS/github/update_progress.py

Only the text between the BEGIN/END GENERATED markers is replaced. The "Decisions and notes"
section below it is written by hand and is never touched. Requires `gh` with repo and project scopes.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
from datetime import date

REPO = "cyborgwastaken/truthguard"
OWNER = "cyborgwastaken"
PROJECT = "3"
OUT = pathlib.Path(__file__).resolve().parents[2] / "DOCS" / "progress.md"
BEGIN = "<!-- BEGIN GENERATED (OPS/github/update_progress.py) -->"
END = "<!-- END GENERATED -->"
COLUMNS = ["Done", "In review", "In progress", "Ready", "Backlog"]

TEMPLATE = """# Project Progress

Current state of the TruthGuard build. The status section below is **generated from the GitHub board**; do not edit it by hand. Regenerate it after each merge:

```bash
python3 OPS/github/update_progress.py
```

The notes section at the bottom is written by hand: decisions, reasons and open questions.

{begin}
{end}

## Decisions and notes

Newest first. One entry per decision, with the reason. Add an entry whenever something is decided that a newcomer (or an AI agent) could not work out from the code.
"""


def gh(*args: str) -> str:
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("gh %s failed: %s" % (" ".join(args[:3]), r.stderr.strip()))
    return r.stdout


def ticket_id(title: str) -> str:
    return title.split(":", 1)[0].strip()


def main() -> None:
    issues = json.loads(gh("issue", "list", "-R", REPO, "--state", "all", "--limit", "200",
                           "--json", "number,title,body,state,milestone,assignees"))
    items = json.loads(gh("project", "item-list", PROJECT, "--owner", OWNER, "--limit", "200",
                          "--format", "json"))["items"]
    status_by_number = {i["content"]["number"]: i.get("status") or "Backlog" for i in items if i.get("content")}
    prs = json.loads(gh("pr", "list", "-R", REPO, "--state", "open",
                        "--json", "number,title,author,reviewDecision,isDraft"))

    tickets = {}
    for i in issues:
        tid = ticket_id(i["title"])
        if not re.fullmatch(r"T\d\d", tid):
            continue
        body = i["body"] or ""
        primary = re.search(r"\*\*Primary:\*\* @(\S+)", body)
        # An actual assignee (for example someone covering for the primary) wins over the role's primary.
        who = i["assignees"][0]["login"] if i["assignees"] else (primary.group(1) if primary else "unassigned")
        deps = [int(n) for n in re.findall(r"#(\d+) \(T\d\d\)", body)]
        tickets[i["number"]] = {
            "id": tid,
            "number": i["number"],
            "title": i["title"].split(":", 1)[1].strip(),
            "owner": who,
            "status": status_by_number.get(i["number"], "Backlog"),
            "wave": (i["milestone"] or {}).get("title", "No wave"),
            "deps": deps,
        }
    ordered = sorted(tickets.values(), key=lambda t: t["id"])

    def waiting_on(t):
        return [tickets[d]["id"] for d in t["deps"] if d in tickets and tickets[d]["status"] != "Done"]

    total = len(ordered)
    counts = {c: sum(1 for t in ordered if t["status"] == c) for c in COLUMNS}
    done = counts["Done"]

    out = ["## Status (generated %s)" % date.today().isoformat(), ""]
    out.append("**%d of %d tickets done.** %s" % (done, total, " · ".join("%s %d" % (c, counts[c]) for c in COLUMNS)))
    out.append("")

    ready = [t for t in ordered if t["status"] == "Ready"]
    out.append("### Ready to start")
    out.append("")
    out += ["- #%d %s: %s (@%s)" % (t["number"], t["id"], t["title"], t["owner"]) for t in ready] or ["- nothing is ready"]
    out.append("")

    active = [t for t in ordered if t["status"] in ("In progress", "In review")]
    out.append("### In flight")
    out.append("")
    out += ["- #%d %s: %s (@%s), %s" % (t["number"], t["id"], t["title"], t["owner"], t["status"].lower()) for t in active] or ["- nothing in flight"]
    out.append("")

    out.append("### Open pull requests")
    out.append("")
    for p in prs:
        decision = (p["reviewDecision"] or "no review yet").lower().replace("_", " ")
        draft = ", draft" if p["isDraft"] else ""
        out.append("- #%d %s (@%s): %s%s" % (p["number"], p["title"], p["author"]["login"], decision, draft))
    if not prs:
        out.append("- none")
    out.append("")

    unblocked_but_backlog = [t for t in ordered if t["status"] == "Backlog" and t["deps"] and not waiting_on(t)]
    if unblocked_but_backlog:
        out.append("### Unblocked but still in Backlog (move to Ready)")
        out.append("")
        out += ["- #%d %s: %s (@%s)" % (t["number"], t["id"], t["title"], t["owner"]) for t in unblocked_but_backlog]
        out.append("")

    out.append("### All tickets")
    out.append("")
    out.append("| Ticket | Issue | Title | Owner | Status | Waiting on |")
    out.append("|---|---|---|---|---|---|")
    last_wave = None
    for t in ordered:
        if t["wave"] != last_wave:
            out.append("| **%s** | | | | | |" % t["wave"])
            last_wave = t["wave"]
        waits = ", ".join(waiting_on(t)) if t["status"] not in ("Done",) else ""
        out.append("| %s | #%d | %s | @%s | %s | %s |" % (t["id"], t["number"], t["title"], t["owner"], t["status"], waits or "-"))
    generated = "\n".join(out)

    text = OUT.read_text() if OUT.exists() else TEMPLATE.format(begin=BEGIN, end=END)
    if BEGIN not in text or END not in text:
        sys.exit("markers missing in %s" % OUT)
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    OUT.write_text("%s%s\n%s\n%s%s" % (head, BEGIN, generated, END, tail))
    print("updated %s: %d/%d done, %d ready, %d in flight" % (OUT.relative_to(OUT.parents[1]), done, total, counts["Ready"], len(active)))


if __name__ == "__main__":
    main()
