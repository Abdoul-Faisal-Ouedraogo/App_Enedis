"""Séparation chronologique et par groupes, sans consulter les cibles du lot réservé."""
import json

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from src.project_paths import ROOT, DATA_PATH
from src.preparation_geography import sha256

TRAIN_END = "2024-01-01"
VALIDATION_END = "2025-01-01"
TRAIN_CAP = 60000
CANDIDATES = [
    {"name": "rf_depth10_balanced", "max_depth": 10, "min_samples_split": 20, "min_samples_leaf": 1, "class_weight": "balanced"},
    {"name": "rf_depth20_balanced", "max_depth": 20, "min_samples_split": 20, "min_samples_leaf": 1, "class_weight": "balanced"},
    {"name": "rf_depth20_unweighted", "max_depth": 20, "min_samples_split": 20, "min_samples_leaf": 1, "class_weight": None},
]


def connected_groups(metadata):
    """Lier adresses BAN, immeubles associés et diagnostics remplacés, transitivement."""
    parent = np.arange(len(metadata))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(a, b):
        left, right = find(a), find(b)
        if left != right:
            parent[max(left, right)] = min(left, right)

    address_registry = {}
    for index, value in enumerate(metadata.identifiant_ban):
        if pd.notna(value):
            if value in address_registry:
                union(index, address_registry[value])
            else:
                address_registry[value] = index
    dpe_registry = {}
    for field in ["numero_dpe", "numero_dpe_immeuble_associe", "numero_dpe_remplace"]:
        for index, value in enumerate(metadata[field]):
            if pd.notna(value):
                if value in dpe_registry:
                    union(index, dpe_registry[value])
                else:
                    dpe_registry[value] = index
    return np.array([find(i) for i in range(len(metadata))])


def make_plan(data):
    manifest = json.loads((ROOT / "output/preparation_manifest.json").read_text(encoding="utf-8"))
    metadata_path = ROOT / "output/cleaned_data_metadata.csv"
    if sha256(DATA_PATH) != manifest["data_sha256"] or sha256(metadata_path) != manifest["metadata_sha256"]:
        raise ValueError("Les données et la traçabilité ne correspondent pas au manifeste")
    metadata = pd.read_csv(metadata_path, dtype="string").replace(r"^\s*$", pd.NA, regex=True)
    if len(metadata) != len(data) or not np.array_equal(metadata.cleaned_row.astype(int), np.arange(len(data))):
        raise ValueError("L'alignement entre données et traçabilité est perdu")
    if metadata.numero_dpe.isna().any() or metadata.numero_dpe.duplicated().any():
        raise ValueError("Numéros DPE manquants ou dupliqués dans les données nettoyées")
    reception = pd.to_datetime(metadata.date_reception_dpe, format="mixed", errors="coerce", utc=True)
    established = pd.to_datetime(metadata.date_etablissement_dpe, format="mixed", errors="coerce", utc=True)
    valid_date = reception.notna() & established.notna() & (established <= reception)
    valid_date &= reception < pd.Timestamp("2026-10-30", tz="Europe/Paris")
    groups = connected_groups(metadata)
    known_geo = metadata.identifiant_ban.notna() | metadata.numero_dpe_immeuble_associe.notna()
    known_group = pd.Series(known_geo.to_numpy()).groupby(groups).transform("any").to_numpy()
    period = np.where(reception < pd.Timestamp(TRAIN_END, tz="UTC"), 0,
                      np.where(reception < pd.Timestamp(VALIDATION_END, tz="UTC"), 1, 2))
    eligible = valid_date.to_numpy() & known_group
    temporal = pd.DataFrame({"group": groups[eligible], "period": period[eligible]})
    spans = temporal.groupby("group").period.nunique()
    crossing = np.isin(groups, spans.index[spans > 1])
    keep = eligible & ~crossing
    labels = np.full(len(data), "excluded", dtype=object)
    for index, name in enumerate(["train", "validation", "reserved"]):
        labels[keep & (period == index)] = name
    assignments = pd.DataFrame({"cleaned_row": np.arange(len(data)), "group": groups, "partition": labels})
    used_groups = [set(groups[labels == label]) for label in ["train", "validation", "reserved"]]
    assert all(not used_groups[i] & used_groups[j] for i in range(3) for j in range(i + 1, 3))
    # Vérification complémentaire de chaque famille d'identifiants, sans regarder y.
    for field in ["numero_dpe", "identifiant_ban", "numero_dpe_immeuble_associe", "numero_dpe_remplace"]:
        sets = [set(metadata.loc[labels == name, field].dropna()) for name in ["train", "validation", "reserved"]]
        assert all(not sets[i] & sets[j] for i in range(3) for j in range(i + 1, 3)), field
    train_indices = np.flatnonzero(labels == "train")
    validation_indices = np.flatnonzero(labels == "validation")
    if not len(train_indices) or not len(validation_indices):
        raise ValueError("Séparation chronologique vide ; examiner les métadonnées sans entraîner")
    if len(train_indices) > TRAIN_CAP:
        train_indices, _ = train_test_split(train_indices, train_size=TRAIN_CAP, random_state=42,
                                           stratify=data.iloc[train_indices].etiquette_dpe)
    assignments["comparison_train"] = False
    assignments.loc[train_indices, "comparison_train"] = True
    summary = {"data_sha256": manifest["data_sha256"], "metadata_sha256": manifest["metadata_sha256"],
        "train_end_exclusive": TRAIN_END, "validation_end_exclusive": VALIDATION_END,
        "date_used": "date_reception_dpe", "date_rule": "date_etablissement_dpe <= date_reception_dpe ; date non future",
        "rows": len(data), "counts": assignments.partition.value_counts().to_dict(),
        "excluded_invalid_dates": int((~valid_date).sum()),
        "excluded_no_address_or_building_group": int((valid_date.to_numpy() & ~known_group).sum()),
        "excluded_crossing_groups": int((eligible & crossing).sum()),
        "grouping": "Composantes connexes BAN + immeuble associé + DPE remplacé ; groupes traversant les périodes exclus",
        "comparison_train_rows": len(train_indices), "comparison_validation_rows": len(validation_indices),
        "train_cap": TRAIN_CAP, "seed": 42, "fit_count": len(CANDIDATES), "trees_per_fit": 100, "n_jobs": 2,
        "candidates": CANDIDATES, "selection_metric": "F1 macro sur validation, classes A à G fixées",
        "tie_rule": "En cas d'égalité à 0.001 près, retenir le premier candidat dans l'ordre déclaré",
        "reserved_policy": "Aucune métrique ni sélection sur le lot réservé. Il reste interne à des données historiquement exploitées, pas externe.",
        "limitations": ["Filtres IQR et regroupement des énergies déjà calculés avant cette séparation",
                        "BAN est un identifiant d'adresse, pas une garantie d'identité physique du bâtiment",
                        "Groupes construits parmi les lignes nettoyées, liens transitifs via des lignes éliminées non garantis",
                        "Échantillonnage des bruts non aléatoire et changement de proportion neuf/existant à contrôler"],
        "partitions": {}}
    for name in ["train", "validation", "reserved"]:
        mask = labels == name
        entry = {"rows": int(mask.sum()), "groups": len(set(groups[mask])),
                 "reception_min": str(reception[mask].min()), "reception_max": str(reception[mask].max()),
                 "sources": metadata.loc[mask, "_source_dataset"].value_counts().to_dict()}
        if name != "reserved":
            entry["classes"] = data.loc[mask, "etiquette_dpe"].value_counts().sort_index().to_dict()
        summary["partitions"][name] = entry
    return assignments, summary
