"""Expliquer la composition des partitions ; pas de cibles réservées avant gel."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
from src.ml_workflow import load_data

data = load_data()
metadata = pd.read_csv(ROOT / "output/cleaned_data_metadata.csv", dtype="string")
split = pd.read_csv(ROOT / "output/classification_split.csv")
raw = json.loads((ROOT / "output/raw_metadata_audit.json").read_text(encoding="utf-8"))
dates = pd.to_datetime(metadata.date_reception_dpe, utc=True)
mask2024 = dates.dt.year.eq(2024)
result = {
    "raw_2024_sources": {source: sum(count for month, count in raw["sources"][source]["dates"]["date_reception_dpe"]["by_month"].items() if month.startswith("2024-"))
                         for source in ["existant", "neuf"]},
    "cleaned_2024_before_group_exclusions": metadata.loc[mask2024, "_source_dataset"].value_counts().to_dict(),
    "validation_after_exclusions": metadata.loc[split.partition.eq("validation"), "_source_dataset"].value_counts().to_dict(),
    "excluded_2024": metadata.loc[mask2024 & split.partition.eq("excluded"), "_source_dataset"].value_counts().to_dict(),
    "partitions": {},
    "reserved_class_distribution": "Différée jusqu'au gel des choix, pour ne pas orienter la sélection."
}
for name in ["train", "validation", "reserved", "excluded"]:
    mask = split.partition.eq(name)
    result["partitions"][name] = {"rows": int(mask.sum()), "sources": metadata.loc[mask, "_source_dataset"].value_counts().to_dict()}
    if name not in ["reserved", "excluded"]:
        result["partitions"][name]["class_by_source"] = pd.crosstab(metadata.loc[mask, "_source_dataset"], data.loc[mask, "etiquette_dpe"]).to_dict(orient="index")
path = ROOT / "output/partition_composition_before_selection.json"
path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
