#!/usr/bin/env python3
"""
Pull Meta (Facebook/Instagram) Ads performance data.

Usage:
    python pull_meta.py --what overview --days 7
    python pull_meta.py --what campaigns --days 14
    python pull_meta.py --what adsets --days 14 [--campaign-id 123]
    python pull_meta.py --what ads --days 14
    python pull_meta.py --what breakdown --days 7 --breakdown hourly
    python pull_meta.py --what breakdown --days 7 --breakdown placement
    python pull_meta.py --what breakdown --days 7 --breakdown device|age|gender|region
"""

import argparse

from common import date_window, previous_window, print_table, fmt_money, fmt_num
import meta_client
from meta_client import api_get, get_account_id, from_minor, extract_actions, extract_cost_per

CONVERSION_TYPES = [
    "purchase", "lead", "complete_registration", "start_trial", "subscribe",
    "onsite_conversion.lead_grouped", "offsite_conversion.fb_pixel_purchase",
    "offsite_conversion.fb_pixel_lead", "offsite_conversion.custom",
]
PURCHASE_TYPES = ["purchase", "offsite_conversion.fb_pixel_purchase", "offsite_conversion.custom"]


def time_range_params(start: str, end: str) -> dict:
    return {"time_range": f'{{"since":"{start}","until":"{end}"}}'}


def insight_fields(level: str) -> str:
    return (
        f"{level}_id,{level}_name,"
        "impressions,clicks,ctr,cpc,cpm,spend,reach,frequency,"
        "actions,cost_per_action_type"
    )


def summarize(insight: dict, level: str = "account") -> dict:
    conv = extract_actions(insight, CONVERSION_TYPES)
    purchases = extract_actions(insight, PURCHASE_TYPES)
    cpa_map = extract_cost_per(insight, CONVERSION_TYPES)
    spend = float(insight.get("spend", 0))
    conversions = sum(conv.values())
    cost_per = next((v for v in cpa_map.values() if v), 0.0)
    return {
        "id": insight.get(f"{level}_id", "") or insight.get("id", ""),
        "name": insight.get(f"{level}_name") or insight.get("ad_name")
                or insight.get("adset_name") or insight.get("campaign_name") or "?",
        "impressions": int(float(insight.get("impressions", 0))),
        "clicks": int(float(insight.get("clicks", 0))),
        "ctr": float(insight.get("ctr", 0)),
        "spend": spend,
        "reach": int(float(insight.get("reach", 0))),
        "frequency": float(insight.get("frequency", 0)),
        "cpm": float(insight.get("cpm", 0)),
        "cpc": float(insight.get("cpc", 0)),
        "conversions": conversions,
        "purchases": sum(purchases.values()),
        "cost_per_conversion": cost_per or (spend / conversions if conversions else 0.0),
    }


def metrics_row(key: str, s: dict) -> list:
    return [
        key, fmt_num(s["impressions"]), fmt_num(s["clicks"]), f"{s['ctr']:.2f}%",
        fmt_money(s["spend"]), fmt_num(s["reach"]), f"{s['frequency']:.2f}",
        fmt_money(s["cpm"]), f"{s['conversions']:.1f}", f"{s['purchases']:.1f}",
        fmt_money(s["cost_per_conversion"]) if s["conversions"] else "-",
    ]


HEADERS = ["Bucket", "Impr", "Clicks", "CTR", "Spend", "Reach", "Freq", "CPM",
           "Conv", "Orders", "CPA"]


def agg(rows) -> dict:
    out = {"impressions": 0, "clicks": 0, "spend": 0.0, "reach": 0, "conversions": 0.0,
           "purchases": 0.0}
    for s in rows:
        out["impressions"] += s["impressions"]
        out["clicks"] += s["clicks"]
        out["spend"] += s["spend"]
        out["reach"] += s["reach"]
        out["conversions"] += s["conversions"]
        out["purchases"] += s["purchases"]
    out["ctr"] = (out["clicks"] / out["impressions"] * 100) if out["impressions"] else 0
    out["frequency"] = (out["impressions"] / out["reach"]) if out["reach"] else 0
    out["cpm"] = (out["spend"] / out["impressions"] * 1000) if out["impressions"] else 0
    out["cost_per_conversion"] = (out["spend"] / out["conversions"]) if out["conversions"] else 0
    return out


