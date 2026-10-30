"""Interface française des niveaux Standard et Intermédiaire."""
import logging
from pathlib import Path

import pandas as pd
import streamlit as st

from src import project_paths
from src.final_model_loader import load_final_bundle
from src.app_services import (LABELS, read_data, filter_data, csv_bytes, chart_pngs,
                              map_points, build_map, category_options, predict)


def number(value, decimals=0):
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


@st.cache_data(show_spinner="Lecture des données locales…", max_entries=2)
def cached_data(path, stamp):
    return read_data(path)


@st.cache_resource(show_spinner="Contrôle et chargement des deux modèles finaux…", max_entries=1)
def cached_bundle(stamps):
    return load_final_bundle()


@st.cache_data(show_spinner="Préparation des graphiques…", max_entries=8)
def cached_charts(data, measure, percent):
    return chart_pngs(data, measure, percent)


@st.cache_data(show_spinner="Préparation du CSV…", max_entries=2)
def cached_csv(data):
    return csv_bytes(data)


def bundle():
    root = project_paths.ROOT
    paths = [root / "MLmodels/final_models.json", *sorted((root / "MLmodels/final_geo_v1").glob("*"))]
    stamps = tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in paths if p.is_file())
    return cached_bundle(stamps)


def load_frame():
    path = project_paths.DATA_PATH
    try:
        frame = cached_data(str(path), (path.stat().st_mtime_ns, path.stat().st_size))
        if frame.empty:
            st.warning("Le fichier local est vide. Fournissez le CSV préparé par le groupe.")
        return frame
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        logging.getLogger(__name__).warning("Lecture impossible : %s", exc)
        st.error("Données locales absentes ou illisibles : output/cleaned_data.csv. "
                 "Récupérez le fichier préparé auprès du groupe. Aucun téléchargement automatique.")
        return None


def context(df):
    st.title("🏡 Comprendre l’habitat et son énergie")
    st.write("Explorer les diagnostics de performance énergétique et estimer, à partir de sept "
             "caractéristiques, une consommation annuelle et une classe DPE.")
    st.image(str(project_paths.ROOT / "assets/habitat.svg"), width="stretch")
    left, right = st.columns(2)
    with left:
        st.subheader("📚 Des données publiques à l’étude locale")
        st.markdown("Les extractions **ADEME DPE logements existants et neufs** sont préparées dans le "
                    "notebook 1. Les identifiants géographiques BAN permettent de rapprocher les communes "
                    "du référentiel communes-france-2025 : altitude et zones climatiques **H1, H2, H3**.")
        st.markdown("[Catalogue des données ADEME](https://data.ademe.fr/) · "
                    "[Base Adresse Nationale](https://adresse.data.gouv.fr/)")
        st.write("Les corrections de jointure Lyon/Pierre-Bénite sont intégrées. L’altitude manquante "
                 "est complétée par la moyenne départementale. Les sous-zones climatiques ne sont pas déduites.")
    with right:
        st.subheader("🔎 Ce que mesure l’application")
        st.write("Consommation finale totale des cinq usages en kWh/an : chauffage, eau chaude, "
                 "refroidissement, éclairage et auxiliaires. Ce n’est ni une consommation par m² "
                 "ni une facture ni une consommation d’énergie primaire.")
        st.info("Application pédagogique locale. Une estimation statistique ne remplace pas un DPE réglementaire.")
    st.subheader("📦 Données réellement chargées")
    if df is not None:
        a, b, c = st.columns(3)
        a.metric("Logements chargés", number(len(df)))
        b.metric("Départements renseignés", df.code_departement_ban.nunique() if "code_departement_ban" in df else "—")
        c.metric("Colonnes disponibles", len(df.columns))
        st.caption("Fichier lu : output/cleaned_data.csv. Aucun appel API ni entraînement au démarrage.")
        details = pd.DataFrame({"Colonne": df.columns, "Description": [LABELS.get(c, c) for c in df],
                                "Valeurs absentes": df.isna().sum().values})
        with st.expander("Consulter les colonnes et les valeurs manquantes"):
            st.dataframe(details, hide_index=True, width="stretch")
    st.warning("Cet échantillon ne représente pas le parc français : les extractions historiques étaient "
               "plafonnées à 5 000 lignes par département et par source, sans échantillonnage temporel représentatif. "
               "Les filtres de nettoyage et la part du neuf influencent les distributions.")
    st.write("L’âge utilise une référence fixe **2026**. Les logements neufs ont reçu un âge nul par imputation. "
             "Les coordonnées BAN ne garantissent pas l’identité d’un bâtiment ; plusieurs logements peuvent se superposer. "
             "Le travail Rhône de Nouhayla est conservé séparément et son enrichissement complet n’est pas rejoué ici.")


