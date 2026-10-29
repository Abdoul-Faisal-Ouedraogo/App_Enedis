"""Contrôler dates et identifiants des bruts, sans téléchargement ni entraînement."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
from src.data_lineage import RAW_FIELDS


def audit_raw():
    frames = []
    for source, name in [("existant", "ademe_data_old.csv"), ("neuf", "ademe_data_new.csv")]:
        frame = pd.read_csv(ROOT / "data" / name, usecols=RAW_FIELDS, dtype="string", low_memory=False)
        frame.insert(0, "_source_dataset", source)
        frames.append(frame)
        print(f"Métadonnées lues : {source}, {len(frame)} lignes", flush=True)
    data = pd.concat(frames, ignore_index=True)
    result = {"as_of": "2026-10-29", "sources": {}, "rows": len(data)}
    for source, frame in [("ensemble", data)] + list(data.groupby("_source_dataset")):
        entry = {"rows": len(frame), "identifiers": {}, "dates": {}}
        for name in ["numero_dpe", "numero_dpe_remplace", "identifiant_ban", "numero_dpe_immeuble_associe"]:
            values = frame[name].str.strip().replace("", pd.NA)
            entry["identifiers"][name] = {"missing": int(values.isna().sum()),
                "distinct": int(values.nunique()), "duplicate_excess": int(values.dropna().duplicated().sum())}
        for name in ["date_reception_dpe", "date_etablissement_dpe", "date_visite_diagnostiqueur"]:
            dates = pd.to_datetime(frame[name], errors="coerce", format="mixed", utc=True)
            entry["dates"][name] = {"missing": int(frame[name].isna().sum()),
                "invalid_nonmissing": int((frame[name].notna() & dates.isna()).sum()),
                "min": str(dates.min()), "max": str(dates.max()),
                "after_audit_date": int((dates >= pd.Timestamp("2026-10-30", tz="Europe/Paris")).sum()),
                "by_month": dates.dt.strftime("%Y-%m").value_counts().sort_index().to_dict()}
        reception = pd.to_datetime(frame.date_reception_dpe, errors="coerce", format="mixed", utc=True)
        established = pd.to_datetime(frame.date_etablissement_dpe, errors="coerce", format="mixed", utc=True)
        entry["established_after_reception"] = int((established > reception).sum())
        result["sources"][source] = entry
    ids = set(data.numero_dpe.dropna())
    result["replacement_links_to_present_dpe"] = int(data.numero_dpe_remplace.isin(ids).sum())
    left, right = frames
    result["dpe_ids_in_both_sources"] = len(set(left.numero_dpe.dropna()) & set(right.numero_dpe.dropna()))
    target = ROOT / "output" / "raw_metadata_audit.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return result


if __name__ == "__main__":
    audit_raw()
