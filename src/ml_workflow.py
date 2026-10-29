"""Évaluation sans réentraînement et entraînement explicite de la classification."""
import hashlib
import json
import platform

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, classification_report, f1_score,
                             mean_absolute_error, r2_score, root_mean_squared_error)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from src.project_paths import DATA_PATH, MODEL_DIR

NUMERIC = ["surface_habitable_logement", "nombre_niveau_logement", "age_batiment", "altitude_moyenne"]
CATEGORICAL = ["type_energie_principale_chauffage", "type_batiment", "zone_climatique"]
CLASS_MODEL = MODEL_DIR / "pipeline_classification_common.pkl"
CLASS_REPORT = MODEL_DIR / "classification_common.json"


def load_data(path=DATA_PATH):
    df = pd.read_csv(path, dtype={"code_insee_ban": str, "code_departement_ban": str}, low_memory=False)
    required = NUMERIC + CATEGORICAL + ["conso_5_usages_ef", "etiquette_dpe"]
    missing = set(required) - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes absentes : {sorted(missing)}")
    if df[required].isna().any().any():
        raise ValueError("Valeurs manquantes dans les variables ML")
    if not np.isfinite(df[NUMERIC + ["conso_5_usages_ef"]].to_numpy()).all():
        raise ValueError("Valeurs numériques non finies")
    if (df.conso_5_usages_ef < 0).any() or not df.etiquette_dpe.isin(list("ABCDEFG")).all():
        raise ValueError("Cible invalide")
    return df


def fingerprint(path=DATA_PATH):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def reference_data_path():
    """La sauvegarde liée aux anciens modèles, sans confondre les versions."""
    from src.project_paths import ROOT
    reference = json.loads((MODEL_DIR / "data_reference.json").read_text(encoding="utf-8"))
    path = ROOT / reference["data_path"]
    if not path.is_file() or fingerprint(path) != reference["data_sha256"]:
        raise ValueError("La sauvegarde de référence des anciens modèles est absente ou modifiée")
    return path


def split_classification(df):
    return train_test_split(df[NUMERIC + CATEGORICAL], df.etiquette_dpe,
                            test_size=0.3, random_state=42, stratify=df.etiquette_dpe)


