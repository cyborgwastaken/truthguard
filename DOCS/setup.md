# Setup Guide

Follow this once to get TruthGuard running on your computer. It takes about 15 minutes. If a step fails, check "Troubleshooting" at the bottom, then ask for help with the exact error text.

## 1. What you need installed

| Tool | Version | Check with | Get it |
|---|---|---|---|
| Git | any recent | `git --version` | https://git-scm.com |
| Python | 3.9 or newer | `python3 --version` | https://www.python.org |
| Docker Desktop | any recent | `docker --version` | https://www.docker.com/products/docker-desktop |
| Node.js | 20.19 or newer (only for the frontend) | `node --version` | https://nodejs.org |

**Docker Desktop must be running** (open the app and wait until it says it is running) before step 4.

## 2. Get the code

```bash
git clone https://github.com/cyborgwastaken/truthguard.git
cd truthguard
```

You need to be a collaborator on the repo. If the clone is refused, accept your GitHub invitation first.

## 3. Python environment

Run these from the repo root (`truthguard/`).

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install --upgrade pip          # old pip versions can fail on the next command
cd BACKEND
pip install -r requirements.txt    # must be run from inside BACKEND/
```

Your terminal prompt now starts with `(.venv)`. **Every new terminal needs `source .venv/bin/activate` again** (run from the repo root).

## 4. Start the database

From the repo root:

```bash
docker compose -f OPS/docker-compose.yml up -d
```

The first run downloads the Postgres image (a minute or two). Check it is healthy:

```bash
docker compose -f OPS/docker-compose.yml ps
```

The `STATUS` column should say `healthy`.

The database listens on **port 5433** on your computer (not the usual 5432, so it does not clash with a Postgres you may have installed). Credentials for local development: user `truthguard`, password `truthguard`, database `truthguard`.

## 5. Create the tables

```bash
cd BACKEND
alembic upgrade head
```

You should see `Running upgrade  -> 0001, initial schema`. Running it again is safe; it just reports nothing to do.

## 6. Check everything works

```bash
# from BACKEND/
python -m pytest            # backend tests (database tests need step 4 and 5)
cd ../AGENT && python -m pytest
```

Both should pass. If the database tests are reported as **skipped**, the database is not running or step 5 was not done; the skip message tells you the command to fix it.

## 7. Run the backend

```bash
cd BACKEND
uvicorn app.main:app --reload
```

Open http://localhost:8000/health. It should show `{"status":"ok"}`. Open http://localhost:8000/docs to see all API endpoints and try them out. Stop the server with `Ctrl+C`.

## 8. Run the frontend

Start the backend (step 7) in one terminal, then in a second terminal:

```bash
cd FRONTEND
npm install
npm run dev
```

Open http://localhost:5173. The top bar should show **Backend: connected** (green dot). It shows **Backend: offline** (red dot) if the backend is not running. More detail in [FRONTEND/README.md](../FRONTEND/README.md).

## 9. Your daily routine

Start of a work session:

```bash
cd truthguard
git checkout main && git pull
source .venv/bin/activate
docker compose -f OPS/docker-compose.yml up -d
cd BACKEND && pip install -r requirements.txt && alembic upgrade head
```

Running `pip install` and `alembic upgrade head` after each `git pull` picks up new dependencies and new database tables that teammates added.

End of the day, if you want to free up resources: `docker compose -f OPS/docker-compose.yml stop`. Your data stays.

## 10. Settings

Defaults work out of the box. To change a setting, create `BACKEND/.env` (it is git-ignored, never commit it):

```text
TRUTHGUARD_DATABASE_URL=postgresql+psycopg://truthguard:truthguard@localhost:5433/truthguard
TRUTHGUARD_CORS_ORIGINS=http://localhost:5173
```

The language-model key (needed from ticket T08 on) is **not** read from `.env`. Set it in your terminal before starting the backend: `export ANTHROPIC_API_KEY=your-key-here` (Windows PowerShell: `$env:ANTHROPIC_API_KEY="your-key-here"`). Never put it in a file that is committed.

To use a different database port, start Docker with `TRUTHGUARD_DB_PORT=5440 docker compose -f OPS/docker-compose.yml up -d` and set the same port in `TRUTHGUARD_DATABASE_URL`.

## 11. Resetting the database

To wipe all data and start fresh (this deletes everything stored locally):

```bash
docker compose -f OPS/docker-compose.yml down -v
docker compose -f OPS/docker-compose.yml up -d
cd BACKEND && alembic upgrade head
```

## Database changes (for developers who add tables)

Edit `BACKEND/app/db/models.py`, then generate a migration and review the file it creates in `BACKEND/alembic/versions/` before committing:

```bash
cd BACKEND
alembic revision --autogenerate -m "short description"
alembic upgrade head
alembic check            # should say: No new upgrade operations detected
```

Never edit a migration that has already been merged; add a new one.

## Troubleshooting

| Problem | Fix |
|---|---|
| `Cannot connect to the Docker daemon` / `failed to connect to the docker API` | Docker Desktop is not running. Open it and wait until it is ready. |
| `port is already allocated` on 5433 | Something else uses that port. Use another one (see step 10). |
| `connection refused` when running `alembic` or tests | The database is not up. Run step 4 and check `docker compose ... ps` shows `healthy`. |
| `password authentication failed` | You have a different Postgres on the same port, or an old volume with different credentials. Use the reset in step 11. |
| `ModuleNotFoundError: truthguard_agent` or `app` | The venv is not active, or `pip install -r requirements.txt` was run outside `BACKEND/`. Redo step 3. |
| `ERROR: ../AGENT is not a valid editable requirement` | Run `pip install -r requirements.txt` from inside `BACKEND/`. |
| `File "setup.py" or "setup.cfg" not found` | Old pip. Run `pip install --upgrade pip`, then retry. |
| `command not found: alembic` / `pytest` | Activate the venv: `source .venv/bin/activate`. |
| `Can't locate revision` | Your database was migrated by a different branch. Use the reset in step 11. |
| Database tests show `SKIPPED` | Database not running or tables missing. Follow the message in the skip reason. |
| Windows: `Activate.ps1 cannot be loaded` | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then retry. |

Still stuck? Comment on your ticket's GitHub issue with the exact command you ran and the full error text.
