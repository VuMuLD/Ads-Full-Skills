#!/usr/bin/env python3
"""
Create Google Ads objects: search campaign (always PAUSED), ad group, RSA, keywords.

Usage:
    python create_google.py --what campaign --name "HI - CRM - Phrase" --budget 50 \
        --bidding MAXIMIZE_CONVERSIONS [--target-cpa 30] --yes
    python create_google.py --what adgroup --campaign-id 123 --name "High Intent" --cpc-bid 2.0 --yes
    python create_google.py --what ad --ad-group-id 456 --headlines "H1" "H2" "H3" \
        --descriptions "D1" "D2" --final-url https://... [--pin-first] --yes
    python create_google.py --what keywords --ad-group-id 456 --keywords "kw1" "kw2" \
        --match-type PHRASE --yes
    python create_google.py --what keywords --ad-group-id 456 --keywords "free" "cheap" --negative --yes

Dry-run by default: --yes actually applies. Campaigns are ALWAYS created PAUSED
(Decision Engine: review before spend).
"""

import argparse
import sys

from common import fmt_money
from google_client import get_client, get_customer_id

BIDDING_TYPES = ["MANUAL_CPC", "MAXIMIZE_CONVERSIONS", "MAXIMIZE_CONVERSION_VALUE",
                 "TARGET_CPA", "TARGET_ROAS"]
CAMPAIGN_TYPES = ["SEARCH", "DISPLAY", "SHOPPING", "PERFORMANCE_MAX", "VIDEO"]
MATCH_TYPES = ["BROAD", "PHRASE", "EXACT"]

RSA_MAX_HEADLINES, RSA_MAX_DESCRIPTIONS = 15, 4
RSA_HEADLINE_LEN, RSA_DESC_LEN = 30, 90


def _dry_run_banner(args):
    if not args.yes:
        print("\nDRY-RUN - re-run with --yes to apply.")
        sys.exit(0)


def create_campaign(client, customer_id, args):
    if args.bidding in ("TARGET_CPA",) and not args.target_cpa:
        sys.exit("ERROR: --bidding TARGET_CPA requires --target-cpa")
    if args.bidding in ("TARGET_ROAS",) and not args.target_roas:
        sys.exit("ERROR: --bidding TARGET_ROAS requires --target-roas")
    if args.type != "SEARCH":
        print("NOTE: non-Search campaigns bypass the intent-first default; see references/google-ads-guide.md")

    print(f"Campaign '{args.name}' | type {args.type} | daily budget {fmt_money(args.budget)} "
          f"| bidding {args.bidding}" + (f" (target {args.target_cpa or args.target_roas})" if args.target_cpa or args.target_roas else ""))
    print("  status: PAUSED (always - enable only after review)")
    print("  network: Google Search only (partners OFF, display OFF)")
    _dry_run_banner(args)

    budget_svc = client.get_service("CampaignBudgetService")
    budget_op = client.get_type("CampaignBudgetOperation")
    budget = budget_op.create
    budget.name = f"{args.name} Budget"
    budget.amount_micros = int(args.budget * 1_000_000)
    budget.delivery_method = client.get_type("BudgetDeliveryMethodEnum").STANDARD
    budget.explicitly_shared = False
    budget_resp = budget_svc.mutate_campaign_budgets(customer_id=customer_id, operations=[budget_op])

    svc = client.get_service("CampaignService")
    op = client.get_type("CampaignOperation")
    camp = op.create
    camp.name = args.name
    camp.status = client.enums.CampaignStatusEnum.PAUSED
    camp.campaign_budget = budget_resp.results[0].resource_name
    camp.advertising_channel_type = getattr(client.enums.AdvertisingChannelTypeEnum, args.type)
    if args.type == "SEARCH":
        camp.network_settings.target_google_search = True
        camp.network_settings.target_search_network = False
        camp.network_settings.target_content_network = False

    bidding = args.bidding
    if bidding == "MANUAL_CPC":
        camp.manual_cpc.enhanced_cpc_enabled = False
    elif bidding == "MAXIMIZE_CONVERSIONS":
        camp.maximize_conversions.target_cpa_micros = (int(args.target_cpa * 1_000_000)
                                                       if args.target_cpa else 0)
    elif bidding == "MAXIMIZE_CONVERSION_VALUE":
        camp.maximize_conversion_value.target_roas = args.target_roas or 0
    elif bidding == "TARGET_CPA":
        camp.target_cpa.target_cpa_micros = int(args.target_cpa * 1_000_000)
    elif bidding == "TARGET_ROAS":
        camp.target_roas.target_roas = args.target_roas

    resp = svc.mutate_campaigns(customer_id=customer_id, operations=[op])
    camp_resource = resp.results[0].resource_name
    camp_id = camp_resource.rsplit("/", 1)[-1]
    print(f"Created campaign ID {camp_id} (PAUSED).")
    print(f"Next: python create_google.py --what adgroup --campaign-id {camp_id} --name '...' --yes")


