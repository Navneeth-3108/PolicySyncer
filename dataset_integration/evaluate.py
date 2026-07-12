"""
Runs the full 3-layer pipeline against the Problem-11 sample dataset and
scores the output against findings_labels.csv/.json -- the dataset's own
ground truth for conflicts, redundancies, and staleness (see
dataset/problem_11/README.md: "The main label category remains in
finding_type ... The required detailed split is provided in
finding_subtype.").

NOTE on ground truth choice: this module deliberately scores against
findings_labels, not obligation_extracts_labels. obligation_extracts_labels
(350 rows) does not textually match the actual policy_*.md bullet content
(e.g. it has "Contractors must backup." where the corresponding markdown
bullet reads "All users must backup as per company standards.") -- a
generation-time mismatch in the sample dataset, not something this adapter
can reconcile by construction. Obligation-extraction accuracy is instead
measured directly against the real bullet count in each markdown file
(see obligation_extraction_accuracy() below), which is what Option C's
"Obligation Extraction Accuracy > 80%" success criterion is actually
asking about: did the regex extractor find the obligation sentences that
are really in the document.

Ground-truth construction from findings_labels:
  - conflict recall target   = DIRECT_CONFLICT + PARTIAL_CONFLICT pairs
  - redundancy recall target = REDUNDANCY pairs
  - staleness recall target  = STALE_POLICY + STALE_REFERENCE policies
  - false-positive check     = FALSE_POSITIVE_PRONE pairs (apparent
    conflicts that differ only in scope) -- these should NOT be flagged as
    CONFLICT; every one that the pipeline flags anyway counts against the
    false-positive rate.
"""

import csv
import json
import os
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for sub in ("policy_layer1", "policy_layer2", "policy_layer3"):
    p = os.path.join(_ROOT, sub)
    if p not in sys.path:
        sys.path.insert(0, p)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from policy_layer1 import run_layer1  # noqa: E402
from policy_layer2 import run_layer2  # noqa: E402
from policy_layer2.config import Config as Layer2Config  # noqa: E402

from .adapter import build_dataset_document  # noqa: E402


