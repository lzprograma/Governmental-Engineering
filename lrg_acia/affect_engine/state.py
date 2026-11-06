"""Estados instrumentais de trabalho; não representam sentimentos subjetivos."""
from dataclasses import dataclass


def _clip(value: float) -> float:
    return min(1.0, max(0.0, value))


@dataclass(frozen=True)
class AffectState:
    curiosity: float = 0.25
    uncertainty: float = 0.50
    urgency: float = 0.10
    friction: float = 0.10
    progress: float = 0.0

    def __post_init__(self) -> None:
        if any(not 0 <= x <= 1 for x in self.as_tuple()):
            raise ValueError("Todos os estados devem estar em [0,1].")

    def as_tuple(self) -> tuple[float, ...]:
        return (self.curiosity, self.uncertainty, self.urgency, self.friction, self.progress)


@dataclass(frozen=True)
class AffectObservation:
    curiosity_target: float
    uncertainty_target: float
    urgency_target: float
    friction_target: float
    progress_target: float


class AffectEngine:
    def __init__(self, persistence: float = 0.8, decay: float = 0.02) -> None:
        if not 0 <= persistence <= 1 or not 0 <= decay <= 1:
            raise ValueError("persistence e decay devem estar em [0,1]")
        self.persistence = persistence
        self.decay = decay

    def update(self, state: AffectState, observation: AffectObservation) -> AffectState:
        values = []
        targets = (observation.curiosity_target, observation.uncertainty_target,
                   observation.urgency_target, observation.friction_target, observation.progress_target)
        for old, target in zip(state.as_tuple(), targets):
            if not 0 <= target <= 1:
                raise ValueError("Observações devem estar em [0,1]")
            new = self.persistence * old + (1 - self.persistence) * target - self.decay * old
            values.append(_clip(new))
        return AffectState(*values)

    def recommended_action(self, state: AffectState) -> str:
        if state.uncertainty > 0.75:
            return "request_independent_verifier"
        if state.friction > 0.70:
            return "reformulate_strategy"
        if state.curiosity > 0.65 and state.urgency < 0.50:
            return "run_small_experiment"
        return "continue_with_current_plan"
