#!/usr/bin/env python3
"""
Pull Google Ads performance data.

Usage:
    python pull_google.py --what overview --days 7
    python pull_google.py --what campaigns --days 14 [--campaign-id 123]
    python pull_google.py --what hours   --days 14      # hour-of-day breakdown
    python pull_google.py --what days    --days 28      # day-of-week breakdown
    python pull_google.py --what devices --days 14
    python pull_google.py --what keywords --days 30 --top 30
    python pull_google.py --what search-terms --days 14 --min-clicks 5
    python pull_google.py --what ads --days 14
"""

import argparse

from common import date_window, previous_window, print_table, fmt_money, fmt_num
from google_client import get_client, get_customer_id, run_query, micros_to_units

METRIC_FIELDS = """
    metrics.impressions,
    metrics.clicks,
    metrics.cost_micros,
    metrics.conversions,
    metrics.conversions_value,
    metrics.all_conversions
"""


def date_clause(start_iso: str, end_iso: str) -> str:
    return f"segments.date BETWEEN '{start_iso}' AND '{end_iso}'"


def sums(rows) -> dict:
    out = {"spend": 0.0, "impressions": 0, "clicks": 0, "conv": 0.0, "value": 0.0}
    for r in rows:
        m = r.metrics
        out["spend"] += micros_to_units(m.cost_micros)
        out["impressions"] += int(m.impressions or 0)
        out["clicks"] += int(m.clicks or 0)
        out["conv"] += float(m.conversions or 0)
        out["value"] += float(m.conversions_value or 0)
    return out


def metrics_row(key: str, s: dict) -> list:
    ctr = (s["clicks"] / s["impressions"] * 100) if s["impressions"] else 0
    cpa = (s["spend"] / s["conv"]) if s["conv"] else 0
    roas = (s["value"] / s["spend"]) if s["spend"] else 0
    return [key, fmt_num(s["impressions"]), fmt_num(s["clicks"]), f"{ctr:.2f}%",
            fmt_money(s["spend"]), f"{s['conv']:.1f}",
            fmt_money(cpa) if s["conv"] else "-",
            fmt_money(s["value"]), f"{roas:.2f}x" if s["spend"] else "-"]


HEADERS = ["Bucket", "Impr", "Clicks", "CTR", "Spend", "Conv", "CPA", "Value", "ROAS"]


def what_overview(client, args):
    start, end = date_window(args.days)
    prev_start, prev_end = previous_window(start, end)

    cur_rows = run_query(client, f"SELECT {METRIC_FIELDS} FROM campaign WHERE {date_clause(start, end)} AND campaign.status != 'REMOVED'")
    prev_rows = run_query(client, f"SELECT {METRIC_FIELDS} FROM campaign WHERE {date_clause(prev_start, prev_end)} AND campaign.status != 'REMOVED'")
    cur, prev = sums(cur_rows), sums(prev_rows)

    print(f"\nGoogle Ads overview | {start} -> {end}  (previous: {prev_start} -> {prev_end})")
    print_table([metrics_row("current", cur), metrics_row("previous", prev)], HEADERS)

    if prev["spend"]:
        print(f"\nSpend change: {(cur['spend'] / prev['spend'] - 1) * 100:+.1f}%")
        if prev["conv"]:
            print(f"Conv change: {(cur['conv'] / prev['conv'] - 1) * 100:+.1f}%")
    if cur["conv"]:
        print(f"Blended CPA: {fmt_money(cur['spend'] / cur['conv'])}")


