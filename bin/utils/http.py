# bin/utils/http.py
import time
from typing import Any, Dict, Optional, Tuple

import requests

DEFAULT_TIMEOUT = 60.0


def make_session() -> requests.Session:
    s = requests.Session()
    # Do NOT set a session-wide timeout; enforce per-call.
    return s


def _should_retry(status: int) -> bool:
    return status >= 500 or status == 429


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    json: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = 2,
    backoff_sec: float = 0.5,
) -> Tuple[int, Dict[str, Any]]:
    last_exc = None
    for attempt in range(retries + 1):
        try:
            resp = session.request(
                method=method.upper(),
                url=url,
                json=json,
                params=params,
                headers=headers,
                timeout=timeout,
            )
            if _should_retry(resp.status_code) and attempt < retries:
                time.sleep(backoff_sec * (2**attempt))
                continue
            # Raise for 4xx/5xx to bubble a clean error
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            return resp.status_code, data
        except requests.RequestException as e:
            last_exc = e
            if attempt < retries:
                time.sleep(backoff_sec * (2**attempt))
            else:
                raise
    # Should not reach here
    raise last_exc  # type: ignore
