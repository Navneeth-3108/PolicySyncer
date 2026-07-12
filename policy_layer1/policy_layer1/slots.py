"""
§5.3 Implicit/passive obligations
§5.4 Multi-clause sentence splitting (helper used by pipeline.py)
§5.5 Actor / Action / Object / Scope extraction

Regex-first extractor is the default (per Config resolution — see
config.py). A SpacySlotExtractor is provided and used automatically only if
spaCy + the configured model are importable at runtime; otherwise pipeline
falls back to RegexSlotExtractor silently.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .modals import ModalMatch
from .schema import Scope

# --------------------------------------------------------------------------
# §5.5 scope keyword tables
# --------------------------------------------------------------------------

SCOPE_KEYWORDS = {
    "role": [
        (re.compile(r"\bemployees?\b"), "employees"),
        (re.compile(r"\bdevelopers?\b"), "developers"),
        (re.compile(r"\bservice accounts?\b"), "service accounts"),
        (re.compile(r"\bcontractors?\b"), "contractors"),
        (re.compile(r"\badministrators?\b"), "administrators"),
    ],
    "system": [
        (re.compile(r"\bcloud(?:-hosted)?\b"), "cloud"),
        (re.compile(r"\bon-?prem(?:ises)?\b"), "on-prem"),
        (re.compile(r"\blegacy\b"), "legacy"),
        (re.compile(r"\bproduction\b"), "production"),
    ],
    "geography": [
        (re.compile(r"\beu\b|\beuropean union\b"), "EU"),
        (re.compile(r"\bglobal\b"), "global"),
    ],
}


def extract_scope(text: str) -> Scope:
    lowered = text.lower()
    scope = Scope()
    for dim, keywords in SCOPE_KEYWORDS.items():
        for pattern, value in keywords:
            if pattern.search(lowered):
                setattr(scope, dim, value)
                break
    return scope


# --------------------------------------------------------------------------
# Regex-based slot extractor (default / fallback)
# --------------------------------------------------------------------------

_ACTOR_BEFORE_MODAL_RE = re.compile(
    r"^(?P<actor>[A-Za-z][\w\s\-]*?)\s+(?=\b(?:must|shall|should|may|is)\b)"
)

# Words that can immediately follow a modal in a passive/adjectival
# construction but are never the obligation's action verb.
_PREPOSITION_NONVERBS = {
    "for", "to", "by", "with", "of", "from", "on", "in", "at", "as", "into",
    "under", "over", "per", "via", "about",
}


@dataclass
class SlotResult:
    actor: str
    action: str
    obj: Optional[str]
    qualifiers: List[str]
    flags: List[str]


def _extract_qualifiers(text_after_verb: str) -> List[str]:
    """Split a comma-separated qualifier list, e.g. 'uppercase, lowercase,
    numbers, and special characters' -> list of items."""
    text_after_verb = text_after_verb.strip().rstrip(".")
    if not text_after_verb:
        return []
    # normalize "and" before the last item
    text_after_verb = re.sub(r",?\s+and\s+", ", ", text_after_verb)
    parts = [p.strip() for p in text_after_verb.split(",") if p.strip()]
    return parts


