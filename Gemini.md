# GEMINI.md — Autonomous Multi-Agent Web Intelligence System
### Project: WebIntel | Team: Antigravity | Hackathon: 36 Hours

---

## 1. PROJECT OVERVIEW

Build an autonomous web intelligence system that accepts a user query, dispatches parallel AI agents to browse and extract information from multiple sources simultaneously, cross-verifies all extracted claims, resolves conflicts intelligently, and returns a structured, confidence-scored insight report — all in real time with a live streaming UI.

**The core differentiator:** Unlike a search engine (which returns links) or a chatbot (which answers from memory), this system *autonomously decides* what to search, *verifies* what it finds across sources, *flags contradictions*, and *explains its reasoning* — live, as it happens.

---

## 2. TECH STACK

### Backend
- **FastAPI (Python)** — Main API server, agent orchestration, SSE streaming
- **asyncio + asyncio.gather** — True parallel agent execution
- **httpx (async)** — Non-blocking HTTP requests for web fetching
- **Tavily API** — AI-optimized search, returns clean content + URLs (no scraping headaches)
- **Google Gemini API** — Primary LLM for planning, extraction, verification, report generation
- **BeautifulSoup4** — Fallback HTML parsing when Tavily content is insufficient
- **Supabase (Postgres)** — Query history, saved reports, scheduled monitor runs
- **APScheduler** — Background scheduler for Monitor mode (daily re-runs)
- **pdfkit / weasyprint** — PDF export generation
- **python-dotenv** — Environment variable management
- **uvicorn** — ASGI server

### Frontend
- **Vanilla HTML + CSS + JavaScript** — No framework, full control, fast to vibe-code
- **Server-Sent Events (EventSource API)** — Live streaming of agent trace to UI
- **Chart.js** — Citation graph visualization, confidence bar charts
- **Marked.js** — Render markdown in report output
- **Vanilla fetch API** — All API calls

### Infrastructure
- **Vercel** — Frontend static hosting (or just serve from FastAPI /static)
- **Railway / Render** — FastAPI backend deployment
- **Supabase** — Managed Postgres + auto-generated REST API
- **GitHub** — Version control, CI/CD trigger

---

## 3. SYSTEM ARCHITECTURE

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────┐
│                  QUERY PLANNER AGENT                │
│  (Gemini) Decomposes query into N sub-tasks,        │
│  decides search strategies, assigns agent roles     │
└─────────────────┬───────────────────────────────────┘
                  │ spawns parallel agents
        ┌─────────┼─────────┬──────────┐
        ▼         ▼         ▼          ▼
   [Agent 1]  [Agent 2]  [Agent 3]  [Agent N]
   News/Blog  Official   Academic   Financial
   Sources    Sites      Papers     Data APIs
        │         │         │          │
        └─────────┴─────────┴──────────┘
                  │ all results
                  ▼
┌─────────────────────────────────────────────────────┐
│               EXTRACTION AGENT                      │
│  Pulls structured claims from raw content           │
│  Normalizes format: {claim, source, timestamp}      │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│             VERIFICATION AGENT                      │
│  Cross-compares claims, scores confidence,          │
│  detects conflicts, applies resolution strategy     │
│  Re-queries if confidence < threshold               │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│            REPORT GENERATOR AGENT                   │
│  Assembles final structured report:                 │
│  claims + confidence + sources + conflicts          │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
             Streaming SSE
                  │
                  ▼
            Frontend UI
```

---

## 4. PARALLEL AGENT DESIGN (Critical)

This is why the system is fast. Instead of searching sources one by one (sequential = slow), we spawn multiple agents simultaneously using Python's `asyncio.gather`.

### How it works

```python
# Each agent is an async function
async def search_agent(sub_query: str, source_type: str, session_id: str):
    # 1. Search via Tavily for this specific sub-query
    results = await tavily_search(sub_query, source_type)
    # 2. Extract content from top URLs
    content = await fetch_page_content(results)
    # 3. Stream progress to UI via SSE
    await stream_event(session_id, f"Agent [{source_type}] found {len(results)} sources")
    return content

# Planner spawns all agents at once
async def run_parallel_agents(sub_queries: list, session_id: str):
    tasks = [
        search_agent(sq["query"], sq["source_type"], session_id)
        for sq in sub_queries
    ]
    # All agents run simultaneously — total time = slowest agent, not sum of all
    all_results = await asyncio.gather(*tasks)
    return all_results
