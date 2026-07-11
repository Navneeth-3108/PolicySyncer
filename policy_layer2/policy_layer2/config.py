"""
Config: every tunable named in the design doc lives here so thresholds/weights
can be swapped without touching detection logic (Design Principle: scoring
policy is a governance decision, §0 B2 / §9).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class Config:
    # ---- §3.5 / §3.3 Stage A blocking ----
    blocking_similarity_threshold: float = 0.45     # low bar, recall-favoring
    action_similarity_high_threshold: float = 0.80  # §4.1 near-paraphrase bar

    # ---- §3.3 Stage B semantic confirmation ----
    nli_contradiction_confirm_threshold: float = 0.55
    nli_neutral_band: Tuple[float, float] = (0.35, 0.55)

    # ---- §8.2 reasoning-confidence linear-combination weights ----
    # symbolic/rule-derived signals dominate statistical ones (Design Principle 4)
    reasoning_weights: Dict[str, float] = field(default_factory=lambda: {
        "modality_certainty": 0.35,
        "scope_certainty": 0.30,
        "nli_score": 0.20,
        "embedding_similarity": 0.15,
    })

    # ---- §8.2 extraction-confidence gate ----
    extraction_confidence_floor: float = 0.50   # mirrors Layer 1 LOW tier

    # ---- §9 severity thresholds ----
    severity_high_confidence: float = 0.75
    severity_medium_confidence: float = 0.50
    severity_min_emission_confidence: float = 0.30  # mirrors Layer 1 floor

    # ---- §7.1 staleness ----
    staleness_age_months_threshold: int = 18
    staleness_signal_weights: Dict[str, float] = field(default_factory=lambda: {
        "review_age": 0.30,
        "deprecated_tech": 0.30,
        "superseded_standard": 0.25,
        "semantic_drift": 0.10,
        "missing_metadata": 0.05,
    })

    # ---- §7.1 maintained reference tables (external, curated; not learned) ----
    # NOTE: "wep" was already covered below. The Problem-11 sample dataset's
    # `(Reference: ...)` annotations also cite "SOX 2002", "GDPR 2016", and
    # "FTP" -- added here even though SOX/GDPR are regulations, not
    # technologies, because this field structurally functions as a flat
    # "staleness indicator" list (§7.1's "references to deprecated
    # technologies OR superseded regulations/standards" collapses both into
    # one signal in this implementation). Treat the regulation entries as a
    # placeholder: a real deployment should confirm year-stamped regulation
    # citations like "GDPR 2016" or "SOX 2002" actually indicate an outdated
    # citation (regulations are sometimes correctly cited by enactment year)
    # before flagging them the same way as a retired cipher or OS version.
    deprecated_technologies: List[str] = field(default_factory=lambda: [
        "tls 1.0", "tls 1.1", "sha-1", "sha1", "md5", "des", "3des",
        "windows server 2012", "windows server 2008", "ssl 3.0", "ssl 2.0",
        "rc4", "wep", "ftp", "sox 2002", "gdpr 2016",
    ])
    superseded_standards: Dict[str, str] = field(default_factory=lambda: {
        # cited-standard token (lowercased substring match) -> note
        "nist sp 800-53 rev 4": "superseded by NIST SP 800-53 Rev 5",
        "nist sp 800-53 rev. 4": "superseded by NIST SP 800-53 Rev 5",
    })
    # current-guidance reference statements used for the semantic-drift signal
    # (§7.1 "semantic drift vs current guidance") -- small curated corpus,
    # keyed by category, one canonical current-guidance sentence per entry.
    current_guidance_corpus: Dict[str, List[str]] = field(default_factory=lambda: {
        "access_control": [
            "Verifiers should not require memorized secrets to be changed "
            "arbitrarily, such as on a periodic basis, absent evidence of "
            "compromise of the authenticator.",
        ],
    })

    # ---- §0 B4 compliance-clause lookup (deterministic, auditable) ----
    # NOTE (§2.2 of the Layer 3 integration prompt): re-keyed to match the
    # category_primary vocabulary Layer 1 actually emits (see
    # policy_layer1/category.py CATEGORY_KEYWORDS: password_management,
    # authentication, encryption, retention, access_control,
    # account_management, network_security, other) and to the citation
    # granularity ("ISO 27001 A.5.1", "NIST IA-5" style) this org uses. The
    # previous seed table's keys (data_protection, data_retention,
    # policy_governance, incident_response) never matched any
    # category_primary Layer 1 produces and so never fired -- this is a
    # data-table edit only, no lookup-logic change. As with the deprecated-
    # tech table, this needs the same periodic human maintenance -- treat it
    # as a starting point, not a finished mapping.
    compliance_clause_table: Dict[str, List[str]] = field(default_factory=lambda: {
        "password_management": ["ISO 27001 A.5.1", "NIST IA-5"],
        "authentication": ["NIST IA-5"],
        "access_control": ["ISO 27001 A.9.4"],
        "account_management": ["ISO 27001 A.9.4"],
        "encryption": ["ISO 27001 A.8.24", "NIST SC-13"],
        "retention": ["GDPR Art. 5(1)(e)"],
        "network_security": ["ISO 27001 A.8.20"],
        # ---- Problem-11 dataset-driven categories (see category.py) ----
        "api_security": ["ISO 27001 A.8.26"],
        "asset_management": ["ISO 27001 A.5.9"],
        "backup_recovery": ["ISO 27001 A.8.13"],
        "change_management": ["ISO 27001 A.8.32"],
        "cloud_security": ["ISO 27001 A.5.23"],
        "vendor_management": ["ISO 27001 A.5.19"],
        "logging_monitoring": ["ISO 27001 A.8.15", "NIST AU-2"],
        "mobile_device_management": ["ISO 27001 A.8.1"],
        "patch_management": ["ISO 27001 A.8.8"],
        "physical_security": ["ISO 27001 A.7.1"],
        "data_privacy": ["GDPR Art. 5"],
        "personnel_security": ["ISO 27001 A.6.1"],
        "other": [],
    })

    # ---- §5.1 scope lattice: per-dimension partial order ----
    # value -> set of values it is a superset of (direct edges; transitive
    # closure computed at load time by scope.ScopeLattice)
    role_lattice_edges: Dict[str, List[str]] = field(default_factory=lambda: {
        "all employees": ["contractors", "developers", "employees", "staff"],
        "employees": ["developers"],
    })
    # dimensions considered "incomparable" (neither subset nor superset) even
    # though textually related -- must be listed explicitly, per §5.1
    role_incomparable_pairs: List[Tuple[str, str]] = field(default_factory=lambda: [
        ("all employees", "service accounts"),
        ("employees", "service accounts"),
    ])

    use_sentence_transformers_if_available: bool = True
    embedding_model_name: str = "all-MiniLM-L6-v2"
