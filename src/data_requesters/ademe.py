from typing import Any, Callable, Optional

import requests

# from data_requesters.helper import retry_on_error
from .helper import retry_on_error
from src.data_requesters.base_api import BaseAPIRequester


class Ademe_API_requester(BaseAPIRequester):
    """
    A class to interact with the ADEME API.
    """

    # Class attributes: base URLs for different datasets
    __base_url_existant = (
        "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant"
    )

    __base_url_neuf = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe02neuf"

    def __init__(
        self,
        size: int = 2500,
    ) -> None:
        """Initializes the Ademe_API_requester class.

        Args:
            size (int, optional): The number of results to return per page. Defaults to 2500.
            max_retries (int, optional): The maximum number of retry attempts for API requests. Defaults to 3.
            backoff_factor (int, optional): The backoff factor for retry delays. Defaults to 2.
        """
        self.__size: int = size

    def bounded_lines_by_date(self, department, start, end, limit=500, neuf=False,
                              progress=None, session=None, sleep=None):
        """Collecte explicite bornée ; échec complet si pagination ou transport incohérent."""
        import datetime
        import re
        import time
        from urllib.parse import urlparse, urljoin
        if not re.fullmatch(r"(?:\d{2,3}|2A|2B)", department):
            raise ValueError("Département invalide")
        first, last = datetime.date.fromisoformat(str(start)), datetime.date.fromisoformat(str(end))
        if first > last or not 1 <= limit <= 5000:
            raise ValueError("Période ou volume invalide (1 à 5 000)")
        client, pause = session or requests.Session(), sleep or time.sleep
        base = self.__base_url_neuf if neuf else self.__base_url_existant
        url = base + "/lines"
        params = {"size": min(self.__size, limit, 500), "sort": "date_reception_dpe,numero_dpe",
                  "qs": f'code_departement_ban:"{department}" AND date_reception_dpe:[{first} TO {last}]'}
        rows, visited = [], set()
        while url and len(rows) < limit:
            if not isinstance(url,str):
                raise ValueError("Lien de pagination invalide")
            url = urljoin(base + "/lines",url)
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.netloc != "data.ademe.fr" or parsed.path != urlparse(base + "/lines").path:
                raise ValueError("Lien de pagination ADEME non autorisé")
            if url in visited:
                raise ValueError("Boucle de pagination ADEME")
            visited.add(url)
            payload = None
            for attempt in range(3):
                try:
                    response = client.get(url, params=params, timeout=(5, 30), allow_redirects=False)
                    if response.status_code == 429 or response.status_code >= 500:
                        raise requests.RequestException("Service temporairement indisponible")
                    if 300 <= response.status_code < 400:
                        raise ValueError("API déplacée : vérifier le contrat ADEME avant de collecter")
                    response.raise_for_status()
                    payload = response.json()
                    break
                except requests.RequestException as exc:
                    if attempt == 2:
                        raise ValueError("Échec ADEME après trois tentatives ; aucune version activée") from exc
                    pause(2 ** attempt)
            if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                raise ValueError("Réponse ADEME invalide")
            page = payload["results"][:limit - len(rows)]
            if not page and payload.get("next"):
                raise ValueError("Pagination vide incohérente")
            for row in page:
                if not isinstance(row, dict):
                    raise ValueError("Ligne ADEME invalide")
                try:
                    date = datetime.date.fromisoformat(str(row["date_reception_dpe"])[:10])
                    dep = str(row["code_departement_ban"]).zfill(2)
                    if not first <= date <= last or dep != department:
                        raise ValueError("Le serveur n'a pas respecté les filtres")
                except (KeyError, TypeError) as exc:
                    raise ValueError("Schéma ADEME incompatible") from exc
            rows.extend(page)
            if progress:
                progress(len(rows), limit)
            url, params = payload.get("next"), None
            if url and len(rows) < limit:
                pause(.25)
        return rows

    def __get_length(self, url: str, params: dict[str, Any] | None = None) -> int:
        """Private method to get the total number of results from the API for monitoring progress.

        Args:
            url (str): The base URL for the API request.
            params (dict[str, Any] | None, optional): The parameters for the API request. Defaults to None.
        """

        # Change the size of the parameter to 1 to speed up the request for total length.
        params = params | {"size": 1} if params else {"size": 1}

        data = self._get_data(url, params=params)
        length = data.get("total", 0) if data else 0
        return length

    def custom_lines_request(
        self,
        neuf: bool = False,
        limit: int | None = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        **kwargs,
    ) -> list[dict[str, Any]]:
        """Make a custom request to the lines endpoint with additional parameters, while handling the looping requests for pagination.

        Args:
            neuf (bool, optional): Whether to request for new houses. Defaults to False.
            limit (int | None, optional): The number of results we want to limit the request to. Defaults to None.
            progress_callback (Optional[Callable[[int, int], None]], optional): A callback function to report progress. Defaults to None.
            **kwargs: Additional parameters to include in the request.

        Returns:
            dict: The response from the API.
        """
        # Initialize the URL to the base URL depending of if we want new or existing buildings.
        url = self.__base_url_existant if not neuf else self.__base_url_neuf
        url += "/lines"  # Endpoint for lines data.

        # Setting the parameters for the request.
        params = {"size": self.__size} | kwargs

        # Initialize the all_data list to get all the data from the pagination loop.
        all_data: list[dict[str, Any]] = []

        total_length = self.__get_length(url, params=params)
        if limit is not None and limit < total_length:
            total_length = limit

        if progress_callback:
            progress_callback(0, total_length)

        if total_length == 0:
            print("No data found for the specified department.")
            return all_data

        print(f"Total records to fetch: {total_length}")

        # Pagination loop.
        while url:
            data = self._get_data(url, params=params)
            if not data:
                print("No data could have been fetched, stopping pagination.")
                break

            results = data["results"]

            # Trim results if we would exceed the limit
            if limit is not None:
                remaining = limit - len(all_data)
                if remaining <= 0:
                    break
                results = results[:remaining]

            all_data.extend(results)

            if progress_callback:
                progress_callback(len(all_data), total_length)

            print(
                f"Fetched {len(results)} records. Total so far: {len(all_data)}/{total_length} ({round(len(all_data) / total_length * 100, 2)}%)"
            )

            # Break if we've reached the limit
            if limit is not None and len(all_data) >= limit:
                break

            url = data.get("next")  # Get the next page URL.
            params = None  # Clear params for subsequent requests.
        # endwhile

        return all_data

    def get_bydepartement(
        self, departement: int, neuf: bool = False
    ) -> list[dict[str, Any]]:
        """Retrieve building data by department.

        Args:
            departement (int): The department code to filter by.
            neuf (bool, optional): Whether to filter for new buildings. Defaults to False.

        Returns:
            list[dict[str, Any]]: A list of dictionaries containing the building data.
        """
        # loggigng
        print(
            f"-- Fetching {'new' if neuf else 'existing'} building data for department: {departement} --"
        )

        # Build the parameter dictionary from the new department argument.
        params = {"size": self.__size} | {"qs": f"code_departement_ban:{departement}"}

        # Initialize the all_data list to get all the data from the pagination loop.
        all_data: list[dict[str, Any]] = []

        # Initialize the URL to the base URL depending of if we want new or existing buildings.
        url = self.__base_url_existant if not neuf else self.__base_url_neuf
        url += "/lines"  # Endpoint for lines data.

        total_length = self.__get_length(url, params=params)

        if total_length == 0:
            print("No data found for the specified department.")
            return all_data

        print(f"Total records to fetch for department: {total_length}")

        # Pagination loop.
        while url:
            data = self._get_data(url, params=params)
            all_data.extend(data["results"])
            print(
                f"Fetched {len(data['results'])} records. Total so far: {len(all_data)}/{total_length} ({round(len(all_data) / total_length * 100, 2)}%)"
            )
            url = data.get("next")  # Get the next page URL.
            params = None  # Clear params for subsequent requests.
        # endwhile

        return all_data

    def get_all_departments_count(self, neuf: bool = False) -> list:
        """Fetch the aggregated count of all departments.

        Args:
            neuf (bool, optional): Whether to request for new houses. Defaults to False.

        Returns:
            list: A list containing the count for each department.
        """
        # Initialize the URL to the base URL depending of if we want new or existing buildings.
        url = self.__base_url_existant if not neuf else self.__base_url_neuf
        url += "/values_agg"  # Endpoint for values aggregation.

        data = self._get_data(
            url, params={"agg_size": 400, "field": "code_departement_ban"}
        )

        return data.get("aggs", []) if data else []

    def get_all_data(self, neuf: bool = False) -> list[dict[str, Any]]:
        """Fetch the complete database of existing or new buildings.

        Args:
            neuf (bool, optional): Whether to filter for new buildings. Defaults to False.

        Returns:
            list[dict[str, Any]]: A list of dictionaries containing the building data.
        """
        # loggigng
        print(
            f"-- Fetching {'new' if neuf else 'existing'} building data for all departments --"
        )

        # Initialize the all_data list to get all the data from the pagination loop.
        all_data: list[dict[str, Any]] = []

        # Initialize the URL to the base URL depending of if we want new or existing buildings.
        url = self.__base_url_existant if not neuf else self.__base_url_neuf
        url += "/lines"  # Endpoint for lines data.

        # Default size parameter.
        params = {"size": self.__size}

        total_length = self.__get_length(url, params=params)

        if total_length == 0:
            print("No data found.")
            return all_data

        print(f"Total records to fetch: {total_length}")

        # Pagination loop.
        while url:
            data = self._get_data(url, params=params)
            all_data.extend(data["results"])
            print(
                f"Fetched {len(data['results'])} records. Total so far: {len(all_data)}/{total_length} ({round(len(all_data) / total_length * 100, 2)}%)"
            )
            url = data.get("next")  # Get the next page URL.
            params = None  # Clear params for subsequent requests.
        # endwhile
        return all_data

    @retry_on_error()
    def get_dataset_fields(self, neuf: bool = False) -> list[dict[str, Any]]:
        """Get the list of available fields (variables) from the ADEME API dataset.

        Args:
            neuf (bool, optional): Whether to get fields for new buildings. Defaults to False (existing buildings).

        Returns:
            list[dict[str, Any]]: A list of dictionaries containing field information.
                Each dictionary contains:
                - key: Field key/name
                - label: Field label (human-readable name)
                - type: Data type (string, integer, number, date, etc.)
                - description: Field description (if available)
                - x-group: Group category (if available)

        Example:
            >>> requester = Ademe_API_requester()
            >>> fields = requester.get_dataset_fields(neuf=False)
            >>> for field in fields:
            ...     print(f"{field['key']}: {field['label']} ({field['type']})")
        """
        # Get the appropriate base URL
        url = self.__base_url_neuf if neuf else self.__base_url_existant

        response = requests.get(url)
        response.raise_for_status()
        dataset_info = response.json()

        schema = dataset_info.get("schema", [])

        return [
            {
                "key": field.get("key"),
                "label": field.get("label") or field.get("title") or field.get("key"),
                "type": field.get("type"),
                "description": field.get("description") or "",
                "x-group": field.get("x-group") or "Non classé",
            }
            for field in schema
        ]

    def get_field_names(self, neuf: bool = False) -> list[str]:
        """Get only the names (keys) of available fields.

        Args:
            neuf (bool, optional): Whether to get fields for new buildings. Defaults to False.

        Returns:
            list[str]: A list of field keys.

        Example:
            >>> requester = Ademe_API_requester()
            >>> field_names = requester.get_field_names(neuf=False)
            >>> print(field_names)
            ['numero_dpe', 'code_postal_ban', 'commune_ban', ...]
        """
        fields = self.get_dataset_fields(neuf=neuf)
        return [field["key"] for field in fields]

    def get_fields_by_group(
        self, neuf: bool = False
    ) -> dict[str, list[dict[str, Any]]]:
        """Get fields organized by their group category.

        Args:
            neuf (bool, optional): Whether to get fields for new buildings. Defaults to False.

        Returns:
            dict[str, list[dict[str, Any]]]: A dictionary with groups as keys and lists of fields as values.

        Example:
            >>> requester = Ademe_API_requester()
            >>> groups = requester.get_fields_by_group(neuf=False)
            >>> for group, fields in groups.items():
            ...     print(f"{group}: {len(fields)} fields")
        """
        fields = self.get_dataset_fields(neuf=neuf)
        groups: dict[str, list[dict[str, Any]]] = {}

        for field in fields:
            group = field.get("x-group", "Non classé")
            if group not in groups:
                groups[group] = []
            groups[group].append(field)

        return groups

    def print_available_fields(self, neuf: bool = False) -> None:
        """Print all available fields in a readable format, organized by group.

        Args:
            neuf (bool, optional): Whether to print fields for new buildings. Defaults to False.

        Example:
            >>> requester = Ademe_API_requester()
            >>> requester.print_available_fields(neuf=False)
        """
        fields_by_group = self.get_fields_by_group(neuf=neuf)
        dataset_type = "Logements neufs" if neuf else "Logements existants"

        print(f"\n{'='*80}")
        print(f"Available fields in ADEME API - {dataset_type}")
        print(
            f"Total: {sum(len(fields) for fields in fields_by_group.values())} fields"
        )
        print(f"{'='*80}\n")

        for group, fields in sorted(fields_by_group.items()):
            print(f"\n{'─'*80}")
            print(f"📁 Groupe: {group} ({len(fields)} champs)")
            print(f"{'─'*80}")

            for i, field in enumerate(fields, 1):
                print(f"{i}. {field['key']}")
                print(f"   Label: {field['label']}")
                print(f"   Type: {field['type']}")
                if field["description"]:
                    print(f"   Description: {field['description']}")
                print()
