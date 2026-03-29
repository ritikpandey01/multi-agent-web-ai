"""Search Agent — runs parallel Tavily searches for all sub-queries.

Uses asyncio.gather with return_exceptions=True so one failure
never crashes the whole pipeline.
"""

import asyncio
from typing import List, Dict
from models.agent_models import SubQuery, RawSearchResult
from services import tavily_service

# Source type → preferred domains (optional filtering)
SOURCE_TYPE_DOMAINS: Dict[str, List[str]] = {
    "official": ["gov.in", "nic.in", "nseindia.com", "bseindia.com", "rbi.org.in", "sebi.gov.in"],
    "academic": ["wikipedia.org", "britannica.com", "scholar.google.com"],
    "financial": ["moneycontrol.com", "investing.com", "nseindia.com", "bseindia.com", "marketwatch.com"],
}


async def _search_one(sub_query: SubQuery, max_results: int = 5) -> List[RawSearchResult]:
    """Search for a single sub-query."""
    domains = SOURCE_TYPE_DOMAINS.get(sub_query.source_type)
    return await tavily_service.search(
        query=sub_query.query,
        max_results=max_results,
        include_domains=domains,
    )


async def search_parallel(sub_queries: List[SubQuery], max_results_per: int = 5) -> List[RawSearchResult]:
    """Run all sub-query searches in parallel and flatten results.
    
    Failed searches are logged and skipped — never crash the pipeline.
    """
    tasks = [_search_one(sq, max_results_per) for sq in sub_queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_results: List[RawSearchResult] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"[SearchAgent] Sub-query {i} failed: {result}")
            continue
        if isinstance(result, list):
            all_results.extend(result)

    # Deduplicate by URL
    seen_urls = set()
    unique: List[RawSearchResult] = []
    for r in all_results:
        if r.url not in seen_urls:
            seen_urls.add(r.url)
            unique.append(r)

    return unique