```

### Agent Types

| Agent Role | Source Focus | Tavily Search Category |
|---|---|---|
| News Agent | News articles, blogs, media | `news` |
| Official Agent | Gov sites, company IR pages, exchanges | `general` + domain filter |
| Academic Agent | Research papers, Wikipedia, encyclopedias | `general` |
| Financial Agent | Stock data, market APIs, financial portals | `finance` |
| Verify Agent | Re-queries on conflict resolution | dynamic |

### Why parallel matters for demo
- Sequential: 5 sources × 3 sec each = 15 seconds total
- Parallel: 5 sources simultaneously = ~3–4 seconds total
- **Demo looks 4× faster. Judges notice.**

---

## 5. BACKEND — FILE STRUCTURE

```
webintel-backend/
├── main.py                  # FastAPI app, all routes
├── agents/
│   ├── __init__.py
│   ├── planner.py           # Query decomposition via Gemini
│   ├── search_agent.py      # Parallel web search via Tavily
│   ├── extraction_agent.py  # Claim extraction from raw content
│   ├── verification_agent.py # Cross-source verification + conflict detection
│   └── report_agent.py      # Final structured report assembly
├── services/
│   ├── tavily_service.py    # Tavily API wrapper
│   ├── gemini_service.py    # Gemini API wrapper (all LLM calls)
│   ├── supabase_service.py  # DB read/write helpers
│   ├── sse_service.py       # SSE streaming event manager
│   └── export_service.py    # PDF + JSON export
├── models/
│   ├── query_models.py      # Pydantic models for requests
│   ├── report_models.py     # Pydantic models for report output
│   └── agent_models.py      # Internal agent data structures
├── scheduler/
│   └── monitor_scheduler.py # APScheduler for Monitor mode
├── utils/
│   ├── trust_scorer.py      # Domain trust tier scoring
│   ├── conflict_resolver.py # Conflict resolution logic
│   └── diff_engine.py       # Report diff for Monitor mode
├── .env                     # API keys (never commit)
├── requirements.txt
└── README.md
```

---

## 6. BACKEND — CORE CODE PATTERNS

### main.py — FastAPI App + Routes

```python
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
import asyncio, json, uuid
from agents.planner import plan_query
from agents.search_agent import run_parallel_agents
from agents.extraction_agent import extract_claims
from agents.verification_agent import verify_claims
from agents.report_agent import generate_report
from services.sse_service import create_session, stream_event, get_session_queue
from models.query_models import QueryRequest
from services.supabase_service import save_report, get_history

app = FastAPI(title="WebIntel API")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="../frontend"), name="static")

# --- SSE stream endpoint ---
@app.get("/stream/{session_id}")
async def stream_events(session_id: str):
    async def event_generator():
        queue = get_session_queue(session_id)
        while True:
            event = await queue.get()
            if event == "__DONE__":
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break
            yield f"data: {json.dumps(event)}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# --- Main query endpoint ---
@app.post("/query")
async def run_query(request: QueryRequest, background_tasks: BackgroundTasks):
    session_id = str(uuid.uuid4())
    create_session(session_id)
    background_tasks.add_task(run_intelligence_pipeline, request, session_id)
    return {"session_id": session_id}

async def run_intelligence_pipeline(request: QueryRequest, session_id: str):
    try:
        # Step 1: Plan
        await stream_event(session_id, {"type": "trace", "step": 1, "msg": "Analysing query and building search strategy..."})
        plan = await plan_query(request.query, request.mode, request.query_type)

        # Step 2: Parallel search
        await stream_event(session_id, {"type": "trace", "step": 2, "msg": f"Dispatching {len(plan.sub_queries)} parallel agents..."})
        raw_results = await run_parallel_agents(plan.sub_queries, session_id)

        # Step 3: Extract claims
        await stream_event(session_id, {"type": "trace", "step": 3, "msg": "Extracting and normalising claims from all sources..."})
        claims = await extract_claims(raw_results, request.query)

        # Step 4: Verify
        await stream_event(session_id, {"type": "trace", "step": 4, "msg": "Cross-verifying claims across sources..."})
        verified = await verify_claims(claims, session_id)

        # Re-query if needed
        if verified.needs_requery:
            await stream_event(session_id, {"type": "trace", "step": "4b", "msg": f"Low confidence detected. Re-querying for: {verified.requery_topic}..."})
            extra = await run_parallel_agents(verified.requery_tasks, session_id)
            extra_claims = await extract_claims(extra, request.query)
            verified = await verify_claims(claims + extra_claims, session_id)

        # Step 5: Generate report
        await stream_event(session_id, {"type": "trace", "step": 5, "msg": "Generating structured insight report..."})
        report = await generate_report(verified, request.query, request.query_type)

        # Save to DB
        await save_report(session_id, request.query, report)

        # Send final report
        await stream_event(session_id, {"type": "report", "data": report.dict()})
        await stream_event(session_id, "__DONE__")

    except Exception as e:
        await stream_event(session_id, {"type": "error", "msg": str(e)})
        await stream_event(session_id, "__DONE__")

