# Optimization Decision Engine

The single source of truth for every scale / keep / decrease / pause decision. All thresholds
are derived from one number the user provides or the account reveals: **Target CPA**
(cost per acquisition — per order, per qualified lead). Currency-agnostic; works for VND, USD, EUR.

Derived from battle-tested operator frameworks: the 3×/1.5× non-performer and maintenance
rules, Poisson-based 3×-spend confidence threshold, Meta frequency fatigue bands from $25M+
spend data, and Google Smart Bidding conversion-volume progression.

---

## 1. Establish Target CPA (always step 1)

Priority order:

1. **User states a business target** (e.g. "tôi cần đơn dưới 100k", "target CPA $30") → use it.
2. **Account has 14+ days of converting data** → derive:
   ```
   Target CPA = median CPA of converting campaigns (last 30d) × 0.80
   ```
   Logic: the trailing median includes known waste; a 20% tightening is achievable through
   cutting losers and scaling winners without structural changes.
3. **No conversions yet** → ask the user for breakeven economics:
   ```
   E-commerce:  Breakeven CPA = AOV × gross margin %
   Lead-gen:    Breakeven CPA = deal size × lead→close rate
   Target CPA   = Breakeven CPA × 0.6..0.8   (profit headroom)
   ```
4. If the user cannot answer, set a provisional Target CPA from the first converting data
   and label every downstream verdict PROVISIONAL.

State which scenario you used. Re-derive at the start of every monthly review.

---

## 2. Data-sufficiency rules (before judging anything)

| Rule | Threshold |
|---|---|
| Learning window after launch or any change > 20% | 4 days minimum (Google full relearn: 1-2 weeks) |
| Minimum spend before calling an entity a non-performer | 2× Target CPA |
| Minimum spend before judging a converting entity's CPA | 1× Target CPA |
| Statistical comfort for a pause verdict on 0 conversions | 2× Target CPA spend ≈ 86% chance a true target-CPA entity would have converted (Poisson e⁻² ≈ 0.135); 3× ≈ 95% |
| Minimum clicks for a percentage verdict (CTR, CVR) | 100 clicks (30 minimum for a directional one) |
| Minimum conversions for a rate comparison (e.g. dayparting) | 2-3 per compared bucket |

If any threshold is unmet → verdict is **WAIT**, and you must state what is missing and when
to re-check. Impatience at day 2-3 is the #1 account killer.

---

## 3. Entity verdicts (campaign / ad set / ad / keyword)

Apply top-down; first match wins.

| # | Condition | Verdict | Action |
|---|---|---|---|
| 1 | Age < 4 days AND NOT (spend ≥ 3× target AND conv = 0) | SLEEP | Observe. No changes. |
| 2 | Age < 4 days AND spend ≥ 3× target AND conv = 0 | PAUSE-EARLY | Stop the bleed; this entity is not even in the auction's favor. |
| 3 | Spend = 0 for 7+ days | PAUSE-ZERO | Meta predicted poor engagement and won't deliver. Kill and replace creative. (Only valid if account is inside ad-count ceiling.) |
| 4 | Spend ≥ 2× target AND conv = 0 | PAUSE-NONPERFORMER | Turn off. Propose replacement (new angle/creative/audience). |
| 5 | Spend ≥ 1× target AND conv ≥ 3 AND CPA ≤ target | SCALE | +20% budget now; repeat +20% every 3-5 days; hard cap 30%/step. |
| 6 | Spend ≥ 1× target AND 0 < conv < 3 AND CPA ≤ 1.3× target | WATCH-ACCUMULATE | Keep; re-check in 2-3 days. |
| 7 | CPA 1.3-1.5× target (window ≥ 7 days) | DECREASE | −20% budget, or fix creative/landing page first if a clear fix exists. |
| 8 | CPA > 1.5× target (window ≥ 7 days, ≥ 100 clicks) | PAUSE-MAINTENANCE | Turn off; reallocate to winners. 1.5× for 14 days means structural, not luck. |
| 9 | Anything else | INSUFFICIENT | State the missing threshold and the re-check date. |

Notes:
- Verdicts 5-8 need window ≥ 7 days for full confidence; at 4-6 days soften PAUSE verdicts to DECREASE.
- SCALE blockers — all must pass: frequency < 3.0 (Meta), no budget spike in last 4 days,
  (for big jumps, +50%+) CPA ≤ target for 2+ consecutive weeks, testing pipeline exists (Meta).
