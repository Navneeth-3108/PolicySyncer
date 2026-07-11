# Layer 3: Recommendation & Reporting Engine

Consumes Layer 2's `Layer2Output` (`Finding[]` + `StalenessRecord[]`) and the
originating Layer 1 `PolicyRecord[]`, and produces the report-shaped JSON
described in the integration prompt's §4: citation resolution, prose
(`description` / `recommendation` / `scope_analysis`), `policy_health_score`,
and final schema assembly. It does not re-derive or override any Layer 2
scoring, severity, or evidence.

```python
from policy_layer1 import run_layer1
from policy_layer2 import run_layer2
from policy_layer2.config import Config as Layer2Config
from policy_layer3 import run_layer3, Layer3Config

layer1_records = run_layer1(raw_text)
layer2_output = run_layer2([r.to_dict() for r in layer1_records], config=Layer2Config())
report = run_layer3(layer2_output, layer1_records, config=Layer3Config(), layer2_config=Layer2Config())
```

## Upstream patches applied (not duplicated into Layer 3)

1. **Layer 1 (`policy_layer1/schema.py`, `pipeline.py`)**: added
   `ObligationRecord.section_ref` (e.g. `"3.1"`), populated from the section
   header the obligation's source sentence fell under. Pure extraction
   change, no new dependency.
2. **Layer 2 config (`policy_layer2/config.py`)**: `compliance_clause_table`
   re-keyed to the category vocabulary Layer 1 actually emits
   (`password_management`, `authentication`, `access_control`,
   `account_management`, `encryption`, `retention`, `network_security`,
   `other` — see `policy_layer1/category.py`). The previous seed table's
   keys (`data_protection`, `data_retention`, `policy_governance`,
   `incident_response`) never matched any `category_primary` Layer 1
   produces, so `compliance_impact` was silently always empty. Data-table
   edit only — no lookup-logic change. **Treat this table as a starting
   point**, same caveat the original seed table carried: it needs the same
   periodic human maintenance as the deprecated-tech table.
