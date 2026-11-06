"""Modelo de transição de estado com incerteza explicitamente fornecida."""
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class TransitionResult:
    next_state: dict[str, float]
    assumptions: tuple[str, ...]
    model_id: str


class LinearWorldModel:
    def __init__(self, coefficients: Mapping[str, float], model_id: str = "linear-world-model-v0") -> None:
        if any(not isinstance(v, (int, float)) for v in coefficients.values()):
            raise ValueError("Coeficientes devem ser numéricos")
        self.coefficients = dict(coefficients)
        self.model_id = model_id

    def transition(self, state: Mapping[str, float], action: Mapping[str, float],
                   disturbance: Mapping[str, float] | None = None) -> TransitionResult:
        disturbance = disturbance or {}
        keys = set(state) | set(action) | set(disturbance) | set(self.coefficients)
        next_state = {}
        for key in keys:
            base = float(state.get(key, 0.0))
            act = float(action.get(key, 0.0))
            noise = float(disturbance.get(key, 0.0))
            gain = float(self.coefficients.get(key, 1.0))
            next_state[key] = base + gain * act + noise
        return TransitionResult(next_state, ("linear transition assumption", "disturbance supplied by caller"), self.model_id)
