"""Réseau simulé et copies minuscules : aucun accès ADEME ni écrasement local."""
from datetime import date
from unittest.mock import Mock

import pandas as pd
import pytest
import requests

from src.data_requesters.ademe import Ademe_API_requester
from src.expert_data import prepare_version
from src.version_store import VersionStore
from src.app_geography import read_geography
from src.project_paths import ROOT
from src.preparation_geography import sha256


def raw_row(number="new", **changes):
    row = dict(numero_dpe=number, numero_dpe_remplace=None, date_reception_dpe="2026-01-10", date_etablissement_dpe="2026-01-01",
               annee_construction=2000, cout_total_5_usages=1000, surface_habitable_logement=80, nombre_niveau_logement=1,
               conso_5_usages_ef=6000, code_insee_ban="69381", code_departement_ban="69", etiquette_dpe="D",
               type_batiment="maison", type_energie_principale_chauffage="Bois", identifiant_ban="adresse-"+number,
               _geopoint="45.7,4.8")
    return row | changes


def response(payload, status=200):
    result = Mock(status_code=status)
    result.json.return_value = payload
    if status >= 400:
        result.raise_for_status.side_effect = requests.HTTPError("erreur simulée")
    return result


def test_pagination_bound_filters_and_timeout():
    url = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant/lines?after=abc"
    session = Mock()
    session.get.side_effect = [response({"results":[raw_row("a")],"next":url}), response({"results":[raw_row("b"),raw_row("c")]})]
    rows = Ademe_API_requester().bounded_lines_by_date("69", date(2026,1,1), date(2026,1,30), 2, session=session, sleep=lambda _:None)
    assert len(rows) == 2 and session.get.call_count == 2
    first = session.get.call_args_list[0].kwargs
    assert first["timeout"] == (5,30) and first["allow_redirects"] is False
    assert "date_reception_dpe" in first["params"]["qs"]


@pytest.mark.parametrize("payload", [{"results":[] ,"next":"https://evil.test/data"}, {"results":[raw_row()],"next":"https://evil.test/data"}, {"bad":[]}])
def test_bad_pagination_fails_closed(payload):
    session = Mock()
    session.get.return_value = response(payload)
    with pytest.raises(ValueError):
        Ademe_API_requester().bounded_lines_by_date("69","2026-01-01","2026-01-30",2,session=session,sleep=lambda _:None)


def test_timeout_retried_then_clear_failure():
    session = Mock()
    session.get.side_effect = requests.Timeout()
    with pytest.raises(ValueError, match="trois tentatives"):
        Ademe_API_requester().bounded_lines_by_date("69","2026-01-01","2026-01-30",session=session,sleep=lambda _:None)
    assert session.get.call_count == 3


def test_server_must_respect_filters():
    session = Mock()
    session.get.return_value = response({"results":[raw_row(code_departement_ban="75")]})
    with pytest.raises(ValueError):
        Ademe_API_requester().bounded_lines_by_date("69","2026-01-01","2026-01-30",session=session)


@pytest.fixture
def tiny_store(tmp_path):
    from src.expert_data import prepare_received
    reference = read_geography(ROOT/"data/communes-france-2025.csv", ROOT/"Notebooks_Api_Traitement/1_data_preparation.ipynb")
    raw = [raw_row("old", date_reception_dpe="2025-01-01",date_etablissement_dpe="2025-01-01")]
    prepared = prepare_received(raw, "existant", reference)
    from src.data_lineage import LINEAGE_FIELDS
    data = prepared.drop(columns=LINEAGE_FIELDS+["annee_construction","_geopoint"], errors="ignore")
    metadata = prepared[LINEAGE_FIELDS].copy()
    metadata.insert(0,"cleaned_row",0)
    data.to_csv(tmp_path/"base.csv",index=False)
    metadata.to_csv(tmp_path/"meta.csv",index=False)
    class TinyStore(VersionStore):
        def data_paths(self, version=None, check=True):
            if (version or self.active()["data"]) == "initial":
                return tmp_path/"base.csv",tmp_path/"meta.csv"
            return super().data_paths(version,check)
    return TinyStore(tmp_path/"runtime"), reference


def test_version_bilan_duplicates_replacements_and_explicit_validation(tiny_store):
    store, ref = tiny_store
    paths = store.data_paths()
    before = [sha256(p) for p in paths]
    raw = [raw_row("new",numero_dpe_remplace="old"),raw_row("new",numero_dpe_remplace="old"),raw_row("invalid",surface_habitable_logement=-1)]
    info = prepare_version(raw,"existant",store,ref)
    assert info["received"] == 3 and info["kept_new"] == 1 and info["rejected"] == 2
    assert info["duplicates"] == 1 and info["replaced_base"] == 1
    assert store.active()["data"] == "initial"
    with pytest.raises(ValueError,match="non validée"):
        store.data_paths(info["id"])
    store.validate_data(info["id"])
    data = pd.read_csv(store.data_paths(info["id"])[0])
    assert len(data)==1 and data.altitude_moyenne.iloc[0] == 237
    assert data.type_energie_principale_chauffage.iloc[0] == "Autre"
    assert before == [sha256(p) for p in paths]


def test_invalid_or_duplicate_only_batch_does_not_create_version(tiny_store):
    store, ref = tiny_store
    with pytest.raises(ValueError,match="Aucune nouvelle ligne"):
        prepare_version([raw_row("old")],"existant",store,ref)
    assert not store.list_versions("datasets")
    with pytest.raises(ValueError,match="Champs ADEME absents"):
        prepare_version([{"numero_dpe":"x"}],"existant",store,ref)


def test_tampered_data_cannot_validate(tiny_store):
    store, ref = tiny_store
    info = prepare_version([raw_row()],"existant",store,ref)
    (store.folder("datasets",info["id"])/"data.csv").write_text("corrompu")
    with pytest.raises(ValueError,match="altérée"):
        store.validate_data(info["id"])


def test_path_and_concurrency_protection(tmp_path):
    store = VersionStore(tmp_path)
    with pytest.raises(ValueError):
        store.folder("models","../x")
    with store.lock():
        with pytest.raises(ValueError,match="opération"):
            with store.lock():
                pass


def test_management_page_no_automatic_actions_and_explicit_collection(tiny_store):
    from unittest.mock import patch
    from streamlit.testing.v1 import AppTest
    store,_=tiny_store
    with patch("src.expert_ui.VersionStore",return_value=store), patch.object(Ademe_API_requester,"bounded_lines_by_date",return_value=[raw_row()]) as collect:
        ui=AppTest.from_file(str(ROOT/"home.py"),default_timeout=90).run()
        ui.sidebar.radio[0].set_value("Gestion des données et modèles").run()
        assert not ui.exception and not collect.called
        assert ui.button(key="collect_data").disabled
        [w for w in ui.checkbox if w.label.startswith("Je souhaite lancer")][0].check().run()
        ui.button(key="collect_data").click().run()
        assert not ui.exception and collect.call_count==1
        assert store.list_versions("datasets")[0]["status"]=="prepared"
        assert store.active()["data"]=="initial"
        [w for w in ui.checkbox if w.label.startswith("J’ai vérifié")][0].check().run()
        ui.button(key="validate_data").click().run()
        assert store.list_versions("datasets")[0]["status"]=="validated"
