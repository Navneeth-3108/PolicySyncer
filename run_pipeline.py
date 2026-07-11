#!/usr/bin/env python3
"""
End-to-end Policy Conflict Detector - runs all three layers sequentially.

Usage:
    python run_pipeline.py [input_file]

If no input file is provided, uses policy_layer1/examples/sample_input.txt
"""

import json
import os
import sys
from pathlib import Path

# Add all layer directories to path
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir / "policy_layer1"))
sys.path.insert(0, str(root_dir / "policy_layer2"))
sys.path.insert(0, str(root_dir / "policy_layer3"))

from policy_layer1 import run_layer1
from policy_layer2 import run_layer2
from policy_layer2.config import Config as Layer2Config
from policy_layer3 import run_layer3, Layer3Config


def main():
    # Determine input file
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = str(root_dir / "policy_layer1" / "examples" / "sample_input.txt")

    if not os.path.exists(input_file):
        print(f"Error: Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    print("=" * 70)
    print("Policy Conflict & Staleness Detector - Full Pipeline")
    print("=" * 70)
    print()

    # Read input
    with open(input_file, "r", encoding="utf-8") as f:
        raw_text = f.read()

    print(f"Input file: {input_file}")
    print(f"Input size: {len(raw_text)} characters")
    print()

    # ========== LAYER 1: Obligation Extraction ==========
    print("-" * 70)
    print("LAYER 1: Rule-Based Obligation Extraction")
    print("-" * 70)
    try:
        layer1_records = run_layer1(raw_text)
        print(f"✓ Extracted {len(layer1_records)} obligation records")
        print()

        # Save Layer 1 output
        layer1_output_file = "layer1_output.json"
        layer1_dicts = [r.to_dict() for r in layer1_records]
        with open(layer1_output_file, "w") as f:
            json.dump(layer1_dicts, f, indent=2)
        print(f"✓ Layer 1 output saved to: {layer1_output_file}")
        print()

    except Exception as e:
        print(f"✗ Layer 1 failed: {e}", file=sys.stderr)
        sys.exit(1)

    # ========== LAYER 2: Conflict & Staleness Analysis ==========
    print("-" * 70)
    print("LAYER 2: Semantic Conflict, Redundancy, Scope & Staleness Reasoning")
    print("-" * 70)
    try:
        # Use loosened threshold if no advanced NLP models are available
        layer2_config = Layer2Config(blocking_similarity_threshold=0.0)
        layer2_output = run_layer2(layer1_dicts, config=layer2_config)

        print(f"✓ Found {len(layer2_output.findings)} findings")
        print(f"✓ Found {len(layer2_output.staleness)} staleness records")
        print()

        # Save Layer 2 output
        layer2_output_file = "layer2_output.json"
        with open(layer2_output_file, "w") as f:
            json.dump(layer2_output.to_dict(), f, indent=2)
        print(f"✓ Layer 2 output saved to: {layer2_output_file}")
        print()

    except Exception as e:
        print(f"✗ Layer 2 failed: {e}", file=sys.stderr)
        sys.exit(1)

    # ========== LAYER 3: Recommendations & Reporting ==========
    print("-" * 70)
    print("LAYER 3: Recommendation & Reporting Engine")
    print("-" * 70)
    try:
        layer3_config = Layer3Config()
        report = run_layer3(
            layer2_output,
            layer1_records,
            config=layer3_config,
            layer2_config=layer2_config,
        )

        print(f"✓ Generated final report")
        print()

        # Save final report
        report_file = "final_report.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)
        print(f"✓ Final report saved to: {report_file}")
        print()

    except Exception as e:
        print(f"✗ Layer 3 failed: {e}", file=sys.stderr)
        sys.exit(1)

    # ========== Summary ==========
    print("=" * 70)
    print("✓ PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 70)
    print()
    print("Output files:")
    print(f"  1. {layer1_output_file} - Layer 1 obligation records")
    print(f"  2. {layer2_output_file} - Layer 2 findings & staleness analysis")
    print(f"  3. {report_file} - Final report with recommendations")
    print()


if __name__ == "__main__":
    main()
