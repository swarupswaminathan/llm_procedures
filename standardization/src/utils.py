# utils.py

import re
from typing import List, Optional, Tuple

from .constants import (
    ABSORBED_BY_ADJACENT_CANONICAL,
    DETAIL_DEGREE_VALUES,
    DETAIL_LOCATION_SYNONYMS,
    DETAIL_QUADRANT_ABBREV,
    DETAIL_QUADRANT_WORDS,
    EQUIVALENT_CANONICAL_GROUPS,
    HYPHEN_CHARS,
    LATERALITY_TOKENS,
    ANTIMETABOLITE_ALT,
    ANTIMETABOLITE_DOSE,
    ANTIMETABOLITE_MODIFIERS,
    NEVER_STARTS_PROCEDURE,
    NONE_TOKENS,
    POSSIBLE_TOKENS,
    PROCEDURE_SYNONYMS,
    STATUS_PREFIXES,
    WHOLE_NAME_ONLY_VARIANTS,
)

# Two-digit year pivot: years <= this map to 2000s, otherwise 1900s.
TWO_DIGIT_YEAR_PIVOT = 40


# ============================================================
# Generic helpers
# ============================================================

def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_trailing_punctuation(text: str) -> str:
    return normalize_whitespace(re.sub(r"[.,;:]+$", "", text))


def detect_none(text: str) -> bool:
    return normalize_whitespace(text.lower()) in NONE_TOKENS


def split_entry_chunks(text: str) -> List[str]:
    """
    Split a per-eye label into distinct (staged) procedure entries by commas /
    semicolons, ignoring separators inside parentheses so that multi-detail groups
    like "(anterior chamber, ST)" are not broken apart.
    """
    chunks: List[str] = []
    buf: List[str] = []
    depth = 0

    for ch in text:
        if ch == "(":
            depth += 1
            buf.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            buf.append(ch)
        elif ch in ",;" and depth == 0:
            chunk = "".join(buf).strip()
            if chunk:
                chunks.append(chunk)
            buf = []
        else:
            buf.append(ch)

    chunk = "".join(buf).strip()
    if chunk:
        chunks.append(chunk)

    return chunks


# ============================================================
# Status prefixes / laterality (R2 already resolved upstream)
# ============================================================

def strip_status_prefixes(text: str) -> str:
    """Remove leading status-post / history markers repeatedly (e.g. 's/p', 'status post')."""
    changed = True
    while changed:
        changed = False
        stripped = text.strip()
        for prefix in sorted(STATUS_PREFIXES, key=len, reverse=True):
            # match prefix as a leading unit followed by space or word boundary
            pattern = rf"^{re.escape(prefix)}\b[\s:.-]*"
            new = re.sub(pattern, "", stripped, flags=re.I)
            if new != stripped:
                text = new
                changed = True
                break
    return normalize_whitespace(text)


def extract_laterality_markers(text: str) -> Tuple[str, bool]:
    """
    Remove OD/OS/OU tokens (laterality is fixed by the source column) and detect the
    explicit "laterality unknown" marker.

    The marker may appear on its own ("SLT (laterality unknown)") or sharing a
    parenthetical with real procedure details ("SLT (x3, laterality unknown)"). In the
    latter case only the marker (and its adjacent separator) is removed, so the other
    details survive and the marker is re-emitted as its own trailing parenthetical.
    """
    laterality_unknown = bool(re.search(r"laterality\s+unknown", text, flags=re.I))

    # Drop the marker together with a neighboring comma/semicolon so a shared
    # parenthetical like "(x3, laterality unknown)" collapses to "(x3)".
    text = re.sub(r"\s*[,;]\s*laterality\s+unknown", "", text, flags=re.I)
    text = re.sub(r"laterality\s+unknown\s*[,;]\s*", "", text, flags=re.I)
    # Remove a now-standalone parenthetical and any remaining bare phrase.
    text = re.sub(r"\(\s*laterality\s+unknown\s*\)", "", text, flags=re.I)
    text = re.sub(r"laterality\s+unknown", "", text, flags=re.I)
    # Clean up parentheses left empty by the removal.
    text = re.sub(r"\(\s*\)", "", text)

    for tok in LATERALITY_TOKENS:
        text = re.sub(rf"\b{tok}\b", "", text, flags=re.I)

    return normalize_whitespace(text), laterality_unknown


# ============================================================
# Uncertainty (R7)
# ============================================================

