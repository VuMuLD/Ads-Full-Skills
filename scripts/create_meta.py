#!/usr/bin/env python3
"""
Create Meta (Facebook/Instagram) Ads objects: campaign (always PAUSED), ad set,
hashed custom audience from CSV, and an interest-search helper.

Usage:
    python create_meta.py --what campaign --name "Scaling - Retargeting" \
        --objective OUTCOME_SALES --daily-budget 500000 --yes
    python create_meta.py --what adset --campaign-id 123 --name "Cold - LAL 1%" \
        --daily-budget 200000 --countries VN --age-min 25 --age-max 65 \
        --optimization-goal OFFSITE_CONVERSIONS --pixel-id 999 --custom-event-type PURCHASE --yes
    python create_meta.py --what adset --campaign-id 123 --name "LeadForm" \
        --optimization-goal LEAD_GENERATION --page-id 888 --yes
    python create_meta.py --what audience --name "CRM Customers 2026" --csv customers.csv --yes
    python create_meta.py --what interests --query "crm software"

Dry-run by default: --yes applies. Campaigns are ALWAYS created PAUSED.
Budgets are in ACCOUNT CURRENCY (auto-converted to API minor units; VND stays whole).
"""

import argparse
import csv
import hashlib
import json
import re
import sys
import time

import meta_client
from meta_client import api_get, api_post, get_account_id, to_minor

COUNTRY_MAP = {
    "vietnam": "vn", "việt nam": "vn", "united states": "us", "usa": "us",
    "united kingdom": "uk", "japan": "jp", "korea": "kr", "singapore": "sg",
    "thailand": "th", "germany": "de", "france": "fr", "australia": "au",
    "canada": "ca", "china": "cn", "india": "in", "malaysia": "my",
}
TITLE_WORDS = {"mr", "mrs", "ms", "dr", "phd", "jr", "sr", "ii", "iii", "iv"}


def _dry_run_banner(args):
    if not args.yes:
        print("\nDRY-RUN - re-run with --yes to apply.")
        sys.exit(0)


def create_campaign(args):
    if not args.daily_budget:
        sys.exit("ERROR: --daily-budget is required (CBO budget lives on the campaign)")
    print(f"Campaign '{args.name}' | objective {args.objective} | CBO daily budget "
          f"{args.daily_budget:,.0f} | special ad categories: {args.special_ad_categories or 'none'}")
    print("  status: PAUSED (always)")
    if not args.special_ad_categories:
        print("  reminder: credit/employment/housing/politics require --special-ad-categories")
    _dry_run_banner(args)
    data = {
        "name": args.name,
        "objective": args.objective,
        "status": "PAUSED",
        "special_ad_categories": json.dumps(args.special_ad_categories or []),
        "daily_budget": to_minor(args.daily_budget),
    }
    result = api_post(f"{get_account_id()}/campaigns", data)
    if result is None:
        sys.exit("FAILED - no campaign created.")
    print(f"Created campaign ID {result.get('id')}.")
    print(f"Next: python create_meta.py --what adset --campaign-id {result.get('id')} --name '...' --daily-budget ... --yes")


def build_targeting(args) -> dict:
    countries = [c.strip().lower() for c in (args.countries or "").split(",") if c.strip()]
    if not countries and not args.custom_audiences:
        print("WARNING: no --countries and no --custom-audiences; Meta needs a geo or audience.")
    targeting = {
        "geo_locations": {"countries": countries} if countries else {},
        "age_min": args.age_min,
        "genders": [1] if args.genders == "male" else [2] if args.genders == "female" else [0],
    }
    if args.age_max:
        targeting["age_max"] = args.age_max
    if args.custom_audiences:
        targeting["custom_audiences"] = [{"id": i.strip()} for i in args.custom_audiences.split(",") if i.strip()]
    if args.excluded_audiences:
        targeting["excluded_custom_audiences"] = [{"id": i.strip()} for i in args.excluded_audiences.split(",") if i.strip()]
    if args.platforms:
        targeting["publisher_platforms"] = [p.strip() for p in args.platforms.split(",") if p.strip()]
    return targeting


