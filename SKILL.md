---
name: ads-optimizer
description: |
  Run and optimize Google Ads and Facebook/Meta Ads accounts end to end: connect to the platform APIs, pull live performance data, and produce data-backed scaling decisions — scale or cut budgets, pause underperformers, dayparting (best/worst hours and days), placement/device/geo/age cuts, creative fatigue detection, keyword and search-term waste, and A/B comparison test design. Acts like a machine-learning optimization advisor: "has orders → propose increasing budget", "ran 3-5 days, this placement is ineffective → propose turning it off", "this hour performs well → propose increasing".
  Use whenever the user mentions: Google Ads, Facebook Ads, Meta Ads, Instagram Ads, quảng cáo Google, quảng cáo Facebook, quảng cáo Facebook/Instagram, camp, campaign, chiến dịch, adset, ad set, ad group, nhóm quảng cáo, ngân sách quảng cáo, budget, CPA, CPL, ROAS, tối ưu quảng cáo, tối ưu camp, tăng camp, giảm camp, tắt camp, pause camp, scale camp, tần suất, frequency, search terms, từ khóa, keyword, tệp khán giả, audience, pixel, CAPI, đơn hàng, lead, hiệu quả quảng cáo, báo cáo quảng cáo — or asks casually like "check ads giúp tôi", "camp này có nên tăng ngân sách không", "quảng cáo chạy 5 ngày rồi thấy không hiệu quả".
  Also use for: deciding which campaigns to kill or scale, reallocation of budget between campaigns, weekly optimization routines, building new campaigns or comparison (A/B) campaign groups, creating campaigns/ad sets/keywords/audiences, and interpreting exported ad reports (CSV/XLSX) when API credentials are not yet connected.
---

# Ads Optimizer — Google Ads + Facebook/Meta Ads

A single skill that manages both Google Ads and Facebook (Meta) Ads like a professional
performance-marketing operator: connect → pull live data → classify every entity with the
Decision Engine → present ranked recommendations → apply changes only after explicit
user confirmation.

## Two operating modes

1. **CONNECTED** — credentials exist (`.env` at this skill's root, in `scripts/`, or in the
   working directory). Run the Python scripts under `scripts/` to pull real data and produce
   recommendations grounded in actual numbers.
2. **ADVISORY** — no credentials yet. Give framework-based advice from the reference files,
   analyze data the user pastes or exports (CSV/XLSX), and guide the user through
   [references/setup-connection.md](references/setup-connection.md) to get connected.

Never fake numbers. In ADVISORY mode, clearly label advice as framework-based, not data-based.

## 0. Connection check (do this first, every session)

```bash
cd C:\Users\phong\.agents\skills\ads-optimizer\scripts
python check_connection.py --platform both
```

- If Python or dependencies are missing, follow [references/setup-connection.md](references/setup-connection.md).
- Output tells you which platform is connected. Then route:
  - Google works → use `pull_google.py` + `optimize.py --platform google`.
  - Meta works → use `pull_meta.py` + `optimize.py --platform meta`.
  - Neither → ADVISORY mode + offer to set up credentials now.

## 1. Command reference

All commands run from `scripts/`. Date windows always end **yesterday** (partial-day data misleads).

| Task | Command |
|---|---|
| Check credentials | `python check_connection.py --platform both` |
| Full optimization report (both platforms) | `python optimize.py --platform both --days 7 --target-cpa <X>` |
| Google: account overview + period comparison | `python pull_google.py --what overview --days 7` |
| Google: campaign table | `python pull_google.py --what campaigns --days 14` |
| Google: hour / day / device breakdowns | `python pull_google.py --what hours --days 14` / `--what days` / `--what devices` |
| Google: keyword quality | `python pull_google.py --what keywords --days 30` |
| Google: wasted search terms | `python pull_google.py --what search-terms --days 14` |
| Google: apply change (dry-run by default) | `python update_google.py --campaign-id <id> --budget <X> --yes` |
| Meta: account overview | `python pull_meta.py --what overview --days 7` |
| Meta: campaigns / adsets / ads | `python pull_meta.py --what campaigns --days 14` (also `adsets`, `ads`) |
| Meta: breakdown analysis | `python pull_meta.py --what breakdown --days 7 --breakdown hourly` (also `placement`, `device`, `age`, `gender`, `region`) |
| Meta: extract active ads copy | `python pull_meta.py --what creatives` |
| Meta: apply change (dry-run by default) | `python update_meta.py --campaign-id <id> --status PAUSED --yes` |
| Self-test (no credentials needed) | `python selftest.py` |

### Build commands (W6) — all dry-run by default, all campaigns created PAUSED

