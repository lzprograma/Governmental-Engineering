"""Ciclo experimental de melhoria. Não executa código candidato nem altera produção."""
from dataclasses import dataclass, field
from uuid import uuid4
from ..evaluation.gates import EvaluationDecision, evaluate_candidate


@dataclass(frozen=True)
class Candidate:
    baseline_hash: str
    candidate_hash: str
    dataset_version: str
    safety_policy_version: str
    change_description: str
    candidate_id: str = field(default_factory=lambda: str(uuid4()))


class LearningExperimentManager:
    def evaluate(self, candidate: Candidate, baseline_metrics: dict[str, float],
                 candidate_metrics: dict[str, float], regression_limits: dict[str, float],
                 *, safety_pass: bool, primary_gain_ci_lower: float,
                 metric_directions: dict[str, str] | None = None) -> EvaluationDecision:
        for name, value in (("baseline_hash", candidate.baseline_hash),
                            ("candidate_hash", candidate.candidate_hash),
                            ("dataset_version", candidate.dataset_version),
                            ("safety_policy_version", candidate.safety_policy_version)):
            if not value.strip():
                raise ValueError(f"{name} é obrigatório")
        if candidate.baseline_hash == candidate.candidate_hash:
            return EvaluationDecision(False, "candidate_identical_to_baseline", ())
        return evaluate_candidate(baseline_metrics, candidate_metrics, regression_limits,
                                  safety_pass=safety_pass, primary_gain_ci_lower=primary_gain_ci_lower,
                                  metric_directions=metric_directions)

    @staticmethod
    def promotion_is_authorized(candidate: Candidate, decision: EvaluationDecision, approval: object | None) -> bool:
        """O candidato elegível exige aprovação humana do mesmo ID; não realiza implantação."""
        return bool(decision.eligible_for_human_review and approval is not None
                    and getattr(approval, "candidate_id", None) == candidate.candidate_id
                    and getattr(approval, "decision", None) == "approved")
