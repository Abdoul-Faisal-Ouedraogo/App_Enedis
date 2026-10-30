"""Entraînements minuscules, gel avant test, erreurs et changement de version."""
import json
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.project_paths import ROOT
from src.version_store import VersionStore, atomic_json
from src.expert_training import train_version, temporal_partitions
from src.model_registry import load_model_version
from src.preparation_geography import sha256
from src.app_services import predict


@pytest.fixture
def training_store(tmp_path):
    from src.data_lineage import LINEAGE_FIELDS
    rows, metadata = [], []
    for period,year in enumerate([2023,2024,2025]):
        for i in range(12):
            rows.append(dict(surface_habitable_logement=50+i,nombre_niveau_logement=1,age_batiment=20,
                altitude_moyenne=237,type_energie_principale_chauffage="Électricité",type_batiment="maison",zone_climatique="H1",
                etiquette_dpe="C" if i%2 else "D",conso_5_usages_ef=5000+i*100))
            entry = {k:None for k in LINEAGE_FIELDS}
            entry.update(_source_dataset="existant",_source_row=len(metadata),numero_dpe=f"d-{period}-{i}",identifiant_ban=f"ban-{period}-{i}",
                         date_reception_dpe=f"{year}-06-01",date_etablissement_dpe=f"{year}-05-01")
            metadata.append(entry)
    data = pd.DataFrame(rows)
    meta = pd.DataFrame(metadata)
    meta.insert(0,"cleaned_row",np.arange(len(meta)))
    store = VersionStore(tmp_path/"runtime")
    folder = store.folder("datasets","tiny")
    folder.mkdir(parents=True)
    data.to_csv(folder/"data.csv",index=False)
    meta.to_csv(folder/"metadata.csv",index=False)
    atomic_json(folder/"manifest.json",{"id":"tiny","status":"validated","rows":len(data),"hashes":{n:sha256(folder/n) for n in ["data.csv","metadata.csv"]}})
    return store,data,meta


def test_temporal_groups_crossing_are_excluded(training_store):
    _,_,meta = training_store
    meta.loc[12,"identifiant_ban"]=meta.loc[0,"identifiant_ban"]
    split = temporal_partitions(meta)
    assert split.loc[[0,12],"partition"].eq("excluded").all()
    groups = [set(split.loc[split.partition.eq(n),"group"]) for n in ["train","validation","reserved"]]
    assert not (groups[0]&groups[1] or groups[0]&groups[2] or groups[1]&groups[2])


def test_small_training_freezes_parameters_and_does_not_activate(training_store,monkeypatch):
    store,data,_ = training_store
    monkeypatch.setattr("src.expert_training.TREES",2)
    events=[]
    result = train_version("tiny",store,lambda fraction,message:events.append((fraction,message)))
    assert result["status"]=="ready" and events[-1][0]==1
    assert store.active()["model"]=="final_geo_v1"
    folder=store.folder("models",result["id"])
    protocol=json.loads((folder/"protocol.json").read_text(encoding="utf-8"))
    assert protocol["counts"]=={"train":12,"validation":12,"reserved":12}
    assert protocol["parameters"]["classification"]["n_jobs"]==2
    model=load_model_version(result["id"],store)
    assert model["results"]["classification"]["rows"]==12
    assert model["variables"]["regression"]["fit_rows"]==24
    value,label=predict(model,data.iloc[0].to_dict())
    assert value>0 and label in "ABCDEFG"
    store.activate(model=result["id"])
    assert store.active()["model"]==result["id"]
    store.rollback()
    assert store.active()["model"]=="final_geo_v1"


def test_training_failure_is_recorded_and_active_models_preserved(training_store,monkeypatch):
    store,_,_ = training_store
    monkeypatch.setattr("src.expert_training.TREES",2)
    with patch("sklearn.ensemble.RandomForestClassifier.fit",side_effect=RuntimeError("panne simulée")):
        with pytest.raises(RuntimeError,match="panne"):
            train_version("tiny",store)
    entry=store.list_versions("models")[0]
    assert entry["status"]=="failed" and "panne" in entry["error"]
    with pytest.raises(ValueError,match="non prête"):
        store.activate(model=entry["id"])
    assert store.active()["model"]=="final_geo_v1"
    assert not (store.root/"training.lock").exists()


def test_unvalidated_data_cannot_train(training_store):
    store,_,_=training_store
    info=store.manifest("datasets","tiny")
    info["status"]="prepared"
    atomic_json(store.folder("datasets","tiny")/"manifest.json",info)
    with pytest.raises(ValueError,match="non validée"):
        train_version("tiny",store)


def test_model_change_invalidates_ui_result_and_reload_cache(training_store,monkeypatch):
    from fastapi.testclient import TestClient
    from src.prediction_api import app
    store,_,_=training_store
    monkeypatch.setattr("src.expert_training.TREES",2)
    new=train_version("tiny",store)["id"]
    monkeypatch.setenv("ENEDIS_RUNTIME",str(store.root))
    ui=AppTest.from_file(str(ROOT/"home.py"),default_timeout=90).run()
    ui.sidebar.radio[0].set_value("Prédiction").run()
    ui.button(key="single_calculate").click().run()
    assert ui.session_state["single_result"]["model_version"]=="final_geo_v1"
    store.activate(model=new)
    assert TestClient(app).get("/health").json()["model_version"]==new
    ui.run()
    assert not ui.exception and not ui.get("download_button")
    ui.button(key="single_calculate").click().run()
    assert ui.session_state["single_result"]["model_version"]==new
    store.rollback()
    assert TestClient(app).get("/health").json()["model_version"]=="final_geo_v1"
    ui.run()
    assert not ui.get("download_button")


def test_tampered_model_refused(training_store,monkeypatch):
    store,_,_=training_store
    monkeypatch.setattr("src.expert_training.TREES",2)
    info=train_version("tiny",store)
    (store.folder("models",info["id"])/"regression.joblib").write_bytes(b"corrompu")
    with pytest.raises(ValueError,match="altérés"):
        store.activate(model=info["id"])
