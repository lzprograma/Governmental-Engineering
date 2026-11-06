"""Gates humanos para mudanças experimentais e promoção."""
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone


class Gate(str, Enum):
    G0 = "G0_synthetic_public"
    G1 = "G1_internal_non_sensitive"
    G2 = "G2_authorized_institutional_data"
    G3 = "G3_low_risk_pilot"
    G4 = "G4_expanded_deployment"


@dataclass(frozen=True)
class Approval:
    candidate_id: str
    approver_id: str
    role: str
    gate: Gate
    decision: str
    rationale: str
    timestamp: str


class ApprovalRegistry:
    def __init__(self) -> None:
        self._approvals: dict[str, Approval] = {}

    def approve(self, candidate_id: str, approver_id: str, role: str, gate: Gate, rationale: str) -> Approval:
        if not all(x.strip() for x in (candidate_id, approver_id, role, rationale)):
            raise ValueError("A aprovação exige candidato, aprovador, função e justificativa.")
        approval = Approval(candidate_id, approver_id, role, gate, "approved",
                            rationale, datetime.now(timezone.utc).isoformat())
        self._approvals[candidate_id] = approval
        return approval

    def get(self, candidate_id: str) -> Approval | None:
        return self._approvals.get(candidate_id)
