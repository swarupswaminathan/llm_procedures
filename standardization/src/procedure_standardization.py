'''
Procedure-label standardization for prior and future glaucoma/cataract procedures.

Test run from the standardization directory with:
    python -m src.procedure_standardization

The input is a per-eye procedure label (already split by laterality and by
prior/future in the source spreadsheet), for example:
    "trab MMC OD 3/2018, phaco + goniotomy 6/12/2024"

This standardizer is used to make LLM-generated labels and human "true" labels
directly comparable, so identical procedures always render to an identical string.

Standardization applies the formatting rules from configs/prompt_config.py that
operate on an extracted label (R4 dates, R5 normalization, R6 detail preservation,
R7 uncertainty, R9 combined formatting, R11 None fallback), and additionally orders
the output list chronologically then alphabetically. There is intentionally NO
de-duplication: every procedure present in the input is preserved.
A "future" label is rendered without a date, since a date on a procedure that has not
happened yet says when it is planned rather than when it occurred; such a list is
therefore ordered alphabetically.
Laterality (R3) and temporal scope (R1/R2) are assumed already resolved by the
choice of source column.
'''

import json
from dataclasses import asdict
from typing import Any, Dict

from .parser import (
    parse_procedure_label,
    render_entry,
    sort_entries,
)

VALID_LABEL_TYPES = {"prior", "future"}


def normalize_label_type(label_type: str) -> str:
    if not isinstance(label_type, str):
        raise TypeError("label_type must be a string")
    normalized = label_type.strip().lower()
    if normalized not in VALID_LABEL_TYPES:
        raise ValueError('label_type must be either "prior" or "future"')
    return normalized


def standardize_procedure_label(procedure_label: str, label_type: str = "prior") -> Dict[str, Any]:
    """
    Standardize a single per-eye procedure label.

    Args:
        procedure_label: Raw procedure label text for one eye.
        label_type: "prior" or "future".

    Returns:
        dict with:
          - input_type: the normalized label_type
          - raw_input: the original label
          - standardized_procedure_list: standardized string ("None" if empty)
          - parsed_items: structured per-entry parse (logging/debug info)
          - failed_match: True if any procedure was ambiguous/unmapped
    """
    label_type = normalize_label_type(label_type)

    entries = parse_procedure_label(procedure_label, label_type)

    failed_match = any(
        e.confidence_flag in {"ambiguous", "unmapped"} for e in entries
    )

    kept = sort_entries([e for e in entries if e.special != "None"])

    rendered = [render_entry(e) for e in kept]
    rendered = [r for r in rendered if r and r != "None"]

    standardized_string = ", ".join(rendered) if rendered else "None"

    return {
        "input_type": label_type,
        "raw_input": procedure_label,
        "standardized_procedure_list": standardized_string,
        "parsed_items": [asdict(e) for e in entries],
        "failed_match": failed_match,
    }


# ============================================================
# Example usage
# ============================================================

if __name__ == "__main__":
    examples = [
        ("May have had ALT", "prior"),
        ("CEIOL, BGI, Xen", "prior"),
        ("LI 2010, CEIOL, YAG 3/24/2022", "prior"),
        ("PCIOL 2020", "prior"),
        ("SLT (temp) 1/16/19, SLT 6/2015", "prior"),
        ("? trab", "prior"),
        ("cataract surgery ~1990s", "prior"),
        ("None", "prior"),
        ("Xen, Durysta", "future"),
        ("Trabeculectomy 2004, Revision Trabeculectomy 2017, CEIOL", "prior"),
        ("trabeculectomy 2004, trabeculectomy revision 2017, CEIOL", "prior"),
        ("phaco/IOL+AGI in anterior chamber (10/3/18)", "prior"),
        ("phaco + Omni 360/180 2/10/23", "prior"),
        ("Phaco iStent 6/2020", "prior"),
        ("BGI350 in sulcus 2/17/2020, CEIOL", "prior"),
        ("AGI (anterior chamber, ST) 11/29/2017, CEIOL 2019", "prior"),
        ("tube revision (with tube extender) 5/1/2024", "prior"),
        ("tube revision & choroidal drainage 4/21/2021", "prior"),
        ("Trab MMC 3/2018", "prior"),
        ("Trabeculectomy + MMC 2/23/2018, Possible SLT 1/2018", "prior"),
        ("needling (5FU) 2/23/2018", "prior"),
        ("BGI 350/trabeculectomy 11/8/2018", "prior"),
        ("CEIOL 2018/2019", "prior"),
        ("CE/PCIOL/GATT 3/25/21", "prior"),
        ("move tubes", "future"),
    ]

    for label, ltype in examples:
        result = standardize_procedure_label(label, ltype)
        print(f"INPUT ({ltype}): {label}")
        print(f"OUTPUT: {result['standardized_procedure_list']}")
        print(json.dumps(result["parsed_items"], indent=2))
        print("-" * 80)