def reset_filters():
    for key in list(st.session_state):
        if key.startswith("filter_"):
            del st.session_state[key]


def filters(df):
    st.sidebar.divider()
    st.sidebar.subheader("Affiner les logements")
    st.sidebar.caption("Liste vide = toutes les valeurs. Les choix suivants s’adaptent aux choix précédents.")
    st.sidebar.button("Réinitialiser les filtres", on_click=reset_filters)
    selections = {}
    facet = df
    for col in ["code_departement_ban", "etiquette_dpe", "type_batiment", "type_energie_principale_chauffage"]:
        if col not in df:
            st.sidebar.caption(f"{LABELS[col]} : colonne absente")
            continue
        options = sorted(facet[col].dropna().unique().tolist())
        key = "filter_" + col
        if key in st.session_state:
            st.session_state[key] = [v for v in st.session_state[key] if v in options]
        selections[col] = st.sidebar.multiselect(LABELS[col], options, key=key)
        if selections[col]:
            facet = facet[facet[col].isin(selections[col])]
    surface = None
    include = True
    if "surface_habitable_logement" in df:
        values = df.surface_habitable_logement.dropna()
        if len(values):
            low, high = float(values.min()), float(values.max())
            if low < high:
                surface = st.sidebar.slider("Surface habitable (m²)", low, high, (low, high), key="filter_surface")
            else:
                st.sidebar.caption(f"Surface unique : {number(low, 1)} m²")
            include = st.sidebar.checkbox("Inclure les surfaces non renseignées", value=True, key="filter_missing")
    result = filter_data(df, selections, surface, include)
    st.sidebar.caption(f"{number(len(result))} / {number(len(df))} logements retenus")
    return result


def exploration(df):
    st.title("📊 Explorer les logements")
    st.write("Les indicateurs, tableaux et exports suivent tous les filtres de la barre latérale.")
    subset = filters(df)
    if subset.empty:
        st.info("Aucun logement ne correspond à ces filtres. Élargissez la surface ou réinitialisez les filtres.")
        return
    a, b, c, d = st.columns(4)
    a.metric("Logements retenus", number(len(subset)))
    b.metric("Surface moyenne", number(subset.surface_habitable_logement.mean(), 1) + " m²"
             if "surface_habitable_logement" in subset and subset.surface_habitable_logement.notna().any() else "—")
    c.metric("Consommation moyenne", number(subset.conso_5_usages_ef.mean()) + " kWh/an"
             if "conso_5_usages_ef" in subset and subset.conso_5_usages_ef.notna().any() else "—")
    d.metric("Part F et G", number(subset.etiquette_dpe.isin(["F", "G"]).mean() * 100, 1) + " %"
             if "etiquette_dpe" in subset else "—")
    st.caption("Moyennes sur les valeurs renseignées. Part F/G calculée sur tous les logements filtrés.")
    measures = [c for c in ["conso_5_usages_ef", "surface_habitable_logement"] if c in subset]
    if measures:
        measure = st.radio("Grandeur à explorer", measures, format_func=LABELS.get, horizontal=True)
        percent = st.checkbox("Afficher les barres en pourcentage")
        required = [c for c in ["etiquette_dpe", "conso_5_usages_ef", "surface_habitable_logement"] if c in subset]
        charts = cached_charts(subset[required], measure, percent)
        columns = st.columns(2)
        for i, (name, png) in enumerate(charts.items()):
            with columns[i % 2]:
                st.image(png, width="stretch")
                st.download_button("📥 Exporter ce graphique en PNG", png, f"dpe_{name}.png", "image/png", key="png_"+name)
        if len(charts) < 4:
            st.warning("Certains graphiques sont indisponibles : colonnes ou valeurs nécessaires absentes.")
        st.caption("Barres, histogramme et quartiles : toutes les lignes filtrées renseignées. "
                   "Boîtes : points extrêmes masqués, valeurs conservées dans les calculs. "
                   "Nuage : au plus 5 000 logements filtrés, tirage fixe (graine 42), effectif inscrit sur le graphique.")
    else:
        st.warning("Les colonnes de consommation et de surface sont absentes ; les graphiques ne peuvent pas être construits.")
    st.subheader("Détail de la sélection")
    st.dataframe(subset.head(500).rename(columns=LABELS), hide_index=True, width="stretch")
    st.caption(f"Aperçu : {number(min(500, len(subset)))} lignes. Le CSV contient les {number(len(subset))} lignes filtrées, toutes les colonnes et les noms d’origine.")
    # L’export complet est calculé seulement sur demande et ne persiste pas après changement des filtres.
    if st.button("Préparer l’export CSV filtré"):
        st.download_button("📥 Télécharger les données filtrées", cached_csv(subset), "logements_filtres.csv",
                           "text/csv", on_click="ignore")


