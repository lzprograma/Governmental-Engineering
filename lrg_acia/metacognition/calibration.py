"""Métricas de calibração e política conservadora de abstenção."""
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class CalibrationReport:
    brier_score: float
    expected_calibration_error: float
    sample_count: int


def calibration_report(probabilities: Sequence[float], outcomes: Sequence[int], bins: int = 10) -> CalibrationReport:
    if len(probabilities) != len(outcomes) or not probabilities:
        raise ValueError("probabilities e outcomes devem ter mesmo tamanho não nulo")
    if bins < 1:
        raise ValueError("bins deve ser positivo")
    if any(not 0 <= p <= 1 for p in probabilities) or any(y not in (0, 1) for y in outcomes):
        raise ValueError("Probabilidades em [0,1] e resultados binários são exigidos")
    brier = sum((p - y) ** 2 for p, y in zip(probabilities, outcomes)) / len(outcomes)
    ece = 0.0
    for index in range(bins):
        low, high = index / bins, (index + 1) / bins
        group = [(p, y) for p, y in zip(probabilities, outcomes)
                 if low <= p < high or (index == bins - 1 and p == 1.0)]
        if group:
            confidence = sum(p for p, _ in group) / len(group)
            accuracy = sum(y for _, y in group) / len(group)
            ece += len(group) / len(outcomes) * abs(confidence - accuracy)
    return CalibrationReport(brier, ece, len(outcomes))


def should_abstain(confidence: float, evidence_count: int, threshold: float = 0.60) -> bool:
    if not 0 <= confidence <= 1 or evidence_count < 0:
        raise ValueError("Entrada inválida")
    return confidence < threshold or evidence_count == 0
