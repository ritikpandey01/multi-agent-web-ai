"""Supabase database service — read/write helpers for reports, monitors, diffs, users."""

import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_url = os.getenv("SUPABASE_URL", "")
_key = os.getenv("SUPABASE_KEY", "")

_client: Optional[Client] = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(_url, _key)
    return _client


# ─── Reports ────────────────────────────────────────────────────────────────

async def save_report(session_id: str, query: str, mode: str, query_type: str,
                      report: dict, overall_confidence: float,
                      user_id: Optional[str] = None) -> dict:
    """Save a completed report to the reports table."""
    try:
        client = _get_client()
        data = {
            "session_id": session_id,
            "query": query,
            "mode": mode,
            "query_type": query_type,
            "report": report,
            "overall_confidence": overall_confidence,
            "created_at": datetime.utcnow().isoformat(),
        }
        if user_id:
            data["user_id"] = user_id
        result = client.table("reports").insert(data).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        print(f"[Supabase] Error saving report: {e}")
        return {}


async def get_reports(limit: int = 20, user_id: Optional[str] = None) -> List[dict]:
    """Get recent reports ordered by creation time, optionally filtered by user."""
    try:
        client = _get_client()
        query = client.table("reports").select("*").order(
            "created_at", desc=True
        ).limit(limit)
        if user_id:
            query = query.eq("user_id", user_id)
        result = query.execute()
        return result.data or []
    except Exception as e:
        print(f"[Supabase] Error fetching reports: {e}")
        return []


async def get_report_by_session(session_id: str) -> Optional[dict]:
    """Get a specific report by session_id."""
    try:
        client = _get_client()
        result = client.table("reports").select("*").eq(
            "session_id", session_id
        ).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"[Supabase] Error fetching report {session_id}: {e}")
        return None


# ─── Monitors ───────────────────────────────────────────────────────────────

async def create_monitor(query: str, mode: str, query_type: str,
                         interval_hours: int) -> dict:
    """Create a new monitor job."""
    try:
        client = _get_client()
        now = datetime.utcnow().isoformat()
        data = {
            "query": query,
            "mode": mode,
            "query_type": query_type,
            "interval_hours": interval_hours,
            "last_run": None,
            "next_run": now,
            "active": True,
        }
        result = client.table("monitors").insert(data).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        print(f"[Supabase] Error creating monitor: {e}")
        return {}


async def get_monitors() -> List[dict]:
    """Get all monitor jobs."""
    try:
        client = _get_client()
        result = client.table("monitors").select("*").order("created_at", desc=True).execute()
        return result.data or []
    except Exception as e:
        print(f"[Supabase] Error fetching monitors: {e}")
        return []


async def update_monitor_run(monitor_id: int, next_run: str) -> None:
    """Update last_run and next_run for a monitor."""
    try:
        client = _get_client()
        client.table("monitors").update({
            "last_run": datetime.utcnow().isoformat(),
            "next_run": next_run,
        }).eq("id", monitor_id).execute()
    except Exception as e:
        print(f"[Supabase] Error updating monitor {monitor_id}: {e}")


# ─── Diffs ──────────────────────────────────────────────────────────────────

async def save_diff(old_session_id: str, new_session_id: str, diff: dict) -> dict:
    """Save a diff between two report runs."""
    try:
        client = _get_client()
        data = {
            "old_session_id": old_session_id,
            "new_session_id": new_session_id,
            "diff": diff,
            "created_at": datetime.utcnow().isoformat(),
        }
        result = client.table("diffs").insert(data).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        print(f"[Supabase] Error saving diff: {e}")
        return {}
