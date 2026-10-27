from typing import Any

import requests

# from data_requesters.helper import retry_on_error
from .helper import retry_on_error
from src.data_requesters.base_api import BaseAPIRequester


class Enedis_API_requester(BaseAPIRequester):
    """
    A class to interact with the Enedis API.
    """

    __base_url = "https://data.enedis.fr/api/explore/v2.1/catalog/datasets/consommation-annuelle-residentielle-par-adresse/records"
    __dataset_url = "https://data.enedis.fr/api/explore/v2.1/catalog/datasets/consommation-annuelle-residentielle-par-adresse"

    def __init__(self, limit: int = 100) -> None:
        """Initializes the Enedis_API_requester class.

        Args:
            limit (int, optional): The number of results to return per page. Defaults to 100.
        """
        self.__params: dict[str, int] = {"limit": limit}
        self.__all_iris_codes: list[str] = []

    def __get_length(self, params: dict[str, Any] | None = None) -> int:
        """Private method to get the total number of results from the API for monitoring progress.

        Args:
            params (dict[str, Any] | None, optional): The parameters for the API request. Defaults to None.
        """

        # Change the limit of the parameter to 1 to speed up the request for total length.
        params = params | {"limit": 0} if params else {"limit": 0}

        response = requests.get(self.__base_url, params=params)
        response.raise_for_status()  # Raise an error for bad responses.
        length = response.json().get("total_count", 0)
        return length

    @retry_on_error()
    def get_dataset_fields(self) -> list[dict[str, Any]]:
        """Get the list of available fields (variables) from the Enedis API dataset.

        Returns:
            list[dict[str, Any]]: A list of dictionaries containing field information.
                Each dictionary contains:
                - name: Field name
                - label: Field label (human-readable name)
                - type: Data type (text, int, double, date, geo_point_2d, etc.)
                - description: Field description (if available)

        Example:
            >>> requester = Enedis_API_requester()
            >>> fields = requester.get_dataset_fields()
            >>> for field in fields:
            ...     print(f"{field['name']}: {field['label']} ({field['type']})")
        """
        response = requests.get(self.__dataset_url)
        response.raise_for_status()
        dataset_info = response.json()

        fields = dataset_info.get("fields", [])

        return [
            {
                "name": field.get("name"),
                "label": field.get("label"),
                "type": field.get("type"),
                "description": field.get("description") or "",
            }
            for field in fields
        ]

    def get_field_names(self) -> list[str]:
        """Get only the names of available fields.

        Returns:
            list[str]: A list of field names.

        Example:
            >>> requester = Enedis_API_requester()
            >>> field_names = requester.get_field_names()
            >>> print(field_names)
            ['annee', 'code_iris', 'nom_iris', 'type_iris', ...]
        """
        fields = self.get_dataset_fields()
        return [field["name"] for field in fields]

    def print_available_fields(self) -> None:
        """Print all available fields in a readable format.

        Example:
            >>> requester = Enedis_API_requester()
            >>> requester.print_available_fields()
        """
        fields = self.get_dataset_fields()
        print(f"\n{'='*80}")
        print(f"Available fields in Enedis API ({len(fields)} total)")
        print(f"{'='*80}\n")

        for i, field in enumerate(fields, 1):
            print(f"{i}. {field['name']}")
            print(f"   Label: {field['label']}")
            print(f"   Type: {field['type']}")
            if field["description"]:
                print(f"   Description: {field['description']}")
            print()
