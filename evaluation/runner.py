"""Orchestrate load → procedure evaluation → tee report to disk.

Pipeline position (do not re-run inference or standardization here):
  Inference → llm_results_{cvar}.csv
  → standardization → llm_results_{acronym}_procedures_standardized.csv
  → this evaluation → {acronym}_results.txt
"""

from __future__ import annotations

import sys
import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TextIO

import numpy as np
import pandas as pd

from evaluation.column_map import build_eval_spec, resolve_cvar, resolve_pred_prefix
from evaluation.procedures import run_procedure_evaluation

warnings.filterwarnings("ignore")


class _Tee:
    """Write to multiple streams (console + results file)."""

    def __init__(self, *streams: TextIO) -> None:
        self.streams = streams

    def write(self, data: str) -> int:
        for s in self.streams:
            s.write(data)
            s.flush()
        return len(data)

    def flush(self) -> None:
        for s in self.streams:
            s.flush()


@contextmanager
def tee_stdout(path: Path) -> Iterator[Path]:
    """Temporarily tee stdout to ``path`` as well as the console."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        old = sys.stdout
        sys.stdout = _Tee(old, fh)  # type: ignore[assignment]
        try:
            yield path
        finally:
            sys.stdout = old


def _read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path)
    return pd.read_csv(path)


def run_evaluation(
    input_path: str | Path,
    *,
    cvar: str | None = None,
    acronym: str | None = None,
    pred_prefix: str | None = None,
    verbose: bool = False,
    output_path: str | Path | None = None,
    seed: int | None = None,
) -> Path:
    """Run evaluation and write ``{acronym}_results.txt`` beside the input file."""
    input_path = Path(input_path)
    cvar = resolve_cvar(input_path, cvar=cvar, acronym=acronym)
    df = _read_table(input_path)
    spec = build_eval_spec(cvar, resolve_pred_prefix(list(df.columns), pred_prefix))

    missing = [c for c in spec.required_columns if c not in df.columns]
    if missing:
        raise ValueError(
            f"{input_path.name} is missing standardized columns {missing}. "
            "Run standardization/run.py on both the adjudicated and the model label columns."
        )

    if output_path is None:
        output_path = input_path.parent / f"{spec.acronym}_results.txt"
    else:
        output_path = Path(output_path)

    if seed is not None:
        np.random.seed(seed)

    with tee_stdout(output_path):
        print(f"Input: {input_path}")
        print(f"cvar={spec.cvar} acronym={spec.acronym}")
        print(f"Target: {spec.target_od}, {spec.target_os}")
        print(f"Ai Prediction: {spec.pred_od}, {spec.pred_os}")
        print(f"Report: {output_path}")
        print(f"Loaded {len(df)} rows")
        print()

        run_procedure_evaluation(df, spec, verbose=verbose)

    return output_path