class RegexSlotExtractor:
    name = "regex"

    def extract(self, clause_text: str, modal: ModalMatch) -> SlotResult:
        flags: List[str] = []

        pre_modal_text = clause_text[: modal.start].strip()
        actor_m = _ACTOR_BEFORE_MODAL_RE.match(pre_modal_text + " ")
        actor = None
        if actor_m:
            candidate = actor_m.group("actor").strip()
            if candidate:
                actor = candidate
        elif pre_modal_text:
            actor = pre_modal_text

        post_modal_text = clause_text[modal.end :].strip()

        # After the modal, capture the immediate verb (including copular
        # "be" itself as a valid action, e.g. "must be at least 12
        # characters" -> action="be", object="at least 12 characters...").
        verb_m = re.match(
            r"^(?:not\s+)?(?P<verb>[a-zA-Z]+)(?:\s+(?P<rest>.*))?$",
            post_modal_text,
        )
        action = "UNSPECIFIED"
        obj = None
        qualifiers: List[str] = []
        if verb_m:
            action = verb_m.group("verb").lower()
            rest = verb_m.group("rest") or ""
            if action in _PREPOSITION_NONVERBS:
                # Passive constructions like "Access is prohibited for all
                # users" leave a bare preposition immediately after the modal,
                # so the naive "first word = verb" rule grabs "for"/"to"/... as
                # the action. The real topic is the pre-modal subject (the
                # actor); don't emit a preposition as the action.
                if actor and actor != "UNSPECIFIED":
                    obj = actor
                action = "UNSPECIFIED"
            else:
                # naive object = first few words up to a comma/qualifier list or
                # a temporal/exception marker
                stop_re = re.compile(
                    r"\b(every|within|for|unless|except|excepting|excluding|other than|"
                    r"with the exception of)\b",
                    re.IGNORECASE,
                )
                stop_m = stop_re.search(rest)
                main_part = rest[: stop_m.start()].strip() if stop_m else rest.strip()

                if "," in main_part:
                    # e.g. "at least 12 characters with uppercase, lowercase, ..."
                    head, _, tail = main_part.partition(",")
                    obj = head.strip().rstrip(",") or None
                    qualifiers = _extract_qualifiers(tail)
                else:
                    obj = main_part.strip().rstrip(".") or None

        if actor is None or actor == "":
            actor = "UNSPECIFIED"
            flags.append("implicit_actor")

        return SlotResult(actor=actor, action=action, obj=obj, qualifiers=qualifiers, flags=flags)


# --------------------------------------------------------------------------
# Optional spaCy-based extractor (auto-detected; not a hard dependency)
# --------------------------------------------------------------------------


class SpacySlotExtractor:
    name = "spacy"

    def __init__(self, model_name: str = "en_core_web_sm"):
        import spacy  # may raise ImportError -> handled by caller

        self.nlp = spacy.load(model_name)  # may raise OSError -> handled by caller

    def extract(self, clause_text: str, modal: ModalMatch) -> SlotResult:
        flags: List[str] = []
        doc = self.nlp(clause_text)

        modal_token = None
        for tok in doc:
            if tok.idx <= modal.start < tok.idx + len(tok.text):
                modal_token = tok
                break

        if modal_token is None:
            # fall back to regex extractor entirely
            return RegexSlotExtractor().extract(clause_text, modal)

        # walk up to governing verb
        gov = modal_token.head
        subj = None
        for child in gov.children:
            if child.dep_ in ("nsubj", "nsubjpass"):
                subj = child
                break
        if subj is None and gov.dep_ in ("nsubj", "nsubjpass"):
            subj = gov

        if subj is not None:
            span = doc[subj.left_edge.i : subj.right_edge.i + 1]
            actor = span.text.strip()
        else:
            actor = "UNSPECIFIED"
            flags.append("implicit_actor")

        action = gov.lemma_.lower()

        obj = None
        qualifiers: List[str] = []
        for child in gov.children:
            if child.dep_ in ("dobj", "attr"):
                span = doc[child.left_edge.i : child.right_edge.i + 1]
                obj = span.text.strip()
                break
        if obj is None:
            for child in gov.children:
                if child.dep_ == "prep":
                    span = doc[child.left_edge.i : child.right_edge.i + 1]
                    obj = span.text.strip()
                    break

        return SlotResult(actor=actor, action=action, obj=obj, qualifiers=qualifiers, flags=flags)


def get_slot_extractor(use_spacy: bool, model_name: str):
    if use_spacy:
        try:
            return SpacySlotExtractor(model_name)
        except Exception:
            # spaCy or the model isn't available -> silent fallback per
            # Config resolution documented in config.py
            pass
    return RegexSlotExtractor()
