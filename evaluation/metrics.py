"""Agreement metrics for eye-level procedure labels.

Exact match, presence/absence accuracy, F1, multiset Jaccard, Gwet AC1, count
errors, and the date-weighted hierarchical Jaccard. Confidence intervals are
Wilson (proportions) or bootstrap (everything else).
"""

from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache

import numpy as np
import pandas as pd
from scipy import stats

from evaluation.extract import NEGATIVE


def wilson_confidence_interval(successes, trials, alpha=0.05):
    """Wilson confidence interval for proportions."""
    if trials == 0:
        return 0, 0, 0
    z = stats.norm.ppf(1 - alpha / 2)
    p = successes / trials
    denominator = 1 + z**2 / trials
    center = (p + z**2 / (2 * trials)) / denominator
    margin = z * np.sqrt((p * (1 - p) + z**2 / (4 * trials)) / trials) / denominator
    return p, max(0, center - margin), min(1, center + margin)


def jaccard_index(list1, list2):
    """Multiset Jaccard index between two lists, keeping duplicates.

    Uses multiset (bag) semantics so repeated procedures are not collapsed: an
    item appearing twice in one list and once in the other contributes 1 to the
    intersection and 2 to the union (giving 0.5, not 1.0). This matters because
    the standardizer deliberately keeps duplicates (e.g. "SLT x2" -> two tokens),
    so a single predicted SLT should not fully match two true SLTs. Two empty
    inputs score 1.0.

    Note: a non-list argument (e.g. a whole label string) is treated as a single
    element, which collapses this to an exact-equality indicator. Pass token
    lists for a genuine multiset overlap.
    """
    counts1 = Counter(list1) if isinstance(list1, list) else Counter([list1])
    counts2 = Counter(list2) if isinstance(list2, list) else Counter([list2])
    if not counts1 and not counts2:
        return 1.0
    intersection = sum((counts1 & counts2).values())
    union = sum((counts1 | counts2).values())
    return intersection / union if union > 0 else 0


def bootstrap_jaccard_ci(true_lists, pred_lists, n_bootstrap=1000, alpha=0.05):
    """Bootstrap confidence interval for mean Jaccard index."""
    n = len(true_lists)
    scores = []
    for _ in range(n_bootstrap):
        idx = np.random.choice(n, size=n, replace=True)
        scores.append(np.mean([jaccard_index(true_lists[i], pred_lists[i]) for i in idx]))
    scores = np.array(scores)
    return np.mean(scores), np.percentile(scores, (alpha / 2) * 100), np.percentile(scores, (1 - alpha / 2) * 100)


def has_procedures(val):
    """True if val contains at least one real procedure (not the NEGATIVE sentinel)."""
    if isinstance(val, list):
        return not (len(val) == 0 or all(v == NEGATIVE for v in val))
    return val != NEGATIVE and not pd.isna(val)


def count_procedures(val):
    """Count real (non-NEGATIVE) procedures."""
    if not isinstance(val, list):
        return 0 if val == NEGATIVE or pd.isna(val) else 1
    return sum(1 for v in val if v != NEGATIVE)


def bootstrap_f1_ci(all_true, all_pred, n_bootstrap=1000, alpha=0.05):
    """Bootstrap confidence interval for F1 score (presence/absence of a procedure)."""
    n = len(all_true)
    f1_scores = []
    for _ in range(n_bootstrap):
        idx = np.random.choice(n, size=n, replace=True)
        bt = [all_true[i] for i in idx]
        bp = [all_pred[i] for i in idx]
        tp = sum(1 for t, p in zip(bt, bp) if has_procedures(t) and has_procedures(p))
        fp = sum(1 for t, p in zip(bt, bp) if not has_procedures(t) and has_procedures(p))
        fn = sum(1 for t, p in zip(bt, bp) if has_procedures(t) and not has_procedures(p))
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec  = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1_scores.append(2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0)
    f1_scores = np.array(f1_scores)
    return np.mean(f1_scores), np.percentile(f1_scores, (alpha / 2) * 100), np.percentile(f1_scores, (1 - alpha / 2) * 100)


