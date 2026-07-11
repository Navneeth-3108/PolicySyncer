"""
Example usage:
    python examples/run_example.py
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from policy_layer1 import run_layer1


def main():
    sample_path = os.path.join(os.path.dirname(__file__), "sample_input.txt")
    with open(sample_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    records = run_layer1(raw_text)

    output = [r.to_dict() for r in records]
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
