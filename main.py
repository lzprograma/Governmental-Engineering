"""Ponto de entrada: python main.py On server | dashboard | task."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lrg_acia.cli import main

if __name__ == "__main__":
    main()
