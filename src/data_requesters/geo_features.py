from pathlib import Path
from typing import Any

import pandas as pd

from src.data_requesters.base_api import BaseAPIRequester

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CLIMATE_ZONES_PATH = BASE_DIR / "data" / "climate_zones.csv"


class Geo_API_requester(BaseAPIRequester):
    """
    A class to interact with the Geo API from datagouv to get geographical features from cities names or INSEE codes.
    """

    __url_cities = "https://data.geopf.fr/geocodage/search/"
    __url_insee = "https://geo.api.gouv.fr/communes/"

    def __init__(self) -> None:
        """Initializes the Geo_API_requester class with the dictionnaries to map department numbers to climate zones."""
        # Read the file for mapping.
        df_zones = pd.read_csv(CLIMATE_ZONES_PATH, dtype={"Departement": str})

        # Create a dict: department -> zone
        self.climate_zones = pd.Series(
            df_zones["Zone climatique"].values, index=df_zones["Departement"]
        ).to_dict()

    def __extract_department_from_feature(self, props: dict) -> str | None:
        """
        Try robustly to extract the department code from the geo feature properties returned
        by api-adresse.data.gouv.fr. Returns a string dept code (e.g. '13' or '2A') or None.
        """
        # 1) try 'context' first: often "13, Bouches-du-Rhône, Provence..."
        context = props.get("context") or ""
        if context:
            first = context.split(",")[0].strip()
            # often a numeric dept code
            if first.isdigit():
                return first.zfill(2)
            # sometimes context might include '2A'/'2B' or other forms: keep as-is
            if first.upper() in {"2A", "2B"}:
                return first.upper()

        # 2) try postcode (first 2 characters usually department for metropolitan FR)
        postcode = props.get("postcode")
        if postcode:
            # handle special overseas codes beginning with 97/98 -> these are 3-digit dept codes sometimes
            if postcode.startswith(("97", "98")):
                return postcode[:3]
            return postcode[:2]

        # 3) try citycode (INSEE) -> first two digits normally department number,
        # but for Corsica INSEE uses 2A/2B in a different field; citycode is numeric string
        citycode = props.get("citycode")
        if citycode and citycode.isdigit():
            return citycode[:2]

        return None

    def get_city_info(self, ville: str) -> dict[str, Any] | None:
        """
        Return {'zone_climatique': 'H1'|'H2'|'H3'|'Unknown', 'altitude_moyenne': float|None, 'dept': str|None, 'lat': float|None, 'lon': float|None}
        Uses api-adresse.data.gouv.fr to find department and coordinates.
        """

        # Initialize the dictionnary result.
        result = {
            "city": None,
            "zone_climatique": str,
            "altitude_moyenne": None,
            "dept": None,
            "lon": None,
            "lat": None,
        }

        # If 'ville' looks like an INSEE code, extract dept directly and call the insee route.
        if len(ville) == 5 and ville[2:].isdigit():
            # first two chars of INSEE usually department number (handles '2A'/'2B' if present)
            dept_from_insee = ville[:2]
            result["dept"] = dept_from_insee

            # Get the data from the API.
            data = self._get_data(f"{self.__url_insee}{ville}")

            # Get the city name.
            if data:
                result["_citycode"] = ville
                ville = data["nom"]
                result["city"] = ville
            else:
                # Return None if the INSEE code is invalid.
                return None

        # When we have the city name, call the city search endpoint, update the result dictionnary.

        # Build the parameters
        params = {"q": ville, "limit": 1}

        data = self._get_data(self.__url_cities, params=params)

        if data:
            features = data.get("features", [])

            # If we couldn't find any feature, return None (invalid city name).
            if not features:
                return None

            else:
                # get the lon et lat
                features = features[0]
                props = features.get("properties", {})
                geom = features.get("geometry", {})
                coords = geom.get("coordinates", [None, None])
                result["lon"], result["lat"] = coords[0], coords[1]

                result["dept"] = self.__extract_department_from_feature(props)

                # Debug info: keep the raw context if you need to log later
                result["_context"] = props.get("context")
                result["_postcode"] = props.get("postcode")
                result["_citycode"] = props.get("citycode")
                result["city"] = props.get("city")

        # Return None if we couldn't extract a department code.
        if result.get("dept") is None:
            return None

        if result.get("dept") in {"2A", "2B"}:
            # Corsica: map '2A' -> 20? (depends on your CLIMATE_ZONES mapping expectations)
            result["dept"] = "20"

        result["zone_climatique"] = self.climate_zones.get(
            result["dept"], "H1"
        )  # Use the most common zone as default

        return result
