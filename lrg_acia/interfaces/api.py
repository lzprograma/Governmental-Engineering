"""API HTTP opcional. Execute somente em loopback no protótipo local."""
from __future__ import annotations
from typing import Literal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from ..core.contracts import Task, RiskLevel
from ..service import ACIAService
from ..core.config import settings


class TaskPayload(BaseModel):
    prompt: str = Field(min_length=1, max_length=settings.max_task_chars)
    domain: str = "general"
    risk_level: Literal["low", "medium", "high", "critical"] = "low"
    modalities: list[str] = ["text"]
    deadline_seconds: float = Field(default=30.0, gt=0, le=3600)
    cost_budget: float = Field(default=1.0, ge=0)
    data_policy: str = "public_or_synthetic"
    required_evidence: bool = False


service = ACIAService()
app = FastAPI(title="LUNZ SOVEREIGN / ACIA", version="0.3.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "nation": settings.nation_name, "mode": "local_prototype"}


@app.get("/dashboard")
def dashboard() -> dict:
    return service.dashboard()


@app.post("/tasks")
def create_task(payload: TaskPayload) -> dict:
    try:
        task = Task(
            prompt=payload.prompt, domain=payload.domain,
            risk_level=RiskLevel(payload.risk_level), modalities=tuple(payload.modalities),
            deadline_seconds=payload.deadline_seconds, cost_budget=payload.cost_budget,
            data_policy=payload.data_policy, required_evidence=payload.required_evidence,
        )
        result = service.execute_task(task)
        return {
            "task_id": result.task_id, "status": result.status.value,
            "answer": result.answer, "selected_models": list(result.selected_models),
            "confidence": result.confidence, "cost": result.cost,
            "trace_id": result.trace_id, "limitations": list(result.limitations),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