def what_campaigns(client, args):
    start, end = date_window(args.days)
    query = f"""
        SELECT
            campaign.id, campaign.name, campaign.status, campaign.bidding_strategy_type,
            campaign.start_date, campaign_budget.amount_micros,
            {METRIC_FIELDS},
            metrics.search_impression_share,
            metrics.search_budget_lost_impression_share
        FROM campaign
        WHERE {date_clause(start, end)}
    """
    if args.campaign_id:
        query += f" AND campaign.id = {args.campaign_id}"
    query += " ORDER BY metrics.cost_micros DESC"

    rows = []
    for r in run_query(client, query):
        c, m, b = r.campaign, r.metrics, r.campaign_budget
        s = {"spend": micros_to_units(m.cost_micros), "impressions": int(m.impressions or 0),
             "clicks": int(m.clicks or 0), "conv": float(m.conversions or 0),
             "value": float(m.conversions_value or 0)}
        ctr = (s["clicks"] / s["impressions"] * 100) if s["impressions"] else 0
        cpa = (s["spend"] / s["conv"]) if s["conv"] else 0
        roas = (s["value"] / s["spend"]) if s["spend"] else 0
        sis = f"{m.search_impression_share:.0%}" if m.search_impression_share else "-"
        lis = f"{m.search_budget_lost_impression_share:.0%}" if m.search_budget_lost_impression_share else "-"
        daily = fmt_money(micros_to_units(b.amount_micros), 0) if b.amount_micros else "-"
        rows.append([
            c.id, str(c.name)[:38], c.status.name, c.bidding_strategy_type.name,
            daily, fmt_num(s["impressions"]), fmt_num(s["clicks"]), f"{ctr:.2f}%",
            fmt_money(s["spend"]), f"{s['conv']:.1f}",
            fmt_money(cpa) if s["conv"] else "-", f"{roas:.2f}x" if s["spend"] else "-", sis, lis,
        ])

    print(f"\nCampaigns | {start} -> {end}")
    print_table(rows, ["ID", "Name", "Status", "Bidding", "Daily", "Impr", "Clicks", "CTR",
                       "Spend", "Conv", "CPA", "ROAS", "IS", "LostIS$"])
    print("\nLostIS$ high (>20%) + converting = budget-capped -> scale candidate (see Decision Engine).")


def what_hours(client, args):
    start, end = date_window(args.days)
    query = f"""
        SELECT segments.hour, {METRIC_FIELDS}
        FROM campaign
        WHERE {date_clause(start, end)} AND campaign.status != 'REMOVED'
    """
    buckets = {}
    for r in run_query(client, query):
        key = f"{int(r.segments.hour):02d}:00"
        buckets.setdefault(key, []).append(r)
    rows = []
    for hour in sorted(buckets):
        rows.append(metrics_row(hour, sums(buckets[hour])))
    print(f"\nHour-of-day breakdown | {start} -> {end} (account timezone)")
    print_table(rows, HEADERS)
    print("\nRule: worst hours = spend>=1% & 0 conv & clicks>=30 -> exclude/-bid. "
          "Best = CPA<=0.7x avg with 2+ conv -> +bid. (Decision Engine 4.1)")


def what_days(client, args):
    start, end = date_window(args.days)
    query = f"""
        SELECT segments.day_of_week, {METRIC_FIELDS}
        FROM campaign
        WHERE {date_clause(start, end)} AND campaign.status != 'REMOVED'
    """
    buckets = {}
    for r in run_query(client, query):
        buckets.setdefault(r.segments.day_of_week.name, []).append(r)
    order = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    rows = [metrics_row(day.title(), sums(buckets[day])) for day in order if day in buckets]
    print(f"\nDay-of-week breakdown | {start} -> {end}")
    print_table(rows, HEADERS)


def what_devices(client, args):
    start, end = date_window(args.days)
    query = f"""
        SELECT segments.device, {METRIC_FIELDS}
        FROM campaign
        WHERE {date_clause(start, end)} AND campaign.status != 'REMOVED'
    """
    buckets = {}
    for r in run_query(client, query):
        buckets.setdefault(r.segments.device.name, []).append(r)
    rows = [metrics_row(name.title(), sums(rows_)) for name, rows_ in sorted(buckets.items())]
    print(f"\nDevice breakdown | {start} -> {end}")
    print_table(rows, HEADERS)
    print("\nRule: 1.5x account CPA with 5%+ spend -> device bid adjustment (-30%..+20% per step).")


def what_keywords(client, args):
    start, end = date_window(args.days)
    query = f"""
        SELECT
            campaign.name, ad_group.name,
            ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type,
            ad_group_criterion.quality_info.quality_score,
            {METRIC_FIELDS}
        FROM keyword_view
        WHERE {date_clause(start, end)}
            AND campaign.advertising_channel_type = 'SEARCH'
            AND ad_group_criterion.type = 'KEYWORD'
        ORDER BY metrics.cost_micros DESC
    """
    rows = []
    for r in run_query(client, query)[: args.top]:
        kw = r.ad_group_criterion.keyword
        m = r.metrics
        qs = r.ad_group_criterion.quality_info.quality_score or 0
        cpa = micros_to_units(m.cost_micros) / float(m.conversions) if m.conversions else 0
        rows.append([
            str(r.campaign.name)[:24], str(r.ad_group.name)[:20],
            kw.text[:30], kw.match_type.name, qs or "-",
            fmt_num(m.impressions), fmt_num(m.clicks), fmt_money(micros_to_units(m.cost_micros)),
            f"{m.conversions:.1f}", fmt_money(cpa) if cpa else "-",
        ])
    print(f"\nKeywords by spend | {start} -> {end} (top {args.top})")
    print_table(rows, ["Campaign", "AdGroup", "Keyword", "Match", "QS",
                       "Impr", "Clicks", "Spend", "Conv", "CPA"])
    print("\nQS<=4 -> fix relevance/landing page before raising bids.")