def bootstrap_error_metrics(true_counts, pred_counts, n_bootstrap=1000, alpha=0.05):
    """Bootstrap confidence intervals for MAE and MSE."""
    n = len(true_counts)
    mae_scores, mse_scores = [], []
    for _ in range(n_bootstrap):
        idx = np.random.choice(n, size=n, replace=True)
        rt = np.array([true_counts[i] for i in idx])
        rp = np.array([pred_counts[i] for i in idx])
        mae_scores.append(np.mean(np.abs(rp - rt)))
        mse_scores.append(np.mean((rp - rt) ** 2))
    def ci(arr): return np.mean(arr), np.percentile(arr, 2.5), np.percentile(arr, 97.5)
    return ci(np.array(mae_scores)), ci(np.array(mse_scores))


def gwet_ac1(rater1, rater2):
    """Gwet's AC1 agreement coefficient."""
    r1 = [tuple(x) if isinstance(x, list) else x for x in rater1]
    r2 = [tuple(x) if isinstance(x, list) else x for x in rater2]

    n = len(r1)
    if n == 0:
        return 0

    Po = sum(a == b for a, b in zip(r1, r2)) / n

    categories = set(r1) | set(r2)
    q = len(categories)

    if q <= 1:
        return 1.0

    c1 = Counter(r1)
    c2 = Counter(r2)

    Pe = sum(
        ((c1[k] / n + c2[k] / n) / 2) * (1 - (c1[k] / n + c2[k] / n) / 2)
        for k in categories
    ) / (q - 1)

    if Pe >= 1:
        return 1.0

    return (Po - Pe) / (1 - Pe)


def gwet_ac1_bootstrap(rater1, rater2, n_iter=1000, alpha=0.05, random_state=None):
    if random_state is not None:
        np.random.seed(random_state)
    n = len(rater1)
    if n == 0:
        return 0, 0
    ac1_samples = []
    for _ in range(n_iter):
        idx = np.random.choice(n, n, replace=True)
        sampled_rater1 = [rater1[i] for i in idx]
        sampled_rater2 = [rater2[i] for i in idx]
        ac1_samples.append(gwet_ac1(sampled_rater1, sampled_rater2))
    lower = np.percentile(ac1_samples, 100 * alpha / 2)
    upper = np.percentile(ac1_samples, 100 * (1 - alpha / 2))
    return lower, upper


