# GEMINI.md — WebIntel
### Autonomous Multi-Agent Web Intelligence System
**Team:** Antigravity | **Hackathon:** 36 Hours

---

## What This System Is

WebIntel is NOT a chatbot. It is NOT a search engine.

It is a real-time reasoning and verification system. The user asks a question, and instead of answering from memory, the system autonomously dispatches multiple AI agents to search the web in parallel, extracts structured facts from everything it finds, cross-verifies those facts across sources, detects conflicts, resolves them with logic, and returns a confidence-scored structured report — all streamed live to the UI as it happens.

One-line identity: **WebIntel searches, verifies, and explains — using parallel agents, in real time.**

---

## Tech Stack

- **Backend:** FastAPI (Python) with async/await throughout
- **LLM:** Google Gemini API (gemini-1.5-flash) — used for planning, extraction, verification, report generation
- **Search:** Tavily API — AI-optimized search that returns clean content + URLs, no raw scraping needed
- **Streaming:** Server-Sent Events (SSE) — streams live agent steps from backend to frontend
- **Database:** Supabase (Postgres) — stores reports, query history, scheduled monitor jobs
- **Scheduler:** APScheduler — runs background re-queries for Monitor mode
- **PDF Export:** WeasyPrint
- **Frontend:** Vanilla HTML + CSS + JavaScript (no framework)
- **Frontend Charts:** Chart.js — for citation graph and confidence visualization
- **Deploy:** Backend on Railway or Render, Frontend served via FastAPI /static or Vercel

---

## Project File Structure

```
webintel/
├── backend/
│   ├── main.py                  ← FastAPI app, all routes, SSE endpoint
│   ├── agents/
│   │   ├── planner.py           ← Breaks query into sub-tasks using Gemini
│   │   ├── search_agent.py      ← Runs parallel searches via Tavily
│   │   ├── extraction_agent.py  ← Pulls structured claims from raw content
│   │   ├── verification_agent.py← Compares claims, scores confidence, detects conflicts
│   │   └── report_agent.py      ← Assembles final structured output
│   ├── services/
│   │   ├── gemini_service.py    ← Single wrapper for all Gemini LLM calls
│   │   ├── tavily_service.py    ← Tavily search wrapper
│   │   ├── supabase_service.py  ← DB read/write helpers
│   │   ├── sse_service.py       ← In-memory session queue for SSE streaming
│   │   └── export_service.py    ← PDF and JSON export
│   ├── utils/
│   │   ├── trust_scorer.py      ← Assigns trust tier to domains (hardcoded list)
│   │   ├── conflict_resolver.py ← Conflict resolution logic
│   │   └── diff_engine.py       ← Diffs two reports for Monitor/Track mode
│   ├── models/
│   │   ├── query_models.py      ← Pydantic models for incoming requests
│   │   ├── report_models.py     ← Pydantic models for final report output
│   │   └── agent_models.py      ← Internal data structures (claims, plans, etc.)
│   ├── scheduler/
│   │   └── monitor_scheduler.py ← APScheduler setup for recurring queries
│   ├── .env                     ← API keys (never commit)
│   └── requirements.txt
└── frontend/
    ├── index.html               ← Single page app shell
    ├── css/
    │   ├── main.css             ← Base styles, CSS variables
    │   ├── components.css       ← Cards, pills, panels, trace steps
    │   └── animations.css       ← Streaming pulse, claim fade-in
    └── js/
        ├── app.js               ← Main controller, query submission
        ├── stream.js            ← EventSource SSE handler
        ├── ui.js                ← All DOM rendering functions
        ├── charts.js            ← Chart.js citation graph
        ├── compare.js           ← Compare mode table builder
        ├── history.js           ← History sidebar
        └── export.js            ← PDF/JSON download triggers
```

---

## How the System Works (Full Flow)

### Step 1 — Query Planning
User submits a query with a mode and query type. The Planner Agent calls Gemini with the query and asks it to decompose it into N focused sub-queries, each assigned a source type (news, official, academic, financial). The number of sub-queries depends on the mode — 3 for Quick, up to 15 for Deep Dive.

### Step 2 — Parallel Search
All sub-queries are dispatched simultaneously using `asyncio.gather`. Each Search Agent calls Tavily with its specific sub-query and returns raw content + source URLs. Because they run in parallel, total time equals the slowest agent, not the sum of all agents. This is what makes the system feel fast.

### Step 3 — Claim Extraction
The Extraction Agent calls Gemini on all collected raw content and asks it to pull out structured, atomic facts. Each claim comes with the source URL it was pulled from and a timestamp. Output is always a clean list of `{claim, source_url, timestamp}` objects.