def extract_possible(text: str) -> Tuple[str, bool]:
    """Detect leading uncertainty markers ('?', 'possible', 'likely', ...) about occurrence."""
    possible = False
    t = text.strip()

    # Leading question mark(s)
    m = re.match(r"^\s*\?+\s*", t)
    if m:
        possible = True
        t = t[m.end():]

    for tok in sorted(POSSIBLE_TOKENS, key=len, reverse=True):
        if tok == "?":
            continue
        pattern = rf"^\s*{re.escape(tok)}\b\s*"
        new = re.sub(pattern, "", t, flags=re.I)
        if new != t:
            possible = True
            t = new
            break

    return normalize_whitespace(t), possible


# ============================================================
# Date handling (R4 + temporal uncertainty R7)
# ============================================================

def _four_digit_year(year: str) -> str:
    if len(year) == 4:
        return year
    yy = int(year)
    century = 2000 if yy <= TWO_DIGIT_YEAR_PIVOT else 1900
    return str(century + yy)


def extract_date(text: str) -> Tuple[str, Optional[str], bool]:
    """
    Extract and normalize a single date from the text.

    Returns (remaining_text, normalized_date_or_None, date_uncertain).

    Normalization (R4):
      - M/D/YYYY, M/D/YY  -> M/D/YYYY
      - M/YYYY            -> M/YYYY (kept)
      - YYYY              -> YYYY
      - decade (YYYYs / YYs) -> normalized decade, marked uncertain (R7)
      - M/D (2-digit tail) -> left as-is (ambiguous without note context, R4)

    Temporal uncertainty (R7): a leading '~', trailing '?', or a decade range marks
    the date uncertain so it renders with a leading '~'.
    """
    date_uncertain = False
    working = text

    # Decade, e.g. 1990s, 2010s, 90s, ~1980s
    decade = re.search(r"~?\s*\b(\d{2,4})s\b", working)
    if decade:
        raw_year = decade.group(1)
        year = _four_digit_year(raw_year) if len(raw_year) in (2, 4) else raw_year
        norm = f"{year}s"
        working = normalize_whitespace(working[:decade.start()] + " " + working[decade.end():])
        return working, norm, True  # decades are inherently a range -> uncertain

    # Year/Year typo, e.g. "2018/2019" -- a single date mis-printed with a slash.
    # Keep only the first year so it doesn't get split into a spurious procedure.
    m = re.search(r"(~)?\s*\b(\d{4})\s*/\s*\d{2,4}\b\s*(\?)?", working)
    if m:
        if m.group(1) or m.group(3):
            date_uncertain = True
        norm = m.group(2)
        working = normalize_whitespace(working[:m.start()] + " " + working[m.end():])
        return working, norm, date_uncertain

    # Full M/D/Y date (with optional ~ prefix and ? suffix)
    m = re.search(r"(~)?\s*\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b\s*(\?)?", working)
    if m:
        if m.group(1) or m.group(5):
            date_uncertain = True
        month, day, year = m.group(2), m.group(3), _four_digit_year(m.group(4))
        norm = f"{int(month)}/{int(day)}/{year}"
        working = normalize_whitespace(working[:m.start()] + " " + working[m.end():])
        return working, norm, date_uncertain

    # Month/Year where tail is a 4-digit year, e.g. 6/2015
    m = re.search(r"(~)?\s*\b(\d{1,2})/(\d{4})\b\s*(\?)?", working)
    if m:
        if m.group(1) or m.group(4):
            date_uncertain = True
        month, year = m.group(2), m.group(3)
        norm = f"{int(month)}/{year}"
        working = normalize_whitespace(working[:m.start()] + " " + working[m.end():])
        return working, norm, date_uncertain

    # Ambiguous two-part M/D (2-digit tail): preserve as-is without a year (R4)
    m = re.search(r"(~)?\s*\b(\d{1,2})/(\d{1,2})\b\s*(\?)?", working)
    if m:
        if m.group(1) or m.group(4):
            date_uncertain = True
        norm = f"{int(m.group(2))}/{int(m.group(3))}"
        working = normalize_whitespace(working[:m.start()] + " " + working[m.end():])
        return working, norm, date_uncertain

    # Bare 4-digit year (with optional ~ prefix and ? suffix)
    m = re.search(r"(~)?\s*\b(\d{4})\b\s*(\?)?", working)
    if m:
        if m.group(1) or m.group(3):
            date_uncertain = True
        norm = m.group(2)
        working = normalize_whitespace(working[:m.start()] + " " + working[m.end():])
        return working, norm, date_uncertain

    return normalize_whitespace(working), None, False


