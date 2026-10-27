import time
from functools import wraps


def retry_on_error(max_retries=3, backoff_factor=2):
    """Decorator/factory to retry an API requester function on exceptions with exponential backoff.

    Args:
        max_retries (int, optional): Maximum number of retry attempts. Defaults to 3.
        backoff_factor (int, optional): Factor by which to increase wait time between retries. Defaults to 2.
    """

    def decorator(func):
        @wraps(func)  # Import metadata from the original function.
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    print(f"Error: {e}")
                    if attempt == max_retries - 1:
                        raise  # Re-raise the exception if max retries reached.

                    # Exponential backoff
                    wait_time = backoff_factor**attempt
                    print(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)

        return wrapper

    return decorator
