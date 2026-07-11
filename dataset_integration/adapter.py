"""
Converts the Problem-11 sample dataset's markdown policy files into the
policy_layer1 pipeline's native document format:

    --- <Policy Name> (v<version>, Last Reviewed: <YYYY-MM-DD>) ---
    Section 1.1: <obligation sentence> <obligation sentence> ...

See policy_layer1/policy_layer1/parsing.py for the exact header/section
grammar this has to match.

Design notes:
  - Each dataset policy file becomes exactly one policy block with a single
    synthetic "Section 1.1" containing every bullet line from the markdown
    (joined with spaces) -- the dataset has no real section structure to
    preserve, and Layer 1's sentence/clause segmentation only needs a
    section body to operate on.
  - The policy name used in the native header is the markdown title
    (`# <Title>`) exactly, taken from the metadata table when available.
    Titles happen to be unique across all 30 sample policies, but this
    module does not rely on that: build_dataset_document() returns an
    explicit name -> source-file mapping built at construction time
    (not recovered later by re-parsing), so evaluation never has to guess.
  - `status` (active/retired/draft) and `author`/`department` from the
    metadata table are not consumed anywhere in policy_layer1/2/3 today
    (grep confirms no `status` handling in the pipeline), so the adapter
    reads them for completeness but does not thread them into the native
    document -- that would require a pipeline schema change, which is out
    of scope here.
"""

import csv
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

_MD_TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_MD_VERSION_RE = re.compile(r"^\*\*Version:\*\*\s*v?([\d.]+)\s*$", re.MULTILINE)
_MD_REVIEWED_RE = re.compile(r"^\*\*Last Reviewed:\*\*\s*(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)
_MD_STATUS_RE = re.compile(r"^\*\*Status:\*\*\s*(.+?)\s*$", re.MULTILINE)
_MD_BULLET_RE = re.compile(r"^-\s+(.+?)\s*$", re.MULTILINE)


def load_policy_metadata(dataset_dir: str) -> Dict[str, Dict[str, Any]]:
    """
    Load policy_metadata.csv (falling back to .json) from the dataset
    directory. Returns {file: {title, author, department, version,
    last_reviewed, status}}. This is informational only -- parse_policy_md()
    below is self-contained and extracts everything it needs directly from
    each markdown file's own front-matter, so a missing/absent metadata
    table does not block conversion.
    """
    csv_path = os.path.join(dataset_dir, "policy_metadata.csv")
    json_path = os.path.join(dataset_dir, "policy_metadata.json")

    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    elif os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            rows = json.load(f)
    else:
        return {}

    return {row["file"]: row for row in rows}


def parse_policy_md(md_text: str, source_file: str) -> Dict[str, Any]:
    """
    Parse a single Problem-11 policy markdown file's front-matter and
    obligation bullets. Returns:
        {
          "title": str,
          "version": Optional[str]  (without leading "v"),
          "last_reviewed": Optional[str],
          "status": Optional[str],
          "bullets": List[str],   # each bullet's raw obligation sentence
        }
    Missing fields are flagged via None rather than guessed -- callers can
    decide how to represent that in the native header (policy_layer1's own
    tolerant-parsing fallback already handles a missing version/date by
    setting metadata_incomplete/staleness_undetermined flags).
    """
    title_m = _MD_TITLE_RE.search(md_text)
    version_m = _MD_VERSION_RE.search(md_text)
    reviewed_m = _MD_REVIEWED_RE.search(md_text)
    status_m = _MD_STATUS_RE.search(md_text)

    title = title_m.group(1).strip() if title_m else source_file
    version = version_m.group(1).strip() if version_m else None
    last_reviewed = reviewed_m.group(1).strip() if reviewed_m else None
    status = status_m.group(1).strip() if status_m else None

    bullets = [b.strip() for b in _MD_BULLET_RE.findall(md_text) if b.strip()]

    return {
        "title": title,
        "version": version,
        "last_reviewed": last_reviewed,
        "status": status,
        "bullets": bullets,
    }


def _native_block(parsed: Dict[str, Any]) -> str:
    """Render one parsed policy dict as a native policy_layer1 block.

    Never fabricates a version or last-reviewed date: if either is missing
    from the source, it's simply omitted from the header. policy_layer1's
    tolerant fallback header parser then sets metadata_incomplete /
    staleness_undetermined flags for the missing piece rather than the
    pipeline ever seeing a fake "v1.0" or "1970-01-01".
    """
    version = parsed["version"]
    last_reviewed = parsed["last_reviewed"]

    meta_parts = []
    if version:
        meta_parts.append(f"v{version}")
    if last_reviewed:
        meta_parts.append(f"Last Reviewed: {last_reviewed}")

    if meta_parts:
        header = f"--- {parsed['title']} ({', '.join(meta_parts)}) ---"
    else:
        header = f"--- {parsed['title']} ---"

    body = " ".join(parsed["bullets"])
    section = f"Section 1.1: {body}"
    return f"{header}\n{section}"


def build_dataset_document(
    dataset_dir: str, policies_subdir: str = "policies"
) -> Tuple[str, Dict[str, str]]:
    """
    Reads every policy_*.md file in dataset_dir/policies_subdir, converts
    each to a native policy_layer1 block, and concatenates them into one
    combined document (parse_policy_blocks() in policy_layer1 splits
    multi-policy documents on the '--- ... ---' header lines, so this is a
    single run_layer1() call away from full Layer 1 output).

    Returns (combined_native_text, name_to_file) where name_to_file maps
    the exact policy_name string used in each native header back to the
    original source filename (e.g. "policy_05.md") -- this is what lets
    evaluate.py match Layer 1/2/3 output (which only knows policy_name)
    back to findings_labels.csv (which references files).
    """
    policies_dir = os.path.join(dataset_dir, policies_subdir)
    files = sorted(f for f in os.listdir(policies_dir) if f.endswith(".md"))

    blocks: List[str] = []
    name_to_file: Dict[str, str] = {}

    for fname in files:
        path = os.path.join(policies_dir, fname)
        with open(path, "r", encoding="utf-8") as fh:
            md_text = fh.read()
        parsed = parse_policy_md(md_text, fname)
        blocks.append(_native_block(parsed))
        name_to_file[parsed["title"]] = fname

    combined_text = "\n".join(blocks) + "\n"
    return combined_text, name_to_file


def file_to_name_map(name_to_file: Dict[str, str]) -> Dict[str, str]:
    """Convenience inverse of the mapping build_dataset_document() returns."""
    return {fname: name for name, fname in name_to_file.items()}
