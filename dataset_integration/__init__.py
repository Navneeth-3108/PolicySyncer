"""
dataset_integration -- adapts the Problem-11 sample dataset (30 markdown
policy files + CSV/JSON metadata + ground-truth labels) into the pipeline's
native input format, and evaluates the full 3-layer pipeline against the
dataset's findings_labels ground truth.

This package is NOT part of the pipeline itself (policy_layer1/2/3) -- it's
a thin, separate adapter layer, per the project's existing "each layer is
independently swappable" philosophy. It does not modify the pipeline's
architecture, only feeds it input in the format it already expects.

Public API:
    adapter.build_dataset_document(dataset_dir) -> (native_text, name_to_file)
    adapter.load_policy_metadata(dataset_dir) -> dict[file] -> metadata dict
    evaluate.run_evaluation(dataset_dir) -> dict of precision/recall/F1 metrics
"""

from .adapter import build_dataset_document, load_policy_metadata

__all__ = ["build_dataset_document", "load_policy_metadata"]
