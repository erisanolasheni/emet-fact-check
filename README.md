# Emet (אמת)

**Emet** (*truth* in Hebrew) is a capstone **LLM fact-checking** application: users submit a question or claim, the system **searches the open web** (OpenAI **hosted web search**, **DuckDuckGo** when using an OpenAI-compatible gateway such as **OpenRouter**, or **your own MCP servers**), **compares** multiple result digests, and returns a **structured report** with **cited sources**, **verdict-style fact rows**, and a **model-assisted confidence score**—with **live progress** over **Server-Sent Events (SSE)** and **Clerk** for authentication and (optionally) paid access.

This document explains **what Emet entails** and **how it works** end to end.

---

## What Emet entails

| Area | What you get |
|------|----------------|
| **User experience** | Web app: sign in (Clerk) → **`/check`** fact-check workspace → enter a question → watch **progress** (phases, %, stepper) → read **summary**, **facts** with **citation chips**, **reference cards** (favicon, title, hostname, snippet, outbound link), and **confidence** with rationale and limitations. (Billing gate is **off** by default right now; see `app/check/page.tsx` + `factcheck` router to turn it back on.) |
| **Evidence** | Multiple **parallel research passes** guided by a **planner** agent, then a **writer** agent that emits **stable source IDs** and **`source_ids` per fact** so the UI can link citations without fragile URL string matching. Search backends are **pluggable** (OpenAI web tool, DuckDuckGo, or **MCP**). |
| **Confidence** | A single **0–100** score plus **rationale** and **limitations**. This is **not** statistical truth—it reflects agreement across digests, source tiers, and gaps (disclosed in UI copy). |
| **Progress** | Each job stores **`progress`** JSON in the DB (phase, message, optional %, optional steps). The API **streams** updates via SSE (implementation **polls the DB** from the stream handler—simple and portable). |
| **Paid usage (when enabled)** | Re-wrap **`/check`** with **`FactCheckSubscriptionGate`** and change **`POST /api/fact-check`** to **`Depends(require_premium)`**. Subscription checks use Clerk **`GET /v1/users/{id}/billing/subscription`** (see Clerk Billing docs) with **`CLERK_SECRET_KEY`**, with a legacy commerce list fallback. Use one **Clerk application** for `CLERK_SECRET_KEY`, `CLERK_JWKS_URL`, and `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`. |
| **Deployment flexibility** | **Default**: pipeline runs **in-process** after `POST` (FastAPI `BackgroundTasks`). **Optional**: enqueue **`SQS`** and run `worker_sqs.py` (or Lambda) for heavier production separation. |

---

## How it works (architecture)

### Logical architecture

End-to-end data flow: the UI talks to FastAPI with a Clerk JWT; jobs and **`progress`** live in the database; the fact-check **pipeline** (planner → parallel **search** → writer) runs **in-process** by default or can be **offloaded** via **SQS** + `worker_sqs.py`. SSE is implemented by **polling the job row** in the stream handler.

```mermaid
flowchart TB
  Browser[Browser]
  Clerk[Clerk]
  Next[Next.js App Router]
  API[FastAPI]
  DB[(Postgres or SQLite)]
  SSE[SSE GET /api/jobs/id/stream]
  Pipe[Pipeline runner]
  Plan[Planner agent]
  Sea[Search layer]
  Wr[Writer agent]
  LLM[(OpenAI / OpenRouter)]
  Ext[Web evidence: CSE / DDG / MCP / legacy tools]

  Browser --> Clerk
  Browser --> Next
  Next -->|"REST + Bearer JWT"| API
  Next --> SSE
  API <--> DB
  SSE -->|"polls job"| DB
  API -->|"BackgroundTasks or SQS send"| Pipe
  Pipe --> Plan
  Plan --> Sea
  Sea --> Wr
  Plan --> LLM
  Sea --> Ext
  Sea --> LLM
  Wr --> LLM
  Pipe -->|"progress JSON + report_payload"| DB
```

### Production deployment (reference)

