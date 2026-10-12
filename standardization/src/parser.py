# parser.py

import re
from typing import List, Optional

from .models import ParsedProcedure, ProcedureComponent
from .matching import resolve_procedure_name
from .constants import (
    CE_UPGRADES_TO_CEIOL_WITH,
    EXCLUDED_CANONICALS,
    HYPHEN_CHARS,
    TRAB360_PATTERN,
)
from .utils import (
    clean_name_text,
    detail_sort_key,
    detect_none,
    extract_date,
    extract_details,
    extract_laterality_markers,
    extract_antimetabolites,
    extract_possible,
    normalize_whitespace,
    render_date,
    separate_model_suffix,
    split_combined_components,
    split_entry_chunks,
    strip_status_prefixes,
)


# ============================================================
# Component-level parsing (a single procedure within an entry)
# ============================================================

def parse_component(text: str) -> Optional[ProcedureComponent]:
    raw = text
    working = text

    # "Trab 360" is a distinct procedure -- collapse its variants to the single token
    # "trab360" BEFORE detail extraction so the "360" is not stripped as a degree detail.
    working = TRAB360_PATTERN.sub("trab360", working)

    working, antimetabolites = extract_antimetabolites(working)
    working, details = extract_details(working)

    # Normalize Baerveldt device+size to "<device> <size>" regardless of how the size
    # is written: "bgi350"/"bgi 350"/"bgi-350" and size-first "350 bgi"/"350bgi".
    sep = rf"[\s{HYPHEN_CHARS}]*"
    working = re.sub(rf"\b(250|350){sep}(bvt|bgi|baerveldt)\b", r"\2 \1", working, flags=re.I)
    working = re.sub(rf"\b(bvt|bgi|baerveldt){sep}(250|350)\b", r"\1 \2", working, flags=re.I)

    working = clean_name_text(working)
    base, model = separate_model_suffix(working)

    if not base:
        # A bare antimetabolite (e.g. "5FU") is itself the procedure ("5FU injection").
        if antimetabolites:
            name = antimetabolites[0]
            for modifier in antimetabolites[1:]:
                name = f"{name} {modifier}"
            return ProcedureComponent(
                raw=raw,
                procedure_name=name,
                details=details,
                confidence_flag="clean",
            )
        return None

    canon, flag, note, implied_details = resolve_procedure_name(base)

    if canon:
        name = canon
    else:
        # Preserve the (cleaned) source text rather than dropping information.
        name = normalize_whitespace(base) or None

    if name is None:
        return None

    if model:
        # Device model / plate size is kept in the name with a space
        # (e.g. "BGI 350", "AGI FP7").
        name = f"{name} {model}"
    for modifier in antimetabolites:
        name = f"{name} {modifier}"

    # Synonym variants may imply subtype details (e.g. "tube trim" -> trimming).
    for detail in implied_details:
        if detail not in details:
            details.append(detail)
    details = sorted(details, key=detail_sort_key)

    return ProcedureComponent(
        raw=raw,
        procedure_name=name,
        details=details,
        confidence_flag=flag,
        correction_notes=note,
    )


# Confidence flags ordered from least to most severe. Used when merging two
# components that describe the same cataract surgery.
_FLAG_SEVERITY = {"clean": 0, "corrected": 1, "ambiguous": 2, "unmapped": 3}


def _collapse_cataract_components(
    components: List[ProcedureComponent],
) -> List[ProcedureComponent]:
    """
    CE and CEIOL in the same combined entry are one cataract surgery.

    "cataract extraction" maps to CE and "phaco" maps to CEIOL, so an explicit
    combined-procedure separator ("GATT with cataract extraction with Phaco")
    would otherwise keep both. Prefer CEIOL whenever an IOL is named (phaco /
    CEIOL) or implied (see CE_UPGRADES_TO_CEIOL_WITH), then drop the redundant
    CEIOL copy.
    """
    names = {c.procedure_name for c in components}
    if "CEIOL" in names or names & CE_UPGRADES_TO_CEIOL_WITH:
        for c in components:
            if c.procedure_name == "CE":
                c.procedure_name = "CEIOL"

    ceiols = [c for c in components if c.procedure_name == "CEIOL"]
    if len(ceiols) <= 1:
        return components

    kept = ceiols[0]
    for extra in ceiols[1:]:
        for detail in extra.details:
            if detail not in kept.details:
                kept.details.append(detail)
        if _FLAG_SEVERITY.get(extra.confidence_flag, 0) > _FLAG_SEVERITY.get(
            kept.confidence_flag, 0
        ):
            kept.confidence_flag = extra.confidence_flag
        if extra.correction_notes:
            if kept.correction_notes:
                kept.correction_notes = (
                    f"{kept.correction_notes}; {extra.correction_notes}"
                )
            else:
                kept.correction_notes = extra.correction_notes
    kept.details = sorted(kept.details, key=detail_sort_key)

    others = [c for c in components if c.procedure_name != "CEIOL"]
    return others + [kept]


# ============================================================
# Entry-level parsing (a comma-delimited procedure entry for one eye)
# ============================================================

