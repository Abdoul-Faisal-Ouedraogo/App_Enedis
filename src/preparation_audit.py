"""Préparation stable et motifs de rejet ligne par ligne, sans écriture ni entraînement."""
from collections import Counter
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from src.app_geography import commune_proposal
from src.data_lineage import LINEAGE_FIELDS
from src.processing.data_cleaner import DataCleaner
from src.project_paths import ROOT

LABELS = {
    "reception_missing":"Date de réception absente ou invalide",
    "established_missing":"Date d’établissement absente ou invalide",
    "date_order":"Date d’établissement postérieure à la réception",
    "future_reception":"Date de réception future au moment de la préparation",
    "identifier_missing":"Numéro DPE absent",
    "construction_missing":"Année de construction absente ou non numérique",
    "negative_age":"Année de construction postérieure à 2026",
    "surface_missing":"Surface habitable absente ou non numérique",
    "surface_nonpositive":"Surface habitable nulle ou négative",
    "consumption_missing":"Consommation absente ou non numérique",
    "consumption_negative":"Consommation négative",
    "dpe_invalid":"Classe DPE absente ou hors A–G",
    "building_invalid":"Type de bâtiment absent ou incompatible",
    "cost_missing":"Coût des cinq usages absent ou non numérique",
    "cost_iqr":"Coût des cinq usages hors des bornes IQR de référence",
    "surface_iqr":"Surface habitable hors des bornes IQR de référence",
    "levels_missing":"Nombre de niveaux absent ou non numérique",
    "levels_invalid":"Nombre de niveaux non entier ou hors de 1 à 10",
    "altitude_missing":"Altitude indisponible dans les références communale/départementale",
    "climate_missing":"Zone climatique H1/H2/H3 non définie par le référentiel",
    "duplicate_batch":"Doublon de numéro DPE dans le lot (seule la réception la plus récente est gardée)",
    "duplicate_base":"Numéro DPE déjà présent dans la version de base",
    "stale_replacement":"Remplaçant reçu avant le diagnostic qu’il remplace",
    "replaced_in_batch":"Diagnostic reçu remplacé par un autre diagnostic du lot",
}
DUPLICATE_CODES={"duplicate_batch","duplicate_base"}


def stable_policy():
    path=ROOT/"config/preparation_initial_geo_v1.json"
    policy=json.loads(path.read_text(encoding="utf-8"))
    manifest=json.loads((ROOT/"MLmodels/final_models.json").read_text(encoding="utf-8"))
    if policy["mode"]!="frozen_initial_iqr" or policy["reference_year"]!=2026 or policy["reference_data_sha256"]!=manifest["data_sha256"]:
        raise ValueError("Profil de préparation incompatible avec la référence initiale")
    for name in ["cout_total_5_usages","surface_habitable_logement"]:
        values=policy["bounds"][name]
        if not np.isfinite([values["lower"],values["upper"]]).all() or values["lower"]>values["upper"]:
            raise ValueError("Bornes figées invalides")
    return policy


def mark(audit, indices, reason):
    for index in indices:
        row=audit["rows"][int(index)]
        if reason not in row["reasons"]:
            row["reasons"].append(reason)
        if row["primary_reason"] is None:
            row["primary_reason"]=reason


def refresh_counts(audit):
    audit["primary_counts"]=dict(Counter(row["primary_reason"] for row in audit["rows"] if row["primary_reason"]))
    audit["all_reason_counts"]=dict(Counter(reason for row in audit["rows"] for reason in row["reasons"]))
    audit["labels"]={key:LABELS[key] for key in audit["all_reason_counts"]}
    audit["kept"]=sum(row["primary_reason"] is None for row in audit["rows"])
    return audit


