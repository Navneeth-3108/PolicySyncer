"""
§11 Implementation Guidance — run_layer1() ties every stage together and
produces the §8 output schema.
"""

import re
from typing import List, Optional, Tuple

from .config import Config
from .preprocessing import preprocess
from .parsing import parse_policy_blocks, PolicyBlock, SectionBlock
from .clauses import segment_clauses, Clause
from .modals import detect_modals, ModalMatch
from .slots import get_slot_extractor, extract_scope, SlotResult
from .temporal import extract_temporal
from .exceptions import extract_exception, strip_exception_clause
from .category import classify_category
from .confidence import score_confidence, tier_for
from .edge_cases import find_cross_reference, find_definitional_statement, has_contradictory_modal
from .schema import (
    PolicyRecord,
    PolicyMetadata,
    ObligationRecord,
)

def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    return slug


_CONJ_RE = re.compile(r"\b(?:and|or)\b\s*,?\s*|,\s*")

# "(Reference: ...)" citations are metadata, not obligation content. They must
# stay in raw_text (Layer 2 staleness scans it for deprecated-tech/superseded-
# standard references), but they must NOT reach slot extraction or category
# classification -- otherwise e.g. "(Reference: TLS 1.0)" on a network rule
# makes it classify as `encryption`, and the citation tokens leak into the
# object slot.
_CITATION_RE = re.compile(r"\s*\(\s*reference\s*:[^)]*\)", re.IGNORECASE)


def _strip_citations(text: str) -> str:
    return _CITATION_RE.sub("", text).strip()


def _split_multi_clause(
    clause_text: str, modal_matches: List[ModalMatch]
) -> List[Tuple[str, ModalMatch, bool]]:
    """
    §5.4 — one sub-clause per independent modal+verb pair. Returns a list of
    (sub_text, local_modal_match, shared_subject_inferred) tuples, where
    local_modal_match has offsets relative to sub_text.

    For the 2nd+ modal, the sub-clause boundary is placed at the nearest
    conjunction ("and"/"or"/",") immediately preceding that modal (searched
    within a short lookback window), not at the end of the previous modal's
    own clause — otherwise the previous clause's trailing object/qualifier
    text ends up misread as this clause's actor. If nothing but the
    conjunction sits between the boundary and the modal, the subject is
    anaphoric (§5.4 "shared_subject_inferred").
    """
    out = []
    n = len(modal_matches)
    prev_end = 0

    for i, mm in enumerate(modal_matches):
        seg_end = modal_matches[i + 1].start if i + 1 < n else len(clause_text)
        shared_subject = False

        if i == 0:
            seg_start = 0
        else:
            lookback_start = max(prev_end, mm.start - 60)
            region = clause_text[lookback_start:mm.start]
            conj_matches = list(_CONJ_RE.finditer(region))
            if conj_matches:
                last = conj_matches[-1]
                seg_start = lookback_start + last.end()
            else:
                seg_start = prev_end
            if clause_text[seg_start : mm.start].strip() == "":
                shared_subject = True

        sub_text = clause_text[seg_start:seg_end]
        local_modal = ModalMatch(
            raw=mm.raw,
            normalized=mm.normalized,
            strength=mm.strength,
            polarity=mm.polarity,
            start=mm.start - seg_start,
            end=mm.end - seg_start,
            split_negation=mm.split_negation,
        )
        out.append((sub_text, local_modal, shared_subject))
        prev_end = mm.end

    return out


