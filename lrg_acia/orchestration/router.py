"""Orquestrador multimodelo com roteamento por qualidade, especialidade, custo, latência e risco."""
from __future__ import annotations
from uuid import uuid4
from ..core.contracts import Task, TaskResult, ResultStatus
from ..core.config import settings
from ..core.events import make_event
from ..memory_engine.store import MemoryStore
from ..security.policy import Principal, PolicyEngine
from .providers import ModelProvider


class ModelOrchestrator:
    def __init__(self, providers: list[ModelProvider], store: MemoryStore,
                 policy: PolicyEngine | None = None, *, allow_external: bool | None = None) -> None:
        if not providers:
            raise ValueError("Pelo menos um provider deve ser registrado")
        self.providers = providers
        self.store = store
        self.policy = policy or PolicyEngine()
        self.allow_external = settings.allow_external_models if allow_external is None else allow_external

    def _score(self, provider: ModelProvider, task: Task) -> float:
        p = provider.profile
        specialty = 0.15 if task.domain in p.specialties else 0.0
        quality = p.quality_score
        cost_penalty = p.cost_per_task / max(task.cost_budget, 0.01)
        latency_penalty = p.latency_ms / max(task.deadline_seconds * 1000, 1)
        return quality + specialty - 0.10 * cost_penalty - 0.10 * latency_penalty - 0.20 * p.risk_score

    def execute(self, task: Task, principal: Principal) -> TaskResult:
        trace_id = str(uuid4())
        eligible = []
        rejections = []
        for provider in self.providers:
            profile = provider.profile
            if profile.is_external and not self.allow_external:
                rejections.append(f"{profile.model_id}:external_provider_disabled")
                continue
            if not set(task.modalities).issubset(set(profile.modalities)):
                rejections.append(f"{profile.model_id}:unsupported_modality")
                continue
            decision = self.policy.authorize_task(principal, task, external_provider=profile.is_external)
            if not decision.allowed:
                rejections.append(f"{profile.model_id}:{decision.reason}")
                continue
            if profile.cost_per_task > task.cost_budget:
                rejections.append(f"{profile.model_id}:budget_exceeded")
                continue
            eligible.append((self._score(provider, task), provider))
        if not eligible:
            event = make_event("orchestrator", "task_abstained", {"task_id": task.task_id, "rejections": rejections}, trace_id=trace_id)
            self.store.record_event(event)
            return TaskResult(task.task_id, ResultStatus.ABSTAIN,
                              "Tarefa não executada: nenhum modelo passou pelas políticas, modalidade e orçamento.",
                              (), (), 0.0, 0.0, trace_id, tuple(rejections))
        provider = max(eligible, key=lambda item: item[0])[1]
        response = provider.generate(task)
        if response.cost > task.cost_budget:
            status = ResultStatus.ABSTAIN
            answer = "Execução interrompida: custo informado excedeu o orçamento da tarefa."
        elif task.required_evidence and not response.evidence:
            status = ResultStatus.ABSTAIN
            answer = "Abstenção: a tarefa exige evidências e o resultado não trouxe evidência verificável."
        else:
            status = response.status
            answer = response.text
        event = make_event("orchestrator", "task_completed", {
            "task_id": task.task_id, "selected_model": response.model_id,
            "status": status.value, "confidence": response.confidence,
            "cost": response.cost, "limitations": rejections,
        }, trace_id=trace_id, sensitivity="internal")
        # O trace é mantido pelo envelope do resultado e gravado no próprio evento.
        self.store.record_event(event)
        return TaskResult(task.task_id, status, answer, (response.model_id,), response.evidence,
                          response.confidence, response.cost, trace_id, tuple(rejections))
