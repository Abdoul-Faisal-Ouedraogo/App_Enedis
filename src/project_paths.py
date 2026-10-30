"""Chemins communs aux notebooks, scripts et à l'application."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "output" / "cleaned_data.csv"
MODEL_DIR = ROOT / "MLmodels"
