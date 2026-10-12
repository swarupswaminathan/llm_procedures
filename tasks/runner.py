"""Grading-set loop: load notes, run staged extraction, write per-note results."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from tqdm import tqdm

from config import RunContext, ServerFailureError
from extraction.extractor import (
    extract_json_content,
    normalize_label,
    target_columns_for,
)
from models.base import BaseAdapter
from output.results_writer import ResultsWriter
from prompts.registry import PromptConfig
from tasks.staged import run_staged_procedures


def load_notes_df(data_xlsx: str | Path) -> pd.DataFrame:
    """Load the adjudicated notes workbook (one row per note)."""
    return pd.read_excel(data_xlsx).reset_index(drop=True)


def run_grading_loop(
    *,
    adapter: BaseAdapter,
    task: PromptConfig,
    ctx: RunContext,
    grading_df: pd.DataFrame,
) -> None:
    """Iterate notes, call staged procedures, score matches, and persist artifacts."""
    writer = ResultsWriter(ctx)
    scores: list = []
    max_count = 0
    prompt_count = 0
    acc = 0.0
    token_drought_acc = 1.0
    prompt_drought_acc = 1.0
    verbose = True

    target_od_col, target_os_col = target_columns_for(ctx.cvar)

    # Per-eye AI label columns, placed right after the ground-truth columns
    label_od_col = f"{ctx.model_alias}_label_OD"
    label_os_col = f"{ctx.model_alias}_label_OS"
    insert_pos = grading_df.columns.get_loc(target_os_col) + 1
    grading_df.insert(insert_pos, label_od_col, pd.NA)
    grading_df.insert(insert_pos + 1, label_os_col, pd.NA)

    for idx, (note, contact_date) in enumerate(
        tqdm(
            zip(grading_df["Combined_NOTE_TEXT"], grading_df["ENC_CONTACT_DATE"]),
            desc="Processing Notes",
            total=len(grading_df),
        )
    ):
        note_changed = (
            f"The encounter date corresponding to this note is: {contact_date}:\n {note}"
        )
        print(f"\nProcessing note {idx + 1}/{len(grading_df)}")

        try:
            final_results = run_staged_procedures(
                adapter,
                task,
                ctx,
                note=note_changed,
                idx=idx,
                verbose=verbose,
                max_count=max_count,
                prompt_count=prompt_count,
            )
            ai_diag = final_results["ai_diag"]
            ai_overview = final_results["ai_overview"]
            ai_reasoning = final_results["ai_reasoning"]
            max_count = final_results["max_count"]
            prompt_count = final_results["prompt_count"]

        except ServerFailureError as e:
            print(f"Server failure on note {idx + 1}: {e}")
            writer.log_server_failure(idx, e)
            continue
        except Exception as e:
            print(f"Error processing note {idx + 1}: {e}")
            writer.log_error(idx, e)
            grading_df.loc[idx, "AI_Diagnosis"] = "None (failed)"
            grading_df.loc[idx, "AI_Explanation"] = "None (failed)"
            grading_df.loc[idx, "AI_Reasoning"] = "None (failed)"
            continue

        grading_df.loc[idx, "AI_Diagnosis"] = ai_diag
        grading_df.loc[idx, "AI_Explanation"] = ai_overview
        grading_df.loc[idx, "AI_Reasoning"] = ai_reasoning

        extracted, _ = extract_json_content(ai_diag, ctx.cvar)
        grading_df.loc[idx, label_od_col] = extracted.get("OD")
        grading_df.loc[idx, label_os_col] = extracted.get("OS")

        writer.write_grading_csv(grading_df, ctx.cvar)
        writer.write_max_count_tracker(ctx.cvar, ctx.global_max_count)

        target_od = grading_df.loc[idx, target_od_col]
        target_os = grading_df.loc[idx, target_os_col]
        target_od = "None" if pd.isna(target_od) or target_od == "No" else target_od
        target_os = "None" if pd.isna(target_os) or target_os == "No" else target_os
        print(f"Target OD: {target_od}, Target OS: {target_os}")

        match_od = int(normalize_label(extracted.get("OD")) == normalize_label(target_od))
        match_os = int(normalize_label(extracted.get("OS")) == normalize_label(target_os))
        scores.append([match_od, match_os])
        acc = (sum(s[0] for s in scores) + sum(s[1] for s in scores)) / (len(scores) * 2)

        token_drought_acc = 1 - (max_count / (idx + 1))
        prompt_drought_acc = 1 - (prompt_count / (idx + 1))
        print(
            f"acc: {acc:.2f}, token_drought_acc: {token_drought_acc:.2f}, "
            f"prompt_drought_acc: {prompt_drought_acc:.2f}"
        )
        print(extracted)
        print("-" * 80)

    final_path = writer.write_final_csv(grading_df, ctx.cvar)
    writer.write_stats(
        cvar=ctx.cvar,
        target_columns=task.target_columns,
        bilateral=task.bilateral,
        acc=acc,
        token_drought_acc=token_drought_acc,
        prompt_drought_acc=prompt_drought_acc,
        max_count=max_count,
    )
    print(f"\nResults saved to {final_path}")
