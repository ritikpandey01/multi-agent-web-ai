"""Monitor Scheduler — APScheduler setup for recurring queries.

Starts in FastAPI's startup event, shuts down cleanly in shutdown.
Checks the monitors table for due jobs and runs them.
"""

import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def start_scheduler():
    """Start the scheduler. Call from FastAPI startup event."""
    scheduler = get_scheduler()
    if not scheduler.running:
        # Add the check_monitors job — runs every 5 minutes
        scheduler.add_job(
            _check_monitors,
            trigger=IntervalTrigger(minutes=5),
            id="check_monitors",
            replace_existing=True,
        )
        scheduler.start()
        print("[Scheduler] Started — checking monitors every 5 minutes")


def shutdown_scheduler():
    """Shut down the scheduler cleanly. Call from FastAPI shutdown event."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        print("[Scheduler] Shut down")
    _scheduler = None


async def _check_monitors():
    """Check for due monitor jobs and run them."""
    try:
        from services.supabase_service import get_monitors, update_monitor_run, get_report_by_session
        
        monitors = await get_monitors()
        now = datetime.utcnow()

        for monitor in monitors:
            if not monitor.get("active", False):
                continue

            next_run = monitor.get("next_run")
            if next_run and datetime.fromisoformat(next_run) > now:
                continue

            # This monitor is due — run it
            print(f"[Scheduler] Running monitor: {monitor.get('query', '')}")

            try:
                # Import here to avoid circular imports
                from _pipeline import run_pipeline

                query = monitor.get("query", "")
                mode = monitor.get("mode", "research")
                query_type = monitor.get("query_type", "track")

                # Run the pipeline (without SSE streaming for background jobs)
                await run_pipeline(
                    query=query,
                    mode=mode,
                    query_type=query_type,
                    session_id=None,  # No SSE for background
                )

                # Update next run time
                interval = monitor.get("interval_hours", 24)
                next_run_time = (now + timedelta(hours=interval)).isoformat()
                await update_monitor_run(monitor["id"], next_run_time)

            except Exception as e:
                print(f"[Scheduler] Error running monitor {monitor.get('id')}: {e}")

    except Exception as e:
        print(f"[Scheduler] Error checking monitors: {e}")
