"""Verification Agent — groups claims, scores confidence, detects conflicts.

Groups similar claims from different sources, compares them,
detects conflicts, and scores confidence. Can trigger re-query
if confidence is below the mode's threshold.
"""

from typing import List, Dict, Tuple
from models.agent_models import ExtractedClaim, VerificationResult
from models.report_models import VerifiedClaim, SourceInfo
from services.llm_service import call_llm_json
from utils.trust_scorer import get_trust_info
from utils.conflict_resolver import resolve_conflict, compute_confidence

# Mode → minimum confidence threshold to avoid re-query
REQUERY_THRESHOLDS = {
    "quick": 0,        # Never re-queries
    "fact_check": 60,
    "research": 70,
    "deep_dive": 80,
}


async def verify_claims(
    claims: List[ExtractedClaim],
    mode: str,
) -> Tuple[List[VerifiedClaim], List[SourceInfo], float]:
    """Verify extracted claims: group, score confidence, detect conflicts.
    
    Returns:
        (verified_claims, source_infos, overall_confidence)
    """
    if not claims:
        return [], [], 0

    # Step 1: Group similar claims using Gemini
    grouped = await _group_claims(claims)

    # Step 2: Build source info map
    all_urls = list(set(c.source_url for c in claims if c.source_url))
    source_map: Dict[str, SourceInfo] = {}
    for url in all_urls:
        domain, tier, score = get_trust_info(url)
        source_map[url] = SourceInfo(
            url=url,
            domain=domain,
            trust_tier=tier,
            trust_score=score,
        )

    # Step 3: Verify each group
    verified_claims: List[VerifiedClaim] = []
    total_conflicts = 0
    total_resolved = 0

    for group in grouped:
        if not group:
            continue

        # Get trust tiers for sources in this group
        source_urls = list(set(c.get("source_url", "") for c in group))
        trust_tiers_map = {}
        trust_tiers_list = []
        for url in source_urls:
            if url in source_map:
                trust_tiers_map[url] = source_map[url].trust_tier
                trust_tiers_list.append(source_map[url].trust_tier)

        # Check for conflicts within the group
        unique_claims = list(set(c.get("claim", "") for c in group))
        has_conflict = len(unique_claims) > 1

        if has_conflict:
            total_conflicts += 1
            winning_claim, method, detail = resolve_conflict(group, trust_tiers_map)
            if method != "unresolved":
                total_resolved += 1

            # Track agreements and conflicts on sources
            for url in source_urls:
                if url in source_map:
                    # Check if this source supported the winning claim
                    source_claims = [c["claim"] for c in group if c.get("source_url") == url]
                    if winning_claim in source_claims:
                        source_map[url].agreement_count += 1
                    else:
                        source_map[url].conflict_count += 1

            confidence = compute_confidence(
                supporting_count=sum(1 for c in group if c.get("claim") == winning_claim),
                conflicting_count=len(unique_claims) - 1,
                trust_tiers=trust_tiers_list,
                has_active_conflict=(method == "unresolved"),
            )

            supporting = [c.get("source_url", "") for c in group if c.get("claim") == winning_claim]
            conflicting = [c.get("source_url", "") for c in group if c.get("claim") != winning_claim]

            verified_claims.append(VerifiedClaim(
                claim=winning_claim,
                confidence=confidence,
                supporting_sources=list(set(supporting)),
                conflicting_sources=list(set(conflicting)),
                conflict_detail=detail,
                resolution_method=method,
                status="conflict" if method == "unresolved" else "verified",
            ))
        else:
            # No conflict — all sources agree
            claim_text = group[0].get("claim", "")
            for url in source_urls:
                if url in source_map:
                    source_map[url].agreement_count += 1

            confidence = compute_confidence(
                supporting_count=len(source_urls),
                conflicting_count=0,
                trust_tiers=trust_tiers_list,
                has_active_conflict=False,
            )

            verified_claims.append(VerifiedClaim(
                claim=claim_text,
                confidence=confidence,
                supporting_sources=source_urls,
                status="verified",
            ))

    # Overall confidence
    if verified_claims:
        overall = sum(c.confidence for c in verified_claims) / len(verified_claims)
    else:
        overall = 0

    source_list = list(source_map.values())

    return verified_claims, source_list, round(overall, 1)


async def _group_claims(claims: List[ExtractedClaim]) -> List[List[dict]]:
    """Group similar/related claims together using Gemini."""
    if len(claims) <= 1:
        return [[{"claim": c.claim, "source_url": c.source_url, "timestamp": c.timestamp} for c in claims]]

    claims_text = "\n".join(
        f'{i+1}. "{c.claim}" (source: {c.source_url})'
        for i, c in enumerate(claims[:40])  # Cap for context
    )

    prompt = f"""You are a claims grouping engine. Group the following claims by topic/subject.
Claims about the same fact (even if they disagree on the specifics) should be in the same group.

Claims:
{claims_text}

Return ONLY valid JSON:
{{
  "groups": [
    [1, 5, 12],
    [2, 8],
    [3],
    ...
  ]
}}

Each group is a list of claim numbers (1-indexed) that are about the same topic.
Return only raw JSON. No markdown, no explanation."""

    result = await call_llm_json(prompt)

    # Map indices back to claim dicts
    groups = []
    claims_list = [
        {"claim": c.claim, "source_url": c.source_url, "timestamp": c.timestamp}
        for c in claims[:40]
    ]

    for group_indices in result.get("groups", []):
        group = []
        for idx in group_indices:
            if isinstance(idx, int) and 1 <= idx <= len(claims_list):
                group.append(claims_list[idx - 1])
        if group:
            groups.append(group)

    # Any claims not in any group get their own group
    grouped_indices = set()
    for g in result.get("groups", []):
        for idx in g:
            if isinstance(idx, int):
                grouped_indices.add(idx)

    for i, c in enumerate(claims_list):
        if (i + 1) not in grouped_indices:
            groups.append([c])

    return groups if groups else [[c] for c in claims_list]


def needs_requery(mode: str, overall_confidence: float, verified_claims: List[VerifiedClaim]) -> bool:
    """Check if a re-query is needed based on mode thresholds."""
    threshold = REQUERY_THRESHOLDS.get(mode, 0)
    if threshold == 0:
        return False

    if mode == "fact_check":
        # Re-query if ANY claim below 60
        return any(c.confidence < 60 for c in verified_claims)
    else:
        # Re-query if overall confidence below threshold
        return overall_confidence < threshold
