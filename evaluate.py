#!/usr/bin/env python3
"""CLI entry for procedure extraction evaluation.

Compares standardized model labels against standardized adjudicated labels and
writes a text report (exact match, F1, Jaccard, Gwet AC1, date-weighted
Jaccard, count errors).

Example:
  python evaluate.py \\
    --input results/prior_procedures_staged/.../llm_results_prior_procedures_standardized.csv \\
    [--cvar prior_procedures_staged | --acronym prior] [--model_name gpt]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evaluation.column_map import ACRONYM_TO_CVAR, CVAR_TO_ACRONYM  # noqa: E402
from evaluation.runner import run_evaluation  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate standardized procedure results against adjudicated labels."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to llm_results_{acronym}_procedures_standardized.csv (or .xlsx)",
    )
    parser.add_argument(
        "--cvar",
        choices=sorted(CVAR_TO_ACRONYM),
        default=None,
        help="Staged cvar (inferred from --acronym or input filename if omitted).",
    )
    parser.add_argument(
        "--acronym",
        choices=sorted(ACRONYM_TO_CVAR),
        default=None,
        help="Short acronym prior/future (inferred if omitted).",
    )
    parser.add_argument(
        "--model_name",
        default=None,
        help=(
            "Model alias whose {alias}_label_OD/OS columns are scored "
            "(inferred when the file holds a single model's labels)."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-eye mismatches.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for the bootstrap confidence intervals.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional report path (default: {acronym}_results.txt beside input).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"Input not found: {input_path}", file=sys.stderr)
        return 2

    out = run_evaluation(
        input_path,
        cvar=args.cvar,
        acronym=args.acronym,
        pred_prefix=f"{args.model_name}_label" if args.model_name else None,
        verbose=args.verbose,
        output_path=args.output,
        seed=args.seed,
    )
    print(f"Wrote report: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