- Rollback: if CPA > 1.5× target within 7 days after a scale step → cut 20-30% immediately,
  resume 10%/week after 2 stable weeks.
- ROAS variant: if the user optimizes for revenue, replace CPA logic with ROAS:
  SCALE if ROAS ≥ target AND value ≥ 3 conv, DECREASE 1.0-1.3× target ROAS, PAUSE < 0.7× target
  with ≥ 7 days of data. Bid-strategy targets move in 10-15% steps only.
- Google bidding guardrail by conversion volume: 0-15 conv/mo → Manual CPC or Maximize
  Conversions (no target); 15-30 → Maximize Conversions; 30+ stable → tCPA; real value data → tROAS.
  Setting a tCPA below trailing-30d CPA chokes delivery — start at or slightly above actual.

### Google-specific mechanics
- A campaign may spend up to 2× its daily budget on a single day; Google balances over the
  month. A one-day overspend is not a signal.
- Budget-capped AND converting → raising budget usually *lowers* CPA. Check
  "Search lost IS (budget)" — if high, budget is the constraint, not quality.
- Brand campaigns: cap them; pour the rest into proven non-brand.

### Meta-specific mechanics
- Two-campaign structure: **Scaling campaign (CBO, ~80%)** for proven ads only +
  **Testing campaign (CBO, ~20%)** for new concepts. Test ads compete only against tests,
  so CBO's winners never starve them. (Alternative used by some operators: ONE campaign with
  a 30% minimum-spend floor per ad set during angle validation — pick one model per account,
  don't mix.)
- Ad-count ceiling per campaign: `ceiling = (daily budget × 14) / (2 × Target CPA)`.
  Above it, ads get crowded out and low spend stops being a signal.
- CBO delivery pre-screen (Stage 1): new ad after 7 days spent < half its fair share
  (`campaign daily budget / active ads × 7 × 0.5`) → CBO rejected it → swap creative.
  Lifetime spend ≥ Target CPA but last-7d spend < ~10/day-equivalent → delivery kill.
  EUR/USD 0 spend after 7+ days = kill immediately. Both checks are only valid at/below the
  ad ceiling — above it, low spend means crowding, not rejection.
- **Learning-phase reset vs safe changes** (Meta AND Google Smart Bidding):
  RESETS = audience change, budget +30%, new creative, optimization-event change,
  bid-strategy change. SAFE = <10% budget tweaks, ad copy tweaks, pausing <24h.
  Stuck in learning → consolidate ad sets (one strong ad set beats five thin ones).
- **Minimum daily budget to exit learning**: `(Target CPA × 50) / 7`
  (100k VND target → ~714k VND/day; $50 target → ~$357/day). Below it, the algorithm cannot
  leave learning on a conversion event — spend is not wasted, it is tuition.
- Scale preconditions (all must be true): proven ads ≥ minimum for the next budget level,
  frequency below the campaign-type band, CPA ≤ target for 2+ consecutive weeks (for big
  jumps), and 3+ ready replacements in the testing pipeline. After a rollback, resume at
  +10% per week only after 2 stable weeks. Replacement SLA: most swaps live within 48h, hard
  max 7 days; empty pipeline → redirect budget to proven ads instead of waiting.

---

## 4. Breakdown optimization (all factors)

Only act on a breakdown bucket when it clears the data-sufficiency thresholds (≥ 100 clicks
for a rate verdict, ≥ 5% of spend for a structural verdict, ≥ 2-3 conversions per bucket for
CVR comparisons). A bucket that fails thresholds is an observation, not an action.

### 4.1 Hours & days (dayparting, both platforms)
- **Worst hours**: spend ≥ 1% of period spend AND clicks ≥ 30 AND conv = 0 AND hour CVR < 0.5×
  account CVR → exclude (Google ad schedule −100% for that block; Meta ad-set hour schedule,
  requires lifetime budget) or −30..50% bid adjustment first for 3-5 days, then exclude.
- **Best hours**: conv ≥ 2 AND CPA ≤ 0.7× account CPA → +20% bid adjustment (Google) /
  schedule weight (Meta). Aggregate 7-14 days before trusting an hourly pattern; single-day
  spikes are noise. Check day-of-week too (weekend vs weekday patterns are common).
