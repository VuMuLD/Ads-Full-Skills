"""
Meta (Facebook/Instagram) Marketing API client for ads-optimizer.
Credentials from .env: META_ACCESS_TOKEN, META_AD_ACCOUNT_ID.
Currency-aware: budgets are converted to the account's minor units
(whole units for VND/JPY/... , cents for USD/EUR/...).
"""

import sys

from common import env_str, is_placeholder, ZERO_DECIMAL_CURRENCIES

API_VERSION = "v22.0"


def _requests():
    """Lazy import so config checks work before `pip install -r requirements.txt`."""
    try:
        import requests
        return requests
    except ImportError:
        print("ERROR: the requests package is not installed.")
        print("Run: py -m pip install -r requirements.txt")
        sys.exit(2)

_account_cache = {}


def missing_config() -> list:
    missing = []
    if is_placeholder(env_str("META_ACCESS_TOKEN")):
        missing.append("META_ACCESS_TOKEN")
    if is_placeholder(env_str("META_AD_ACCOUNT_ID")):
        missing.append("META_AD_ACCOUNT_ID")
    return missing


def get_account_id() -> str:
    account = env_str("META_AD_ACCOUNT_ID")
    if not account:
        print("ERROR: META_AD_ACCOUNT_ID is not set in .env")
        print("See references/setup-connection.md for the one-time setup.")
        sys.exit(2)
    return account if account.startswith("act_") else f"act_{account}"


def _token() -> str:
    token = env_str("META_ACCESS_TOKEN")
    if not token:
        print("ERROR: META_ACCESS_TOKEN is not set in .env")
        print("See references/setup-connection.md for the one-time setup.")
        sys.exit(2)
    return token


def api_get(endpoint: str, params: dict = None):
    """GET with automatic pagination. Paginated lists -> combined list; single objects -> dict; errors -> None."""
    requests = _requests()
    base_url = f"https://graph.facebook.com/{API_VERSION}"
    merged = {"access_token": _token()}
    if params:
        merged.update(params)

    url = f"{base_url}/{endpoint}"
    all_data = []
    is_list = None

    while url:
        try:
            resp = requests.get(url, params=merged, timeout=60)
        except requests.RequestException as exc:
            print(f"Network error calling Meta API: {exc}")
            return None
        if resp.status_code == 401:
            print("ERROR: Meta token rejected (401). Regenerate the access token.")
            return None
        data = resp.json()

        if isinstance(data, dict) and "error" in data:
            err = data["error"]
            print(f"Meta API error {err.get('code', '')}: {err.get('message', err)}")
            return None

        if is_list is None:
            is_list = isinstance(data, dict) and "data" in data

        if is_list:
            all_data.extend(data.get("data", []))
            paging = data.get("paging", {})
            url = paging.get("next")
            merged = {}  # next URL already carries all params
        else:
            return data

    return all_data


def api_post(endpoint: str, data: dict = None):
    """POST an update. Returns response dict or None on error."""
    requests = _requests()
    base_url = f"https://graph.facebook.com/{API_VERSION}"
    merged = {"access_token": _token()}
    if data:
        merged.update(data)
    url = f"{base_url}/{endpoint}"
    try:
        resp = requests.post(url, data=merged, timeout=60)
    except requests.RequestException as exc:
        print(f"Network error calling Meta API: {exc}")
        return None
    result = resp.json()
    if isinstance(result, dict) and "error" in result:
        err = result["error"]
        print(f"Meta API error {err.get('code', '')}: {err.get('message', err)}")
        return None
    return result


def account_info(force: bool = False) -> dict:
    """Fetch/caches ad account info: currency, status, spend cap fields."""
    if _account_cache and not force:
        return _account_cache
    info = api_get(get_account_id(), {
        "fields": "currency,account_status,name,amount_spent,balance,timezone_name,created_time",
    })
    if info is None:
        print("ERROR: could not read ad account info (check token/account id).")
        sys.exit(2)
    _account_cache.update(info)
    return _account_cache


def account_currency() -> str:
    return (account_info().get("currency") or "USD").upper()


def currency_exponent(currency: str = None) -> int:
    """Minor-unit exponent: 0 for VND/JPY/..., 2 for USD/EUR/..."""
    currency = (currency or account_currency()).upper()
    return 0 if currency in ZERO_DECIMAL_CURRENCIES else 2


def to_minor(amount: float, currency: str = None) -> int:
    """Convert a human amount into the API's minor units."""
    return int(round(float(amount) * (10 ** currency_exponent(currency))))


def from_minor(amount, currency: str = None) -> float:
    """Convert API minor units into a human amount."""
    try:
        return float(amount or 0) / (10 ** currency_exponent(currency))
    except (TypeError, ValueError):
        return 0.0


def extract_actions(insight: dict, wanted: list) -> dict:
    """Sum per action_type counts from an insights 'actions' list."""
    totals = {name: 0.0 for name in wanted}
    for action in insight.get("actions") or []:
        atype = action.get("action_type", "")
        for name in wanted:
            if atype == name or atype.endswith(name):
                totals[name] += float(action.get("value", 0))
    return totals


def extract_cost_per(insight: dict, wanted: list) -> dict:
    """Cost per action_type from 'cost_per_action_type'."""
    out = {name: 0.0 for name in wanted}
    for item in insight.get("cost_per_action_type") or []:
        atype = item.get("action_type", "")
        for name in wanted:
            if atype == name or atype.endswith(name):
                out[name] = float(item.get("value", 0))
    return out
