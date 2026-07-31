"""Thin HTTP client for the ServiceNow Table API — shared by tools/balances.py
and tools/requests.py so both talk to the instance the same way (auth,
error handling) instead of duplicating that logic in each file.
"""

from __future__ import annotations

import requests

from app import config


class ServiceNowError(Exception):
    """Raised on any Table API failure — network error, timeout, or a
    non-2xx response. Callers should catch this and explain the failure
    rather than letting it fail silently (real latency, real errors — see
    coursework.md Part 3).
    """


def _auth():
    return (config.SERVICENOW_USERNAME, config.SERVICENOW_PASSWORD)


def _request(method: str, table: str, sys_id: str = "", **kwargs) -> dict | list:
    path = f"{table}/{sys_id}" if sys_id else table
    url = f"{config.SERVICENOW_INSTANCE_URL}/api/now/table/{path}"
    try:
        resp = requests.request(
            method,
            url,
            auth=_auth(),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=10,
            **kwargs,
        )
    except requests.exceptions.RequestException as e:
        raise ServiceNowError(f"Could not reach ServiceNow: {e}") from e

    if not resp.ok:
        raise ServiceNowError(f"ServiceNow returned {resp.status_code}: {resp.text[:300]}")

    if resp.status_code == 204:  # DELETE has no body
        return {}
    return resp.json().get("result", {})


def query(table: str, sysparm_query: str = "", limit: int = 100) -> list[dict]:
    result = _request("GET", table, params={"sysparm_query": sysparm_query, "sysparm_limit": limit})
    return result if isinstance(result, list) else [result]


def create(table: str, fields: dict) -> dict:
    return _request("POST", table, json=fields)


def update(table: str, sys_id: str, fields: dict) -> dict:
    return _request("PATCH", table, sys_id=sys_id, json=fields)
