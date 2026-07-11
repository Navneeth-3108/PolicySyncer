"""
End-to-end example: raw policy text -> Layer 1 -> Layer 2 -> Layer 3.

    python examples/run_example.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "policy_layer1"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "policy_layer2"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from policy_layer1 import run_layer1
from policy_layer2 import run_layer2
from policy_layer2.config import Config as Layer2Config
from policy_layer3 import run_layer3, Layer3Config


def main():
    sample_path = os.path.join(os.path.dirname(__file__), "sample_input.txt")
    with open(sample_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    layer1_records = run_layer1(raw_text)
    layer1_dicts = [r.to_dict() for r in layer1_records]

    # NOTE: see this package's README -- without sentence-transformers
    # installed, Layer 2's Stage-A blocking needs a loosened threshold to
    # surface any candidate pairs at all with the stdlib fallback similarity
    # engine. This mirrors policy_layer2/examples/run_example.py's own demo
    # config, not a Layer 3 change.
    layer2_config = Layer2Config(blocking_similarity_threshold=0.0)
    layer2_output = run_layer2(layer1_dicts, config=layer2_config)

    layer3_config = Layer3Config()
    report = run_layer3(
        layer2_output,
        layer1_records,
        config=layer3_config,
        layer2_config=layer2_config,
    )

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
