"""Pydantic models for the final report output."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class VerifiedClaim(BaseModel):
    """A single verified claim with confidence and source info."""
    claim: str
    confidence: float = Field(..., ge=0, le=100)
    supporting_sources: List[str] = []
    conflicting_sources: List[str] = []
    conflict_detail: Optional[str] = None
    resolution_method: Optional[str] = None
    status: str = Field(default="verified", description="verified | conflict | unresolved")


class SourceInfo(BaseModel):
    """Information about a source visited during research."""
    url: str
    domain: str
    trust_tier: str = Field(default="unknown", description="high | medium | low | unknown")
    trust_score: int = Field(default=45, ge=0, le=100)
    agreement_count: int = 0
    conflict_count: int = 0
    discarded: bool = False


class CompareCell(BaseModel):
    """One cell in a comparison table."""
    value: str
    confidence: float = 0
    source: Optional[str] = None


class CompareTable(BaseModel):
    """Comparison table for compare-mode queries."""
    criteria: List[str] = []
    entities: List[str] = []
    data: Dict[str, Dict[str, CompareCell]] = {}


class DiffItem(BaseModel):
    """A single diff entry between two reports."""
    type: str = Field(..., description="added | removed | changed")
    claim: str
    old_confidence: Optional[float] = None
    new_confidence: Optional[float] = None


class DiffResult(BaseModel):
    """Full diff between old and new report."""
    added: List[DiffItem] = []
    removed: List[DiffItem] = []
    changed: List[DiffItem] = []


class FinalReport(BaseModel):
    """The complete report returned to the user."""
    session_id: str
    query: str
    query_type: str
    mode: str
    verified_claims: List[VerifiedClaim] = []
    sources: List[SourceInfo] = []
    overall_confidence: float = 0
    compare_table: Optional[CompareTable] = None
    diff: Optional[DiffResult] = None
    total_sources_visited: int = 0
    conflicts_detected: int = 0
    conflicts_resolved: int = 0
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