- Timezone sanity: platform reports use account timezone — confirm with the user before
  proposing schedules.

### 4.2 Placements & positions (Meta)
- Breakdown: `publisher_platform × platform_positions`.
- Worst placement: spend share ≥ 5-10% AND CPA ≥ 1.5× account CPA (or spend ≥ 2× target, 0 conv)
  → propose excluding that position or feeding it placement-specific creative. Never exclude a
  whole platform (e.g. all of Reels) on one bad position.
- Best placement: CPA ≤ 0.7× average AND ≥ 2 conv → consider creative built natively for it
  (vertical video for Reels/Stories) before excluding the rest.
- Defaults by campaign type (verify with numbers before overriding): Audience Network is a
  standing exclusion candidate for lead-gen (lowest quality); retargeting runs manual with
  Feed priority; Stories/Reels only with dedicated 9:16 creative — if you only have 1:1,
  exclude Story positions rather than run bad crops.
- Google analog: Search vs Display vs Search Partners split — Display traffic inside Search
  campaigns is a classic hidden waste; separate networks or exclude.

### 4.3 Devices, age, gender, region
- Same 1.5× rule. Google → device bid adjustments (−30% floor, +20% default cap per step).
  Meta → age/gender edits on the ad set, or region splits; keep edits one variable at a time.
- Region: list top regions by spend with CPA; suggest geofence increases on winners
  (≥ 2 conv, CPA ≤ 0.7×) and exclusions on persistent losers (≥ 1.5× with ≥ 5-10% spend share).

### 4.4 Keywords & search terms (Google)
- Weekly ritual: pull search terms; terms with clicks ≥ 5 and 0 conv = waste candidates →
  negatives (start with phrase negatives). Recurring converting terms → new exact keywords.
- Quality Score ≤ 4 → fix expected CTR / ad relevance / landing page before raising bids.
- Match-type progression: Phrase (control) → Broad only with Smart Bidding + 30+ conv/month.
- Self-competition check: same keyword in multiple campaigns → consolidate or geofence/segment cleanly.

### 4.5 Creative & fatigue (Meta)
- Frequency bands vary by campaign type — judge against the right band, not one universal
  number:

| Campaign type | Healthy | Warning | Critical (act now) |
|---|---|---|---|
| Cold prospecting | 1.0-2.5 | 2.5-3.5 | > 4.0 |
| Retargeting | 2-4 | 4-6 | > 6.0 |
| ABM / niche lists | 2-5 | 5-8 | > 8.0 |