def carte(df):
    st.title("🗺️ Situer les logements")
    subset = filters(df)
    if subset.empty:
        st.info("Aucun logement ne correspond à ces filtres. Élargissez-les pour afficher la carte.")
        return
    limit = st.select_slider("Nombre maximal de marqueurs", options=[1000, 2500, 5000, 10000], value=5000)
    basemap = st.checkbox("Afficher le fond de carte en ligne (CARTO)", value=False)
    st.caption("Le fond CARTO est facultatif et nécessite Internet. Sans ce fond, les marqueurs restent navigables sur un canevas local.")
    points, valid = map_points(subset, limit)
    a, b, c = st.columns(3)
    a.metric("Logements filtrés", number(len(subset)))
    b.metric("Coordonnées admissibles", number(valid))
    c.metric("Logements représentés", number(len(points)))
    st.caption(f"{number(len(subset) - valid)} coordonnées absentes ou hors emprise écartées. "
               "Contrôle : valeurs finies, latitude de 41 à 51,5°, longitude de −5,5 à 10° (métropole et Corse). "
               "Les points géographiquement plausibles ne sont pas certifiés à l’adresse.")
    if points.empty:
        st.warning("Aucune coordonnée admissible. Les colonnes lat/lon doivent être présentes et renseignées.")
        return
    st.info(f"{number(len(points))} logements représentés sur {number(valid)} géolocalisables : "
            + ("échantillon aléatoire déterministe (graine 42), sans pondération." if len(points) < valid else "affichage complet de la sélection géolocalisable."))
    st.pydeck_chart(build_map(points, basemap), height=570, width="stretch")
    st.caption("Survolez un marqueur pour lire ses informations. Déplacez et zoomez avec la souris. "
               "Couleurs : A vert → G rouge ; inconnu gris. Plusieurs logements à une adresse peuvent se superposer.")


