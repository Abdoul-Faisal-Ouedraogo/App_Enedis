from typing import Any, Optional

import requests

from src.data_requesters.helper import retry_on_error


class BaseAPIRequester:
    """Base class providing a common method to safely fetch JSON data from APIs."""

    @staticmethod
    @retry_on_error()
    def _get_data(url: str, params: Optional[dict[str, Any]] = None) -> Optional[dict]:
        """Generic method to get data from an API endpoint.

        Args:
            url (str): The API URL to request.
            params (dict[str, Any] | None, optional): Query parameters for the request.

        Returns:
            dict | None: Parsed JSON data, or None if an error or 404 occurred.
        """
        try:
            response = requests.get(url, params=params)
            if response.status_code == 404:
                return None

            response.raise_for_status()
            try:
                return response.json()
            except ValueError:
                # Response was not JSON
                return None
        except requests.RequestException:
            return None
