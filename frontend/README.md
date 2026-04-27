# Emet frontend

Next.js 14 (App Router) app: Clerk auth, **`/check`** fact-check workspace, SSE + poll for job progress, citation UI.

## Documentation

- **Product architecture, API, env vars, MCP (search backends), deployment** — see the repository root **[`../README.md`](../README.md)**.
- **Backend-only concerns** (Postgres, `uvicorn`, OpenRouter, `EMET_MCP_*`, workers) are documented there; this folder covers the browser app.

## Local setup

```bash
cp .env.local.example .env.local
npm install
npm run dev
```

Point **`NEXT_PUBLIC_API_URL`** at your FastAPI origin (default `http://localhost:8000`). Clerk keys must match the same Clerk application as the API’s **`CLERK_JWKS_URL`** / **`CLERK_SECRET_KEY`**.

## Scripts

| Command | Purpose |
|---------|---------|
| `npm run dev` | Dev server |
| `npm run build` | Production build |
| `npm run lint` | ESLint |
| `npm run test` | Unit tests |

CI runs the same checks from the repo root **`.github/workflows/ci.yml`**.