def what_overview(args):
    start, end = date_window(args.days)
    prev_start, prev_end = previous_window(start, end)

    def window_rows(since, until):
        data = api_get(f"{get_account_id()}/insights", {
            "fields": insight_fields("account"),
            "level": "account",
            **time_range_params(since, until),
            "limit": 500,
        })
        if not data:
            return agg([summarize({}, "account")])
        return agg([summarize(i, "account") for i in data])

    cur, prev = window_rows(start, end), window_rows(prev_start, prev_end)
    currency = meta_client.account_currency()

    print(f"\nMeta Ads overview | {start} -> {end}  (previous: {prev_start} -> {prev_end})")
    print(f"Account: {get_account_id()} | currency {currency} | "
          f"timezone {meta_client.account_info().get('timezone_name', '?')}")
    print_table([metrics_row("current", cur), metrics_row("previous", prev)], HEADERS)

    if prev["spend"]:
        print(f"\nSpend change: {(cur['spend'] / prev['spend'] - 1) * 100:+.1f}%")
        if prev["conversions"]:
            print(f"Conv change: {(cur['conversions'] / prev['conversions'] - 1) * 100:+.1f}%")
    if cur["frequency"] >= 3.0:
        print(f"WARNING: account frequency {cur['frequency']:.2f} >= 3.0 (fatigue band).")
    if cur["conversions"]:
        print(f"Blended CPA: {fmt_money(cur['cost_per_conversion'])} {currency}")


def fetch_level(args, level: str):
    start, end = date_window(args.days)
    params = {
        "fields": insight_fields(level),
        "level": level,
        "time_range": time_range_params(start, end)["time_range"],
        "limit": 500,
    }
    if args.campaign_id and level in ("adset", "ad"):
        params["filtering"] = f'[{{"field":"campaign.id","operator":"IN","value":["{args.campaign_id}"]}}]'
    data = api_get(f"{get_account_id()}/insights", params)
    rows = [summarize(i, level) for i in (data or [])]
    rows.sort(key=lambda r: r["spend"], reverse=True)
    return rows


def what_campaigns(args):
    rows = fetch_level(args, "campaign")
    print(f"\nCampaigns | {date_window(args.days)[0]} -> {date_window(args.days)[1]}")
    print_table([metrics_row(f"{r['id']}", r) for r in rows], ["ID"] + HEADERS[1:])
    print("\nNote: IDs above are campaign IDs -> use with update_meta.py --campaign-id.")


def what_adsets(args):
    rows = fetch_level(args, "adset")
    print(f"\nAd sets | {date_window(args.days)[0]} -> {date_window(args.days)[1]}")
    print_table([metrics_row(f"{r['id']}", r) for r in rows], ["ID"] + HEADERS[1:])
    print("\nNote: IDs above are ad set IDs -> use with update_meta.py --adset-id.")


def what_ads(args):
    rows = fetch_level(args, "ad")
    print(f"\nAds | {date_window(args.days)[0]} -> {date_window(args.days)[1]}")
    print_table([metrics_row(f"{r['id']}", r) for r in rows], ["ID"] + HEADERS[1:])
    print("\nNote: IDs above are ad IDs -> use with update_meta.py --ad-id.")


