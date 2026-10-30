"""Présenter les modèles finaux en conservant intégralement les notebooks précédents."""
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "Notebooks_Api_Traitement"


def cell(kind, source):
    value = {"cell_type": kind, "metadata": {}, "source": source.splitlines(True)}
    if kind == "code":
        value.update(execution_count=None, outputs=[])
    return value


BOOTSTRAP = '''from pathlib import Path
import os
import sys
ROOT = next((p for p in [Path.cwd(), *Path.cwd().parents]
             if (p / "pyproject.toml").exists() and (p / "MLmodels").is_dir()), None)
if ROOT is None:
    raise RuntimeError("Ouvrez le notebook depuis le dépôt App_Enedis.")
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.resource_limits import configure
configure()
import pandas as pd
import json
from src.final_model_loader import load_final_bundle
bundle = load_final_bundle()
print("Modèles finaux rechargés ; prédictions de contrôle identiques.")
print("Aucun entraînement ni nouvelle évaluation du lot réservé.")
'''

classification = [
    cell("markdown", "# Classification DPE — modèle final géographique v1\n\nDonnées corrigées avec les règles de Nouhayla pour Lyon/Pierre-Bénite. Comparaison de trois Random Forest sur 60 000 lignes d'entraînement et 55 235 de validation. Sélection au F1 macro de validation, puis entraînement final sur les 453 680 lignes entraînement + validation. Les 107 666 lignes réservées ont été évaluées après gel des choix. **Ce lot reste interne à des données déjà exploitées, pas externe.**\n\nCe notebook lit les résultats sauvegardés ; il ne réentraîne rien et ne recalcule pas les prédictions réservées. Les travaux antérieurs sont intégralement conservés dans archives/.\n"),
    cell("code", BOOTSTRAP),
    cell("code", '''comparison = bundle["comparison"]
partitions = json.loads((ROOT / "MLmodels/final_geo_v1/partition_distributions.json").read_text(encoding="utf-8"))
display(pd.DataFrame([{ "Partition": name, "Effectif": values["rows"],
                       "Existant": values["sources"].get("existant", 0), "Neuf": values["sources"].get("neuf", 0)}
                     for name, values in partitions.items()]))
display(pd.DataFrame({name: values["classes"] for name, values in partitions.items()}).T)
print("Référence majoritaire de validation :", comparison["baseline_class"])
print("Accuracy :", comparison["baseline_validation"]["accuracy"])
print("F1 macro :", comparison["baseline_validation"]["f1_macro"])
table = pd.DataFrame([{
    "Modèle": m["name"], "Accuracy validation": m["accuracy"], "F1 macro validation": m["f1_macro"],
    "Accuracy existant": m["by_source"]["existant"]["accuracy"],
    "F1 macro existant": m["by_source"]["existant"]["f1_macro"],
    "Accuracy neuf": m["by_source"]["neuf"]["accuracy"],
    "F1 macro neuf": m["by_source"]["neuf"]["f1_macro"],
} for m in comparison["models"]])
display(table)
print("Choix figé sur validation :", comparison["selected_on_validation"])
'''),
    cell("code", '''rows = []
for model in comparison["models"]:
    for scope, report in [("ensemble", model)] + list(model["by_source"].items()):
        for label in "ABCDEFG":
            rows.append({"Modèle": model["name"], "Population": scope, "DPE": label,
                         **report["report"][label]})
display(pd.DataFrame(rows).pivot(index=["Modèle", "Population"], columns="DPE", values="f1-score"))
'''),
    cell("code", '''result = bundle["results"]
print("LOT RÉSERVÉ INTERNE — résultat final déjà évalué, aucun réglage ultérieur")
print("Accuracy :", result["classification"]["accuracy"])
print("F1 macro :", result["classification"]["f1_macro"])
print("Référence majoritaire :", result["baseline"]["classification_majority"])
print("Accuracy référence :", result["baseline"]["classification"]["accuracy"])
print("F1 macro référence :", result["baseline"]["classification"]["f1_macro"])
display(pd.DataFrame({label: result["classification"]["report"][label] for label in "ABCDEFG"}).T)
display(pd.DataFrame([{ "Population": source, "Effectif": v["classification"]["rows"],
                      "Accuracy": v["classification"]["accuracy"], "F1 macro": v["classification"]["f1_macro"]}
                     for source, v in result["by_source"].items()]))
'''),
    cell("code", '''per_source = []
for source, values in result["by_source"].items():
    for label in "ABCDEFG":
        per_source.append({"Population": source, "DPE": label, **values["classification"]["report"][label]})
display(pd.DataFrame(per_source))
from sklearn.metrics import ConfusionMatrixDisplay
import matplotlib.pyplot as plt
ConfusionMatrixDisplay(confusion_matrix=__import__("numpy").array(result["classification"]["confusion_matrix"]),
                       display_labels=list("ABCDEFG")).plot()
plt.title("Lot réservé interne — matrice sauvegardée")
plt.show()
'''),
    cell("markdown", "La validation contient 91,7 % de neuf, mais le réservé 46,8 %. Les résultats par population et par classe sont donc nécessaires. La classe A est bien mieux reconnue que F/G ; le modèle produit beaucoup de fausses alertes F/G. Ne pas utiliser ces prédictions comme diagnostic réglementaire. Les anciens scores aléatoires ne sont pas directement comparables à ce protocole. Les filtres de préparation restent appris globalement et BAN n'identifie pas parfaitement les bâtiments : une validation externe reste nécessaire.\n"),
    cell("code", '''print("Variables :", bundle["variables"]["classification"]["features"])
print("Cible :", bundle["variables"]["classification"]["target"])
print("Paramètres :", bundle["variables"]["classification"]["model_parameters"])
print("Modèle : MLmodels/final_geo_v1/classification.joblib")
'''),
]

