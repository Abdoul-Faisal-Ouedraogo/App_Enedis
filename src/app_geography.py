"""Références locales en lecture seule, conformément au notebook de préparation."""
import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.preparation_geography import GEO_CORRECTIONS


def notebook_climate_zones(path):
    """Lire les listes littérales H1/H2/H3, sans exécuter une cellule."""
    notebook = json.loads(Path(path).read_text(encoding="utf-8"))
    zones = {}
    found = set()
    for cell in notebook["cells"]:
        if cell.get("cell_type") != "code":
            continue
        try:
            tree = ast.parse("".join(cell["source"]))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"H1", "H2", "H3"}:
                    values = ast.literal_eval(node.value)
                    if target.id in found or not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                        raise ValueError("Définition climatique ambiguë")
                    found.add(target.id)
                    for department in values:
                        if department in zones:
                            raise ValueError("Département dans plusieurs zones climatiques")
                        zones[department] = target.id
    if found != {"H1", "H2", "H3"}:
        raise ValueError("Règles H1/H2/H3 locales introuvables")
    return zones


def read_geography(cities_path, notebook_path):
    cities = pd.read_csv(cities_path, usecols=["code_insee", "nom_standard", "dep_code", "dep_nom", "altitude_moyenne"],
                         dtype={"code_insee": "string", "dep_code": "string"}, low_memory=False)
    cities["code_insee"] = cities.code_insee.str.zfill(5)
    cities["dep_code"] = cities.dep_code.str.zfill(2)
    if cities.code_insee.isna().any() or cities.code_insee.duplicated().any():
        raise ValueError("Clés du référentiel communal non uniques")
    cities["altitude_moyenne"] = pd.to_numeric(cities.altitude_moyenne, errors="coerce").replace([np.inf, -np.inf], np.nan)
    # Exactement la règle de préparation : moyenne des communes du référentiel,
    # sans pondération par population ni par nombre de logements.
    means = cities.groupby("dep_code").altitude_moyenne.mean().to_dict()
    return {"cities": cities, "department_means": means, "zones": notebook_climate_zones(notebook_path)}


def commune_proposal(reference, code, department):
    original = str(code).zfill(5)
    department = str(department).zfill(2)
    corrected = GEO_CORRECTIONS.get(original, original)
    rows = reference["cities"].loc[lambda d: d.code_insee.eq(corrected)]
    # Un code inconnu ne crée jamais une commune : seul le repli départemental est disponible.
    altitude = float(rows.iloc[0].altitude_moyenne) if len(rows) else np.nan
    source = "Altitude moyenne communale"
    if not np.isfinite(altitude):
        altitude = reference["department_means"].get(department, np.nan)
        source = "Remplacement par la moyenne départementale des communes du référentiel"
    return {"original_code": original, "reference_code": corrected, "department": department,
            "commune": str(rows.iloc[0].nom_standard) if len(rows) else "Commune sans correspondance",
            "altitude": float(altitude) if np.isfinite(altitude) else None,
            "zone": reference["zones"].get(department), "source": source,
            "corrected": corrected != original}
