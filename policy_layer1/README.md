# Layer 1: Rule-Based Obligation Extraction

Implements the Layer 1 pipeline of the Policy Conflict & Staleness Detector,
per the spec: preprocessing → policy/section parsing → clause segmentation →
modal detection & negation resolution → slot extraction → temporal/exception
extraction → category classification → confidence scoring → `ObligationRecord`
assembly (§1–§8, §11).

## Project structure

```
policy_layer1/
  policy_layer1/
    __init__.py        Public API: run_layer1()
    config.py           Config (open-item resolutions live here)
    schema.py            Output dataclasses matching spec §8
    preprocessing.py    §2  whitespace/unicode normalization, line-joining
    parsing.py           §3  policy block header + section parsing
    clauses.py           §2.5, §4  sentence + clause (semicolon) segmentation
    modals.py             §5.1, §5.2, §10  modal lexicon, split negation, definitional stoplist
    slots.py               §5.3, §5.4 helper, §5.5  actor/action/object/scope
    temporal.py           §5.6  temporal constraint extraction
    exceptions.py         §5.7  exception clause extraction
    category.py           §6  keyword-based category classification
    confidence.py         §7  confidence scoring
    edge_cases.py          §10  cross-references, definitional statements, contradictory modals
    pipeline.py            §11  run_layer1() orchestration
  tests/                 regression suite (43 tests, one per disambiguation rule / edge case)
  examples/
    sample_input.txt     reconstruction of the §9 worked example
    run_example.py       usage example
  requirements.txt
```

## Resolved open items (spec §12)

These were explicitly left to the implementer; resolutions are recorded in
code comments at the point of decision (`config.py`, `slots.py`) as well as
here:

1. **Category priority ordering** — made configurable via
   `Config.category_priority` (a `List[str]`), defaulting to the spec's own
   §6 order. Pass a custom list to `run_layer1(text, config=Config(category_priority=[...]))`.

2. **spaCy dependency** — the base pipeline has **zero hard third-party
   dependencies** (pure stdlib regex). `slots.py` exposes both a
   `RegexSlotExtractor` (default) and a `SpacySlotExtractor`. If
   `Config.use_spacy_if_available=True` (the default) *and* `spacy` plus the
   configured model are importable at runtime, spaCy is used for
   actor/action/object extraction, per the spec's "hybrid regex + shallow
   dependency parsing" recommendation (§5.5). Otherwise it silently falls
   back to regex — nothing breaks if spaCy isn't installed.

3. **Low-confidence blocking** — Layer 1 never blocks. Every obligation,
   including `LOW` tier, is emitted with `confidence_tier` set.
   Auto-process vs. human-review gating is treated as a Layer 2/dashboard
   policy decision, consistent with the spec's own framing of Layer 1's job
   as "produce the structured obligation records."

## Known limitation (flagged by the spec itself)

§5.5 states plainly that "regex-only extraction is fragile" for actor/
action/object slots and recommends dependency parsing as the primary
method, with regex as a fast fallback. The bundled `RegexSlotExtractor`
handles the patterns demonstrated in the spec's examples correctly (see
`examples/run_example.py` output, which reproduces the §9 worked table),
but will misparse some syntactic constructions a real parser would not
(e.g. multi-word verb phrases with intervening adverbs). Installing spaCy
+ `en_core_web_sm` and leaving `use_spacy_if_available=True` upgrades slot
extraction automatically with no code changes.

## Install & run

```bash
cd policy_layer1
pip install -r requirements.txt   # pytest only; core pipeline needs nothing
python examples/run_example.py    # prints Layer 1 JSON for the sample policy
```

Optional spaCy upgrade:

```bash
pip install spacy
python -m spacy download en_core_web_sm
```

## Tests

```bash
pytest tests/
```

(If `pytest` can't be installed in your environment, `tests/_run_without_pytest.py`
runs the same `test_*` functions with only the standard library.)

The suite (43 cases) covers every disambiguation rule called out in the
spec: modal ordering (§5.1), split negation (§5.2), implicit actor (§5.3),
multi-clause splitting incl. shared-subject anaphora (§5.4), qualifier
lists, temporal extraction incl. the bare-count-vs-unit distinction (§5.6),
exception/scope-override extraction (§5.7), category ambiguity + priority
config (§6), confidence scoring tiers and floor (§7), and the §10 edge
cases: cross-references, definitional `shall`, contradictory modals in one
clause, and numbered sub-lists.

## Usage

```python
from policy_layer1 import run_layer1, Config

with open("my_policies.txt") as f:
    raw_text = f.read()

records = run_layer1(raw_text)          # default config
# or: records = run_layer1(raw_text, config=Config(category_priority=[...]))

for policy in records:
    print(policy.policy_metadata.policy_name, policy.policy_metadata.version)
    for obligation in policy.obligations:
        print(" ", obligation.to_dict())
```

`run_layer1()` returns `list[PolicyRecord]`; call `.to_dict()` on any
record for the exact JSON shape specified in §8 (this is the Layer 1 →
Layer 2 contract — Layer 2's conflict/staleness findings and
`policy_health_score` are explicitly out of scope here, per Assumption A0
in the original spec).

## Deviations / notes on faithfulness to spec

- §5.4's pseudocode ("split the clause at each new modal occurrence... keeping
  any leading shared subject if the second clause has none") is
  implemented via a bounded backward search for the nearest conjunction
  (`and`/`or`/`,`) before each 2nd+ modal, rather than a full dependency
  parse — this is a regex-appropriate reading of that instruction and is
  covered by `test_multi_clause_sentence_produces_two_records`.
- §10's numbered/lettered sub-list handling assumes `(a)`, `(b)`, `1)`, `2)`
  style markers; a bare `a.`/`1.` style (without parens) is not currently
  matched — flagged here rather than silently mishandled, since the spec's
  own example used the parenthesized style.
- All extraction flags, penalties, and confidence tiers use exactly the
  names and values from §7's table.
