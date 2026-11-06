#!/usr/bin/env python3
"""
Ads Optimizer - pulls live data from Google Ads and/or Meta Ads, applies the
Decision Engine (references/optimization-decision-engine.md) and prints ranked
recommendations: scale / keep / decrease / pause, dayparting, placement & audience
cuts, creative fatigue, search-term waste, and A/B comparison suggestions.

Usage:
    python optimize.py --platform both --days 7
    python optimize.py --platform meta --days 7 --target-cpa 100000
    python optimize.py --platform google --days 14 --target-cpa 30 --learning-days 4

--target-cpa is in account currency (e.g. 100000 = 100k VND per order/lead).
If omitted, the target is derived from the account (median converting CPA x 0.8)
and the derivation is printed - confirm with the user before acting on it.
"""

import argparse
import json
import statistics
from datetime import date

from common import (date_window, print_table, fmt_money, fmt_num, ensure_reports_dir)
from google_client import get_client, run_query, micros_to_units, missing_config as google_missing
import meta_client
from meta_client import api_get, get_account_id, from_minor, extract_actions


# ---------------------------------------------------------------- classify

def classify(spend, conv, age_days, target, window_days, learning_days, min_clicks, clicks):
    """Return (verdict, action, note). First match wins - mirrors Decision Engine section 3."""
    if target is None:
        return ("NO-TARGET", "Cannot judge without Target CPA",
                "Provide --target-cpa or breakeven economics")

    if age_days < learning_days:
        if spend >= 3 * target and conv == 0:
            return ("PAUSE-EARLY", "Pause now (bleeding)",
                    f"Only {age_days:.0f}d old but spent {fmt_money(spend)} >= 3x target with 0 conv")
        return ("SLEEP", "Observe - inside learning window",
                f"Age {age_days:.0f}d < {learning_days}d; re-check in {learning_days - age_days:.0f} days")

    if spend == 0:
        return ("INSUFFICIENT", "Wait", "No spend in window - check status/audience size")

    if conv == 0:
        if spend >= 2 * target:
            return ("PAUSE-NONPERFORMER", "Turn off",
                    f"Spent {fmt_money(spend)} = {spend / target:.1f}x target with 0 conversions")
        needed = 2 * target - spend
        return ("INSUFFICIENT", "Wait",
                f"0 conv but only {fmt_money(spend)} spent "
                f"({fmt_money(needed)} more before the non-performer rule fires)")

    cpa = spend / conv
    multiple = cpa / target

    if conv >= 3 and multiple <= 1.0:
        return ("SCALE", "+20% budget",
                f"CPA {fmt_money(cpa)} = {multiple:.2f}x target with {conv:.0f} conv -> "
                f"scale ladder (+20% now, +20%/3-5d, cap 30%)")
    if multiple <= 1.3:
        return ("WATCH", "Keep",
                f"CPA {fmt_money(cpa)} = {multiple:.2f}x target - healthy band, re-check in 2-3d")
    if multiple <= 1.5:
        return ("DECREASE", "-20% budget or fix creative/LP",
                f"CPA {fmt_money(cpa)} = {multiple:.2f}x target (window {window_days}d)")
    # multiple > 1.5
    if window_days >= 7 and clicks >= min_clicks:
        return ("PAUSE-MAINTENANCE", "Turn off, reallocate to winners",
                f"CPA {fmt_money(cpa)} = {multiple:.2f}x target over {window_days}d "
                f"with {clicks} clicks - structural")
    return ("WATCH-BAD", "Keep (short window)",
            f"CPA {multiple:.2f}x target but window {window_days}d / {clicks} clicks - confirm next check")


def derive_target(campaigns):
    cpas = [c["spend"] / c["conv"] for c in campaigns if c["conv"] >= 1 and c["spend"] > 0]
    if not cpas:
        return None
    return statistics.median(cpas) * 0.80


def _blended_cpa(out):
    spend = sum(c["spend"] for c in out["campaigns"])
    conv = sum(c["conv"] for c in out["campaigns"])
    return (spend / conv) if conv else 0


