# TruthGuard Frontend

React + TypeScript, built with Vite. Needs Node.js 20.19 or newer.

## Run

```bash
cd FRONTEND
npm install
npm run dev          # http://localhost:5173
```

The page talks to the backend at `http://localhost:8000` (start it with `cd BACKEND && uvicorn app.main:app --reload`; see [DOCS/setup.md](../DOCS/setup.md)). The top bar shows **Backend: connected** or **Backend: offline**.

To use another backend address, copy `.env.example` to `.env.local` and change `VITE_API_URL`.

## Commands

| Command | What it does |
|---|---|
| `npm run dev` | Dev server with hot reload |
| `npm run build` | Type-check and build to `dist/` |
| `npm run lint` | Lint the code |

Run `npm run build` and `npm run lint` before opening a PR.

## Layout

```text
src/
  api/          # functions that call the backend (client.ts)
  components/   # small reusable pieces (TopBar)
  features/     # one folder per feature: chat/, documents/, health/ ...
  types/        # TypeScript types that mirror the backend models
```

Calls to the backend go through `src/api/client.ts` only. Chat and Documents are placeholder pages until ticket T11.
