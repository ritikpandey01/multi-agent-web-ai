"""Report Agent — assembles the final structured report.

Handles all query types:
- single: claim list + sources + conflict log
- compare: comparison table with per-entity data
- track: diff view against previous report
- summarise_url: verified claims from a specific URL
"""

from typing import List, Optional
from datetime import datetime
from models.report_models import (
    FinalReport, VerifiedClaim, SourceInfo,
    CompareTable, CompareCell, DiffResult,
)
from services.llm_service import call_llm_json


async def assemble_report(
    session_id: str,
    query: str,
    mode: str,
    query_type: str,
    verified_claims: List[VerifiedClaim],
    sources: List[SourceInfo],
    overall_confidence: float,
    entities: Optional[List[str]] = None,
    previous_report: Optional[dict] = None,
) -> FinalReport:
    """Assemble the final report from verified data."""

    compare_table = None
    diff_result = None

    # Build compare table if in compare mode
    if query_type == "compare" and entities:
        compare_table = await _build_compare_table(verified_claims, entities, query)

    # Build diff if in track mode and there's a previous report
    if query_type == "track" and previous_report:
        from utils.diff_engine import diff_reports
        current_data = {
            "verified_claims": [c.model_dump() for c in verified_claims]
        }
        diff_result = diff_reports(previous_report, current_data)

    # Count stats
    conflicts_detected = sum(
        1 for c in verified_claims
        if c.conflicting_sources or c.status in ("conflict", "unresolved")
    )
    conflicts_resolved = sum(
        1 for c in verified_claims
        if c.resolution_method and c.resolution_method != "unresolved"
    )

    return FinalReport(
        session_id=session_id,
        query=query,
        query_type=query_type,
        mode=mode,
        verified_claims=verified_claims,
        sources=sources,
        overall_confidence=overall_confidence,
        compare_table=compare_table,
        diff=diff_result,
        total_sources_visited=len(sources),
        conflicts_detected=conflicts_detected,
        conflicts_resolved=conflicts_resolved,
        generated_at=datetime.utcnow().isoformat(),
    )


async def _build_compare_table(
    claims: List[VerifiedClaim],
    entities: List[str],
    query: str,
) -> CompareTable:
    """Build a comparison table from verified claims using Gemini."""
    claims_text = "\n".join(
        f'- "{c.claim}" (confidence: {c.confidence}%)'
        for c in claims
    )

    prompt = f"""You are building a comparison table. 

Original query: "{query}"
Entities to compare: {entities}

Verified claims:
{claims_text}

Build a comparison table with criteria as rows and entities as columns.
Assign each cell a value and confidence score.

Return ONLY valid JSON:
{{
  "criteria": ["criterion1", "criterion2", ...],
  "data": {{
    "criterion1": {{
      "Entity1": {{"value": "some value", "confidence": 85}},
      "Entity2": {{"value": "some value", "confidence": 72}}
    }},
    ...
  }}
}}

Return only raw JSON. No markdown, no explanation."""

    result = await call_llm_json(prompt)

    criteria = result.get("criteria", [])
    data = {}
    for criterion in criteria:
        criterion_data = result.get("data", {}).get(criterion, {})
        data[criterion] = {}
        for entity in entities:
            cell = criterion_data.get(entity, {})
            data[criterion][entity] = CompareCell(
                value=cell.get("value", "N/A"),
                confidence=cell.get("confidence", 0),
            )

    return CompareTable(
        criteria=criteria,
        entities=entities,
        data=data,
    )
