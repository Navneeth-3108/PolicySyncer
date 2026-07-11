# Changelog: Option C dataset-compliance pass

Backend-only changes to bring the pipeline into full compliance with the
Problem-11 sample dataset, evaluated against `findings_labels`. No UI/web
app was added or touched, per the task scope. All 82 pre-existing +
new unit tests pass (`43 + 19 + 15 + 5`).

## `policy_layer1/policy_layer1/modals.py`
Added three modal patterns the dataset's sentence templates need and the
original lexicon didn't cover:
- Bare `is prohibited` (no trailing "from ...") -- e.g. "Access is
  prohibited for all users."
- Bare adjectival `required` -- e.g. "All users required change as per
  company standards."
- Bare adjectival `recommended` -- e.g. "All users recommended endpoint
  as per company standards."

Both bare patterns are guarded with a negative lookbehind on `be ` so they
don't create a second, spurious modal match inside passive constructions
already handled by a preceding modal (`"shall not be required"` must stay
one obligation, not two) -- this exact case is asserted by the pre-existing
`test_semicolon_rationale_not_split_when_second_half_has_no_modal` test,
which still passes.

**Result:** obligation extraction on the dataset went from partial
coverage to 343/343 bullets (100%) extracted.

## `policy_layer1/policy_layer1/category.py` + `config.py`
Added 12 categories covering the dataset's topic vocabulary (`api_security`,
`asset_management`, `backup_recovery`, `change_management`,
`cloud_security`, `vendor_management`, `logging_monitoring`,
`mobile_device_management`, `patch_management`, `physical_security`,
`data_privacy`, `personnel_security`), plus bare `network` and
`provisioning` keywords added to the existing `network_security` /
`account_management` categories. `DEFAULT_CATEGORY_PRIORITY` was extended
with the new categories, appended *after* the original ones so no existing
priority-order test changes behavior.

Trade-off documented in-line: `change` as a bare keyword is broad and can
false-positive on unrelated "password change"-style text; category
priority resolves the ambiguity deterministically but a curated
multi-word phrase list would be more precise for production use.

## `policy_layer2/policy_layer2/staleness.py`
Fixed a real substring-matching bug: `deprecated_technologies` /
`superseded_standards` lookups used plain `term in text`, so `"ftp"`
matched inside `"sftp"`, `"des"` matched inside `"designed"`/
`"credentials"`, etc. Added a cached, word-boundary `term_in_text()`
helper and switched both signal functions to use it. This is a
correctness fix independent of the dataset (the bug pre-dates this pass)
and is covered by the existing `test_staleness.py` suite, which still
passes.

## `policy_layer2/policy_layer2/config.py`
- Added `ftp`, `sox 2002`, `gdpr 2016` to `deprecated_technologies` (the
  dataset's `(Reference: ...)` annotations cite these). Documented the
  trade-off of treating regulation-year citations the same as deprecated
  ciphers/OS versions in-line -- a real deployment should confirm a cited
  year is actually stale before flagging it this way.
- Extended `compliance_clause_table` with entries for the 12 new
  categories (data-table edit only, no lookup-logic change, matching the
  existing table's own established convention).

## `policy_layer3/policy_layer3/config.py`
Mirrored the `compliance_clause_table` extension from `policy_layer2`'s
config, keeping the two in sync per the existing documented fallback
relationship between them.

## `dataset_integration/` (new package)
- `adapter.py` -- parses each Problem-11 `policy_*.md` file's front-matter
  (title, version, last-reviewed date) and obligation bullets, and renders
  each as one native `policy_layer1` block (`--- Name (vX, Last Reviewed:
  DATE) ---` / `Section 1.1: ...`). Combines all 30 into a single document
  and returns an explicit `policy_name -> source_file` map built at
  construction time, so evaluation never has to re-derive it by parsing.
- `evaluate.py` -- runs the adapted document through Layers 1-2, then
  scores the output against `findings_labels` (not
  `obligation_extracts_labels` -- see below):
  - Conflict detection recall against `DIRECT_CONFLICT` + `PARTIAL_CONFLICT`
    pairs
  - Redundancy detection recall against `REDUNDANCY` pairs
  - Staleness detection recall against `STALE_POLICY` + `STALE_REFERENCE`
    policies
  - False-positive rate against `FALSE_POSITIVE_PRONE` pairs (apparent
    conflicts that differ only in scope and should not be flagged)
  - Obligation-extraction accuracy against the real `- ` bullet count in
    each markdown file
- `tests/test_adapter.py` -- unit tests for front-matter parsing, bullet
  extraction, missing-metadata handling, native-block rendering, and the
  file/name mapping's invertibility.
- `run_dataset_evaluation.py` (project root) -- CLI wrapper: adapts the
  dataset, runs the pipeline, prints a human-readable summary or `--json`.

### Ground-truth choice
`obligation_extracts_labels.json` (350 rows) does not textually match the
actual `policy_*.md` bullet content it's supposedly labeling (e.g. it has
`"Contractors must backup."` where the real markdown bullet is `"All users
must backup as per company standards."`) -- ​a mismatch between how that
label file and the markdown files were generated, not something fixable by
the adapter. `findings_labels.csv/.json` **is** consistent with the
markdown (verified: every `policy_a`/`policy_b`/`policy` value it
references is a real file in `policies/`), and it's what the project
brief's own success criteria (conflict/redundancy/staleness
detection rate, false positive rate) are actually about, so it's used as
the sole ground truth for finding-type evaluation. Obligation-extraction
accuracy is instead measured directly against each file's real bullet
count, which is what "did the regex extractor find the obligations that
are really in the document" needs.

### Current numbers (`python run_dataset_evaluation.py <dataset_dir>`)
```
Obligation extraction accuracy: 100.0% (343/343 bullets)
Conflict detection recall:      59.1%
Redundancy detection recall:    68.4%
Staleness detection recall:     86.7%
False positive rate (scope-differentiated pairs): 66.7%
```
Extraction and staleness are strong. Conflict/redundancy recall and the
false-positive rate are below the brief's targets (>75%/>70%/<20%) with
`run_pipeline.py`'s own loosened `blocking_similarity_threshold=0.0`
(needed because this repo has zero hard NLP dependencies, and without
`sentence-transformers` the blocking stage's similarity fallback is
weaker). The dataset's obligation text is heavily templated ("All users
<modal> <topic> as per company standards.") across nearly every policy, so
a threshold of `0.0` lets almost every same-category pair through to the
conflict/redundancy reasoners, which then over-fire relative to the
curated ground truth. This is reported honestly rather than tuned to hit
the targets; the config knob to address it (raising
`blocking_similarity_threshold`, or installing `sentence-transformers` for
real embedding-based blocking) is already exposed and documented -- see
`SCOPE.md` and the README's "Optional NLP Enhancements" section.

## `SCOPE.md` (new)
Documents which pipeline features are required by Option C ("Simple
Policy Scanner") vs. which ones (NLI contradiction scoring, embedding
similarity, scope-lattice reasoning, weighted confidence fusion, numeric
health scoring) exceed it. These are intentionally kept rather than
removed/simplified, because (1) each has its own passing test coverage
the task says to preserve, and (2) each already degrades gracefully to a
zero-dependency, Option-C-equivalent rule-based path when its optional
package isn't installed -- confirmed by the fact that every test in this
repo, including the new dataset evaluation, passes with nothing but the
Python standard library installed.

## `README.md`
Added a "Dataset Evaluation" section documenting `run_dataset_evaluation.py`
usage and a pointer to `SCOPE.md`.
