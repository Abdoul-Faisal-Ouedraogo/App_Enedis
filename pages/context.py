"""
# Context Page - Data Presentation and Visualization
"""

import os
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.data_requesters.ademe import Ademe_API_requester
from src.data_requesters.enedis import Enedis_API_requester

ASSETS_PATH = Path(__file__).parent.parent / "assets"
# Image
st.sidebar.image(ASSETS_PATH / "light_bulb.gif")

# Add parent path to import local modules
sys.path.append(os.path.dirname(os.path.dirname(__file__)))


# Plotly configuration
config = {"width": "stretch"}

# ⚙️ General configuration
st.set_page_config(page_title="DPE - Data Context", page_icon="📋", layout="wide")

# 📋 Title
st.title("📋 Context - Overview of Available Data")

st.markdown("""
This page presents all the **available data** in the project, their structure, 
their sources, and visualizations to better understand the usage context.
""")

st.divider()

# === Data sources overview ===
st.header("📊 Data Sources")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="🏛️ ADEME - DPE",
        value="Main source",
        help="Database of energy performance certificates",
    )
    st.caption("Energy data for French housing")

with col2:
    st.metric(
        label="⚡ Enedis",
        value="Complementary data",
        help="Electricity consumption by territory",
    )
    st.caption("Actual electricity consumption")

with col3:
    st.metric(
        label="🗺️ Geographic",
        value="Enrichment",
        help="Communes, climate zones, altitude",
    )
    st.caption("Geographic and climatic context")

with col4:
    st.metric(
        label="⛰️ Altitude",
        value="Elevation API",
        help="Precise altitude from GPS coordinates",
    )
    st.caption("Altitude enrichment")

st.divider()

# === ADEME data - DPE ===
st.header("🏛️ ADEME Data - Energy Performance Certificate (DPE)")

st.markdown("""
The **ADEME** data is the project's main source. The DPE evaluates the energy performance 
of housing and classifies them from **A (most efficient)** to **G (least efficient)**.
""")

