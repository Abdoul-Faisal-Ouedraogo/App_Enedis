import pandas as pd

from backend.models.input_model import InputData
from src.data_requesters import geo_api
from src.data_requesters.elevation import Elevation_API_requester


def prepare_data(input_data: InputData) -> pd.DataFrame | None:
    """Function to prepare data from the user input in order to feed the ML model.

    Args:
        input_data (InputData): The data from the user.

    Returns:
        pd.DataFrame: The prepared input data for the ML model.
    """
    # Get the geographical features
    geo_info = geo_api.get_city_info(ville=input_data.city)

    if not geo_info:
        return None

    zone_clim = geo_info.get("zone_climatique")
    lat, lon = geo_info.get("lat"), geo_info.get("lon")

    if lat is None or lon is None:
        altitude_moyenne = 0

    else:
        # ---- Step 2: Retrieve elevation
        elev_requester = Elevation_API_requester()
        altitude_moyenne = elev_requester.get_elevation(lat, lon) or 0

    # ---- Prepare input dataframe
    user_input = {
        "cout_total_5_usages": input_data.cost,
        "surface_habitable_logement": input_data.area,
        "nombre_niveau_logement": input_data.n_floors,
        "age_batiment": input_data.age,
        "altitude_moyenne": altitude_moyenne,
        "type_energie_principale_chauffage": input_data.main_heating_energy,
        "type_batiment": input_data.building,
        "zone_climatique": zone_clim,
    }

    X_input = pd.DataFrame([user_input])

    return X_input
