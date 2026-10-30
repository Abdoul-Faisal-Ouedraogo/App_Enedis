"""Chargeur commun Streamlit/API ; aucune activation implicite."""
from src.final_model_loader import load_final_bundle


def load_model_version(version="final_geo_v1", store=None):
    if version != "final_geo_v1":
        raise ValueError("Version de modèles inconnue ou non prête")
    result = load_final_bundle()
    result["version"] = version
    return result
