"""Bilateral (OD/OS) procedure evaluation: one sample per eye, two per note."""

from __future__ import annotations

import numpy as np
import pandas as pd

from evaluation.column_map import NOTE_COL, EvalSpec
from evaluation.extract import (
    count_failed_matches,
    procedures_components_from_parsed,
    procedures_from_parsed,
    split_label_items,
)
from evaluation.metrics import (
    bootstrap_error_metrics,
    bootstrap_jaccard_ci,
    bootstrap_weighted_jaccard_ci,
    count_procedures,
    evaluate_scenario,
    has_procedures,
)


def _banner(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def preprocess(df: pd.DataFrame, spec: EvalSpec) -> pd.DataFrame:
    df = df.copy()
    df["original_index"] = df.index

    missing_rows = (
        (df[spec.target_od].isna() & df[spec.target_parsed_od].isna())
        | (df[spec.target_os].isna() & df[spec.target_parsed_os].isna())
    )
    print(
        f"{missing_rows.sum()} rows have a missing ground-truth label for at least "
        "one eye (kept in the analysis)."
    )

    # NaN standardized text means "no procedures" for that eye.
    for col in [spec.target_od, spec.target_os, spec.pred_od, spec.pred_os]:
        df[col] = df[col].astype(str).str.lower()
        df[col] = df[col].replace({"nan": "no"})

    for col, label in [
        (spec.target_parsed_od, "target OD"), (spec.target_parsed_os, "target OS"),
        (spec.pred_parsed_od, "pred OD"), (spec.pred_parsed_os, "pred OS"),
    ]:
        print(f"failed_match flagged in {label}: {count_failed_matches(df[col])}")
    return df


def _report_counts(title: str, pairs: list[tuple[int, int]], n_label: str) -> None:
    _banner(title)
    if not pairs:
        print("No samples found.")
        return
    true_counts, pred_counts = zip(*pairs)
    print(f"{n_label}: {len(true_counts)}")
    (mae_mean, mae_lower, mae_upper), (mse_mean, mse_lower, mse_upper) = bootstrap_error_metrics(
        list(true_counts), list(pred_counts)
    )
    print(f"MAE: {mae_mean:.3f} (95% CI: {mae_lower:.3f} - {mae_upper:.3f})")
    print(f"MSE: {mse_mean:.3f} (95% CI: {mse_lower:.3f} - {mse_upper:.3f})")
    print(f"True count  (mean +/- std): {np.mean(true_counts):.3f} +/- {np.std(true_counts):.3f}")
    print(f"Pred count  (mean +/- std): {np.mean(pred_counts):.3f} +/- {np.std(pred_counts):.3f}")


def run_procedure_evaluation(df: pd.DataFrame, spec: EvalSpec, *, verbose: bool = False) -> dict:
    """Print the full report for one standardized results frame; return scenario dicts."""
    df = preprocess(df, spec)

    # ── Eye-level samples (two eyes per note) ────────────────────────────────
    all_true_diag, all_pred_diag = [], []
    all_true_procs, all_pred_procs = [], []              # procedure name + date
    all_true_procs_name, all_pred_procs_name = [], []    # procedure name only
    all_true_comps, all_pred_comps = [], []              # structured: name + details + date
    all_true_label_items, all_pred_label_items = [], []  # full standardized label as a multiset
    note_ids, eye_labels = [], []

    for _, row in df.iterrows():
        for eye, target_col, pred_col, target_parsed_col, pred_parsed_col in [
            ("OD", spec.target_od, spec.pred_od, spec.target_parsed_od, spec.pred_parsed_od),
            ("OS", spec.target_os, spec.pred_os, spec.target_parsed_os, spec.pred_parsed_os),
        ]:
            all_true_diag.append(row[target_col])
            all_pred_diag.append(row[pred_col])
            all_true_procs.append(procedures_from_parsed(row[target_parsed_col]))
            all_pred_procs.append(procedures_from_parsed(row[pred_parsed_col]))
            all_true_procs_name.append(procedures_from_parsed(row[target_parsed_col], include_date=False))
            all_pred_procs_name.append(procedures_from_parsed(row[pred_parsed_col], include_date=False))
            all_true_comps.append(procedures_components_from_parsed(row[target_parsed_col]))
            all_pred_comps.append(procedures_components_from_parsed(row[pred_parsed_col]))
            all_true_label_items.append(split_label_items(row[target_col]))
            all_pred_label_items.append(split_label_items(row[pred_col]))
            note_ids.append(row[NOTE_COL])
            eye_labels.append(eye)

    total_samples = len(all_true_diag)
    print(f"Total samples (both eyes combined): {total_samples}")

    if verbose:
        print("\n=== Cases Where Predicted != True (standardized text) ===")
        for nid, eye, t, p in zip(note_ids, eye_labels, all_true_diag, all_pred_diag):
            if t != p:
                print(f"NOTE_ID {nid} ({eye}) | True: {t} | Pred: {p}")

    true_has_proc = [has_procedures(t) for t in all_true_diag]
    positive_indices = [i for i, h in enumerate(true_has_proc) if h]
    negative_indices = [i for i, h in enumerate(true_has_proc) if not h]
    exact_matches = sum(1 for t, p in zip(all_true_diag, all_pred_diag) if t == p)

    _banner("Breakdown:")
    print(f"Total samples (eye-level): {total_samples}")
    print(f"Eyes with {spec.noun} (positive class): {len(positive_indices)}")
    print(f"Eyes without {spec.noun} (negative class): {len(negative_indices)}")
    if positive_indices:
        pos_exact = sum(1 for i in positive_indices if all_true_diag[i] == all_pred_diag[i])
        print(f"Exact matches in positive eyes: {pos_exact}/{len(positive_indices)}")
    if negative_indices:
        neg_exact = sum(1 for i in negative_indices if all_true_diag[i] == all_pred_diag[i])
        print(f"Exact matches in negative eyes: {neg_exact}/{len(negative_indices)}")
    print(f"Total exact matches: {exact_matches}/{total_samples}")

    def pos(values: list) -> list:
        return [values[i] for i in positive_indices]

    # ── Scenario evaluations ─────────────────────────────────────────────────
    results = {
        "overall": evaluate_scenario(all_true_diag, all_pred_diag, "overall"),
        "positives_only": evaluate_scenario(
            pos(all_true_diag), pos(all_pred_diag), "positives_only", compute_specificity=False,
            jaccard_true=pos(all_true_label_items), jaccard_pred=pos(all_pred_label_items),
        ),
        "procedure_name_and_date": evaluate_scenario(
            pos(all_true_procs), pos(all_pred_procs), "procedure_name_and_date",
            compute_specificity=False,
        ),
        "procedure_name": evaluate_scenario(
            pos(all_true_procs_name), pos(all_pred_procs_name), "procedure_name",
            compute_specificity=False,
        ),
    }

    # ── Date-weighted hierarchical Jaccard ───────────────────────────────────
    _banner("DATE-WEIGHTED HIERARCHICAL JACCARD")
    print("Name-gated; details (when included) weighted 1 total (whole set must match),")
    print("date parts (month/day/year) weighted 1/3 each.")
    for label, tl, pl, include_details in [
        ("overall (all eyes; name + details + date)", all_true_comps, all_pred_comps, True),
        ("positives_only (name + details + date)", pos(all_true_comps), pos(all_pred_comps), True),
        ("procedure_name_and_date (name + date)", pos(all_true_comps), pos(all_pred_comps), False),
    ]:
        if not tl:
            print(f"{label} (n=0): No samples found")
            continue
        m, lo, hi = bootstrap_weighted_jaccard_ci(tl, pl, include_details=include_details)
        print(f"{label} (n={len(tl)}): {m:.3f} (95% CI: {lo:.3f} - {hi:.3f})")

    # ── Jaccard by procedure count subgroup ──────────────────────────────────
    _banner("JACCARD INDEX BY PROCEDURE COUNT SUBGROUP")
    subgroups = {
        "Exactly 1 procedure": lambda c: c == 1,
        "Exactly 2 procedures": lambda c: c == 2,
        "Exactly 3 procedures": lambda c: c == 3,
        "4 or more procedures": lambda c: c >= 4,
    }
    for label, condition in subgroups.items():
        filtered = [(t, p) for t, p in zip(all_true_procs, all_pred_procs) if condition(count_procedures(t))]
        if not filtered:
            print(f"{label} (n=0): No samples found")
            continue
        ft, fp = zip(*filtered)
        j_mean, j_lower, j_upper = bootstrap_jaccard_ci(list(ft), list(fp))
        print(f"{label} (n={len(filtered)}): {j_mean:.3f} (95% CI: {j_lower:.3f} - {j_upper:.3f})")

    # ── MAE / MSE for procedure counts ───────────────────────────────────────
    _report_counts(
        f"MSE AND MAE FOR PROCEDURE COUNTS (EYES WITH {spec.noun.upper()})",
        [(count_procedures(t), count_procedures(p))
         for t, p in zip(all_true_procs, all_pred_procs) if has_procedures(t)],
        f"Eyes with {spec.noun}",
    )
    _report_counts(
        "MSE AND MAE FOR OVERALL PROCEDURE COUNTS (ALL EYES)",
        [(count_procedures(t), count_procedures(p)) for t, p in zip(all_true_procs, all_pred_procs)],
        "Overall eyes",
    )

    _banner("ANALYSIS COMPLETE")
    return results