def apply_verdicts(out_google, out_meta, target, args):
    """Classify campaigns and ads. Runs AFTER target derivation so verdicts use the final target."""
    for out in (out_google, out_meta):
        if not out:
            continue
        plat = out["platform"]
        for c in out["campaigns"]:
            verdict, action, note = classify(c["spend"], c["conv"], c["age_days"], target,
                                             args.days, args.learning_days, args.min_clicks, c["clicks"])
            if plat == "meta" and verdict == "SCALE" and c["frequency"] >= 3.0:
                verdict, action, note = ("WATCH", "Keep (scale blocked by frequency)",
                                         f"CPA qualifies but frequency {c['frequency']:.2f} >= 3.0 "
                                         f"- refresh audience/creative first")
            c["verdict"], c["action"], c["note"] = verdict, action, note
        if plat == "meta":
            for a in out["ads"]:
                verdict, action, note = classify(a["spend"], a["conv"], 99, target, args.days,
                                                 args.learning_days, args.min_clicks, a["clicks"])
                a["verdict"], a["action"], a["note"] = verdict, action, note


# ---------------------------------------------------------------- google

def analyze_google(args, target):
    start, end = date_window(args.days)
    clause = f"segments.date BETWEEN '{start}' AND '{end}'"
    out = {"platform": "google", "window": f"{start} -> {end}", "campaigns": []}

    query = f"""
        SELECT campaign.id, campaign.name, campaign.status, campaign.bidding_strategy_type,
               campaign.start_date, campaign_budget.amount_micros,
               metrics.impressions, metrics.clicks, metrics.cost_micros,
               metrics.conversions, metrics.conversions_value, metrics.all_conversions,
               metrics.search_impression_share, metrics.search_budget_lost_impression_share
        FROM campaign
        WHERE {clause} AND campaign.status != 'REMOVED'
        ORDER BY metrics.cost_micros DESC
    """
    for r in run_query(get_client(), query):
        c, m, b = r.campaign, r.metrics, r.campaign_budget
        age_days = 999
        if c.start_date:
            try:
                from datetime import datetime as _dt
                age_days = (_dt.strptime(end, "%Y-%m-%d") - _dt.strptime(c.start_date, "%Y-%m-%d")).days
            except ValueError:
                pass
        camp = {
            "id": c.id, "name": c.name, "status": c.status.name,
            "bidding": c.bidding_strategy_type.name,
            "daily_budget": micros_to_units(b.amount_micros),
            "age_days": age_days,
            "impressions": int(m.impressions or 0), "clicks": int(m.clicks or 0),
            "spend": micros_to_units(m.cost_micros), "conv": float(m.conversions or 0),
            "value": float(m.conversions_value or 0),
            "search_is": float(m.search_impression_share or 0),
            "lost_is_budget": float(m.search_budget_lost_impression_share or 0),
        }
        camp["cpa"] = (camp["spend"] / camp["conv"]) if camp["conv"] else 0
        out["campaigns"].append(camp)

    out["total_spend"] = sum(c["spend"] for c in out["campaigns"])

    # search-term waste
    st_query = f"""
        SELECT search_term_view.search_term, campaign.name,
               metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions
        FROM search_term_view
        WHERE {clause}
        ORDER BY metrics.cost_micros DESC
    """
    waste = []
    for r in run_query(get_client(), st_query):
        m = r.metrics
        conv = float(m.conversions or 0)
        clicks = int(m.clicks or 0)
        if conv == 0 and clicks >= 5:
            waste.append({"term": r.search_term_view.search_term,
                          "campaign": r.campaign.name, "clicks": clicks,
                          "spend": micros_to_units(m.cost_micros)})
    out["search_waste"] = sorted(waste, key=lambda w: w["spend"], reverse=True)[:15]

    # device skew
    dev_query = f"""
        SELECT segments.device, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions
        FROM campaign WHERE {clause} AND campaign.status != 'REMOVED'
    """
    devices = {}
    for r in run_query(get_client(), dev_query):
        d = r.segments.device.name
        dev = devices.setdefault(d, {"spend": 0.0, "conv": 0.0, "clicks": 0})
        dev["spend"] += micros_to_units(r.metrics.cost_micros)
        dev["conv"] += float(r.metrics.conversions or 0)
        dev["clicks"] += int(r.metrics.clicks or 0)
    out["devices"] = devices

    # low quality score keywords
    kw_query = f"""
        SELECT campaign.name, ad_group.name, ad_group_criterion.keyword.text,
               ad_group_criterion.quality_info.quality_score,
               metrics.clicks, metrics.cost_micros, metrics.conversions
        FROM keyword_view
        WHERE {clause} AND campaign.advertising_channel_type = 'SEARCH'
              AND ad_group_criterion.type = 'KEYWORD'
        ORDER BY metrics.cost_micros DESC
    """
    low_qs = []
    for r in run_query(get_client(), kw_query):
        qs = r.ad_group_criterion.quality_info.quality_score or 0
        if qs and qs <= 4:
            low_qs.append({"keyword": r.ad_group_criterion.keyword.text,
                           "campaign": r.campaign.name, "qs": qs,
                           "spend": micros_to_units(r.metrics.cost_micros)})
    out["low_qs"] = low_qs[:15]

    # hourly pattern (fresh 7d window for signal)
    h_start, h_end = date_window(7)
    hour_query = f"""
        SELECT segments.hour, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions
        FROM campaign WHERE segments.date BETWEEN '{h_start}' AND '{h_end}'
              AND campaign.status != 'REMOVED'
    """
    hours = {}
    for r in run_query(get_client(), hour_query):
        h = int(r.segments.hour)
        b = hours.setdefault(h, {"spend": 0.0, "conv": 0.0, "clicks": 0})
        b["spend"] += micros_to_units(r.metrics.cost_micros)
        b["conv"] += float(r.metrics.conversions or 0)
        b["clicks"] += int(r.metrics.clicks or 0)
    out["hours"] = hours
    out["hours_window"] = f"{h_start} -> {h_end}"
    return out


