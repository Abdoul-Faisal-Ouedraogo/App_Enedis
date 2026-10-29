"""Vérifier artefacts, rechargement et résultats conservés, sans réévaluer les modèles sur le réservé."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.resource_limits import configure
configure()
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from src.final_models import FINAL_DIR, check_reload_fixture, classification_metrics, regression_metrics
from src.ml_workflow import NUMERIC, CATEGORICAL
from src.preparation_geography import sha256


def verify():
    manifest = json.loads((ROOT / "MLmodels/final_models.json").read_text(encoding="utf-8"))
    report = json.loads((FINAL_DIR / "results.json").read_text(encoding="utf-8"))
    protocol = json.loads((FINAL_DIR / "frozen_protocol.json").read_text(encoding="utf-8"))
    assert sha256(FINAL_DIR / "results.json") == manifest["results_sha256"]
    assert sha256(FINAL_DIR / "frozen_protocol.json") == report["protocol_sha256"]
    for relative, expected in [("output/cleaned_data.csv", protocol["data_sha256"]),
                               ("output/cleaned_data_metadata.csv", protocol["metadata_sha256"]),
                               ("output/classification_split.csv", protocol["assignments_sha256"])]:
        assert sha256(ROOT / relative) == expected, relative
    for filename, expected in protocol["old_model_hashes"].items():
        assert sha256(ROOT / "MLmodels" / filename) == expected, filename
    models = {}
    for name, target in [("classification", "etiquette_dpe"), ("regression", "conso_5_usages_ef")]:
        variables = json.loads((FINAL_DIR / f"{name}_variables.json").read_text(encoding="utf-8"))
        path = FINAL_DIR / f"{name}.joblib"
        assert sha256(path) == variables["model_sha256"]
        assert variables["features"] == NUMERIC + CATEGORICAL
        assert variables["target"] == target and variables["fit_rows"] == protocol["fit_rows"]
        model = joblib.load(path)
        assert list(model.feature_names_in_) == NUMERIC + CATEGORICAL
        assert model.named_steps["model"].get_params() == variables["model_parameters"]
        assert model.named_steps["model"].n_jobs == 2
        for key, value in protocol[f"{name}_parameters"].items():
            assert model.named_steps["model"].get_params()[key] == value
        models[name] = model
    fixture = json.loads((FINAL_DIR / "reload_check.json").read_text(encoding="utf-8"))
    with threadpool_limits(limits=2):
        check_reload_fixture(fixture, models["classification"], models["regression"])
    prediction_path = ROOT / report["predictions_path"]
    assert sha256(prediction_path) == report["predictions_sha256"]
    predictions = pd.read_csv(prediction_path)
    split = pd.read_csv(ROOT / "output/classification_split.csv")
    np.testing.assert_array_equal(predictions.cleaned_row, split.loc[split.partition.eq("reserved"), "cleaned_row"])
    assert len(predictions) == protocol["reserved_rows"]
    # Recalcul depuis les prédictions déjà figées : aucun nouvel appel predict sur le réservé.
    metrics = classification_metrics(predictions.true_dpe, predictions.predicted_dpe)
    for key in ["accuracy", "f1_macro"]:
        np.testing.assert_allclose(metrics[key], report["classification"][key], rtol=1e-12)
    np.testing.assert_array_equal(metrics["confusion_matrix"], report["classification"]["confusion_matrix"])
    for label in list("ABCDEFG") + ["macro avg", "weighted avg"]:
        np.testing.assert_allclose(list(metrics["report"][label].values()), list(report["classification"]["report"][label].values()), rtol=1e-12)
    metrics = regression_metrics(predictions.true_consumption, predictions.predicted_consumption)
    for key in ["mae", "rmse", "r2"]:
        np.testing.assert_allclose(metrics[key], report["regression"][key], rtol=1e-10, atol=1e-8)
    print("OK : modèles/variables/empreintes, deux threads, anciens modèles conservés, rechargement et prédictions identiques.")
    print("OK : résultats vérifiés depuis les prédictions conservées ; aucun nouvel entraînement ni nouvelle prédiction sur le réservé.")
    return report


if __name__ == "__main__":
    verify()