def prepare_audited(raw,source,reference,policy=None,as_of=None):
    policy=stable_policy() if policy is None else policy
    if policy.get("mode") not in {"frozen_initial_iqr","batch_iqr"}:
        raise ValueError("Politique de préparation inconnue")
    frame=pd.DataFrame(raw).copy()
    required=["numero_dpe","date_reception_dpe","date_etablissement_dpe","annee_construction","cout_total_5_usages",
              "surface_habitable_logement","nombre_niveau_logement","conso_5_usages_ef","code_insee_ban",
              "code_departement_ban","etiquette_dpe","type_batiment","type_energie_principale_chauffage"]
    if source=="neuf":
        frame["annee_construction"]=2026
    if set(required)-set(frame):
        raise ValueError("Champs ADEME absents : "+", ".join(sorted(set(required)-set(frame))))
    frame["_source_row"]=np.arange(len(frame))
    frame["_source_dataset"]=source
    for col in LINEAGE_FIELDS:
        if col not in frame:
            frame[col]=pd.NA
    for col in ["annee_construction","cout_total_5_usages","surface_habitable_logement","nombre_niveau_logement","conso_5_usages_ef"]:
        frame[col]=pd.to_numeric(frame[col],errors="coerce").replace([np.inf,-np.inf],np.nan)
    frame["age_batiment"]=2026-frame.annee_construction
    instant=pd.Timestamp(as_of or datetime.now(timezone.utc))
    audit={"policy":policy["id"],"evaluated_at":instant.isoformat(),"thresholds":{},"stages":[],
           "rows":[{"source_row":i,"primary_reason":None,"reasons":[]} for i in range(len(frame))]}
    active=pd.Series(True,index=frame.index)
    def reject(reason,bad):
        nonlocal active
        bad=bad.fillna(False)
        for index in frame.index[bad]:
            if reason not in audit["rows"][int(index)]["reasons"]:
                audit["rows"][int(index)]["reasons"].append(reason)
        selected=frame.index[bad & active]
        mark(audit,selected,reason)
        active &= ~bad
        audit["stages"].append({"reason":reason,"rejected":len(selected),"remaining":int(active.sum())})
    reception=pd.to_datetime(frame.date_reception_dpe,utc=True,errors="coerce",format="mixed")
    established=pd.to_datetime(frame.date_etablissement_dpe,utc=True,errors="coerce",format="mixed")
    checks=[("reception_missing",reception.isna()),("established_missing",established.isna()),
            ("date_order",established>reception),("future_reception",reception>instant),
            ("identifier_missing",frame.numero_dpe.isna()|frame.numero_dpe.astype(str).str.strip().eq("")),
            ("construction_missing",frame.annee_construction.isna()),("negative_age",frame.age_batiment<0),
            ("surface_missing",frame.surface_habitable_logement.isna()),("surface_nonpositive",frame.surface_habitable_logement<=0),
            ("consumption_missing",frame.conso_5_usages_ef.isna()),("consumption_negative",frame.conso_5_usages_ef<0),
            ("dpe_invalid",~frame.etiquette_dpe.isin(list("ABCDEFG"))),
            ("building_invalid",~frame.type_batiment.isin(["appartement","immeuble","maison"]))]
    for reason,bad in checks:
        reject(reason,bad)
    reject("cost_missing",frame.cout_total_5_usages.isna())
    for col,reason in [("cout_total_5_usages","cost_iqr"),("surface_habitable_logement","surface_iqr")]:
        if policy["mode"]=="batch_iqr":
            q1,q3=frame.loc[active,col].quantile([.25,.75])
            low,high=q1-1.5*(q3-q1),q3+1.5*(q3-q1)
        else:
            low,high=policy["bounds"][col]["lower"],policy["bounds"][col]["upper"]
        audit["thresholds"][col]={"lower":float(low) if pd.notna(low) else None,"upper":float(high) if pd.notna(high) else None,
                                    "rows_before":int(active.sum())}
        # Ne pas ajouter des motifs IQR secondaires à des lignes déjà éliminées avant ce filtre.
        reject(reason,active & ~frame[col].between(low,high))
    reject("levels_missing",frame.nombre_niveau_logement.isna())
    reject("levels_invalid",frame.nombre_niveau_logement.notna() & (~frame.nombre_niveau_logement.between(1,10)|frame.nombre_niveau_logement.ne(frame.nombre_niveau_logement.round())))
    kept=frame.loc[active].copy()
    cleaner=DataCleaner.__new__(DataCleaner)
    cleaner.df=kept
    cleaner.energie_type_cleaning()
    kept=cleaner.df.copy()
    kept["code_insee_ban"]=kept.code_insee_ban.astype("string").str.zfill(5)
    kept["code_departement_ban"]=kept.code_departement_ban.astype("string").str.zfill(2)
    proposals=[commune_proposal(reference,code,dep) for code,dep in zip(kept.code_insee_ban,kept.code_departement_ban)]
    kept["altitude_moyenne"]=[p["altitude"] for p in proposals]
    kept["zone_climatique"]=[p["zone"] for p in proposals]
    for col,reason in [("altitude_moyenne","altitude_missing"),("zone_climatique","climate_missing")]:
        mark(audit,kept.index[kept[col].isna()],reason)
    kept=kept.dropna(subset=["altitude_moyenne","zone_climatique"])
    if "_geopoint" in kept:
        coords=kept._geopoint.astype(str).str.split(",",expand=True).reindex(columns=[0,1])
        kept["lat"],kept["lon"]=pd.to_numeric(coords[0],errors="coerce"),pd.to_numeric(coords[1],errors="coerce")
    for col in ["lat","lon","nom_commune_ban","code_postal_ban"]:
        if col not in kept:
            kept[col]=np.nan
    refresh_counts(audit)
    assert audit["kept"]==len(kept)
    return kept,audit
