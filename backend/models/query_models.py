"""Pydantic models for incoming API requests."""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class QueryMode(str, Enum):
    quick = "quick"
    fact_check = "fact_check"
    research = "research"
    deep_dive = "deep_dive"


class QueryType(str, Enum):
    single = "single"
    compare = "compare"
    track = "track"
    summarise_url = "summarise_url"


class QueryRequest(BaseModel):
    """Main query request from the user."""
    query: str = Field(..., description="The user's question or search query")
    mode: QueryMode = Field(default=QueryMode.quick, description="Depth of analysis")
    query_type: QueryType = Field(default=QueryType.single, description="Type of query")

    model_config = {"json_schema_extra": {
        "examples": [{
            "query": "What is the current market cap of Reliance Industries?",
            "mode": "research",
            "query_type": "single"
        }]
    }}


class MonitorCreateRequest(BaseModel):
    """Request to create a scheduled monitor job."""
    query: str
    mode: QueryMode = QueryMode.research
    query_type: QueryType = QueryType.single
    interval_hours: int = Field(default=24, ge=1, le=168, description="Re-run interval in hours")
