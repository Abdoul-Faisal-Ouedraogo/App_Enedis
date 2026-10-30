"""Copies de données préparées avec profil figé et bilan auditable ; aucun fit ni activation."""
import json
import uuid
import numpy as np
import pandas as pd

from src.app_geography import read_geography
from src.data_lineage import LINEAGE_FIELDS
from src.ml_workflow import NUMERIC, CATEGORICAL
from src.project_paths import ROOT
from src.preparation_geography import sha256
from src.preparation_audit import prepare_audited, stable_policy, mark, refresh_counts
from src.version_store import VersionStore, atomic_json, now


class PreparationRejected(ValueError):
    def __init__(self,summary):
        self.summary=summary
        super().__init__(f"Aucune nouvelle ligne conservée (reçues {summary['received']}, rejetées {summary['rejected']})")


def prepare_received(raw,source,reference,*,policy=None,return_audit=False,as_of=None):
    frame,audit=prepare_audited(raw,source,reference,policy,as_of)
    return (frame,audit) if return_audit else frame


def filter_incoming(incoming,metadata,audit):
    incoming=incoming.assign(_received_sort=pd.to_datetime(incoming.date_reception_dpe,utc=True)).sort_values("_received_sort",kind="stable")
    duplicates=incoming.numero_dpe.duplicated(keep="last")
    mark(audit,incoming.index[duplicates],"duplicate_batch")
    duplicate_count=int(duplicates.sum())
    incoming=incoming.loc[~duplicates].copy()
    known=incoming.numero_dpe.isin(metadata.numero_dpe)
    mark(audit,incoming.index[known],"duplicate_base")
    duplicate_count+=int(known.sum())
    incoming=incoming.loc[~known].copy()
    dates=pd.to_datetime(metadata.date_reception_dpe,utc=True,errors="coerce",format="mixed")
    old_date_by_id=dict(zip(metadata.numero_dpe,dates))
    stale=pd.Series([str(row.numero_dpe_remplace) in old_date_by_id
                     and pd.to_datetime(row.date_reception_dpe,utc=True)<old_date_by_id[str(row.numero_dpe_remplace)]
                     for row in incoming.itertuples()],index=incoming.index,dtype=bool)
    mark(audit,incoming.index[stale],"stale_replacement")
    incoming=incoming.loc[~stale].copy()
    replacements=set(incoming.numero_dpe_remplace.dropna().astype(str)) - {"","nan"}
    replaced=incoming.numero_dpe.astype(str).isin(replacements)
    mark(audit,incoming.index[replaced],"replaced_in_batch")
    replaced_count=int(replaced.sum())
    incoming=incoming.loc[~replaced].copy()
    remove_old=metadata.numero_dpe.astype(str).isin(replacements).to_numpy()
    stats={"duplicates":duplicate_count,"stale_replacements":int(stale.sum()),
           "replaced_in_batch":replaced_count,"replaced_base":int(remove_old.sum()) if len(incoming) else 0}
    refresh_counts(audit)
    assert audit["kept"]==len(incoming)
    return incoming,remove_old,stats


