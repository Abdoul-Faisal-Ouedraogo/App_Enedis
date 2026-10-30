"""Lecture des modèles finaux et de leurs résultats figés, sans entraînement."""
import json
import joblib
from threadpoolctl import threadpool_limits

from src.final_models import FINAL_DIR, check_reload_fixture
from src.preparation_geography import sha256
from src.project_paths import ROOT


def load_final_bundle():
    """Recharger et contrôler sur les exemples de développement, pas sur le réservé."""
    manifest = json.loads((ROOT / "MLmodels/final_models.json").read_text(encoding="utf-8"))
    assert sha256(FINAL_DIR / "results.json") == manifest["results_sha256"]
    results = json.loads((FINAL_DIR / "results.json").read_text(encoding="utf-8"))
    assert sha256(FINAL_DIR / "frozen_protocol.json") == results["protocol_sha256"]
    bundle = {"results": results,
        "comparison": json.loads((FINAL_DIR / "comparison_validation.json").read_text(encoding="utf-8")),
        "protocol": json.loads((FINAL_DIR / "frozen_protocol.json").read_text(encoding="utf-8")), "variables": {}}
    for name in ["classification", "regression"]:
        variables = json.loads((FINAL_DIR / f"{name}_variables.json").read_text(encoding="utf-8"))
        assert sha256(FINAL_DIR / f"{name}.joblib") == variables["model_sha256"]
        bundle[name] = joblib.load(FINAL_DIR / f"{name}.joblib")
        bundle["variables"][name] = variables
    fixture = json.loads((FINAL_DIR / "reload_check.json").read_text(encoding="utf-8"))
    with threadpool_limits(limits=2):
        check_reload_fixture(fixture, bundle["classification"], bundle["regression"])
    return bundle
