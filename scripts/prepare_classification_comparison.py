"""Préparer la comparaison et son ampleur ; ce script n'entraîne aucun modèle."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.ml_workflow import load_data
from src.validation_plan import make_plan
from src.preparation_geography import sha256

assignments, plan = make_plan(load_data())
path = ROOT / "output/classification_split.csv"
assignments.to_csv(path, index=False)
plan["assignments_sha256"] = sha256(path)
plan_path = ROOT / "output/classification_comparison_plan.json"
plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
print("Plan préparé uniquement : aucun fit, aucun score du lot réservé, aucun modèle remplacé.")
