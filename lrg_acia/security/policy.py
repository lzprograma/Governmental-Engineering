"""Autorização mínima. A camada cognitiva não administra IAM nem controles de segurança."""
from dataclasses import dataclass
from enum import Enum
from ..core.contracts import RiskLevel, Task


class Permission(str, Enum):
    TASK_READ = "task:read"
    TASK_EXECUTE = "task:execute"
    MEMORY_READ = "memory:read"
    MEMORY_WRITE = "memory:write"
    RELATION_PROPOSE = "relation:propose"
    WEIGHT_INSPECT = "weight:inspect"
    EXPERIMENT_SUBMIT = "experiment:submit"
    PROMOTE_CANDIDATE = "candidate:promote"


@dataclass(frozen=True)
class Principal:
    principal_id: str
    roles: tuple[str, ...]
    permissions: frozenset[Permission]


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str


class PolicyEngine:
    """Política fail-closed para o protótipo."""

    def authorize_task(self, principal: Principal, task: Task, *, external_provider: bool = False) -> AuthorizationDecision:
        if Permission.TASK_EXECUTE not in principal.permissions:
            return AuthorizationDecision(False, "missing_task_execute_permission")
        if task.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            return AuthorizationDecision(False, "high_impact_tasks_require_separate_human_authorization")
        if task.data_policy not in {"public_or_synthetic", "internal_non_sensitive"}:
            return AuthorizationDecision(False, "data_policy_not_approved_for_prototype")
        if external_provider and task.data_policy != "public_or_synthetic":
            return AuthorizationDecision(False, "external_provider_blocked_for_non_public_data")
        return AuthorizationDecision(True, "authorized_within_prototype_scope")
