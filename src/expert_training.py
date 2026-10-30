"""Deux entraînements finaux explicites ; protocole figé, aucun choix sur le réservé."""
import json
import platform
import uuid
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from threadpoolctl import threadpool_limits

from src.validation_plan import connected_groups, TRAIN_END, VALIDATION_END
from src.final_models import classification_metrics, regression_metrics, build_reload_fixture
from src.final_model_loader import load_final_bundle
from src.app_services import category_options
from src.ml_workflow import NUMERIC, CATEGORICAL
from src.preparation_geography import sha256
from src.version_store import VersionStore, atomic_json, now

TREES = 100


def temporal_partitions(metadata):
    if metadata.numero_dpe.isna().any() or metadata.numero_dpe.duplicated().any():
        raise ValueError("Identifiants DPE manquants ou dupliqués")
    received = pd.to_datetime(metadata.date_reception_dpe,format="mixed",errors="coerce",utc=True)
    established = pd.to_datetime(metadata.date_etablissement_dpe,format="mixed",errors="coerce",utc=True)
    valid = received.notna() & established.notna() & established.le(received) & received.le(pd.Timestamp.now(tz="UTC"))
    groups = connected_groups(metadata)
    known = (metadata.identifiant_ban.notna() | metadata.numero_dpe_immeuble_associe.notna()).to_numpy()
    known = pd.Series(known).groupby(groups).transform("any").to_numpy()
    period = np.where(received < pd.Timestamp(TRAIN_END,tz="UTC"),0,np.where(received < pd.Timestamp(VALIDATION_END,tz="UTC"),1,2))
    eligible = valid.to_numpy() & known
    spans = pd.DataFrame({"group":groups[eligible],"period":period[eligible]}).groupby("group").period.nunique()
    crossing = np.isin(groups,spans.index[spans>1])
    labels = np.full(len(metadata),"excluded",dtype=object)
    for i,name in enumerate(["train","validation","reserved"]):
        labels[eligible & ~crossing & (period==i)] = name
    for name in ["train","validation","reserved"]:
        if np.sum(labels==name) < 2:
            raise ValueError(f"Partition {name} insuffisante : au moins deux groupes/lignes admissibles sont nécessaires")
    return pd.DataFrame({"group":groups,"partition":labels})