def prediction(df):
    st.title("✨ Estimer un logement")
    st.write("Deux modèles finaux, sept caractéristiques communes. Les résultats sont des estimations pédagogiques.")
    try:
        models = bundle()
    except Exception:
        logging.getLogger(__name__).exception("Échec du chargement des modèles finaux")
        st.error("Les modèles finaux sont absents, incompatibles ou leur contrôle d’intégrité a échoué. "
                 "Vérifiez MLmodels/final_geo_v1/, le manifeste et requirements-app.txt. Aucun ancien modèle n’est utilisé.")
        return
    contract = models["variables"]["classification"]
    year = contract["reference_year"]
    options = category_options(models)
    st.info(f"Âge = {year} − année de construction, indépendamment de l’année actuelle. "
            "Pour le neuf, la préparation du modèle a imputé l’âge à 0. Zones H1 (froide), H2 (tempérée), "
            "H3 (méditerranéenne) : reprendre la zone du référentiel départemental du projet, sans sous-zone.")
    with st.form("logement"):
        left, right = st.columns(2)
        with left:
            surface = st.number_input("Surface habitable (m²)", min_value=0.1, max_value=10000.0, value=80.0, step=1.0)
            levels = st.number_input("Nombre de niveaux du logement", min_value=1, max_value=100, value=1, step=1)
            age = st.number_input(f"Âge du bâtiment en {year} (années)", min_value=0, max_value=1000, value=30, step=1)
            altitude = st.number_input("Altitude moyenne de la commune (m)", min_value=-500.0, max_value=5000.0, value=150.0, step=10.0)
        values = dict(zip(contract["quantitative_features"], [surface, levels, age, altitude]))
        with right:
            for col in contract["qualitative_features"]:
                values[col] = st.selectbox(LABELS[col], options[col])
            st.caption("Catégories reprises de l’encodeur final : « Autre » regroupe les énergies selon la préparation commune.")
        submitted = st.form_submit_button("Calculer les estimations", type="primary")
    st.caption("Bornes de saisie : garde-fous physiques larges, pas une garantie de validité du modèle. "
               "L’altitude est communale ; le nombre de niveaux concerne le logement.")
    if submitted:
        try:
            if df is not None:
                outside = [LABELS[col] for col in contract["quantitative_features"] if col in df
                           and df[col].notna().any() and not df[col].min() <= values[col] <= df[col].max()]
                if outside:
                    st.warning("Valeur hors du domaine observé dans le CSV : " + ", ".join(outside) + ". Estimation extrapolée, particulièrement incertaine.")
            consumption, label = predict(models, values)
            a, b = st.columns(2)
            a.metric("Consommation finale estimée · cinq usages", number(consumption) + " kWh/an")
            b.metric("Lettre DPE estimée", label)
            st.caption("La lettre est produite par le classificateur ; elle n’est pas déduite de la consommation estimée.")
        except (ValueError, TypeError, KeyError):
            st.error("Saisie invalide ou incompatible avec le contrat des modèles. Vérifiez les sept caractéristiques.")
    results = models["results"]
    st.subheader("Résultats réels des modèles finaux")
    st.caption(f"Lot réservé interne : {number(results['classification']['rows'])} logements, réceptions depuis 2025. "
               "Choix des modèles figé avant son évaluation ; ce lot n’est pas une validation externe indépendante.")
    a, b, c = st.columns(3)
    a.metric("DPE correctement classés", number(results["classification"]["accuracy"] * 100, 2) + " %")
    b.metric("F1 macro A–G", number(results["classification"]["f1_macro"], 4))
    c.metric("Erreur absolue moyenne", number(results["regression"]["mae"], 2) + " kWh/an")
    st.warning("La MAE est une moyenne des erreurs sur un groupe. Elle ne constitue pas un intervalle de confiance "
               "pour ce logement. Le modèle ne fournit pas d’intervalle individuel calibré.")
    rows = []
    for source, scores in results["by_source"].items():
        rows.append({"Population": source, "Effectif": scores["classification"]["rows"],
                     "Accuracy DPE": scores["classification"]["accuracy"],
                     "F1 macro": scores["classification"]["f1_macro"],
                     "MAE (kWh/an)": scores["regression"]["mae"],
                     "RMSE (kWh/an)": scores["regression"]["rmse"], "R²": scores["regression"]["r2"]})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.write("Sur les logements existants, l’accuracy tombe à environ 38,70 % et la MAE atteint 2 802 kWh/an. "
             "L’ancien est moins bien couvert que le neuf ; le mélange des populations masque cet écart.")
    with st.expander("Détail des classes A à G et erreurs de consommation"):
        class_report = pd.DataFrame({k: results["classification"]["report"][k] for k in "ABCDEFG"}).T
        class_report = class_report.rename(columns={"precision": "Précision", "recall": "Rappel", "f1-score": "F1", "support": "Effectif"})
        st.dataframe(class_report, width="stretch")
        st.dataframe(pd.DataFrame(results["regression_by_dpe"]).T.rename(columns={
            "rows": "Effectif", "mae": "MAE (kWh/an)", "rmse": "RMSE (kWh/an)", "r2": "R²"}), width="stretch")
    st.error("F/G : fiabilité faible. Précision d’environ 8,77 % pour F et 5,82 % pour G, donc nombreuses "
             "fausses alertes. MAE de consommation : environ 4 265 kWh/an pour F et 6 668 kWh/an pour G. "
             "Le lot G ne compte que 467 logements. Ne prenez pas de décision de rénovation sur cette seule estimation.")
    st.caption("Forêts aléatoires finales, entraînement + validation : 453 680 lignes. Séparation temporelle avec groupes "
               "communs exclus ; distributions différentes entre périodes. Nettoyage IQR et regroupements d’énergies "
               "effectués globalement avant séparation : toute la chaîne de préparation n’est pas validée sans fuite. "
               "Voir doc/modeles_finaux_2026-10-29.md pour le protocole et toutes les limites.")


def run():
    st.markdown("""<style>
        .stApp {background-color:#f8faf9;} h1,h2,h3 {color:#143c43;}
        [data-testid="stSidebar"] {background:#edf3f0;}
        [data-testid="stMetric"] {background:white;padding:14px;border-radius:12px;border:1px solid #dde8e2;}
        .block-container {padding-top:2rem;max-width:1450px;}
        </style>""", unsafe_allow_html=True)
    st.sidebar.title("🏡 Habitat & énergie")
    st.sidebar.caption("DPE · étude locale ADEME")
    page = st.sidebar.radio("Navigation", ["Contexte", "Exploration", "Carte", "Prédiction"], key="page")
    df = load_frame()
    if page == "Contexte":
        context(df)
    elif page == "Prédiction":
        prediction(df)
    elif df is not None and not df.empty:
        {"Exploration": exploration, "Carte": carte}[page](df)
    st.sidebar.divider()
    st.sidebar.caption("Local uniquement · sans extraction ni réentraînement")