def evaluate_scenario(all_true, all_pred, scenario_name, n_bootstrap=1000, alpha=0.05, compute_specificity=True,
                      jaccard_true=None, jaccard_pred=None):
    """Compute and print all metrics for a given scenario.

    jaccard_true / jaccard_pred (optional): per-eye token lists used for the
    Jaccard index instead of all_true / all_pred. Pass these when the primary
    inputs are whole label strings (e.g. positives_only) so the Jaccard is a real
    multiset overlap of the procedures rather than exact string equality. They
    must align 1:1 with all_true / all_pred.
    """
    true_pos_mask = [has_procedures(t) for t in all_true]
    pred_pos_mask = [has_procedures(p) for p in all_pred]

    TP = sum(1 for t, p in zip(true_pos_mask, pred_pos_mask) if t and p)
    FP = sum(1 for t, p in zip(true_pos_mask, pred_pos_mask) if not t and p)
    TN = sum(1 for t, p in zip(true_pos_mask, pred_pos_mask) if not t and not p)
    FN = sum(1 for t, p in zip(true_pos_mask, pred_pos_mask) if t and not p)
    N  = len(all_true)

    pos_idx = [i for i, t in enumerate(true_pos_mask) if t]
    neg_idx = [i for i, t in enumerate(true_pos_mask) if not t]

    exact_matches = sum(1 for t, p in zip(all_true, all_pred) if t == p)
    em_accuracy = wilson_confidence_interval(exact_matches, N, alpha)
    em_sens = wilson_confidence_interval(sum(1 for i in pos_idx if all_true[i] == all_pred[i]), len(pos_idx), alpha) if pos_idx else (None, None, None)
    em_spec = wilson_confidence_interval(sum(1 for i in neg_idx if all_true[i] == all_pred[i]), len(neg_idx), alpha) if neg_idx and compute_specificity else (None, None, None)
    accuracy    = wilson_confidence_interval(TP + TN, N, alpha)
    sensitivity = wilson_confidence_interval(TP, TP + FN, alpha) if (TP + FN) > 0 else (None, None, None)
    specificity = wilson_confidence_interval(TN, TN + FP, alpha) if (TN + FP) > 0 and compute_specificity else (None, None, None)
    precision   = wilson_confidence_interval(TP, TP + FP, alpha) if (TP + FP) > 0 else (None, None, None)
    recall      = wilson_confidence_interval(TP, TP + FN, alpha) if (TP + FN) > 0 else (None, None, None)
    f1          = bootstrap_f1_ci(all_true, all_pred, n_bootstrap, alpha)

    # Jaccard on token lists when supplied (real multiset overlap), else on the
    # primary inputs. Passing whole strings collapses Jaccard to exact match.
    jt = jaccard_true if jaccard_true is not None else all_true
    jp = jaccard_pred if jaccard_pred is not None else all_pred
    jaccard     = bootstrap_jaccard_ci(jt, jp, n_bootstrap, alpha)

    ac1 = gwet_ac1(all_true, all_pred)
    ac1_lower, ac1_upper = gwet_ac1_bootstrap(all_true, all_pred, n_iter=n_bootstrap, alpha=alpha)

    def fmt(triple):
        v, lo, hi = triple
        return "undefined" if v is None else f"{v:.3f} (95% CI: {lo:.3f} - {hi:.3f})"

    print("\n" + "=" * 60)
    print(f"SCENARIO: {scenario_name.upper()}")
    print("=" * 60)
    print(f"Total samples:    {N}  |  Positives: {len(pos_idx)}  |  Negatives: {len(neg_idx)}")
    print(f"TP={TP}  FP={FP}  TN={TN}  FN={FN}")
    print(f"\nEM Accuracy:      {fmt(em_accuracy)}")
    print(f"EM Sensitivity:   {fmt(em_sens)}")
    print(f"EM Specificity:   {fmt(em_spec)}")
    print(f"Accuracy:         {fmt(accuracy)}")
    print(f"Sensitivity:      {fmt(sensitivity)}")
    print(f"Specificity:      {fmt(specificity)}")
    print(f"Precision:        {fmt(precision)}")
    print(f"Recall:           {fmt(recall)}")
    print(f"F1 Score:         {fmt(f1)}")
    print(f"Jaccard Index:    {fmt(jaccard)}")
    print(f"Gwet AC1 Score:   {ac1:.3f} (95% CI: {ac1_lower:.3f} - {ac1_upper:.3f})")

    return dict(
        scenario=scenario_name, N=N, TP=TP, FP=FP, TN=TN, FN=FN,
        em_accuracy=em_accuracy, em_sensitivity=em_sens, em_specificity=em_spec, accuracy=accuracy,
        sensitivity=sensitivity, specificity=specificity,
        precision=precision, recall=recall, f1=f1, jaccard=jaccard, ac1=ac1,
        ac1_ci=(ac1_lower, ac1_upper)
    )


# =============================================================================
# DATE-WEIGHTED HIERARCHICAL JACCARD
# =============================================================================
# Operates on the structured records from procedures_components_from_parsed.
# Components scored: procedure name (weight 1), optionally details (weight 1
# total, matched all-or-nothing on the whole detail set), and month / day / year
# (weight 1/3 each). Procedure name is a gate -- details and date parts earn
# credit only when the two procedure names match. include_details toggles the
# detail component so the same machinery yields both the with-details and the
# name+date-only variants.

DATE_COMPONENT_WEIGHT = 1 / 3



def parse_date_parts(date_text):
    """Split one date string into MONTH / DAY / YEAR component labels."""
    date_text = re.sub(r"^~\s*", "", str(date_text).strip().lower())

    full_date = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", date_text)
    if full_date:
        month, day, year = full_date.groups()
        return {f"MONTH:{int(month)}", f"DAY:{int(day)}", f"YEAR:{year}"}

    month_year = re.fullmatch(r"(\d{1,2})/(\d{4})", date_text)
    if month_year:
        month, year = month_year.groups()
        return {f"MONTH:{int(month)}", f"YEAR:{year}"}

    month_day = re.fullmatch(r"(\d{1,2})/(\d{1,2})", date_text)
    if month_day:
        month, day = month_day.groups()
        return {f"MONTH:{int(month)}", f"DAY:{int(day)}"}

    if re.fullmatch(r"\d{4}", date_text):
        return {f"YEAR:{date_text}"}

    if re.fullmatch(r"\d{4}s", date_text):
        return {f"YEAR:{date_text}"}

    return set()


