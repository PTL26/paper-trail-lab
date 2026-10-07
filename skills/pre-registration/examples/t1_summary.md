# Example: T1 — small-holder events on a €2,000 account (summary)

A real pre-registered study, shortened. All figures are derived results; offer terms come from
public SEC filings; no market price data is reproduced.

## Question
Would a €2,000 brokerage account have made money, repeatedly, on US "small-holder" events —
odd-lot tender offers (holders of fewer than 100 shares bought without proration) and reverse-split
cash-outs at a fixed price — announced between January 2024 and August 2026?

## Frozen before any data
- **Universe:** SEC EDGAR tender-offer, going-private and proxy filings in the window, grouped into
  events.
- **Eligibility:** E1 small-holder priority or fixed-price cash-out · E2 street-name holders treated
  like record holders (cash-outs) · E3 99 shares cost ≤ €1,900 · E4 US-listed · E5 prices available.
- **Trade rule:** buy 99 shares at the close of the first trading day after the announcement;
  tender; collect the final price paid.
- **Costs:** $1 per order, $2 FX per event.
- **Gates:** G1 ≥ 22 eligible events (8 a year) · G2 median net ≥ €25 · G3 worst event ≥ −€150 ·
  INCONCLUSIVE if more than 20% of eligible events lack prices.

## What happened
3,858 filing groups → 365 extracted in detail → 48 with a small-holder clause → 26 listed →
15 eligible after the cost limit.

**Verdict: FAIL on all three gates.** 15 eligible events (5.6 a year) · median net €12.51 · worst
−€524.38 · €2,000 would have ended at about €1,885 (−2.2% a year).

14 amendments were made, each committed before the data it governed and reported both ways. None
changed the verdict.

## Post-hoc view (not pre-registered)
Had the entry rule required the market price to be **below** the offer price at entry, the per-event
results would have been positive (median ≈ €50, worst ≈ −€96) — but only 8 to 12 events qualify in
32 months, so the frequency gate still fails. The verdict does not change.

## Lessons
1. **The entry rule did not condition on the edge.** "Always buy the day after the announcement"
   bought one stock above its fixed tender price ($7.50 per the filing) and lost €524 on a single
   event. The rule should have required entry below the offer price.
2. **The validation rule could not accept a verified "absent".** Field accuracy was checked by
   requiring a verbatim quote for every value. A correct "not stated" value cannot be quoted, so
   4 of 7 errors in the first check and 4 of 5 in the second were correct answers scored as wrong.
   Decide in advance how absence is verified.