def what_breakdown(args):
    start, end = date_window(args.days)
    b = args.breakdown

    # Base fields; hourly breakdown rejects reach/frequency, so keep hourly minimal.
    base = "impressions,clicks,ctr,cpc,cpm,spend,actions,cost_per_action_type"
    extra = {
        "hourly": ",hourly_stats_aggregated_by_audience_time_zone",
        "placement": ",publisher_platform,platform_positions",
        "device": ",impression_device",
        "age": ",age",
        "gender": ",gender",
        "region": ",region",
    }[b]

    params = {
        "fields": base + extra,
        "level": "account",
        "time_range": time_range_params(start, end)["time_range"],
        "limit": 500,
    }
    if b == "hourly":
        params["time_increment"] = "1"
        params["breakdowns"] = "hourly"
    elif b == "placement":
        params["breakdowns"] = "publisher_platform,platform_positions"
    elif b == "device":
        params["breakdowns"] = "impression_device"
    else:
        params["breakdowns"] = b

    data = api_get(f"{get_account_id()}/insights", params)
    buckets = {}
    for i in (data or []):
        if b == "hourly":
            slot = i.get("hourly_stats_aggregated_by_audience_time_zone", "")
            key = slot.split(" - ")[0][:5] if slot else "?"
        elif b == "placement":
            key = f"{i.get('publisher_platform', '?')} / {i.get('platform_positions', '?')}"
        else:
            key = str(i.get(b, "?"))
        s = summarize(i, "account")
        s["name"] = key
        buckets.setdefault(key, []).append(s)

    rows = [metrics_row(key, agg(items)) for key, items in sorted(buckets.items())]
    title = {
        "hourly": "Hour of day (audience timezone)",
        "placement": "Placement (platform / position)",
        "device": "Device",
        "age": "Age",
        "gender": "Gender",
        "region": "Region",
    }[b]
    print(f"\nBreakdown: {title} | {start} -> {end}")
    print_table(rows, HEADERS)
    print("\nRule: bucket with 5%+ spend & CPA>=1.5x avg (or 0 conv at 2x target) -> cut/narrow; "
          "CPA<=0.7x with 2+ conv -> push (Decision Engine 4.x)")


def what_creatives(args):
    """Extract copy of ACTIVE ads (body/headline/CTA/type) for creative audits."""
    ads = api_get(f"{get_account_id()}/ads", {
        "fields": "id,name,creative{id}",
        "effective_status": '["ACTIVE"]',
        "limit": 100,
    }) or []
    if not ads:
        print("No active ads found.")
        return
    print(f"\nActive ads copy ({len(ads)} ads)")
    counts = {}
    for a in ads:
        cid = (a.get("creative") or {}).get("id")
        if not cid:
            continue
        c = api_get(f"{cid}", {
            "fields": "id,name,body,title,link_url,call_to_action_type,object_story_spec,thumbnail_url",
        })
        if not c:
            continue
        spec = c.get("object_story_spec") or {}
        link = spec.get("link_data") or {}
        video = spec.get("video_data") or {}
        body = c.get("body") or link.get("message") or video.get("message") or ""
        headline = c.get("title") or link.get("name") or video.get("title") or ""
        ctype = "video" if video else ("carousel" if link.get("child_attachments") else "image/link")
        counts[ctype] = counts.get(ctype, 0) + 1
        print(f"\n--- ad {a.get('id')} '{a.get('name')}' [{ctype}] "
              f"CTA={c.get('call_to_action_type', '?')}")
        if headline:
            print(f"  Headline: {headline}")
        if body:
            print(f"  Body: {body[:300]}")
        if c.get("link_url"):
            print(f"  URL: {c.get('link_url')}")
    print(f"\nFormat mix: {counts}")
    print("Rule: judge by CPA/quality score, not CPL; 4-6 distinct concepts per campaign "
          "(references/meta-ads-guide.md - creative system).")


WHAT = {
    "overview": what_overview,
    "campaigns": what_campaigns,
    "adsets": what_adsets,
    "ads": what_ads,
    "breakdown": what_breakdown,
    "creatives": what_creatives,
}


def main():
    parser = argparse.ArgumentParser(description="Pull Meta Ads data")
    parser.add_argument("--what", required=True, choices=list(WHAT))
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--campaign-id", help="Filter ad sets / ads by campaign ID")
    parser.add_argument("--breakdown", default="hourly",
                        choices=["hourly", "placement", "device", "age", "gender", "region"])
    args = parser.parse_args()

    WHAT[args.what](args)


if __name__ == "__main__":
    main()
