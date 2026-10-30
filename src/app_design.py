"""Identité visuelle locale : composants natifs et quelques styles limités."""
import streamlit as st
import pandas as pd

from src import project_paths
from src.app_services import LABELS, DPE_COLORS

NAV_LABELS = {"Contexte": "🏡 Accueil", "Exploration": "📊 Exploration", "Carte": "🗺️ Carte", "Prédiction": "✨ Prédiction"}
NAV_LABELS["Gestion des données et modèles"] = "⚙️ Gestion"


def number(value, decimals=0):
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def styles():
    st.markdown("""<style>
    .stApp {background:#fafbf7;color:#173d33;}
    h1,h2,h3 {color:#123e35;letter-spacing:-.025em;}
    .block-container {max-width:1440px;padding-top:2.5rem;padding-bottom:3rem;}
    [data-testid="stSidebar"] {background:#eef3ec;border-right:1px solid #d9e3d5;}
    [data-testid="stMetric"] {background:#fff;border:1px solid #dce5d8;border-radius:16px;padding:18px;}
    [data-testid="stMetricValue"] {font-size:clamp(1.5rem,2.3vw,2.25rem);color:#123e35;}
    .dpe-scale {display:flex;gap:5px;margin:16px 0 8px;flex-wrap:wrap;}
    .dpe-grade {flex:1;min-width:30px;text-align:center;padding:10px 4px;border-radius:7px;color:#102a20;font-size:1.1rem;font-weight:750;border:2px solid transparent;}
    .dpe-grade.active {outline:3px solid #123e35;outline-offset:2px;transform:translateY(-3px);}
    .eyebrow {color:#466746;letter-spacing:.12em;font-size:.8rem;font-weight:700;text-transform:uppercase;}
    @media(max-width:700px) {.block-container {padding:1.3rem 1rem;} h1 {font-size:2rem;} .dpe-grade {padding:8px 2px;} }
    </style>""", unsafe_allow_html=True)


def scale(label=None):
    pieces = []
    for letter, color in zip("ABCDEFG", DPE_COLORS):
        selected = letter == label
        pieces.append(f'<span class="dpe-grade{" active" if selected else ""}" style="background:{color};color:{"white" if letter in "AG" else "#102a20"}" aria-label="Classe {letter}{", prédite" if selected else ""}">{letter}{" ✓" if selected else ""}</span>')
    st.markdown('<div class="dpe-scale" role="img" aria-label="Échelle DPE de A à G">' + "".join(pieces) + '</div>', unsafe_allow_html=True)
    st.caption(f"Classe prédite : {label}" if label else "A : moins énergivore → G : plus énergivore · gris : classe inconnue sur la carte")


def go(page):
    st.session_state.page = page


def context(df):
    st.markdown('<p class="eyebrow">Observer · Comprendre · Estimer</p>', unsafe_allow_html=True)
    st.title("Mieux comprendre l’énergie des logements")
    st.write("Explorez les diagnostics de logements, repérez les tendances et comparez deux estimations. "
             "Une lecture simple de l’habitat, avec les limites des données toujours en vue.")
    a, b = st.columns(2)
    a.button("Explorer les logements", icon="📊", type="primary", width="stretch", on_click=go, args=("Exploration",))
    b.button("Estimer un logement", icon="✨", width="stretch", on_click=go, args=("Prédiction",))
    st.image(str(project_paths.ROOT / "assets/habitat.svg"), width="stretch")
    if df is not None:
        a, b, c = st.columns(3)
        a.metric("Logements dans l’étude", number(len(df)))
        b.metric("Départements renseignés", df.code_departement_ban.nunique() if "code_departement_ban" in df else "—")
        c.metric("Classes énergétiques", "A à G")
    st.subheader("Un parcours, quatre regards")
    for column, title, description in zip(st.columns(3), ["📊 Explorer", "🗺️ Situer", "✨ Estimer"],
        ["Filtrez les logements et découvrez leurs surfaces, consommations et classes DPE.",
         "Parcourez la carte et consultez les caractéristiques des logements représentés.",
         "Renseignez un logement ou comparez deux profils, puis emportez un résumé PDF."]):
        with column.container(border=True):
            st.subheader(title)
            st.write(description)
    st.info("Une étude pédagogique : cet échantillon ne représente pas tout le parc français et les estimations ne remplacent pas un diagnostic DPE.")
    with st.expander("D’où viennent les données ?"):
        st.write("Les diagnostics ADEME de logements existants et neufs sont enrichis par les références locales "
                 "des communes : altitude moyenne et zones climatiques H1, H2, H3. La géographie BAN permet les rapprochements.")
        st.markdown("[Données ADEME](https://data.ademe.fr/) · [Base Adresse Nationale](https://adresse.data.gouv.fr/)")
        st.write("Les extractions historiques étaient plafonnées à 5 000 lignes par département et par source, "
                 "sans échantillonnage temporel représentatif. Le nettoyage et la part du neuf influencent les distributions.")
    with st.expander("Comprendre les unités et les limites"):
        st.write("La consommation est l’énergie finale totale des cinq usages en kWh/an : chauffage, eau chaude, "
                 "refroidissement, éclairage et auxiliaires. Elle n’est ni une facture ni une consommation par m².")
        st.write("L’âge est référencé à 2026 ; le neuf a reçu un âge nul par imputation. L’altitude est communale, "
                 "ou remplacée par la moyenne départementale des communes du référentiel. Les sous-zones ne sont pas inventées. "
                 "Les positions BAN ne certifient pas l’adresse ; plusieurs logements peuvent se superposer.")
    with st.expander("Détail des données chargées et méthode"):
        from src.version_store import VersionStore
        st.caption("Version de données chargée : " + VersionStore().active()["data"] + ". Aucun appel API, téléchargement ou entraînement au démarrage.")
        if df is not None:
            st.dataframe(pd.DataFrame({"Variable": [LABELS.get(c,c) for c in df], "Colonne technique": df.columns,
                                       "Valeurs absentes": df.isna().sum().values}), hide_index=True, width="stretch")
        st.write("Les modèles finaux sont contrôlés au chargement. Les résultats détaillés et leurs limites sont disponibles dans la page Prédiction.")
    with st.expander("Crédits et travaux du groupe"):
        st.write("Projet de groupe App_Enedis. Sources : ADEME, BAN et référentiel communes-france-2025. "
                 "Corrections géographiques intégrées du travail de Nouhayla, notamment Lyon et Pierre-Bénite. "
                 "Son enrichissement Rhône complet reste distinct et n’est pas rejoué sans ses fichiers.")