# ---------------------------------------------------------------- meta

META_CONV_TYPES = [
    "purchase", "offsite_conversion.fb_pixel_purchase", "offsite_conversion.custom",
    "lead", "onsite_conversion.lead_grouped", "complete_registration",
    "start_trial", "subscribe",
]


def analyze_meta(args, target):
    start, end = date_window(args.days)
    time_range = f'{{"since":"{start}","until":"{end}"}}'
    currency = meta_client.account_currency()
    out = {"platform": "meta", "window": f"{start} -> {end}", "currency": currency,
           "campaigns": [], "ads": []}

    # campaign metadata (status, budgets, created_time)
    meta_by_id = {}
    for c in api_get(f"{get_account_id()}/campaigns", {
        "fields": "id,name,status,effective_status,daily_budget,lifetime_budget,created_time,objective",
        "limit": 500,
    }) or []:
        meta_by_id[c["id"]] = c

    # campaign-level insights
    insights = api_get(f"{get_account_id()}/insights", {
        "fields": ("campaign_id,campaign_name,impressions,clicks,ctr,spend,reach,frequency,"
                   "actions,cost_per_action_type"),
        "level": "campaign",
        "time_range": time_range,
        "limit": 500,
    }) or []

    from datetime import datetime as _dt
    for i in insights:
        cid = i.get("campaign_id", "")
        md = meta_by_id.get(cid, {})
        age_days = 999
        created = md.get("created_time", "")
        if created:
            try:
                age_days = (_dt.strptime(end, "%Y-%m-%d") - _dt.strptime(created[:10], "%Y-%m-%d")).days
            except ValueError:
                pass
        conv = sum(extract_actions(i, META_CONV_TYPES).values())
        spend = float(i.get("spend", 0))
        camp = {
            "id": cid, "name": i.get("campaign_name", "?"),
            "status": md.get("effective_status", "?"),
            "objective": md.get("objective", "?"),
            "daily_budget": from_minor(md.get("daily_budget"), currency),
            "age_days": age_days,
            "impressions": int(float(i.get("impressions", 0))),
            "clicks": int(float(i.get("clicks", 0))),
            "spend": spend,
            "conv": conv,
            "frequency": float(i.get("frequency", 0)),
        }
        camp["cpa"] = (spend / conv) if conv else 0
        out["campaigns"].append(camp)

    out["total_spend"] = sum(c["spend"] for c in out["campaigns"])

    # ad-level insights (creative verdicts)
    ad_ins = api_get(f"{get_account_id()}/insights", {
        "fields": ("ad_id,ad_name,adset_name,campaign_name,impressions,clicks,spend,reach,"
                   "frequency,actions,cost_per_action_type"),
        "level": "ad",
        "time_range": time_range,
        "limit": 500,
    }) or []
    for i in ad_ins:
        conv = sum(extract_actions(i, META_CONV_TYPES).values())
        spend = float(i.get("spend", 0))
        ad = {
            "id": i.get("ad_id", ""), "name": i.get("ad_name", "?"),
            "campaign": i.get("campaign_name", "?"), "adset": i.get("adset_name", "?"),
            "spend": spend, "conv": conv,
            "frequency": float(i.get("frequency", 0)),
            "clicks": int(float(i.get("clicks", 0))),
        }
        ad["cpa"] = (spend / conv) if conv else 0
        out["ads"].append(ad)
    out["ads"].sort(key=lambda a: a["spend"], reverse=True)

    # account frequency (fatigue)
    acct = api_get(f"{get_account_id()}/insights", {
        "fields": "spend,reach,frequency", "level": "account", "time_range": time_range, "limit": 1,
    })
    out["account_frequency"] = float(acct[0].get("frequency", 0)) if acct else 0

    out["hours"] = _meta_breakdown(args, "hourly", META_CONV_TYPES)
    out["placements"] = _meta_breakdown(args, "placement", META_CONV_TYPES)
    out["ages"] = _meta_breakdown(args, "age", META_CONV_TYPES)
    out["genders"] = _meta_breakdown(args, "gender", META_CONV_TYPES)
    out["regions"] = _meta_breakdown(args, "region", META_CONV_TYPES)
    out["devices"] = _meta_breakdown(args, "device", META_CONV_TYPES)
    return out


