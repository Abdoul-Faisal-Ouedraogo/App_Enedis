"""Interface française des niveaux Standard et Intermédiaire."""
import logging
import json

import pandas as pd
import streamlit as st

from src import project_paths
from src.final_model_loader import load_final_bundle
from src.app_design import context, styles, scale, NAV_LABELS
from src.app_prediction_ui import render_prediction
from src.app_map import camera_for_selection, MAP_HEIGHT
from src.app_services import (LABELS, read_data, filter_data, csv_bytes, chart_pngs,
                              map_points, build_map)


def number(value, decimals=0):
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


@st.cache_data(show_spinner="Lecture des données locales…", max_entries=2)
def cached_data(path, stamp):
    return read_data(path)


@st.cache_resource(show_spinner="Contrôle et chargement des deux modèles finaux…", max_entries=1)
def cached_bundle(stamps):
    models = load_final_bundle()
    models["version"] = json.loads((project_paths.ROOT / "MLmodels/final_models.json").read_text(encoding="utf-8"))["version"]
    return models


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
        st.error("Données locales absentes ou illisibles. "
                 "Récupérez le jeu préparé auprès du groupe. Aucun téléchargement automatique.")
        return None


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
    active = [LABELS[col] + " : " + ", ".join(values) for col, values in selections.items() if values]
    if surface and (surface[0] > low or surface[1] < high):
        active.append(f"Surface : {number(surface[0], 1)} à {number(surface[1], 1)} m²")
    if not include:
        active.append("Surfaces non renseignées exclues")
    with st.container(border=True):
        st.markdown("**Filtres actifs**")
        st.write(" · ".join(active) if active else "Tous les logements · aucun filtre restrictif")
        st.button("Effacer les filtres actifs", on_click=reset_filters)
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
        st.session_state.pop("map_camera", None)
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
        st.session_state.pop("map_camera", None)
        st.warning("Aucune coordonnée admissible. Les colonnes lat/lon doivent être présentes et renseignées.")
        return
    st.info(f"{number(len(points))} logements représentés sur {number(valid)} géolocalisables : "
            + ("échantillon aléatoire déterministe (graine 42), sans pondération." if len(points) < valid else "affichage complet de la sélection géolocalisable."))
    scale()
    view, map_key = camera_for_selection(subset)
    st.pydeck_chart(build_map(points, basemap, view=view), height=MAP_HEIGHT, width="stretch",
                    key=map_key, on_select="rerun")
    st.caption("Survolez un marqueur pour lire ses informations. Déplacez et zoomez avec la souris. "
               "Couleurs : A vert → G rouge ; inconnu gris. Plusieurs logements à une adresse peuvent se superposer.")


def prediction(df):
    try:
        models = bundle()
    except Exception:
        logging.getLogger(__name__).exception("Échec du chargement des modèles finaux")
        st.error("Les modèles finaux sont indisponibles ou leur contrôle a échoué. Contactez le groupe pour restaurer les artefacts locaux compatibles.")
        return
    render_prediction(models, df)


def run():
    styles()
    st.sidebar.title("🏡 Habitat & énergie")
    st.sidebar.caption("DPE · étude locale ADEME")
    page = st.sidebar.radio("Navigation", ["Contexte", "Exploration", "Carte", "Prédiction"], key="page", format_func=NAV_LABELS.get)
    df = load_frame()
    if page == "Contexte":
        context(df)
    elif page == "Prédiction":
        prediction(df)
    elif df is not None and not df.empty:
        {"Exploration": exploration, "Carte": carte}[page](df)
    st.sidebar.divider()
    st.sidebar.caption("Local uniquement · sans extraction ni réentraînement")