# --- Other endpoints ---
@app.get("/history")
async def get_query_history():
    return await get_history()

@app.get("/report/{session_id}/pdf")
async def export_pdf(session_id: str):
    from services.export_service import generate_pdf
    return await generate_pdf(session_id)

@app.get("/report/{session_id}/json")
async def export_json(session_id: str):
    from services.supabase_service import get_report
    return await get_report(session_id)

@app.post("/monitor/schedule")
async def schedule_monitor(session_id: str, interval_hours: int = 24):
    from scheduler.monitor_scheduler import add_job
    await add_job(session_id, interval_hours)
    return {"status": "scheduled"}
```

### agents/planner.py

```python
from services.gemini_service import gemini_call
from models.agent_models import QueryPlan
import json

PLANNER_PROMPT = """
You are a web intelligence query planner.
Given a user query, decompose it into specific search sub-queries for parallel agents.

Return ONLY valid JSON like:
{{
  "sub_queries": [
    {{"query": "specific search string", "source_type": "news|official|academic|financial", "priority": 1}},
    ...
  ],
  "strategy": "brief description of search strategy"
}}

Rules:
- Max 6 sub-queries for Quick mode, 10 for Research, 15 for Deep Dive
- Each sub-query must be specific and targeted
- Distribute across different source types
- For Compare mode, create sub-queries for EACH entity being compared

Query: {query}
Mode: {mode}
Query Type: {query_type}
"""

async def plan_query(query: str, mode: str, query_type: str) -> QueryPlan:
    response = await gemini_call(PLANNER_PROMPT.format(
        query=query, mode=mode, query_type=query_type
    ))
    data = json.loads(response)
    return QueryPlan(**data)
```

### agents/verification_agent.py

```python
from services.gemini_service import gemini_call
from models.agent_models import VerificationResult
from utils.conflict_resolver import resolve_conflict
import json

VERIFY_PROMPT = """
You are a cross-source claim verifier.
Given multiple claims extracted from different sources about the same topic, your job is to:
1. Group claims that refer to the same fact
2. Check if they agree or conflict
3. For numeric claims: conflict = more than 3% variance
4. For factual claims: conflict = directly contradicting statements
5. Assign a confidence score (0-100) to each claim group
6. Suggest resolution for each conflict

Return ONLY valid JSON:
{{
  "verified_claims": [
    {{
      "claim": "the verified claim text",
      "confidence": 85,
      "supporting_sources": ["url1", "url2"],
      "conflicting_sources": ["url3"],
      "conflict_detail": "url3 says X while url1,url2 say Y",
      "resolution": "majority_vote|latest_date|official_priority|flagged",
      "status": "verified|conflict|unresolved"
    }}
  ],
  "needs_requery": false,
  "requery_topic": "",
  "overall_confidence": 80
}}

Claims to verify:
{claims}
"""

async def verify_claims(claims: list, session_id: str) -> VerificationResult:
    from services.sse_service import stream_event
    claims_text = json.dumps([c.dict() for c in claims], indent=2)
    response = await gemini_call(VERIFY_PROMPT.format(claims=claims_text))
    data = json.loads(response)

    # Stream each verified claim live
    for claim in data["verified_claims"]:
        await stream_event(session_id, {
            "type": "claim",
            "data": claim
        })

    return VerificationResult(**data)