def _meta_breakdown(args, b, conv_types):
    """Return {bucket: {spend, conv, clicks, impressions}} for a breakdown dimension."""
    start, end = date_window(args.days if b != "hourly" else 7)
    time_range = f'{{"since":"{start}","until":"{end}"}}'
    base = "impressions,clicks,spend,actions"
    extra = {
        "hourly": ",hourly_stats_aggregated_by_audience_time_zone",
        "placement": ",publisher_platform,platform_positions",
        "device": ",impression_device",
        "age": ",age", "gender": ",gender", "region": ",region",
    }[b]
    params = {"fields": base + extra, "level": "account", "time_range": time_range, "limit": 500}
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
            key = f"{i.get('publisher_platform', '?')}/{i.get('platform_positions', '?')}"
        else:
            key = str(i.get(b, "?"))
        rec = buckets.setdefault(key, {"spend": 0.0, "conv": 0.0, "clicks": 0, "impressions": 0})
        rec["spend"] += float(i.get("spend", 0))
        rec["conv"] += sum(extract_actions(i, conv_types).values())
        rec["clicks"] += int(float(i.get("clicks", 0)))
        rec["impressions"] += int(float(i.get("impressions", 0)))
    return buckets


# ---------------------------------------------------------------- recommendations

def _rec(priority, platform, action, evidence, command=None):
    return {"priority": priority, "platform": platform, "action": action,
            "evidence": evidence, "command": command}


