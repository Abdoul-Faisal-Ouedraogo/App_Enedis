import os

import joblib
import pandas as pd
import streamlit as st

from src.data_requesters import geo_api
from src.data_requesters.elevation import Elevation_API_requester

# Page configuration
st.set_page_config(page_title="DPE Prediction", page_icon="🔮", layout="centered")
st.title("🔮 Prediction of a Home's DPE Class")

ML_DIR = "MLmodels"
ASSETS = "assets"

# Dynamic model selector in sidebar


def get_available_model_versions():
    """Detect which model versions exist."""
    options = ["Original models"]
    retrain_reg = os.path.join(ML_DIR, "pipeline_best_regression_retrained.pkl")
    retrain_clf = os.path.join(ML_DIR, "pipeline_xgboost_classification_retrained.pkl")
    if os.path.exists(retrain_reg) and os.path.exists(retrain_clf):
        options.append("New models (retrained)")
    return options


def load_models(selection):
    """Load regression/classification pipelines and label encoder."""
    if selection == "New models (retrained)":
        reg_path = os.path.join(ML_DIR, "pipeline_best_regression_retrained.pkl")
        clf_path = os.path.join(ML_DIR, "pipeline_xgboost_classification_retrained.pkl")
    else:
        reg_path = os.path.join(ML_DIR, "pipeline_best_regression.pkl")
        clf_path = os.path.join(ML_DIR, "pipeline_xgboost_classification.pkl")

    reg_model = joblib.load(reg_path)
    clf_model = joblib.load(clf_path)
    label_enc = joblib.load(os.path.join(ML_DIR, "label_encoder_target.pkl"))
    return reg_model, clf_model, label_enc


# Sidebar model selection
st.sidebar.header("⚙️ Settings")
available_models = get_available_model_versions()
model_choice = st.sidebar.selectbox(
    "🧠 Model selection",
    options=available_models,
    help="Choose which version of the models to use for prediction.",
)
st.sidebar.info(f"Using: **{model_choice}**")

# Load models safely
try:
    pipeline_regression, pipeline_classification, label_encoder = load_models(
        model_choice
    )
    st.sidebar.success("✅ ML models successfully loaded")
except FileNotFoundError as e:
    st.error(f"❌ Missing model file: {e}")
    st.stop()
except Exception as e:
    st.error(f"❌ Error while loading models: {e}")
    st.stop()

# 🧾 User form
st.markdown("### 🧾 Enter the home's characteristics")

include_cost = st.checkbox("**Specify total cost (€/year)?**", value=False)
with st.form("form_pred"):
    # ---- City input (auto climate zone & altitude)
    st.subheader("🏙️ Location")
    city = st.text_input("City name", placeholder="e.g. Marseille, Lyon, Lille...")
    st.caption(
        "💡 You can also specify a district, e.g. 'Lyon 1', 'Paris 15', 'Marseille 8'."
    )

    # ---- Quantitative inputs
    st.subheader("🔹 Quantitative characteristics")
    cout_total_5_usages = None
    if include_cost:
        cout_total_5_usages = st.number_input(
            "Total cost 5 uses (€/year)", 0.0, 5000.0, 500.0, 10.0
        )
    surface_habitable_logement = st.number_input(
        "Living area (m²)", 10.0, 400.0, 75.0, 1.0
    )
    nombre_niveau_logement = st.number_input("Number of floors", 1, 10, 2)
    age_batiment = st.number_input("Building age (years)", 0, 150, 33)

    # ---- Qualitative inputs
    st.subheader("🔹 Qualitative characteristics")
    energy_options = {
        "Other": "Autre",
        "Natural gas": "Gaz naturel",
        "Electricity": "Électricité",
    }
    building_options = {
        "Apartment": "appartement",
        "House": "maison",
        "Building": "immeuble",
    }

    type_energie_principale_chauffage_label = st.selectbox(
        "Main heating energy", list(energy_options.keys())
    )
    type_batiment_label = st.selectbox("Building type", list(building_options.keys()))

    submitted = st.form_submit_button("🔮 Predict DPE class")