def create_adgroup(client, customer_id, args):
    print(f"Ad group '{args.name}' in campaign {args.campaign_id} | CPC bid {fmt_money(args.cpc_bid)}")
    _dry_run_banner(args)

    svc = client.get_service("AdGroupService")
    op = client.get_type("AdGroupOperation")
    ag = op.create
    ag.name = args.name
    ag.status = client.enums.AdGroupStatusEnum.ENABLED
    ag.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD
    ag.campaign = svc.campaign_path(customer_id, str(args.campaign_id))
    ag.cpc_bid_micros = int(args.cpc_bid * 1_000_000)
    resp = svc.mutate_ad_groups(customer_id=customer_id, operations=[op])
    ag_id = resp.results[0].resource_name.rsplit("/", 1)[-1]
    print(f"Created ad group ID {ag_id}.")
    print(f"Next: python create_google.py --what keywords --ad-group-id {ag_id} --keywords '...' --match-type PHRASE --yes")
    print(f"      python create_google.py --what ad --ad-group-id {ag_id} --headlines '...' --descriptions '...' --final-url '...' --yes")


def create_ad(client, customer_id, args):
    headlines = [h.strip() for h in args.headlines if h.strip()]
    descriptions = [d.strip() for d in args.descriptions if d.strip()]
    if len(headlines) < 3:
        sys.exit("ERROR: RSA needs at least 3 headlines")
    if len(descriptions) < 2:
        sys.exit("ERROR: RSA needs at least 2 descriptions")
    if len(headlines) > RSA_MAX_HEADLINES or len(descriptions) > RSA_MAX_DESCRIPTIONS:
        sys.exit(f"ERROR: max {RSA_MAX_HEADLINES} headlines / {RSA_MAX_DESCRIPTIONS} descriptions")
    for h in headlines:
        if len(h) > RSA_HEADLINE_LEN:
            print(f"WARNING: headline >30 chars, will truncate: '{h}'")
    for d in descriptions:
        if len(d) > RSA_DESC_LEN:
            print(f"WARNING: description >90 chars, will truncate: '{d}'")
    print(f"RSA in ad group {args.ad_group_id} | {len(headlines)} headlines, {len(descriptions)} descriptions"
          + (" | headline 1 pinned" if args.pin_first else ""))
    _dry_run_banner(args)

    svc = client.get_service("AdGroupAdService")
    op = client.get_type("AdGroupAdOperation")
    aga = op.create
    aga.status = client.enums.AdGroupAdStatusEnum.ENABLED
    aga.ad_group = client.get_service("AdGroupService").ad_group_path(customer_id, str(args.ad_group_id))
    aga.ad.final_urls.append(args.final_url)
    rsa = aga.ad.responsive_search_ad
    for i, text in enumerate(headlines):
        asset = client.get_type("AdTextAsset")
        asset.text = text
        if args.pin_first and i == 0:
            asset.pinned_field = client.enums.ServingConstraintMediaTypeEnum.HEADLINE_1
        rsa.headlines.append(asset)
    for text in descriptions:
        asset = client.get_type("AdTextAsset")
        asset.text = text
        rsa.descriptions.append(asset)
    if args.path1:
        rsa.path1 = args.path1
    if args.path2:
        rsa.path2 = args.path2
    resp = svc.mutate_ad_group_ads(customer_id=customer_id, operations=[op])
    print(f"Created RSA: {resp.results[0].resource_name}")
    print("Rule: 8-12 genuinely different headlines (value/outcome/proof/differentiator/CTA); "
          "pin at most 1 critical headline.")


