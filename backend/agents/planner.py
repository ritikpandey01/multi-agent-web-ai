"""Planner Agent — decomposes user query into sub-queries using Gemini.

The number of sub-queries depends on the mode:
- quick: 3
- fact_check: 4
- research: 8
- deep_dive: 15

For compare-mode queries, also extracts entities to compare.
"""

from typing import List
from models.agent_models import SubQuery, PlannerOutput
from services.llm_service import call_llm_json

MODE_SUBQUERY_COUNT = {
    "quick": 3,
    "fact_check": 4,
    "research": 8,
    "deep_dive": 15,
}


async def plan_query(query: str, mode: str, query_type: str) -> PlannerOutput:
    """Break a user query into focused sub-queries via Gemini."""
    count = MODE_SUBQUERY_COUNT.get(mode, 3)

    if query_type == "compare":
        return await _plan_compare(query, count)
    elif query_type == "summarise_url":
        return PlannerOutput(sub_queries=[
            SubQuery(query=f"Verify claims from: {query}", source_type="general")
        ])
    else:
        return await _plan_single(query, count)


async def _plan_single(query: str, count: int) -> PlannerOutput:
    """Plan sub-queries for a single/track query."""
    prompt = f"""You are a research planner. Break the following query into exactly {count} focused sub-queries for web search.

Each sub-query should target a different angle or source type.
Assign each a source_type from: news, official, academic, financial, general.

Query: "{query}"

Return ONLY valid JSON with this exact structure:
{{
  "sub_queries": [
    {{"query": "specific search query", "source_type": "news", "priority": 1}},
    ...
  ]
}}

Return only raw JSON. No markdown, no explanation."""

    result = await call_llm_json(prompt)

    sub_queries = []
    for sq in result.get("sub_queries", []):
        sub_queries.append(SubQuery(
            query=sq.get("query", query),
            source_type=sq.get("source_type", "general"),
            priority=sq.get("priority", 1),
        ))

    # Fallback if Gemini didn't return enough
    if not sub_queries:
        sub_queries = [SubQuery(query=query, source_type="general")]

    return PlannerOutput(sub_queries=sub_queries)


async def _plan_compare(query: str, count: int) -> PlannerOutput:
    """Plan sub-queries for a compare-mode query — one batch per entity."""
    prompt = f"""You are a research planner. The user wants to compare entities.

Query: "{query}"

1. Extract the entities being compared.
2. For each entity, create {max(2, count // 3)} focused sub-queries covering different aspects.
3. Assign source_type from: news, official, academic, financial, general.

Return ONLY valid JSON:
{{
  "entities": ["Entity1", "Entity2", ...],
  "sub_queries": [
    {{"query": "specific query about Entity1", "source_type": "news", "priority": 1}},
    ...
  ]
}}

Return only raw JSON. No markdown, no explanation."""

    result = await call_llm_json(prompt)

    entities = result.get("entities", [])
    sub_queries = []
    for sq in result.get("sub_queries", []):
        sub_queries.append(SubQuery(
            query=sq.get("query", query),
            source_type=sq.get("source_type", "general"),
            priority=sq.get("priority", 1),
        ))

    if not sub_queries:
        sub_queries = [SubQuery(query=query, source_type="general")]

    return PlannerOutput(sub_queries=sub_queries, entities=entities)