def parse_single_entry(chunk: str, label_type: str) -> ParsedProcedure:
    raw_chunk = chunk

    text = strip_status_prefixes(chunk)
    text, possible = extract_possible(text)
    text, laterality_unknown = extract_laterality_markers(text)
    text, date, date_uncertain = extract_date(text)

    # A future procedure has not happened yet, so a date in the text is when it is
    # planned for rather than part of the label: the future rules format a proposed
    # procedure as "[procedure] ([detail])" with no date. The date is still parsed out
    # above so that it cannot be mistaken for a procedural detail.
    if label_type == "future":
        date = None
        date_uncertain = False

    if not text or detect_none(text):
        return ParsedProcedure(
            raw_chunk=raw_chunk,
            label_type=label_type,
            components=[],
            special="None",
        )

    component_texts = split_combined_components(text)

    components: List[ProcedureComponent] = []
    # Details that lived on a dropped fragment ("with patch graft in the sulcus",
    # "with sulcus") still belong to the surviving procedure in this entry.
    orphan_details: List[str] = []
    for ct in component_texts:
        comp = parse_component(ct)
        if not comp or not comp.procedure_name:
            _, details = extract_details(ct)
            for detail in details:
                if detail not in orphan_details:
                    orphan_details.append(detail)
            continue
        # R1-excluded procedures (e.g. AC paracentesis, patch graft) are recognized so
        # they can be dropped cleanly rather than left as flagged unmapped text.
        if comp.procedure_name in EXCLUDED_CANONICALS:
            for detail in comp.details:
                if detail not in orphan_details:
                    orphan_details.append(detail)
            continue
        components.append(comp)

    if orphan_details and components:
        target = components[-1]
        for detail in orphan_details:
            if detail not in target.details:
                target.details.append(detail)
        target.details = sorted(target.details, key=detail_sort_key)

    if not components:
        return ParsedProcedure(
            raw_chunk=raw_chunk,
            label_type=label_type,
            components=[],
            special="None",
        )

    components = _collapse_cataract_components(components)

    # Combined (same-day) procedures are always rendered in a fixed alphabetical order
    # so that, e.g., "phaco + goniotomy" and "goniotomy + phaco" standardize identically.
    components.sort(key=lambda c: (c.procedure_name or "").lower())

    flags = [c.confidence_flag for c in components]
    if any(f in {"ambiguous", "unmapped"} for f in flags):
        worst = "ambiguous"
    elif any(f == "corrected" for f in flags):
        worst = "corrected"
    else:
        worst = "clean"

    return ParsedProcedure(
        raw_chunk=raw_chunk,
        label_type=label_type,
        components=components,
        date=date,
        date_uncertain=date_uncertain,
        possible=possible,
        laterality_unknown=laterality_unknown,
        confidence_flag=worst,
    )


def parse_procedure_label(label: str, label_type: str) -> List[ParsedProcedure]:
    chunks = split_entry_chunks(label)
    return [parse_single_entry(c, label_type) for c in chunks]


# ============================================================
# Ordering: chronological, then alphabetical
# ============================================================

def _date_sort_tuple(date: Optional[str]):
    """
    Convert a normalized date string into a comparable (year, month, day) tuple.

    Returns None when no year can be resolved (e.g. ambiguous "M/D"), so the entry is
    ordered after all dated procedures.
    """
    if not date:
        return None

    m = re.fullmatch(r"(\d{4})s", date)         # decade, e.g. "1990s"
    if m:
        return (int(m.group(1)), 0, 0)
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", date)
    if m:
        return (int(m.group(3)), int(m.group(1)), int(m.group(2)))
    m = re.fullmatch(r"(\d{1,2})/(\d{4})", date)
    if m:
        return (int(m.group(2)), int(m.group(1)), 0)
    m = re.fullmatch(r"(\d{4})", date)
    if m:
        return (int(m.group(1)), 0, 0)
    return None


def _alpha_key(entry: ParsedProcedure) -> str:
    """Alphabetical tie-breaker: the procedure body, ignoring the 'possible' prefix."""
    return "/".join(
        render_component(c) for c in entry.components if c.procedure_name
    ).lower()


def sort_entries(entries: List[ParsedProcedure]) -> List[ParsedProcedure]:
    """
    Order procedures chronologically, then alphabetically (R-ORDER).

    Dated procedures come first in ascending date order; undated procedures follow,
    sorted alphabetically. Ties among dated procedures are broken alphabetically.
    """
    def key(entry: ParsedProcedure):
        dt = _date_sort_tuple(entry.date)
        alpha = _alpha_key(entry)
        if dt is None:
            return (1, 9999, 99, 99, alpha)
        return (0, dt[0], dt[1], dt[2], alpha)

    return sorted(entries, key=key)


# ============================================================
# Rendering
# ============================================================

def render_component(comp: ProcedureComponent) -> str:
    if not comp.procedure_name:
        return ""
    if comp.details:
        return f"{comp.procedure_name} ({', '.join(comp.details)})"
    return comp.procedure_name


def render_entry(entry: ParsedProcedure) -> str:
    if entry.special == "None" or not entry.components:
        return "None"

    body = "/".join(render_component(c) for c in entry.components if c.procedure_name)
    if not body:
        return "None"

    if entry.possible:
        body = f"possible {body}"

    date_str = render_date(entry.date, entry.date_uncertain)
    if date_str:
        body = f"{body} {date_str}"

    if entry.laterality_unknown:
        body = f"{body} (laterality unknown)"

    return body