### Step 4 — Verification
The Verification Agent groups similar claims from different sources, compares them, detects conflicts, and scores confidence. If confidence falls below the mode's threshold, it triggers a re-query — the planner generates new sub-queries for the weak areas, agents run again, and new claims are merged into the pool before re-verifying.

### Step 5 — Report Generation
The Report Agent assembles everything into the final structured output. For Compare mode, claims are aligned into a table. For Track mode, the diff engine compares against the last saved report and highlights what changed.

### Step 6 — Streaming to UI
Every step above pushes events to an in-memory SSE queue tied to the session ID. The frontend connects to `/stream/{session_id}` via EventSource and receives live updates — trace steps, individual claim cards as they're verified, and finally the full report.

---

## Parallel Agent Architecture

This is the most important technical decision. Every search runs concurrently, not sequentially.

The Planner produces a list of sub-queries. The backend runs all of them at once using `asyncio.gather`. Each sub-query is a separate async task hitting Tavily with a different focused query and source type filter.

Agent roles:
- **News Agent** — targets recent articles, media coverage, blogs
- **Official Agent** — targets government sites, company IR pages, official exchanges
- **Academic Agent** — targets encyclopedias, research summaries, reference content
- **Financial Agent** — targets stock portals, financial databases, market data

For Compare mode, a separate batch of agents is spawned per entity being compared (e.g. one batch for Jio, one for Airtel, one for Vi) — all running in parallel simultaneously.

One agent failing must never stop the others. Always use `return_exceptions=True` in gather calls and continue with whatever results succeeded.

---

## Verification Logic

### Conflict Detection
- **Numeric claims:** more than 3% variance between sources = conflict
- **Factual claims:** directly contradictory statements = conflict
- **Same claim from same domain:** ignore duplicates, count once

### Conflict Resolution Priority
1. Official/government source wins
2. Majority agreement across sources wins
3. Most recent timestamp wins
4. If none resolve it → mark as `unresolved` and surface to user

### Confidence Scoring (0–100)
- 3+ high-trust sources agree → 90+
- Mixed trust levels → 60–80
- Active conflict present → below 60
- Single source only → cap at 55 regardless of trust

### Re-query Trigger
- Quick mode: never re-queries
- Fact Check: re-query if any claim below 60
- Research: re-query if overall confidence below 70
- Deep Dive: re-query if overall confidence below 80

---

## Source Trust System

Trust tiers are hardcoded — no ML needed here.

**High trust (score 85–95):** Government domains (.gov.in, .nic.in), official exchange sites (nseindia.com, bse.india.com), regulatory bodies (rbi.org.in, sebi.gov.in), globally recognized wire services (reuters.com, apnews.com, bloomberg.com), WHO, UN

**Medium trust (score 55–70):** Established national news (economictimes, livemint, thehindu, ndtv), major tech media (techcrunch, wired, theverge), Forbes, business publications

**Low trust (score 25–40):** Reddit, Quora, personal blogs, Medium posts, unknown domains

**Unknown:** Default to 45. Surface to user as "unverified source".

Discard sources below score 25 automatically. Still show them in the UI as "discarded" so the user can audit the decision.

---

## Output Data Structure

Every response from every Gemini call must be valid JSON. No markdown, no explanation text, just the raw JSON object. This is critical — enforce it in every prompt.

The final report contains:
- `query` — original user query
- `query_type` — single / compare / track / summarise_url
- `mode` — quick / fact_check / research / deep_dive
- `verified_claims` — array of claims, each with: claim text, confidence score, supporting source URLs, conflicting source URLs, conflict detail, resolution method, status (verified / conflict / unresolved)
- `sources` — all sources visited, each with URL, domain, trust tier, trust score, agreement count, conflict count, discarded flag
- `overall_confidence` — single number for the whole report
- `compare_table` — populated only for compare mode (criteria → values per entity)
- `diff` — populated only for track mode (added / removed / changed claims vs last run)
- `total_sources_visited`, `conflicts_detected`, `conflicts_resolved` — summary stats
- `generated_at` — ISO timestamp

---

## Modes

| Mode | Sub-queries | Sources | Re-query threshold | Speed |
|---|---|---|---|---|
| quick | 3 | 2–3 | Never | ~5 sec |
| fact_check | 4 | 3–5 | < 60% | ~10 sec |
| research | 8 | 5–8 | < 70% | ~20 sec |
| deep_dive | 15 | 10–20 | < 80% | ~45 sec |

---

## Query Types

**single** — Standard. User asks about one thing. Output is claim list + sources + conflict log.

**compare** — User wants A vs B vs C. Agent spawns separate search batches per entity. Output is a comparison table with rows per criterion and columns per entity. Each cell has a confidence indicator.