def create_keywords(client, customer_id, args):
    display = {"BROAD": "{}", "PHRASE": '"{}"', "EXACT": "[{}]"}
    kws = [k.strip() for k in args.keywords if k.strip()]
    print(f"{'NEGATIVE ' if args.negative else ''}{args.match_type} keywords -> ad group {args.ad_group_id}: "
          + ", ".join(display[args.match_type].format(k) for k in kws))
    if args.negative and args.match_type == "BROAD":
        print("NOTE: negative BROAD blocks only when ALL words appear in the query "
              "('free trial' does not block 'free' alone).")
    _dry_run_banner(args)

    svc = client.get_service("AdGroupCriterionService")
    ops = []
    for text in kws:
        op = client.get_type("AdGroupCriterionOperation")
        crit = op.create
        crit.ad_group = client.get_service("AdGroupService").ad_group_path(customer_id, str(args.ad_group_id))
        crit.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
        crit.keyword.text = text
        crit.keyword.match_type = getattr(client.enums.KeywordMatchTypeEnum, args.match_type)
        if args.negative:
            crit.negative = True
        if args.keyword_cpc_bid:
            crit.cpc_bid_micros = int(args.keyword_cpc_bid * 1_000_000)
        ops.append(op)
    resp = svc.mutate_ad_group_criteria(customer_id=customer_id, operations=ops)
    print(f"Added {len(resp.results)} keywords.")
    print("Weekly ritual: pull search terms (pull_google.py --what search-terms) and negative the waste.")


WHAT = {}


def main():
    parser = argparse.ArgumentParser(description="Create Google Ads objects (dry-run by default)")
    parser.add_argument("--what", required=True, choices=["campaign", "adgroup", "ad", "keywords"])
    parser.add_argument("--name")
    parser.add_argument("--type", default="SEARCH", choices=CAMPAIGN_TYPES)
    parser.add_argument("--budget", type=float, help="Daily budget (account currency)")
    parser.add_argument("--bidding", default="MANUAL_CPC", choices=BIDDING_TYPES)
    parser.add_argument("--target-cpa", type=float)
    parser.add_argument("--target-roas", type=float)
    parser.add_argument("--campaign-id", type=int)
    parser.add_argument("--ad-group-id", type=int)
    parser.add_argument("--cpc-bid", type=float, default=2.0)
    parser.add_argument("--headlines", nargs="+", default=[])
    parser.add_argument("--descriptions", nargs="+", default=[])
    parser.add_argument("--final-url")
    parser.add_argument("--path1")
    parser.add_argument("--path2")
    parser.add_argument("--pin-first", action="store_true")
    parser.add_argument("--keywords", nargs="+", default=[])
    parser.add_argument("--match-type", default="PHRASE", choices=MATCH_TYPES)
    parser.add_argument("--negative", action="store_true")
    parser.add_argument("--keyword-cpc-bid", type=float, help="Optional per-keyword CPC bid")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    required = {"campaign": ["name", "budget"], "adgroup": ["campaign_id", "name"],
                "ad": ["ad_group_id", "final_url"], "keywords": ["ad_group_id", "keywords"]}
    missing = [f for f in required[args.what] if not getattr(args, f)]
    if missing:
        sys.exit(f"ERROR: --what {args.what} requires: --" + " --".join(missing))

    client = get_client()
    customer_id = get_customer_id()
    {"campaign": create_campaign, "adgroup": create_adgroup,
     "ad": create_ad, "keywords": create_keywords}[args.what](client, customer_id, args)


if __name__ == "__main__":
    main()