def render_date(date: Optional[str], date_uncertain: bool) -> str:
    if not date:
        return ""
    return f"~{date}" if date_uncertain else date


# ============================================================
# Combined-procedure splitting (R9)
# ============================================================

# A dash joins two procedures ("phaco-Hydrus") about as often as it hyphenates a single
# name ("i-stent", "Ex-PRESS", "5-FU") or introduces a detail ("Ahmed FP7 - sulcus"), so
# it separates only when a known procedure name sits on either side of it. The word to
# the right is matched with a lookahead so it can also open the next pair, letting a
# chain like "phaco-KDB-goniotomy" come apart at every dash.
HYPHENATED_PAIR_PATTERN = re.compile(
    rf"\b([a-z][a-z0-9/]*)\s*[{HYPHEN_CHARS}]+\s*(?=([a-z][a-z0-9/]*)\b)",
    re.I,
)


def _space_hyphenated_procedures(match: "re.Match") -> str:
    """Turn a dash between two procedure names into a space, leaving other dashes be."""
    left, right = match.group(1), match.group(2)
    if left.lower() in PROCEDURE_SYNONYMS and right.lower() in PROCEDURE_SYNONYMS:
        # Whether the pair really is two procedures ("phaco-Hydrus") or one procedure
        # named twice ("Ahmed-FP7", "KDB-goniotomy") is decided by the space-separated
        # logic, which already knows those cases.
        return f"{left} "
    return match.group(0)


def _protect_slashes_inside_parentheses(text: str) -> str:
    """Replace '/' inside parentheses so it is not treated as a combined separator."""
    out: List[str] = []
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
            out.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            out.append(ch)
        elif ch == "/" and depth > 0:
            out.append("\x00")
        else:
            out.append(ch)
    return "".join(out)


