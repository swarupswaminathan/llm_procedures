"""Pull procedure tokens and structured components from ``parsed_items`` JSON.

``parsed_items`` cells are written by ``standardization/run.py``.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

NEGATIVE = "no"  # sentinel for "this eye had no procedures"


def _items(value: Any) -> list[dict]:
    """Parsed entries of a cell, dropping the special "None" marker."""
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return []
    items = []
    for item in payload.get("parsed_items") or []:
        special = item.get("special")
        if isinstance(special, str) and special.strip().lower() == "none":
            continue
        items.append(item)
    return items


def _date(item: dict) -> str | None:
    date = item.get("date")
    return date.strip() if isinstance(date, str) and date.strip() else None


def procedures_from_parsed(value: Any, include_date: bool = True) -> list[str]:
    """
    Pull canonical procedure-name tokens out of a parsed_items JSON cell.

    Combined procedures (e.g. CEIOL/Hydrus) become one token per component.
    Empty cells and the special "None" marker become [NEGATIVE]. Matching is on
    procedure_name; extra detail text is ignored.

    include_date controls whether each token carries its date:
      True  -> "ceiol 9/10/2019"  (procedure name + date)
      False -> "ceiol"            (procedure name only)
    """
    tokens = []
    for item in _items(value):
        date = _date(item)
        for component in item.get("components") or []:
            name = (component.get("procedure_name") or "").strip().lower()
            if not name:
                continue
            tokens.append(f"{name} {date}" if (include_date and date) else name)

    return sorted(tokens) if tokens else [NEGATIVE]


def procedures_components_from_parsed(value: Any) -> list[dict]:
    """
    Structured procedures from a parsed_items JSON cell: one dict per component,
    carrying the components used by the date-weighted Jaccard.

    Each element is {'name': str, 'details': frozenset[str], 'date': str|None}:
      - name    : the component's procedure_name (lowercased)
      - details : the component's `details` (location/laterality/degree/count,
                  e.g. 'nasal', 'st', '360/180', 'x2')
      - date    : the entry's date string, or None

    Combined procedures (e.g. CEIOL/Hydrus) become one dict per component, each
    inheriting the entry's date. Empty cells and the special "None" marker yield
    [] (no procedures for this eye).
    """
    procedures = []
    for item in _items(value):
        date = _date(item)
        for component in item.get("components") or []:
            name = (component.get("procedure_name") or "").strip().lower()
            if not name:
                continue
            details = set()
            for d in component.get("details") or []:
                d = str(d).strip().lower()
                if d:
                    details.add(d)
            procedures.append({"name": name, "details": frozenset(details), "date": date})

    return procedures


def split_label_items(label: Any) -> list[str]:
    """
    Split a standardized label string into its procedure entries as a multiset.

    Procedures are comma/semicolon separated, but a comma can appear inside a
    procedure's parenthesised detail (e.g. "tube shunt (anterior chamber, st)"),
    so the split only fires at parenthesis depth zero. Returns a sorted list that
    keeps duplicates so repeated procedures are not collapsed. Empty / 'no' /
    'none' -> [NEGATIVE]. Used for the full-label multiset Jaccard.
    """
    if not isinstance(label, str) or label.strip().lower() in ("", "no", "nan", "none"):
        return [NEGATIVE]

    items, depth, buf = [], 0, ""
    for ch in label:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch in ",;" and depth == 0:
            items.append(buf.strip())
            buf = ""
        else:
            buf += ch
    items.append(buf.strip())

    items = [it.lower() for it in items if it.strip()]
    return sorted(items) if items else [NEGATIVE]


def count_failed_matches(parsed_items: pd.Series) -> int:
    """Rows whose standardization flagged an ambiguous/low-confidence procedure mapping."""
    n = 0
    for value in parsed_items:
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            n += bool(json.loads(value).get("failed_match"))
        except json.JSONDecodeError:
            continue
    return n