def what_search_terms(client, args):
    start, end = date_window(args.days)
    query = f"""
        SELECT
            search_term_view.search_term, search_term_view.status,
            campaign.name,
            {METRIC_FIELDS}
        FROM search_term_view
        WHERE {date_clause(start, end)}
        ORDER BY metrics.cost_micros DESC
    """
    rows = []
    total_waste = 0.0
    status_mark = {"ADDED": "+", "NONE": "o", "EXCLUDED": "x"}
    for r in run_query(client, query):
        m = r.metrics
        clicks = int(m.clicks or 0)
        if clicks < args.min_clicks and float(m.conversions or 0) == 0:
            continue
        spend = micros_to_units(m.cost_micros)
        conv = float(m.conversions or 0)
        waste = spend if conv == 0 else 0.0
        total_waste += waste
        try:
            mark = status_mark.get(r.search_term_view.status.name, "?")
        except Exception:
            mark = "?"
        rows.append([
            str(r.search_term_view.search_term)[:40], str(r.campaign.name)[:24],
            mark,
            fmt_num(m.impressions), fmt_num(clicks), fmt_money(spend),
            f"{conv:.1f}", "WASTE" if conv == 0 else "ok",
        ])
    print(f"\nSearch terms | {start} -> {end} (min {args.min_clicks} clicks for zero-conv terms)")
    print_table(rows, ["Search term", "Campaign", "KW", "Impr", "Clicks", "Spend", "Conv", "Flag"])
    print(f"\nKW status: +=already a keyword  o=not matched  x=negated")
    print(f"Wasted spend (0 conv): {fmt_money(total_waste)}")
    print("Rule: clicks>=5 & 0 conv & not negated -> phrase negative. Repeated converters -> new exact keywords.")


def what_ads(client, args):
    start, end = date_window(args.days)
    query = f"""
        SELECT
            campaign.name, ad_group.name, ad_group_ad.ad.id, ad_group_ad.status,
            {METRIC_FIELDS}
        FROM ad_group_ad
        WHERE {date_clause(start, end)} AND campaign.status != 'REMOVED'
        ORDER BY metrics.cost_micros DESC
    """
    rows = []
    for r in run_query(client, query):
        m = r.metrics
        cpa = micros_to_units(m.cost_micros) / float(m.conversions) if m.conversions else 0
        rows.append([
            str(r.campaign.name)[:22], str(r.ad_group.name)[:18], r.ad_group_ad.ad.id,
            r.ad_group_ad.status.name,
            fmt_num(m.impressions), fmt_num(m.clicks), fmt_money(micros_to_units(m.cost_micros)),
            f"{m.conversions:.1f}", fmt_money(cpa) if cpa else "-",
        ])
    print(f"\nAds | {start} -> {end}")
    print_table(rows, ["Campaign", "AdGroup", "AdID", "Status", "Impr", "Clicks", "Spend", "Conv", "CPA"])


WHAT = {
    "overview": what_overview,
    "campaigns": what_campaigns,
    "hours": what_hours,
    "days": what_days,
    "devices": what_devices,
    "keywords": what_keywords,
    "search-terms": what_search_terms,
    "ads": what_ads,
}


def main():
    parser = argparse.ArgumentParser(description="Pull Google Ads data")
    parser.add_argument("--what", required=True, choices=list(WHAT))
    parser.add_argument("--days", type=int, default=14, help="Window length ending yesterday")
    parser.add_argument("--campaign-id", type=int, help="Restrict to one campaign")
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--min-clicks", type=int, default=5)
    args = parser.parse_args()

    client = get_client()
    WHAT[args.what](client, args)


if __name__ == "__main__":
    main()
