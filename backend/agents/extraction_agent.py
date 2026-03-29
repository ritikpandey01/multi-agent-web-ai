"""Extraction Agent — pulls structured atomic claims from raw search content.

Calls Gemini to extract {claim, source_url, timestamp} objects from
the raw content collected by the search agent.
"""

from typing import List
from models.agent_models import RawSearchResult, ExtractedClaim
from services.llm_service import call_llm_json


async def extract_claims(search_results: List[RawSearchResult]) -> List[ExtractedClaim]:
    """Extract structured claims from all search results via Gemini.
    
    Batches content to avoid exceeding context limits, then merges.
    """
    if not search_results:
        return []

    # Build context from search results
    context_parts = []
    for i, result in enumerate(search_results[:20]):  # Cap to prevent context overflow
        context_parts.append(
            f"[Source {i+1}] URL: {result.url}\n"
            f"Title: {result.title}\n"
            f"Content: {result.content[:1500]}\n"
        )

    context = "\n---\n".join(context_parts)

    prompt = f"""You are a fact extraction engine. Extract ALL distinct, atomic factual claims from the following search results.

Each claim must be:
- A single, specific, verifiable statement
- Attributed to its source URL
- Include a timestamp if mentioned in the content

Search Results:
{context}

Return ONLY valid JSON with this exact structure:
{{
  "claims": [
    {{"claim": "specific factual statement", "source_url": "https://...", "timestamp": "2024-01-15 or null"}},
    ...
  ]
}}

Extract as many distinct facts as possible. Do NOT summarize — extract specific claims.
Return only raw JSON. No markdown, no explanation."""

    result = await call_llm_json(prompt)

    claims = []
    for c in result.get("claims", []):
        claims.append(ExtractedClaim(
            claim=c.get("claim", ""),
            source_url=c.get("source_url", ""),
            timestamp=c.get("timestamp"),
        ))

    return claims
