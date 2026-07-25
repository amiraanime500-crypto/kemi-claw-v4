# Kemi-Claw

**Kemi-Claw** is an autonomous, **authorization-gated** offensive-security AI agent. It plans, executes, evaluates and re-plans security tasks against targets you are **explicitly authorized** to test. It ships with a planning brain, persistent cross-session memory, a pluggable any-LLM provider layer, MCP-style tool integration, a Client/Server API, a Celery/Redis task queue, a web dashboard, and role-based access control (RBAC).

> **Legal & safety notice.** Every run is guarded by `require_scope_confirmation`. The agent refuses to act unless `authorized=true` is passed for the target. Use Kemi-Claw **only** on systems you own or have explicit written permission to test (licensed pentests, authorized bug-bounty scope, or your own lab). Unauthorized use is illegal.

---

## Capabilities

| Layer | What it does |
|---|---|
| **Planner** (`core/planner.py`) | Turns a goal + available tools into a JSON plan, evaluates results, decides continue/replan/done. |
| **Brain** (`core/brain.py`) | Persistent SQLite memory across sessions. |
| **LLM provider** (`models/llm_provider.py`) | One interface for Claude / OpenAI / Deepseek / local (Ollama). |
| **MCP tools** (`tools/`) | Registry + built-in `nmap_scan`, `http_probe`; auto-loaded `plugins/`. |
| **Agent loop** (`core/agent.py`) | Parallel step execution, per-step failure isolation, logging, Markdown report. |
| **Autopilot** (`core/autopilot.py`) | Unattended multi-target runs. |
| **Integrations** (`integrations/`) | Slack alerts, Jira issues, Burp Suite scans. |
| **Live CVE** (`knowledge/cve_live.py`) | Queries the NVD API. |
| **Queue** (`queue/`) | Celery + Redis fan-out across workers. |
| **Dashboard** (`web/`) | FastAPI + Jinja UI to launch batches and view sessions. |
| **RBAC** (`auth/`) | JWT login + bcrypt; roles `viewer` / `operator` / `admin`. |

---

## Architecture

```
                 +-------------------+
   operator ---> |   Dashboard (web) | --(JWT/RBAC)
                 +---------+---------+
                           | run_batch.delay()
                           v
                 +-------------------+        +-----------+
                 |   Celery queue    | <----> |   Redis   |
                 +---------+---------+        +-----------+
            run_target.delay() (parallel workers)
                           |
                           v
   +----------------------------------------------------+
   |                 KemiClawAgent.run()                |
   |                                                    |
   |  scope-confirm gate  ->  Planner.make_plan()       |
   |        ^                      |                     |
   |        |                      v                     |
   |   Planner.evaluate()  <-- parallel _exec_step()     |
   |   (continue/replan/done)      |                     |
   |                               v                     |
   |        +---------+     +--------------+             |
   |        |  Brain  | <-- | MCP registry | --> tools   |
   |        | (SQLite)|     +--------------+   (nmap,   |
   |        +---------+                         http,    |
   |             |                              burp,    |
   |             v                              plugins)  |
   |     build_report() -> Markdown -> Slack/Jira       |
   +-------------------------+--------------------------+
                             |
                  LLMProvider (Claude/GPT/Deepseek/local)
```

---

## Quick start (Docker, recommended)

```bash
cp .env.example .env        # set ANTHROPIC_API_KEY, KEMI_JWT_SECRET, KEMI_API_KEY
mkdir -p data
docker compose up --build   # api:8000  dashboard:8080  flower:5555
```

Create the first admin (inside the running dashboard container or locally):

```bash
python bootstrap_admin.py admin "StrongPass123!"
```

## Local (no Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export KEMI_API_KEY=mykey
uvicorn kemi_claw.server:app --reload
```

## Run a single task

```bash
# via the CLI entrypoint installed by pip
kemi-claw "discover web vulns" "https://your-authorized-target" mykey

# or the raw API
curl -X POST http://localhost:8000/run \
  -H "x-api-key: mykey" -H "Content-Type: application/json" \
  -d '{"goal":"recon","target":"https://authorized","authorized":true,"notify":false}'
```

## Batch via the dashboard (RBAC)

```bash
# 1) login -> token
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"StrongPass123!"}'

# 2) admin creates an operator
curl -X POST http://localhost:8080/auth/users \
  -H "Authorization: Bearer <ADMIN_TOKEN>" -H "Content-Type: application/json" \
  -d '{"username":"op1","password":"OpPass123!","role":"operator"}'

# 3) operator launches a batch
curl -X POST http://localhost:8080/api/batch \
  -H "Authorization: Bearer <OPERATOR_TOKEN>" -H "Content-Type: application/json" \
  -d '{"goal":"full recon","targets":["https://t1","https://t2"]}'
```

## Autopilot (CLI)

```bash
python -m kemi_claw.core.autopilot "full recon" https://t1 https://t2
```

## Roles

| Action | viewer | operator | admin |
|---|:---:|:---:|:---:|
| View sessions / reports | yes | yes | yes |
| Launch tasks / batches | no | yes | yes |
| Manage users | no | no | yes |

## Tests

```bash
pip install -e ".[dev]"
pytest -q
```

## Extending with plugins

Drop a module in `plugins/` that calls `registry.register(...)`. Load them at startup with `kemi_claw.tools.plugin_loader.load_plugins()`.

## Security model

- Passwords stored bcrypt-hashed (never plaintext).
- JWTs are short-lived (`KEMI_JWT_TTL`) and signed with `KEMI_JWT_SECRET` -- change it before deploying.
- Least privilege: start every user as `viewer`.
- `require_scope_confirmation` sits **above** RBAC -- even an authorized operator cannot run against an unconfirmed target.