def split_combined_components(text: str) -> List[str]:
    """
    Split a single entry into combined same-day components (R9).

    Separators: '+', '&', 'with', 'w/', 'plus', 'combined with', '/' (only when NOT
    between digits, so degree details like '360/180' are preserved), and a dash between
    two procedure names (see HYPHENATED_PAIR_PATTERN). A bare space also separates
    procedures ("Phaco iStent"); see split_space_separated_components.
    Cataract "phaco/IOL" style strings are normalized to a single token beforehand.
    """
    working = text

    # Antimetabolites (MMC, 5FU) are modifiers, not separate procedures. Detach them
    # from any combined separator so "trabeculectomy + MMC" / "Trab+5FU" stay a single
    # procedure ("trabeculectomy MMC" / "trabeculectomy 5FU") rather than splitting off
    # an unmappable modifier. An optional dose between the separator and the drug
    # ("w/ 10 mg 5FU") is consumed here so it cannot open a second component.
    # `\bw/` is listed before `/` so "w/ 5FU" does not leave a stray "w".
    working = re.sub(
        rf"\s*(?:\+|&|\bcombined with\b|\bwith\b|\bw/|\bplus\b|[{HYPHEN_CHARS}]|/)"
        rf"\s*(?:{ANTIMETABOLITE_DOSE})?\b({ANTIMETABOLITE_ALT})\b",
        r" \1",
        working,
        flags=re.I,
    )

    # Normalize cataract "phaco/IOL" family to a single token before '/' splitting.
    # The "/IOL" / "/PCIOL" suffix denotes the lens implant, not a separate procedure,
    # so "CE/PCIOL", "phaco/PCIOL", "phaco-IOL", etc. collapse into the cataract token
    # (-> CEIOL) instead of being read as two procedures.
    lens = rf"\s*[/{HYPHEN_CHARS}]\s*"
    working = re.sub(rf"\bphaco{lens}p?ciol\b", "phaco/iol", working, flags=re.I)
    working = re.sub(rf"\bce{lens}p?ciol\b", "ce/iol", working, flags=re.I)
    working = re.sub(rf"\bphaco{lens}iol\b", "phaco/iol", working, flags=re.I)
    working = re.sub(rf"\bce{lens}iol\b", "ce/iol", working, flags=re.I)

    # Ex-PRESS is a trabeculectomy detail, not a second procedure. Collapse
    # "trab/express", "trab-express", "express/trab", "Ex-PRESS-trab", etc. into a
    # space-separated pair before '/' / dash splitting so they standardize as
    # "trabeculectomy (express)" rather than a combined procedure.
    join = rf"\s*[/{HYPHEN_CHARS}]\s*"
    trab_name = r"(?:trab|trabs|trabeculectomy)"
    express_name = (
        rf"(?:ex[{HYPHEN_CHARS}]?press|express)"
        rf"(?:\s+shunt)?(?!\s+(?:removal|explant|explantation))"
    )
    working = re.sub(
        rf"\b{trab_name}{join}{express_name}\b", "trab express", working, flags=re.I
    )
    working = re.sub(
        rf"\b{express_name}{join}{trab_name}\b", "trab express", working, flags=re.I
    )

    # Dash-separated combinations ("phaco-Hydrus"), now that the cataract lens suffix
    # above is no longer a dash that could be mistaken for one.
    working = HYPHENATED_PAIR_PATTERN.sub(_space_hyphenated_procedures, working)

    # Protect the recognized single-token cataract combos.
    working = re.sub(r"\bphaco/iol\b", "PHACOIOL_TOKEN", working, flags=re.I)
    working = re.sub(r"\bce/iol\b", "CEIOL_TOKEN", working, flags=re.I)

    # Word separators
    working = re.sub(r"\bcombined with\b", "+", working, flags=re.I)
    working = re.sub(r"\bw/", "+", working, flags=re.I)
    working = re.sub(r"\bwith\b", "+", working, flags=re.I)
    working = re.sub(r"\bplus\b", "+", working, flags=re.I)
    working = working.replace("&", "+")

    # '/' is a combined separator except (1) inside parentheses, where it is
    # commentary or a detail ("mod/heavy", "360/180"), and (2) between digits, a
    # degree range like "360/180". Protect those slashes, split the rest, restore.
    working = _protect_slashes_inside_parentheses(working)
    working = re.sub(r"(?<=\d)\s*/\s*(?=\d)", "\x00", working)
    working = re.sub(r"\s*/\s*", "+", working)
    working = working.replace("\x00", "/")

    parts = [p.strip() for p in working.split("+") if p.strip()]

    # Restore protected cataract tokens
    restored = []
    for p in parts:
        p = p.replace("PHACOIOL_TOKEN", "phaco/IOL").replace("CEIOL_TOKEN", "CE/IOL")
        restored.append(p)

    # A combination may carry no separator at all ("Phaco iStent"), so every part is
    # split further wherever two recognized procedure names sit side by side.
    components: List[str] = []
    for p in restored:
        components.extend(split_space_separated_components(p))
    return components


# ============================================================
# Space-separated combined procedures (R9)
# ============================================================

# Longest vocabulary entry, in tokens (e.g. "laser peripheral iridotomy").
MAX_ANCHOR_TOKENS = max(len(key.split()) for key in PROCEDURE_SYNONYMS)


def _vocabulary_token(token: str) -> str:
    """Lower-case a token and drop surrounding punctuation for vocabulary lookup."""
    return token.strip("()[]{}.,;:!?\"'").lower()


def _tokenize_with_depth(text: str) -> List[Tuple[str, int]]:
    """
    Split on whitespace, pairing each token with its parenthesis nesting depth.

    A token that opens a parenthetical counts as being inside it, so nothing in
    "(iTrack, 360)" is mistaken for a separate procedure. Unbalanced input is clamped.
    """
    tokens: List[Tuple[str, int]] = []
    buf: List[str] = []
    buf_depth = 0
    depth = 0

    for ch in text:
        if ch.isspace():
            if buf:
                tokens.append(("".join(buf), buf_depth))
                buf = []
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if not buf:
            buf_depth = depth
        buf.append(ch)

    if buf:
        tokens.append(("".join(buf), buf_depth))
    return tokens


def _same_procedure(canonical: str, other: Optional[str]) -> bool:
    """True when two canonical names are alternative descriptions of one procedure."""
    if other is None:
        return False
    if canonical == other:
        return True
    return any(
        canonical in group and other in group for group in EQUIVALENT_CANONICAL_GROUPS
    )


