#!/usr/bin/env python3
"""
Verify credentials for Google Ads and/or Meta Ads.

Usage:
    python check_connection.py --platform both   (default)
    python check_connection.py --platform google
    python check_connection.py --platform meta
"""

import argparse
import sys

from common import fmt_money


def check_google() -> bool:
    from google_client import get_client, run_query

    print("Google Ads:")
    client = get_client()
    rows = run_query(
        client,
        "SELECT customer.descriptive_name, customer.currency_code, customer.time_zone "
        "FROM customer LIMIT 1",
    )
    if not rows:
        print("  FAILED: connected but could not read account info.")
        return False
    cust = rows[0].customer
    print(f"  OK: account '{cust.descriptive_name}' | currency {cust.currency_code} "
          f"| timezone {cust.time_zone}")
    return True


def check_meta() -> bool:
    import meta_client

    print("Meta Ads:")
    info = meta_client.account_info()
    status = {1: "ACTIVE", 2: "DISABLED", 3: "UNSETTLED", 7: "PENDING_RISK_REVIEW",
              8: "PENDING_SETTLEMENT", 9: "IN_GRACE_PERIOD", 100: "PENDING_CLOSURE",
              101: "CLOSED"}.get(info.get("account_status"), str(info.get("account_status")))
    print(f"  OK: account {meta_client.get_account_id()} '{info.get('name', '?')}'")
    print(f"      status {status} | currency {meta_client.account_currency()} | "
          f"timezone {info.get('timezone_name', '?')}")
    print(f"      lifetime spend {fmt_money(meta_client.from_minor(info.get('amount_spent')))} | "
          f"balance {fmt_money(meta_client.from_minor(info.get('balance')))}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Check ads platform connections")
    parser.add_argument("--platform", default="both", choices=["google", "meta", "both"])
    args = parser.parse_args()

    results = {}
    if args.platform in ("google", "both"):
        from google_client import missing_config
        if missing_config():
            print("Google Ads:  NOT CONFIGURED (missing .env keys: " + ", ".join(missing_config()) + ")")
            results["google"] = False
        else:
            try:
                results["google"] = check_google()
            except SystemExit:
                results["google"] = False
            except Exception as exc:
                print(f"  FAILED: {exc}")
                results["google"] = False

    if args.platform in ("meta", "both"):
        import meta_client
        if meta_client.missing_config():
            print("Meta Ads:    NOT CONFIGURED (missing .env keys: " + ", ".join(meta_client.missing_config()) + ")")
            results["meta"] = False
        else:
            try:
                results["meta"] = check_meta()
            except SystemExit:
                results["meta"] = False
            except Exception as exc:
                print(f"  FAILED: {exc}")
                results["meta"] = False

    print()
    if all(results.values()):
        print("All requested platforms are connected.")
    else:
        print("Some platforms are not connected — see references/setup-connection.md.")
        sys.exit(1)


if __name__ == "__main__":
    main()