def train_version(data_version, store=None, progress=None):
    store = store or VersionStore()
    with store.lock("training"):
        version = "m-" + uuid.uuid4().hex
        folder = store.folder("models",version)
        folder.mkdir(parents=True)
        manifest = {"id":version,"status":"training","data_version":data_version,"started_at":now(),"sklearn":sklearn.__version__}
        atomic_json(folder/"manifest.json",manifest)
        def report(fraction,message):
            atomic_json(folder/"progress.json",{"fraction":fraction,"message":message,"at":now()})
            if progress:
                progress(fraction,message)
        try:
            report(.05,"Vérification de la version validée et des partitions")
            data_path,meta_path = store.data_paths(data_version)
            data = pd.read_csv(data_path,dtype={"code_departement_ban":"string"},low_memory=False)
            meta = pd.read_csv(meta_path,dtype="string").replace(r"^\s*$",pd.NA,regex=True)
            if len(data)!=len(meta) or not np.array_equal(meta.cleaned_row.astype(int),np.arange(len(data))):
                raise ValueError("Alignement données/métadonnées perdu")
            required = NUMERIC+CATEGORICAL+["etiquette_dpe","conso_5_usages_ef"]
            if not set(required).issubset(data) or data[required].isna().any().any():
                raise ValueError("Données d'entraînement incomplètes")
            if not np.isfinite(data[NUMERIC+["conso_5_usages_ef"]].to_numpy()).all() or not data.etiquette_dpe.isin(list("ABCDEFG")).all():
                raise ValueError("Données numériques ou cibles invalides")
            if not (data.surface_habitable_logement.gt(0) & data.nombre_niveau_logement.between(1,10) & data.age_batiment.ge(0) & data.conso_5_usages_ef.ge(0)).all():
                raise ValueError("Données hors conventions de préparation")
            assignments = temporal_partitions(meta)
            fit = assignments.partition.isin(["train","validation"]).to_numpy()
            test = assignments.partition.eq("reserved").to_numpy()
            if data.loc[fit,"etiquette_dpe"].nunique()<2:
                raise ValueError("Au moins deux classes d'entraînement sont nécessaires")
            reference = load_final_bundle()
            options = category_options(reference)
            if any(not data[col].isin(options[col]).all() for col in CATEGORICAL):
                raise ValueError("Catégorie non compatible avec les conventions finales")
            params = {kind:dict(reference["variables"][kind]["model_parameters"]) for kind in ["classification","regression"]}
            for value in params.values():
                value.update(n_estimators=TREES,n_jobs=2)
            assignments.to_csv(folder/"assignments.csv",index=False)
            protocol = {"frozen_at":now(),"data_sha256":sha256(data_path),"metadata_sha256":sha256(meta_path),
                        "assignments_sha256":sha256(folder/"assignments.csv"),"counts":assignments.partition.value_counts().to_dict(),
                        "train_end":TRAIN_END,"validation_end":VALIDATION_END,"parameters":params,
                        "selection":"Réglages finaux existants figés ; aucune recherche ni sélection sur le lot réservé",
                        "fit_partitions":["train","validation"],"grouping":"connected_groups BAN/immeuble/remplacement ; groupes traversant périodes exclus",
                        "resources":{"native_threads":2,"forest_jobs":2},"python":platform.python_version(),"sklearn":sklearn.__version__}
            atomic_json(folder/"protocol.json",protocol)
            bundles = {}
            with threadpool_limits(limits=2):
                for kind, estimator, target, fraction in [("classification",RandomForestClassifier,"etiquette_dpe",.2),
                                                          ("regression",RandomForestRegressor,"conso_5_usages_ef",.5)]:
                    report(fraction,f"Entraînement : {kind} (deux threads)")
                    pipeline = Pipeline([("preprocessor",ColumnTransformer([
                        ("numeric","passthrough",NUMERIC),
                        ("encoder",OneHotEncoder(categories=[options[c] for c in CATEGORICAL],handle_unknown="ignore"),CATEGORICAL)])),
                        ("model",estimator(**params[kind]))])
                    pipeline.fit(data.loc[fit,NUMERIC+CATEGORICAL],data.loc[fit,target])
                    joblib.dump(pipeline,folder/f"{kind}.joblib",compress=3)
                    variables = dict(reference["variables"][kind])
                    variables.update(data_sha256=protocol["data_sha256"],fit_rows=int(fit.sum()),model_parameters=pipeline.named_steps["model"].get_params(),
                                     model_sha256=sha256(folder/f"{kind}.joblib"))
                    atomic_json(folder/f"{kind}_variables.json",variables)
                    bundles[kind]=pipeline
                fixture = build_reload_fixture(data.loc[fit],bundles["classification"],bundles["regression"])
                atomic_json(folder/"reload_check.json",fixture)
                report(.8,"Évaluation du lot réservé après gel des paramètres et sauvegarde")
                x = data.loc[test,NUMERIC+CATEGORICAL]
                labels,consumption = bundles["classification"].predict(x),bundles["regression"].predict(x)
            actual = data.loc[test].reset_index(drop=True)
            sources = meta.loc[test,"_source_dataset"].reset_index(drop=True)
            results = {"scope":"Lot réservé interne, pas une validation externe", "classification":classification_metrics(actual.etiquette_dpe,labels),
                       "regression":regression_metrics(actual.conso_5_usages_ef,consumption),"by_source":{},"regression_by_dpe":{}}
            for source in sources.dropna().unique():
                mask = sources.eq(source).to_numpy()
                results["by_source"][str(source)]={"classification":classification_metrics(actual.loc[mask,"etiquette_dpe"],labels[mask]),
                    "regression":regression_metrics(actual.loc[mask,"conso_5_usages_ef"],consumption[mask])}
            for label in "ABCDEFG":
                mask = actual.etiquette_dpe.eq(label).to_numpy()
                if mask.any():
                    results["regression_by_dpe"][label]=regression_metrics(actual.loc[mask,"conso_5_usages_ef"],consumption[mask])
            atomic_json(folder/"results.json",results)
            pd.DataFrame({"true_dpe":actual.etiquette_dpe,"predicted_dpe":labels,"true_consumption":actual.conso_5_usages_ef,"predicted_consumption":consumption}).to_csv(folder/"reserved_predictions.csv",index=False)
            files = [p for p in folder.iterdir() if p.name not in {"manifest.json","progress.json"}]
            manifest.update(status="ready",finished_at=now(),hashes={p.name:sha256(p) for p in files})
            atomic_json(folder/"manifest.json",manifest)
            report(1.0,"Version prête, non activée")
            return manifest
        except Exception as exc:
            manifest.update(status="failed",finished_at=now(),error=str(exc))
            atomic_json(folder/"manifest.json",manifest)
            report(0.0,"Échec : modèles actifs conservés")
            raise