# Dynamic retrieval of variables from the ADEME API
with st.expander("📋 See available DPE variables (fetched in real time from the API)"):
    # Choose between existing and new housing
    col1, col2 = st.columns(2)
    with col1:
        dataset_type = st.radio(
            "Housing type",
            ["Existing housing", "New housing"],
            index=0,
            horizontal=True,
        )

    neuf = dataset_type == "New housing"

    try:
        with st.spinner(f"Fetching ADEME API metadata ({dataset_type})..."):
            requester = Ademe_API_requester()
            fields_by_group = requester.get_fields_by_group(neuf=neuf)

        if fields_by_group:
            total_fields = sum(len(fields) for fields in fields_by_group.values())
            st.success(
                f"✅ {total_fields} variables successfully retrieved from the ADEME API"
            )

            # Show stats
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📊 Total fields", total_fields)
            with col2:
                st.metric("📁 Variable groups", len(fields_by_group))
            with col3:
                # Count unique types
                all_fields = []
                for fields in fields_by_group.values():
                    all_fields.extend(fields)
                types_count = len(set(f["type"] for f in all_fields))
                st.metric("🔢 Data types", types_count)

            # Display by group
            st.markdown("#### 📋 Variables by group")

            for group_name in sorted(fields_by_group.keys()):
                group_fields = fields_by_group[group_name]

                with st.container():
                    st.markdown(f"**📁 {group_name}** ({len(group_fields)} fields)")

                    # Create a DataFrame for display
                    df_group = pd.DataFrame(group_fields)
                    display_df = df_group[
                        ["key", "label", "type", "description"]
                    ].copy()
                    display_df.columns = ["Field name", "Label", "Type", "Description"]

                    st.dataframe(
                        display_df,
                        width="stretch",
                        hide_index=True,
                        height=min(len(group_fields) * 35 + 38, 400),
                    )

            # Export metadata option
            st.divider()
            st.markdown("#### 💾 Export metadata")

            # Create a DataFrame with all fields
            all_fields_list = []
            for group, fields in fields_by_group.items():
                for field in fields:
                    all_fields_list.append(field)

            df_all_fields = pd.DataFrame(all_fields_list)
            csv = df_all_fields.to_csv(index=False)

            filename = f"ademe_api_fields_{'new' if neuf else 'existing'}.csv"
            st.download_button(
                label="📥 Download full variable list (CSV)",
                data=csv,
                file_name=filename,
                mime="text/csv",
            )

    except Exception as e:
        st.error(f"❌ Error while fetching variables: {e}")

        # Fallback with basic information
        st.markdown("**Main variables (basic information)**:")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            **Identifiers and location**
            - `N°DPE`: Unique certificate ID
            - `Code_postal_(BAN)`: Postal code
            - `Commune_(BAN)`: Commune name
            - `Département`: Department code
            - `Longitude` / `Latitude`: GPS coordinates
            - `Altitude`: Dwelling altitude
            
            **Building characteristics**
            - `Type_bâtiment`: House, apartment, etc.
            - `Année_construction`: Year built
            - `Surface_habitable_logement`: Living area (m²)
            - `Type_installation_chauffage`: Heating system type
            - `Type_énergie_principale_chauffage`: Main heating energy
            - `Isolation_toiture`, `Isolation_murs`, `Isolation_plancher_bas`
            """)

        with col2:
            st.markdown("""
            **Energy performance**
            - `Classe_consommation_énergie`: A, B, C, D, E, F, G
            - `Conso_5_usages_é_finale`: Final consumption (kWh/m²/year)
            - `Conso_5_usages_é_primaire`: Primary consumption
            - `Classe_estimation_ges`: GHG emissions class
            - `Estimation_ges`: CO2 emissions (kg/m²/year)
            
            **Equipment**
            - `Type_installation_ECS`: Domestic hot water system
            - `Type_énergie_n°1_ECS`: Energy for hot water
            - `Qualité_isolation_enveloppe`: Envelope insulation quality
            - `Qualité_isolation_menuiseries`: Windows quality
            - `Type_ventilation`: Ventilation system
            """)

st.info("💡 **Source**: [data.ademe.fr](https://data.ademe.fr) - National DPE database")

st.divider()

# === Enedis data ===
st.header("⚡ Enedis Data - Electricity Consumption")

st.markdown("""
**Enedis** provides actual electricity consumption by territory, 
allowing to enrich the analysis with real consumption data.
""")

with st.expander(
    "📋 See available Enedis variables (fetched in real time from the API)"
):
    try:
        with st.spinner("Fetching Enedis API metadata..."):
            requester = Enedis_API_requester()
            fields = requester.get_dataset_fields()

        if fields:
            st.success(
                f"✅ {len(fields)} variables successfully retrieved from the Enedis API"
            )

            # Create a DataFrame for display
            df_fields = pd.DataFrame(fields)

            # Show stats
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📊 Total fields", len(fields))
            with col2:
                types_count = df_fields["type"].nunique()
                st.metric("🔢 Data types", types_count)
            with col3:
                with_desc = df_fields["description"].apply(lambda x: bool(x)).sum()
                st.metric("📝 Documented fields", with_desc)

            # Group by data type
            st.markdown("#### 📋 Variables by type")

            # Iterate by category
            types = df_fields["type"].unique()

            for data_type in sorted(types):
                fields_of_type = df_fields[df_fields["type"] == data_type]

                with st.container():
                    st.markdown(
                        f"**Type: `{data_type}`** ({len(fields_of_type)} fields)"
                    )

                    # Compact table
                    display_df = fields_of_type[["name", "label", "description"]].copy()
                    display_df.columns = ["Field name", "Label", "Description"]

                    st.dataframe(
                        display_df,
                        width="stretch",
                        hide_index=True,
                        height=min(len(fields_of_type) * 35 + 38, 300),
                    )

            # Export option
            st.divider()
            st.markdown("#### 💾 Export metadata")

            csv = df_fields.to_csv(index=False)
            st.download_button(
                label="📥 Download full variable list (CSV)",
                data=csv,
                file_name="enedis_api_fields.csv",
                mime="text/csv",
            )

    except Exception as e:
        st.error(f"❌ Error while fetching variables: {e}")

        # Fallback with basic information
        st.markdown("**Main variables (basic information)**:")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            **Location**
            - INSEE commune code
            - Commune name
            - Department code
            - Region
            
            **Consumption**
            - Annual consumption (MWh)
            - Number of sites
            - Average consumption per site
            """)

        with col2:
            st.markdown("""
            **Typology**
            - Residential sector
            - Consumption profile
            - Subscribed power
            
            **Temporality**
            - Reference year
            - Time evolution
            """)

