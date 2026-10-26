import json
import logging
import time
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote

import requests

from helpers.helper import retry_on_error

logger = logging.getLogger(__name__)


class _BaseAPIRequester:
    """Fonctions communes aux clients API."""

    def __init__(self, timeout: tuple[float, float] = (5, 30)) -> None:
        self._session = requests.Session()
        self._timeout = timeout

    @retry_on_error(max_retries=3, backoff_factor=2)
    def _get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self._session.get(
            url,
            params=params,
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        """Ferme la session HTTP."""
        self._session.close()


class Ademe_API_requester(_BaseAPIRequester):
    """Client pour les jeux de données ADEME logements existants et neufs."""

    _BASE_URL_EXISTANT = (
        "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant"
    )
    _BASE_URL_NEUF = (
        "https://data.ademe.fr/data-fair/api/v1/datasets/dpe02neuf"
    )

    def __init__(
        self,
        size: int = 2500,
        timeout: tuple[float, float] = (5, 30),
    ) -> None:
        super().__init__(timeout=timeout)

        if size < 1:
            raise ValueError("size doit être supérieur ou égal à 1.")

        self._size = size

    def _base_url(self, neuf: bool) -> str:
        return self._BASE_URL_NEUF if neuf else self._BASE_URL_EXISTANT

    def _get_length(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> int:
        count_params = dict(params or {})
        count_params["size"] = 1

        data = self._get_json(url, params=count_params)
        return int(data.get("total", 0))

    def _iter_lines(
        self,
        neuf: bool = False,
        limit: int | None = None,
        **filters: Any,
    ) -> Iterator[dict[str, Any]]:
        if limit is not None and limit < 0:
            raise ValueError("limit ne peut pas être négatif.")

        if limit == 0:
            return

        url = f"{self._base_url(neuf)}/lines"
        params = {"size": self._size, **filters}
        total = self._get_length(url, params=params)

        if limit is not None:
            total = min(total, limit)

        if total == 0:
            logger.info("Aucune donnée ADEME trouvée.")
            return

        fetched = 0

        while url and fetched < total:
            data = self._get_json(url, params=params)
            results = data.get("results", [])

            if not results:
                break

            remaining = total - fetched
            results = results[:remaining]

            for record in results:
                yield record

            fetched += len(results)
            logger.info("ADEME : %s/%s lignes récupérées.", fetched, total)

            url = data.get("next")
            params = None

    def custom_lines_request(
        self,
        neuf: bool = False,
        limit: int | None = None,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        """Récupère les lignes ADEME et les retourne dans une liste."""
        return list(self._iter_lines(neuf=neuf, limit=limit, **filters))

    def save_lines_jsonl(
        self,
        path: str | Path,
        neuf: bool = False,
        limit: int | None = None,
        mode: str = "w",
        **filters: Any,
    ) -> int:
        """Écrit les lignes ADEME progressivement dans un fichier JSONL.

        Utilisez mode="w" pour commencer un fichier et mode="a" pour
        ajouter des données à un fichier existant.
        """
        if mode not in {"w", "a"}:
            raise ValueError("mode doit être 'w' ou 'a'.")

        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        saved = 0
        with output_path.open(mode, encoding="utf-8") as output_file:
            for record in self._iter_lines(
                neuf=neuf,
                limit=limit,
                **filters,
            ):
                output_file.write(
                    json.dumps(record, ensure_ascii=False) + "\n"
                )
                saved += 1

        logger.info("%s lignes enregistrées dans %s.", saved, output_path)
        return saved

    def get_bydepartement(
        self,
        departement: int | str,
        neuf: bool = False,
    ) -> list[dict[str, Any]]:
        """Récupère toutes les lignes ADEME d'un département."""
        return self.custom_lines_request(
            neuf=neuf,
            qs=f"code_departement_ban:{departement}",
        )

    def get_all_data(
        self,
        neuf: bool = False,
    ) -> list[dict[str, Any]]:
        """Récupère toutes les lignes ADEME du jeu de données choisi."""
        return self.custom_lines_request(neuf=neuf)

    def custom_agg_request(
        self,
        neuf: bool = False,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        """Récupère les résultats d'une agrégation ADEME."""
        url = f"{self._base_url(neuf)}/values_agg"
        params = {"agg_size": 1000, **filters}
        data = self._get_json(url, params=params)
        return data.get("aggs", [])

    def get_all_departments_count(
        self,
        neuf: bool = False,
    ) -> list[dict[str, Any]]:
        """Récupère les agrégations par département."""
        return self.custom_agg_request(
            neuf=neuf,
            agg_size=400,
            field="code_departement_ban",
        )

    def get_unique_values(
        self,
        field: str,
        neuf: bool = False,
        **filters: Any,
    ) -> Any:
        """Récupère les valeurs disponibles pour un champ ADEME."""
        encoded_field = quote(field, safe="")
        url = f"{self._base_url(neuf)}/values/{encoded_field}/"
        return self._get_json(url, params=filters)


class Enedis_API_requester(_BaseAPIRequester):
    """Client pour l'API Enedis de consommation annuelle résidentielle."""

    _BASE_URL = (
        "https://data.enedis.fr/api/explore/v2.1/catalog/datasets/"
        "consommation-annuelle-residentielle-par-adresse/records"
    )

    def __init__(
        self,
        limit: int = 100,
        timeout: tuple[float, float] = (5, 30),
    ) -> None:
        super().__init__(timeout=timeout)

        if limit < 1:
            raise ValueError("limit doit être supérieur ou égal à 1.")

        self._limit = limit

    def _get_length(self, where: str | None = None) -> int:
        params: dict[str, Any] = {"limit": 0}
        if where:
            params["where"] = where

        data = self._get_json(self._BASE_URL, params=params)
        return int(data.get("total_count", 0))

    def get_all_data(
        self,
        where: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Récupère les enregistrements Enedis par pages."""
        if limit is not None and limit < 0:
            raise ValueError("limit ne peut pas être négatif.")

        if limit == 0:
            return []

        total = self._get_length(where=where)
        if limit is not None:
            total = min(total, limit)

        records: list[dict[str, Any]] = []
        offset = 0

        while offset < total:
            page_size = min(self._limit, total - offset)
            params: dict[str, Any] = {
                "limit": page_size,
                "offset": offset,
            }
            if where:
                params["where"] = where

            data = self._get_json(self._BASE_URL, params=params)
            page = data.get("results", [])

            if not page:
                break

            records.extend(page)
            offset += len(page)
            logger.info("Enedis : %s/%s lignes récupérées.", offset, total)

        return records


class Elevation_API_requester(_BaseAPIRequester):
    """Client pour l'API d'altitude."""

    _BASE_URL = "https://api.elevationapi.com/api/Elevation"

    def get_elevation(
        self,
        lat: float,
        lon: float,
        delay: float = 0,
    ) -> float | None:
        """Retourne l'altitude pour des coordonnées géographiques."""
        if lat is None or lon is None:
            return None

        if not -90 <= lat <= 90:
            raise ValueError("lat doit être comprise entre -90 et 90.")

        if not -180 <= lon <= 180:
            raise ValueError("lon doit être comprise entre -180 et 180.")

        if delay < 0:
            raise ValueError("delay ne peut pas être négatif.")

        if delay:
            time.sleep(delay)

        data = self._get_json(
            self._BASE_URL,
            params={"lat": lat, "lon": lon},
        )

        if data.get("resultCount", 0) == 0:
            return None

        geo_points = data.get("geoPoints", [])
        if not geo_points:
            return None

        return geo_points[0].get("elevation")