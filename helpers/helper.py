import logging
import time
from functools import wraps

import requests

logger = logging.getLogger(__name__)


def retry_on_error(max_retries: int = 3, backoff_factor: float = 2):
    """Réessaie une requête en cas d'erreur réseau ou de réponse temporaire.

    max_retries correspond au nombre total de tentatives.
    Les erreurs HTTP 4xx, sauf 429, ne sont pas réessayées.
    """
    if max_retries < 1:
        raise ValueError("max_retries doit être supérieur ou égal à 1.")

    if backoff_factor < 0:
        raise ValueError("backoff_factor ne peut pas être négatif.")

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as error:
                    response = getattr(error, "response", None)
                    status_code = response.status_code if response is not None else None

                    # Réessayer les erreurs réseau, les erreurs serveur et les 429.
                    retryable = (
                        status_code is None
                        or status_code == 429
                        or status_code >= 500
                    )

                    if not retryable or attempt == max_retries - 1:
                        raise

                    wait_time = backoff_factor**attempt
                    logger.warning(
                        "%s a échoué (%s). Nouvelle tentative dans %.1f s.",
                        func.__name__,
                        error,
                        wait_time,
                    )
                    time.sleep(wait_time)

        return wrapper

    return decorator