# 🚀 Prediction
if submitted:
    if not city.strip():
        st.error("❌ Please enter a city name before predicting.")
        st.stop()

    # ---- Step 1: Retrieve location info
    with st.spinner(f"📡 Retrieving climate zone for {city}..."):
        geo_info = geo_api.get_city_info(ville=city)
        zone_clim = geo_info.get("zone_climatique") if geo_info else None
        lat, lon = (
            geo_info.get("lat") if geo_info else None,
            geo_info.get("lon") if geo_info else None,
        )

    if not lat or not lon:
        st.warning("⚠️ Could not retrieve coordinates for this city.")
        altitude_moyenne = 0
    else:
        with st.spinner(f"⛰️ Fetching elevation data for {city}..."):
            elev_requester = Elevation_API_requester()
            altitude_moyenne = elev_requester.get_elevation(lat, lon) or 0

    # ---- Display fetched info
    st.markdown("### 🌦️ Automatically detected information")
    st.info(
        f"- **City:** {geo_info['city'] if geo_info else 'Unknown'}  \n"
        f"- **Latitude / Longitude:** {lat}, {lon}  \n"
        f"- **Climate zone:** {zone_clim or 'Unknown'}  \n"
        f"- **Average altitude:** {altitude_moyenne:.1f} m"
    )

    # ---- Prepare input dataframe
    user_input = {
        "cout_total_5_usages": cout_total_5_usages,
        "surface_habitable_logement": surface_habitable_logement,
        "nombre_niveau_logement": nombre_niveau_logement,
        "age_batiment": age_batiment,
        "altitude_moyenne": altitude_moyenne,
        "type_energie_principale_chauffage": energy_options[
            type_energie_principale_chauffage_label
        ],
        "type_batiment": building_options[type_batiment_label],
        "zone_climatique": zone_clim,
    }
    X_input = pd.DataFrame([user_input])

    # ---- Regression prediction if needed
    need_regression = X_input["cout_total_5_usages"].isnull().any()
    if need_regression:
        try:
            cost_pred = pipeline_regression.predict(
                X_input.drop(columns=["cout_total_5_usages"])
            )
            X_input["cout_total_5_usages"] = cost_pred[0]

        except ValueError as e:
            msg = str(e)
            if "Found unknown categories" in msg:
                bad_cat = msg.split("['")[1].split("']")[0]
                if "in column" in msg:
                    col_part = msg.split("in column")[1].strip().split()[0]
                    col_name = (
                        X_input.columns[int(col_part)]
                        if col_part.isdigit()
                        else col_part
                    )
                else:
                    col_name = "unknown column"
                st.error(
                    f"⚠️ The regression model doesn't recognize category **'{bad_cat}'** "
                    f"for variable **'{col_name}'**.\n\n"
                    f"This usually means your input contains a new value not seen during training.\n\n"
                    f"👉 Try switching to the **retrained model** in the sidebar or choose a different input."
                )
                st.stop()
            else:
                st.error(f"❌ Error during cost prediction: {e}")
                st.stop()

    # ---- Classification prediction
    try:
        y_pred_int = pipeline_classification.predict(X_input)
        y_pred_label = label_encoder.inverse_transform(y_pred_int)

    except ValueError as e:
        msg = str(e)
        if "Found unknown categories" in msg:
            bad_cat = msg.split("['")[1].split("']")[0]
            if "in column" in msg:
                col_part = msg.split("in column")[1].strip().split()[0]
                col_name = (
                    X_input.columns[int(col_part)] if col_part.isdigit() else col_part
                )
            else:
                col_name = "unknown column"
            st.error(
                f"⚠️ The model doesn't recognize category **'{bad_cat}'** "
                f"for variable **'{col_name}'**.\n\n"
                f"This typically means your input contains a value never seen during training "
                f"(e.g., a new climate zone or energy type).\n\n"
                f"👉 Try using the **retrained model** in the sidebar."
            )
            st.stop()
        else:
            st.error(f"❌ Unexpected error during prediction:\n\n```\n{e}\n```")
            st.stop()

    except Exception as e:
        st.error(f"❌ Unexpected error during prediction:\n\n```\n{e}\n```")
        st.stop()

    # ---- Display result
    dpe_colors = {
        "A": "#00b050",
        "B": "#92d050",
        "C": "#ffff00",
        "D": "#ffc000",
        "E": "#ff0000",
        "F": "#a61c00",
        "G": "#7030a0",
    }
    couleur = dpe_colors.get(str(y_pred_label[0]).upper(), "#CCCCCC")

    if need_regression:
        st.success(
            f"✅ Predicted Cost: **{int(X_input['cout_total_5_usages'][0])} €/year**"
        )
    st.success(f"✅ Predicted DPE class: **{y_pred_label[0]}**")

    # Centered image of the DPE label
    icon = f"DPE-{y_pred_label[0].upper()}.png"
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(os.path.join(ASSETS, icon), width=200)
