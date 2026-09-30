# React + FastAPI Monorepo

JavaScript React (Vite) frontend + FastAPI backend, with dev proxy wiring.

## Structure

```
.
├── backend/     # FastAPI (uv + ruff + pyright)
├── frontend/    # React + Vite (JavaScript)
├── scripts/     # dev.ps1 — start both servers without hanging
└── README.md
```

## Prerequisites

- [Node.js](https://nodejs.org/) 20+
- [uv](https://docs.astral.sh/uv/)

## Backend

```bash
cd backend
uv sync
uv run uvicorn backend.main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- Example endpoints: `GET /api/health`, `GET /api/hello?name=...`

Lint / type-check:

```bash
cd backend
uv run ruff check src/
uv run ruff format src/
uv run pyright src/
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

- App: http://localhost:5173
- Vite proxies `/api/*` → `http://localhost:8000`

## Dev workflow

One shot (starts both, waits until ready):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1
```

Or manually:

1. Start backend on port 8000 (terminal 1)
2. Start frontend on port 5173 (terminal 2)
3. Open http://localhost:5173 — the page calls `/api/health` and `/api/hello`

Note: on Windows, start long-running servers without `Start-Process -RedirectStandardOutput/-NoNewWindow` (that hangs the shell). Prefer `scripts/dev.ps1`. `npm` is a `.cmd` shim — wrap it as `cmd /c npm run dev`.
