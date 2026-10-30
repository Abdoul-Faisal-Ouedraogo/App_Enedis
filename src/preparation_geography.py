"""Corrections de Nouhayla appliquées aux clés de jointure, sans changer le climat."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

import numpy as np
import pandas as pd

from src.data_lineage import LINEAGE_FIELDS
from src.project_paths import ROOT, DATA_PATH

GEO_CORRECTIONS = {**{str(code): "69123" for code in range(69381, 69390)}, "69152": "69149"}


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def backup_file(path):
    path = Path(path)
    digest = sha256(path)
    folder = ROOT / "output" / "backups"
    folder.mkdir(exist_ok=True)
    backup = folder / f"{path.stem}_{digest[:16]}{path.suffix}"
    if backup.exists():
        if sha256(backup) != digest:
            raise ValueError(f"Sauvegarde existante incohérente : {backup}")
    else:
        shutil.copy2(path, backup)
    return backup


def join_commune_altitudes(frame, cities):
    """Jointure validée n:1, conservation du code INSEE original et de l'ordre."""
    reference = cities[["code_insee", "altitude_moyenne"]].copy()
    reference["code_insee"] = reference.code_insee.astype("string").str.zfill(5)
    if reference.code_insee.isna().any() or reference.code_insee.duplicated().any():
        raise ValueError("La table des communes contient des clés manquantes ou dupliquées")
    target = reference.set_index("code_insee").altitude_moyenne.reindex(set(GEO_CORRECTIONS.values()))
    if target.isna().any() or not np.isfinite(target.to_numpy()).all():
        raise ValueError("Les communes corrigées n'ont pas d'altitude de référence valide")
    work = frame.copy()
    work["code_insee_jointure"] = work.code_insee_ban.astype("string").str.zfill(5).replace(GEO_CORRECTIONS)
    result = work.merge(reference, left_on="code_insee_jointure", right_on="code_insee",
                        how="left", sort=False, validate="many_to_one")
    if len(result) != len(frame):
        raise AssertionError("La jointure a modifié le nombre de logements")
    np.testing.assert_array_equal(result.code_insee_ban, frame.code_insee_ban.to_numpy())
    return result


def atomic_csv(frame, path):
    # L'ancien fichier est sauvegardé par l'appelant avant tout remplacement.
    with tempfile.NamedTemporaryFile(dir=Path(path).parent, suffix=".csv", delete=False) as temp:
        temporary = Path(temp.name)
    frame.to_csv(temporary, index=False)
    os.replace(temporary, path)


def export_prepared(frame):
    """Exporter les données ML et leur traçabilité séparée, avec sauvegardes."""
    missing = set(LINEAGE_FIELDS) - set(frame.columns)
    if missing:
        raise ValueError(f"Traçabilité absente : {sorted(missing)}")
    metadata = frame[LINEAGE_FIELDS].reset_index(drop=True).copy()
    metadata.insert(0, "cleaned_row", np.arange(len(metadata)))
    if metadata[["_source_dataset", "_source_row"]].duplicated().any():
        raise ValueError("Une ligne brute a été multipliée par les jointures")
    cleaned = frame.drop(columns=LINEAGE_FIELDS + ["code_insee_jointure", "code_insee"], errors="ignore").reset_index(drop=True)
    if cleaned.altitude_moyenne.isna().any() or not np.isfinite(cleaned.altitude_moyenne).all():
        raise ValueError("Altitudes finales invalides")
    if not cleaned.zone_climatique.isin(["H1", "H2", "H3"]).all():
        raise ValueError("Les zones H1/H2/H3 doivent être conservées")
    backups = {}
    for path in [DATA_PATH, ROOT / "output/cleaned_data_metadata.csv", ROOT / "output/preparation_manifest.json"]:
        if path.exists():
            backups[path.name] = backup_file(path).relative_to(ROOT).as_posix()
    # La référence des anciens modèles est figée une seule fois, avant migration.
    reference_path = ROOT / "MLmodels/data_reference.json"
    if not reference_path.exists() and DATA_PATH.exists():
        legacy_report = json.loads((ROOT / "MLmodels/classification_common.json").read_text(encoding="utf-8"))
        if sha256(DATA_PATH) != legacy_report["data_sha256"]:
            raise ValueError("Le CSV initial ne correspond pas à la référence des modèles historiques")
        reference = {"data_path": backups[DATA_PATH.name], "data_sha256": sha256(DATA_PATH),
            "note": "Données antérieures aux corrections géographiques ; anciens scores uniquement.",
            "regression_model_sha256": sha256(ROOT / "MLmodels/pipeline_random_forest_consommation.pkl")}
        reference_path.write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    atomic_csv(cleaned, DATA_PATH)
    metadata_path = ROOT / "output/cleaned_data_metadata.csv"
    atomic_csv(metadata, metadata_path)
    manifest = {"version": "geo-nouhayla-2026-10-29", "rows": len(cleaned),
        "data_sha256": sha256(DATA_PATH), "metadata_sha256": sha256(metadata_path),
        "metadata_path": metadata_path.relative_to(ROOT).as_posix(), "backups": backups,
        "reference_year": 2026, "climate_zones": ["H1", "H2", "H3"],
        "geo_corrections": GEO_CORRECTIONS,
        "raw_sources": {name: sha256(ROOT / "data" / name)
                        for name in ["ademe_data_old.csv", "ademe_data_new.csv", "communes-france-2025.csv"]}}
    (ROOT / "output/preparation_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Export : {len(cleaned):,} logements ; traçabilité séparée ; sauvegardes : {backups}")
    return manifest
