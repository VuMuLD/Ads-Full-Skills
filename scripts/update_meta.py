#!/usr/bin/env python3
"""
Update a Meta (Facebook/Instagram) campaign / ad set / ad — DRY-RUN by default,
add --yes to execute. Pause (never delete) is the only way this script turns
anything off. Budgets are converted to the account's minor units automatically
(whole units for VND, cents for USD/EUR/...).

Usage:
    python update_meta.py --campaign-id 123 --status PAUSED           # preview
    python update_meta.py --campaign-id 123 --status PAUSED --yes     # apply
    python update_meta.py --campaign-id 123 --daily-budget 600000 --yes
    python update_meta.py --adset-id 456 --daily-budget 200000 --yes
    python update_meta.py --ad-id 789 --status PAUSED --yes
"""

import argparse
import sys

from common import fmt_money
import meta_client
from meta_client import api_post, get_account_id, to_minor, from_minor


def fetch_current(kind: str, object_id: str) -> dict:
    return meta_client.api_get(f"{object_id}", {"fields": "name,status,effective_status,daily_budget"}) or {}


def main():
    parser = argparse.ArgumentParser(description="Update a Meta campaign/ad set/ad (dry-run by default)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--campaign-id")
    group.add_argument("--adset-id")
    group.add_argument("--ad-id")
    parser.add_argument("--status", choices=["ACTIVE", "PAUSED"])
    parser.add_argument("--daily-budget", type=float, help="New daily budget in ACCOUNT CURRENCY (e.g. 600000 = 600k VND)")
    parser.add_argument("--name")
    parser.add_argument("--yes", action="store_true", help="Actually apply (default: preview only)")
    args = parser.parse_args()

    if args.adset_id and args.daily_budget is None and not args.status and not args.name:
        print("Nothing to do for ad set: pass --status and/or --daily-budget.")
        sys.exit(1)

    object_id = args.campaign_id or args.adset_id or args.ad_id
    kind = "campaign" if args.campaign_id else ("adset" if args.adset_id else "ad")

    currency = meta_client.account_currency()
    current = fetch_current(kind, object_id)
    if not current:
        print(f"Could not read {kind} {object_id} — check the ID and token permissions.")
        sys.exit(1)

    old_budget = from_minor(current.get("daily_budget"), currency)
    print(f"{kind.capitalize()} {object_id} '{current.get('name', '?')}'")
    print(f"  current status: {current.get('effective_status', current.get('status', '?'))} | "
          f"current daily budget: {fmt_money(old_budget)} {currency}")
    data = {}
    if args.status:
        data["status"] = args.status
        print(f"  new status:     {args.status}")
    if args.daily_budget is not None:
        delta = (args.daily_budget / old_budget - 1) if old_budget else 0
        print(f"  new budget:     {fmt_money(args.daily_budget)} {currency} ({delta * 100:+.0f}%) "
              f"[API value: {to_minor(args.daily_budget, currency)}]")
        if old_budget and abs(delta) > 0.30:
            print("  WARNING: change exceeds 30% — Decision Engine says split into steps. "
                  "Aborting unless this is intentional (remove this guard by editing the script).")
            if not args.yes:
                sys.exit(1)
        data["daily_budget"] = to_minor(args.daily_budget, currency)
    if args.name:
        data["name"] = args.name
        print(f"  new name:       {args.name}")

    if not data:
        print("Nothing to do.")
        sys.exit(1)
    if not args.yes:
        print("\nDRY-RUN — re-run with --yes to apply.")
        return

    result = api_post(object_id, data)
    if result is None:
        print("FAILED — no change applied.")
        sys.exit(1)
    print("Applied successfully. Re-verify in 3 days (learning window) before judging results.")
    print("Note: Meta ad set hourly scheduling requires a lifetime budget; "
          "dayparting via budget alone spreads spend across the day.")


if __name__ == "__main__":
    main()
