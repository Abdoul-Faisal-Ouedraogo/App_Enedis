"""Vérifier que seule l'altitude des communes corrigées a changé."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
from src.ml_workflow import load_data, reference_data_path
from src.preparation_geography import GEO_CORRECTIONS, join_commune_altitudes, sha256

before = load_data(reference_data_path())
after = load_data()
assert len(before) == len(after) == 616057
pd.testing.assert_frame_equal(before.drop(columns="altitude_moyenne"), after.drop(columns="altitude_moyenne"))
changed = ~np.isclose(before.altitude_moyenne, after.altitude_moyenne)
assert int(changed.sum()) == 2103
expected_mask = after.code_insee_ban.isin(GEO_CORRECTIONS)
np.testing.assert_array_equal(changed, expected_mask)
assert not after.altitude_moyenne.isna().any()
assert after.zone_climatique.equals(before.zone_climatique)
cities = pd.read_csv(ROOT / "data/communes-france-2025.csv", dtype={"code_insee": str}, low_memory=False)
assert not cities.code_insee.duplicated().any()
target = after.code_insee_ban[changed].replace(GEO_CORRECTIONS).map(cities.set_index("code_insee").altitude_moyenne)
np.testing.assert_allclose(after.loc[changed, "altitude_moyenne"], target)
audit = before.loc[changed, ["code_insee_ban", "altitude_moyenne"]].copy()
audit.columns = ["code_insee_ban", "altitude_before"]
audit["altitude_after"] = after.loc[changed, "altitude_moyenne"]
summary = audit.groupby(["code_insee_ban", "altitude_before", "altitude_after"]).size().reset_index(name="rows")

# Les jointures doivent refuser des références ambiguës ou incomplètes.
sample = after.loc[changed, ["code_insee_ban"]].head(3)
for bad_reference in [pd.concat([cities, cities.iloc[[0]]]), cities[~cities.code_insee.eq("69123")]]:
    try:
        join_commune_altitudes(sample, bad_reference)
    except ValueError:
        pass
    else:
        raise AssertionError("Une référence ambiguë ou incomplète a été acceptée")

report = {"before_sha256": sha256(reference_data_path()), "after_sha256": sha256(ROOT / "output/cleaned_data.csv"),
          "rows": len(after), "changed_altitudes": int(changed.sum()), "other_columns_unchanged": True,
          "climate_unchanged": True, "commune_keys_unique": True, "negative_join_checks_passed": True,
          "changes": summary.to_dict(orient="records")}
(ROOT / "output/geography_correction_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