def _procedure_anchors(tokens: List[Tuple[str, int]]) -> List[Tuple[int, str]]:
    """
    Locate the vocabulary matches that each start a distinct procedure.

    Matching is exact and longest-first, so multi-word names ("laser peripheral
    iridotomy", "MP CPC") are consumed whole; a match that only re-describes the
    procedure beside it is dropped. Returns (token index, canonical name).
    """
    candidates: List[Tuple[int, str, str]] = []

    i = 0
    while i < len(tokens):
        matched = 0
        if tokens[i][1] == 0:
            for size in range(min(MAX_ANCHOR_TOKENS, len(tokens) - i), 0, -1):
                phrase = " ".join(_vocabulary_token(t) for t, _ in tokens[i:i + size])
                canonical = PROCEDURE_SYNONYMS.get(phrase)
                if canonical is None:
                    continue
                # Vague names like "laser" / "lysis" may be a procedure on their own, but
                # must not open a new component inside a longer unknown phrase
                # ("laser suture lysis").
                is_complete = i == 0 and i + size == len(tokens)
                if phrase in WHOLE_NAME_ONLY_VARIANTS and not is_complete:
                    matched = size
                    break
                if phrase not in NEVER_STARTS_PROCEDURE:
                    candidates.append((i, canonical, phrase))
                matched = size
                break
        i += max(1, matched)

    anchors: List[Tuple[int, str]] = []
    for position, (index, canonical, phrase) in enumerate(candidates):
        previous = anchors[-1][1] if anchors else None
        following = (
            candidates[position + 1][1] if position + 1 < len(candidates) else None
        )

        if _same_procedure(canonical, previous) or _same_procedure(canonical, following):
            continue

        absorbing = ABSORBED_BY_ADJACENT_CANONICAL.get(phrase, set())
        if previous in absorbing or following in absorbing:
            continue

        anchors.append((index, canonical))

    return anchors


def split_space_separated_components(text: str) -> List[str]:
    """
    Split a combination written with only whitespace between the procedures, e.g.
    "Phaco iStent" -> ["Phaco", "iStent"] (R9).

    Boundaries are placed only at exact vocabulary matches, so unrecognized words and
    detail text ("BGI 350 in sulcus", "SLT temp") stay attached to the procedure they
    follow. Text containing fewer than two recognized procedures is returned unchanged,
    which keeps single procedures whose name spans several words intact.
    """
    tokens = _tokenize_with_depth(text)
    if len(tokens) < 2:
        return [text] if text.strip() else []

    anchors = _procedure_anchors(tokens)
    if len(anchors) < 2:
        return [text]

    # The first anchor is not a boundary, so any leading text stays with it.
    boundaries = [index for index, _ in anchors[1:]] + [len(tokens)]

    components = []
    start = 0
    for boundary in boundaries:
        chunk = " ".join(tok for tok, _ in tokens[start:boundary]).strip()
        if chunk:
            components.append(chunk)
        start = boundary
    return components


# ============================================================
# Detail extraction (R6) + MMC handling
# ============================================================

def extract_antimetabolites(text: str) -> Tuple[str, List[str]]:
    """
    Extract antimetabolite modifiers (MMC, 5FU) that attach to the procedure name.

    Returns (remaining_text, [canonical modifiers]) in a fixed order.
    """
    found: List[str] = []
    for pattern, canonical in ANTIMETABOLITE_MODIFIERS:
        if re.search(pattern, text, flags=re.I):
            text = re.sub(pattern, "", text, flags=re.I)
            found.append(canonical)
    return normalize_whitespace(text), found


