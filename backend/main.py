"""FastAPI application — all routes, SSE endpoint, CORS, startup/shutdown.

Routes:
  POST /auth/register    — Create account
  POST /auth/login       — Login
  GET  /auth/me          — Current user info
  POST /query            — Submit a new query, starts the pipeline
  GET  /stream/{id}      — SSE stream for live updates
  GET  /reports           — List recent reports
  GET  /reports/{id}      — Get specific report
  POST /monitors          — Create a scheduled monitor
  GET  /monitors          — List all monitors
  GET  /export/{id}/json  — Export report as JSON
  GET  /export/{id}/pdf   — Export report as PDF
"""

import uuid
import json
import asyncio
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from models.query_models import QueryRequest, MonitorCreateRequest
from services import sse_service, supabase_service
from services.export_service import export_json, generate_pdf
from scheduler.monitor_scheduler import start_scheduler, shutdown_scheduler
from _pipeline import run_pipeline
from auth import router as auth_router, get_current_user


# ─── Lifespan ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    start_scheduler()
    print("🚀 WebIntel backend started")
    yield
    shutdown_scheduler()
    print("🛑 WebIntel backend stopped")


# ─── App ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="WebIntel API",
    description="Autonomous Multi-Agent Web Intelligence System",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include auth router
app.include_router(auth_router)


# ─── Static File Serving ────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "Backend is running"}


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "WebIntel", "version": "2.0.0"}


@app.post("/query", tags=["Query"])
async def submit_query(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Submit a new query. Returns session_id immediately, starts pipeline in background.
    
    Connect to GET /stream/{session_id} for live updates via SSE.
    """
    session_id = str(uuid.uuid4())

    # Create SSE queue for this session
    sse_service.create_session(session_id)

    # Run pipeline in background so we return session_id immediately
    background_tasks.add_task(
        run_pipeline,
        query=request.query,
        mode=request.mode.value,
        query_type=request.query_type.value,
        session_id=session_id,
        user_id=user["id"],
    )

    return {
        "session_id": session_id,
        "message": "Query submitted. Connect to /stream/{session_id} for live updates.",
        "stream_url": f"/stream/{session_id}",
    }


@app.get("/stream/{session_id}", tags=["Stream"])
async def stream_events(session_id: str):
    """SSE endpoint — streams live agent updates for a session.
    
    Event types: trace, claim, report, error, done
    """
    queue = sse_service.get_session(session_id)
    if not queue:
        raise HTTPException(status_code=404, detail="Session not found. Submit a query first.")

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=120)
                except asyncio.TimeoutError:
                    yield f"event: keepalive\ndata: {{}}\n\n"
                    continue

                event_type = event.get("event", "message")
                data = json.dumps(event.get("data", {}))
                yield f"event: {event_type}\ndata: {data}\n\n"

                if event_type == "done":
                    break
        finally:
            sse_service.cleanup_session(session_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/reports", tags=["Reports"])
async def list_reports(
    limit: int = 20,
    user: dict = Depends(get_current_user),
):
    """Get recent reports for the authenticated user."""
    reports = await supabase_service.get_reports(limit=limit, user_id=user["id"])
    return {"reports": reports, "count": len(reports)}


@app.get("/reports/{session_id}", tags=["Reports"])
async def get_report(
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """Get a specific report by session ID."""
    report = await supabase_service.get_report_by_session(session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@app.post("/monitors", tags=["Monitors"])
async def create_monitor(
    request: MonitorCreateRequest,
    user: dict = Depends(get_current_user),
):
    """Create a new scheduled monitor job."""
    monitor = await supabase_service.create_monitor(
        query=request.query,
        mode=request.mode.value,
        query_type=request.query_type.value,
        interval_hours=request.interval_hours,
    )
    return {"monitor": monitor, "message": "Monitor created successfully"}


@app.get("/monitors", tags=["Monitors"])
async def list_monitors(user: dict = Depends(get_current_user)):
    """List all monitor jobs."""
    monitors = await supabase_service.get_monitors()
    return {"monitors": monitors, "count": len(monitors)}


@app.get("/export/{session_id}/json", tags=["Export"])
async def export_report_json(
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """Export a report as JSON file download."""
    report = await supabase_service.get_report_by_session(session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    json_content = export_json(report.get("report", report))
    return Response(
        content=json_content,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=webintel-{session_id[:8]}.json"},
    )


@app.get("/export/{session_id}/pdf", tags=["Export"])
async def export_report_pdf(
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """Export a report as PDF download."""
    report = await supabase_service.get_report_by_session(session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    pdf_bytes = generate_pdf(report.get("report", report))
    if not pdf_bytes:
        raise HTTPException(status_code=500, detail="PDF generation failed. WeasyPrint may not be installed.")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=webintel-{session_id[:8]}.pdf"},
    )
