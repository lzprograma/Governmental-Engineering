"""Interfaces de modelos. O provider incluído é um baseline local determinístico."""
from __future__ import annotations
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol
from ..core.contracts import ModelResponse, ResultStatus, Task


@dataclass(frozen=True)
class ProviderProfile:
    model_id: str
    specialties: tuple[str, ...]
    quality_score: float
    cost_per_task: float
    latency_ms: float
    risk_score: float
    is_external: bool = False
    modalities: tuple[str, ...] = ("text",)


class ModelProvider(Protocol):
    profile: ProviderProfile
    def generate(self, task: Task) -> ModelResponse: ...


class LocalDemonstrationProvider:
    """Não é um LLM: baseline determinístico para exercitar contratos e avaliação."""
    def __init__(self) -> None:
        self.profile = ProviderProfile(
            model_id="lrg-local-demonstrator-v0", specialties=("general", "research", "engineering"),
            quality_score=0.50, cost_per_task=0.0, latency_ms=1.0, risk_score=0.01,
            is_external=False, modalities=("text",))

    def generate(self, task: Task) -> ModelResponse:
        started = perf_counter()
        answer = (
            "ACIA recebeu a tarefa em modo de demonstração local.\n\n"
            f"Domínio: {task.domain}\n"
            f"Risco declarado: {task.risk_level.value}\n"
            f"Objetivo recebido: {task.prompt.strip()}\n\n"
            "Próxima etapa: decompor o objetivo em hipóteses verificáveis, identificar evidências "
            "necessárias e executar verificadores independentes. Este baseline não consulta a internet, "
            "não chama modelos externos e não afirma ter resolvido o problema."
        )
        elapsed = (perf_counter() - started) * 1000
        return ModelResponse(self.profile.model_id, answer, 0.55, 0.0, max(elapsed, 0.01), (), ResultStatus.PARTIAL)
