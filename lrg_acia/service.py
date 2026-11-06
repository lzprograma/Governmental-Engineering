"""Composição dos serviços ACIA para CLI, API e testes."""
from pathlib import Path
from .core.config import settings, Settings
from .core.contracts import Task
from .memory_engine.store import MemoryStore
from .orchestration.providers import LocalDemonstrationProvider
from .orchestration.router import ModelOrchestrator
from .security.policy import Principal, Permission, PolicyEngine
from .relational_engine.ragi import RAGIEngine
from .affect_engine.state import AffectEngine, AffectState
from .reasoning_engine.selector import ReasoningEngine
from .simulation.engine import SimulationEngine
from .learning.candidates import LearningExperimentManager
from .weight_intelligence.safetensors_inspector import WeightIntelligenceEngine
from .metacognition.calibration import calibration_report, should_abstain
from .governance.approvals import ApprovalRegistry


class ACIAService:
    def __init__(self, config: Settings = settings) -> None:
        config.ensure_directories()
        self.config = config
        self.store = MemoryStore(config.database_path)
        self.policy = PolicyEngine()
        self.principal = Principal(
            principal_id="local-research-operator",
            roles=("researcher",),
            permissions=frozenset({
                Permission.TASK_READ, Permission.TASK_EXECUTE,
                Permission.MEMORY_READ, Permission.MEMORY_WRITE,
                Permission.RELATION_PROPOSE, Permission.WEIGHT_INSPECT,
                Permission.EXPERIMENT_SUBMIT,
            }),
        )
        self.orchestrator = ModelOrchestrator(
            [LocalDemonstrationProvider()], self.store, self.policy,
            allow_external=config.allow_external_models,
        )
        self.ragi = RAGIEngine(self.store, transitive_types={"is_ancestor_of"},
                               incompatible_pairs={("is_employed_by", "is_not_employed_by")})
        self.affect = AffectEngine()
        self.affect_state = AffectState()
        self.reasoning = ReasoningEngine()
        self.simulation = SimulationEngine()
        self.learning = LearningExperimentManager()
        self.wie = WeightIntelligenceEngine()
        self.calibration_report = calibration_report
        self.should_abstain = should_abstain
        self.approvals = ApprovalRegistry()

    def execute_task(self, task: Task):
        reasoning_plan = self.reasoning.select(task.prompt, task.domain)
        result = self.orchestrator.execute(task, self.principal)
        self.store.add_memory(
            memory_id=f"task:{task.task_id}", memory_type="episodic",
            content=f"Pergunta: {task.prompt}\nResultado: {result.answer}",
            source="orchestrator", confidence=result.confidence,
            metadata={"task_id": task.task_id, "status": result.status.value,
                      "selected_models": list(result.selected_models), "trace_id": result.trace_id,
                      "reasoning_method": reasoning_plan.method,
                      "verification_required": reasoning_plan.requires_external_verification},
            ttl_days=365,
        )
        return result

    def dashboard(self) -> dict:
        return {
            "program": self.config.program_name,
            "architecture": self.config.architecture_name,
            "institution": self.config.institution,
            "nation": self.config.nation_name,
            "prototype_version": "0.3.0",
            "registered_providers": [p.profile.model_id for p in self.orchestrator.providers],
            "external_models_enabled": self.config.allow_external_models,
            "recent_events": self.store.recent_events(10),
        }
