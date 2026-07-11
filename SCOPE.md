# Scope note: this implementation vs. Option C

The project brief offers three approaches of increasing complexity:

- **Option A** (LLM-powered, embeddings, knowledge graph, dashboard) -- 30-40h, complexity 4/5
- **Option B** (rule-based NLP + NetworkX graph analysis, basic web UI) -- 20-30h, complexity 3/5
- **Option C** (regex extraction, manual category keywords, simple conflict/staleness rules, HTML/PDF report) -- 15-20h, complexity 2/5

This codebase's *required* surface area matches Option C:

| Option C requirement | Where it lives |
|---|---|
| Extract "must/shall/required" sentences via regex | `policy_layer1/modals.py` (`_MODAL_LEXICON`) |
| Group obligations by manually defined categories/keywords | `policy_layer1/category.py` (`CATEGORY_KEYWORDS`) |
| Flag same-category, opposing-keyword obligations as conflicts | `policy_layer2/conflict.py` |
| Staleness check against an 18-month threshold | `policy_layer2/staleness.py` (`_review_age_signal`) |
| Policy health report | `policy_layer3` (`health_score.py`, `prose.py`) -- emitted as **JSON**, not HTML/PDF or a dashboard (see below) |

No web app was built and none should be added per the task instructions --
input is a text/markdown document (or, via `dataset_integration/`, the
sample dataset), output is JSON written to disk by `run_pipeline.py` /
`run_dataset_evaluation.py`. There is no Flask/FastAPI server, no HTML/PDF
report generator, and no dashboard anywhere in this repo.

## Where the implementation exceeds Option C

Several parts of the pipeline go beyond "simple conflict detection" and
"18-month threshold" into Option B/A territory:

- **`policy_layer2/nli.py`** -- an optional NLI (natural-language
  inference) contradiction-scoring engine, used both for conflict
  confirmation and for the staleness "semantic drift vs. current
  guidance" signal (§7.1's 5th staleness signal, which Option C's brief
  does not ask for at all -- Option C only asks for the review-age and
  deprecated-reference checks).
- **`policy_layer2/similarity.py`** -- optional sentence-transformer
  embedding similarity for candidate-pair blocking, closer to Option B's
  "semantic embeddings" than Option C's manual keyword matching.
- **`policy_layer2/scope.py`** -- a role/system/geography scope lattice
  with partial-order reasoning (subset/superset/incomparable), well beyond
  Option C's flat category match.
- **`policy_layer2/confidence.py` / `severity.py`** -- a weighted,
  multi-signal confidence-fusion model, rather than Option C's simple
  traffic-light flag.
- **`policy_layer3/health_score.py`** -- a numeric policy health score
  with configurable severity weights and a two-sided-penalty policy
  choice, beyond Option C's "traffic-light indicators."

**These are not being removed or simplified**, for two reasons the task
also asks to weigh:

1. **"Preserve the existing architecture and tests."** All of the above
   have their own passing unit tests (`policy_layer2/tests/test_confidence.py`,
   `test_scope.py`, `test_staleness.py`, `policy_layer3/tests/test_health_score.py`,
   etc.) that assert on this exact behavior. Deleting the functionality
   would break passing tests the task says to keep.
2. **They already degrade gracefully to an Option-C-equivalent core.**
   Every advanced piece is opt-in and falls back to a pure rule-based path
   with zero extra dependencies when the optional package isn't installed
   (see README's "Optional NLP Enhancements" section and
   `install_dependencies.sh`): no `sentence-transformers` -> a lexical
   similarity fallback; no `transformers`/`torch` -> a rule-based
   contradiction heuristic in `nli.py`; no `spacy` -> the regex slot
   extractor in `slots.py`. The mandatory dependency set is exactly
   Option C's ("Python (Flask/FastAPI), regex, HTML/CSS, basic NLP
   concepts" minus the never-built web UI) plus `pytest` for the test
   suite -- `python run_pipeline.py` and `python run_dataset_evaluation.py`
   both run correctly with nothing but the standard library installed.

In short: the mandatory Option C feature set is fully implemented and is
what runs by default; the additional signals are optional accuracy
upgrades that a from-scratch Option C build would not include, kept here
because removing them would regress test coverage without being asked to,
and because they cost nothing when unavailable.