st.info("💡 **Source**: [data.enedis.fr](https://data.enedis.fr) - Enedis Open Data")

st.divider()

# === Altitude data (Elevation API) ===
st.header("⛰️ Altitude Data - Elevation API")

st.markdown("""
The **Elevation API** enriches the data with the precise altitude of housing 
from their GPS coordinates (latitude/longitude).
""")

with st.expander("📋 See information about the Elevation API"):
    st.markdown("""
    ### 🎯 How it works
    
    The Elevation API is used to get the **altitude in meters** of a geographic point.
    
    **Input parameters**:
    - `lat`: Latitude (decimal)
    - `lon`: Longitude (decimal)
    
    **Example request**:
    ```
    https://api.elevationapi.com/api/Elevation?lat=48.8566&lon=2.3522
    ```
    """)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
    ### 📊 Returned data
        
    **Geographic point**:
    - `elevation`: Altitude in meters
    - `latitude`: Point latitude
    - `longitude`: Point longitude
    - `distanceFromOriginMeters`: Distance from origin
        
    **Metrics**:
    - `minElevation`: Minimum altitude
    - `maxElevation`: Maximum altitude
    - `distance`: Total distance
    - `numPoints`: Number of points
        """)

    with col2:
        st.markdown("""
        ### 📁 Source dataset
        
        **Characteristics**:
        - `name`: Dataset name
        - `description`: Description
        - `resolutionMeters`: Resolution in meters
        - `resolutionArcSeconds`: Resolution in arc seconds
        - `fileFormat`: Source file format
        - `attribution`: Data attribution
        
        **Quality**:
        - Global coverage
        - Accuracy varies by area
        - Multiple sources (SRTM, ASTER, etc.)
        """)

    st.info("""
    💡 **Usage in the project**: Altitude is an important factor for DPE calculations 
    because it influences heating needs (lower temperatures at higher altitude).
    """)

st.info(
    "💡 **Source**: [elevationapi.com](https://elevationapi.com) - Global altitude API"
)

st.divider()

# === Geographic data ===
st.header("🗺️ Geographic and Climatic Data")

st.markdown("""
Geographic data enrich analyses with the **territorial context** 
and the **climatic** setting of housing.
""")

tab1, tab2 = st.tabs(["🌍 French Communes", "🌡️ Climate Zones"])

with tab1:
    st.markdown("### French Communes Reference (2025)")

    st.info(
        "💡 **Source**: [data.gouv.fr - Communes et villes de France](https://www.data.gouv.fr/datasets/communes-et-villes-de-france-en-csv-excel-json-parquet-et-feather/) - Government open data"
    )

    # Chargement et affichage des données des communes
    data_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "communes-france-2025.csv"
    )

    if os.path.exists(data_path):
        try:
            df_communes = pd.read_csv(data_path, nrows=5)

            st.markdown("""
            📊 **File overview**: `communes-france-2025.csv`
            
            This file comes from the **French government's Open Data portal** and contains 
            comprehensive information on all communes in metropolitan and overseas France.
            
            **Characteristics**:
            - **Total number of communes**: ~35,000
            - **Available formats**: CSV, Excel, JSON, Parquet, Feather
            - **Updates**: Regular (2025 data)
            - **License**: Open License (Licence Ouverte)
            """)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📍 Geographic variables", "~40")
            with col2:
                st.metric("🏘️ Demographic data", "Yes")
            with col3:
                st.metric("🔗 Identifiers", "Multiple")

            with st.expander("See main available variables"):
                st.markdown("""
                **Identifiers and names**
                - `code_insee`: INSEE-assigned commune code
                - `nom_standard`: Normalized name with article (e.g., Le Havre)
                - `nom_sans_pronom`: Name without article (e.g., Havre)
                - `nom_a`: With preposition à/au/aux (e.g., au Havre)
                - `nom_de`: With preposition d'/de/du/des (e.g., du Havre)
                - `nom_sans_accent`: Without accents or special characters
                - `nom_standard_majuscule`: Uppercase (e.g., LE HAVRE)
                
                **Commune type**
                - `typecom`: Abbreviated type (COM, COMA, COMD, ARM)
                - `typecom_texte`: Textual type
                
                **Administrative location**
                - `reg_code` / `reg_nom`: Region code and name
                - `dep_code` / `dep_nom`: Department code and name
                - `canton_code` / `canton_nom`: Canton code and name
                - `epci_code` / `epci_nom`: EPCI code and name
                - `academie_code` / `academie_nom`: Academy code and name
                
                **Postal codes**
                - `code_postal`: Main postal code
                - `codes_postaux`: All postal codes attached
                
                **Geography**
                - `latitude_mairie` / `longitude_mairie`: Town hall coordinates
                - `latitude_centre` / `longitude_centre`: Territory centroid coordinates
                - `altitude_moyenne` / `altitude_minimale` / `altitude_maximale`: Altitudes (m)
                - `superficie_hectare` / `superficie_km2`: Area (ha and km²)
                
                **Demographics**
                - `population`: Municipal population
                - `densite`: Density (inhabitants/km²)
                
                **Urbanization**
                - `grille_densite`: 7-level density grid (INSEE)
                - `grille_densite_texte`: Text version of the density grid
                - `code_unite_urbaine`: Urban unit (agglomeration) code
                - `nom_unite_urbaine`: Agglomeration name
                - `taille_unite_urbaine`: Urban unit size
                - `type_commune_unite_urbaine`: Type (Outside urban unit or In urban unit)
                - `statut_commune_unite_urbaine`: Status (H: Outside, C: City center, B: Suburb, I: Isolated city)
                
                **Economy and services**
                - `zone_emploi`: Employment zone code (INSEE)
                - `code_insee_centre_zone_emploi`: INSEE code of the center commune of the employment zone
                - `niveau_equipements_services`: Equipment level (0 to 4)
                - `niveau_equipements_services_texte`: Text version of equipment level
                
                **Additional information**
                - `gentile`: Demonym (inhabitant name)
                - `url_wikipedia`: Wikipedia page
                - `url_villedereve`: Ville de rêve page
                """)

            st.dataframe(df_communes.head(), width="stretch")

        except Exception as e:
            st.warning(f"Unable to load preview: {e}")
    else:
        st.warning("⚠️ File `communes-france-2025.csv` not found in the `data/` folder")

with tab2:
    st.markdown("### Climate Zones by Department")

    # Chargement et visualisation des zones climatiques
    climate_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "climate_zones.csv"
    )

    if os.path.exists(climate_path):
        try:
            df_climate = pd.read_csv(climate_path)

            st.markdown("""
            France is divided into **3 regulatory climate zones** for building energy performance calculations:
            """)

            col1, col2, col3 = st.columns(3)

            with col1:
                h1_count = len(df_climate[df_climate["Zone climatique"] == "H1"])
                st.metric(
                    "🥶 Zone H1 (Cold)",
                    f"{h1_count} depts.",
                    help="North and East of France - Most rigorous climate",
                )

            with col2:
                h2_count = len(df_climate[df_climate["Zone climatique"] == "H2"])
                st.metric(
                    "🌤️ Zone H2 (Temperate)",
                    f"{h2_count} depts.",
                    help="Center and West of France - Intermediate climate",
                )

            with col3:
                h3_count = len(df_climate[df_climate["Zone climatique"] == "H3"])
                st.metric(
                    "☀️ Zone H3 (Warm)",
                    f"{h3_count} depts.",
                    help="South of France and Mediterranean coast - Mild climate",
                )

            # Graphique de répartition
            fig = px.pie(
                df_climate.groupby("Zone climatique").size().reset_index(name="count"),
                values="count",
                names="Zone climatique",
                title="Distribution of departments by climate zone",
                color="Zone climatique",
                color_discrete_map={"H1": "#4A90E2", "H2": "#F5A623", "H3": "#E94B3C"},
            )
            st.plotly_chart(fig, config=config)

            with st.expander("📋 See the full list of departments"):
                st.dataframe(df_climate, width="stretch", height=400)

        except Exception as e:
            st.warning(f"Unable to load climate data: {e}")
    else:
        st.warning("⚠️ File `climate_zones.csv` not found in the `data/` folder")

st.divider()

# === Input data structure for prediction ===
st.header("🔮 Variables Used for Prediction")

st.markdown("""
The DPE prediction model uses a set of **specific variables** to estimate 
the energy class of a dwelling (A → G). Here are the model inputs:
""")

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
        ### 📝 Model variables
    
        **Quantitative features**:
        - `surface_habitable_logement`: Living area (m²)
        - `nombre_niveau_logement`: Number of levels/floors
        - `age_batiment`: Building age (years)
        - `altitude_moyenne`: Average altitude (m)
        - `cout_total_5_usages`: Total annual cost (€/year) - optional
    
        **Qualitative features**:
        - `type_energie_principale_chauffage`: Main heating energy
            - Natural gas
            - Electricity  
            - Other
        - `type_batiment`: Building type
            - Apartment
            - House
            - Building
        - `zone_climatique`: Regulatory climate zone (H1, H2, H3)
    """)

