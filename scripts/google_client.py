"""
Google Ads API client for ads-optimizer.
Credentials come from .env (see references/setup-connection.md).
Provides get_client(), get_customer_id() and run_query() returning plain dicts.
"""

import sys

from common import env_str, is_placeholder

REQUIRED_FIELDS = [
    "GOOGLE_ADS_DEVELOPER_TOKEN",
    "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET",
    "GOOGLE_ADS_REFRESH_TOKEN",
    "GOOGLE_ADS_CUSTOMER_ID",
]


def missing_config() -> list:
    return [f for f in REQUIRED_FIELDS if is_placeholder(env_str(f))]


def _clean_id(value: str) -> str:
    return value.replace("-", "").strip()


def get_client():
    """Authenticate and return a GoogleAdsClient. Exits with a helpful message on failure."""
    missing = missing_config()
    if missing:
        print("ERROR: missing Google Ads credentials in .env: " + ", ".join(missing))
        print("See references/setup-connection.md for the one-time setup.")
        sys.exit(2)
    try:
        from google.ads.googleads.client import GoogleAdsClient
    except ImportError:
        print("ERROR: the google-ads package is not installed.")
        print("Run: py -m pip install -r requirements.txt")
        sys.exit(2)

    credentials = {
        "developer_token": env_str("GOOGLE_ADS_DEVELOPER_TOKEN"),
        "client_id": env_str("GOOGLE_ADS_CLIENT_ID"),
        "client_secret": env_str("GOOGLE_ADS_CLIENT_SECRET"),
        "refresh_token": env_str("GOOGLE_ADS_REFRESH_TOKEN"),
        "use_proto_plus": True,
    }
    login_customer = _clean_id(env_str("GOOGLE_ADS_LOGIN_CUSTOMER_ID"))
    if login_customer:
        credentials["login_customer_id"] = login_customer

    try:
        return GoogleAdsClient.load_from_dict(credentials)
    except Exception as exc:  # auth/config errors surface here
        print(f"ERROR: could not create Google Ads client: {exc}")
        print("Check the credentials in .env (see references/setup-connection.md).")
        sys.exit(2)


def get_customer_id() -> str:
    return _clean_id(env_str("GOOGLE_ADS_CUSTOMER_ID"))


def run_query(client, query: str) -> list:
    """Run a GAQL query, return rows as plain dicts keyed by snake_case fields used in queries."""
    ga_service = client.get_service("GoogleAdsService")
    response = ga_service.search(customer_id=get_customer_id(), query=query)
    rows = []
    for row in response:
        rows.append(_flatten(row))
    return rows


def _flatten(row) -> dict:
    """Convert a proto-plus row into a dict of {resource.field: value} with enums as strings."""
    out = {}
    for resource in ("customer", "campaign", "ad_group", "ad_group_criterion",
                     "search_term_view", "metrics", "segments", "campaign_budget"):
        obj = getattr(row, resource, None)
        if obj is None:
            continue
        for field in dir(obj):
            if field.startswith("_") or callable(getattr(obj, field, None)):
                continue
            try:
                value = getattr(obj, field)
            except Exception:
                continue
            if hasattr(value, "name") and not hasattr(value, "DESCRIPTOR"):  # enum
                value = value.name
            elif hasattr(value, "value") and not isinstance(value, (str, int, float, bool)):
                value = value.value
            if isinstance(value, (str, int, float, bool)) or value is None:
                out[f"{resource}.{field}"] = value
    return out


def micros_to_units(cost_micros) -> float:
    """cost_micros is 1e-6 of the account currency unit regardless of currency."""
    try:
        return float(cost_micros or 0) / 1_000_000
    except (TypeError, ValueError):
        return 0.0
