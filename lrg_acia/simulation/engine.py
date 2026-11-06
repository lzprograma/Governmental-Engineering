"""Execução determinística de simulações registráveis."""
from dataclasses import dataclass
from hashlib import sha256
import json
import random
from typing import Callable, Any


@dataclass(frozen=True)
class SimulationRun:
    model_id: str
    seed: int
    horizon: int
    assumptions: tuple[str, ...]
    outputs: tuple[dict[str, Any], ...]
    run_hash: str


class SimulationEngine:
    def run(self, model_id: str, initial_state: dict[str, float], horizon: int, seed: int,
            transition: Callable[[dict[str, float], random.Random], dict[str, float]],
            assumptions: tuple[str, ...] = ()) -> SimulationRun:
        if horizon < 1 or horizon > 100_000:
            raise ValueError("horizon deve estar entre 1 e 100000")
        rng = random.Random(seed)
        state = dict(initial_state)
        outputs = [dict(state)]
        for _ in range(horizon):
            state = transition(dict(state), rng)
            if not all(isinstance(v, (int, float)) for v in state.values()):
                raise TypeError("O estado simulado deve conter somente valores numéricos")
            outputs.append(dict(state))
        raw = json.dumps({"model_id": model_id, "seed": seed, "outputs": outputs}, sort_keys=True).encode()
        return SimulationRun(model_id, seed, horizon, assumptions, tuple(outputs), sha256(raw).hexdigest())
