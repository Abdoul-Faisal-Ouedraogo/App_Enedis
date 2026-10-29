"""Figer les choix, entraîner deux modèles puis évaluer une fois le lot réservé."""
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.resource_limits import configure
configure()

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from threadpoolctl import threadpool_limits

from src.final_models import (FINAL_DIR, build_reload_fixture, check_reload_fixture,
                             classification_metrics, regression_metrics, write_json)
from src.ml_workflow import NUMERIC, CATEGORICAL, load_data
from src.preparation_geography import sha256
from src.validation_plan import CANDIDATES

REGRESSION_PARAMETERS = {"n_estimators": 100, "max_depth": 10, "min_samples_split": 20,
                         "min_samples_leaf": 1, "random_state": 42, "n_jobs": 2}


def pipeline(model):
    return Pipeline([("preprocessor", ColumnTransformer([
        ("numeric", "passthrough", NUMERIC),
        ("encoder", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL)])), ("model", model)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", type=Path, required=True, help="Rapport de comparaison validé")
    parser.add_argument("--run", action="store_true", help="Autoriser les deux entraînements finaux et l'évaluation unique")
    args = parser.parse_args()
    comparison = json.loads(args.comparison.read_text(encoding="utf-8"))
    plan = json.loads((ROOT / "output/classification_comparison_plan.json").read_text(encoding="utf-8"))
    assert comparison["plan"] == plan
    assert plan["candidates"] == CANDIDATES
    assert [entry["name"] for entry in comparison["models"]] == [entry["name"] for entry in CANDIDATES]
    best_f1 = max(entry["f1_macro"] for entry in comparison["models"])
    selected = next(entry["name"] for entry in comparison["models"] if entry["f1_macro"] >= best_f1 - 0.001)
    assert comparison["selected_on_validation"] == selected
    candidate = next(candidate for candidate in CANDIDATES if candidate["name"] == selected)
    class_parameters = {key: value for key, value in candidate.items() if key != "name"}
    class_parameters.update(n_estimators=100, random_state=42, n_jobs=2)
    for relative, expected in [("output/cleaned_data.csv", plan["data_sha256"]),
                               ("output/cleaned_data_metadata.csv", plan["metadata_sha256"]),
                               ("output/classification_split.csv", plan["assignments_sha256"])]:
        if sha256(ROOT / relative) != expected:
            raise ValueError(f"Empreinte différente : {relative}")
    split = pd.read_csv(ROOT / "output/classification_split.csv")
    fit_rows = split.loc[split.partition.isin(["train", "validation"]), "cleaned_row"].to_numpy()
    reserved_rows = split.loc[split.partition.eq("reserved"), "cleaned_row"].to_numpy()
    assert len(fit_rows) == 453680 and len(reserved_rows) == 107666
    assert not set(fit_rows) & set(reserved_rows)
    assert not set(split.loc[split.partition.isin(["train", "validation"]), "group"]) & set(split.loc[split.partition.eq("reserved"), "group"])
    print(f"Ampleur : 2 entraînements finaux x 100 arbres, {len(fit_rows)} lignes, 2 threads. Réservé : {len(reserved_rows)} lignes, évaluation après gel.", flush=True)
    print("Classification :", class_parameters, flush=True)
    print("Régression sans nouvelle recherche :", REGRESSION_PARAMETERS, flush=True)
    if not args.run:
        print("Préparation uniquement, aucun entraînement.")
        return
    if FINAL_DIR.exists():
        if (FINAL_DIR / "results.json").exists():
            print("Modèles finaux déjà terminés : refus de réentraîner ou réévaluer. Utiliser scripts/verify_final_models.py.")
            return
        raise FileExistsError("Répertoire final déjà présent : conserver l'état et examiner le journal avant une reprise.")
    FINAL_DIR.mkdir()
    old_hashes = {p.name: sha256(p) for p in (ROOT / "MLmodels").glob("*.pkl")}
    versions = {name: importlib.metadata.version(name) for name in ["numpy", "pandas", "scipy", "scikit-learn", "joblib", "threadpoolctl"]}
    protocol = {"frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "selection": selected, "selection_basis": "F1 macro validation uniquement, trois candidats, tolérance 0.001",
        "comparison_sha256": sha256(args.comparison), "data_sha256": plan["data_sha256"],
        "metadata_sha256": plan["metadata_sha256"], "assignments_sha256": plan["assignments_sha256"],
        "fit_partitions": ["train", "validation"], "fit_rows": len(fit_rows), "reserved_rows": len(reserved_rows),
        "classification_parameters": class_parameters, "regression_parameters": REGRESSION_PARAMETERS,
        "regression_selection": "Réglages précédemment retenus, figés sans nouvelle recherche ni score réservé",
        "refit_after_reserved": False, "resources": {"forest_n_jobs": 2, "native_threads": 2},
        "internal_reserved_warning": "Lot interne à des données déjà exploitées, pas une évaluation externe indépendante",
        "limitations": plan["limitations"] + ["Validation à 91.7 % de neuf, classes F/G peu nombreuses",
            "Année de construction des logements neufs imputée à 2026, donc âge zéro dans la préparation"],
        "versions": versions, "python": sys.version, "old_model_hashes": old_hashes,
        "implementation_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in [Path(__file__), ROOT / "src/final_models.py", ROOT / "src/validation_plan.py", ROOT / "scripts/compare_classification.py"]}}
    # Gel sur disque avant le premier entraînement et avant toute inspection des classes réservées.
    write_json(FINAL_DIR / "frozen_protocol.json", protocol)
    write_json(FINAL_DIR / "comparison_validation.json", comparison)
    write_json(FINAL_DIR / "split_plan.json", plan)
    data = load_data()
    fit_data = data.iloc[fit_rows]
    Xfit = fit_data[NUMERIC + CATEGORICAL]
    classifiers = pipeline(RandomForestClassifier(**class_parameters))
    regressors = pipeline(RandomForestRegressor(**REGRESSION_PARAMETERS))
    timings = {}
    with threadpool_limits(limits=2):
        for name, model, target in [("classification", classifiers, "etiquette_dpe"),
                                     ("regression", regressors, "conso_5_usages_ef")]:
            print("Entraînement final :", name, flush=True)
            started = time.perf_counter()
            model.fit(Xfit, fit_data[target])
            timings[name] = time.perf_counter() - started
            joblib.dump(model, FINAL_DIR / f"{name}.joblib", compress=3)
            variables = {"quantitative_features": NUMERIC, "qualitative_features": CATEGORICAL,
                "features": NUMERIC + CATEGORICAL, "target": target,
                "unit": "classe A à G" if name == "classification" else "kWh/an, énergie finale cinq usages",
                "reference_year": 2026, "climate_zones": ["H1", "H2", "H3"],
                "data_sha256": plan["data_sha256"], "fit_rows": len(fit_rows),
                "model_parameters": model.named_steps["model"].get_params(),
                "model_sha256": sha256(FINAL_DIR / f"{name}.joblib")}
            write_json(FINAL_DIR / f"{name}_variables.json", variables)
            print(f"Modèle sauvegardé : {name}, {timings[name]:.1f} s", flush=True)
        fixture = build_reload_fixture(fit_data, classifiers, regressors)
        write_json(FINAL_DIR / "reload_check.json", fixture)
        check_reload_fixture(fixture, joblib.load(FINAL_DIR / "classification.joblib"), joblib.load(FINAL_DIR / "regression.joblib"))
        # Les paramètres et les modèles sont désormais figés. Pas de modification après cette ligne.
        marker = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
                  "protocol_sha256": sha256(FINAL_DIR / "frozen_protocol.json")}
        write_json(FINAL_DIR / "reserved_evaluation_started.json", marker)
        reserved = data.iloc[reserved_rows]
        Xreserved = reserved[NUMERIC + CATEGORICAL]
        print("Évaluation unique du lot réservé interne, après gel des deux modèles.", flush=True)
        pred_class = classifiers.predict(Xreserved)
        pred_reg = regressors.predict(Xreserved)
    metadata = pd.read_csv(ROOT / "output/cleaned_data_metadata.csv", dtype="string")
    reserved_sources = metadata.iloc[reserved_rows]._source_dataset.to_numpy()
    predictions = pd.DataFrame({"cleaned_row": reserved_rows, "source": reserved_sources,
        "true_dpe": reserved.etiquette_dpe.to_numpy(), "predicted_dpe": pred_class,
        "true_consumption": reserved.conso_5_usages_ef.to_numpy(), "predicted_consumption": pred_reg})
    prediction_dir = ROOT / "output/final_geo_v1"
    prediction_dir.mkdir(exist_ok=True)
    prediction_path = prediction_dir / "reserved_predictions.csv"
    predictions.to_csv(prediction_path, index=False)
    majority = fit_data.etiquette_dpe.value_counts().idxmax()
    median = float(fit_data.conso_5_usages_ef.median())
    baseline_class = np.full(len(reserved), majority)
    baseline_reg = np.full(len(reserved), median)
    results = {"protocol_sha256": sha256(FINAL_DIR / "frozen_protocol.json"),
        "reserved_evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": protocol["internal_reserved_warning"], "timings_seconds": timings,
        "predictions_path": prediction_path.relative_to(ROOT).as_posix(), "predictions_sha256": sha256(prediction_path),
        "classification": classification_metrics(reserved.etiquette_dpe, pred_class),
        "regression": regression_metrics(reserved.conso_5_usages_ef, pred_reg),
        "baseline": {"classification_majority": majority, "regression_median_kwh": median,
            "classification": classification_metrics(reserved.etiquette_dpe, baseline_class),
            "regression": regression_metrics(reserved.conso_5_usages_ef, baseline_reg)},
        "by_source": {}, "regression_by_dpe": {}}
    for source in ["existant", "neuf"]:
        positions = np.flatnonzero(reserved_sources == source)
        actual = reserved.iloc[positions]
        results["by_source"][source] = {
            "classification": classification_metrics(actual.etiquette_dpe, pred_class[positions]),
            "regression": regression_metrics(actual.conso_5_usages_ef, pred_reg[positions]),
            "baseline_classification": classification_metrics(actual.etiquette_dpe, baseline_class[positions]),
            "baseline_regression": regression_metrics(actual.conso_5_usages_ef, baseline_reg[positions])}
    for label in "ABCDEFG":
        positions = np.flatnonzero(reserved.etiquette_dpe.to_numpy() == label)
        if len(positions):
            results["regression_by_dpe"][label] = regression_metrics(reserved.iloc[positions].conso_5_usages_ef, pred_reg[positions])
    distribution = {}
    for partition in ["train", "validation", "reserved", "excluded"]:
        positions = np.flatnonzero(split.partition.to_numpy() == partition)
        sources = metadata.iloc[positions]._source_dataset
        labels = data.iloc[positions].etiquette_dpe
        distribution[partition] = {"rows": len(positions), "sources": sources.value_counts().to_dict(),
            "classes": labels.value_counts().sort_index().to_dict(),
            "class_by_source": pd.crosstab(sources.to_numpy(), labels.to_numpy()).to_dict(orient="index")}
    write_json(FINAL_DIR / "partition_distributions.json", distribution)
    assert old_hashes == {p.name: sha256(p) for p in (ROOT / "MLmodels").glob("*.pkl")}
    results["old_models_unchanged"] = True
    results["reload_predictions_verified"] = True
    write_json(FINAL_DIR / "results.json", results)
    manifest = {"version": "final_geo_v1", "directory": FINAL_DIR.relative_to(ROOT).as_posix(),
        "data_sha256": plan["data_sha256"], "results_sha256": sha256(FINAL_DIR / "results.json"),
        "classification": (FINAL_DIR / "classification.joblib").relative_to(ROOT).as_posix(),
        "regression": (FINAL_DIR / "regression.joblib").relative_to(ROOT).as_posix(),
        "note": protocol["internal_reserved_warning"]}
    manifest_path = ROOT / "MLmodels/final_models.json"
    if manifest_path.exists():
        raise FileExistsError("Ne pas remplacer un manifeste final existant sans examiner sa version")
    write_json(manifest_path, manifest)
    print("TERMINÉ", json.dumps({"classification": {k: results["classification"][k] for k in ["accuracy", "f1_macro"]},
        "regression": results["regression"], "baseline_regression": results["baseline"]["regression"]}), flush=True)


if __name__ == "__main__":
    main()