def build_recommendations(target, google_out, meta_out, args):
    recs = []

    for name, out in (("Google", google_out), ("Meta", meta_out)):
        if not out:
            continue
        plat = out["platform"]
        for c in out["campaigns"]:
            v = c["verdict"]
            ev = (f"{fmt_money(c['spend'])} spent, {c['conv']:.0f} conv"
                  + (f", CPA {fmt_money(c['cpa'])}" if c["conv"] else "")
                  + f", {c['clicks']} clicks, age {c['age_days']}d - {c['note']}")
            if v in ("PAUSE-NONPERFORMER", "PAUSE-MAINTENANCE", "PAUSE-EARLY"):
                cmd = (f"python update_google.py --campaign-id {c['id']} --status PAUSED --yes"
                       if plat == "google"
                       else f"python update_meta.py --campaign-id {c['id']} --status PAUSED --yes")
                recs.append(_rec("P0", name, f"PAUSE campaign '{c['name']}'", ev, cmd))
            elif v == "SCALE" and c["daily_budget"] > 0:
                new = round(c["daily_budget"] * 1.2)
                cmd = (f"python update_google.py --campaign-id {c['id']} --budget {new} --yes"
                       if plat == "google"
                       else f"python update_meta.py --campaign-id {c['id']} --daily-budget {new} --yes")
                recs.append(_rec("P1", name,
                                 f"SCALE campaign '{c['name']}' {fmt_money(c['daily_budget'], 0)} "
                                 f"-> {fmt_money(new, 0)}/day (+20%)", ev, cmd))
            elif v == "DECREASE" and c["daily_budget"] > 0:
                new = round(c["daily_budget"] * 0.8)
                cmd = (f"python update_google.py --campaign-id {c['id']} --budget {new} --yes"
                       if plat == "google"
                       else f"python update_meta.py --campaign-id {c['id']} --daily-budget {new} --yes")
                recs.append(_rec("P2", name,
                                 f"DECREASE campaign '{c['name']}' {fmt_money(c['daily_budget'], 0)} "
                                 f"-> {fmt_money(new, 0)}/day (-20%)", ev, cmd))
            elif v in ("SLEEP", "WATCH", "WATCH-BAD", "INSUFFICIENT", "NO-TARGET"):
                prio = "P3" if v in ("WATCH", "SLEEP") else "P2"
                recs.append(_rec(prio, name, f"MONITOR campaign '{c['name']}'", ev))

            if plat == "google":
                if c["lost_is_budget"] > 0.2 and c["conv"] > 0 and c["verdict"] in ("SCALE", "WATCH"):
                    budget_cmd = (f"python update_google.py --campaign-id {c['id']} --budget "
                                  f"{round(c['daily_budget'] * 1.2) if c['daily_budget'] else '<X>'} --yes")
                    recs.append(_rec("P1", name, f"SCALE campaign '{c['name']}' (budget-capped)",
                                     f"Search lost IS (budget) {c['lost_is_budget']:.0%} while converting "
                                     f"at CPA {fmt_money(c['cpa'])} - raising budget often lowers CPA",
                                     budget_cmd))
                if c["bidding"] in ("MAXIMIZE_CONVERSIONS", "MANUAL_CPC") and c["conv"] >= 30 and args.days >= 28:
                    recs.append(_rec("P2", name, f"BIDDING: switch '{c['name']}' to Target CPA",
                                     f"{c['conv']:.0f} conv in {args.days}d >= 30 threshold; start tCPA at "
                                     f"trailing CPA {fmt_money(c['cpa'])}, move in 10-15% steps"))

            if plat == "meta":
                if c["frequency"] >= 3.5:
                    recs.append(_rec("P0", name, f"FATIGUE-CRITICAL campaign '{c['name']}'",
                                     f"frequency {c['frequency']:.2f} > 3.5 - swap creatives immediately "
                                     f"(2 new iterations ready within 14 days)"))
                elif c["frequency"] >= 3.0:
                    recs.append(_rec("P2", name, f"FATIGUE-WARNING campaign '{c['name']}'",
                                     f"frequency {c['frequency']:.2f} in 3.0-3.5 band - produce 2 iterations now"))

        # ad-level creative fatigue (Meta only)
        if plat == "meta":
            for a in out.get("ads", []):
                if a["frequency"] >= 3.5:
                    recs.append(_rec("P0", name, f"FATIGUE-CRITICAL ad '{a['name']}'",
                                     f"frequency {a['frequency']:.2f} > 3.5 with {fmt_money(a['spend'])} spend - "
                                     f"swap/rotate this creative immediately"))
                elif a["frequency"] >= 3.0:
                    recs.append(_rec("P2", name, f"FATIGUE-WARNING ad '{a['name']}'",
                                     f"frequency {a['frequency']:.2f} in 3.0-3.5 band with "
                                     f"{fmt_money(a['spend'])} spend - prepare iterations"))

    if meta_out:
        total = meta_out["total_spend"]
        blended = _blended_cpa(meta_out)
        for key, b in meta_out["placements"].items():
            if not total or b["spend"] / total < 0.05:
                continue
            bcpa = (b["spend"] / b["conv"]) if b["conv"] else 0
            if b["conv"] == 0 and target and b["spend"] >= 2 * target:
                recs.append(_rec("P2", "Meta", f"PLACEMENT CUT: exclude '{key}'",
                                 f"{b['spend'] / total:.0%} of spend ({fmt_money(b['spend'])}), 0 conv"))
            elif blended and b["conv"] and bcpa >= 1.5 * blended:
                recs.append(_rec("P2", "Meta", f"PLACEMENT CUT: exclude '{key}'",
                                 f"CPA {fmt_money(bcpa)} >= 1.5x account avg {fmt_money(blended)} "
                                 f"at {b['spend'] / total:.0%} of spend"))
            elif blended and b["conv"] >= 2 and bcpa <= 0.7 * blended:
                recs.append(_rec("P1", "Meta", f"PLACEMENT PUSH: native creative for '{key}'",
                                 f"CPA {fmt_money(bcpa)} <= 0.7x account avg at "
                                 f"{b['spend'] / total:.0%} of spend"))
        _hour_recs(recs, meta_out["hours"], "Meta", target, blended)

    if google_out:
        blended_g = _blended_cpa(google_out)
        _hour_recs(recs, google_out["hours"], "Google", target, blended_g)
        if google_out["search_waste"]:
            waste_total = sum(w["spend"] for w in google_out["search_waste"])
            recs.append(_rec("P2", "Google", "NEGATIVES: search-term waste found",
                             f"Top waste: {', '.join(w['term'] for w in google_out['search_waste'][:5])} "
                             f"({fmt_money(waste_total)} spend, 0 conv) - add phrase negatives",
                             "python pull_google.py --what search-terms --days 14"))
        if google_out["low_qs"]:
            recs.append(_rec("P3", "Google", "QS FIX: low Quality Score keywords",
                             ", ".join(f"{k['keyword']} (QS {k['qs']})" for k in google_out["low_qs"][:5]) +
                             " - fix ad relevance/landing page before raising bids"))

    # A/B comparison suggestions for the biggest spender on each platform
    for name, out in (("Google", google_out), ("Meta", meta_out)):
        if not out or not out["campaigns"]:
            continue
        top = max(out["campaigns"], key=lambda c: c["spend"])
        if top["spend"] <= 0:
            continue
        if out["platform"] == "meta":
            idea = ("create a Testing campaign (CBO, ~20% of budget) with 2-3 new hooks against "
                    "the current winner; graduate only if 5+ conv at CPA <= target "
                    "(see references/ab-testing-playbook.md)")
        else:
            idea = ("duplicate the ad group with one variable changed (new RSA set or landing "
                    "page) via Drafts & Experiments for a 50/50 split; verdict after 3-5 days "
                    "AND 100+ clicks/2-3 conv per variant")
        recs.append(_rec("P3", name, f"A/B TEST vs campaign '{top['name']}'",
                         f"Largest spender ({fmt_money(top['spend'])}). {idea}"))

    recs.sort(key=lambda r: {"P0": 0, "P1": 1, "P2": 2, "P3": 3}[r["priority"]])
    return recs