```

### utils/trust_scorer.py

```python
# Domain trust tier — hardcoded, no ML needed
TRUST_TIERS = {
    "high": [
        "bse.india.com", "nseindia.com", "rbi.org.in", "sebi.gov.in",
        "reuters.com", "apnews.com", "bbc.com", "bloomberg.com",
        "who.int", "un.org", "gov.in", "nic.in", "pib.gov.in",
        "supremecourt.gov.in", "mca.gov.in"
    ],
    "medium": [
        "moneycontrol.com", "economictimes.indiatimes.com", "livemint.com",
        "thehindu.com", "hindustantimes.com", "ndtv.com", "indiatoday.in",
        "techcrunch.com", "wired.com", "theverge.com", "forbes.com"
    ],
    "low": [
        "reddit.com", "quora.com", "medium.com"
    ]
}

def score_domain(url: str) -> dict:
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.replace("www.", "")

    for tier, domains in TRUST_TIERS.items():
        if any(d in domain for d in domains):
            trust_map = {"high": 90, "medium": 65, "low": 30}
            return {"tier": tier, "score": trust_map[tier], "domain": domain}

    return {"tier": "unknown", "score": 45, "domain": domain}
```

### utils/diff_engine.py (Monitor Mode)

```python
def diff_reports(old_report: dict, new_report: dict) -> dict:
    """Compare two reports and return what changed."""
    changes = {"added": [], "removed": [], "changed": [], "unchanged": []}

    old_claims = {c["claim"]: c for c in old_report.get("verified_claims", [])}
    new_claims = {c["claim"]: c for c in new_report.get("verified_claims", [])}

    for claim, data in new_claims.items():
        if claim not in old_claims:
            changes["added"].append(data)
        elif old_claims[claim]["confidence"] != data["confidence"]:
            changes["changed"].append({
                "claim": claim,
                "old_confidence": old_claims[claim]["confidence"],
                "new_confidence": data["confidence"],
                "detail": f"Confidence shifted from {old_claims[claim]['confidence']}% to {data['confidence']}%"
            })
        else:
            changes["unchanged"].append(data)

    for claim in old_claims:
        if claim not in new_claims:
            changes["removed"].append(old_claims[claim])

    return changes
```

---

## 7. FRONTEND — FILE STRUCTURE

```
webintel-frontend/
├── index.html               # Main app shell
├── css/
│   ├── main.css             # Base styles, CSS variables
│   ├── components.css       # Cards, pills, panels
│   └── animations.css       # Streaming pulse, loading states
├── js/
│   ├── app.js               # Main app controller
│   ├── stream.js            # SSE EventSource handler
│   ├── ui.js                # DOM manipulation helpers
│   ├── charts.js            # Chart.js citation graph
│   ├── compare.js           # Compare mode table builder
│   ├── history.js           # History sidebar
│   └── export.js            # PDF/JSON download
└── assets/
    └── logo.svg
```

---

## 8. FRONTEND — CORE CODE PATTERNS

### js/stream.js — SSE Handler

```javascript
class AgentStream {
  constructor(sessionId) {
    this.sessionId = sessionId;
    this.source = null;
  }

  connect(onEvent) {
    this.source = new EventSource(`/stream/${this.sessionId}`);

    this.source.onmessage = (e) => {
      const event = JSON.parse(e.data);

      switch(event.type) {
        case 'trace':
          onEvent('trace', event);
          break;
        case 'claim':
          onEvent('claim', event.data);
          break;
        case 'report':
          onEvent('report', event.data);
          break;
        case 'error':
          onEvent('error', event);
          break;
        case 'done':
          this.source.close();
          onEvent('done', {});
          break;
      }
    };

    this.source.onerror = () => {
      this.source.close();
      onEvent('error', { msg: 'Connection lost' });
    };
  }

  disconnect() {
    if (this.source) this.source.close();
  }
}
```

### js/app.js — Main Controller

```javascript
async function runQuery() {
  const query = document.getElementById('query-input').value.trim();
  const mode = document.getElementById('mode-select').value;
  const queryType = document.getElementById('type-select').value;
  if (!query) return;

  // Reset UI
  clearUI();
  showPanel('trace-panel');

  // Start query
  const res = await fetch('/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, mode, query_type: queryType })
  });
  const { session_id } = await res.json();

  // Connect stream
  const stream = new AgentStream(session_id);
  stream.connect((type, data) => {
    if (type === 'trace')  renderTraceStep(data);
    if (type === 'claim')  renderClaim(data);
    if (type === 'report') renderFullReport(data);
    if (type === 'done')   finalizeUI(session_id);
    if (type === 'error')  renderError(data);
  });
}
```

### js/ui.js — Rendering

```javascript
function renderTraceStep({ step, msg }) {
  const container = document.getElementById('trace-steps');
  const el = document.createElement('div');
  el.className = 'trace-step trace-step--active';
  el.innerHTML = `
    <span class="trace-num">${step}</span>
    <span class="trace-msg">${msg}</span>
    <span class="trace-pulse"></span>
  `;
  container.appendChild(el);
  // Mark previous step done
  const prev = container.querySelector('.trace-step--active:not(:last-child)');
  if (prev) prev.className = 'trace-step trace-step--done';
}