def _build_obligation(
    policy_slug: str,
    version: Optional[str],
    section: SectionBlock,
    clause: Clause,
    sub_text: str,
    modal: ModalMatch,
    shared_subject: bool,
    prev_actor: Optional[str],
    slot_extractor,
    config: Config,
    seq: int,
    contradictory: bool,
) -> ObligationRecord:
    flags: List[str] = list(section.flags)  # e.g. nonstandard_section_format
    if modal.split_negation:
        flags.append("split_negation_detected")
    if shared_subject:
        flags.append("shared_subject_inferred")
    if contradictory:
        flags.append("contradictory_modal_in_clause")

    # exception clause (§5.7) — extracted from the sub-clause, then stripped
    # before slot extraction so it doesn't pollute actor/object. Citations
    # (§ "(Reference: ...)") are stripped for the same reason, but only from
    # the slot/category/temporal input -- raw_text (clause.text) keeps them.
    exception = extract_exception(sub_text)
    slot_input_text = strip_exception_clause(sub_text) if exception else sub_text
    slot_input_text = _strip_citations(slot_input_text)

    slots: SlotResult = slot_extractor.extract(slot_input_text, modal)
    flags.extend(slots.flags)

    actor = slots.actor
    if shared_subject and prev_actor:
        actor = prev_actor
        # shared-subject inference resolves the actor; don't also penalize
        # as implicit_actor if it was only "empty because shared".
        if "implicit_actor" in flags and actor != "UNSPECIFIED":
            flags.remove("implicit_actor")

    scope = extract_scope(clause.text)

    temporal, temporal_flags = extract_temporal(slot_input_text)
    flags.extend(temporal_flags)

    category_primary, category_secondary, cat_flags = classify_category(
        slot_input_text, config.category_priority
    )
    flags.extend(cat_flags)

    if contradictory:
        confidence = config.confidence_floor
    else:
        confidence = score_confidence(flags, config)
    tier = "LOW" if contradictory else tier_for(confidence, config)

    section_suffix = f"_{clause.list_id_suffix}" if clause.is_list_item else ""
    obligation_id = f"{policy_slug}_v{version or 'NA'}_{section.section_id}{section_suffix}_{seq:03d}"

    return ObligationRecord(
        obligation_id=obligation_id,
        source_section=section.section_id,
        section_ref=section.section_id,
        raw_text=clause.text,
        modal_raw=modal.raw,
        modal_normalized=modal.normalized,
        modal_strength=modal.strength,
        polarity=modal.polarity,
        actor=actor,
        action=slots.action,
        object=slots.obj,
        qualifiers=slots.qualifiers,
        scope=scope,
        temporal_constraint=temporal,
        exception=exception,
        rationale_text=None,
        category_primary=category_primary,
        category_secondary=category_secondary,
        confidence=confidence,
        confidence_tier=tier,
        extraction_flags=flags,
    )


def _process_section(
    policy_slug: str, version: Optional[str], section: SectionBlock, config: Config, slot_extractor
) -> Tuple[List[ObligationRecord], List[dict], List[dict]]:
    obligations: List[ObligationRecord] = []
    cross_refs: List[dict] = []
    definitional: List[dict] = []

    clauses = segment_clauses(section.body)
    seq = 1
    prev_actor: Optional[str] = None

    for clause in clauses:
        cross_ref = find_cross_reference(clause.text)
        if cross_ref:
            cross_ref["source_section"] = section.section_id
            cross_refs.append(cross_ref)
            continue

        definitional_stmt = find_definitional_statement(clause.text)
        if definitional_stmt:
            definitional_stmt["source_section"] = section.section_id
            definitional.append(definitional_stmt)
            continue

        working_text = clause.text
        rationale_text = None

        # §4 — semicolon rationale attachment: if ';' present and only one
        # side has a modal, the non-modal side is rationale, not a new
        # obligation.
        if ";" in working_text:
            head, _, tail = working_text.partition(";")
            head, tail = head.strip(), tail.strip()
            if head and tail and detect_modals(head) and not detect_modals(tail):
                working_text = head
                rationale_text = tail

        contradictory = has_contradictory_modal(working_text)
        modal_matches = detect_modals(working_text)
        if not modal_matches:
            continue

        sub_clauses = _split_multi_clause(working_text, modal_matches)

        for sub_text, local_modal, shared_subject in sub_clauses:
            record = _build_obligation(
                policy_slug=policy_slug,
                version=version,
                section=section,
                clause=clause,
                sub_text=sub_text,
                modal=local_modal,
                shared_subject=shared_subject,
                prev_actor=prev_actor,
                slot_extractor=slot_extractor,
                config=config,
                seq=seq,
                contradictory=contradictory,
            )
            prev_actor = record.actor
            obligations.append(record)
            seq += 1

        if rationale_text and obligations:
            # attach rationale to the first record produced from this clause
            first_new = obligations[-len(sub_clauses)]
            first_new.rationale_text = rationale_text

    return obligations, cross_refs, definitional


def run_layer1(raw_text: str, config: Optional[Config] = None) -> List[PolicyRecord]:
    config = config or Config()
    text = preprocess(raw_text)
    blocks: List[PolicyBlock] = parse_policy_blocks(text)

    slot_extractor = get_slot_extractor(config.use_spacy_if_available, config.spacy_model_name)

    results: List[PolicyRecord] = []
    for block in blocks:
        policy_slug = _slugify(block.name)
        obligations: List[ObligationRecord] = []
        cross_refs: List[dict] = []
        definitional: List[dict] = []

        for section in block.sections:
            sec_obligations, sec_cross_refs, sec_definitional = _process_section(
                policy_slug, block.version, section, config, slot_extractor
            )
            obligations.extend(sec_obligations)
            cross_refs.extend(sec_cross_refs)
            definitional.extend(sec_definitional)

        metadata = PolicyMetadata(
            policy_name=block.name,
            version=block.version,
            last_reviewed=block.last_reviewed,
            metadata_flags=block.metadata_flags,
        )
        results.append(
            PolicyRecord(
                policy_metadata=metadata,
                obligations=obligations,
                cross_references=cross_refs,
                definitional_statements=definitional,
            )
        )

    return results