def _hour_recs(recs, hours, platform, target, blended):
    """Append dayparting recommendations directly (module-level, no closure)."""
    if not hours:
        return
    total = sum(b["spend"] for b in hours.values())
    if not total:
        return
    worst, best = None, None
    for key, b in sorted(hours.items()):
        share = b["spend"] / total
        if b["conv"] == 0 and b["clicks"] >= 30 and share >= 0.01 and (not target or b["spend"] >= 0.5 * target):
            if worst is None or b["spend"] > hours[worst]["spend"]:
                worst = key
        if b["conv"] >= 2 and blended and (b["spend"] / b["conv"]) <= 0.7 * blended:
            if best is None or (b["spend"] / b["conv"]) < (hours[best]["spend"] / hours[best]["conv"]):
                best = key
    if worst:
        b = hours[worst]
        recs.append(_rec("P2", platform, f"DAYPARTING: cut {worst}:00 hour",
                         f"{fmt_money(b['spend'])} spend, {b['clicks']} clicks, 0 conv - "
                         f"exclude or -30..50% bid for 3-5d first"))
    if best:
        b = hours[best]
        recs.append(_rec("P2", platform, f"DAYPARTING: push {best}:00 hour",
                         f"CPA {fmt_money(b['spend'] / b['conv'])} <= 0.7x avg, {b['conv']:.0f} conv - "
                         f"+20% bid / schedule weight"))


# ---------------------------------------------------------------- render