function renderClaim({ claim, confidence, status, supporting_sources, conflict_detail }) {
  const container = document.getElementById('claims-container');
  const color = confidence >= 80 ? 'green' : confidence >= 55 ? 'amber' : 'red';
  const el = document.createElement('div');
  el.className = 'claim-card claim-card--new';
  el.innerHTML = `
    <div class="claim-header">
      <span class="claim-text">${claim}</span>
      <span class="pill pill--${color}">${confidence}% conf.</span>
    </div>
    <div class="conf-bar">
      <div class="conf-fill conf-fill--${color}" style="width:${confidence}%"></div>
    </div>
    <div class="claim-sources">${supporting_sources.length} sources agree</div>
    ${conflict_detail ? `<div class="claim-conflict">⚠ ${conflict_detail}</div>` : ''}
  `;
  container.appendChild(el);
  // Animate in
  requestAnimationFrame(() => el.classList.remove('claim-card--new'));
}

function renderFullReport(report) {
  // Show all panels
  showPanel('sources-panel');
  showPanel('conflicts-panel');
  showPanel('export-panel');

  // Render source trust list
  renderSources(report.sources);

  // Render conflict log
  renderConflicts(report.verified_claims.filter(c => c.status === 'conflict'));

  // If compare mode — render table
  if (report.query_type === 'compare') {
    renderCompareTable(report);
  }

  // Citation graph
  renderCitationGraph(report);
}
```

### js/charts.js — Citation Graph

```javascript
function renderCitationGraph(report) {
  const canvas = document.getElementById('citation-graph');
  if (!canvas) return;

  const labels = report.sources.map(s => s.domain);
  const agreements = report.sources.map(s => s.agreement_count);
  const conflicts = report.sources.map(s => s.conflict_count);

  new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: 'Agreements', data: agreements, backgroundColor: '#1D9E75' },
        { label: 'Conflicts',  data: conflicts,  backgroundColor: '#E24B4A' }
      ]
    },
    options: {
      responsive: true,
      plugins: { legend: { position: 'bottom' } },
      scales: { x: { stacked: true }, y: { stacked: true } }
    }
  });
}
```

---

## 9. DATA MODELS (Pydantic)

```python
# models/query_models.py
from pydantic import BaseModel
from typing import Optional

class QueryRequest(BaseModel):
    query: str
    mode: str = "research"        # quick | fact_check | research | deep_dive
    query_type: str = "single"    # single | compare | track | summarise_url
    domain_whitelist: list[str] = []
    domain_blacklist: list[str] = []
    url: Optional[str] = None     # for summarise_url mode

# models/agent_models.py
class SubQuery(BaseModel):
    query: str
    source_type: str
    priority: int

class QueryPlan(BaseModel):
    sub_queries: list[SubQuery]
    strategy: str

class RawClaim(BaseModel):
    claim: str
    source_url: str
    source_domain: str
    trust_score: int
    extracted_at: str

class VerifiedClaim(BaseModel):
    claim: str
    confidence: int
    supporting_sources: list[str]
    conflicting_sources: list[str]
    conflict_detail: str = ""
    resolution: str
    status: str  # verified | conflict | unresolved

class VerificationResult(BaseModel):
    verified_claims: list[VerifiedClaim]
    needs_requery: bool
    requery_topic: str = ""
    requery_tasks: list[SubQuery] = []
    overall_confidence: int

# models/report_models.py
class SourceSummary(BaseModel):
    url: str
    domain: str
    trust_tier: str
    trust_score: int
    agreement_count: int
    conflict_count: int
    discarded: bool

