"""
Read a CSV containing prior and/or future procedure labels, standardize the
selected columns, and write the results to a new CSV.

For every input column processed, two columns are inserted immediately to the
right of it:
  - "<input_col> standardized"    the standardized procedure label
  - "<input_col> parsed_items"    JSON with all logging/debugging information
                                  (analogous to the med_standardization
                                  "parsed_items" column)

Examples:
python run.py \
    --input procedures.csv \
    --output procedures_standardized.csv \
    --prior-od-col "Prior Procedures OD" \
    --prior-os-col "Prior Procedures OS" \
    --future-od-col "Future Procedures OD" \
    --future-os-col "Future Procedures OS"

python run.py \
    --input procedures.csv \
    --output procedures_standardized.csv \
    --prior-od-col "Prior Procedures OD" LLM_OD\
    --prior-os-col "Prior Procedures OS" LLM_OS\

You may pass any subset of the four column arguments, and each accepts one or
more column names.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.procedure_standardization import standardize_procedure_label


# --------------------------------------------------
# Logging setup
# --------------------------------------------------

logger = logging.getLogger("procedure_csv_standardizer")
logger.setLevel(logging.INFO)

if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


# --------------------------------------------------
# Column config
# --------------------------------------------------

# Maps each CLI argument to the label_type passed to the standardizer.
COLUMN_SPECS = {
    "prior_od_col": {"label_type": "prior"},
    "prior_os_col": {"label_type": "prior"},
    "future_od_col": {"label_type": "future"},
    "future_os_col": {"label_type": "future"},
}


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Standardize prior/future procedure-label columns from a CSV file."
    )

    parser.add_argument("--input", required=True, help="Path to input CSV file.")
    parser.add_argument("--output", required=True, help="Path to output CSV file.")

    parser.add_argument(
        "--prior-od-col",
        dest="prior_od_col",
        nargs="+",
        help="Column name(s) containing prior procedures for the right eye (OD).",
    )
    parser.add_argument(
        "--prior-os-col",
        dest="prior_os_col",
        nargs="+",
        help="Column name(s) containing prior procedures for the left eye (OS).",
    )
    parser.add_argument(
        "--future-od-col",
        dest="future_od_col",
        nargs="+",
        help="Column name(s) containing future procedures for the right eye (OD).",
    )
    parser.add_argument(
        "--future-os-col",
        dest="future_os_col",
        nargs="+",
        help="Column name(s) containing future procedures for the left eye (OS).",
    )

    return parser.parse_args()


def normalize_cell_value(value: Any) -> Optional[str]:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text == "":
        return None
    return text


def insert_columns_next_to_input(
    df: pd.DataFrame,
    input_col: str,
    column_data: Dict[str, List[Any]],
) -> pd.DataFrame:
    for col in list(column_data.keys()):
        if col in df.columns:
            df.drop(columns=[col], inplace=True)

    insert_idx = df.columns.get_loc(input_col) + 1

    for offset, (col_name, values) in enumerate(column_data.items()):
        df.insert(insert_idx + offset, col_name, values)

    return df


def standardize_one_column(
    df: pd.DataFrame,
    input_col: str,
    label_type: str,
) -> pd.DataFrame:
    if input_col not in df.columns:
        raise ValueError(f"Column '{input_col}' was not found in the input CSV.")

    standardized_col = f"{input_col}_standardized"
    parsed_items_col = f"{input_col}_parsed_items"

    standardized_values: List[Any] = []
    parsed_items_values: List[Any] = []

    logger.info("Processing column '%s' as label_type=%s", input_col, label_type)

    for idx, raw_value in df[input_col].items():
        text = normalize_cell_value(raw_value)

        if text is None:
            standardized_values.append("None")
            parsed_items_values.append(None)
            continue

        try:
            result = standardize_procedure_label(text, label_type=label_type)
            standardized_values.append(result["standardized_procedure_list"])
            parsed_items_values.append(
                json.dumps(
                    {
                        "input_type": result["input_type"],
                        "raw_input": result["raw_input"],
                        "standardized_procedure_list": result["standardized_procedure_list"],
                        "failed_match": result["failed_match"],
                        "parsed_items": result["parsed_items"],
                    },
                    ensure_ascii=False,
                )
            )
        except Exception as exc:  # noqa: BLE001 - keep row-level failures isolated
            standardized_values.append(None)
            parsed_items_values.append(json.dumps({"error": str(exc)}, ensure_ascii=False))
            logger.exception("Failed on row index %s, column '%s'", idx, input_col)

    return insert_columns_next_to_input(
        df,
        input_col,
        {
            standardized_col: standardized_values,
            parsed_items_col: parsed_items_values,
        },
    )


def validate_requested_columns(args: argparse.Namespace) -> Dict[str, List[str]]:
    selected: Dict[str, List[str]] = {}
    for arg_name in COLUMN_SPECS:
        value = getattr(args, arg_name)
        if value:
            selected[arg_name] = value if isinstance(value, list) else [value]

    if not selected:
        raise ValueError(
            "You must provide at least one procedure column argument, such as "
            "--prior-od-col, --prior-os-col, --future-od-col, or --future-os-col."
        )

    return selected


def main() -> None:
    args = parse_args()
    selected = validate_requested_columns(args)

    input_path = Path(args.input)
    output_path = Path(args.output)

    logger.info("Reading input CSV: %s", input_path)
    df = pd.read_csv(input_path)

    for arg_name, input_cols in selected.items():
        spec = COLUMN_SPECS[arg_name]
        for input_col in input_cols:
            df = standardize_one_column(
                df=df,
                input_col=input_col,
                label_type=spec["label_type"],
            )

    logger.info("Writing output CSV: %s", output_path)
    df.to_csv(output_path, index=False)
    logger.info("Done.")


if __name__ == "__main__":
    main()
