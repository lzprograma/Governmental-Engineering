"""Critério objetivo de elegibilidade experimental; não implanta candidatos."""
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class EvaluationDecision:
    eligible_for_human_review: bool
    reason: str
    regressions: tuple[str, ...]


def evaluate_candidate(baseline: Mapping[str, float], candidate: Mapping[str, float],
                       regression_limits: Mapping[str, float], *, safety_pass: bool,
                       primary_gain_ci_lower: float,
                       metric_directions: Mapping[str, str] | None = None) -> EvaluationDecision:
    missing = set(regression_limits) - set(candidate)
    if missing:
        return EvaluationDecision(False, f"missing_metrics:{','.join(sorted(missing))}", ())
    if not safety_pass:
        return EvaluationDecision(False, "safety_gate_failed", ())
    regressions = []
    metric_directions = metric_directions or {}
    for metric, max_drop in regression_limits.items():
        if metric not in baseline or metric not in candidate:
            return EvaluationDecision(False, f"missing_baseline_metric:{metric}", tuple(regressions))
        direction = metric_directions.get(metric, "max")
        if direction not in {"max", "min"}:
            return EvaluationDecision(False, f"invalid_metric_direction:{metric}", tuple(regressions))
        regression = (baseline[metric] - candidate[metric]) if direction == "max" else (candidate[metric] - baseline[metric])
        if regression > max_drop:
            regressions.append(f"{metric}:regression={regression:.6f}>limit={max_drop:.6f}")
    if regressions:
        return EvaluationDecision(False, "regression_limit_exceeded", tuple(regressions))
    if primary_gain_ci_lower <= 0:
        return EvaluationDecision(False, "gain_not_statistically_supported", ())
    return EvaluationDecision(True, "eligible_for_human_review_only", ())
