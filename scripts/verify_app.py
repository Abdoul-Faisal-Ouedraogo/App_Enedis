"""Exécuter les tests de l'application dans l'environnement Python courant."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "-q",
                                     str(ROOT / "tests")], cwd=ROOT))
