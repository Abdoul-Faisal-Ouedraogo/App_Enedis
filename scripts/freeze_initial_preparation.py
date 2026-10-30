"""Recalculer UNE FOIS les bornes historiques, en lecture seule des CSV sources."""
import json
from pathlib import Path
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.preparation_geography import sha256
from src.version_store import atomic_json


def build_profile():
    manifest=json.loads((ROOT/"output/preparation_manifest.json").read_text(encoding="utf-8"))
    parts=[]
    for source in ["ademe_data_old.csv","ademe_data_new.csv"]:
        path=ROOT/"data"/source
        if sha256(path)!=manifest["raw_sources"][source]:
            raise ValueError("Source initiale différente du manifeste : "+source)
        usecols=["cout_total_5_usages","surface_habitable_logement"]
        if source.endswith("old.csv"):
            usecols.append("annee_construction")
        for chunk in pd.read_csv(path,usecols=usecols,chunksize=100000,low_memory=False):
            if source.endswith("new.csv"):
                chunk["annee_construction"]=2026
            for col in chunk:
                chunk[col]=pd.to_numeric(chunk[col],errors="coerce")
            # Ordre exact du notebook avant le premier IQR : année connue, âge non négatif,
            # puis coût connu. Pas de filtre spécifique au petit lot reçu.
            chunk=chunk.loc[chunk.annee_construction.notna() & chunk.annee_construction.le(2026)
                            & chunk.cout_total_5_usages.notna()]
            parts.append(chunk[["cout_total_5_usages","surface_habitable_logement"]])
    frame=pd.concat(parts,ignore_index=True)
    bounds={}
    for col in ["cout_total_5_usages","surface_habitable_logement"]:
        q1,q3=frame[col].quantile([.25,.75])
        low,high=float(q1-1.5*(q3-q1)),float(q3+1.5*(q3-q1))
        before=len(frame)
        frame=frame[frame[col].between(low,high)].copy()
        bounds[col]={"q1":float(q1),"q3":float(q3),"lower":low,"upper":high,"reference_rows_before":before,"reference_rows_after":len(frame)}
    original=ROOT/"output/cleaned_data.csv"
    if sha256(original)!=manifest["data_sha256"]:
        raise ValueError("CSV préparé initial altéré")
    data=pd.read_csv(original,usecols=list(bounds))
    assert all(data[col].between(b["lower"],b["upper"]).all() for col,b in bounds.items())
    return {"id":"initial_geo_v1_iqr_v1","mode":"frozen_initial_iqr","reference_year":2026,
            "reference_data_sha256":manifest["data_sha256"],"raw_sources_sha256":{name:manifest["raw_sources"][name] for name in ["ademe_data_old.csv","ademe_data_new.csv"]},
            "notebook_sha256":sha256(ROOT/"Notebooks_Api_Traitement/1_data_preparation.ipynb"),
            "derivation":"Ordre du notebook 1 : année non manquante, âge >= 0, coût non manquant, IQR coût, puis IQR surface. Quantiles linéaires pandas, facteur 1.5, bornes inclusives.",
            "bounds":bounds,"verified_initial_rows":len(data)}


if __name__=="__main__":
    path=ROOT/"config/preparation_initial_geo_v1.json"
    if path.exists():
        raise SystemExit("Profil déjà figé : ne pas le remplacer automatiquement")
    profile=build_profile()
    atomic_json(path,profile)
    print(json.dumps(profile,ensure_ascii=False,indent=2))