class FinalReport(BaseModel):
    query: str
    query_type: str
    mode: str
    verified_claims: list[VerifiedClaim]
    sources: list[SourceSummary]
    overall_confidence: int
    strategy_used: str
    total_sources_visited: int
    conflicts_detected: int
    conflicts_resolved: int
    compare_table: dict = {}     # populated for compare mode
    diff: dict = {}              # populated for track mode
    generated_at: str
```

---

## 10. MODES — BEHAVIOUR SPEC

| Mode | Sub-queries | Sources Target | Re-query Threshold | Approx Time |
|---|---|---|---|---|
| `quick` | 3 | 2–3 | Never | ~5 sec |
| `fact_check` | 4 | 3–5 | < 60% confidence | ~10 sec |
| `research` | 8 | 5–8 | < 70% confidence | ~20 sec |
| `deep_dive` | 15 | 10–20 | < 80% confidence | ~45 sec |

---

## 11. QUERY TYPES — OUTPUT SPEC

### `single` — Standard report
Output: List of verified claims with confidence + sources + conflict log

### `compare` — Side-by-side comparison
- Agent creates separate sub-query batches per entity
- Verification aligns results into matching criteria rows
- Output: Comparison table `{ criteria: [entity_a_value, entity_b_value, ...] }`
- Example: "Compare Jio vs Airtel vs Vi" → table with rows: subscribers, revenue, 5G coverage, growth rate

### `track` / `monitor` — Change detection
- Runs same query, compares to last saved report via diff engine
- Output: { added_claims, removed_claims, changed_confidence, unchanged }
- Stored in Supabase, can be scheduled via APScheduler

### `summarise_url` — URL verification
- Fetches target URL content directly
- Extracts all factual claims from the page
- Verifies each claim against external sources
- Output: Per-claim verdict (verified / false / unverifiable)

---

## 12. SUPABASE SCHEMA

```sql
-- Reports table
CREATE TABLE reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id TEXT UNIQUE NOT NULL,
  query TEXT NOT NULL,
  query_type TEXT NOT NULL,
  mode TEXT NOT NULL,
  report JSONB NOT NULL,
  overall_confidence INT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Scheduled monitors
CREATE TABLE monitors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id TEXT REFERENCES reports(session_id),
  query TEXT NOT NULL,
  mode TEXT NOT NULL,
  interval_hours INT DEFAULT 24,
  last_run TIMESTAMPTZ,
  next_run TIMESTAMPTZ,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Diff history (for track mode)
CREATE TABLE diffs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  monitor_id UUID REFERENCES monitors(id),
  old_session_id TEXT,
  new_session_id TEXT,
  diff JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## 13. ENVIRONMENT VARIABLES

```env
# .env — never commit this file
GEMINI_API_KEY=your_gemini_api_key
TAVILY_API_KEY=your_tavily_api_key
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:3000,https://your-frontend-domain.vercel.app
```

---

## 14. REQUIREMENTS.TXT

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
httpx==0.27.0
pydantic==2.8.0
python-dotenv==1.0.0
tavily-python==0.3.3
google-generativeai==0.7.2
beautifulsoup4==4.12.3
supabase==2.6.0
apscheduler==3.10.4
weasyprint==62.3
python-multipart==0.0.9
```

---

## 15. KEY GEMINI PROMPTING PATTERNS

### All Gemini calls MUST return JSON only
Always end prompts with:
```
Return ONLY valid JSON. No markdown, no explanation, no backticks. Just the raw JSON object.
```

### Temperature settings
- Planner agent: `temperature=0.3` (deterministic, structured)
- Extraction agent: `temperature=0.1` (precise fact extraction)
- Verification agent: `temperature=0.2` (consistent scoring)
- Report generator: `temperature=0.4` (slight creativity for summaries)

### gemini_service.py pattern
```python
import google.generativeai as genai
import os, asyncio

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

async def gemini_call(prompt: str, temperature: float = 0.2) -> str:
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=temperature)
        )
    )
    return response.text.strip()
```

---

## 16. SSE SERVICE

```python
# services/sse_service.py
import asyncio
from typing import Dict

_sessions: Dict[str, asyncio.Queue] = {}

def create_session(session_id: str):
    _sessions[session_id] = asyncio.Queue()

def get_session_queue(session_id: str) -> asyncio.Queue:
    return _sessions.get(session_id)

async def stream_event(session_id: str, event):
    queue = _sessions.get(session_id)
    if queue:
        await queue.put(event)

def cleanup_session(session_id: str):
    _sessions.pop(session_id, None)
