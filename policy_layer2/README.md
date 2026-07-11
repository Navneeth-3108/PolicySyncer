# Layer 2: Semantic Conflict, Redundancy, Scope & Staleness Reasoning

Implements the Layer 2 pipeline of the Policy Conflict & Staleness Detector,
per the design document: normalization & enrichment → candidate pair
generation & blocking → conflict / redundancy-subsumption / scope-overlap /
staleness reasoners → fusion, confidence propagation & severity scoring
(§2–§9). Consumes the Layer 1 → Layer 2 `ObligationRecord[]` contract and
emits a `Finding[]` + `StalenessRecord[]` array (§6). No `recommendation`
text and no `policy_health_score` are produced here — those are Layer 3 /
aggregation concerns (§0, B1–B2).

## Project structure

```
policy_layer2/
  policy_layer2/
    __init__.py         Public API: run_layer2()
    config.py            Thresholds, weights, reference tables (§8, §9, §7 tunables)
    schema.py             Finding / StalenessRecord output dataclasses (§6)
    normalize.py           §2.1, §3.2  deontic proposition construction
    similarity.py            §3.2, §4.2  sentence-embedding similarity (SBERT / fallback)
    nli.py                     §3.3 Stage B  contradiction scoring (NLI / heuristic fallback)
    temporal.py                 §3.4  Allen interval algebra + trigger-mismatch detection
    scope.py                     §5  scope lattice & overlap reasoner (shared module)
    blocking.py                    §2.2, §3.3 Stage A  candidate pair generation
    conflict.py                     §3  five-way conflict typology reasoner
    redundancy.py                     §4  redundancy / subsumption reasoner
    staleness.py                        §7  weighted staleness signal combination
    compliance.py                         §0 B4  category -> framework-clause lookup
    confidence.py                          §8  two-stage confidence propagation
    severity.py                             §9  dual-axis (confidence x impact) severity
    pipeline.py                              §2.3  run_layer2() orchestration
  tests/                 19 tests covering scope lattice, Allen relations,
                          confidence fusion, all 4 emitted conflict subtypes
                          + 1 suppression case, and staleness signal combination
  examples/
    sample_layer1_output.json   6 policies covering every worked scenario
                                 in the design doc (paraphrase rotation vs
                                 refresh, VPN/CI-CD exception, 7yr-retention
                                 vs delete-on-request, stale TLS 1.0 reference)
    run_example.py
  requirements.txt
```

## Design-doc traceability

Every module's docstring cites the design-document section(s) it implements
(§ numbers refer to the Layer 2 design document). The four boundary
decisions in §0 (B1–B4) are honored exactly:

- **B1** — no `recommendation` field anywhere in `schema.py`.
- **B2** — no `policy_health_score` computed; `Finding.severity`/`confidence`
  are the inputs a downstream aggregator would use.