def parse_date_weighted_components(proc, include_details=True):
    """
    Weighted components for one structured procedure record
    {'name', 'details', 'date'}.

    Weights: procedure name = 1, details = 1 total, month/day/year = 1/3 each.

    Details are treated as a single all-or-nothing component: the whole detail
    set is encoded into one DETAILS key, so it counts as matching only when both
    procedures carry the exact same set of details (weight 1 total, not 1 per
    detail). A procedure with no details contributes no DETAILS component.
    include_details=False drops the detail component entirely (name + date only).
    """
    name = proc["name"]
    weighted_components = {f"NAME:{name}": 1.0}

    if include_details and proc["details"]:
        detail_key = ",".join(sorted(proc["details"]))
        weighted_components[f"DETAILS:{detail_key}"] = 1.0

    if proc["date"]:
        for date_part in parse_date_parts(proc["date"]):
            weighted_components[date_part] = DATE_COMPONENT_WEIGHT

    return name, weighted_components


def weighted_component_jaccard(true_components, pred_components):
    """
    Weighted Jaccard between two component -> weight dicts.

    Intersection uses min(weight), union uses max(weight) per component.
    """
    component_keys = set(true_components) | set(pred_components)
    if not component_keys:
        return 1.0

    intersection_weight = sum(
        min(true_components.get(c, 0.0), pred_components.get(c, 0.0))
        for c in component_keys
    )
    union_weight = sum(
        max(true_components.get(c, 0.0), pred_components.get(c, 0.0))
        for c in component_keys
    )
    return intersection_weight / union_weight


def matched_date_weighted_jaccard(true_proc, pred_proc, include_details=True):
    """
    Date-weighted component Jaccard for one procedure pair.

    Procedure name is a gate: details and date components earn credit only when
    the two procedure names match; otherwise the pair scores 0.
    """
    true_name, true_components = parse_date_weighted_components(true_proc, include_details)
    pred_name, pred_components = parse_date_weighted_components(pred_proc, include_details)

    if true_name != pred_name:
        return 0.0

    return weighted_component_jaccard(true_components, pred_components)


def date_weighted_hierarchical_jaccard(true_procs, pred_procs, include_details=True):
    """
    Eye-level date-weighted hierarchical Jaccard over structured procedure records.

    Procedures are matched one-to-one by the assignment that maximises total
    weighted-component similarity; procedure names must match before details or
    date parts receive credit. Missing and extra procedures contribute zero.
    Two eyes with no procedures score 1.0; one empty and one not scores 0.0.
    include_details toggles the detail component (see parse_date_weighted_components).
    """
    true_procs = list(true_procs)
    pred_procs = list(pred_procs)

    if not true_procs and not pred_procs:
        return 1.0
    if not true_procs or not pred_procs:
        return 0.0

    # Keep the smaller collection on the bitmask side.
    if len(true_procs) >= len(pred_procs):
        left, right = true_procs, pred_procs
    else:
        left, right = pred_procs, true_procs

    similarity_matrix = tuple(
        tuple(matched_date_weighted_jaccard(left_item, right_item, include_details) for right_item in right)
        for left_item in left
    )

    @lru_cache(maxsize=None)
    def maximize_similarity(left_index, used_right_mask):
        if left_index == len(left):
            return 0.0
        best = maximize_similarity(left_index + 1, used_right_mask)
        for right_index in range(len(right)):
            bit = 1 << right_index
            if used_right_mask & bit:
                continue
            candidate = (
                similarity_matrix[left_index][right_index]
                + maximize_similarity(left_index + 1, used_right_mask | bit)
            )
            best = max(best, candidate)
        return best

    total_similarity = maximize_similarity(0, 0)
    soft_union = len(true_procs) + len(pred_procs) - total_similarity
    return total_similarity / soft_union if soft_union > 0 else 1.0


def bootstrap_weighted_jaccard_ci(true_lists, pred_lists, include_details=True, n_bootstrap=1000, alpha=0.05):
    """Bootstrap confidence interval for mean date-weighted hierarchical Jaccard."""
    n = len(true_lists)
    scores = []
    for _ in range(n_bootstrap):
        idx = np.random.choice(n, size=n, replace=True)
        scores.append(np.mean([
            date_weighted_hierarchical_jaccard(true_lists[i], pred_lists[i], include_details)
            for i in idx
        ]))
    scores = np.array(scores)
    return np.mean(scores), np.percentile(scores, (alpha / 2) * 100), np.percentile(scores, (1 - alpha / 2) * 100)
