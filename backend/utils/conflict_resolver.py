"""Conflict detection and resolution logic.

Conflict Detection:
- Numeric claims: >3% variance = conflict
- Factual claims: directly contradictory = conflict
- Same claim from same domain: deduplicated

Conflict Resolution Priority:
1. Official/government source wins
2. Majority agreement wins
3. Most recent timestamp wins
4. Otherwise → unresolved
"""

from typing import List, Dict, Optional, Tuple
from models.agent_models import VerificationResult


def detect_numeric_conflict(values: List[float], threshold: float = 0.03) -> bool:
    """Check if numeric values have >3% variance."""
    if len(values) < 2:
        return False
    avg = sum(values) / len(values)
    if avg == 0:
        return False
    for v in values:
        if abs(v - avg) / abs(avg) > threshold:
            return True
    return False


def resolve_conflict(
    claims: List[dict],
    source_trust_tiers: Dict[str, str],
) -> Tuple[str, str, Optional[str]]:
    """Resolve a conflict among competing claims.
    
    Args:
        claims: list of {"claim": str, "source_url": str, "timestamp": str}
        source_trust_tiers: mapping of source_url → trust tier
    
    Returns:
        (winning_claim, resolution_method, conflict_detail)
    """
    if not claims:
        return ("", "none", None)

    # 1. Official source wins
    for c in claims:
        tier = source_trust_tiers.get(c.get("source_url", ""), "unknown")
        if tier == "high":
            return (
                c["claim"],
                "official_source",
                f"Resolved via official/high-trust source: {c.get('source_url', '')}"
            )

    # 2. Majority agreement
    claim_counts: Dict[str, int] = {}
    for c in claims:
        text = c["claim"].strip().lower()
        claim_counts[text] = claim_counts.get(text, 0) + 1

    if claim_counts:
        majority = max(claim_counts, key=claim_counts.get)
        majority_count = claim_counts[majority]
        if majority_count > len(claims) / 2:
            # Find original claim text (not lowered)
            for c in claims:
                if c["claim"].strip().lower() == majority:
                    return (
                        c["claim"],
                        "majority_agreement",
                        f"Resolved by majority ({majority_count}/{len(claims)} sources agree)"
                    )

    # 3. Most recent timestamp
    dated_claims = [c for c in claims if c.get("timestamp")]
    if dated_claims:
        latest = max(dated_claims, key=lambda c: c["timestamp"])
        return (
            latest["claim"],
            "most_recent",
            f"Resolved by most recent source (timestamp: {latest['timestamp']})"
        )

    # 4. Unresolved
    all_claims = "; ".join(c["claim"] for c in claims[:3])
    return (
        claims[0]["claim"],
        "unresolved",
        f"Conflict unresolved. Competing claims: {all_claims}"
    )


def compute_confidence(
    supporting_count: int,
    conflicting_count: int,
    trust_tiers: List[str],
    has_active_conflict: bool,
) -> float:
    """Compute confidence score (0—100) for a claim.
    
    Rules:
    - 3+ high-trust sources agree → 90+
    - Mixed trust levels → 60–80
    - Active conflict → below 60
    - Single source → cap at 55
    """
    total = supporting_count + conflicting_count
    if total == 0:
        return 0

    high_count = sum(1 for t in trust_tiers if t == "high")

    # Single source cap
    if supporting_count <= 1 and conflicting_count == 0:
        base = 55 if high_count > 0 else 45
        return min(base, 55)

    # Active conflict
    if has_active_conflict:
        return max(20, 60 - (conflicting_count * 10))

    # 3+ high trust agree
    if high_count >= 3:
        return min(98, 90 + high_count)

    # Mixed trust
    if supporting_count >= 2:
        base = 60 + (supporting_count * 5) + (high_count * 8)
        return min(base, 89)

    return 50
