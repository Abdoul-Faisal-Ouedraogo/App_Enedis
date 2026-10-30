"""Préparation incrémentale et nouvelles copies de données ; jamais d'écriture des originaux."""
import uuid
import numpy as np
import pandas as pd

from src.app_geography import read_geography, commune_proposal
from src.data_lineage import LINEAGE_FIELDS
from src.ml_workflow import NUMERIC, CATEGORICAL
from src.processing.data_cleaner import DataCleaner
from src.project_paths import ROOT
from src.preparation_geography import sha256
from src.version_store import VersionStore, atomic_json, now


def prepare_received(raw, source, reference):
    frame = pd.DataFrame(raw).copy()
    required = ["numero_dpe", "date_reception_dpe", "date_etablissement_dpe", "annee_construction",
                "cout_total_5_usages", "surface_habitable_logement", "nombre_niveau_logement", "conso_5_usages_ef",
                "code_insee_ban", "code_departement_ban", "etiquette_dpe", "type_batiment", "type_energie_principale_chauffage"]
    if source == "neuf":
        frame["annee_construction"] = 2026
    missing = set(required) - set(frame)
    if missing:
        raise ValueError("Champs ADEME absents : " + ", ".join(sorted(missing)))
    frame["_source_row"] = np.arange(len(frame))
    frame["_source_dataset"] = source
    for col in LINEAGE_FIELDS:
        if col not in frame:
            frame[col] = pd.NA
    for col in ["annee_construction", "cout_total_5_usages", "surface_habitable_logement", "nombre_niveau_logement", "conso_5_usages_ef"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
    frame["age_batiment"] = 2026 - frame.annee_construction
    reception = pd.to_datetime(frame.date_reception_dpe, utc=True, errors="coerce", format="mixed")
    established = pd.to_datetime(frame.date_etablissement_dpe, utc=True, errors="coerce", format="mixed")
    keep = reception.notna() & established.notna() & (established <= reception) & (reception <= pd.Timestamp.now(tz="UTC"))
    keep &= frame.numero_dpe.notna() & frame.numero_dpe.astype(str).str.strip().ne("")
    keep &= frame.age_batiment.ge(0) & frame.surface_habitable_logement.gt(0) & frame.conso_5_usages_ef.ge(0)
    keep &= frame.etiquette_dpe.isin(list("ABCDEFG")) & frame.type_batiment.isin(["appartement", "immeuble", "maison"])
    frame = frame.loc[keep].copy()
    # Réutiliser les méthodes de nettoyage existantes sans leur constructeur ancien
    # (qui exige un autre fichier climat absent) ni ses méthodes d'export.
    cleaner = DataCleaner.__new__(DataCleaner)
    cleaner.df = frame
    cleaner.cost_cleaning()
    cleaner.surface_cleaning()
    cleaner.energie_type_cleaning()
    frame = cleaner.df.copy()
    frame = frame[frame.nombre_niveau_logement.between(1, 10) & frame.nombre_niveau_logement.eq(frame.nombre_niveau_logement.round())].copy()
    frame["code_insee_ban"] = frame.code_insee_ban.astype("string").str.zfill(5)
    frame["code_departement_ban"] = frame.code_departement_ban.astype("string").str.zfill(2)
    proposals = [commune_proposal(reference, code, dep) for code, dep in zip(frame.code_insee_ban, frame.code_departement_ban)]
    frame["altitude_moyenne"] = [p["altitude"] for p in proposals]
    frame["zone_climatique"] = [p["zone"] for p in proposals]
    if "_geopoint" in frame:
        coords = frame._geopoint.astype(str).str.split(",", expand=True).reindex(columns=[0, 1])
        frame["lat"], frame["lon"] = pd.to_numeric(coords[0], errors="coerce"), pd.to_numeric(coords[1], errors="coerce")
    for col in ["lat", "lon", "nom_commune_ban", "code_postal_ban"]:
        if col not in frame:
            frame[col] = np.nan
    frame = frame.dropna(subset=NUMERIC + CATEGORICAL)
    return frame


def prepare_version(raw, source, store=None, reference=None):
    store = store or VersionStore()
    if not raw:
        raise ValueError("Aucune ligne reçue ; aucune version créée")
    reference = reference or read_geography(ROOT / "data/communes-france-2025.csv", ROOT / "Notebooks_Api_Traitement/1_data_preparation.ipynb")
    base_id = store.active()["data"]
    data_path, meta_path = store.data_paths(base_id)
    base = pd.read_csv(data_path, dtype={"code_insee_ban":"string", "code_departement_ban":"string"}, low_memory=False)
    metadata = pd.read_csv(meta_path, dtype="string").drop(columns="cleaned_row", errors="ignore")
    if not set(NUMERIC + CATEGORICAL + ["etiquette_dpe", "conso_5_usages_ef"]).issubset(base):
        raise ValueError("Colonnes de la base incomplètes")
    if len(base) != len(metadata) or metadata.numero_dpe.isna().any() or metadata.numero_dpe.duplicated().any():
        raise ValueError("Base et traçabilité incompatibles")
    incoming = prepare_received(raw, source, reference)
    rejected_preparation = len(raw) - len(incoming)
    incoming = incoming.assign(_received_sort=pd.to_datetime(incoming.date_reception_dpe,utc=True)).sort_values("_received_sort", kind="stable")
    duplicates = incoming.numero_dpe.duplicated(keep="last")
    duplicates_count = int(duplicates.sum())
    incoming = incoming.loc[~duplicates].copy()
    known = incoming.numero_dpe.isin(metadata.numero_dpe)
    duplicates_count += int(known.sum())
    incoming = incoming.loc[~known].copy()
    old_dates = pd.to_datetime(metadata.date_reception_dpe, utc=True, errors="coerce", format="mixed")
    old_date_by_id = dict(zip(metadata.numero_dpe, old_dates))
    stale = incoming.apply(lambda row: str(row.numero_dpe_remplace) in old_date_by_id
                           and pd.to_datetime(row.date_reception_dpe, utc=True) < old_date_by_id[str(row.numero_dpe_remplace)], axis=1)
    stale_count = int(stale.sum())
    incoming = incoming.loc[~stale].copy()
    # Un remplacement n'est appliqué qu'après admission du nouveau diagnostic.
    # Le diagnostic remplacé reste dans l'archive/base d'origine immuable.
    replacements = set(incoming.numero_dpe_remplace.dropna().astype(str)) - {"", "nan"}
    new_replaced = incoming.numero_dpe.astype(str).isin(replacements)
    replaced_new = int(new_replaced.sum())
    incoming = incoming.loc[~new_replaced].copy()
    remove_old = metadata.numero_dpe.astype(str).isin(replacements).to_numpy()
    rejected = rejected_preparation + duplicates_count + replaced_new + stale_count
    if incoming.empty:
        raise ValueError(f"Aucune nouvelle ligne conservée (reçues {len(raw)}, rejetées {rejected})")
    version = "d-" + uuid.uuid4().hex
    if "_source_batch" not in metadata:
        metadata["_source_batch"] = "initial"
    incoming["_source_batch"] = version
    new_data = incoming.drop(columns=LINEAGE_FIELDS + ["annee_construction", "_geopoint"], errors="ignore").reindex(columns=base.columns)
    data = pd.concat([base.loc[~remove_old], new_data], ignore_index=True)
    meta = pd.concat([metadata.loc[~remove_old], incoming.reindex(columns=metadata.columns)], ignore_index=True)
    meta.insert(0, "cleaned_row", np.arange(len(meta)))
    folder = store.folder("datasets", version)
    folder.mkdir(parents=True)
    data.to_csv(folder / "data.csv", index=False)
    meta.to_csv(folder / "metadata.csv", index=False)
    pd.DataFrame(raw).to_json(folder / "received.json", orient="records", force_ascii=False)
    info = {"id": version, "status":"prepared", "created_at":now(), "base":base_id, "rows":len(data),
            "received":len(raw), "kept_new":len(incoming), "rejected":rejected,
            "duplicates":duplicates_count, "replaced_base":int(remove_old.sum()), "replaced_in_batch":replaced_new,
            "rejected_preparation":rejected_preparation,
            "stale_replacements":stale_count, "base_hashes":{"data":sha256(data_path), "metadata":sha256(meta_path)},
            "hashes":{n:sha256(folder/n) for n in ["data.csv", "metadata.csv", "received.json"]},
            "preparation":"Référence 2026 ; méthodes IQR coût/surface du projet appliquées au lot reçu ; énergies regroupées ; altitudes référentiel communal/départemental ; H1/H2/H3 du notebook",
            "limits":"Nettoyage IQR par lot, seuils historiques non figés. Comparabilité et stabilité à contrôler ; aucune représentativité nationale garantie."}
    atomic_json(folder / "manifest.json", info)
    return info
