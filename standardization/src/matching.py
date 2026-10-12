# matching.py

import re
from typing import List, Optional, Tuple

from rapidfuzz.distance import DamerauLevenshtein

from .constants import (
    PROCEDURE_IMPLIED_DETAILS,
    PROCEDURE_SYNONYMS,
    TRABECULECTOMY_DETAIL_SYNONYMS,
    TUBE_REVISION_SUBTYPE_SYNONYMS,
    WHOLE_NAME_ONLY_VARIANTS,
)


# ============================================================
# Bounded fuzzy matching for procedure names
# ============================================================

AUTO_CORRECT_DISTANCE_CUTOFF = 0.22
AMBIGUOUS_DISTANCE_CUTOFF = 0.34
MIN_SCORE_GAP = 0.06

_ALL_CANDIDATES = sorted(PROCEDURE_SYNONYMS.keys())
_PREFIX_CANDIDATES = sorted(set(_ALL_CANDIDATES) - WHOLE_NAME_ONLY_VARIANTS)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalized_dl_distance(a: str, b: str) -> float:
    """Normalized Damerau-Levenshtein distance in [0, 1] (0 = exact match)."""
    if not a and not b:
        return 0.0
    dist = DamerauLevenshtein.distance(a, b)
    return dist / max(len(a), len(b), 1)


def score_candidate(token: str, candidate: str) -> float:
    """Lower is better. Base is normalized DL distance with a length-mismatch penalty."""
    score = normalized_dl_distance(token, candidate)
    len_diff = abs(len(token) - len(candidate))
    if len_diff >= 4:
        score += 0.08
    elif len_diff >= 2:
        score += 0.03
    return score


def bounded_fuzzy_map_procedure(
    token: str,
    whole_name: bool = True,
) -> Tuple[Optional[str], str, Optional[str], float, Optional[str]]:
    """
    Map a raw procedure token to a canonical procedure name.

    Returns (canonical_name, confidence_flag, note, score, matched_variant).
    confidence_flag is one of: clean / corrected / ambiguous / unmapped.
    matched_variant is the PROCEDURE_SYNONYMS key that produced the canonical name
    (exact token or fuzzy best term), or None when nothing usable matched.

    Set whole_name=False when the token is only the leading part of a longer procedure
    name; the vaguest variants (WHOLE_NAME_ONLY_VARIANTS) are then not considered.
    """
    token = _normalize_whitespace(token.lower())
    if not token:
        return None, "unmapped", "empty token", float("inf"), None

    candidates = _ALL_CANDIDATES if whole_name else _PREFIX_CANDIDATES

    # Exact synonym / canonical hit
    if token in PROCEDURE_SYNONYMS and (whole_name or token not in WHOLE_NAME_ONLY_VARIANTS):
        canon = PROCEDURE_SYNONYMS[token]
        if canon.lower() != token:
            return canon, "corrected", f"exact mapping: {token} -> {canon}", 0.0, token
        return canon, "clean", None, 0.0, token

    # Fuzzy search across all known variants
    scored = [(cand, score_candidate(token, cand)) for cand in candidates]
    scored.sort(key=lambda x: x[1])

    best_term, best_score = scored[0]
    second_score = scored[1][1] if len(scored) > 1 else float("inf")
    canon = PROCEDURE_SYNONYMS[best_term]

    if best_score <= AUTO_CORRECT_DISTANCE_CUTOFF and (second_score - best_score >= MIN_SCORE_GAP):
        return (
            canon,
            "corrected",
            f"fuzzy corrected: {token} -> {best_term} -> {canon} "
            f"(score={best_score:.3f}, second={second_score:.3f})",
            best_score,
            best_term,
        )

    if best_score <= AMBIGUOUS_DISTANCE_CUTOFF:
        return (
            None,
            "ambiguous",
            f"ambiguous fuzzy match for '{token}'; best='{best_term}' "
            f"score={best_score:.3f}; second_score={second_score:.3f}",
            best_score,
            None,
        )

    return (
        None,
        "unmapped",
        f"low-confidence fuzzy match for '{token}'; best='{best_term}' score={best_score:.3f}",
        best_score,
        None,
    )


def _leading_candidates(text: str) -> list:
    """Leading token prefixes, longest first (e.g. 'kdb goniotomy' -> [..., 'kdb'])."""
    tokens = text.split()
    return [" ".join(tokens[:size]) for size in range(len(tokens), 0, -1)]


def _implied_details(
    canon: Optional[str],
    matched_variant: Optional[str],
    full_text: str,
    matched_cand: str,
) -> List[str]:
    """Details implied by the matched synonym variant and any trailing subtype tokens."""
    details: List[str] = []
    seen = set()

    def _add(detail: str) -> None:
        if detail not in seen:
            details.append(detail)
            seen.add(detail)

    if matched_variant:
        for detail in PROCEDURE_IMPLIED_DETAILS.get(matched_variant, []):
            _add(detail)

    # "tube revision repositioning" matches the leading name "tube revision"; harvest
    # the leftover subtype token so it still becomes a parenthetical detail.
    if canon == "tube revision" and full_text.startswith(matched_cand):
        rest = full_text[len(matched_cand):].strip()
        for tok in rest.split():
            subtype = TUBE_REVISION_SUBTYPE_SYNONYMS.get(tok)
            if subtype:
                _add(subtype)

    # "trab express" / "trabeculectomy express shunt" -- express trails a trab name.
    if canon == "trabeculectomy" and full_text.startswith(matched_cand):
        rest = full_text[len(matched_cand):].strip()
        if rest.startswith("express shunt"):
            _add("express")
        else:
            for tok in rest.split():
                detail = TRABECULECTOMY_DETAIL_SYNONYMS.get(tok)
                if detail:
                    _add(detail)

    return details


def resolve_procedure_name(
    text: str,
) -> Tuple[Optional[str], str, Optional[str], List[str]]:
    """
    Resolve a procedure name, trying the full string first and then progressively
    shorter leading prefixes. This lets 'KDB goniotomy' resolve to 'KDB' and
    'laser peripheral iridotomy' resolve to 'LPI' while still allowing fuzzy typo
    correction on the full string. Only the full string may resolve to one of the
    vaguest names (WHOLE_NAME_ONLY_VARIANTS), so 'laser' alone becomes the generic
    laser procedure while 'laser suture lysis' stays unmapped.

    Returns (canonical_name, confidence_flag, note, implied_details).
    """
    text = _normalize_whitespace(text.lower())
    if not text:
        return None, "unmapped", "empty token", []

    best_fuzzy: Optional[Tuple[Optional[str], str, Optional[str], List[str]]] = None
    for cand in _leading_candidates(text):
        canon, flag, note, _, variant = bounded_fuzzy_map_procedure(
            cand, whole_name=cand == text
        )
        implied = _implied_details(canon, variant, text, cand)
        if canon and flag in {"clean", "corrected"}:
            return canon, flag, note, implied
        if canon and best_fuzzy is None:
            best_fuzzy = (canon, flag, note, implied)

    if best_fuzzy is not None:
        return best_fuzzy

    canon, flag, note, _, variant = bounded_fuzzy_map_procedure(text)
    return canon, flag, note, _implied_details(canon, variant, text, text)