def create_adset(args):
    if not args.daily_budget:
        sys.exit("ERROR: --daily-budget is required for an ad set (ABO) unless the campaign shares budget")
    goal = args.optimization_goal
    print(f"Ad set '{args.name}' in campaign {args.campaign_id} | goal {goal} | "
          f"budget {args.daily_budget:,.0f} | geo {args.countries or '-'} | ages {args.age_min}-{args.age_max or '65+'}"
          + (f" | audiences {args.custom_audiences}" if args.custom_audiences else ""))
    if goal == "OFFSITE_CONVERSIONS" and not (args.pixel_id and args.custom_event_type):
        sys.exit("ERROR: OFFSITE_CONVERSIONS needs --pixel-id and --custom-event-type (e.g. PURCHASE)")
    if goal == "LEAD_GENERATION" and not args.page_id:
        sys.exit("ERROR: LEAD_GENERATION needs --page-id (the Facebook Page hosting the lead form)")
    _dry_run_banner(args)

    data = {
        "name": args.name,
        "campaign_id": args.campaign_id,
        "optimization_goal": goal,
        "billing_event": args.billing_event,
        "targeting": json.dumps(build_targeting(args)),
        "daily_budget": to_minor(args.daily_budget),
        "status": "PAUSED",
    }
    if goal == "OFFSITE_CONVERSIONS":
        data["promoted_object"] = json.dumps({"pixel_id": args.pixel_id,
                                              "custom_event_type": args.custom_event_type})
    elif goal == "LEAD_GENERATION":
        data["promoted_object"] = json.dumps({"page_id": args.page_id})
    result = api_post(f"{get_account_id()}/adsets", data)
    if result is None:
        sys.exit("FAILED - no ad set created.")
    print(f"Created ad set ID {result.get('id')} (PAUSED). Attach ads in Ads Manager or via the API, then enable.")


