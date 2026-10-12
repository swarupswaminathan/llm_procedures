# models.py

from dataclasses import dataclass, field
from typing import List, Optional

# ============================================================
# Canonical schema
# ============================================================


@dataclass
class ProcedureComponent:
    """
    A single procedure within a (possibly combined) entry.

    A combined, same-day entry such as "phaco/Omni (360/180)" is represented by
    two components: one for "phaco" and one for "Omni" (with detail "360/180").
    """

    raw: str
    procedure_name: Optional[str]           # normalized canonical name, e.g. "trabeculectomy", "SLT", "AGI FP7"
    details: List[str] = field(default_factory=list)   # preserved modifiers, alphabetical
    confidence_flag: str = "clean"          # clean / corrected / ambiguous / unmapped
    correction_notes: Optional[str] = None


@dataclass
class ParsedProcedure:
    """
    A single standardized procedure entry for one eye.

    Entries are comma-separated in the source label and correspond to distinct
    (staged) procedures. Combined same-day procedures are captured as multiple
    ``components`` joined by "/" at render time.
    """

    raw_chunk: str
    label_type: str                         # prior / future
    components: List[ProcedureComponent] = field(default_factory=list)

    date: Optional[str] = None              # normalized date, e.g. "1/16/2019", "6/2015", "2015"
    date_uncertain: bool = False            # render date with a leading "~"

    possible: bool = False                  # uncertainty whether the procedure occurred (R7)
    laterality_unknown: bool = False        # append "(laterality unknown)"

    special: Optional[str] = None           # "None" when no qualifying procedure

    confidence_flag: str = "clean"          # worst flag across components
    correction_notes: Optional[str] = None
