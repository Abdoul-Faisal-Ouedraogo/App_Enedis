from pathlib import Path

import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_dynamic_filters import DynamicFilters

from src.utils.dataloader import generate_file_selector

ASSETS = "assets"

# Plotly configuration
config = {"width": "stretch"}

# General configuration
st.set_page_config(page_title="Statistics", page_icon="📊", layout="wide")

# === Path to CSV Files ===
DATASETS_DIR = Path(__file__).parent.parent / "data" / "datasets"


st.title("📊 Statistics of the DPE Dataset")

# === Side bar files selection ===

with st.sidebar:
    st.header("📂 Dataset Selection")

generate_file_selector()

# Load the data in memory.
data = st.session_state.get("df", None)

# === Display Data ===
if data is not None:
    # Check required columns
    required_cols = {"lat", "lon", "etiquette_dpe", "cout_total_5_usages"}
    if not required_cols.issubset(data.columns):
        st.error(f"❌ Missing columns: {required_cols - set(data.columns)}")
        st.stop()

    # Main tabs
    (
        tab1,
        tab2,
    ) = st.tabs(["🧮 Datasets Print", "📊 Dataset Statistics"])

    # --- Tab 1: Datasets ---
    with tab1:
        st.subheader("Your data preview")
        if data is not None:
            st.write(f"Number of rows: {len(data)}")
            st.dataframe(data.head(50), width="stretch")
        else:
            st.info("No CSV files uploaded.")

    # --- Tab 3: Statistics ---
    with tab2:
        # ------------------------------------------------------------------------------------------

        # Filter Section
        cols = ["nom_commune_ban", "type_batiment", "etiquette_dpe"]
        for c in cols:
            data[c] = data[c].fillna("Unknown").astype(str)

        dynamic_filters = DynamicFilters(data, filters=cols)
        st.markdown("<br>", unsafe_allow_html=True)
        st.write("Filters")
        dynamic_filters.display_filters(location="columns", num_columns=3, gap="large")

        filtered_df = dynamic_filters.filter_df()

        # Get the number of filtered rows
        n = filtered_df.shape[0]

        st.divider()

        # ------------------------------------------------------------------------------------------
        # Metrics Section
        col1, col2, col3, col4 = st.columns(4)

        # Mean surface habitable
        surface_moyenne = filtered_df["surface_habitable_logement"].mean()
        col1.metric(
            label="Average living area",
            value=f"{round(surface_moyenne, 2)} m²",
            border=True,
        )
        # Mean consumption
        consommation_moyenne = filtered_df["cout_total_5_usages"].mean()
        col2.metric(
            label="Average consumption (kWep/year)",
            value=f"{round(consommation_moyenne, 2)}",
            border=True,
        )
        # Mean cost
        cout_moyen = filtered_df["cout_total_5_usages"].mean()
        col3.metric(
            label="Average cost (€/year)",
            value=f"{round(cout_moyen, 2)} €",
            border=True,
        )
        # Most frequent DPE class
        most_common_dpe = filtered_df["etiquette_dpe"].mode()[0]
        icon = f"Small-DPE-{most_common_dpe.upper()}.png"
        # Detect active theme
        theme = st.get_option("theme.base")
        text_color = "rgba(250, 250, 250, 0.6)" if theme == "dark" else "rgba(30, 30, 30, 0.6)"
        with col4.container(border=True):
            st.markdown(
                """
                <style>
                .metric-label {
                    font-size: 0.875rem;        /* same label as metrics */
                    font-weight: 500;
                    color: {text_color};
                    text-align: left;
                    margin-bottom: 0.25rem;
                }
                </style>
                <div class="metric-label">Most frequent DPE label</div>
                """,
                unsafe_allow_html=True
            )
            st.image(os.path.join(ASSETS, icon), width=190)


        # ------------------------------------------------------------------------------------------
        # General Info
        col1, col2, col3 = st.columns([0.4, 0.3, 0.3])

        # Statistics Table
        with col1:
            st.write("")
            st.write("")
            conso_stats = filtered_df["conso_5_usages_ef"].describe()
            cout_stats = filtered_df["cout_total_5_usages"].describe()
            ges_stat = filtered_df["emission_ges_5_usages"].describe()
            with st.container():
                summary_df = pd.DataFrame(
                    {
                        "Energy consumption (kWep)": conso_stats,
                        "GES emissions (kgCO₂/year)": ges_stat,
                        "Cost (€)": cout_stats,
                    }
                ).round(2)
                st.markdown("**Statistics**")
                st.dataframe(
                    summary_df.style.set_table_styles(
                        [{"selector": "td, th", "props": [("font-size", "12px")]}]
                    )
                )
        # DPE class Distribution
        with col2:
            dpe_counts = (
                filtered_df["etiquette_dpe"]
                .value_counts()
                .reindex(["A", "B", "C", "D", "E", "F", "G"], fill_value=0)
            )
            labels = dpe_counts.index.tolist()
            counts = dpe_counts.values
            percentages = counts / counts.sum() * 100

            # DPE colors
            dpe_colors = {
                "A": "#006400",  # Dark Green
                "B": "#008000",  # Green
                "C": "#9ACD32",  # Yellow-Green
                "D": "#FFFF00",  # Yellow
                "E": "#FFA500",  # Orange
                "F": "#FF4500",  # Red-Orange
                "G": "#FF0000",  # Red
            }
            colors = [dpe_colors[label] for label in labels]

            # horizontal bar chart
            fig_col = go.Figure(
                data=[
                    go.Bar(
                        y=labels,
                        x=percentages,
                        marker_color=colors,
                        text=[f"{p:.2f}%" for p in percentages],
                        textposition="auto",
                        orientation="h",
                    )
                ]
            )

            fig_col.update_layout(
                title="Distribution of DPE classes",
                xaxis_title="",
                yaxis_title="DPE class",
            )
            fig_col.update_yaxes(autorange="reversed")

            st.plotly_chart(fig_col, config=config)

        # GES class Distribution
        with col3:
            ges_colors = {
                "A": "#E3D1F4",  # very light violet
                "B": "#C7A8E4",
                "C": "#AB7ED4",
                "D": "#8F55C4",
                "E": "#733BB4",
                "F": "#5722A4",
                "G": "#3B0A94",  # dark violet
            }

            # Count and order
            ges_counts = (
                filtered_df["etiquette_ges"]
                .value_counts()
                .reindex(["A", "B", "C", "D", "E", "F", "G"], fill_value=0)
            )
            labels = ges_counts.index.tolist()
            counts = ges_counts.values
            percentages = counts / counts.sum() * 100

            colors = [ges_colors[label] for label in labels]

            # horizontal bar chart
            fig_ges = go.Figure(
                data=[
                    go.Bar(
                        y=labels,
                        x=percentages,
                        marker_color=colors,
                        text=[f"{p:.2f}%" for p in percentages],
                        textposition="auto",
                        orientation="h",
                    )
                ]
            )

            fig_ges.update_layout(
                title="Distribution of GES classes",
                xaxis_title="",
                yaxis_title="GES class",
            )
            fig_ges.update_yaxes(autorange="reversed")

            st.plotly_chart(fig_ges, config=config)

        # Energy consumption and cost by DPE class
        col1, col2 = st.columns(2)

        # Energy consumption by DPE class
        with col1:
            fig_box = px.box(
                filtered_df,
                x="etiquette_dpe",
                y="conso_5_usages_ef",
                category_orders={"etiquette_dpe": ["A", "B", "C", "D", "E", "F", "G"]},
                points=False,
                title="Energy consumption by DPE class",
            )
            st.plotly_chart(fig_box, config=config)

        # Average cost by DPE class
        with col2:
            fig = px.histogram(
                filtered_df,
                x="etiquette_dpe",
                y="cout_total_5_usages",
                category_orders={"etiquette_dpe": ["A", "B", "C", "D", "E", "F", "G"]},
                histfunc="avg",
                title="Average cost by DPE class",
                labels={
                    "etiquette_dpe": "DPE class",
                    "cout_total_5_usages": "Cost (€)",
                },
                text_auto=True,
            )

            fig.update_layout(template="plotly_white", showlegend=False)
            st.plotly_chart(fig, config=config)

        st.divider()
        # ------------------------------------------------------------------------------------------
        # Energy consumption by use type
        st.subheader("Energy consumption by use type")
        usage_map = {
            "Heating": {
                "conso": "conso_chauffage_ef",
                "cout": "cout_chauffage",
                "ges": "emission_ges_chauffage",
            },
            "ECS": {
                "conso": "conso_ecs_ef",
                "cout": "cout_ecs",
                "ges": "emission_ges_ecs",
            },
            "Cooling": {
                "conso": "conso_refroidissement_ef",
                "cout": "cout_refroidissement",
                "ges": "emission_ges_refroidissement",
            },
            "Lighting": {
                "conso": "conso_eclairage_ef",
                "cout": "cout_eclairage",
                "ges": "emission_ges_eclairage",
            },
            "Auxiliaries": {
                "conso": "conso_auxiliaires_ef",
                "cout": "cout_auxiliaires",
                "ges": "emission_ges_auxiliaires",
            },
        }

        # Radio button filter
        usages = list(usage_map.keys())
        selected_usage = st.radio("Choose consumption type", usages)

        # Get the correct columns
        conso_col = usage_map[selected_usage]["conso"]
        cout_col = usage_map[selected_usage]["cout"]
        ges_col = usage_map[selected_usage]["ges"]

        col1, col2, col3 = st.columns([0.5, 0.25, 0.25])
        # statistics table
        with col1:
            summary_df = pd.DataFrame(
                {
                    "Energy consumption (kWep/year)": [
                        filtered_df[conso_col].mean(),
                        filtered_df[conso_col].std(),
                        filtered_df[conso_col].min(),
                        filtered_df[conso_col].max(),
                    ],
                    "GES emissions (kgCO₂/year)": [
                        filtered_df[ges_col].mean(),
                        filtered_df[ges_col].std(),
                        filtered_df[ges_col].min(),
                        filtered_df[ges_col].max(),
                    ],
                    "Cost (€)": [
                        filtered_df[cout_col].mean(),
                        filtered_df[cout_col].std(),
                        filtered_df[cout_col].min(),
                        filtered_df[cout_col].max(),
                    ],
                },
                index=["Average", "Std dev", "Min", "Max"],
            ).round(2)

            st.write(f"Energy consumption: {selected_usage}")
            st.dataframe(summary_df)

        # Gauge consumption
        with col2:
            total_conso_sum = filtered_df["conso_5_usages_ef"].sum()
            usage_sum = filtered_df[conso_col].sum()
            prop = usage_sum / total_conso_sum * 100

            # Simple gauge
            fig = go.Figure(
                go.Indicator(
                    mode="gauge+number",
                    value=prop,
                    number={"suffix": "%"},
                    title={
                        "text": f"Contribution of {selected_usage} <br> to energy consumption",
                        "font": {"size": 14},
                    },
                    gauge={
                        "axis": {"range": [0, 100], "showticklabels": False},
                        "bar": {"color": "#B22222"},
                    },
                )
            )

            # Adjust size
            fig.update_layout(
                height=250,
                width=250,
                margin={"t": 60, "b": 20, "l": 20, "r": 20},
            )

            st.plotly_chart(fig, config=config)

        # Gauge GES emissions
        with col3:
            total_ges_sum = filtered_df["emission_ges_5_usages"].sum()

            usage_ges_sum = filtered_df[ges_col].sum()

            prop_ges = usage_ges_sum / total_ges_sum * 100

            fig_ges = go.Figure(
                go.Indicator(
                    mode="gauge+number",
                    value=prop_ges,
                    number={"suffix": "%"},
                    title={
                        "text": f"Contribution of {selected_usage} <br> to GES emissions",
                        "font": {"size": 14},
                    },
                    gauge={
                        "axis": {"range": [0, 100], "showticklabels": False},
                        "bar": {"color": "#AB63FA"},
                    },
                )
            )

            fig_ges.update_layout(
                height=250,
                width=250,
                margin={"t": 60, "b": 20, "l": 20, "r": 20},
            )

            st.plotly_chart(fig_ges, config=config)

        st.divider()

        # ------------------------------------------------------------------------------------------
        # SCATTER PLOT
        st.subheader("Impact of variables on energy consumption")
        col1, col2 = st.columns([0.3, 0.7])
        with col1:
            numeric_cols = filtered_df.select_dtypes(include="number").columns.tolist()
            option = st.selectbox(
                "Choose Y variable",
                numeric_cols,
            )
            st.write("Y = ", option)
        with col2:
            corr_value = filtered_df["conso_5_usages_ef"].corr(filtered_df[option])
            fig = px.scatter(
                filtered_df.sample(n=1000 if n > 1000 else n, random_state=42),
                x="conso_5_usages_ef",  # X is fixed as total consumption
                y=option,
                labels={
                    "conso_5_usages_ef": "Total consumption (kWep/m²/year)",
                    option: option,
                },
                title=f"Relationship between energy consumption and {option} (Correlation = {corr_value:.2f})",
            )

            st.plotly_chart(fig, config=config)

else:
    st.info("⬆️ Please upload a dataset to get started.")
