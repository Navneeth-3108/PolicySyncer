import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from policy_layer2 import run_layer2, Config


def main():
    path = os.path.join(os.path.dirname(__file__), "sample_layer1_output.json")
    with open(path) as f:
        policy_records = json.load(f)

    # NOTE: with no sentence-transformers/transformers installed, similarity.py
    # and nli.py fall back to a weak stdlib TF-IDF/heuristic backend (see their
    # module docstrings). That fallback under-scores true paraphrases like
    # "rotate passwords" vs "refresh credentials" (near-zero token overlap),
    # so Stage-A blocking is loosened here purely to make this demo legible
    # without installing anything. In production, install sentence-transformers
    # (and ideally a real NLI checkpoint for nli.py) and use Config()'s default,
    # higher, precision-appropriate threshold instead.
    demo_config = Config(blocking_similarity_threshold=0.0)
    output = run_layer2(policy_records, config=demo_config)
    print(json.dumps(output.to_dict(), indent=2))

    print(f"\n{len(output.findings)} finding(s), {len(output.staleness)} staleness record(s)", file=sys.stderr)


if __name__ == "__main__":
    main()
