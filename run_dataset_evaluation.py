#!/usr/bin/env python3
"""
Adapts the Problem-11 sample dataset into the pipeline's native format,
runs it through all three layers, and scores the output against
findings_labels.csv/.json ground truth.

Usage:
    python run_dataset_evaluation.py [dataset_dir] [--json]

dataset_dir defaults to ../dataset/problem_11 relative to this repo if not
given (i.e. the sibling `dataset.zip` extraction used during development);
pass an explicit path if your dataset lives elsewhere. --json prints raw
JSON instead of the human-readable summary (useful for scripting/CI).
"""

import json
import os
import sys

root_dir = os.path.dirname(os.path.abspath(__file__))
for sub in ("policy_layer1", "policy_layer2", "policy_layer3"):
    sys.path.insert(0, os.path.join(root_dir, sub))
sys.path.insert(0, root_dir)

from dataset_integration.evaluate import run_evaluation  # noqa: E402


def _default_dataset_dir() -> str:
    # Common locations this dataset tends to get extracted to.
    candidates = [
        os.path.join(root_dir, "..", "dataset", "problem_11"),
        os.path.join(root_dir, "dataset", "problem_11"),
        os.path.join(root_dir, "problem_11"),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return os.path.abspath(c)
    return os.path.abspath(candidates[0])


def _print_summary(result: dict) -> None:
    print("=" * 70)
    print("Problem-11 Dataset Evaluation")
    print("=" * 70)

    ext = result["obligation_extraction"]
    print(f"\nObligation extraction accuracy: {ext['accuracy']:.1%} "
          f"({ext['extracted_obligations']}/{ext['expected_obligations']} bullets)")

    def _fmt(v):
        return f"{v:.1%}" if v is not None else "n/a (no ground truth pairs)"

    print(f"Conflict detection recall:      {_fmt(result['conflict_detection_recall'])}")
    print(f"Redundancy detection recall:    {_fmt(result['redundancy_detection_recall'])}")
    print(f"Staleness detection recall:     {_fmt(result['staleness_detection_recall'])}")
    print(f"False positive rate (scope-differentiated pairs): "
          f"{_fmt(result['false_positive_rate_on_scope_differentiated_pairs'])}")

    print("\nCounts:")
    for k, v in result["counts"].items():
        print(f"  {k}: {v}")

    print(f"\nTotal findings emitted: {result['findings_total']}")
    print(f"Total staleness records emitted: {result['staleness_records_total']}")
    print()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv[1:]

    dataset_dir = args[0] if args else _default_dataset_dir()
    if not os.path.isdir(dataset_dir):
        print(f"Error: dataset directory not found: {dataset_dir}", file=sys.stderr)
        sys.exit(1)

    result = run_evaluation(dataset_dir)

    if as_json:
        print(json.dumps(result, indent=2))
    else:
        _print_summary(result)


if __name__ == "__main__":
    main()
