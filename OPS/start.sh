#!/usr/bin/env bash
# Start the whole TruthGuard demo: database, backend, sample documents and frontend.
#
#   OPS/start.sh        start everything (safe to run again)
#   OPS/stop.sh         stop it
#
# Needs: Docker Desktop (running), Node 20.19+, Python 3.12+. Logs and process ids go to .run/ (git-ignored).
#
# The language model:
#   GROQ_API_KEY set (environment or BACKEND/.env)  -> live answers
#   no key, but recorded replies exist               -> replay mode (answers are labelled "Replayed recording")
#   neither                                          -> the app starts, questions return a clear error
# Set TRUTHGUARD_LLM_MODE yourself to override.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
RUN="$ROOT/.run"
mkdir -p "$RUN"

step() { printf '\n==> %s\n' "$*"; }
die() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }
alive() { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null; }
wait_for() {  # wait_for <url> <seconds> <name>
  for _ in $(seq 1 "$2"); do curl -sf "$1" >/dev/null 2>&1 && return 0; sleep 1; done
  die "$3 did not start within $2 s. See the log in .run/"
}

step "Checking what is installed"
command -v docker >/dev/null 2>&1 || die "Docker is not installed. Install Docker Desktop and start it."
docker info >/dev/null 2>&1 || die "Docker is installed but not running. Open Docker Desktop, wait until it is ready, and run this again."
command -v node >/dev/null 2>&1 || die "Node.js is not installed. Install Node 20.19 or newer."
node -e 'const [a,b]=process.versions.node.split(".").map(Number); process.exit(a>20||(a===20&&b>=19)||a>22||(a===22&&b>=12)?0:1)' \
  || die "Node $(node --version) is too old. Install Node 20.19 or newer (22.12+ also works)."
PY=""
for candidate in python3.13 python3.12 python3.14 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then PY="$candidate"; break; fi
done
[ -n "$PY" ] || die "Python 3.12 or newer is needed. On a Mac: brew install python@3.12"
echo "docker ok, node $(node --version), $($PY --version)"

step "Python environment"
if [ -x .venv/bin/python ] && ! .venv/bin/python -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
  echo "The existing .venv uses an older Python; recreating it."
  rm -rf .venv
fi
[ -x .venv/bin/python ] || "$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
HASH="$(cat BACKEND/requirements.txt AGENT/pyproject.toml | shasum | cut -d' ' -f1)"
if [ "$(cat "$RUN/requirements.hash" 2>/dev/null || true)" != "$HASH" ]; then
  python -m pip install -q --upgrade pip
  (cd BACKEND && python -m pip install -q -r requirements.txt)
  echo "$HASH" > "$RUN/requirements.hash"
  echo "installed"
else
  echo "up to date"
fi

step "Database"
docker compose -f OPS/docker-compose.yml up -d --wait db >/dev/null
(cd BACKEND && alembic upgrade head 2>&1 | tail -1)

# Language model mode
if [ -z "${TRUTHGUARD_LLM_MODE:-}" ]; then
  KEY="${GROQ_API_KEY:-}"
  if [ -z "$KEY" ] && [ -f BACKEND/.env ]; then KEY="$(grep -E '^(GROQ_API_KEY|TRUTHGUARD_GROQ_API_KEY)=' BACKEND/.env | head -1 | cut -d= -f2- || true)"; fi
  if [ -n "$KEY" ]; then
    export TRUTHGUARD_LLM_MODE=live
  elif [ -s AGENT/datasets/recorded/replies.jsonl ]; then
    export TRUTHGUARD_LLM_MODE=replay
  else
    export TRUTHGUARD_LLM_MODE=live
    LLM_WARNING="No GROQ_API_KEY and no recorded replies: questions will return an error until a key is set."
  fi
fi

step "Backend"
if alive "$RUN/backend.pid"; then
  echo "already running (pid $(cat "$RUN/backend.pid")); stop it with OPS/stop.sh to change the model mode"
else
  # exec replaces the subshell with the server, so the saved pid is the server's and nothing keeps this
  # script's output open (a plain "a && b &" would, and a caller reading the output would wait forever)
  (cd BACKEND && exec nohup python -m uvicorn app.main:app --port 8000 > "$RUN/backend.log" 2>&1 < /dev/null) &
  echo $! > "$RUN/backend.pid"
fi
wait_for http://localhost:8000/health 40 "The backend"
curl -s http://localhost:8000/health; echo

step "Sample documents"
python OPS/load_fixtures.py

step "Frontend"
[ -d FRONTEND/node_modules ] || (cd FRONTEND && npm install --no-audit --no-fund >/dev/null 2>&1)
if alive "$RUN/frontend.pid"; then
  echo "already running (pid $(cat "$RUN/frontend.pid"))"
else
  (cd FRONTEND && exec nohup npm run dev -- --port 5173 --strictPort > "$RUN/frontend.log" 2>&1 < /dev/null) &
  echo $! > "$RUN/frontend.pid"
fi
wait_for http://localhost:5173 40 "The frontend"

printf '\n============================================================\n'
printf ' TruthGuard is running.\n'
printf '   App:      http://localhost:5173\n'
printf '   API docs: http://localhost:8000/docs\n'
printf '   Model:    %s mode\n' "${TRUTHGUARD_LLM_MODE:-live}"
[ -z "${LLM_WARNING:-}" ] || printf '   WARNING:  %s\n' "$LLM_WARNING"
printf '   Stop:     OPS/stop.sh      Clear old answers: OPS/reset_answers.sh\n'
printf '============================================================\n'
