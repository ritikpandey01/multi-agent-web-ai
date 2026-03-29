"""In-memory SSE session queue management.

Each session gets its own asyncio.Queue. Events are pushed by agents
and consumed by the SSE streaming endpoint.
"""

import asyncio
from typing import Dict, Any

# Session ID → asyncio.Queue
_sessions: Dict[str, asyncio.Queue] = {}


def create_session(session_id: str) -> asyncio.Queue:
    """Create a new SSE queue for a session."""
    queue = asyncio.Queue()
    _sessions[session_id] = queue
    return queue


def get_session(session_id: str) -> asyncio.Queue | None:
    """Get the queue for a session, or None if it doesn't exist."""
    return _sessions.get(session_id)


async def push_event(session_id: str, event_type: str, data: Any) -> None:
    """Push an event to a session's queue.
    
    Event types: trace, claim, report, error, done
    """
    queue = _sessions.get(session_id)
    if queue:
        await queue.put({"event": event_type, "data": data})


async def push_trace(session_id: str, step: int, message: str) -> None:
    """Convenience: push a trace event."""
    await push_event(session_id, "trace", {"step": step, "message": message})


async def push_claim(session_id: str, claim: dict) -> None:
    """Convenience: push a single verified claim event."""
    await push_event(session_id, "claim", claim)


async def push_error(session_id: str, message: str) -> None:
    """Convenience: push an error event."""
    await push_event(session_id, "error", {"message": message})


async def push_done(session_id: str) -> None:
    """Convenience: push the done event to signal stream end."""
    await push_event(session_id, "done", {})


def cleanup_session(session_id: str) -> None:
    """Remove a session's queue after the stream ends."""
    _sessions.pop(session_id, None)
