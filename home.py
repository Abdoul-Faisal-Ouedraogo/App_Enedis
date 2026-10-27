"""
Point d'entrée de l'application Streamlit :
définit le menu de navigation et lance la page sélectionnée.
"""

from pathlib import Path

import streamlit as st

# NB : pas de st.set_page_config ici, chaque page définit le sien (titre, icône, layout).

# === Chemins ===
PAGES_PATH = Path(__file__).parent / "pages"
ASSETS_PATH = Path(__file__).parent / "assets"

# === Définition du menu ===
pages = {
    "Projet": [
        st.Page(PAGES_PATH / "intro.py", title="🏠 Accueil"),
        st.Page(PAGES_PATH / "context.py", title="📋 Contexte"),
    ],
    "Données": [
        st.Page(PAGES_PATH / "data.py", title="📊 Statistiques & Visualisation"),
        st.Page(PAGES_PATH / "map.py", title="🗺️ Carte DPE"),
        st.Page(
            PAGES_PATH / "datasets.py", title="📂 Jeux de données et téléchargements"
        ),
    ],
    "Prédiction": [
        st.Page(PAGES_PATH / "prediction.py", title="🔮 Prédire la classe DPE"),
        st.Page(
            PAGES_PATH / "retrain_models.py", title="🔄 Réentraînement des modèles"
        ),
    ],
}

# === CSS du menu latéral ===
st.markdown(
    """
    <style>
    /* Titres des catégories */
    [data-testid="stNavSectionHeader"] {
        font-size: 1.5rem !important;
        font-weight: 700 !important;
        margin-top: 1.5rem !important;
        margin-bottom: 0.8rem !important;
        padding-left: 0.5rem !important;
    }

    /* Liens du menu */
    [data-testid="stSidebarNav"] a {
        font-size: 1.05rem !important;
        font-weight: 500 !important;
    }

    /* Page active */
    [data-testid="stSidebarNav"] a[aria-current="page"] {
        background-color: rgba(255, 190, 0, 0.20) !important;
        border-left: 4px solid #FF4B4B !important;
        font-weight: 600 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# === Navigation ===
pg = st.navigation(pages)
pg.run()