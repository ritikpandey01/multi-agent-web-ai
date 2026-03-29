"""Internal data structures used between agents."""

from pydantic import BaseModel, Field
from typing import List, Optional


class SubQuery(BaseModel):
    """A single sub-query produced by the Planner agent."""
    query: str
    source_type: str = Field(default="general", description="news | official | academic | financial | general")
    priority: int = 1


class PlannerOutput(BaseModel):
    """Output from the Planner agent."""
    sub_queries: List[SubQuery] = []
    entities: List[str] = []  # For compare mode — list of entities to compare


class RawSearchResult(BaseModel):
    """A single search result from Tavily."""
    title: str = ""
    url: str = ""
    content: str = ""
    score: float = 0.0


class ExtractedClaim(BaseModel):
    """A single atomic claim extracted from search content."""
    claim: str
    source_url: str = ""
    timestamp: Optional[str] = None


class VerificationResult(BaseModel):
    """Result of verifying a group of related claims."""
    canonical_claim: str
    confidence: float = 0
    supporting_sources: List[str] = []
    conflicting_sources: List[str] = []
    conflict_detail: Optional[str] = None
    resolution_method: Optional[str] = None
    status: str = "verified"
