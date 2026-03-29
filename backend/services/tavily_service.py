"""Wrapper for Tavily search API calls."""

import os
from typing import List, Optional
from tavily import TavilyClient
from dotenv import load_dotenv
from models.agent_models import RawSearchResult

load_dotenv()

_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


async def search(query: str, max_results: int = 5, search_depth: str = "basic",
                 include_domains: Optional[List[str]] = None) -> List[RawSearchResult]:
    """Run a Tavily search and return structured results.
    
    Tavily's client is synchronous but fast enough for our use.
    We wrap in asyncio for consistency but the actual call is sync.
    """
    import asyncio
    import functools

    def _search_sync():
        kwargs = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
        }
        if include_domains:
            kwargs["include_domains"] = include_domains

        try:
            response = _client.search(**kwargs)
            results = []
            for item in response.get("results", []):
                results.append(RawSearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("content", ""),
                    score=item.get("score", 0.0),
                ))
            return results
        except Exception as e:
            print(f"[Tavily] Search error for '{query}': {e}")
            return []

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _search_sync)
