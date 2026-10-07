---
name: pre-registration
description: Run a pre-registered test of a trading or research hypothesis — freeze the question, data window, universe, eligibility, trade rules, costs and pass/fail gates BEFORE looking at the data, then handle any later change as an amendment with a reason and both-way reporting, and end with a PASS / FAIL / INCONCLUSIVE verdict. Use when someone describes a backtest idea, a trading strategy test, an event study or any data-driven hypothesis they want to test honestly; when they want to change a rule, threshold, filter or universe after seeing results; or when they ask how to avoid overfitting, p-hacking or "testing until it works".
---

# Pre-registration

A pre-registration is a short, frozen document that says exactly how a test will be run and judged
**before** any result is seen. Its purpose is simple: the verdict cannot be bent toward the answer
you hoped for, because the rules were fixed while you still did not know the answer.

Use the templates in `templates/` and the worked example in `examples/t1_summary.md`.

## When this applies

- Someone has a trading or research idea and wants to test it (backtest, event study, screen,
  signal, strategy, A/B-style comparison on historical data).
- Someone has seen results and wants to change a rule, threshold, filter, universe or window.
- Someone asks whether a result is real, overfit, or "worth trading".

It does not apply to ordinary coding, debugging or data-plumbing questions with no hypothesis to
judge.

## Procedure

### 1. Write the hypothesis (before any data)
One or two sentences that can be wrong. Name the edge: **what price relationship or mechanism
should produce the profit, and for whom.** "Small holders get paid a premium in odd-lot tender
offers" is testable; "tenders are good" is not.

### 2. Freeze the design — fill in `templates/prereg.md`
- **Window:** exact start and end dates, and which date decides membership (e.g. first public
  announcement).
- **Universe and discovery:** data sources, search terms, how candidates are found, how duplicates
  are grouped into one event.
- **Eligibility:** numbered conditions (E1, E2, …) every event must pass, each checkable without
  hindsight.
- **Trade rules:** entry (date, price, size), exit for every outcome (completed, cancelled, partial),
  cash timing. **The entry rule must condition on the price relationship that defines the edge**
  (see Lessons).
- **Costs:** commissions, fees, FX, slippage — conservative defaults, written as constants.
- **Gates:** two to four numeric pass/fail thresholds decided now (`templates/gate_table.md`),
  plus the rule for INCONCLUSIVE (e.g. too much missing data). For long-only strategies, judge
  returns against a benchmark (market-adjusted or excess return), not against zero. A raw profit
  that mostly comes from the market going up is not an edge.
- **Variants:** list every variant you will test (parameters, filters, holding periods) now.
  Report results for all of them, not only the best. Testing many variants and reporting the
  winner is selection, not evidence.
- **Early stop:** a cheap check that can end the study before the expensive part (e.g. too few
  candidates to ever pass a frequency gate).
- **Validation:** how extracted or labelled data will be checked (sample size, seed, accuracy
  threshold) — including how a correct "not stated / absent" value is verified (see Lessons).

### 3. Commit it before touching the data
Save the pre-registration and commit it (or otherwise timestamp it) **before** downloading or
looking at results. Record the commit hash; the final report cites it.

### 4. Run it — and handle every change as an amendment
Once data has been seen, the frozen sections are never edited in place. Any change — new rule,
fixed bug, different data source, new bucket — is an **amendment** (`templates/amendment.md`):
- number, date, what changes, and **why** (one honest sentence);
- whether it was decided before or after seeing the data it affects; if after, label it
  **post-hoc**;
- **both-way reporting:** the result is shown with and without the amendment; if the verdict
  differs, say so in the first line of the report;
- whether it adds or removes events that count toward the gates.

If someone asks to change a rule after seeing results, do not just change it. Write the amendment,
keep the original result, and report both.

Pipeline bug fixes (wrong parser, broken input) are still amendments. They need no post-hoc label
only if they do not change any rule's meaning and were decided before seeing their effect on the
results.

### 5. Give the verdict — fill in `templates/verdict.md`
- **PASS:** every gate met.
- **FAIL:** any gate missed.
- **INCONCLUSIVE:** the pre-registered INCONCLUSIVE condition is met (e.g. too much missing data),
  regardless of the gates.

State the verdict, every gate value against its threshold, and the sensitivities and post-hoc views
clearly separated from the verdict. A clean FAIL is a result. Record the decision it implies.

## Lessons from a real study (see `examples/t1_summary.md`)

1. **Entry rules must condition on the price relationship that defines the edge.** A rule like
   "always buy the day after the announcement" ignores whether the market price is already above the
   payoff; it buys trades that cannot win (e.g. buying above a fixed tender price). Write the
   condition into the trade rule up front — e.g. "enter only if the entry price is below the offer
   price".
2. **Validation scoring must allow verified absence.** If a check requires a quote or citation for
   every field, a correct "not stated" value can never be supported and gets scored as an error.
   Define in advance how absence is verified (e.g. a deterministic search of the source showing no
   such statement, or a human check) instead of counting it as wrong.
3. **A profitable trade is not a strategy.** In the example study, trades taken with a sensible
   entry rule were profitable per event, but there were only a few per year. Include a frequency or
   capacity gate, so a real but rare edge is not mistaken for something worth building.

## Output style

When helping someone, produce the filled-in document, not a lecture: the hypothesis, the frozen
sections, the gate table, and the next concrete step ("commit this before downloading data").
Mark anything the user still has to decide as `TODO:` rather than inventing it.