**track / monitor** — Same query on a schedule. Each run diffs against the previous saved report. Output highlights new claims, removed claims, confidence changes. Stored in Supabase and triggered by APScheduler.

**summarise_url** — User pastes a URL. Agent fetches that page, extracts all factual claims, then verifies each against external sources. Output shows which claims are verified, false, or undeterminable.

---

## SSE Streaming — Event Types

The backend pushes these event types through the SSE queue in real time:

- `trace` — one agent step completed. Has step number and message. Updates the live trace panel.
- `claim` — a single verified claim is ready. Pushed immediately as each claim clears verification, not batched at the end. This makes the UI feel alive.
- `report` — the complete final report object. Pushed once at the very end.
- `error` — something failed. Always human-readable message.
- `done` — stream is finished. Frontend closes the EventSource connection.

Each session gets its own in-memory asyncio Queue keyed by session_id. SSE endpoint reads from this queue and yields events. Clean up the queue after the stream ends.

---

## Database Schema (Supabase)

**reports table** — every completed report. Stores session_id, query, mode, query_type, and the full report as a JSONB blob, plus overall_confidence and created_at timestamp. Store report as one JSONB blob — do not normalise individual claims into rows.

**monitors table** — scheduled recurring queries. Stores the query, mode, interval in hours, last_run, next_run, and active flag.

**diffs table** — output of each monitor re-run. Stores old and new session IDs and the diff as JSONB.

---

## UI Layout

Single page. No routing needed. Panels appear progressively as the query runs.

**Top bar:** Logo, History button, About

**Query bar:** Full-width text input + Mode dropdown + Query Type dropdown + Run button

**Three-column live panel (appears when query starts):**
- Left — Agent Trace: live step log, each step marked pending / active (pulsing) / done
- Center — Extracted Claims: cards appear one by one as claims are verified. Each card shows claim text, confidence percentage, confidence bar, source count, conflict warning if applicable
- Right — Sources Visited: list with trust tier badge, agreement/conflict counts, discarded marker

**Bottom row (appears on completion):**
- Left — Conflict Log: each conflict with full resolution explanation
- Right — Citation Graph: Chart.js bar chart showing agreements vs conflicts per source domain

**For Compare mode:** Center panel becomes a comparison table instead of claim cards

**For Track mode:** Center panel shows diff view — green for new, red for removed, amber for confidence shifts

**Footer bar:** Download JSON, Export PDF, Send to Slack, Schedule Monitor

**History sidebar:** Slides in from right. Shows past queries with timestamps, clickable to reload any report.

---

## Critical Implementation Rules

**Never block the event loop.** Gemini's Python SDK is synchronous. Always wrap every Gemini call in `asyncio.run_in_executor` so it doesn't freeze FastAPI's event loop and kill SSE streaming.

**Always return JSON from Gemini.** Every single prompt must end with a hard instruction: return only raw valid JSON, no markdown fences, no preamble, no explanation. Parse with `json.loads()` and always catch parse exceptions.

**Parallel agents must use return_exceptions=True.** One failing Tavily call must never crash the whole pipeline. Continue with whatever succeeded and log the failure in the trace.

**SSE needs no-cache headers.** Add `Cache-Control: no-cache` and `X-Accel-Buffering: no` to every StreamingResponse or some browsers and reverse proxies will buffer the stream silently.

**APScheduler must start in FastAPI startup event.** Initialize and start the scheduler in `@app.on_event("startup")` and shut it down cleanly in `@app.on_event("shutdown")`.

**CORS middleware must be added before mounting static files.** Middleware order matters in FastAPI.

**WeasyPrint needs system dependencies on Linux.** On Railway or Render, use a Dockerfile with `apt-get install -y weasyprint` or PDF export will fail silently on deployment.

---

## Environment Variables Needed

```
GEMINI_API_KEY
TAVILY_API_KEY
SUPABASE_URL
SUPABASE_KEY
ENVIRONMENT
CORS_ORIGINS
```

---

## Demo Queries (Prepare These Before Presenting)

**Query 1 — Verification demo**
"What is the current market cap of Reliance Industries?"
Mode: Research | Type: Single
Shows: multi-source verification, NSE vs BSE variance, conflict detection, resolution via majority vote

**Query 2 — Compare demo (most visually impressive)**
"Compare Jio vs Airtel vs Vi — subscribers, revenue, and 5G coverage"
Mode: Research | Type: Compare
Shows: parallel agent batches per entity, comparison table, citation graph

**Query 3 — Autonomy demo**
"What are the latest AI regulations being considered in India?"
Mode: Deep Dive | Type: Single
Shows: agent re-querying after low-confidence first pass, confidence scores updating live, government + news sources triangulating

---

*WebIntel — Antigravity*