"""Column names and cvar/acronym resolution for evaluation inputs.

Standardized column names follow ``standardization/run.py``: every processed
column ``X`` gains ``X_standardized`` and ``X_parsed_items``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# cvar -> adjudicated (ground-truth) column prefix; " OD" / " OS" is appended
CVAR_TO_TARGET: dict[str, str] = {
    "prior_procedures_staged": "Prior glaucoma surgeries or lasers",
    "future_procedures_staged": "Other proposed intervention",
}

# cvar <-> acronym registry
CVAR_TO_ACRONYM: dict[str, str] = {
    "prior_procedures_staged": "prior",
    "future_procedures_staged": "future",
}

ACRONYM_TO_CVAR: dict[str, str] = {v: k for k, v in CVAR_TO_ACRONYM.items()}

# cvar -> wording used in the report
CVAR_TO_NOUN: dict[str, str] = {
    "prior_procedures_staged": "prior procedures",
    "future_procedures_staged": "proposed procedures",
}

# Basename -> acronym (includes short-form and long-form standardized names)
BASENAME_TO_ACRONYM: dict[str, str] = {
    "llm_results_prior_procedures_standardized": "prior",
    "llm_results_future_procedures_standardized": "future",
    "llm_results_prior_procedures_staged_standardized": "prior",
    "llm_results_future_procedures_staged_standardized": "future",
}

NOTE_COL = "NOTE_ID"


@dataclass(frozen=True)
class EvalSpec:
    """Resolved evaluation configuration for one standardized results file."""

    cvar: str
    acronym: str
    noun: str
    pred_prefix: str
    target_od: str
    target_os: str
    pred_od: str
    pred_os: str
    target_parsed_od: str
    target_parsed_os: str
    pred_parsed_od: str
    pred_parsed_os: str

    @property
    def required_columns(self) -> list[str]:
        return [
            NOTE_COL,
            self.target_od, self.target_os, self.pred_od, self.pred_os,
            self.target_parsed_od, self.target_parsed_os,
            self.pred_parsed_od, self.pred_parsed_os,
        ]


def resolve_cvar(
    input_path: str | Path,
    cvar: str | None = None,
    acronym: str | None = None,
) -> str:
    """Resolve the cvar from ``--cvar`` / ``--acronym`` or the input filename registry."""
    if cvar and acronym:
        if CVAR_TO_ACRONYM.get(cvar) != acronym:
            raise ValueError(
                f"--cvar {cvar!r} and --acronym {acronym!r} disagree "
                f"(expected acronym {CVAR_TO_ACRONYM.get(cvar)!r})"
            )
    if cvar:
        if cvar not in CVAR_TO_ACRONYM:
            raise ValueError(f"Unknown cvar {cvar!r}. Expected one of {sorted(CVAR_TO_ACRONYM)}")
        return cvar
    if acronym:
        if acronym not in ACRONYM_TO_CVAR:
            raise ValueError(
                f"Unknown acronym {acronym!r}. Expected one of {sorted(ACRONYM_TO_CVAR)}"
            )
        return ACRONYM_TO_CVAR[acronym]
    stem = Path(input_path).stem
    if stem not in BASENAME_TO_ACRONYM:
        raise ValueError(
            f"Cannot infer cvar from filename {Path(input_path).name!r}. "
            f"Pass --cvar / --acronym, or use a known basename: {sorted(BASENAME_TO_ACRONYM)}"
        )
    return ACRONYM_TO_CVAR[BASENAME_TO_ACRONYM[stem]]


def resolve_pred_prefix(columns: list[str], pred_prefix: str | None) -> str:
    """Return the ``{model}_label`` prefix, inferring it when exactly one exists."""
    if pred_prefix:
        return pred_prefix
    found = sorted(
        {m.group(1) for c in columns if (m := re.fullmatch(r"(.+_label)_OD_standardized", c))}
    )
    if len(found) != 1:
        raise ValueError(
            f"Expected exactly one '*_label_OD_standardized' column, found {found}. "
            "Pass --model_name."
        )
    return found[0]


def build_eval_spec(cvar: str, pred_prefix: str) -> EvalSpec:
    target = CVAR_TO_TARGET[cvar]
    return EvalSpec(
        cvar=cvar,
        acronym=CVAR_TO_ACRONYM[cvar],
        noun=CVAR_TO_NOUN[cvar],
        pred_prefix=pred_prefix,
        target_od=f"{target} OD_standardized",
        target_os=f"{target} OS_standardized",
        pred_od=f"{pred_prefix}_OD_standardized",
        pred_os=f"{pred_prefix}_OS_standardized",
        target_parsed_od=f"{target} OD_parsed_items",
        target_parsed_os=f"{target} OS_parsed_items",
        pred_parsed_od=f"{pred_prefix}_OD_parsed_items",
        pred_parsed_os=f"{pred_prefix}_OS_parsed_items",
    )