def prepare_version(raw,source,store=None,reference=None):
    store=store or VersionStore()
    if not raw:
        raise ValueError("Aucune ligne reçue ; aucune version créée")
    reference=reference or read_geography(ROOT/"data/communes-france-2025.csv",ROOT/"Notebooks_Api_Traitement/1_data_preparation.ipynb")
    policy=stable_policy()
    base_id=store.active()["data"]
    data_path,meta_path=store.data_paths(base_id)
    base=pd.read_csv(data_path,dtype={"code_insee_ban":"string","code_departement_ban":"string"},low_memory=False)
    metadata=pd.read_csv(meta_path,dtype="string").drop(columns="cleaned_row",errors="ignore")
    if not set(NUMERIC+CATEGORICAL+["etiquette_dpe","conso_5_usages_ef"]).issubset(base):
        raise ValueError("Colonnes de la base incomplètes")
    if len(base)!=len(metadata) or metadata.numero_dpe.isna().any() or metadata.numero_dpe.duplicated().any():
        raise ValueError("Base et traçabilité incompatibles")
    incoming,audit=prepare_received(raw,source,reference,policy=policy,return_audit=True)
    rejected_preparation=len(raw)-len(incoming)
    incoming,remove_old,stats=filter_incoming(incoming,metadata,audit)
    info={"status":"prepared","created_at":now(),"source":source,"base":base_id,
          "received":len(raw),"kept_new":len(incoming),"rejected":len(raw)-len(incoming),
          "rejected_preparation":rejected_preparation,**stats,
          "policy":policy,"audit":{k:v for k,v in audit.items() if k!="rows"},
          "base_hashes":{"data":sha256(data_path),"metadata":sha256(meta_path)},
          "preparation":"Référence 2026 ; bornes IQR initiales figées pour tous les lots ; énergies regroupées ; géographie du projet",
          "limits":"Année absente dans l’existant non imputée. Profil initial global (pas ajusté sur train seul) ; prix/coûts pouvant évoluer. Ni représentativité nationale ni nouvelle performance ML garanties."}
    if incoming.empty:
        info.update(status="not_created",rows=len(base))
        raise PreparationRejected(info)
    version="d-"+uuid.uuid4().hex
    if "_source_batch" not in metadata:
        metadata["_source_batch"]="initial"
    incoming["_source_batch"]=version
    new_data=incoming.drop(columns=LINEAGE_FIELDS+["annee_construction","_geopoint"],errors="ignore").reindex(columns=base.columns)
    data=pd.concat([base.loc[~remove_old],new_data],ignore_index=True)
    meta=pd.concat([metadata.loc[~remove_old],incoming.reindex(columns=metadata.columns)],ignore_index=True)
    meta.insert(0,"cleaned_row",np.arange(len(meta)))
    folder=store.folder("datasets",version)
    folder.mkdir(parents=True)
    data.to_csv(folder/"data.csv",index=False)
    meta.to_csv(folder/"metadata.csv",index=False)
    pd.DataFrame(raw).to_json(folder/"received.json",orient="records",force_ascii=False)
    atomic_json(folder/"audit.json",audit)
    info.update(id=version,rows=len(data),hashes={n:sha256(folder/n) for n in ["data.csv","metadata.csv","received.json","audit.json"]})
    atomic_json(folder/"manifest.json",info)
    return info


def audit_existing_version(version,store=None):
    """Enrichir en mémoire un ancien bilan ; aucun manifeste/CSV/pointeur n'est écrit."""
    store=store or VersionStore()
    info=store.manifest("datasets",version)
    if "audit" in info:
        return info
    if "au lot reçu" not in info.get("preparation",""):
        raise ValueError("Politique historique non identifiée : ne pas inventer les raisons")
    folder=store.folder("datasets",version)
    for name in ["received.json","metadata.csv","data.csv"]:
        if sha256(folder/name)!=info["hashes"][name]:
            raise ValueError("Version historique altérée : audit refusé")
    meta=pd.read_csv(folder/"metadata.csv",dtype="string",usecols=["_source_batch","_source_dataset","numero_dpe"])
    sources=meta.loc[meta._source_batch.eq(version),"_source_dataset"].dropna().unique()
    if len(sources)!=1:
        raise ValueError("Source du lot historique non déterminable")
    data_path,base_meta_path=store.data_paths(info["base"])
    if sha256(data_path)!=info["base_hashes"]["data"] or sha256(base_meta_path)!=info["base_hashes"]["metadata"]:
        raise ValueError("La base historique ne correspond plus au bilan")
    base_meta=pd.read_csv(base_meta_path,dtype="string")
    reference=read_geography(ROOT/"data/communes-france-2025.csv",ROOT/"Notebooks_Api_Traitement/1_data_preparation.ipynb")
    raw=json.loads((folder/"received.json").read_text(encoding="utf-8"))
    legacy={"id":"legacy_batch_iqr_v1","mode":"batch_iqr"}
    incoming,audit=prepare_received(raw,str(sources[0]),reference,policy=legacy,return_audit=True,as_of=info["created_at"])
    incoming,_,stats=filter_incoming(incoming,base_meta,audit)
    expected_ids=set(meta.loc[meta._source_batch.eq(version),"numero_dpe"].astype(str))
    if len(incoming)!=info["kept_new"] or set(incoming.numero_dpe.astype(str))!=expected_ids or any(stats[k]!=info[k] for k in stats):
        raise ValueError("Audit non reproductible : bilan conservé sans attribuer de motifs incertains")
    stable,stable_audit=prepare_received(raw,str(sources[0]),reference,return_audit=True,as_of=info["created_at"])
    stable,_,_=filter_incoming(stable,base_meta,stable_audit)
    return info|{"audit":{k:v for k,v in audit.items() if k!="rows"},"audit_read_only":True,
                 "stable_comparison":{"kept_new":len(stable),"rejected":len(raw)-len(stable),
                                      "policy":stable_audit["policy"],"primary_counts":stable_audit["primary_counts"]}}
