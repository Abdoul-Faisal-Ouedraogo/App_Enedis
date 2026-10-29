"""Contrats et métriques des modèles finaux ; aucune fonction ne les entraîne."""
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                             f1_score, mean_absolute_error, r2_score, root_mean_squared_error)

from src.project_paths import ROOT

FINAL_DIR = ROOT / "MLmodels/final_geo_v1"


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def classification_metrics(truth, predictions):
    return {"rows": len(truth), "accuracy": float(accuracy_score(truth, predictions)),
            "f1_macro": float(f1_score(truth, predictions, labels=list("ABCDEFG"), average="macro", zero_division=0)),
            "report": classification_report(truth, predictions, labels=list("ABCDEFG"), output_dict=True, zero_division=0),
            "confusion_labels": list("ABCDEFG"),
            "confusion_matrix": confusion_matrix(truth, predictions, labels=list("ABCDEFG")).tolist()}


def regression_metrics(truth, predictions):
    return {"rows": len(truth), "mae": float(mean_absolute_error(truth, predictions)),
            "rmse": float(root_mean_squared_error(truth, predictions)),
            "r2": float(r2_score(truth, predictions)) if len(truth) >= 2 else None}


def build_reload_fixture(data, classifier, regressor):
    from src.ml_workflow import NUMERIC, CATEGORICAL
    features = data[NUMERIC + CATEGORICAL].sample(n=min(32, len(data)), random_state=42)
    return {"origin": "Échantillon entraînement + validation, jamais le lot réservé",
            "features": features.to_dict(orient="records"),
            "classification": classifier.predict(features).tolist(),
            "regression": regressor.predict(features).tolist()}


def check_reload_fixture(fixture, classifier, regressor):
    import pandas as pd
    from src.ml_workflow import NUMERIC, CATEGORICAL
    features = pd.DataFrame(fixture["features"])[NUMERIC + CATEGORICAL]
    np.testing.assert_array_equal(classifier.predict(features), fixture["classification"])
    np.testing.assert_allclose(regressor.predict(features), fixture["regression"], rtol=1e-12, atol=1e-8)
