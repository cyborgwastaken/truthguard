#!/usr/bin/env bash
# Move a ticket's card on the "Virtusa TruthGuard" board.
# Usage: OPS/github/move_card.sh <issue-number> <backlog|ready|in-progress|in-review|done>
# Example: OPS/github/move_card.sh 4 done
set -euo pipefail

OWNER="cyborgwastaken"
PROJECT=3
STATUS_FIELD="PVTSSF_lAHOCDU-7c4BnxxizhmUzuQ"

issue="${1:?issue number required}"
case "${2:?status required}" in
  backlog)     option="f75ad846" ;;
  ready)       option="61e4505c" ;;
  in-progress) option="47fc9ee4" ;;
  in-review)   option="df73e18b" ;;
  done)        option="98236657" ;;
  *) echo "status must be one of: backlog ready in-progress in-review done" >&2; exit 1 ;;
esac

project_id=$(gh project view "$PROJECT" --owner "$OWNER" --format json --jq .id)
item_id=$(gh project item-list "$PROJECT" --owner "$OWNER" --limit 200 --format json \
  --jq ".items[] | select(.content.number==$issue) | .id")
[ -n "$item_id" ] || { echo "issue #$issue is not on the board" >&2; exit 1; }

gh project item-edit --id "$item_id" --project-id "$project_id" \
  --field-id "$STATUS_FIELD" --single-select-option-id "$option"
echo "issue #$issue -> $2"
