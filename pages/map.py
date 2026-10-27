from pathlib import Path

import pydeck as pdk
import streamlit as st

from src.utils.dataloader import generate_file_selector

# General configuration
st.set_page_config(page_title="DPE Map & Statistics", page_icon="🗺️", layout="wide")

# === Path to CSV Files ===
DATASETS_DIR = Path(__file__).parent.parent / "data" / "datasets"


st.title("🗺️ Map the DPE Dataset")


with st.sidebar:
    st.header("📂 Dataset Selection")

generate_file_selector()
data = st.session_state.get("df", None)


st.subheader("Geographical visualization of housing")

# === Global parameters ===
DEFAULT_POINTS_MAP = 50_000
DEFAULT_ROWS_DISPLAY = 10_000
NB_BINS = 50

# === Sidebar Filters ===

if data is not None:
    col_map, col_filters = st.columns([0.75, 0.25])

    with col_filters:
        st.markdown("### 🔎 Filters")

        # Choice of DPE classes
        dpe_classes = ["A", "B", "C", "D", "E", "F", "G"]
        selected_dpe = []
        for c in dpe_classes:
            if st.checkbox(f"Class {c}", value=True, key=f"dpe_{c}"):
                selected_dpe.append(c)

        # Filtering
        data_filtered = data[data["etiquette_dpe"].isin(selected_dpe)]

        # Slider to choose the number of points on the map
        max_points_possible = len(data_filtered)
        if max_points_possible == 0:
            st.warning("⚠️ No data matches the selected filters.")
            st.stop()

        nb_points_map = st.slider(
            "Number of homes displayed on the map 🗺️",
            min_value=0,
            max_value=max_points_possible,
            value=min(DEFAULT_POINTS_MAP, max_points_possible),
            step=10,
            help="Adjust to limit the number of points and improve smoothness.",
        )

        if nb_points_map == 0:
            st.error("🏠 No homes displayed on the map.")
            st.stop()
        # Random sampling
        if len(data_filtered) > nb_points_map:
            data_map = data_filtered.sample(nb_points_map, random_state=42)
            st.warning(
                f"🏠 {nb_points_map:,} homes displayed out of {max_points_possible:,}."
            )
        else:
            data_map = data_filtered
            st.success(f"🏠 All {len(data_filtered):,} homes are displayed.")

    with col_map:
        with st.spinner("⏳ Generating the map..."):
            load_bar = st.progress(0.0)

            # Define DPE colors
            dpe_colors = {
                "A": [38, 160, 110],  # Dark green
                "B": [84, 176, 87],  # Green
                "C": [165, 202, 118],  # Light green
                "D": [238, 229, 54],  # Yellow
                "E": [237, 180, 37],  # Orange
                "F": [231, 131, 63],  # Orange red
                "G": [212, 38, 41],  # Red
            }

            # Add color column to data_map
            data_map["color"] = data_map["etiquette_dpe"].map(
                lambda x: dpe_colors.get(x, [128, 128, 128])
            )

            # Pydeck map
            view_state = pdk.ViewState(
                latitude=data_map["lat"].mean(),
                longitude=data_map["lon"].mean(),
                zoom=6,
                pitch=0,
            )

            load_bar.progress(0.3)

            layer = pdk.Layer(
                "ScatterplotLayer",
                data=data_map,
                get_position="[lon, lat]",
                get_color="color",
                get_radius=10,
                pickable=True,
            )

            load_bar.progress(0.5)

            tooltip = {
                "html": "<b>DPE Label:</b> {etiquette_dpe}<br/>"
                "<b>Total Cost (5 Uses):</b> {cout_total_5_usages}<br/>"
                "<b>Lat:</b> {lat}<br/><b>Lon:</b> {lon} <br/>",
                "style": {"backgroundColor": "white", "color": "black"},
            }

            load_bar.progress(0.6)

            deck = pdk.Deck(
                map_style="mapbox://styles/mapbox/satellite-streets-v12",
                initial_view_state=view_state,
                layers=[layer],
                tooltip=tooltip,  # type: ignore
            )

            load_bar.progress(0.9)

            st.pydeck_chart(deck, use_container_width=True)

            load_bar.progress(1.0)

    load_bar.empty()
else:
    st.info("⬆️ Please upload a dataset to get started.")
