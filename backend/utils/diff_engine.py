"""Diff engine — compares two reports to identify changes.

Used for Track/Monitor mode to highlight what changed between runs.
"""

from typing import List, Dict
from models.report_models import DiffItem, DiffResult, FinalReport


def diff_reports(old_report: dict, new_report: dict) -> DiffResult:
    """Compare two report dicts and return a DiffResult.
    
    Identifies:
    - added: claims in new but not in old
    - removed: claims in old but not in new
    - changed: claims present in both but with different confidence
    """
    old_claims = {c["claim"]: c for c in old_report.get("verified_claims", [])}
    new_claims = {c["claim"]: c for c in new_report.get("verified_claims", [])}

    added = []
    removed = []
    changed = []

    # Find added and changed
    for claim_text, new_claim in new_claims.items():
        if claim_text not in old_claims:
            added.append(DiffItem(
                type="added",
                claim=claim_text,
                new_confidence=new_claim.get("confidence", 0),
            ))
        else:
            old_conf = old_claims[claim_text].get("confidence", 0)
            new_conf = new_claim.get("confidence", 0)
            if abs(old_conf - new_conf) > 2:  # Only flag meaningful changes
                changed.append(DiffItem(
                    type="changed",
                    claim=claim_text,
                    old_confidence=old_conf,
                    new_confidence=new_conf,
                ))

    # Find removed
    for claim_text in old_claims:
        if claim_text not in new_claims:
            removed.append(DiffItem(
                type="removed",
                claim=claim_text,
                old_confidence=old_claims[claim_text].get("confidence", 0),
            ))

    return DiffResult(added=added, removed=removed, changed=changed)