Typical AWS layout: **ECR** hosts **`emet-frontend`** and **`emet-backend`** images; **App Runner** runs both services (**3000** / **8000**). **RDS Postgres** (or Aurora) holds job rows. Optionally **SQS** + a **worker** process repeats the same pipeline for scale; **Terraform** in this repo can add **SQS**, **S3**, and **CloudFront** for a static or alternate UI delivery path (see [`terraform/README.md`](terraform/README.md)).

```mermaid
flowchart LR
  subgraph Users
    U[Browser users]
  end
  subgraph AWS["AWS"]
    ECR[ECR]
    FR[App Runner frontend]
    BK[App Runner backend]
    RDS[(RDS Postgres)]
    Q[SQS optional]
    WK[worker_sqs optional]
    TF[Terraform: CloudFront + S3 optional]
  end
  U --> FR
  FR -->|"HTTPS API"| BK
  BK --> RDS
  BK -.->|"if configured"| Q
  Q -.-> WK
  WK -.-> RDS
  ECR -.-> FR
  ECR -.-> BK
  TF -.->|"static assets"| U
```

### Request lifecycle

1. **Authenticate** — Clerk issues a session; the frontend sends **`Authorization: Bearer <JWT>`** to the API.
2. **Authorize** — Clerk session; **`POST /api/fact-check`** uses **`require_premium`**: when **`REQUIRE_SUBSCRIPTION=false`**, any signed-in user may run jobs; when **`true`**, Clerk Billing must show the configured premium plan.
3. **Create job** — `POST /api/fact-check` inserts a row: `status=pending`, `request_payload.question`, initial `progress`.
4. **Run pipeline** — Worker loads the question, runs **planner → N parallel searches → writer**, persisting **`progress`** after meaningful steps, then saves **`report_payload`** (`FactCheckResult`) and sets `status=completed` (or `failed`).
5. **Observe progress** — Client opens **`GET /api/jobs/{id}/stream`** (SSE). Handler polls DB and pushes JSON until terminal state; client also **polls** `GET /api/jobs/{id}` every few seconds as backup.
6. **Render results** — UI maps **facts → citation badges → reference cards** by **`sources[].id`**.

### Agent pipeline (`backend/emet_agents/`)

| Stage | Role |
|-------|------|
| **Planner** | Given the user question, outputs a **`WebSearchPlan`**: several `{ query, reason }` items biased toward authoritative, fact-check-friendly searches. |
| **Search** | **MCP** (if enabled and connected) uses your tools. Otherwise **structured research** (default): **Google CSE** when `GOOGLE_API_KEY` + `GOOGLE_CSE_ID` are set, else **DuckDuckGo** text results, then the top N URLs are fetched and **main article text** is extracted with **trafilatura** so citations map to real pages. Set `EMET_STRUCTURED_RESEARCH=false` for the legacy path: **OpenAI `WebSearchTool`** when **`LLM_BASE_URL`** is unset, else **DuckDuckGo** via a **`function_tool`**. |
| **Writer** | Consumes **all digests** and emits **`FactCheckAgentResult`**: `summary`, `facts[]` (with `status` and `source_ids`), `sources[]` (stable **`id`**, `url`, `title`, `snippet`, `tier`, `hostname`), `confidence_percent`, `confidence_rationale`, `limitations`. |

**Mock mode** — If `EMET_MOCK_PIPELINE=true` or **`OPENAI_API_KEY`** is unset, **`run_fact_check_mock`** runs: no live LLM/web search (useful for CI and cheap demos).

**Grounded URLs** — With structured research, the writer is instructed to cite only URLs present in the evidence blocks; the backend can **filter** model output to that allowlist. Placeholder hosts like **example.com** are stripped on non-structured paths.

**Legacy caveat** — **`WebSearchTool`** (OpenAI direct API + `EMET_STRUCTURED_RESEARCH=false`) is snippet-class. **OpenRouter** does not support that tool; use structured research, **`LLM_BASE_URL`** + legacy DuckDuckGo, or **MCP**.

---

## MCP integration (Model Context Protocol)

Emet can attach **an MCP server** (stdio, SSE, or streamable HTTP) to the **search** step so the model calls **real MCP tools** (Tavily, Brave, Firecrawl, internal corpora, etc.). Tools are bridged through the OpenAI Agents SDK as **function tools**, which keeps **OpenRouter** and other OpenAI-compatible gateways happy. The repo ships **one configured MCP endpoint** via env vars; extend `emet_agents/mcp_servers.py` if you need multiple servers in code.