| Task | Command |
|---|---|
| Google: search campaign | `python create_google.py --what campaign --name "HI - Theme - Phrase" --budget 50 --bidding MAXIMIZE_CONVERSIONS --yes` |
| Google: ad group / RSA / keywords | `--what adgroup` · `--what ad --headlines ... --descriptions ... --final-url ...` · `--what keywords --match-type PHRASE` (`--negative` for negatives) |
| Meta: campaign (CBO) | `python create_meta.py --what campaign --name "Scaling" --objective OUTCOME_SALES --daily-budget 500000 --yes` |
| Meta: ad set | `python create_meta.py --what adset --campaign-id <id> --countries VN --pixel-id <id> --custom-event-type PURCHASE --yes` |
| Meta: custom audience upload (hashed) | `python create_meta.py --what audience --name "CRM 2026" --csv customers.csv --yes` |
| Meta: interest search | `python create_meta.py --what interests --query "crm software"` |
| Google: OAuth refresh token helper | `python google_oauth_helper.py` (one-time; loopback flow) |

`--target-cpa` is in **account currency** (e.g. `100000` for 100,000 VND per order/lead).
If the user doesn't give one, `optimize.py` derives it from the account (see the Decision Engine)
and prints the derivation. Confirm it with the user before acting on it.

## 2. The Decision Engine (core rules)

Full detail with formulas and rationale: [references/optimization-decision-engine.md](references/optimization-decision-engine.md).
Read it before producing any recommendation. Summary:

| Signal (per campaign / ad set / ad) | Verdict | Action to propose |
|---|---|---|
| Younger than learning window (default 4 days) | SLEEP | Observe. No budget changes. Exception: spend ≥ 3× target with 0 conversions → pause. |
| 0 conversions AND spend ≥ 2× target CPA | PAUSE (non-performer) | Turn off. Replace (A/B test) rather than just shrinking. |
| 0 conversions AND spend < 2× target | INSUFFICIENT DATA | Wait. State how much more spend is needed before judging. |
| Conversions AND CPA ≤ target AND ≥ 3 conversions in window | SCALE | +20% budget now; +20% every 3-5 days; never > 30% at once. |
| Conversions AND CPA ≤ 1.3× target | WATCH | Keep. Re-check in 2-3 days. |
| CPA 1.3-1.5× target | DECREASE | −20% budget or fix creative/landing page. |
| CPA > 1.5× target for ≥ 7 days with enough clicks | PAUSE (maintenance) | Turn off, reallocate to winners. |
| Frequency ≥ 3.0 (Meta) | FATIGUE WARNING | Produce/rotate 2 new creatives within 14 days. |
| Frequency ≥ 3.5 (Meta) | FATIGUE CRITICAL | Swap creatives immediately. |
| Google: < 30 conversions/30 days | BIDDING GUARDRAIL | Stay on Manual CPC / Maximize Conversions — do not set tCPA yet. |

Learning-phase protection: after ANY budget change > 20%, bid strategy change, or target change,
wait 3+ days (Google full learning: 1-2 weeks) before judging again. Never edit inside the window.

Scale blockers (ALL must pass before proposing +20%): frequency < 3.0 (Meta), CPA ≤ target for
2+ consecutive weeks for big jumps, pipeline of test creatives exists (Meta), campaign not
budget-capped by daily spend limit it keeps hitting — if it IS capped and healthy, raising
budget is the #1 move.

## 3. Workflows

### W1 — Daily / weekly optimization (the main loop)

1. Ask (or assume): goal metric (orders? leads?), target CPA/CPL, review window (default 7 days).
2. `python optimize.py --platform <both|google|meta> --days 7 --target-cpa <X>`
3. The report classifies every campaign and lists ranked recommendations with the exact
   command to apply each one.
4. Walk the user through recommendations **in the user's language**. Group them:
   STOP-LOSS (pause/decrease) → SCALE (increase winners) → OPTIMIZE (breakdown cuts,
   dayparting, fatigue) → TEST (new comparison campaigns).
5. Apply only what the user approves. Apply one change at a time, then re-verify.

### W2 — Deep breakdown (why is it underperforming?)

Run breakdown pulls and read [references/optimization-decision-engine.md](references/optimization-decision-engine.md) §4 before interpreting:

- **Hours/days** (both platforms): worst hours = spend ≥ ~1% of total, 0 conversions,
  clicks ≥ 30 → propose exclusion or −bid; best hours = CPA ≤ 0.7× average with ≥ 2 conversions
  → propose +bid/schedule. Meta scheduling needs a lifetime budget; Google uses ad schedules.
- **Placements** (Meta): a placement with ≥ 5-10% of spend and CPA ≥ 1.5× account average
  → propose exclusion or placement-specific creative. Never exclude Reels wholesale without
  checking spend share.
- **Device / age / gender / region**: same 1.5× rule → bid adjustments (Google) or
  audience/geo edits (Meta).
- **Google search terms**: terms with clicks ≥ 5 and 0 conversions = waste → propose negatives;
  recurring converting terms = new exact keywords.