def render(out_google, out_meta, target, target_source, recs, args):
    lines = []
    lines.append(f"# Ads Optimization Report - {date.today().isoformat()}")
    lines.append(f"Window: last {args.days} days (ending yesterday) | Target CPA: "
                 f"{fmt_money(target) if target else 'NOT SET'} ({target_source})")
    lines.append("")

    for out in (out_google, out_meta):
        if not out:
            continue
        plat = out["platform"].title()
        lines.append(f"## {plat} - {out['window']}")
        lines.append("")
        rows = []
        for c in out["campaigns"]:
            rows.append([
                c["id"], str(c["name"])[:30], c["status"], f"{c['age_days']}d",
                fmt_num(c["impressions"]), fmt_num(c["clicks"]), fmt_money(c["spend"]),
                f"{c['conv']:.0f}", fmt_money(c["cpa"]) if c["conv"] else "-",
                c["verdict"], c["action"],
            ])
        table = print_table(rows, ["ID", "Name", "Status", "Age", "Impr", "Clicks", "Spend",
                                   "Conv", "CPA", "Verdict", "Action"], echo=False)
        lines.append("```")
        if table:
            lines.append(table)
        lines.append("```")
        lines.append("")
        if out["platform"] == "meta" and out["ads"]:
            lines.append("### Ad-level (creative) verdicts")
            lines.append("")
            rows = [[a["id"], str(a["name"])[:30], str(a["campaign"])[:24], fmt_money(a["spend"]),
                     f"{a['conv']:.0f}", fmt_money(a["cpa"]) if a["conv"] else "-",
                     f"{a['frequency']:.2f}", a["verdict"]] for a in out["ads"][:15]]
            ad_table = print_table(rows, ["ID", "Ad", "Campaign", "Spend", "Conv", "CPA", "Freq", "Verdict"], echo=False)
            lines.append("```")
            if ad_table:
                lines.append(ad_table)
            lines.append("```")
            lines.append("")
        if out["platform"] == "meta":
            freq = out.get("account_frequency", 0)
            band = "OK" if freq < 3 else ("WARNING (3.0-3.5)" if freq < 3.5 else "CRITICAL (>3.5)")
            lines.append(f"Account frequency: **{freq:.2f}** ({band})")
            lines.append("")

    lines.append("## Recommendations (ranked)")
    lines.append("")
    if recs:
        for i, r in enumerate(recs, 1):
            lines.append(f"{i}. **[{r['priority']}][{r['platform']}] {r['action']}**")
            lines.append(f"   Evidence: {r['evidence']}")
            if r.get("command"):
                lines.append(f"   Apply: `{r['command']}`")
    else:
        lines.append("No action triggers fired - account is inside normal bands. Re-check in 3 days.")
    lines.append("")
    lines.append("_Draft only - apply each change after explicit user confirmation. "
                 "Never delete; pause/archive only. One change per entity per learning window._")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Ads optimization report (Google + Meta)")
    parser.add_argument("--platform", default="both", choices=["google", "meta", "both"])
    parser.add_argument("--days", type=int, default=7, help="Analysis window (ends yesterday)")
    parser.add_argument("--target-cpa", type=float, help="Target cost per acquisition (account currency)")
    parser.add_argument("--learning-days", type=int, default=4, help="Learning-phase length (default 4)")
    parser.add_argument("--min-clicks", type=int, default=100, help="Min clicks for maintenance pause")
    args = parser.parse_args()

    target = args.target_cpa
    target_source = "user-provided" if target else None

    out_google = out_meta = None

    if args.platform in ("google", "both"):
        if google_missing():
            print("Google Ads not configured - skipping (see references/setup-connection.md).")
        else:
            out_google = analyze_google(args, target)

    if args.platform in ("meta", "both"):
        if meta_client.missing_config():
            print("Meta Ads not configured - skipping (see references/setup-connection.md).")
        else:
            out_meta = analyze_meta(args, target)

    if out_meta and not target:
        t = derive_target(out_meta["campaigns"])
        if t:
            target, target_source = t, "derived: median converting CPA x 0.80 (confirm with user)"
    if out_google and not target:
        t = derive_target(out_google["campaigns"])
        if t:
            target, target_source = t, "derived: median converting CPA x 0.80 (confirm with user)"

    if target is None:
        target_source = "missing - give --target-cpa or breakeven economics"

    apply_verdicts(out_google, out_meta, target, args)
    recs = build_recommendations(target, out_google, out_meta, args)
    report = render(out_google, out_meta, target, target_source, recs, args)

    print(report)

    out_dir = ensure_reports_dir()
    md_path = out_dir / f"ads_optimization_{date.today().isoformat()}.md"
    md_path.write_text(report, encoding="utf-8")
    json_path = out_dir / f"ads_optimization_{date.today().isoformat()}.json"
    json_path.write_text(json.dumps({"target": target, "target_source": target_source,
                                     "recommendations": recs}, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    print(f"\nSaved: {md_path}")
    print(f"Saved: {json_path}")


if __name__ == "__main__":
    main()
