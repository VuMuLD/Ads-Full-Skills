#!/usr/bin/env python3
"""
Self-test without credentials: unit-checks the Decision Engine thresholds and runs
the full Meta optimization pipeline against a mocked Graph API with fixture data.
Use this to verify changes to the engine or scripts before connecting real accounts.

Usage:
    python selftest.py            # runs everything, prints verdicts, exits 0/1
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import optimize  # noqa: E402
import meta_client  # noqa: E402

FAILED = []


def check(name, condition, detail=""):
    mark = "PASS" if condition else "FAIL"
    if not condition:
        FAILED.append(name)
    print(f"  [{mark}] {name}" + (f" - {detail}" if detail else ""))


def test_classify():
    """Shared Decision Engine thresholds (target = 100 for easy math)."""
    print("\nDecision Engine unit checks (target CPA = 100):")
    v, a, _ = optimize.classify(spend=50, conv=0, age_days=1, target=100, window_days=7,
                                learning_days=4, min_clicks=100, clicks=40)
    check("young + low spend -> SLEEP", v == "SLEEP", a)
    v, a, _ = optimize.classify(spend=350, conv=0, age_days=1, target=100, window_days=7,
                                learning_days=4, min_clicks=100, clicks=60)
    check("young + 3.5x target, 0 conv -> PAUSE-EARLY", v == "PAUSE-EARLY", a)
    v, a, _ = optimize.classify(spend=250, conv=0, age_days=10, target=100, window_days=7,
                                learning_days=4, min_clicks=100, clicks=80)
    check("2.5x target, 0 conv -> PAUSE-NONPERFORMER", v == "PAUSE-NONPERFORMER", a)
    v, a, _ = optimize.classify(spend=50, conv=0, age_days=10, target=100, window_days=7,
                                learning_days=4, min_clicks=100, clicks=30)
    check("0 conv, under 2x -> INSUFFICIENT (wait)", v == "INSUFFICIENT", a)
    v, a, _ = optimize.classify(spend=300, conv=5, age_days=30, target=100, window_days=7,
                                learning_days=4, min_clicks=100, clicks=300)
    check("CPA 60 with 5 conv -> SCALE", v == "SCALE", a)
    v, a, _ = optimize.classify(spend=100, conv=1, age_days=30, target=100, window_days=7,
                                learning_days=4, min_clicks=100, clicks=150)
    check("CPA 100 but 1 conv -> WATCH-ACCUMULATE path (not SCALE)", v in ("WATCH", "WATCH-BAD"), a)
    v, a, _ = optimize.classify(spend=140, conv=1, age_days=30, target=100, window_days=7,
                                learning_days=4, min_clicks=100, clicks=150)
    check("CPA 140 (1.4x) -> DECREASE", v == "DECREASE", a)
    v, a, _ = optimize.classify(spend=200, conv=1, age_days=30, target=100, window_days=7,
                                learning_days=4, min_clicks=100, clicks=150)
    check("CPA 200 (2x), 7d, 150 clicks -> PAUSE-MAINTENANCE", v == "PAUSE-MAINTENANCE", a)
    v, a, _ = optimize.classify(spend=200, conv=1, age_days=30, target=100, window_days=5,
                                learning_days=4, min_clicks=100, clicks=150)
    check("CPA 2x but 5d window -> WATCH-BAD (too early to pause)", v == "WATCH-BAD", a)


# ---------------- Meta mock ----------------

CAMPAIGNS = [
    {"id": "1", "name": "Winner - Retargeting", "status": "ACTIVE", "effective_status": "ACTIVE",
     "daily_budget": "500000", "lifetime_budget": None, "created_time": "2026-08-01T00:00:00+0700",
     "objective": "OUTCOME_SALES"},
    {"id": "2", "name": "Loser - Prospecting", "status": "ACTIVE", "effective_status": "ACTIVE",
     "daily_budget": "300000", "lifetime_budget": None, "created_time": "2026-08-01T00:00:00+0700",
     "objective": "OUTCOME_SALES"},
    {"id": "3", "name": "New - Testing", "status": "ACTIVE", "effective_status": "ACTIVE",
     "daily_budget": "150000", "lifetime_budget": None, "created_time": "2026-10-01T00:00:00+0700",
     "objective": "OUTCOME_SALES"},
]

CAMPAIGN_INSIGHTS = [
    {"campaign_id": "1", "campaign_name": "Winner - Retargeting", "impressions": "100000",
     "clicks": "5000", "ctr": "5", "spend": "700000", "reach": "50000", "frequency": "2.0",
     "actions": [{"action_type": "purchase", "value": "10"}],
     "cost_per_action_type": [{"action_type": "purchase", "value": "70000"}]},
    {"campaign_id": "2", "campaign_name": "Loser - Prospecting", "impressions": "80000",
     "clicks": "2000", "ctr": "2.5", "spend": "300000", "reach": "70000", "frequency": "1.1",
     "actions": [], "cost_per_action_type": []},
    {"campaign_id": "3", "campaign_name": "New - Testing", "impressions": "10000",
     "clicks": "300", "ctr": "3", "spend": "100000", "reach": "9000", "frequency": "1.1",
     "actions": [], "cost_per_action_type": []},
]

AD_INSIGHTS = [
    {"ad_id": "11", "ad_name": "Ad Hook A", "adset_name": "Adset 1",
     "campaign_name": "Winner - Retargeting", "impressions": "60000", "clicks": "3000",
     "spend": "400000", "reach": "15000", "frequency": "3.6",
     "actions": [{"action_type": "purchase", "value": "7"}],
     "cost_per_action_type": [{"action_type": "purchase", "value": "57142"}]},
]

PLACEMENTS = [
    {"impressions": "100000", "clicks": "4000", "spend": "660000", "publisher_platform": "facebook",
     "platform_positions": "feed", "actions": [{"action_type": "purchase", "value": "10"}]},
    {"impressions": "30000", "clicks": "800", "spend": "110000", "publisher_platform": "audience_network",
     "platform_positions": "classic", "actions": []},
]

HOURS = [
    {"impressions": "10000", "clicks": "120", "spend": "60000", "actions": [],
     "hourly_stats_aggregated_by_audience_time_zone": "03:00:00 - 03:59:59"},
    {"impressions": "50000", "clicks": "2000", "spend": "300000",
     "actions": [{"action_type": "purchase", "value": "8"}],
     "hourly_stats_aggregated_by_audience_time_zone": "19:00:00 - 19:59:59"},
]


def fake_api_get(endpoint, params=None):
    p = params or {}
    if "/campaigns" in endpoint:
        return CAMPAIGNS
    if "/insights" in endpoint:
        if p.get("level") == "campaign":
            return CAMPAIGN_INSIGHTS
        if p.get("level") == "ad":
            return AD_INSIGHTS
        if p.get("breakdowns") == "hourly":
            return HOURS
        if p.get("breakdowns") == "publisher_platform,platform_positions":
            return PLACEMENTS
        return [{"spend": "1100000", "reach": "90000", "frequency": "2.1"}]
    return []


def test_meta_pipeline():
    print("\nMeta pipeline (mocked API, VND fixtures):")
    meta_client.api_get = fake_api_get
    meta_client.missing_config = lambda: []
    meta_client.get_account_id = lambda: "act_test"
    optimize.api_get = fake_api_get
    optimize.get_account_id = lambda: "act_test"

    args = argparse.Namespace(days=7, target_cpa=None, learning_days=4, min_clicks=100,
                              platform="meta")
    out = optimize.analyze_meta(args, None)
    target = optimize.derive_target(out["campaigns"])
    check("target derived = median converting CPA x 0.80", target == 56000.0, f"got {target}")
    optimize.apply_verdicts(None, out, target, args)

    by_name = {c["name"]: c for c in out["campaigns"]}
    check("Winner: CPA 1.25x target -> WATCH", by_name["Winner - Retargeting"]["verdict"] == "WATCH")
    check("Loser: 300k spend 0 conv -> PAUSE-NONPERFORMER",
          by_name["Loser - Prospecting"]["verdict"] == "PAUSE-NONPERFORMER")
    check("New (0d): learning window -> SLEEP", by_name["New - Testing"]["verdict"] == "SLEEP")
    ad = out["ads"][0]
    check("Ad Hook A frequency 3.6 detected", ad["frequency"] == 3.6)
    check("account frequency 2.1 read", out["account_frequency"] == 2.1)
    check("placements fetched", "facebook/feed" in out["placements"], str(list(out["placements"])))

    recs = optimize.build_recommendations(target, None, out, args)
    actions = [r["action"] for r in recs]
    check("P0 pause recommendation with command",
          any(r["priority"] == "P0" and r["command"] for r in recs))
    check("placement push for facebook/feed (CPA 66k <= 0.7x avg 100k)",
          any("PLACEMENT PUSH" in a and "facebook/feed" in a for a in actions))
    check("dayparting cut 03:00 (60k, 120 clicks, 0 conv)",
          any("DAYPARTING: cut 03:00" in a for a in actions))
    check("dayparting push 19:00 (CPA 37.5k)", any("DAYPARTING: push 19:00" in a for a in actions))
    check("A/B comparison suggested for top spender",
          any("A/B TEST" in a and "Winner" in a for a in actions))
    check("ad fatigue critical at freq 3.6",
          any("FATIGUE-CRITICAL" in a and "Ad Hook A" in a for a in actions))

    report = optimize.render(None, out, target, "selftest", recs, args)
    check("report contains verdict table", "PAUSE-NONPERFORMER" in report)
    check("report has ranked recommendations", "## Recommendations" in report and "1. **[P0]" in report)


def main():
    print(f"ads-optimizer selftest - {sys.version.split()[0]}")
    test_classify()
    test_meta_pipeline()
    print()
    if FAILED:
        print(f"RESULT: {len(FAILED)} FAILED -> {', '.join(FAILED)}")
        sys.exit(1)
    print("RESULT: ALL TESTS PASSED")


if __name__ == "__main__":
    main()
