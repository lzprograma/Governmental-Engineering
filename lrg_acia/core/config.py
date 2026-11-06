"""Configuração central do programa. O identificador nacional definido é Lunz."""
from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    program_name: str = "LRG SOVEREIGN AGI"
    architecture_name: str = "Adaptive Cognitive Intelligence Architecture (ACIA)"
    institution: str = "Governo de Lunz"
    nation_name: str = "Lunz"
    data_dir: Path = Path(os.getenv("LRG_DATA_DIR", "./data"))
    database_path: Path = Path(os.getenv("LRG_DATABASE_PATH", "./data/acia.sqlite3"))
    default_model: str = "lrg-demo-model"
    max_task_chars: int = 20_000
    max_memory_chars: int = 50_000
    default_cost_budget: float = 1.0
    allow_external_models: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = 8765

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
