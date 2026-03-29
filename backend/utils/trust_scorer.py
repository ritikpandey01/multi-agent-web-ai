"""Source trust scorer — hardcoded domain trust tiers.

No ML needed. Assigns trust tier and score based on domain matching.
"""

from urllib.parse import urlparse
from typing import Tuple

# ─── Trust Tier Definitions ─────────────────────────────────────────────────

HIGH_TRUST_DOMAINS = {
    # Government
    "gov.in", "nic.in", "gov.uk", "gov.us", ".gov",
    # Regulatory / Exchanges
    "nseindia.com", "bseindia.com", "rbi.org.in", "sebi.gov.in",
    # Global wire services
    "reuters.com", "apnews.com", "bloomberg.com",
    # International orgs
    "who.int", "un.org", "worldbank.org",
}

MEDIUM_TRUST_DOMAINS = {
    # Indian national news
    "economictimes.indiatimes.com", "livemint.com", "thehindu.com",
    "ndtv.com", "hindustantimes.com", "indianexpress.com",
    # Major tech / business media
    "techcrunch.com", "wired.com", "theverge.com", "arstechnica.com",
    "forbes.com", "cnbc.com", "bbc.com", "nytimes.com",
    "washingtonpost.com", "theguardian.com",
    # Finance
    "moneycontrol.com", "investing.com", "marketwatch.com",
}

LOW_TRUST_DOMAINS = {
    "reddit.com", "quora.com", "medium.com",
    "blogspot.com", "wordpress.com", "tumblr.com",
}

# Score ranges per tier
TIER_SCORES = {
    "high": (85, 95),
    "medium": (55, 70),
    "low": (25, 40),
    "unknown": (45, 45),
}


def _extract_domain(url: str) -> str:
    """Extract the domain from a URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _match_domain(domain: str, domain_set: set) -> bool:
    """Check if a domain matches any entry in the set (supports suffix matching)."""
    for d in domain_set:
        if domain == d or domain.endswith("." + d) or domain.endswith(d):
            return True
    return False


def get_trust_info(url: str) -> Tuple[str, str, int]:
    """Return (domain, trust_tier, trust_score) for a given URL.
    
    Returns:
        Tuple of (domain_name, tier_string, numeric_score)
    """
    domain = _extract_domain(url)
    if not domain:
        return ("unknown", "unknown", 45)

    if _match_domain(domain, HIGH_TRUST_DOMAINS):
        tier = "high"
        score = 90  # midpoint of 85-95
    elif _match_domain(domain, MEDIUM_TRUST_DOMAINS):
        tier = "medium"
        score = 62  # midpoint of 55-70
    elif _match_domain(domain, LOW_TRUST_DOMAINS):
        tier = "low"
        score = 32  # midpoint of 25-40
    else:
        tier = "unknown"
        score = 45

    return (domain, tier, score)


def should_discard(trust_score: int) -> bool:
    """Sources below 25 should be discarded."""
    return trust_score < 25