### When MCP is used

If **`EMET_MCP_ENABLED=true`** and `build_mcp_servers()` in `backend/emet_agents/mcp_servers.py` returns at least one server definition, `run_fact_check` wraps the parallel search phase in **`MCPServerManager`** (see `backend/emet_agents/pipeline.py`): each server is **`connect()`**ed before **`Runner.run`**, and **`cleanup()`** runs when the context exits.

If MCP is enabled but **every** server fails to connect, the pipeline **logs a warning** and **falls back** to the same logic as when MCP is off (structured research, or legacy search).

### Search backend priority

1. **MCP** — `EMET_MCP_ENABLED=true` and at least one server **connects** → tools from your server(s).  
2. **Structured research** (default: `EMET_STRUCTURED_RESEARCH=true`, no MCP) — Google CSE or DuckDuckGo **ranked** results, then **trafilatura** extracts for the top URLs (`backend/emet_agents/structured_research.py`).  
3. **Legacy** — `EMET_STRUCTURED_RESEARCH=false`: **OpenAI `WebSearchTool`** if `LLM_BASE_URL` is empty, else **DuckDuckGo** `function_tool` (`search_factory`).

Optional **Google** keys — create a [Programmable Search Engine](https://programmablesearchengine.google.com/) and a JSON API key in Google Cloud; set `GOOGLE_CSE_ID` and `GOOGLE_API_KEY`. Without them, DuckDuckGo is used for ranked links.

### Supported MCP transports

| `EMET_MCP_TRANSPORT` | Required env | Notes |
|----------------------|---------------|--------|
| **`stdio`** | `EMET_MCP_STDIO_COMMAND` (+ optional `EMET_MCP_STDIO_ARGS_JSON`) | Spawns a subprocess (e.g. `npx -y @scope/mcp-server`). Optional `EMET_MCP_STDIO_ENV_JSON` object merged into the child env (API keys). |
| **`sse`** | `EMET_MCP_URL` | HTTP + Server-Sent Events endpoint. Optional `EMET_MCP_HEADERS_JSON` for auth. |
| **`streamable_http`** | `EMET_MCP_URL` | Streamable HTTP per MCP spec; `ignore_initialized_notification_failure` is enabled for flaky proxies. |

### MCP-related environment variables

| Variable | Role |
|----------|------|
| `EMET_MCP_ENABLED` | `true` to turn on MCP for the search agent. |
| `EMET_MCP_TRANSPORT` | `stdio`, `sse`, or `streamable_http`. |
| `EMET_MCP_URL` | Base URL for `sse` / `streamable_http`. |
| `EMET_MCP_STDIO_COMMAND` | Executable for `stdio` (e.g. `npx`). |
| `EMET_MCP_STDIO_ARGS_JSON` | JSON array of extra argv tokens (default `[]`). |
| `EMET_MCP_STDIO_ENV_JSON` | JSON object of env vars for the MCP child process. |
| `EMET_MCP_HEADERS_JSON` | JSON object of HTTP headers for remote MCP. |
| `EMET_MCP_TOOL_ALLOWLIST` | Comma-separated MCP tool names to expose (empty = all tools). |
| `EMET_MCP_SERVER_NAME` | Optional display name for logs / tracing. |
| `EMET_MCP_STRICT_CONNECT` | If `true`, **`MCPServerManager(..., strict=True)`** — first connect failure aborts the run. |
| `EMET_MCP_CONNECT_TIMEOUT_SECONDS` | Connect timeout (default `30`). |
| `EMET_MCP_CLEANUP_TIMEOUT_SECONDS` | Cleanup timeout (default `20`). |

### Example: stdio MCP (illustrative)

Exact packages change over time; substitute the MCP server your team standardizes on.

```bash
EMET_MCP_ENABLED=true
EMET_MCP_TRANSPORT=stdio
EMET_MCP_STDIO_COMMAND=npx
EMET_MCP_STDIO_ARGS_JSON=["-y","@some-scope/search-mcp@latest"]
EMET_MCP_STDIO_ENV_JSON={"SEARCH_API_KEY":"replace-me"}
EMET_MCP_TOOL_ALLOWLIST=search,fetch_page
```

Restart **`uvicorn`** (and any **SQS worker**) after changing MCP env vars.

### Operations and security

- **Secrets** — Prefer **`EMET_MCP_STDIO_ENV_JSON`** / **`EMET_MCP_HEADERS_JSON`** over baking keys into argv.  
- **Allowlists** — Use **`EMET_MCP_TOOL_ALLOWLIST`** in production to reduce prompt-injection surface.  
- **Networking** — Remote MCP URLs must be reachable from the **same network** as the API container / worker.  
- **Concurrency** — Each parallel search run uses the **same** connected MCP servers for that job; heavy servers should rate-limit or scale horizontally with a queue.

### Code map

| File | Purpose |
|------|---------|
| `backend/emet_agents/mcp_servers.py` | Build `MCPServerStdio` / `MCPServerSse` / `MCPServerStreamableHttp` from settings. |
| `backend/emet_agents/search_factory.py` | `build_search_agent(mcp_servers)` — MCP vs DuckDuckGo vs `WebSearchTool`. |
| `backend/emet_agents/pipeline.py` | `MCPServerManager` lifecycle around parallel **`Runner.run`** search calls. |
| `backend/app/config.py` | Pydantic fields for all **`EMET_MCP_*`** variables. |

For MCP protocol details, see the [Model Context Protocol specification](https://modelcontextprotocol.io/).

## Data model (jobs)

| Field | Purpose |
|-------|---------|
| `status` | `pending` → `running` → `completed` \| `failed` |
| `progress` | `{ phase, message, percent?, steps?, updated_at }` — drives SSE + UI stepper |
| `request_payload` | e.g. `{ "question": "..." }` |
| `report_payload` | Serialized **`FactCheckResult`** when complete |
| `error_message` | Populated on failure |

---

## Repository layout

| Path | Purpose |
|------|---------|
| `frontend/` | Next.js 14 (App Router), Tailwind, Clerk, citation UI, SSE client (`fetch` stream) |
| `backend/` | FastAPI app (`app/`), DB models, routers, Clerk + subscription helpers |
| `backend/emet_agents/` | Planner, **`structured_research.py`**, search factory, optional **`mcp_servers.py`**, writer, **`evidence_sanitize.py`**; **`pipeline.py`** |
| `backend/worker_sqs.py` | Optional SQS loop → `run_pipeline_for_job` |
| `backend/alembic/` | SQL migrations (Postgres-oriented) |
| `shared/types.ts` | TypeScript shapes aligned with API payloads |

---

## Environment variables

- **API / worker / Alembic:** one file at the **repo root**: copy **`.env.example` → `emet/.env`**
- **Next.js:** **`frontend/.env.local`** from **`frontend/.env.local.example`**

Key variables:

| Variable | Role |
|----------|------|
| `DATABASE_URL` | Async SQLAlchemy URL (e.g. `postgresql+asyncpg://...` or SQLite for tests) |
| `CLERK_JWKS_URL` | Clerk JWKS for JWT verification |
| `CLERK_SECRET_KEY` | Clerk secret (subscription API + dashboard) |
| `OPENAI_API_KEY` | LLM key (OpenAI or OpenRouter `sk-or-v1-*`, etc.) |
| `LLM_BASE_URL` | Optional OpenAI-compatible base URL (e.g. OpenRouter). Empty = official OpenAI. With `EMET_STRUCTURED_RESEARCH=false` and no MCP, empty also enables `WebSearchTool` for the legacy path. |
| `LLM_MODEL` | Chat model id for the configured API (e.g. `openai/gpt-4o-mini` on OpenRouter). |
| `GOOGLE_API_KEY` / `GOOGLE_CSE_ID` | Optional — **Programmable Search** JSON API + search engine id for ranked results in structured research |
| `EMET_STRUCTURED_RESEARCH` | `true` (default): Google CSE or DDG + trafilatura; `false`: legacy search agent only |
| `EMET_RESEARCH_TOP_URLS` | How many result URLs to fetch per planned query (default `5`) |
| `EMET_MCP_*` | Optional MCP for the search step — see **MCP integration** above. |
| `REQUIRE_SUBSCRIPTION` | `true` enforces paid plan on `POST /api/fact-check` (via `require_premium`) |
| `CLERK_PREMIUM_PLAN_KEY` | Must match the plan **key** in Clerk Billing (e.g. `emet_subscription`) |
| `NEXT_PUBLIC_CLERK_PREMIUM_PLAN_KEY` | Same as `CLERK_PREMIUM_PLAN_KEY` (docs only; UI gate uses the API) |
| `NEXT_PUBLIC_API_URL` | Backend origin for the browser |
| `EMET_MOCK_PIPELINE` | `true` forces mock pipeline |
| `SQS_QUEUE_URL` | If set, enqueue only; run **`worker_sqs.py`** separately |

---

## Prerequisites

- **Python 3.11+**, **Node 20+**, **PostgreSQL** (recommended) or SQLite for tests
- **Clerk** application (JWT / JWKS); **Clerk Billing** if you use subscription gates
- **LLM provider** — OpenAI and/or OpenRouter (or another OpenAI-compatible host); optional **MCP** servers for search; DuckDuckGo fallback requires no extra key

---

## Quick start (local)

### 1. Database

```bash
export DATABASE_URL=postgresql+asyncpg://USER:PASS@localhost:5432/emet
```

Alembic (from `backend/`):

```bash
pip install -r requirements.txt
alembic upgrade head
```

The API also runs `metadata.create_all` on startup for convenience.

### 2. Backend

```bash
# from repo root
cp .env.example .env   # edit keys and URLs
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **`REQUIRE_SUBSCRIPTION=false`** — easiest local path without Billing wired.
- **`EMET_MOCK_PIPELINE=true`** — no OpenAI calls (CI-safe).
- **`SQS_QUEUE_URL`** — optional. With **`EMET_RUN_PIPELINE_INLINE=true`** (default), the API still runs the pipeline in-process and progress updates without a separate worker. Set **`EMET_RUN_PIPELINE_INLINE=false`** when you want **only** the queue consumer (`python worker_sqs.py` or Lambda) to run jobs; then start the worker with the **same** `.env` as the API (including **`EMET_MCP_*`**).

### 3. Frontend

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). **`/check`** is **sign-in only** by default (no Billing UI gate). **`POST /api/fact-check`** uses **`require_premium`**: with **`REQUIRE_SUBSCRIPTION=false`**, any signed-in user can enqueue jobs; set **`true`** and align **`CLERK_PREMIUM_PLAN_KEY`** / **`CLERK_SECRET_KEY`** / JWKS / publishable key with the same Clerk app. **`/pricing`** remains for marketing. To add a **UI** subscription gate, wrap **`/check`** with **`FactCheckSubscriptionGate`** (see frontend components).

**`REQUIRE_SUBSCRIPTION`:** when **`false`**, `require_premium` skips the Clerk Billing call; when **`true`**, the backend calls Clerk Billing (and legacy commerce list fallback) before accepting a fact-check job.

---

## API summary

| Method | Path | Notes |
|--------|------|--------|
| `GET` | `/health` | Liveness |
| `GET` | `/api/subscription` | `{ "has_premium": true|false }` — same Commerce check as `require_premium`; Bearer JWT |
| `POST` | `/api/fact-check` | Body `{ "question": "..." }`, Bearer JWT. Creates job; worker runs pipeline. Premium enforced when **`REQUIRE_SUBSCRIPTION=true`**. |
| `GET` | `/api/jobs` | List recent jobs for user |
| `GET` | `/api/jobs/{id}` | Job row: `status`, `progress`, `report_payload` |
| `GET` | `/api/jobs/{id}/stream` | **SSE** — use **`fetch()` + `Authorization: Bearer`** (see `frontend/lib/useJobStream.ts`). Poll job GET as fallback. |

---

## SSE and auth

Native **`EventSource`** cannot send custom headers. Emet’s client uses **`fetch()`** with a **Bearer** token and parses `data:` SSE lines. If streaming fails (proxy, API Gateway buffering), the UI **polls** job status.

---

## Security and responsibility

- **Rate limits / abuse** — not implemented in this demo; add reverse-proxy or app limits for production.
- **Question length** — capped in API schema (see `FactCheckRequest`).
- **PII** — avoid logging raw prompts in production.
- **Fact-checking** — outputs are **assistive**; high-stakes domains (legal, medical) need stronger review, disclaimers, or human-in-the-loop.

---

## Human checklist (things only you can do)

- Configure **Clerk** (providers, redirects, **Billing** plan key consistency).
- Provision **cloud** accounts, **DNS**, **TLS**, **secrets** in hosting.
- Add **Terms / Privacy** and confidence **disclaimers** appropriate for your jurisdiction.
- **End-to-end QA** in production (sign-up → pay → run check → verify progress + citations).

---

## Deploy (outline)

1. **Database** — Postgres reachable from the API (e.g. RDS); run **`cd backend && alembic upgrade head`** from a machine that can reach the DB.
2. **Backend** — long-lived HTTP + SSE: use a container host (e.g. **AWS App Runner**, ECS, Fly). Set **`CORS_ORIGINS`** to your real frontend URL(s). The API Dockerfile is `backend/Dockerfile`.
3. **Frontend** — Next.js needs **`NEXT_PUBLIC_*` baked at build time** for Docker (see `frontend/Dockerfile`). Point **`NEXT_PUBLIC_API_URL`** at the public backend URL.
4. **Worker** (optional) — same codebase; use **SQS + `worker_sqs.py`** when you outgrow in-process tasks.

### AWS App Runner + ECR (both services)

Prerequisites: ECR repositories **`emet-backend`** and **`emet-frontend`**, two App Runner services pulling those images (port **8000** / **3000**), and runtime env vars set in the service (DB, Clerk, `OPENAI_API_KEY`, `CORS_ORIGINS`, etc.).

From the repo root (Docker must support **linux/amd64**; Docker Desktop on Apple Silicon: enable **buildx**):

```bash
export AWS_REGION=us-east-1
# Public values used when building the frontend image:
export NEXT_PUBLIC_API_URL=https://YOUR-BACKEND-PUBLIC-URL.awsapprunner.com
export NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
export NEXT_PUBLIC_CLERK_PREMIUM_PLAN_KEY=emet_subscription

# Optional: force new pull of the same tag
export APP_RUNNER_BACKEND_ARN=arn:aws:apprunner:...
export APP_RUNNER_FRONTEND_ARN=arn:aws:apprunner:...

python3 scripts/deploy_app_runner.py
```

Alternatively, put the same three `NEXT_PUBLIC_*` values as on the frontend App Runner service into **`deploy/frontend-build.env`** (copy from **`deploy/frontend-build.env.example`**, keep that file gitignored) so you don’t re-export them each time. Shell exports still override the file.

The script logs in to ECR, builds and pushes **emet-backend:amd64** and **emet-frontend:amd64**, then runs **`aws apprunner start-deployment`** when the ARN env vars are set. See **`scripts/deploy_app_runner.py`** for all options.

Templates for App Runner payloads are **`deploy/apprunner-*.example.json`** (no secrets). Keep real copies like `deploy/apprunner-frontend.json` **local / gitignored**; prefer the App Runner console, **`aws apprunner update-service`**, or Parameter Store / Secrets Manager for runtime configuration.

### AWS: SQS + CloudFront with Terraform

This repo includes **[`terraform/`](terraform/README.md)** to provision:

- **`sqs_queue_url`** → paste into **`SQS_QUEUE_URL`**
- **`cloudfront_url`** → paste into **`CLOUDFRONT_URL`** and add the same HTTPS origin to **`CORS_ORIGINS`** on the API  
- **S3 bucket** + **CloudFront** for a static-export frontend (Alex-style); sync `out/` after `next export` / `output: 'export'` (see Terraform README).

```bash
cd terraform && terraform init && terraform apply
terraform output
```

IAM permissions for **`sqs:SendMessage`** (API) and **`sqs:ReceiveMessage`/`DeleteMessage`** (worker) are documented in [`terraform/README.md`](terraform/README.md).

---

## Scripts & CI

```bash
cd backend && pytest
cd frontend && npm run lint && npm run test && npm run build
```

GitHub Actions: `.github/workflows/ci.yml`.

---

## License

MIT (adjust as needed for your cohort).
