#!/usr/bin/env python3
"""Upload the fictional T01 fixture documents to a running TruthGuard backend.

Usage (backend must be running, see DOCS/setup.md):
  python3 OPS/load_fixtures.py                          # http://localhost:8000
  python3 OPS/load_fixtures.py --api http://localhost:8010

Safe to run repeatedly: documents that are already stored are reported as unchanged.
Needs only the Python standard library.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.error
import urllib.request

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "AGENT" / "datasets" / "fixtures"


def post(api: str, payload: dict):
    request = urllib.request.Request(
        api.rstrip("/") + "/documents",
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, ""
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--api", default="http://localhost:8000", help="backend address")
    args = parser.parse_args()

    files = sorted(FIXTURES.glob("*.json"))
    if not files:
        print("no fixture files found in %s" % FIXTURES, file=sys.stderr)
        return 1
    created = unchanged = failed = 0
    for path in files:
        try:
            status, detail = post(args.api, json.loads(path.read_text()))
        except (urllib.error.URLError, OSError) as error:
            print("cannot reach %s: %s\nIs the backend running? (cd BACKEND && uvicorn app.main:app)" % (args.api, error), file=sys.stderr)
            return 1
        if status == 201:
            created += 1
        elif status == 200:
            unchanged += 1
        else:
            failed += 1
            print("FAILED %s: HTTP %d %s" % (path.name, status, detail), file=sys.stderr)
    print("%d fixtures: %d created, %d unchanged, %d failed" % (len(files), created, unchanged, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
