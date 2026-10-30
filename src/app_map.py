"""Dimensions réelles et cycle de vie du cadrage de la carte native Streamlit."""
import hashlib

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

from src.app_services import map_view

MAP_HEIGHT = 700

# Composant natif v2, local, sans dépendance JS externe. Sa largeur est celle de
# la colonne contenant la carte. Aucun accès aux éléments internes de Streamlit.
MEASURE_JS = """
export default function({parentElement, data, setStateValue}) {
    const probe = parentElement.querySelector('[data-map-dimensions]');
    let last = data.reported_width || 0;
    let timer;
    const report = () => {
        const width = Math.round(probe.getBoundingClientRect().width);
        if (width > 0 && Math.abs(width - last) > 1) {
            last = width;
            setStateValue('viewport_width', width);
        }
    };
    const observer = new ResizeObserver(() => {
        clearTimeout(timer);
        timer = setTimeout(report, 150);
    });
    observer.observe(probe);
    report();
    return () => { observer.disconnect(); clearTimeout(timer); };
}
"""

_measure = st.components.v2.component("enedis_map_dimensions",
    html='<div data-map-dimensions style="width:100%;height:1px" aria-hidden="true"></div>', js=MEASURE_JS)


def map_dimensions():
    previous = st.session_state.get("map_dimensions_probe", {})
    result = _measure(key="map_dimensions_probe", width="stretch", height=1,
                      data={"reported_width": previous.get("viewport_width")},
                      on_viewport_width_change=lambda: None)
    measured = result.get("viewport_width")
    if isinstance(measured, (int, float)) and np.isfinite(measured) and measured > 0:
        return float(measured), MAP_HEIGHT, True
    # Première passe serveur avant que le navigateur n'ait communiqué sa largeur.
    return 1000.0, MAP_HEIGHT, False


def selection_signature(frame):
    hashed = pd.util.hash_pandas_object(frame[["lat", "lon"]], index=True)
    # L'ordre d'affichage n'est pas un changement de sélection.
    return hashlib.sha256(np.sort(hashed.to_numpy()).tobytes()).hexdigest()


def update_camera(state, frame, width, height, measured=True, recenter=False):
    """Garder le même cadrage initial et la même clé tant que la sélection reste identique.

    Le zoom/déplacement manuel est conservé côté composant natif. Une nouvelle clé
    remonte explicitement la carte pour recentrer, même si les bornes sont identiques.
    Une première mesure réelle corrige la passe serveur de dimensions provisoires.
    Les redimensionnements suivants gardent le zoom manuel ; les dimensions les
    plus récentes seront utilisées au prochain recentrage ou changement de sélection.
    """
    signature = selection_signature(frame)
    refresh = (not state or state["selection"] != signature or recenter
               or (measured and not state["measured"]))
    if refresh:
        view = map_view(frame, width, height)
        return {"selection": signature, "generation": state["generation"] + 1 if state else 0,
                "measured": measured, "view": {"latitude": view.latitude, "longitude": view.longitude,
                                               "zoom": view.zoom, "pitch": 0}}
    return state


def camera_for_selection(frame):
    width, height, measured = map_dimensions()
    recenter = st.button("Recentrer sur la sélection", key="recenter_map", icon="🎯")
    state = update_camera(st.session_state.get("map_camera"), frame, width, height, measured, recenter)
    st.session_state.map_camera = state
    return pdk.ViewState(**state["view"]), f"housing_map_{state['generation']}"
