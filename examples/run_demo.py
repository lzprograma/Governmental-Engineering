"""Demonstra os fluxos centrais sem serviços externos ou dados reais."""
from pathlib import Path
from tempfile import TemporaryDirectory
import sys

# Permite executar o exemplo diretamente a partir de um checkout sem instalação prévia.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from lrg_acia.core.config import Settings
from lrg_acia.core.contracts import Task, RiskLevel
from lrg_acia.service import ACIAService
from lrg_acia.relational_engine.ragi import Relation
from lrg_acia.affect_engine.state import AffectObservation


def main() -> None:
    with TemporaryDirectory() as tmp:
        config = Settings(data_dir=Path(tmp), database_path=Path(tmp) / "demo.sqlite3")
        acia = ACIAService(config)
        print("=== DASHBOARD ===")
        print(acia.dashboard())

        print("\n=== TAREFA ===")
        result = acia.execute_task(Task(
            prompt="Organize um plano experimental para avaliar melhoria de recuperação documental.",
            domain="research", risk_level=RiskLevel.LOW,
        ))
        print(result.status.value, result.answer)

        print("\n=== RAGI ===")
        first = acia.ragi.propose(Relation("A", "B", "is_ancestor_of", ("source-1",), 0.98))
        second = acia.ragi.propose(Relation("B", "C", "is_ancestor_of", ("source-2",), 0.95))
        acia.ragi.verify(first.relation_id, "reviewer-1")
        acia.ragi.verify(second.relation_id, "reviewer-1")
        print("Inferências candidatas:", acia.ragi.infer_transitive())

        print("\n=== AFFECT ENGINE ===")
        acia.affect_state = acia.affect.update(
            acia.affect_state,
            AffectObservation(0.8, 0.3, 0.1, 0.2, 0.4),
        )
        print(acia.affect_state, acia.affect.recommended_action(acia.affect_state))


if __name__ == "__main__":
    main()
