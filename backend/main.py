from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.models.input_model import InputData
from backend.services.prediction import predict_cost_dpe

app = FastAPI(
    title="DEP and consumption prediction API",
    description="API for predicting DPE class and energy consumption based on building features. Developped for M2 SISE 2025 project.",
)

# Autoriser les appels depuis Streamlit
app.add_middleware(
    # Protecting CORS issues, allowing front-end to communicate with back-end.
    CORSMiddleware,
    allow_origins=["*"],  # Front end URL(s) can be specified here
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post(
    "/predict",
    summary="Predict DPE class and energy consumption",
    description="Predict DPE class and energy consumption based on building features.",
)
def predict_route(data: InputData):
    result = predict_cost_dpe(features=data)
    return result
