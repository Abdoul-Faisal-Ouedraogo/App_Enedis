"""Vérifier les liens transitifs et la séparation conservatrice des groupes."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
from src.validation_plan import connected_groups

# A et B ont la même adresse. B et C partagent un immeuble ; D remplace C.
# E et F référencent le même ancien diagnostic absent du fichier.
sample = pd.DataFrame({
    "numero_dpe": ["a", "b", "c", "d", "e", "f", "g"],
    "identifiant_ban": ["adresse1", "adresse1", "adresse2", pd.NA, "adresse3", "adresse4", pd.NA],
    "numero_dpe_immeuble_associe": [pd.NA, "immeuble", "immeuble", pd.NA, pd.NA, pd.NA, pd.NA],
    "numero_dpe_remplace": [pd.NA, pd.NA, pd.NA, "c", "absent", "absent", pd.NA],
}, dtype="string")
groups = connected_groups(sample)
assert len(set(groups[:4])) == 1
assert groups[4] == groups[5]
assert len(set(groups[[0, 4, 6]])) == 3

split = pd.read_csv(ROOT / "output/classification_split.csv")
metadata = pd.read_csv(ROOT / "output/cleaned_data_metadata.csv", dtype="string")
dates = pd.to_datetime(metadata.date_reception_dpe, utc=True, errors="raise")
names = ["train", "validation", "reserved"]
for i, left in enumerate(names):
    for right in names[i + 1:]:
        assert not set(split.loc[split.partition.eq(left), "group"]) & set(split.loc[split.partition.eq(right), "group"])
assert dates[split.partition.eq("train")].max() < dates[split.partition.eq("validation")].min()
assert dates[split.partition.eq("validation")].max() < dates[split.partition.eq("reserved")].min()
assert not np.any(split.comparison_train & ~split.partition.eq("train"))
print("OK : liens transitifs adresse/immeuble/remplacement et séparation chronologique des groupes")
