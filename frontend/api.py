import os
import re
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
API_URL = (
    os.getenv("GITINSIGHT_API_URL")
    or dotenv_values(ROOT / ".env").get("GITINSIGHT_API_URL")
    or "http://127.0.0.1:8000"
)


def valid_username(name: str) -> bool:
    return len(name) <= 39 and re.fullmatch(r"[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*", name) is not None


class APIError(Exception):
    pass


def fetch(path: str, *, body: dict | None = None, **params: str) -> dict:
    try:
        response = httpx.request(
            "POST" if body is not None else "GET",
            f"{API_URL.rstrip('/')}/api/v1/{path}",
            params=params,
            json=body,
            timeout=180,
        )
        if response.is_error:
            error = response.json()
            message = error.get("detail") if isinstance(error, dict) else None
            if not isinstance(message, str):
                message = "Check the username and try again."
            retry = response.headers.get("retry-after")
            raise APIError(f"{message} Try again in {retry} seconds." if retry else message)
        return response.json()
    except (httpx.RequestError, ValueError):
        raise APIError(
            "The analytics service is unavailable. Check the backend connection and retry."
        ) from None