- **Google Quality Score ≤ 4** → fix ad relevance / landing page before raising bids.

### W3 — "It's making orders, should I scale?"

Confirm unit economics first (breakeven formulas in the Decision Engine), then apply the
scale ladder: +20% every 3-5 days, never > 30% at once; watch CPA after each step; if CPA
exceeds 1.5× target after a step, roll back 20-30% and wait 2 weeks. On Meta, scale via the
Scaling Campaign (CBO); on Google, scale budget-capped winners or raise tCPA in ≤ 10-15% steps.

### W4 — "Ran 3-5 days, not effective, turn it off?"

Check the SLEEP/INSUFFICIENT rules first — at 3-5 days with spend < 2× target CPA the honest
answer is usually "not enough data yet". Pause only when the non-performer rule fires
(spend ≥ 2× target, 0 conversions) or maintenance rule (CPA > 1.5× target, 7+ days, enough clicks).
Always propose a replacement or fix, never a bare pause.

### W5 — Design a comparison (A/B) campaign group

Follow [references/ab-testing-playbook.md](references/ab-testing-playbook.md). Core rules:
one variable at a time; minimum 3-5 days or ≥ 100 clicks / 2-3 conversions per variant;
Meta: 80% Scaling campaign (CBO) + 20% Testing campaign, winners graduate after
≥ 5 conversions at ≤ target CPA; Google: duplicate ad group / campaign via experiments,
same budget split. Name variants systematically (`[TestID]-[Variable]`).

### W6 — Build a new campaign

Use the `create_google.py` / `create_meta.py` build commands (§1). Google: Search first
(intent-first: brand → high-intent → competitor), Phrase match, Manual CPC or Maximize
Conversions until 30 conv/month, **always created PAUSED**, 8-12 RSA headlines. Meta:
remarketing → prospecting order, CBO, 4-6 creative concepts, pixel/CAPI verified before
spend. Copy for new ads comes from [references/copywriting-frameworks.md](references/copywriting-frameworks.md).
Review setup with the user before enabling anything.

## 4. Applying changes — safety contract

- **Draft first.** Present the proposed change and its exact command; wait for explicit
  approval. One approved change at a time.
- **Never delete.** Pause or archive only. Deletion is irreversible and out of contract.
- Update scripts are dry-run by default — `--yes` executes. Show the user the dry-run output.
- Budget changes: never > 30% at once. Bid/target changes: 10-15% steps. One change per
  entity per learning window.
- After applying, re-pull the entity to verify the change took effect, and schedule the
  re-check: 3 days for budget changes, 7-14 days for creative/audience changes.

## 5. Recommendation output format

Present every recommendation as a numbered list item with: **action**, **entity**, **evidence
(numbers from the report)**, **expected effect**, and the **exact command to apply**. Example:

> 1. [SCALE] Campaign "Retargeting - 30d" (+20% budget 500,000 → 600,000 VND)
>    Evidence: 14 orders at CPA 82,000 VND vs target 100,000; frequency 2.1; 14-day trend up.
>    Expected: +3-4 orders/day at stable CPA.
>    Apply: `python update_meta.py --campaign-id 1203... --daily-budget 600000 --yes`

When data is insufficient to judge, say exactly what threshold is missing and when to re-check.
This honesty is the skill's credibility — never invent urgency.

## 6. Core rules

1. Read [references/optimization-decision-engine.md](references/optimization-decision-engine.md) before any recommendation;
   platform nuance lives in [references/google-ads-guide.md](references/google-ads-guide.md)
   and [references/meta-ads-guide.md](references/meta-ads-guide.md). For new ad copy or A/B
   variants, read [references/copywriting-frameworks.md](references/copywriting-frameworks.md).
2. Money and metrics come from the scripts, not from memory. Quote the numbers you acted on.
3. Benchmarks are sanity checks, never the sole reason to change an account — account trend
   vs its own baseline outranks any industry number (comparison order: own prior period →
   holdout → CRM cohort → peer → industry, narrowest first).
4. Protect the learning phase. Most bad decisions are impatience at day 2-3. Budget +30%,
   audience change, new creative, event change, or bid-strategy change all RESET learning.
5. Every pause is paired with a replacement, a fix, or a reallocation — pausing without
   replacing just shrinks the account.
6. Cross-platform numbers are never summed: Meta (7d click) and Google (often 30d) attribute
   differently — compare side-by-side with windows stated; when platform and CRM disagree,
   the CRM wins.
7. All thresholds in the Decision Engine are operator policy, not universal laws — before
   one fires, check conversion-lag maturity, seasonality (Q4 CPM +60-80%), and learning state.
8. Reply in the user's language (Vietnamese users: reply in Vietnamese). Keep platform
   terminology in English where practitioners use it (campaign, ad set, frequency, ROAS).
