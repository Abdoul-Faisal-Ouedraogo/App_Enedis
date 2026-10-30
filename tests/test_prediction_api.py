"""Requêtes API réelles en mémoire, modèles finaux partagés, aucun réseau externe."""
from unittest.mock import patch
from fastapi.testclient import TestClient
import pytest

from src.prediction_api import app
from src.app_services import predict
from src.model_registry import load_model_version

VALUES={"surface_habitable_logement":80.0,"nombre_niveau_logement":1,"age_batiment":30.0,
        "altitude_moyenne":150.0,"type_energie_principale_chauffage":"Électricité","type_batiment":"maison","zone_climatique":"H1"}


def test_api_matches_streamlit_shared_prediction():
    client=TestClient(app)
    assert client.get("/health").status_code==200
    response=client.post("/predict",json=VALUES)
    assert response.status_code==200
    result=response.json()
    consumption,label=predict(load_model_version(),VALUES)
    assert result["consumption"]==pytest.approx(consumption)
    assert result["estimated_dpe"]==label
    assert result["units"]["consumption"]=="kWh/an" and result["model_version"]=="final_geo_v1"
    assert client.get("/openapi.json").json()["paths"]["/predict"]


@pytest.mark.parametrize("changes",[{"surface_habitable_logement":0},{"nombre_niveau_logement":1.5},{"age_batiment":-1},
    {"age_batiment":2.5},{"zone_climatique":"H1a"},{"type_batiment":"château"},{"extra":True},
    {"surface_habitable_logement":"80"},{"altitude_moyenne":6000}])
def test_invalid_requests_rejected(changes):
    assert TestClient(app).post("/predict",json=VALUES|changes).status_code==422


def test_missing_models_service_unavailable():
    with patch("src.prediction_api.active_bundle",side_effect=FileNotFoundError("chemin-secret")):
        client=TestClient(app)
        assert client.get("/health").status_code==503
        response=client.post("/predict",json=VALUES)
        assert response.status_code==503 and "chemin-secret" not in response.text


def test_missing_feature_and_malformed_body():
    client=TestClient(app)
    assert client.post("/predict",json={}).status_code==422
    assert client.post("/predict",content="not json",headers={"content-type":"application/json"}).status_code==422
    import json
    invalid=json.dumps(VALUES|{"altitude_moyenne":float("nan")})
    assert client.post("/predict",content=invalid,headers={"content-type":"application/json"}).status_code==422


def test_unexpected_inference_error_is_clear():
    with patch("src.prediction_api.predict",side_effect=RuntimeError("panne interne")):
        response=TestClient(app).post("/predict",json=VALUES)
        assert response.status_code==503 and "panne interne" not in response.text
