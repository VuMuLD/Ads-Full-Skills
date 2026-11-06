# Google Ads Platform Guide

Read when working on Google-specific strategy, structure, or bidding.

## Philosophy: intent first

Google Ads captures existing demand. Build bottom-up by intent and prove unit economics at
each rung before expanding:

```
Brand → High-intent (solution/product terms) → Competitor → Problem-aware → Demand gen (PMax/Display/Video)
```

## Account structure

- Split campaigns by intent tier, one theme per ad group (themed ad groups beat SKAGs):
  5-15 keywords sharing one intent, 2-3 RSAs per ad group.
- **Consolidation rule:** a campaign that cannot reach ~15-30 conversions/month starves
  Smart Bidding — merge it. Fragmentation is the silent account killer.
- Naming convention: `IntentTier - Theme - MatchType - Bidding` (e.g. `HI - CRM Software - Phrase - tCPA`).
- Defaults to fix on every new campaign: Search Partners OFF, Display Network OFF,
  location = presence (not interest), language explicit (it targets UI language, not query language).
- Landing page by intent tier: brand → homepage; high-intent → dedicated LP; informational →
  content/comparison page; competitor → comparison page.

## Keywords & match types

- Start **Phrase** for control; move winners to **Exact**; add **Broad** only with Smart
  Bidding + 30+ conv/month per campaign.
- Research from: search terms report, Search Console queries, competitor landing pages,
  sales call language.
- **Seed negative lists** (apply as a shared list to all non-brand campaigns):
  universal junk (free, cheap, jobs, salary, hiring, career, intern, student, course,
  tutorial, training, certification, pdf, reddit, wiki, crack, torrent),
  research-not-buying (what is, how to, examples, meaning),
  and **your own brand as a negative in non-brand campaigns** (forces clean data routing).
- Negative match-type gotcha: negative BROAD blocks only when ALL words appear in the query —
  `"free trial"` as a negative broad does NOT block "free" alone. Use negative phrase for that.
  Don't over-negative low-volume accounts: cut the clearly-wrong, not the merely-uncertain.
- Self-competition: never let the same keyword exist in multiple ad groups/campaigns at the
  same match type — you bid against yourself and split learning data. Route with negatives.
- Zero-impression keywords: a keyword with 0 impressions has a DELIVERY problem (disapproval,
  bid, budget), not a performance problem — diagnose differently.

## Bidding (by conversion volume)

| Conversions/month | Strategy |
|---|---|
| 0-15 | Manual CPC or Maximize Conversions (no target) |
| 15-30 | Maximize Conversions |
| 30+ stable | Target CPA — start at/slightly above trailing-30d actual CPA |
| Real value data flowing | Target ROAS |

- Move targets ±10-15%, wait 1-2 weeks between moves. Expect 1-2 week learning after any
  major change — do not judge or panic-edit inside it.
- The B2B/quality trap: Smart Bidding optimizes whatever you call a "conversion". Feed
  qualified-conversion signals (offline import / values) or keep human QA on lead quality.
- Budget-capped + converting → raise budget; it often *lowers* CPA. Check Search lost IS (budget).

## Search terms & negatives (weekly ritual)

1. Pull search terms ≥ 5 clicks, 0 conv → waste → phrase negatives.
2. Terms converting repeatedly → add as exact keywords.
3. Check match-type drift (Phrase/Broad expanding into junk).
4. Keep an experiment log: hypothesis → result → learning.

## Quality Score & RSAs

- QS ≤ 4 = ad relevance / expected CTR / landing page problem. Fix before raising bids —
  higher QS directly lowers CPC.
- RSAs: 8-12 genuinely different headlines (Google max 15) covering value prop / outcome /
  proof / differentiator / CTA / keyword theme, 3-4 descriptions. Pin at most ONE critical
  headline to position 1 — over-pinning tanks Ad Strength. "Poor" Ad Strength = too few or
  too-similar assets. Message-match the landing page (same promise, same words).
- Ad strength is directional — never sacrifice relevance for "Excellent" rating.
- **Brand-pause test:** if you're the only bidder on your brand and organic owns the SERP,
  test pausing brand and judge on TOTAL brand conversions (paid + organic), not paid alone.
- Account-level negative lists exist separately from campaign negatives — keep junk there.
- Enhanced conversions + consent mode: verify they're on in the measurement audit; they
  materially change what Smart Bidding can see.

## Landing page checklist (beyond message match)

One job per page (one offer, one primary CTA, kill nav-away links) · mobile speed test
(> 3s ≈ 20% of clicks lost) · proof above the fold · form length = intent gate (short forms
buy volume, long forms buy quality — match to funnel stage). Pull the page exactly as the
ad audience sees it: mobile, fresh session, from the paid click.

## Campaign type selection

| Type | When |
|---|---|
| Search | Always — the foundation; intent capture |
| Performance Max | After Search proves unit economics; guardrails: brand exclusions, audience signals, exclude junk via account-level negatives |
| Display | Remarketing first, prospecting second; separate campaign, never inside Search |
| Shopping | Product catalogs (ecommerce) |
| Video | Awareness/remarketing after core is profitable |

## Benchmarks (B2B-ish sanity ranges — sanity checks only, never targets)

| Metric | Brand | Non-brand high-intent | Competitor |
|---|---|---|---|
| CTR | 8-20% | 2-6% | 1.5-4% |
| CVR (click→lead) | 15-40% | 3-10% | 2-6% |
| CPL | low | $80-400+ (category-dependent) | higher, CPCs often above non-brand |

Anchor to the account's own 30-day baseline and trend, not to industry tables.

## Weekly scorecard (the 8 numbers that matter)

Spend · Conversions · CPA · conv value/ROAS · Search Impression Share · Search lost IS (budget
vs rank) · QS distribution · top wasted search terms. Healthy and trending right = account
healthy; everything else is detail.
