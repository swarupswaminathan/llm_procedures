"""Evaluate standardized procedure results against adjudicated labels.

Modules:
  column_map — cvar resolution and standardized column names
  extract    — pull procedure tokens/components from ``parsed_items`` JSON
  metrics    — agreement metrics (EM, F1, Jaccard, Gwet AC1, date-weighted Jaccard)
  procedures — bilateral OD/OS evaluation report
  runner     — CLI orchestration and report tee
"""

from evaluation.runner import run_evaluation

__all__ = ["run_evaluation"]