with col2:
    st.markdown("""
    ### 🔄 Prediction process
    
    **Step 1: User input**
    - City name → automatic retrieval of GPS coordinates
    
    **Step 2: Automatic enrichment**
    - Latitude/Longitude → via communes database
    - Climate zone → determined by department
    - Altitude → fetched via Elevation API
    
    **Step 3: Cost prediction (if not provided)**
    - Regression model to estimate `cout_total_5_usages`
    - Based on other dwelling characteristics
    
    **Step 4: DPE class prediction**
    - XGBoost classification model
    - Output: Energy class from A (best) to G (worst)
    """)

st.info("""
💡 **Practical usage**: On the **Prediction** page, the user only needs to enter:
- City name (automatic enrichment)
- Living area, number of levels, building age
- Heating energy type and building type
- Optionally: total annual cost

The model automatically retrieves the climate zone and altitude!
""")

st.divider()

# === Data workflow ===
st.header("🔄 Data Processing Flow")

st.markdown("""
Here is the application's **full data processing workflow**:
""")

# Diagramme de flux avec des colonnes
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""
    ### 1️⃣ Collection
    📥 **Sources**
    - ADEME API
    - Enedis Open Data
    - CSV files
    """)

with col2:
    st.markdown("""
    ### 2️⃣ Enrichment
    🔧 **Additions**
    - Climate zones
    - Geographic data
    - Altitudes
    - Densities
    """)

with col3:
    st.markdown("""
    ### 3️⃣ Processing
    ⚙️ **Cleaning**
    - Missing values
    - Duplicates
    - Normalization
    - Feature engineering
    """)

with col4:
    st.markdown("""
    ### 4️⃣ Usage
    🎯 **Applications**
    - Visualizations
    - Statistics
    - ML predictions
    - Export
    """)

st.divider()

# === Data quality ===
st.header("✅ Data Quality and Reliability")

st.markdown("""
**Data quality** is essential to obtain reliable analyses and predictions.
""")

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    ### Strengths ✅
    - Official certified data
    - Regular updates
    - Full national coverage
    - Standardized variables
    - Precise geolocation
    """)

with col2:
    st.markdown("""
    ### Warnings ⚠️
    - Possible missing values
    - Heterogeneity in older data
    - Evolving DPE standards
    - Quality varies by department
    - Enedis data aggregated by commune
    """)

st.divider()

# === Footer ===
st.caption("💡 Use the left sidebar to navigate to other pages and work with the data.")
st.caption("📊 **Data** page: Visualize data on an interactive map")
st.caption("🔮 **Prediction** page: Use the ML model to predict the DPE class")
st.caption("🌐 **API** page: Query the ADEME API in real time")
st.caption("📈 **Stats** page: Analyze detailed dataset statistics")
