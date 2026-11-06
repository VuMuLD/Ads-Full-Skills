# Meta (Facebook/Instagram) Ads Platform Guide

Read when working on Meta-specific strategy, structure, audiences, or creative.

## Philosophy: data + creative are the targeting

Meta's algorithm (Andromeda + Gem) optimizes delivery relentlessly but cannot see lead/
customer *quality*. Two consequences:

1. Feed it high-quality audience inputs (customer lists, lookalikes, pixel/CAPI events).
2. Let **creative do the filtering** — ad copy should call out who it's for and repel who it's
   not ("mosquito-repellent targeting").

Data hierarchy: CRM customer-list lookalikes (Tier 1) → high-quality interest/behavior stacks
(Tier 2) → broad (Tier 3, only with large TAM and strong creative filter).

## Campaign structure

- Phase 1 — Audience validation: ABO, one ad set per audience source, same ads everywhere,
  2-4 weeks. Win = an audience producing quality results at target CPA.
- Phase 2 — Creative scaling (most accounts live here): two CBO campaigns —
  **Scaling (~80%)** holds graduated winners only; **Testing (~20%)** holds new concepts.
- Phase 3 — Advantage+ / Advantage+ Shopping: only when volume supports it
  (~50+ conversions/week/ad set). Until then, manual control wins.
- Naming: `[FunnelStage] - [Audience] - [Offer] - [CBO/ABO]`.
- Order of build: Remarketing → Prospecting → Acceleration (retargeting is cheapest ROI).
- Cross-channel play: build Meta retargeting audiences from Google/website traffic via UTM+pixel.

## Audiences

- Remarketing windows: site visitors 7/30/180d, video viewers 50/75%, IG/FB engagers 30/90d,
  lead-form openers non-converters.
- Lookalikes: 1-3% for precision, test 3-5% for scale; seed with purchasers/qualified leads,
  never raw junk leads. Seed minimums: LAL origin ≥ 100 members (1,000-5,000 recommended),
  retargeting list ≥ 100, broad prospecting 500K-2M people.
- Broad works for big-TAM offers with 4-6 strong creatives; it fails for niche/ABM.
- Match-rate reality for customer uploads: raw business emails often match <5%; enriching
  (phone, name, location) lifts 40-85%. Hashing and upload are handled by
  `scripts/create_meta.py --what audience`.
- Always exclude: closed-won customers, converters from the last 7-30 days, employees,
  disqualified accounts. Check audience overlap and freshness (stale lists decay).
- ABM viability gates on Meta: target-account list ≥ 1,000 companies (under ~500 →
  retargeting only), ≥ $3k/month to exit learning, 60+ day sales cycle, $25k+ deal value.
  Below those, precision platforms win.

## Acceleration (ads on open pipeline)

- Objective must be AWARENESS (never conversion — you're not pushing demos to people already
  in deals); ~$50-200/day scaled to deal size; measure incrementality with an 80/20 holdout
  judged after 21+ days.
- Attribution for lead quality: store the Meta click ID / lead ID at lead creation and pass
  it through every CRM stage change — without it, downstream MQL/SQL attribution silently
  breaks. Meta Conversion Leads optimization needs ~200 leads/month and a stage converting
  1-40%.

## Creative system

- 4-6 distinct concepts per campaign (algorithm needs diversity), 3-5 ads per ad set.
- Concept > variation: test UGC vs before/after vs demo vs meme vs testimonial — not button colors.
- 50/30/20 production split: iterations of winners / iterations of mid / new concepts.
- Image-first for new concepts (cheap validation); produce video only after a concept proves out.
- Creative IS the audience filter: first line names the target, e.g. "Dành cho chủ shop
  Shopify đang chạy quảng cáo..."
- Lead forms (lead-gen campaigns): Higher Intent type, work-email enforcement, 1-3 qualifying
  questions — fights "social amnesia" and junk leads.

## Placement strategy

- Advantage+ placements ON by default; judge placements by CPA breakdown (see Decision
  Engine §4.2), not gut feeling.
- Common pattern: Reels/Stories cheap reach but variable quality; Feed/FB positions often
  carry intent; Audience Network frequently the worst — verify with numbers before excluding.

## Tracking prerequisites (before any spend)

- Pixel installed + Events Manager verified domain + priority events mapped
  (Purchase > Lead > CompleteRegistration > ...).
- Conversions API (CAPI) active with deduplication (event_id match), Event Match Quality ≥ 6.
- Aggregated Event Measurement configured for the domain (8 priority events).
- If conversions are off-domain (webinar platforms etc.), track via pixel on thank-you page
  or CAPI server events — do not optimize blind.

## Benchmarks & patterns (sanity checks, not targets)

Lead-gen directional ranges with red flags (flag = investigate, not auto-act):

| Metric | Healthy | Red flag |
|---|---|---|
| CTR (link) | 1.0-1.5% (2%+ strong) | < 0.8% |
| CPM | $10-20 (market-dependent) | > $25 sustained |
| CPC | $1.50-2.50 | > $3.50 |
| CPL | $20-50 | > $75 |
| Landing page CVR | 8-12% | < 5% |
| MQL→SQL | 5-10% | < 3% |
| Frequency (cold) | 1.5-3.0 | > 4.0 |

- Lead form vs landing page: LP converts ≥ 5% → use the LP (quality); LP below 2% →
  lead form. Forms: "More Volume" + 0-1 questions only for audience validation; drop-off
  spikes above 3 questions; confirmation message must state exactly what happens next.
- Weekend/weeknight patterns vary by market — verify with the hourly breakdown, never assume.
- Seasonality: Q4 CPMs inflate 60-80% in many markets; re-derive Target CPA per season
  (Decision Engine §5.2).
- Never optimize a considered/quality purchase for Link Clicks — the cheapest click is the
  worst customer.

## Scaling protocol

1. All SCALE blockers pass (Decision Engine §3).
2. Scale the Scaling campaign +20% every 3-5 days (cap 30%).
3. Testing budget scales proportionally to keep the 80/20 split.
4. Frequency > 3.0 → expand audiences (1% → 2-3% LAL, new seeds, broad, cross-channel
   retargeting) before pushing budget harder.
5. Rollback per Decision Engine if CPA > 1.5× target post-scale.