3. **Layer 2 bug fix (`policy_layer2/normalize.py`)** — found while wiring
   Layer 3 end-to-end, not requested by the original prompt, but required
   for the pipeline to produce any correct `CONFLICT` findings at all:
   Layer 1's `modal_normalized` field is *already* the four-way deontic type
   (`OBLIGATION`/`PROHIBITION`/`RECOMMENDATION`/`PERMISSION` — see
   `policy_layer1/modals.py`), not the raw modal word (`"must"`/`"should"`/
   `"may"`) Layer 2's original `_MODALITY_TABLE` assumed. Every real Layer 1
   record therefore missed every key in that table and silently fell back to
   `RECOMMENDATION`, which collapsed every `OBLIGATION`/`PROHIBITION` pair to
   the same modality and made direct-conflict detection unreachable in
   practice (see `test_conflict.py`, which — tellingly — only ever
   constructs fixtures with lowercase `"must"`/`"should"` directly, so this
   never surfaced in Layer 2's own test suite). Fixed by consuming
   `modal_normalized` directly when it's already one of the four valid
   categories, falling back to the old word-based table only for legacy/raw
   inputs. Both layers' existing test suites still pass after this change
   (43/43 Layer 1, 19/19 Layer 2).

## §5.4 prose-generation mode: **template-based**

Every `description` / `recommendation` / `scope_analysis` string is built
from a small set of per-`conflict_subtype` / per-staleness-signal string
templates filled from `Finding.evidence` / `StalenessRecord.staleness_signals`
and the cited obligations' `raw_text`. No LLM call, fully deterministic and
auditable — consistent with Layer 2's own Design Principle 4 and its
explicit note that pure-LLM-as-judge is "a legitimate hybrid... but not the
primary mechanism" (design doc §11.1).

## §5.2 `scope_analysis`: **qualitative-only**

No population/HR/asset-inventory source is wired into this implementation.
Per the integration prompt's own explicit warning ("never let an LLM call
fabricate a percentage from the text alone — a worse failure mode than
omitting it"), `scope_analysis` here **never invents a number**. It either:
- is omitted entirely when both obligations' scopes are universal/unspecified
  (nothing non-trivial to say), or
- describes qualitatively which scopes overlap (e.g. "employees who also
  fall under cloud-hosted systems"), with an explicit note that no
  population source is configured.

`Layer3Config.population_source` is a documented extension point
(`Callable[[scope_a, scope_b, scope_relation], Optional[str]]`) — wire in a
real HR/asset-inventory query there to switch to quantitative estimates.
Leaving it `None` (the default) is a deliberate safety choice, not an
oversight: it means this implementation's output will **not** reproduce the
integration prompt's own hand-authored `"estimated 80% of workforce"` figure
in its §7 worked example, because that figure was illustrative, not derived
from any wired data source, and the prompt itself flags fabricating it as
the exact failure mode to avoid.

## §6 `policy_health_score`

`severity_weight = {HIGH: 30, MEDIUM: 20, LOW: 8}` (`Layer3Config`), same
values the prompt suggests as a starting point — **not validated against
real reviewer judgments**, calibrate before treating any specific score as
meaningful (same caveat the Layer 2 design doc makes about its own
thresholds).

**Two-sided penalty (open governance choice, §6):** default is `"full"` —
a pairwise finding penalizes *both* policies by the full severity weight,
which is what the §6 pseudocode literally specifies (no split). Set
`Layer3Config(two_sided_penalty_mode="half")` for the alternative where each
side bears half the weight instead. Neither is "more correct" — this is a
governance decision the prompt explicitly asks to be stated, not defaulted
silently.

`overall` = mean of all per-policy scores, rounded.

## STALE `compliance_impact`

Layer 2's `StalenessRecord` carries no `compliance_impact` field (§0 B4
scopes that lookup to pairwise `Finding`s only). Layer 3 derives it
deterministically — a lookup, not a generative step — by unioning
`compliance_clause_table` entries across every `category_primary` actually
present among the stale policy's own obligations. Pass the same
`layer2_config=` used for the run into `run_layer3()` so this reuses the
exact table Layer 2 used, rather than risking a second, drifting copy.

## Known limitation of the bundled example run

`examples/run_example.py` — like `policy_layer2/examples/run_example.py`
itself — runs with `blocking_similarity_threshold=0.0` because no
`sentence-transformers` install is available in this environment (no
network access to install it). With that stdlib TF-IDF/heuristic fallback,
several genuinely unrelated obligation pairs score ~0.0 action similarity —
the same score the one *real* target conflict in the worked fixture also
gets — so no non-zero threshold cleanly separates signal from noise with
this fallback. The result: the bundled example's output includes several
extra low-value `CONFLICT`/`SUBSUMPTION` findings beyond the one the
fixture was designed to illustrate, and `policy_health_score` reflects that
larger finding set (this is Layer 2's Stage-A blocking behavior, which
Layer 3 must render faithfully — see the prohibition on re-deriving Layer 2's
scoring above). **Install `sentence-transformers` (and Layer 2's default,
higher `blocking_similarity_threshold`) in a networked environment for
production-quality precision.**

## Tests

`tests/_run_without_pytest.py` runs:
- `test_citations.py` — citation resolution (`obligation_id` → `"Policy
  §section"`, policy → `"Policy vX.Y"`, slug convention, unresolved-id
  fallback).
- `test_field_presence.py` — `compliance_impact` omitted iff empty,
  `scope_analysis` present only on `OVERLAP`/`SUPERSET`/`SUBSET` with
  non-trivial scope and never containing a fabricated `%`, `STALE` uses
  `policy` not `policy_a`/`policy_b`.
- `test_health_score.py` — arithmetic on synthetic cases: no findings ⇒
  perfect scores, full vs. half two-sided penalty, staleness penalizing
  only its own policy, scores floored at 0.