def _hash(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


def _norm_name(value: str) -> str:
    words = [w for w in re.split(r"[^a-zA-ZÀ-ỹđĐ]+", value.lower()) if w and w not in TITLE_WORDS]
    return " ".join(words)


def create_audience(args):
    try:
        with open(args.csv, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    except OSError as exc:
        sys.exit(f"ERROR: cannot read {args.csv}: {exc}")
    if not rows:
        sys.exit("ERROR: CSV has no data rows")

    cols = {c.lower(): c for c in rows[0]}
    email_c = next((cols[c] for c in cols if "email" in c), None)
    fn_c = next((cols[c] for c in cols if "first" in c or "ho" in c), None)
    ln_c = next((cols[c] for c in cols if "last" in c or "ten" in c), None)
    loc_c = next((cols[c] for c in cols if "country" in c or "nation" in c or "location" in c), None)
    if not email_c:
        sys.exit("ERROR: CSV needs an email column")
    print(f"Audience '{args.name}' from {args.csv}: {len(rows)} rows "
          f"(email={bool(email_c)}, first={bool(fn_c)}, last={bool(ln_c)}, country={bool(loc_c)})")
    print("PII is SHA-256 hashed locally; raw data never leaves this machine.")
    _dry_run_banner(args)

    created = api_post(f"{get_account_id()}/customaudiences", {
        "name": args.name,
        "description": args.description or "ads-optimizer upload",
        "subtype": "CUSTOM",
        "customer_file_source": "USER_PROVIDED_ONLY",
    })
    if created is None:
        sys.exit("FAILED - audience not created (if error 1359208: re-accept Custom Audience TOS in Ads Manager).")
    audience_id = created.get("id")

    sent = invalid = 0
    for start in range(0, len(rows), 10000):
        batch = rows[start:start + 10000]
        payload = {"schema": ["EMAIL"] + (["FN"] if fn_c else []) + (["LN"] if ln_c else []) + (["COUNTRY"] if loc_c else []),
                   "data": []}
        for r in batch:
            row = [_hash(r.get(email_c) or "")]
            if fn_c:
                row.append(_hash(_norm_name(r.get(fn_c) or "")))
            if ln_c:
                row.append(_hash(_norm_name(r.get(ln_c) or "")))
            if loc_c:
                raw = (r.get(loc_c) or "").strip().lower()
                country = COUNTRY_MAP.get(raw, raw[:2])
                row.append(_hash(country))
            payload["data"].append(row)
        result = api_post(f"{audience_id}/users", {"payload": json.dumps(payload)})
        if result is None:
            sys.exit(f"FAILED - upload batch starting at row {start} not delivered.")
        sent += int(result.get("num_received", 0))
        invalid += int(result.get("num_invalid_entries", 0))
        time.sleep(1)

    print(f"Uploaded {sent} rows ({invalid} invalid) to audience ID {audience_id}.")
    print("Match-rate reality: raw business emails often match <5%; enriched lists reach 40%+. "
          "Wait for processing, then check size in Ads Manager.")


def search_interests(args):
    result = api_get("search", {"type": "adinterest", "q": args.query, "limit": 25})
    if not result:
        print("No interests found.")
        return
    print(f"\nInterests matching '{args.query}' (use IDs in ad set targeting):")
    for item in result:
        print(f"  {item.get('id')}  {item.get('name')}  "
              f"(audience ~{int(item.get('audience_size', 0)):,}{', ' + item.get('topic') if item.get('topic') else ''})")


WHAT = {"campaign": create_campaign, "adset": create_adset,
        "audience": create_audience, "interests": search_interests}


def main():
    parser = argparse.ArgumentParser(description="Create Meta Ads objects (dry-run by default)")
    parser.add_argument("--what", required=True, choices=list(WHAT))
    parser.add_argument("--name")
    parser.add_argument("--objective", default="OUTCOME_SALES",
                        choices=["OUTCOME_SALES", "OUTCOME_LEADS", "OUTCOME_TRAFFIC",
                                 "OUTCOME_AWARENESS", "OUTCOME_ENGAGEMENT"])
    parser.add_argument("--daily-budget", type=float, help="Daily budget in ACCOUNT CURRENCY")
    parser.add_argument("--special-ad-categories", nargs="*", default=[],
                        choices=["CREDIT", "EMPLOYMENT", "HOUSING", "SOCIAL_ISSUES_ELECTIONS_POLITICS"])
    parser.add_argument("--campaign-id")
    parser.add_argument("--optimization-goal", default="OFFSITE_CONVERSIONS",
                        choices=["OFFSITE_CONVERSIONS", "LEAD_GENERATION", "LINK_CLICKS", "VALUE"])
    parser.add_argument("--billing-event", default="IMPRESSIONS", choices=["IMPRESSIONS", "LINK_CLICKS"])
    parser.add_argument("--pixel-id")
    parser.add_argument("--custom-event-type", default="PURCHASE",
                        choices=["PURCHASE", "LEAD", "COMPLETE_REGISTRATION", "ADD_TO_CART"])
    parser.add_argument("--page-id", help="Facebook Page ID (lead forms)")
    parser.add_argument("--countries", help="Comma-separated ISO-2 codes, e.g. VN,US")
    parser.add_argument("--age-min", type=int, default=18)
    parser.add_argument("--age-max", type=int, default=65)
    parser.add_argument("--genders", default="all", choices=["all", "male", "female"])
    parser.add_argument("--custom-audiences", help="Comma-separated audience IDs to target")
    parser.add_argument("--excluded-audiences", help="Comma-separated audience IDs to exclude")
    parser.add_argument("--platforms", help="Comma-separated: facebook,instagram,messenger,audience_network")
    parser.add_argument("--csv", help="CSV with email/first_name/last_name/country columns")
    parser.add_argument("--description")
    parser.add_argument("--query", help="Interest search keyword")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    needs = {"campaign": ["name"], "adset": ["campaign_id", "name"], "audience": ["name", "csv"], "interests": ["query"]}
    missing = [f for f in needs[args.what] if not getattr(args, f)]
    if missing:
        sys.exit(f"ERROR: --what {args.what} requires: --" + " --".join(missing))

    if args.what == "interests":
        WHAT[args.what](args)
        return
    meta_client.missing_config()
    WHAT[args.what](args)


if __name__ == "__main__":
    main()
