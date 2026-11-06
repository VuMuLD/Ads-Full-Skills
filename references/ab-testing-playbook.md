# A/B Testing & Comparison Campaign Playbook

How to design comparison campaigns / ad groups so every ad gets a fair, fast, readable verdict.
The user's mental model: "thêm camp nhóm để so sánh cho từng quảng cáo" — build a comparison
group and let the numbers pick the winner.

## 1. What to test, in priority order

1. **Offer** (same traffic, new proposition) — biggest effect.
2. **Hook / first 3 seconds / headline** (same body, new opener) — a new hook on a winner
   extends its lifespan 2-4 weeks. Iteration hierarchy: hook > visual treatment > format >
   body copy/CTA.
3. **Creative format** (image vs video vs carousel).
4. **Audience** (same creative, different segment).
5. **Bidding strategy** (Google only, per conversion-volume table).
6. Landing page (split 50/50 per ad set).
Never test two variables at once — the result is unreadable. Prioritize the backlog with
RICE (Reach, Impact, Confidence, Effort, 1-5 each) and log every test's spend + learning —
unlogged tests mean repeated mistakes ("activity trap": testing to feel busy, not to learn).

## 2. Structure per platform

### Meta
- **Testing campaign (CBO, ~20% of total budget)** separate from the Scaling campaign —
  test ads compete only against other tests, so CBO winners never starve them.
- 2-4 test ads per batch inside the Testing campaign; identical audience across the batch.
- Winner graduation (ALL must hold): ≥ 5 conversions, CPA ≤ target, QL/quality rate ≥ 60%
  if measured, running ≥ 14 days, ≥ 1 conversion in last 7 days → duplicate into Scaling
  campaign, pause the test copy.
- Losers: swap per Decision Engine swap rules — every pause paired with a replacement.
- Watch the ad-count ceiling: `(daily budget × 14) / (2 × Target CPA)`.

### Google
- Prefer **Drafts & Experiments** (Campaign Experiments) for budget-split comparisons —
  it splits traffic 50/50 cleanly.
- Ad-group level: duplicate the ad group inside the campaign, one variable changed
  (new RSA set, new match types, new landing page); same budget environment.
- Keep both variants until the verdict rule fires; delete nothing — pause the loser.

## 3. Verdict rules (when is a test "done")

| Rule | Threshold |
|---|---|
| Duration floor | 3-5 days minimum (full days, learning included) |
| Volume floor (per variant) | ≥ 100 clicks, or ≥ 2-3 conversions |
| Winner declared | Variant CPA ≤ 0.8× the other's CPA AND volume floor met — or conversion rate difference ≥ 20% relative with ≥ 100 clicks each |
| Too close | CPAs within ±20% → keep the incumbent (less disruption), note as inconclusive, retest with a bigger lever |
| Stopped early | If one variant spends ≥ 2× Target CPA with 0 conversions while the other converts — stop-loss beats symmetry |

Never declare a winner inside the first 3 days or below the volume floor — that's reading noise.

## 4. Naming & tracking

- `[TestID]-[Variable]-[Variant]` e.g. `T014-Hook-ProblemAgit` / `T014-Hook-SocialProof`.
- Log every test in a simple table: hypothesis ("If X then Y measured by Z"), start date,
  budget, verdict, learning. Unlogged tests = repeated mistakes.
- UTM discipline: `utm_content` distinguishes variants so analytics matches platforms.

## 5. Suggested comparison batches (starting points)

- **Meta, lead-gen:** same audience, 3 hooks: (a) pain-point question, (b) result proof
  (number/screenshot), (c) objection crusher ("không cần...", "chỉ từ...").
- **Meta, ecommerce:** same product, image vs UGC-style video vs review-carousel.
- **Google Search:** exact-match ad group with 2 RSAs: benefit-led vs offer-led headlines.
- **Budget comparison:** incumbent campaign vs +20%-budget twin for 5 days — validates the
  scale ladder cheaply before committing the whole budget.
