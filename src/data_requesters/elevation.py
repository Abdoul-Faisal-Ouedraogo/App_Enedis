import time

from src.data_requesters.base_api import BaseAPIRequester


class Elevation_API_requester(BaseAPIRequester):
    """
    A class to interact with the Elevation API to get the altitude from geographical coordinates.
    """

    __base_url = "https://api.elevationapi.com/api/Elevation"

    def get_elevation(self, lat: float, lon: float, delay=0) -> float | None:
        """Get elevation data for given locations. Exemple request: https://api.elevationapi.com/api/Elevation?lat=12&lon=32

        Args:
            lat (float): The latitude of the location.
            lon (float): The longitude of the location.

        Returns:
            float | None: The elevation data or None if an error occurred.
        """

        if not lat or not lon:
            return None

        # Prepare the paramaters
        params = {"lat": lat, "lon": lon}

        if delay:
            time.sleep(delay)

        data = self._get_data(self.__base_url, params=params)
        print("data recuperated")

        if not data or data["resultCount"] == 0:
            return None
        else:
            return data["geoPoints"][0]["elevation"]