- **B3** — `scope.py` emits only the qualitative `EQUAL/SUPERSET/SUBSET/
  OVERLAP/DISJOINT` relation, never a headcount estimate; the workforce-
  percentage figure from the worked example is explicitly out of scope
  (see `scope.scope_breadth_rank`'s docstring).
- **B4** — `compliance.py` is a deterministic table lookup keyed on Layer 1's
  `category_primary`, not a generative classification.

## Zero-hard-dependency policy (mirrors Layer 1)

Like Layer 1, the core pipeline runs with **nothing installed beyond the
standard library**:

- `similarity.py` defaults to a stdlib TF-IDF cosine-similarity fallback and
  auto-upgrades to `sentence-transformers` (SBERT, Reimers & Gurevych 2019)
  if importable.
- `nli.py` defaults to a heuristic contradiction scorer (deontic-opposition +
  negation-cue asymmetry) and auto-upgrades to a `transformers` NLI
  checkpoint if importable.

**This fallback boundary is a real, documented limitation, not a cosmetic
one.** The stdlib fallback has near-zero token overlap on true paraphrases
like "rotate passwords" vs. "refresh credentials on a periodic basis" — the
exact case the design doc calls out as SBERT's reason for existing (§3.2).
`examples/run_example.py` demonstrates this directly: it has to loosen
`blocking_similarity_threshold` to `0.0` for the fallback backend to let that
pair through Stage A at all. **Before trusting recall in production, install
`sentence-transformers` (and ideally a real NLI checkpoint)** — see
`requirements.txt`. Everything downstream of blocking/NLI (scope lattice,
Allen-interval temporal reasoning, confidence fusion, severity thresholding)
is fully deterministic and unaffected by this choice.

## Install & run

```bash
cd policy_layer2
python examples/run_example.py     # prints Layer 2 JSON for the sample corpus
```

Optional upgrades:

```bash
pip install sentence-transformers   # real SBERT embeddings
pip install transformers torch      # real NLI contradiction model
```

## Tests

```bash
python -m pytest tests/             # if pytest is available
python tests/_run_without_pytest.py # stdlib-only fallback (no install needed)
```

19/19 tests pass against the stdlib fallback backends. Coverage: scope
lattice relations (universal-null handling, disjoint-forces-overall-disjoint,
role-lattice superset/subset, explicit incomparability), Allen temporal
relations + duration-vs-deadline trigger mismatch, confidence propagation
(min-gate not product, linear fusion doesn't collapse, hard cap by extraction
confidence), all conflict-typology branches actually reachable from the
`evaluate_conflict` entry point (DIRECT, PARTIAL_OVERLAP, disjoint-scope
suppression, exception-mediated suppression), and staleness signal
combination (deprecated-tech fires independent of review recency; age alone
fires; a clean policy emits nothing).

## Known limitations / deviations, stated explicitly rather than hidden

- **Embedding/NLI fallback recall**, as above — the single biggest quality
  lever available without any new code, since swapping in real models
  requires no changes to `conflict.py`, `redundancy.py`, or `staleness.py`.
- **`scope.py`'s lattice is hand-authored** for the `role` dimension only
  (`Config.role_lattice_edges`); `system` and `geography` currently default
  to flat equality/disjoint comparison. Building out lattices for those
  dimensions (e.g. `cloud` ⊐ `AWS`, `AWS` ⊐ `us-east-1`) is a direct,
  low-risk extension using the same `ScopeLattice._close()` transitive-
  closure machinery already in place — flagged here as the most valuable
  next increment, not implemented speculatively.
- **`_classify_subtype` in `conflict.py` is a rule table, not a learned
  classifier** — consistent with Design Principle 4 in the design doc
  (symbolic structure constrains/interprets statistical signals, not the
  reverse), but it means subtype boundaries (e.g. exactly when a scope-nested
  pair is `PARTIAL_OVERLAP` vs. plain `DIRECT`) are as good as the rules
  encoded and should be validated against the gold-annotated evaluation set
  described in the design doc's §10 before the default thresholds in
  `config.py` are treated as anything but provisional — the design doc says
  this explicitly about its own thresholds (§9, §11.2) and that caveat
  carries over unchanged to this implementation.
- **Compliance-clause table (`config.py`) is a small illustrative seed**,
  not a maintained authoritative mapping — it needs the same "periodic human
  maintenance" the design doc requires for the deprecated-tech and
  superseded-standard tables (§7.1).
- **No precedence resolution** (§11.2) — a `TEMPORAL_TRIGGER_MISMATCH` or
  irreducible `DIRECT` conflict is surfaced with both obligations' evidence;
  nothing in this codebase decides which one wins. That is intentionally out
  of scope here, same as in the design doc.

## Interface to Layer 3

`run_layer2()` returns a `Layer2Output` (`findings: List[Finding]`,
`staleness: List[StalenessRecord]`). Each `Finding.to_dict()` / 
`StalenessRecord.to_dict()` is the exact JSON contract Layer 3 (recommendation
generation) and any policy-health aggregation step should consume — every
field needed to compute a health score or generate remediation prose
(`severity`, `confidence`, `compliance_impact`, `obligation_refs`, full
`evidence`) is present; nothing generative or headcount-derived is included,
per §0.