def train_classification(df):
    """Un seul modèle borné ; aucune recherche de paramètres ni accès réseau."""
    reference_report = json.loads(CLASS_REPORT.read_text(encoding="utf-8"))
    if fingerprint() != reference_report["data_sha256"]:
        raise ValueError("CSV corrigé : utiliser la comparaison entraînement/validation préparée, pas l'ancien découpage aléatoire.")
    Xtrain, Xtest, ytrain, ytest = split_classification(df)
    pipeline = Pipeline([
        ("preprocessor", ColumnTransformer([
            ("numeric", "passthrough", NUMERIC),
            ("encoder", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
        ])),
        ("model", RandomForestClassifier(n_estimators=100, max_depth=10,
                                        min_samples_split=20, class_weight="balanced",
                                        random_state=42, n_jobs=2)),
    ])
    pipeline.fit(Xtrain, ytrain)
    predictions = pipeline.predict(Xtest)
    report = {
        "source": "output/cleaned_data.csv", "data_sha256": fingerprint(),
        "rows": len(df), "train_rows": len(Xtrain), "test_rows": len(Xtest),
        "random_state": 42, "test_size": 0.3, "stratified": True,
        "quantitative_features": NUMERIC, "qualitative_features": CATEGORICAL,
        "target": "etiquette_dpe", "python": platform.python_version(),
        "sklearn": sklearn.__version__, "pandas": pd.__version__,
        "accuracy": accuracy_score(ytest, predictions),
        "f1_macro": f1_score(ytest, predictions, average="macro"),
        "report": classification_report(ytest, predictions, output_dict=True, zero_division=0),
        "parameters": pipeline.named_steps["model"].get_params(),
        "note": "Réglages fixés avant évaluation, sans recherche sur le test. Coût et consommation exclus des entrées.",
    }
    MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump(pipeline, CLASS_MODEL, compress=3)
    with CLASS_MODEL.open("rb") as stream:
        report["model_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    reloaded = joblib.load(CLASS_MODEL)
    np.testing.assert_array_equal(predictions, reloaded.predict(Xtest))
    CLASS_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return pipeline, report


def verify_regression(df, data_path=DATA_PATH):
    reference = json.loads((MODEL_DIR / "data_reference.json").read_text(encoding="utf-8"))
    if fingerprint(data_path) != reference["data_sha256"]:
        raise ValueError("Les anciens scores de régression concernent uniquement le CSV sauvegardé avant correction géographique")
    if fingerprint(MODEL_DIR / "pipeline_random_forest_consommation.pkl") != reference["regression_model_sha256"]:
        raise ValueError("Le modèle de régression ne correspond plus à sa référence")
    info = joblib.load(MODEL_DIR / "features_target_columns_consommation.pkl")
    pipeline = joblib.load(MODEL_DIR / "pipeline_random_forest_consommation.pkl")
    assert info["target"] == "conso_5_usages_ef"
    assert info["quantitative_features"] == NUMERIC
    assert info["qualitative_features"] == CATEGORICAL
    assert list(pipeline.feature_names_in_) == NUMERIC + CATEGORICAL
    X = df[info["quantitative_features"] + info["qualitative_features"]]
    _, Xtest, _, ytest = train_test_split(X, df[info["target"]], test_size=0.3, random_state=42)
    predictions = pipeline.predict(Xtest)
    metrics = {"mae": mean_absolute_error(ytest, predictions),
               "rmse": root_mean_squared_error(ytest, predictions),
               "r2": r2_score(ytest, predictions)}
    np.testing.assert_allclose(list(metrics.values()), [2121.4521188838185, 3954.6997277004607, 0.6932078583487365], rtol=1e-6)
    np.testing.assert_allclose(predictions[:20], joblib.load(
        MODEL_DIR / "pipeline_random_forest_consommation.pkl").predict(Xtest.head(20)))
    return metrics


def verify_classification(df, data_path=DATA_PATH):
    report = json.loads(CLASS_REPORT.read_text(encoding="utf-8"))
    if report["data_sha256"] != fingerprint(data_path):
        raise ValueError("Le CSV diffère de celui utilisé pour la classification")
    with CLASS_MODEL.open("rb") as stream:
        model_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    if report["model_sha256"] != model_hash:
        raise ValueError("Le modèle de classification ne correspond pas à son rapport")
    assert report["target"] == "etiquette_dpe"
    assert report["quantitative_features"] == NUMERIC
    assert report["qualitative_features"] == CATEGORICAL
    pipeline = joblib.load(CLASS_MODEL)
    assert list(pipeline.feature_names_in_) == NUMERIC + CATEGORICAL
    _, Xtest, _, ytest = split_classification(df)
    predictions = pipeline.predict(Xtest)
    metrics = {"accuracy": accuracy_score(ytest, predictions),
               "f1_macro": f1_score(ytest, predictions, average="macro")}
    np.testing.assert_allclose(list(metrics.values()), [report[k] for k in metrics], rtol=1e-12)
    calculated = classification_report(ytest, predictions, output_dict=True, zero_division=0)
    for label in list("ABCDEFG") + ["macro avg", "weighted avg"]:
        np.testing.assert_allclose(list(calculated[label].values()),
                                   list(report["report"][label].values()), rtol=1e-12)
    np.testing.assert_array_equal(predictions[:20], joblib.load(CLASS_MODEL).predict(Xtest.head(20)))
    return metrics


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-classification", action="store_true")
    parser.add_argument("--historical", action="store_true", help="Vérifier les anciens scores sur leur CSV sauvegardé")
    args = parser.parse_args()
    selected_path = reference_data_path() if args.historical else DATA_PATH
    data = load_data(selected_path)
    print(f"Source commune : {len(data)} logements, {data.code_departement_ban.nunique()} départements", flush=True)
    if args.train_classification:
        if args.historical:
            parser.error("--historical est réservé à la vérification, sans entraînement")
        _, result = train_classification(data)
        print("Classification :", {k: result[k] for k in ["accuracy", "f1_macro"]}, flush=True)
    elif args.historical:
        print("Régression historique vérifiée :", verify_regression(data, selected_path), flush=True)
        print("Classification historique vérifiée :", verify_classification(data, selected_path), flush=True)
    else:
        from src.project_paths import ROOT
        if (MODEL_DIR / "final_models.json").is_file():
            from scripts.verify_final_models import verify
            verify()
        else:
            print("CSV corrigé validé. Anciens scores associés au CSV sauvegardé ; --historical pour les reproduire. Aucun entraînement.")
