import joblib
from fastapi import HTTPException

from backend.models.input_model import InputData
from backend.services import BASE_DIR
from backend.services.data_preparation import prepare_data

CLASSIFICATION_MODEL_PATH = (
    BASE_DIR / "MLmodels" / "pipeline_xgboost_classification.pkl"
)
REGRESSION_MODEL_PATH = BASE_DIR / "MLmodels" / "pipeline_best_regression.pkl"
ENCODER_PATH = BASE_DIR / "MLmodels" / "label_encoder_target.pkl"


def predict_cost_dpe(features: InputData) -> dict:
    # ---- Prepare data
    X_input = prepare_data(features)

    # If we couldn't retrive geographical features, return an error.
    if X_input is None:
        raise HTTPException(
            status_code=400,
            detail="❌ Unable to retrieve geographical features for the provided city/INSEE code.",
        )

    need_cost_prediction = X_input["cout_total_5_usages"].isnull().any()
    # Check if the cost is provided or not.
    if need_cost_prediction:
        # If not provided, run the prediction using the regression model.
        # load the regression pipeline
        pipeline_regression_model = joblib.load(REGRESSION_MODEL_PATH)

        X_input_regression = X_input.drop(columns=["cout_total_5_usages"])

        # Make the prediction
        cost_pred = pipeline_regression_model.predict(X_input_regression)

        # Complete the cost in the input data for classification.
        X_input["cout_total_5_usages"] = cost_pred

    # load the pipeline and the model
    pipeline_classification_model = joblib.load(CLASSIFICATION_MODEL_PATH)
    label_encoder = joblib.load(ENCODER_PATH)

    # ---- Prediction
    try:
        y_pred_int = pipeline_classification_model.predict(X_input)
        y_pred_label = label_encoder.inverse_transform(y_pred_int)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Return the values.
    if need_cost_prediction:
        return {
            "predicted_cost_eur": round(
                float(X_input["cout_total_5_usages"].iloc[0]), 2
            ),
            "predicted_dpe_class": y_pred_label[0],
        }
    else:
        return {
            "predicted_dpe_class": y_pred_label[0],
        }
