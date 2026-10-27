from pathlib import Path

import streamlit as st

# Page config
st.set_page_config(
    page_title="DPE Ademe & Enedis - Home",
    page_icon="🏠",
    layout="wide",  # nécessaire pour aligner le logo à gauche
)

ASSETS_PATH = Path(__file__).parent.parent / "assets"
# Image
st.sidebar.image(ASSETS_PATH / "light_bulb.gif")


# Title and description
st.title("🏠 DPE Dashboard - Ademe & Enedis")
st.markdown("""
Welcome to the **DPE Ademe** app, an interactive tool to:
- Explore **housing energy data** (ADEME, Enedis),
- Visualize **dynamic maps** by geographic area,
- **Predict the DPE class** of a home using your Machine Learning models,
- Request data from the **ADEME API** to enrich your analysis.

Select a page below to get started:
""")

st.divider()

# Links to pages
col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.page_link("pages/context.py", label="Context", icon="📋")
    st.markdown("""
    Overview of available data and schemas.  
    - Live variables from ADEME & Enedis APIs  
    - Communes, climate zones, elevation  
    - Prediction inputs and processing workflow  
    - Data quality and sources
    """)

with col2:
    st.page_link("pages/data.py", label="Statistics & Visualizations", icon="📊")
    st.markdown("""
    Quickly explore the main characteristics of your dataset: 
    distributions, missing values, and descriptive statistics to better understand your data.
    """)

with col3:
    st.page_link("pages/map.py", label="DPE Map", icon="🗺️")
    st.markdown("""
    Visualize up to hundreds of thousands of homes on an **interactive map**.  
    Filter by region, department, or energy class.
    """)

with col4:
    st.page_link("pages/datasets.py", label="Datasets and Download", icon="🗃️")
    st.markdown("""
    Access and download the datasets used in this project.
    """)

with col5:
    st.page_link("pages/prediction.py", label="Predict DPE class", icon="🔮")
    st.markdown("""
    Use your **prediction models (.pkl)** to estimate the **DPE class (A → G)**  
    based on the home's characteristics.
    """)

with col6:
    st.page_link("pages/retrain_models.py", label="Model Retraining", icon="⚙️")
    st.markdown("""
    Retrain both regression and classification models on a new dataset of your choice.  
    Compare performance with previous models.
    """)

st.divider()

# Additional information section
col1, col2, col3 = st.columns(3)

with col2:
    with st.expander("About the application", icon="ℹ️"):
        st.markdown("""
        - **Author:** Abdoul, Mounir, Nouhayla
        - **Data sources:** [ADEME - DPE](https://data.ademe.fr) & [Enedis Open Data](https://data.enedis.fr)  
        - **Technologies:** Streamlit, Pydeck, Scikit-Learn, Pandas, Plotly  
        - **Repository:** [GitHub link](https://github.com/Abdoul-Faisal-Ouedraogo/App_Enedis)
        - **Last update:** October 2026  
        """)

    st.caption("💡 Tip: use the left sidebar to navigate between pages.")
