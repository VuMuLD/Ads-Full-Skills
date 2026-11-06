#!/usr/bin/env python3
"""
Update a Google Ads campaign — DRY-RUN by default, add --yes to execute.
Pause (never delete) is the only way this script turns anything off.

Usage:
    python update_google.py --campaign-id 123 --status PAUSED            # preview
    python update_google.py --campaign-id 123 --status PAUSED --yes      # apply
    python update_google.py --campaign-id 123 --budget 75 --yes          # daily budget
    python update_google.py --campaign-id 123 --budget 60 --status ENABLED --yes
"""

import argparse
import sys

from common import fmt_money
from google_client import get_client, get_customer_id


def fetch_campaign(client, customer_id, campaign_id):
    ga = client.get_service("GoogleAdsService")
    rows = ga.search(
        customer_id=customer_id,
        query=f"""
            SELECT campaign.name, campaign.status, campaign_budget.amount_micros
            FROM campaign WHERE campaign.id = {campaign_id}
        """,
    )
    for row in rows:
        return row
    return None


def main():
    parser = argparse.ArgumentParser(description="Update a Google Ads campaign (dry-run by default)")
    parser.add_argument("--campaign-id", required=True, type=int)
    parser.add_argument("--status", choices=["ENABLED", "PAUSED"])
    parser.add_argument("--budget", type=float, help="New daily budget (account currency)")
    parser.add_argument("--name")
    parser.add_argument("--yes", action="store_true", help="Actually apply (default: preview only)")
    args = parser.parse_args()

    if not any([args.status, args.budget, args.name]):
        print("Nothing to do: pass --status and/or --budget and/or --name.")
        sys.exit(1)

    client = get_client()
    customer_id = get_customer_id()
    current = fetch_campaign(client, customer_id, args.campaign_id)
    if current is None:
        print(f"Campaign {args.campaign_id} not found in this account.")
        sys.exit(1)

    current_budget = current.campaign_budget.amount_micros / 1_000_000
    print(f"Campaign {args.campaign_id} '{current.campaign.name}'")
    print(f"  current status: {current.campaign.status.name} | current daily budget: "
          f"{fmt_money(current_budget)}")
    if args.status:
        print(f"  new status:     {args.status}")
    if args.budget is not None:
        old = current_budget
        delta = (args.budget / old - 1) if old else 0
        print(f"  new budget:     {fmt_money(args.budget)} ({delta * 100:+.0f}%)")
        if old and abs(delta) > 0.30:
            print("  WARNING: change exceeds 30% - Decision Engine says split into steps. "
                  "Aborting unless this is intentional (remove this guard by editing the script).")
            if not args.yes:
                sys.exit(1)
    if args.name:
        print(f"  new name:       {args.name}")
    if not args.yes:
        print("\nDRY-RUN - re-run with --yes to apply.")
        return

    from google.api_core import protobuf_helpers

    changes = []
    if args.status or args.name:
        svc = client.get_service("CampaignService")
        op = client.get_type("CampaignOperation")
        camp = op.update
        camp.resource_name = svc.campaign_path(customer_id, str(args.campaign_id))
        mask_paths = []
        if args.status:
            camp.status = getattr(client.enums.CampaignStatusEnum, args.status.upper())
            mask_paths.append("status")
            changes.append(f"status -> {args.status}")
        if args.name:
            camp.name = args.name
            mask_paths.append("name")
            changes.append(f"name -> '{args.name}'")
        client.copy_from(op.update_mask, protobuf_helpers.field_mask(None, camp, mask_paths))
        svc.mutate_campaigns(customer_id=customer_id, operations=[op])

    if args.budget is not None:
        ga = client.get_service("GoogleAdsService")
        rows = ga.search(
            customer_id=customer_id,
            query=f"SELECT campaign.campaign_budget FROM campaign WHERE campaign.id = {args.campaign_id}",
        )
        budget_resource = None
        for row in rows:
            budget_resource = row.campaign.campaign_budget
            break
        if not budget_resource:
            print("Could not resolve campaign budget resource — budget not changed.")
            sys.exit(1)
        svc = client.get_service("CampaignBudgetService")
        op = client.get_type("CampaignBudgetOperation")
        budget = op.update
        budget.resource_name = budget_resource
        budget.amount_micros = int(args.budget * 1_000_000)
        client.copy_from(op.update_mask, protobuf_helpers.field_mask(None, budget, ["amount_micros"]))
        svc.mutate_campaign_budgets(customer_id=customer_id, operations=[op])
        changes.append(f"daily budget -> {fmt_money(args.budget)}")

    print("Applied:")
    for ch in changes:
        print(f"  - {ch}")
    print("Re-verify in 3 days (learning window) before judging results.")


if __name__ == "__main__":
    main()
