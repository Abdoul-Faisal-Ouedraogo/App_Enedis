"""Contrôle réel à exécuter DANS l'image construite, sans réseau ni entraînement."""
from pathlib import Path
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from streamlit.testing.v1 import AppTest
from src.app_services import read_data, csv_bytes, chart_pngs
from src.app_geography import read_geography, commune_proposal

paths = [ROOT / "output/cleaned_data.csv", *sorted((ROOT / "MLmodels/final_geo_v1").glob("*"))]
def hashes():
    return {str(p): hashlib.file_digest(p.open("rb"), "sha256").hexdigest() for p in paths if p.is_file()}
before = hashes()
app = AppTest.from_file(str(ROOT / "home.py"), default_timeout=120).run()
for page in ["Contexte", "Exploration", "Carte", "Prédiction"]:
    app.sidebar.radio[0].set_value(page).run()
    assert not app.exception, app.exception
app.button(key="single_calculate").click().run()
assert not app.exception and app.metric[0].value.endswith("kWh/an")
assert app.get("download_button")
reference = read_geography(ROOT / "data/communes-france-2025.csv", ROOT / "Notebooks_Api_Traitement/1_data_preparation.ipynb")
assert commune_proposal(reference, "69381", "69")["altitude"] == 237
data = read_data(ROOT / "output/cleaned_data.csv").head(500)
assert csv_bytes(data).startswith(b"\xef\xbb\xbf")
assert len(chart_pngs(data, "conso_5_usages_ef")) == 4
assert before == hashes()
print("OK conteneur : quatre pages, prediction, commune, exports et empreintes.")
