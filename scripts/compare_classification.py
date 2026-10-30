"""Trois candidats sur entraînement/validation uniquement. Sans --run, aucun fit."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.resource_limits import configure
configure()
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from threadpoolctl import threadpool_limits
import time

from src.ml_workflow import NUMERIC, CATEGORICAL, load_data
from src.preparation_geography import sha256
from src.validation_plan import CANDIDATES, TRAIN_CAP


def evaluate(truth, predictions):
    return {"accuracy": accuracy_score(truth, predictions),
            "f1_macro": f1_score(truth, predictions, labels=list("ABCDEFG"), average="macro", zero_division=0),
            "report": classification_report(truth, predictions, labels=list("ABCDEFG"), output_dict=True, zero_division=0)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Lancer explicitement les trois entraînements annoncés")
    args = parser.parse_args()
    plan = json.loads((ROOT / "output/classification_comparison_plan.json").read_text(encoding="utf-8"))
    assert plan["candidates"] == CANDIDATES
    assert plan["train_cap"] == TRAIN_CAP
    assert plan["fit_count"] == 3 and plan["trees_per_fit"] == 100 and plan["n_jobs"] == 2
    for relative, digest in [("output/cleaned_data.csv", plan["data_sha256"]),
                             ("output/cleaned_data_metadata.csv", plan["metadata_sha256"]),
                             ("output/classification_split.csv", plan["assignments_sha256"])]:
        if sha256(ROOT / relative) != digest:
            raise ValueError(f"Le fichier {relative} a changé ; régénérer et revoir le plan avant entraînement")
    split = pd.read_csv(ROOT / "output/classification_split.csv")
    train_rows = split.loc[split.comparison_train, "cleaned_row"].to_numpy()
    validation_rows = split.loc[split.partition.eq("validation"), "cleaned_row"].to_numpy()
    assert len(train_rows) == plan["comparison_train_rows"] <= TRAIN_CAP
    assert len(validation_rows) == plan["comparison_validation_rows"]
    assert split.loc[split.comparison_train, "partition"].eq("train").all()
    assert not set(split.loc[split.comparison_train, "group"]) & set(split.loc[split.partition.eq("validation"), "group"])
    print(f"Ampleur prévue : 3 entraînements x 100 arbres, 2 threads ; {len(train_rows)} lignes d'entraînement communes ; {len(validation_rows)} de validation.", flush=True)
    print("Sélection : F1 macro A–G sur validation. Aucun accès aux cibles du lot réservé, aucun remplacement des modèles existants.", flush=True)
    if not args.run:
        print("Préparation uniquement. Ajouter --run après annonce de cette ampleur pour lancer les entraînements.")
        return
    data = load_data()
    # Extraire seulement les cibles d'entraînement et de validation.
    train, validation = data.iloc[train_rows], data.iloc[validation_rows]
    del data
    Xtrain, ytrain = train[NUMERIC + CATEGORICAL], train.etiquette_dpe
    Xvalidation, yvalidation = validation[NUMERIC + CATEGORICAL], validation.etiquette_dpe
    majority = ytrain.value_counts().idxmax()
    result = {"plan": plan, "baseline_class": majority,
              "baseline_validation": evaluate(yvalidation, np.full(len(yvalidation), majority)), "models": []}
    result["resources"] = {"forest_n_jobs": 2, "native_threads": 2}
    metadata = pd.read_csv(ROOT / "output/cleaned_data_metadata.csv", usecols=["_source_dataset"])
    for candidate in CANDIDATES:
        print("Entraînement :", candidate["name"], flush=True)
        parameters = {key: value for key, value in candidate.items() if key != "name"}
        pipeline = Pipeline([
            ("preprocessor", ColumnTransformer([("numeric", "passthrough", NUMERIC),
                ("encoder", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL)])),
            ("model", RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=2, **parameters))])
        started = time.perf_counter()
        with threadpool_limits(limits=2):
            pipeline.fit(Xtrain, ytrain)
            predictions = pipeline.predict(Xvalidation)
        metrics = evaluate(yvalidation, predictions)
        metrics["name"] = candidate["name"]
        metrics["seconds"] = time.perf_counter() - started
        metrics["by_source"] = {}
        for source in ["existant", "neuf"]:
            mask = metadata.iloc[validation_rows]._source_dataset.eq(source).to_numpy()
            if mask.any():
                metrics["by_source"][source] = evaluate(yvalidation.iloc[np.flatnonzero(mask)], predictions[mask])
        result["models"].append(metrics)
        print(f"Validation : accuracy={metrics['accuracy']:.4f}, F1 macro={metrics['f1_macro']:.4f}, {metrics['seconds']:.1f} s", flush=True)
    best_score = max(entry["f1_macro"] for entry in result["models"])
    result["selected_on_validation"] = next(entry["name"] for entry in result["models"] if entry["f1_macro"] >= best_score - 0.001)
    # Seul un rapport horodaté est écrit ; aucun pipeline n'est publié/remplacé.
    directory = ROOT / "output/classification_comparisons"
    directory.mkdir(exist_ok=True)
    path = directory / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Comparaison terminée, sélection sur validation uniquement :", result["selected_on_validation"], flush=True)
    print("Rapport :", path)


if __name__ == "__main__":
    main()
