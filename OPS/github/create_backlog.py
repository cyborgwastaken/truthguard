#!/usr/bin/env python3
"""Create the TruthGuard backlog as GitHub issues and add them to the project board.

Usage:
  python OPS/github/create_backlog.py --dry-run    # print the plan only
  python OPS/github/create_backlog.py              # create labels, milestones, issues, board items
  python OPS/github/create_backlog.py --assign     # assign issues to primary devs (after invites are accepted)
  python OPS/github/create_backlog.py --reassign   # re-sync body, labels, assignees after role changes

Requires `gh` authenticated with repo and project scopes. Issues are created in ID order so
dependency references (#N) resolve to real issue numbers.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

REPO = "cyborgwastaken/truthguard"
OWNER = "cyborgwastaken"
PROJECT = 3
STATUS_FIELD = "PVTSSF_lAHOCDU-7c4BnxxizhmUzuQ"
STATUS = {"Backlog": "f75ad846", "Ready": "61e4505c", "Done": "98236657"}

ME, SARIK, YASH, ASHWANI, DHRUV = "cyborgwastaken", "iamsarik", "yashdiwan12", "AshwaniArya2005", "dhruvt293"

# role number -> (label, role name, primary dev, secondary devs)
ROLES = {
    1: ("role:1-backend-database", "Backend and Database", ME, [YASH]),
    2: ("role:2-retrieval-ai", "Retrieval and AI Pipeline", ASHWANI, [ME, YASH]),
    3: ("role:3-verification", "Verification", YASH, [ASHWANI]),
    4: ("role:4-frontend", "Frontend", SARIK, [ME]),
    5: ("role:5-data-eval-demo", "Data, Evaluation and Demo", DHRUV, [SARIK]),
}
OLD_LABELS = ["role:backend-agents", "role:verification", "role:frontend", "role:corpus-benchmark", "role:dashboard-docs-demo"]
WAVES = {
    0: "Wave 0: Scaffold",
    1: "Wave 1: Foundation",
    2: "Wave 2: Core pipeline",
    3: "Wave 3: Verification",
    4: "Wave 4: Showcase",
    5: "Wave 5: Demo readiness",
    6: "Post-hackathon",
}

# (id, wave, role number, title, depends_on, done_when)
T = [
    ("T00", 0, 1, "Repo scaffold, shared schemas, /health", [], "Folders, schemas and health endpoint merged with passing tests."),
    ("T01", 1, 5, "Fictional corpus with labeled cases", ["T00"], "15-30 docs in AGENT/datasets covering superseded, unresolved-conflict, insufficient-evidence and hard-negative cases, each with an expected-outcome label."),
    ("T02", 1, 2, "Ingestion: normalize, chunk, hash", ["T00"], "Text is chunked with stable chunk IDs and offsets; content hash stored; unit tests pass."),
    ("T03", 1, 1, "Postgres, models and migrations", ["T00"], "Docker Compose starts Postgres; models/migrations for Document, Chunk, Answer, Claim, EvidenceLink apply cleanly."),
    ("T04", 1, 4, "Frontend scaffold (Vite + React + TS)", ["T00"], "App runs, API client calls /health, layout shell in FRONTEND."),
    ("T05", 1, 3, "Resolver rules design doc", ["T00"], "DOCS page defines supersession, effective-date, authority and abstention rules with worked examples."),
    ("T06", 2, 1, "POST/GET /documents", ["T02", "T03"], "Documents ingest and list via API with metadata; tests pass."),
    ("T07", 2, 2, "Keyword/full-text retriever", ["T02", "T03"], "Returns ranked passages with IDs, metadata and scores; retrieval recall measured on the corpus."),
    ("T08", 2, 2, "Synthesizer with claim-level citations", ["T07"], "Pydantic-validated claims each carry citation IDs; one retry then safe failure."),
    ("T09", 2, 3, "Resolver engine", ["T05"], "Deterministic rules yield resolved / conflict_unresolved / insufficient_evidence; unit tests per rule."),
    ("T10", 2, 5, "Baseline RAG", ["T07"], "Retrieve-and-answer baseline with no critic, runnable on the benchmark cases."),
    ("T11", 2, 4, "Chat UI and document list/upload", ["T04", "T06"], "User can upload a document and ask a question from the UI."),
    ("T12", 3, 3, "Critic agent", ["T08"], "Returns contradictions, staleness and unsupported claims, each with evidence refs; fixture tests pass."),
    ("T13", 3, 2, "Orchestrator", ["T08", "T09", "T12"], "retrieve -> synthesize -> critic -> resolve with explicit failure states; timeouts never read as success."),
    ("T14", 3, 1, "POST /questions and GET /answers/{id}", ["T13"], "Answers persist and are retrievable with claims and evidence links."),
    ("T15", 3, 3, "Evidence graph assembler and endpoint", ["T12", "T14"], "GET /answers/{id}/evidence-graph returns claims, links and conflicts; tested against fixtures."),
    ("T16", 3, 5, "Benchmark dataset v1 and metric functions", ["T01", "T10"], "Versioned labeled set plus functions for recall, contradiction P/R, citation support, abstention and resolution accuracy."),
    ("T17", 3, 4, "Answer view with citations and conflict comparison", ["T11", "T14"], "Shows answer, status, citations, source passage and side-by-side conflicting passages."),
    ("T18", 4, 3, "Trust report builder and endpoint", ["T15"], "Dimensions with documented formulas and denominators; unknown metadata reported as unknown; tests on fixed examples."),
    ("T19", 4, 5, "Benchmark runner (3 configs)", ["T13", "T16"], "Runs baseline, RAG+critic and full TruthGuard on the same cases; per-case results recorded."),
    ("T20", 4, 4, "Evidence graph UI", ["T15", "T17"], "Claims, evidence and conflicts visible; clicking a node opens the source passage."),
    ("T21", 4, 4, "Trust report panel", ["T18"], "Dimensions shown separately with definitions; no single trust score."),
    ("T22", 4, 4, "Benchmark dashboard", ["T19"], "Compare configs and drill into failed cases with retrieved passages and outputs."),
    ("T23", 4, 2, "Prompt-injection hardening", ["T13"], "Retrieved text treated as untrusted; injection fixtures do not change behaviour."),
    ("T24", 4, 1, "Persist evaluation runs", ["T19"], "Run config, dataset version, metrics and per-case results stored and queryable."),
    ("T25", 5, 5, "Record real results and evaluation methodology doc", ["T19"], "Measured results recorded; no improvement claimed beyond the data."),
    ("T26", 5, 4, "Loading/error states and metadata display", ["T20", "T21"], "UI handles loading, errors and shows version/date metadata."),
    ("T27", 5, 1, "Setup docs and one-command start", ["T24"], "Fresh clone runs via documented commands; architecture doc in DOCS."),
    ("T28", 5, 5, "Demo script, rehearsal, fallback recording", ["T25", "T26"], "Repeatable demo of the three required scenarios from a clean start."),
    ("T29", 6, None, "Counterfactual verification", [], "Post-hackathon. See DOCS/truthguard_expansion_roadmap.md, Feature D."),
    ("T30", 6, None, "Human review workflow with auth and audit log", [], "Post-hackathon. See Feature E."),
    ("T31", 6, None, "Continuous monitoring and change-impact reports", [], "Post-hackathon. See Feature F."),
]


def gh(*args, check=True):
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit("gh %s failed: %s" % (" ".join(args[:3]), r.stderr.strip()))
    return r.stdout.strip()


def initial_status(wave, deps):
    if wave == 0:
        return "Done"
    return "Ready" if wave == 1 else "Backlog"


def people(role):
    if role is None:
        return None, []
    return ROLES[role][2], ROLES[role][3]


def body(t, nums):
    tid, wave, role, title, deps, done = t
    primary, secondary = people(role)
    if role:
        who = "**Role:** %d, %s  \n**Primary:** @%s  \n**Secondary:** %s" % (
            role, ROLES[role][1], primary, ", ".join("@" + x for x in secondary))
    else:
        who = "**Role:** unassigned"
    lines = ["**Ticket:** %s  \n**Wave:** %s  \n%s" % (tid, WAVES[wave], who)]
    lines.append("\n**Depends on:** " + (", ".join("#%d (%s)" % (nums[d], d) for d in deps) if deps else "none"))
    lines.append("\n**Done when:** " + done)
    lines.append("\n_Review: cyborgwastaken reviews every ticket before it moves to Done._")
    return "\n".join(lines)


def reassign_mode():
    """Rewrite body, role label and assignee of existing issues from the T table."""
    issues = json.loads(gh("issue", "list", "-R", REPO, "--state", "all", "--limit", "200", "--json", "number,title,labels,assignees"))
    nums = {i["title"].split(":")[0]: i["number"] for i in issues}
    by_num = {i["number"]: i for i in issues}
    for label, *_ in ROLES.values():
        gh("label", "create", label, "-R", REPO, "--force", "--color", "5319e7")
    for t in T:
        tid, _, role, *_ = t
        n = nums[tid]
        cur = by_num[n]
        cmd = ["issue", "edit", str(n), "-R", REPO, "--body", body(t, nums)]
        for l in cur["labels"]:
            if l["name"] in OLD_LABELS or (l["name"].startswith("role:") and role and l["name"] != ROLES[role][0]):
                cmd += ["--remove-label", l["name"]]
        if role:
            cmd += ["--add-label", ROLES[role][0]]
        for a in cur["assignees"]:
            cmd += ["--remove-assignee", a["login"]]
        gh(*cmd)
        if role:
            r = subprocess.run(["gh", "issue", "edit", str(n), "-R", REPO, "--add-assignee", ROLES[role][2]],
                               capture_output=True, text=True)
            note = "" if r.returncode == 0 else "  (assignee not set: %s)" % r.stderr.strip().splitlines()[-1]
        else:
            note = ""
        print("%s -> role %s%s" % (tid, role, note))
    for old in OLD_LABELS:
        subprocess.run(["gh", "label", "delete", old, "-R", REPO, "--yes"], capture_output=True)


def assign_mode():
    issues = json.loads(gh("issue", "list", "-R", REPO, "--state", "all", "--limit", "200", "--json", "number,title"))
    by_prefix = {i["title"].split(":")[0]: i["number"] for i in issues}
    for tid, _, role, *_ in T:
        if role and tid in by_prefix:
            r = subprocess.run(["gh", "issue", "edit", str(by_prefix[tid]), "-R", REPO, "--add-assignee", ROLES[role][2]],
                               capture_output=True, text=True)
            print(tid, "->", ROLES[role][2], "ok" if r.returncode == 0 else "FAILED: " + r.stderr.strip().splitlines()[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--assign", action="store_true")
    ap.add_argument("--reassign", action="store_true", help="re-sync body, labels and assignees of existing issues")
    a = ap.parse_args()
    if a.assign:
        return assign_mode()
    if a.reassign:
        return reassign_mode()
    if a.dry_run:
        for tid, wave, role, title, deps, _ in T:
            owner = ROLES[role][2] if role else None
            print("%s  W%d  %-16s %s  deps=%s  -> %s" % (tid, wave, owner or "-", title, ",".join(deps) or "-", initial_status(wave, deps)))
        return

    for label in [r[0] for r in ROLES.values()] + ["post-hackathon"]:
        gh("label", "create", label, "-R", REPO, "--force", "--color", "5319e7")
    for w in WAVES.values():
        gh("api", "repos/%s/milestones" % REPO, "-f", "title=" + w, check=False)

    existing = {i["title"].split(":")[0]: i for i in json.loads(
        gh("issue", "list", "-R", REPO, "--state", "all", "--limit", "200", "--json", "number,title,url"))}
    items = json.loads(gh("project", "item-list", str(PROJECT), "--owner", OWNER, "--limit", "200", "--format", "json"))["items"]
    item_by_num = {i["content"]["number"]: i for i in items if i.get("content")}
    pid = gh("project", "view", str(PROJECT), "--owner", OWNER, "--format", "json", "--jq", ".id")

    nums = {}
    for t in T:
        tid, wave, role, title, deps, _ = t
        if tid in existing:
            nums[tid] = existing[tid]["number"]
            url = existing[tid]["url"]
            fresh = False
        else:
            labels = [ROLES[role][0]] if role else ["post-hackathon"]
            cmd = ["issue", "create", "-R", REPO, "--title", "%s: %s" % (tid, title), "--body", body(t, nums),
                   "--milestone", WAVES[wave]]
            for l in labels:
                cmd += ["--label", l]
            url = gh(*cmd)
            nums[tid] = int(url.rsplit("/", 1)[1])
            fresh = True
            if wave == 0:
                gh("issue", "close", str(nums[tid]), "-R", REPO)
        item = item_by_num.get(nums[tid])
        if item is None:
            r = subprocess.run(["gh", "project", "item-add", str(PROJECT), "--owner", OWNER, "--url", url,
                                "--format", "json"], capture_output=True, text=True)
            if r.returncode == 0:
                item = json.loads(r.stdout)
            else:  # auto-add rule got there first; its item can take a moment to show up in the list
                for _ in range(10):
                    items = json.loads(gh("project", "item-list", str(PROJECT), "--owner", OWNER, "--limit", "200", "--format", "json"))["items"]
                    item = next((i for i in items if i.get("content", {}).get("number") == nums[tid]), None)
                    if item:
                        break
                    time.sleep(2)
                else:
                    sys.exit("%s: board item not found for %s" % (tid, url))
        if fresh or not item.get("status"):
            gh("project", "item-edit", "--id", item["id"], "--project-id", pid,
               "--field-id", STATUS_FIELD, "--single-select-option-id", STATUS[initial_status(wave, deps)])
        print("created" if fresh else "kept   ", tid, "->", url)

if __name__ == "__main__":
    main()
