"""Rejouer le nettoyage local sans réseau ni écriture du CSV de travail."""
import contextlib
import io
import json
from pathlib import Path
import sys
import argparse
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from src.data_lineage import RAW_FIELDS, LINEAGE_FIELDS
from src.preparation_geography import export_prepared as real_export


def forbidden(*args, **kwargs):
    raise AssertionError("Accès réseau interdit pendant la vérification")


notebook = json.loads((ROOT / "Notebooks_Api_Traitement/1_data_preparation.ipynb").read_text(encoding="utf-8"))
namespace = {"__name__": "__notebook__"}
selection = next("".join(c["source"]) for c in notebook["cells"]
                 if c["cell_type"] == "code" and "features = [" in "".join(c["source"]))
exec(selection, namespace)
columns = set(namespace["features"]) | {"_geopoint"} | set(RAW_FIELDS)
read_csv = pd.read_csv
exports = []
native_to_csv = pd.DataFrame.to_csv
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--apply-geography", action="store_true", help="Exporter après contrôle, avec sauvegarde du CSV précédent")
args = parser.parse_args()


def read_local(path, *args, **kwargs):
    # Éviter de matérialiser les centaines de colonnes inutilisées des bruts.
    # Le notebook ne les utilise que pour les tableaux exploratoires.
    if Path(path).name in {"ademe_data_old.csv", "ademe_data_new.csv"}:
        kwargs["usecols"] = lambda name: name in columns
    return read_csv(path, *args, **kwargs)


def verify_export(frame):
    expected = read_csv(ROOT / "output/cleaned_data.csv", low_memory=False)
    actual = frame.drop(columns=LINEAGE_FIELDS).reset_index(drop=True).copy()
    # Comparer les valeurs après la même inférence CSV que dans les notebooks ML.
    for column in actual.columns:
        if pd.api.types.is_numeric_dtype(expected[column]):
            actual[column] = pd.to_numeric(actual[column], errors="raise")
    if args.apply_geography:
        codes = expected.code_insee_ban.astype(str)
        expected.loc[codes.isin([str(c) for c in range(69381, 69390)]), "altitude_moyenne"] = 237.0
        expected.loc[codes.eq("69152"), "altitude_moyenne"] = 194.0
    pd.testing.assert_frame_equal(actual, expected, check_dtype=False, rtol=1e-12, atol=1e-9)
    assert not frame.numero_dpe.isna().any()
    assert not frame.numero_dpe.duplicated().any()
    exports.append(len(actual))
    if args.apply_geography:
        with patch.object(pd.DataFrame, "to_csv", native_to_csv):
            return real_export(frame)
    metadata = read_csv(ROOT / "output/cleaned_data_metadata.csv", dtype={c: "string" for c in RAW_FIELDS})
    for column in LINEAGE_FIELDS:
        pd.testing.assert_series_equal(frame[column].reset_index(drop=True).astype("string"),
                                       metadata[column].astype("string"), check_names=False)
    return {"version": "vérification sans écriture"}


with (patch("requests.sessions.Session.request", forbidden),
      patch.object(pd, "read_csv", read_local),
      patch.object(pd.DataFrame, "to_csv", forbidden),
      patch("src.preparation_geography.export_prepared", verify_export)):
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        print(f"Cellule {index}", flush=True) if index in (15, 17, 38, 83, 96) else None
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                exec(compile("".join(cell["source"]), f"preparation:cell{index}", "exec"), namespace)
        except Exception as exc:
            raise RuntimeError(f"Préparation, cellule {index}") from exc
        plt.close("all")
assert exports == [616057], exports
print("OK : préparation reproduite depuis les bruts locaux, sans réseau ; "
      + ("CSV corrigé exporté avec sauvegarde" if args.apply_geography else "CSV et traçabilité vérifiés sans écriture"))
