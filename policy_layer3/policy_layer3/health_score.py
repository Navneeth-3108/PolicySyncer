"""
§6 policy_health_score -- deterministic weighted rollup. Arithmetic only;
never delegated to an LLM call.
"""

from typing import Any, Dict, List

from .citations import CitationIndex


def compute_health_scores(
    findings: List[Any],
    staleness: List[Any],
    citation_index: CitationIndex,
    config,
) -> Dict[str, int]:
    weight = config.severity_weight
    penalty: Dict[str, float] = {info.slug: 0.0 for info in citation_index.policies.values()}

    for finding in findings:
        w = weight.get(finding.severity, 0.0)
        policy_names = {
            citation_index.obligations[ref].policy_name
            for ref in finding.obligation_refs
            if ref in citation_index.obligations
        }
        if config.two_sided_penalty_mode == "half" and len(policy_names) > 1:
            w = w / len(policy_names)
        for name in policy_names:
            slug = citation_index.slug_for(name)
            penalty[slug] = penalty.get(slug, 0.0) + w

    for record in staleness:
        slug = citation_index.slug_for(record.policy_name)
        penalty[slug] = penalty.get(slug, 0.0) + weight.get(record.severity, 0.0)

    # Penalty maps 1:1 into a 0-100 deduction (capped so the score floors at 0,
    # not below). The previous formula multiplied the capped penalty by 0.7,
    # which made the deduction top out at 70 -- so no policy could ever score
    # below 30% and the entire 0-29 "CRITICAL" band was unreachable no matter
    # how many HIGH conflicts a policy had. With HIGH=30/MEDIUM=20/LOW=8, a
    # single HIGH now yields 70 (Warning), two HIGH -> 40 (Critical).
    scores: Dict[str, int] = {
        slug: max(0, round(100 - min(p, 100))) for slug, p in penalty.items()
    }
    overall = round(sum(scores.values()) / len(scores)) if scores else 100
    scores["overall"] = overall
    return scores