- Non-frequency fatigue signals (act on these even below the frequency band):
  CTR −20% from 7d baseline, CPM +30% over 2 weeks, any Ad Relevance "Below Average".
  RETIRE (don't iterate) at CTR −30% from peak or frequency > 5.0 cold.
- Hook rate (3-second video views ÷ impressions): target 20-25%; below 15% the ad will
  never perform — fix the hook before touching anything else.
- Iteration priority: hook > visual treatment > format > body copy/CTA. A new hook on a
  winner extends its lifespan 2-4 weeks.
- Format lifespans: static 14-28d · video 21-35d (<30s for prospecting, captions always,
  9:16 + audio ≈ +12% conversions) · carousel 21-35d (3-5 cards, first card stands alone;
  reordering cards counts as a "new" ad) · UGC 28-42d (fatigues slowest; refresh with a
  different customer, same concept). 4:5 aspect ratio ≈ +18% CTR / −22% CPA; human faces
  ≈ +38% engagement; numbers in headlines ≈ +20-30% CTR.
- Creative rotation: 50% iterations on winners, 30% iterations on mid performers,
  20% new concepts. Image-first for new concepts (cheap validation before video production).
- Rotate without resetting learning: launch new ads ALONGSIDE performers; never swap inside
  a performing ad set mid-learning; pausing is not editing.
- A Meta ad needs ~5,000-equivalent monthly spend headroom before fatigue; more proven ads
  = more scalable budget.
- Revenue-quality scoring: after ~20 leads/demos, score urgency/budget/fit 0-3 each (max 9),
  rank ads by average quality score — never by CPL/CTR (the cheapest lead is often the worst).
  Kill variations whose score drops below 5/9.

### 4.6 Budget reallocation (cross-campaign)
- Rank campaigns by CPA (or ROAS). Bottom quartile (≥ 1.5× target, ≥ 7d data) → paused or
  decreased; freed budget → top performers by the SCALE ladder, not dumped at once.
- Cap single-step reallocation at 30% of the source's budget.

---

## 5. Diagnostics, attribution & policy

### 5.1 CPA rising — diagnostic order (most common cause first)
1. **Tracking** (do this first): pixel/CAPI health, dedup, event match quality — recovering
   CAPI alone often restores 20-30% of "lost" conversions; check the attribution window
   (post-Jan 2026 Meta: 1d/7d click + 1d view only; default 7d-click/1d-view).
2. Frequency / creative decay (see §4.5 signals).
3. Learning phase (did you change ≥ 30% budget, audience, event, or bidding in the last week?).
4. Audience overlap / saturation (cold frequency up, reach flat).
5. Landing page (load > 3s ≈ 20% of clicks lost; mobile-first, one job per page).

### 5.2 Seasonality (re-derive Target CPA per season)
Meta CPM calendar: Q1 lowest · Q2 +10-20% · Q3 +15-25% · Q4 +60-80%.
Do not judge Q4 CPA against a Q2 baseline; consider deliberately trimming B2B spend in Q4.

### 5.3 Attribution comparability gate (cross-platform)
Never add or directly compare Meta conversions (7d-click window) with Google conversions
(often 30d window) as if they were the same people. Compare only side-by-side with windows
stated, or normalized. Platform ROAS ≠ business MER (`business revenue ÷ total ad spend`) —
state which one you are quoting. When platform and CRM disagree, the CRM wins.

### 5.4 Marginal efficiency (for reallocation)
```
marginal CPA  = incremental spend / incremental accepted conversions
marginal ROAS = incremental value / incremental spend
```
Reallocate from the weakest MARGINAL opportunity (the next dollar's return), not the worst
average CPA. An entity at good average CPA but flat conversions when fed more budget is a
worse home for money than its average suggests.

### 5.5 Baseline comparison order (narrowest first)
1. Same account, same objective, prior comparable period (exclude known outages/learning).
2. Same-account experiment or holdout.
3. CRM/revenue cohort joined to spend.
4. Peer cohort with disclosed methodology.
5. Industry benchmark — directional only, never the reason to change an account.

### 5.6 Policy, not law
Every threshold in this engine (2×, 1.5×, +20%, 30%, frequency bands) is **operator policy
chosen for repeatability**, not a platform truth. Before any threshold fires, sanity-check:
conversion lag maturity (is the window even final?), seasonality, planned changes, and
learning state. A threshold without those checks is a suggestion; with them, it is a decision.

---

## 6. Quick reference — all formulas

| Formula | Calculation |
|---|---|
| Target CPA (derived) | median converting CPA (30d) × 0.80 |
| Breakeven CPA (ecom) | AOV × gross margin % |
| Breakeven CPA (leadgen) | deal size × lead→close rate |
| Non-performer pause | spend ≥ 2× Target CPA, 0 conversions |
| Maintenance pause | CPA > 1.5× Target CPA, ≥ 7 days, ≥ 100 clicks |
| Scale step | +20% per 3-5 days, cap 30%/step |
| Scale rollback | CPA > 1.5× target post-scale → −20..30% now |
| Meta ad-count ceiling | (daily budget × 14) / (2 × Target CPA) |
| Meta CBO delivery kill (day 7) | spend < (campaign daily budget / active ads) × 7 × 0.5 |
| Meta fatigue | freq 3.0-3.5 warning · > 3.5 critical |
| Google Smart Bidding entry | ≥ 30 conversions / 30 days per campaign |
| Google target move | ±10-15% per 1-2 weeks |
| Google budget note | daily spend can hit 2× daily budget; judged monthly |
| Meta min daily budget to exit learning | (Target CPA × 50) / 7 |
| Meta hook rate | 3s views ÷ impressions; 20-25% good, <15% = hook is broken |
| Fatigue alt-signals | CTR −20%/7d · CPM +30%/2wk · retire at CTR −30% from peak |
| Search-term waste filter | clicks ≥ 5 (5 = default; 3 = aggressive for high-CPA niches) |
| Breakeven CPC | CPL target × landing-page conversion rate |
| Test duration floor | 3-5 days or ≥ 100 clicks / 2-3 conv per variant |