def extract_details(text: str) -> Tuple[str, List[str]]:
    """
    Extract clinically-relevant procedural details (R6) in source order.

    Returns (remaining_name_text, [canonical_details]).
    Handles: degrees (360/180), counts (x2), locations/approaches (temporal, sulcus,
    pars plana, anterior chamber, ...), and quadrants (ST, INQ, superotemporal, ...).
    """
    matches = []  # (start_index, canonical_detail, match_span)

    # 1) Degrees, e.g. "360", "360/180" -- only valid degree values
    for m in re.finditer(r"\b(90|180|270|360)(?:\s*/\s*(90|180|270|360))+\b|\b(90|180|270|360)\b", text):
        raw = m.group(0)
        canonical = re.sub(r"\s*/\s*", "/", raw)
        matches.append((m.start(), canonical, m.span()))

    # 2) Counts, e.g. x2, x3, 2x, 3x, ×2
    for m in re.finditer(r"\b(?:[x\u00d7]\s?\d+|\d+\s?[x\u00d7])\b", text, flags=re.I):
        raw = m.group(0)
        num = re.search(r"\d+", raw).group(0)
        matches.append((m.start(), f"x{num}", m.span()))

    # 3) Multi-word locations first (anterior chamber, pars plana), then single words
    for phrase in ("anterior chamber", "pars plana"):
        for m in re.finditer(rf"\b{re.escape(phrase)}\b", text, flags=re.I):
            matches.append((m.start(), DETAIL_LOCATION_SYNONYMS[phrase], m.span()))

    single_locs = {k: v for k, v in DETAIL_LOCATION_SYNONYMS.items() if " " not in k}
    for variant, canonical in single_locs.items():
        for m in re.finditer(rf"\b{re.escape(variant)}\b", text, flags=re.I):
            matches.append((m.start(), canonical, m.span()))

    # 4) Quadrants: full words (case-insensitive) and abbreviations (case-sensitive upper)
    for word, canonical in DETAIL_QUADRANT_WORDS.items():
        for m in re.finditer(rf"\b{word}\b", text, flags=re.I):
            matches.append((m.start(), canonical, m.span()))
    for abbrev, canonical in DETAIL_QUADRANT_ABBREV.items():
        for m in re.finditer(rf"\b{abbrev}\b", text):  # case-sensitive
            matches.append((m.start(), canonical, m.span()))

    if not matches:
        return normalize_whitespace(text), []

    # Resolve overlaps: prefer earliest start, then longest span
    matches.sort(key=lambda x: (x[0], -(x[2][1] - x[2][0])))
    chosen = []
    occupied = []
    for start, canonical, span in matches:
        if any(not (span[1] <= s or span[0] >= e) for s, e in occupied):
            continue
        chosen.append((start, canonical, span))
        occupied.append(span)

    # Remove matched spans from the text (right to left to keep indices valid)
    chosen_by_pos = sorted(chosen, key=lambda x: x[2][0], reverse=True)
    for _, _, span in chosen_by_pos:
        text = text[:span[0]] + " " + text[span[1]:]

    # De-duplicate details, then sort alphabetically so equivalent labels written
    # with details in a different order still match.
    seen = set()
    unique = []
    for _, canonical, _ in sorted(chosen, key=lambda x: x[0]):
        if canonical not in seen:
            unique.append(canonical)
            seen.add(canonical)

    details = sorted(unique, key=detail_sort_key)
    return normalize_whitespace(text), details


def detail_sort_key(detail: str) -> str:
    """Alphabetical ordering for parenthetical details (case-insensitive)."""
    return detail.lower()


# ============================================================
# Name cleanup helpers
# ============================================================

def clean_name_text(text: str) -> str:
    """
    Prepare the residual procedure-name text for resolution.

    Removes non-detail parenthetical commentary (R6 says outcome/efficacy notes like
    "did not work" are not preserved), connector words, filler verbiage, and stray
    punctuation. Words that are legitimately part of procedure names (e.g. "laser",
    "surgery", "blade") are intentionally kept.
    """
    # Any parenthetical detail was already captured by extract_details; drop leftover
    # parenthetical commentary entirely.
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[()\[\]]", " ", text)

    # Spot counts ("12-14 spots", "12 spots") are treatment-technique notes, not
    # a retained detail (R6 keeps x2 / 3x treatment *counts*, not CPC spot numbers).
    text = re.sub(r"\b\d+(?:\s*-\s*\d+)?\s*spots?\b", " ", text, flags=re.I)

    text = re.sub(
        r"\b(?:in|of|the|a|an|degree|degrees|performed|previously|done|prior|status)\b",
        " ",
        text,
        flags=re.I,
    )
    text = re.sub(r"[-]{2,}", " ", text)
    return normalize_whitespace(text)


def separate_model_suffix(text: str) -> Tuple[str, Optional[str]]:
    """
    Split a trailing device model/size token (FP7, 250, 350) from the base name so it
    can be re-attached to the canonical name (R6: models stay in the name).
    """
    # A dash before the model is punctuation within the name: "BGI-350" is "BGI 350".
    text = re.sub(rf"[{HYPHEN_CHARS}]+\s*(?=(?:fp7|250|350)\b)", " ", text, flags=re.I)

    m = re.search(r"\b(fp7|250|350)\b\s*$", text, flags=re.I)
    if not m:
        return normalize_whitespace(text), None
    model = m.group(1).upper()
    base = normalize_whitespace(text[:m.start()])
    return base, model
