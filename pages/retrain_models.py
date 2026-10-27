import os
import pickle
import time

import joblib
import numpy as np
import streamlit as st
from sklearn.metrics import accuracy_score, mean_squared_error, r2_score
from sklearn.preprocessing import LabelEncoder

from src.utils.dataloader import generate_file_selector

MODELS_DIR = "./MLmodels/"

# General configuration
st.set_page_config(page_title="Model retaining", page_icon="⚙️")


# helpers
def load_model(path):
    return joblib.load(path)


def save_model(obj, path):
    joblib.dump(obj, path)


def rmse_score(y_true, y_pred):
    """Compute RMSE safely (compatible with older sklearn versions)."""
    try:
        return mean_squared_error(y_true, y_pred, squared=False)
    except TypeError:
        return np.sqrt(mean_squared_error(y_true, y_pred))


def diff_icon(new, old, higher_is_better=True):
    """Display an icon depending on metric improvement."""
    if old is None:
        return ""
    if new == old:
        return "➖"
    if (new > old and higher_is_better) or (new < old and not higher_is_better):
        return "✅🔼"
    else:
        return "⚠️🔽"


# Interface
st.title("🔄 Retrain regression and classification models")
st.caption("Training may take several minutes depending on dataset size ⏳")
st.write(
    "Select a dataset in the **sidebar**, then click the button to retrain both models on the new data."
)

# Sidebar dataset selector
with st.sidebar:
    st.header("📂 Dataset selection")
    generate_file_selector(sidebar=True)

df = st.session_state.get("df", None)
if df is None:
    st.info("⬅️ Please select a dataset in the sidebar.")
    st.stop()

st.success(f"✅ Dataset loaded: {st.session_state.get('last_file', '')}")
st.write(f"**Rows:** {len(df)}")
st.dataframe(df.head())

# Retraining
if st.button("🚀 Retrain models"):
    with st.spinner("Processing..."):
        # Load features and targets info
        with open(
            os.path.join(MODELS_DIR, "features_target_columns_regression.pkl"), "rb"
        ) as f:
            reg_info = pickle.load(f)
        with open(
            os.path.join(MODELS_DIR, "features_target_columns_classification.pkl"), "rb"
        ) as f:
            clf_info = pickle.load(f)

        reg_features = (
            reg_info["quantitative_features"] + reg_info["qualitative_features"]
        )
        reg_target = reg_info["target"]
        clf_features = (
            clf_info["quantitative_features"] + clf_info["qualitative_features"]
        )
        clf_target = clf_info["target"]

        # Regression
        with st.spinner("Training regression model..."):
            start = time.time()

            reg_pipeline_orig = load_model(
                os.path.join(MODELS_DIR, "pipeline_best_regression.pkl")
            )
            X_reg, y_reg = df[reg_features], df[reg_target]

            # Evaluate original model on new data
            try:
                y_pred_orig = reg_pipeline_orig.predict(X_reg)
                metrics_reg_orig = {
                    "R2": r2_score(y_reg, y_pred_orig),
                    "RMSE": rmse_score(y_reg, y_pred_orig),
                }
            except Exception as e:
                st.warning(f"⚠️ Could not evaluate original regression model: {e}")
                metrics_reg_orig = {"R2": None, "RMSE": None}

            # Retrain the model directly (DataCleaner already handles unseen categories)
            reg_pipeline_retrained = load_model(
                os.path.join(MODELS_DIR, "pipeline_best_regression.pkl")
            )
            reg_pipeline_retrained.fit(X_reg, y_reg)

            retrain_reg_path = os.path.join(
                MODELS_DIR, "pipeline_best_regression_retrained.pkl"
            )
            save_model(reg_pipeline_retrained, retrain_reg_path)

            y_pred_new = reg_pipeline_retrained.predict(X_reg)
            metrics_reg_new = {
                "R2": r2_score(y_reg, y_pred_new),
                "RMSE": rmse_score(y_reg, y_pred_new),
            }

            duration = time.time() - start
            st.success(f"✅ Regression retrained in {duration/60:.2f} min")

            st.subheader("📊 Regression comparison")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Original model**")
                st.write(metrics_reg_orig)
            with col2:
                st.markdown("**Retrained model**")
                st.write(
                    {
                        "R2": f"{metrics_reg_new['R2']:.4f} {diff_icon(metrics_reg_new['R2'], metrics_reg_orig['R2'], True)}",
                        "RMSE": f"{metrics_reg_new['RMSE']:.2f} {diff_icon(metrics_reg_new['RMSE'], metrics_reg_orig['RMSE'], False)}",
                    }
                )

        # Classification
        with st.spinner("Training classification model..."):
            start = time.time()

            clf_pipeline_orig = load_model(
                os.path.join(MODELS_DIR, "pipeline_xgboost_classification.pkl")
            )

            # Import the original label encoder to decode predicted labels for the original model (for comparison purposes)
            label_encoder_original = joblib.load(
                os.path.join(MODELS_DIR, "label_encoder_target.pkl")
            )

            # Create a new label encoder in case the training data does not have the same classes
            label_encoder = LabelEncoder()
            X_clf, y_clf = df[clf_features], df[clf_target]
            y_clf_encoded = label_encoder.fit_transform(y_clf)

            try:
                y_pred_orig_encoded = clf_pipeline_orig.predict(X_clf)

                # Use the original label encoder to decode predictions from the original model.
                y_pred_orig = label_encoder_original.inverse_transform(
                    y_pred_orig_encoded
                )

                metrics_clf_orig = {"Accuracy": accuracy_score(y_clf, y_pred_orig)}
            except Exception as e:
                st.warning(f"⚠️ Could not evaluate original classification model: {e}")
                metrics_clf_orig = {"Accuracy": None}

            clf_pipeline_retrained = load_model(
                os.path.join(MODELS_DIR, "pipeline_xgboost_classification.pkl")
            )

            clf_pipeline_retrained.fit(X_clf, y_clf_encoded)

            retrain_clf_path = os.path.join(
                MODELS_DIR, "pipeline_xgboost_classification_retrained.pkl"
            )
            save_model(clf_pipeline_retrained, retrain_clf_path)

            y_pred_new_encoded = clf_pipeline_retrained.predict(X_clf)

            # Use the new label encoder to decode predictions from the retrained model.
            y_pred_new = label_encoder.inverse_transform(y_pred_new_encoded)
            metrics_clf_new = {"Accuracy": accuracy_score(y_clf, y_pred_new)}

            duration = time.time() - start
            st.success(f"✅ Classification retrained in {duration/60:.2f} min")

            st.subheader("📊 Classification comparison")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Original model**")
                st.write(metrics_clf_orig)
            with col2:
                st.markdown("**Retrained model**")
                st.write(
                    {
                        "Accuracy": f"{metrics_clf_new['Accuracy']:.4f} "
                        f"{diff_icon(metrics_clf_new['Accuracy'], metrics_clf_orig['Accuracy'], True)}"
                    }
                )

    st.success("🎉 All models retrained successfully")