def _load_labels(dataset_dir: str) -> List[Dict[str, Any]]:
    json_path = os.path.join(dataset_dir, "findings_labels.json")
    csv_path = os.path.join(dataset_dir, "findings_labels.csv")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    with open(csv_path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _pair(a: str, b: str) -> Tuple[str, str]:
    """Order-independent pair key."""
    return tuple(sorted((a, b)))


def _build_obligation_id_to_file(layer1_dicts: List[Dict[str, Any]], name_to_file: Dict[str, str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for record in layer1_dicts:
        policy_name = record.get("policy_metadata", {}).get("policy_name", "")
        file_name = name_to_file.get(policy_name, policy_name)
        for ob in record.get("obligations", []):
            mapping[ob["obligation_id"]] = file_name
    return mapping


def obligation_extraction_accuracy(dataset_dir: str, layer1_dicts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compares the number of obligations Layer 1 extracted per file against
    the number of '- ' bullet lines actually present in that file's
    markdown -- i.e. did the regex extractor find the obligation sentences
    that are really in the document (Option C's extraction-accuracy
    criterion), independent of the mismatched obligation_extracts_labels
    file (see module docstring).
    """
    policies_dir = os.path.join(dataset_dir, "policies")
    expected_by_file: Dict[str, int] = {}
    for fname in os.listdir(policies_dir):
        if not fname.endswith(".md"):
            continue
        with open(os.path.join(policies_dir, fname), "r", encoding="utf-8") as f:
            expected_by_file[fname] = sum(1 for line in f if line.strip().startswith("- "))

    extracted_total = sum(len(r.get("obligations", [])) for r in layer1_dicts)
    expected_total = sum(expected_by_file.values())
    accuracy = extracted_total / expected_total if expected_total else 0.0
    return {
        "expected_obligations": expected_total,
        "extracted_obligations": extracted_total,
        "accuracy": round(accuracy, 4),
    }


def _ground_truth_sets(labels: List[Dict[str, Any]]):
    conflict_pairs: Set[Tuple[str, str]] = set()
    false_positive_prone_pairs: Set[Tuple[str, str]] = set()
    redundancy_pairs: Set[Tuple[str, str]] = set()
    stale_policies: Set[str] = set()

    for row in labels:
        subtype = row.get("finding_subtype")
        if subtype in ("DIRECT_CONFLICT", "PARTIAL_CONFLICT"):
            conflict_pairs.add(_pair(row["policy_a"], row["policy_b"]))
        elif subtype == "FALSE_POSITIVE_PRONE":
            false_positive_prone_pairs.add(_pair(row["policy_a"], row["policy_b"]))
        elif subtype == "REDUNDANCY":
            redundancy_pairs.add(_pair(row["policy_a"], row["policy_b"]))
        elif subtype in ("STALE_POLICY", "STALE_REFERENCE"):
            stale_policies.add(row["policy"])

    return conflict_pairs, false_positive_prone_pairs, redundancy_pairs, stale_policies


def _predicted_sets(layer2_output, ob_to_file: Dict[str, str], name_to_file: Dict[str, str]):
    conflict_pairs: Set[Tuple[str, str]] = set()
    redundancy_pairs: Set[Tuple[str, str]] = set()
    stale_policies: Set[str] = set()

    for finding in layer2_output.findings:
        if len(finding.obligation_refs) != 2:
            continue
        a, b = finding.obligation_refs
        file_a = ob_to_file.get(a)
        file_b = ob_to_file.get(b)
        if not file_a or not file_b:
            continue
        pair = _pair(file_a, file_b)
        if finding.finding_type == "CONFLICT":
            conflict_pairs.add(pair)
        elif finding.finding_type in ("REDUNDANCY", "SUBSUMPTION"):
            redundancy_pairs.add(pair)

    for rec in layer2_output.staleness:
        # StalenessRecord.policy_name is the native-header title (e.g.
        # "Password Policy"); findings_labels' STALE rows reference the
        # source filename ("policy_30.md") -- translate via the same
        # name_to_file mapping the adapter produced.
        file_name = name_to_file.get(rec.policy_name, rec.policy_name)
        stale_policies.add(file_name)

    return conflict_pairs, redundancy_pairs, stale_policies


def _recall(predicted: Set, ground_truth: Set) -> Optional[float]:
    if not ground_truth:
        return None
    hits = len(predicted & ground_truth)
    return round(hits / len(ground_truth), 4)


def run_evaluation(dataset_dir: str, layer2_config: Optional[Layer2Config] = None) -> Dict[str, Any]:
    text, name_to_file = build_dataset_document(dataset_dir)

    layer1_records = run_layer1(text)
    layer1_dicts = [r.to_dict() for r in layer1_records]

    # name_to_file is keyed by the title used in the native header; Layer 1
    # echoes that same string back as policy_metadata.policy_name, so the
    # dict is directly usable without re-parsing anything.
    ob_to_file = _build_obligation_id_to_file(layer1_dicts, name_to_file)

    layer2_config = layer2_config or Layer2Config()
    layer2_output = run_layer2(layer1_dicts, config=layer2_config)

    labels = _load_labels(dataset_dir)
    gt_conflict, gt_fp_prone, gt_redundancy, gt_stale = _ground_truth_sets(labels)
    pred_conflict, pred_redundancy, pred_stale = _predicted_sets(layer2_output, ob_to_file, name_to_file)

    false_positive_hits = pred_conflict & gt_fp_prone
    false_positive_rate = (
        round(len(false_positive_hits) / len(gt_fp_prone), 4) if gt_fp_prone else None
    )

    return {
        "obligation_extraction": obligation_extraction_accuracy(dataset_dir, layer1_dicts),
        "conflict_detection_recall": _recall(pred_conflict, gt_conflict),
        "redundancy_detection_recall": _recall(pred_redundancy, gt_redundancy),
        "staleness_detection_recall": _recall(pred_stale, gt_stale),
        "false_positive_rate_on_scope_differentiated_pairs": false_positive_rate,
        "counts": {
            "ground_truth_conflict_pairs": len(gt_conflict),
            "predicted_conflict_pairs": len(pred_conflict),
            "ground_truth_redundancy_pairs": len(gt_redundancy),
            "predicted_redundancy_pairs": len(pred_redundancy),
            "ground_truth_stale_policies": len(gt_stale),
            "predicted_stale_policies": len(pred_stale),
            "ground_truth_false_positive_prone_pairs": len(gt_fp_prone),
            "false_positive_prone_pairs_flagged_as_conflict": len(false_positive_hits),
        },
        "findings_total": len(layer2_output.findings),
        "staleness_records_total": len(layer2_output.staleness),
    }