regression = [
    cell("markdown", "# Régression de consommation finale — modèle final géographique v1\n\nCible : **conso_5_usages_ef, kWh/an**, sans coût ni étiquette en entrée. Les sept caractéristiques sont communes à la classification. Les corrections d'altitude de Nouhayla sont intégrées. Random Forest de 100 arbres, profondeur 10, min_samples_split=20, graine 42, deux threads. Réglages conservés sans nouvelle recherche, entraînement final sur les 453 680 lignes entraînement + validation.\n\nÉvaluation sur les 107 666 lignes réservées après gel des choix. **Lot interne à des données déjà exploitées : ce n'est pas un test externe indépendant.** Le notebook affiche les résultats figés et n'entraîne ni ne réévalue les modèles. La version précédente est conservée dans archives/.\n"),
    cell("code", BOOTSTRAP),
    cell("code", '''result = bundle["results"]
print("LOT RÉSERVÉ INTERNE — résultats sauvegardés")
print("MAE (kWh/an) :", result["regression"]["mae"])
print("RMSE (kWh/an) :", result["regression"]["rmse"])
print("R² :", result["regression"]["r2"])
print("Référence : médiane de l'entraînement + validation =", result["baseline"]["regression_median_kwh"])
display(pd.DataFrame([{"Modèle": "Random Forest", **result["regression"]},
                      {"Modèle": "Médiane constante", **result["baseline"]["regression"]}]))
'''),
    cell("code", '''display(pd.DataFrame([{ "Population": source, **values["regression"]}
                      for source, values in result["by_source"].items()]))
display(pd.DataFrame(result["regression_by_dpe"]).T)
'''),
    cell("code", '''# Analyse des prédictions déjà conservées ; aucun nouvel appel au modèle sur le réservé.
path = ROOT / result["predictions_path"]
if path.is_file():
    predictions = pd.read_csv(path)
    residuals = predictions.true_consumption - predictions.predicted_consumption
    import matplotlib.pyplot as plt
    sample = predictions.sample(n=min(3000, len(predictions)), random_state=42)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].hist(residuals, bins=60)
    axes[0].set_xlabel("Consommation réelle moins prédite (kWh/an)")
    axes[0].set_title("Résidus conservés — lot interne")
    axes[1].scatter(sample.true_consumption, sample.predicted_consumption, s=5, alpha=0.25)
    axes[1].set_xlabel("Consommation réelle (kWh/an)")
    axes[1].set_ylabel("Consommation prédite (kWh/an)")
    plt.tight_layout()
    plt.show()
else:
    print("Prédictions détaillées locales absentes ; les métriques et modèles restent disponibles.")
'''),
    cell("code", '''print("Variables :", bundle["variables"]["regression"]["features"])
print("Cible :", bundle["variables"]["regression"]["target"])
print("Unité :", bundle["variables"]["regression"]["unit"])
print("Paramètres :", bundle["variables"]["regression"]["model_parameters"])
print("Modèle : MLmodels/final_geo_v1/regression.joblib")
'''),
    cell("markdown", "L'erreur est plus élevée dans l'existant que dans le neuf. La MAE n'est pas un intervalle de confiance individuel. Les anciens scores (MAE 2 121,45 ; R² 0,6932) concernent un autre CSV et un autre découpage ; leur différence avec les scores présents ne démontre pas un progrès du modèle. Une évaluation externe et une préparation ajustée uniquement sur l'entraînement restent à prévoir. Aucun réglage n'a été modifié après observation du lot réservé.\n"),
]

archive = DIRECTORY / "archives"
archive.mkdir(exist_ok=True)
for name, cells in [("2_classification_dpe.ipynb", classification), ("3_regression_consommation.ipynb", regression)]:
    path = DIRECTORY / name
    old = json.loads(path.read_text(encoding="utf-8"))
    snapshot = archive / (path.stem + "_avant_final_geo_v1.ipynb")
    if not snapshot.exists():
        shutil.copy2(path, snapshot)
    old["cells"] = cells
    path.write_text(json.dumps(old, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
