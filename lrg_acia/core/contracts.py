"""Contratos tipados compartilhados pelos motores ACIA."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4
import math


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ResultStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    ABSTAIN = "abstain"
    ERROR = "error"


@dataclass(frozen=True)
class Task:
    prompt: str
    domain: str = "general"
    risk_level: RiskLevel = RiskLevel.LOW
    modalities: tuple[str, ...] = ("text",)
    deadline_seconds: float = 30.0
    cost_budget: float = 1.0
    data_policy: str = "public_or_synthetic"
    required_evidence: bool = False
    task_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.prompt.strip():
            raise ValueError("A tarefa precisa conter um prompt não vazio.")
        if not isinstance(self.risk_level, RiskLevel):
            object.__setattr__(self, "risk_level", RiskLevel(self.risk_level))
        object.__setattr__(self, "modalities", tuple(self.modalities))
        if (not math.isfinite(self.deadline_seconds) or not math.isfinite(self.cost_budget)
                or self.deadline_seconds <= 0 or self.cost_budget < 0):
            raise ValueError("Prazo deve ser finito e positivo; orçamento deve ser finito e não negativo.")


@dataclass(frozen=True)
class Evidence:
    claim: str
    source: str
    method: str
    confidence: float
    observed_at: str = field(default_factory=utc_now)
    excerpt: str | None = None
    source_hash: str | None = None
    dependencies: tuple[str, ...] = ()
    evidence_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence deve ser finita e estar entre 0 e 1.")


@dataclass(frozen=True)
class Event:
    producer: str
    event_type: str
    payload: Mapping[str, Any]
    trace_id: str
    sensitivity: str = "public"
    policy_tags: tuple[str, ...] = ()
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=utc_now)
    schema_version: str = "1.0"


@dataclass(frozen=True)
class ModelArtifact:
    model_id: str
    provider: str
    access_mode: str
    license_name: str = "unknown"
    snapshot: str | None = None
    artifact_hash: str | None = None
    local_path: str | None = None
    modalities: tuple[str, ...] = ("text",)
    authorized_for_weight_analysis: bool = False


@dataclass(frozen=True)
class ModelResponse:
    model_id: str
    text: str
    confidence: float
    cost: float
    latency_ms: float
    evidence: tuple[Evidence, ...] = ()
    status: ResultStatus = ResultStatus.SUCCESS

    def __post_init__(self) -> None:
        if not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError("confidence da resposta deve estar em [0,1]")
        if not math.isfinite(self.cost) or self.cost < 0:
            raise ValueError("cost deve ser finito e não negativo")
        if not math.isfinite(self.latency_ms) or self.latency_ms < 0:
            raise ValueError("latency_ms deve ser finito e não negativo")


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    status: ResultStatus
    answer: str
    selected_models: tuple[str, ...]
    evidence: tuple[Evidence, ...]
    confidence: float
    cost: float
    trace_id: str
    limitations: tuple[str, ...] = ()
    created_at: str = field(default_factory=utc_now)


def to_dict(value: Any) -> dict[str, Any]:
    """Converte dataclasses e enums em estruturas serializáveis."""
    raw = asdict(value)
    for key, item in list(raw.items()):
        if isinstance(item, Enum):
            raw[key] = item.value
    return raw
