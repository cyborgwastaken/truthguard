#!/usr/bin/env bash
# Stop the backend and frontend started by OPS/start.sh. The database keeps running unless you pass --db.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for name in frontend backend; do
  pidfile="$ROOT/.run/$name.pid"
  if [ -f "$pidfile" ]; then
    pid="$(cat "$pidfile")"
    # kill the process and anything it started (npm starts vite, which starts node)
    pkill -P "$pid" 2>/dev/null; kill "$pid" 2>/dev/null && echo "stopped $name"
    rm -f "$pidfile"
  fi
done
pkill -f "vite --port 5173" 2>/dev/null
[ "${1:-}" = "--db" ] && docker compose -f "$ROOT/OPS/docker-compose.yml" stop db && echo "stopped db (data kept)"
exit 0