```

---

## 17. UI LAYOUT — FINAL SPEC

```
┌────────────────────────────────────────────────────────────────────┐
│  WEBINTEL                                          [History] [About]│
├────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Ask anything...                           [Mode ▾] [Type ▾] │  │
│  │                                                  [Run Agent →]│  │
│  └──────────────────────────────────────────────────────────────┘  │
├───────────────────┬────────────────────────┬───────────────────────┤
│  AGENT TRACE      │  EXTRACTED CLAIMS       │  SOURCES VISITED      │
│                   │                         │                       │
│  ✓ Step 1         │  [Claim card]           │  ● NSE India  [High]  │
│  ✓ Step 2         │  [Claim card]           │  ● Reuters    [High]  │
│  ● Step 3 (live)  │  [Claim card ⚠]         │  ● Livemint   [Med]   │
│  ○ Step 4         │  [Claim card]           │  ✕ Blog       [Low]   │
│                   │                         │                       │
│  [Reasoning box]  │                         │  2 discarded          │
├───────────────────┴────────────────────────┴───────────────────────┤
│  CONFLICT LOG                    │  CITATION GRAPH                  │
│                                  │                                  │
│  ⚠ Claim X: A says Y, B says Z   │  [Bar chart: agreements vs       │
│  ✕ Claim W: 3-way conflict       │   conflicts per source]          │
│    → agent re-queried            │                                  │
├──────────────────────────────────┴──────────────────────────────────┤
│  [Download JSON]  [Export PDF]  [Send to Slack]  [Schedule Monitor] │
└─────────────────────────────────────────────────────────────────────┘
```

For **Compare mode**, the claims panel is replaced by a full comparison table:
```
┌─────────────────┬────────────────┬────────────────┬────────────────┐
│ Criteria        │ Entity A       │ Entity B       │ Entity C       │
├─────────────────┼────────────────┼────────────────┼────────────────┤
│ Market Cap      │ ₹19.8L cr ✓   │ ₹6.2L cr ✓    │ ₹4.1L cr ⚠    │
│ Revenue (Q3)    │ ₹2.41L cr ✓   │ ₹88K cr ✓     │ ₹72K cr ✓     │
│ Subscribers     │ 48.9 cr ✓     │ 37.5 cr ✓     │ 21.6 cr ⚠     │
└─────────────────┴────────────────┴────────────────┴────────────────┘
```

---

## 18. DEMO QUERIES (Prepare These 3 Before Presenting)

### Query 1 — Fact with conflict (shows verification)
```
"What is the current market cap of Reliance Industries?"
Mode: Research | Type: Single
```
Expected: Multi-source verification, show NSE vs BSE vs Moneycontrol slight variance → conflict log → resolution

### Query 2 — Compare (most impressive visually)
```
"Compare Jio vs Airtel vs Vi — subscribers, revenue, and 5G coverage"
Mode: Research | Type: Compare
```
Expected: Parallel agents per entity, comparison table output, citation graph

### Query 3 — Deep dive with re-query (shows autonomy)
```
"What are the latest AI regulations being considered in India?"
Mode: Deep Dive | Type: Single
```
Expected: Agent re-queries after first pass, shows evolving confidence scores, government + news sources

---

## 19. STARTUP COMMANDS

```bash
# Backend
cd webintel-backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (just open index.html or serve via FastAPI /static)
# Frontend is already mounted at /static in main.py

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 20. IMPORTANT GOTCHAS

1. **Gemini is synchronous** — always wrap in `loop.run_in_executor()` to avoid blocking the FastAPI event loop
2. **SSE needs `Cache-Control: no-cache`** — add to StreamingResponse headers or browser will buffer
3. **Tavily returns max 10 results** — for Deep Dive mode, run multiple Tavily calls with different queries
4. **asyncio.gather fails fast** — use `return_exceptions=True` so one failing agent doesn't kill all others
5. **Supabase JSONB** — store full report as JSONB, don't try to normalise every claim into rows
6. **CORS** — FastAPI CORS middleware must be added BEFORE mounting static files
7. **APScheduler in FastAPI** — use `BackgroundScheduler`, start it in `@app.on_event("startup")`
8. **WeasyPrint needs system fonts** — on Railway/Render, add a `Dockerfile` with `apt-get install -y weasyprint`

---

*GEMINI.md — Antigravity | WebIntel | Built for speed, built to win*