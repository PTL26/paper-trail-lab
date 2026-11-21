# Honest Arena — Pre-registration (v1.0, FROZEN)

Paper Trail Lab · **version 1.0 · status: FROZEN · frozen 2026-11-22** (Sunday), before the first scored decision (after the US close on Monday 2026-11-23). Frozen with a signed commit; this file's SHA-256 is timestamped with OpenTimestamps (`HONEST_ARENA_PREREG.md.ots` next to it). Drafts v0.1–v0.6: 2026-11-13. Any later change is an amendment under section 12.

Items that were marked [PILOT] in the drafts are filled in from the pilot week (Monday 2026-11-16 → Friday 2026-11-20, 5 trading days). The pilot may only settle feasibility questions: cost, data availability, run time, output parsing. Pilot returns are never computed or looked at. Pilot runs write only to `arena-data/pilot/`; pilot output is never scored and never decrypted publicly. The pilot report covers run success, timing, cost, retries, failed data sources and the REVIEW count, and no labels or returns.

Changes in v1.0 (2026-11-22, freeze; after the pilot, before any scored data; no pilot labels or returns were seen): the [PILOT] items are filled in (TradingAgents commit, fallback model not needed, smallest detectable alpha) and a pilot results note is added (section 15).

Changes in v0.6 (2026-11-13, before any data): all dates move one week earlier (pilot 16–20 Nov, freeze 22 Nov, first scored decision 23 Nov, scored period 24 Nov 2026 – 22 Feb 2027); the price source is confirmed; the weekly report carries no verdict wording.

Changes in v0.5 (2026-11-13, before any scored data): seeds fixed (D: 20261130, bootstrap: 20270226); the Gemini client's own retries set to 2; the price source for the simulation is named; how section 11 is implemented is stated; the pilot's separation is stated.

Changes in v0.4 (2026-11-13, after the dry run, before any scored data; no returns or labels were seen): the model is fixed as gemini-3.1-flash-lite on the paid tier; a harness-level retry for rate-limit and server errors is added as infrastructure; data-source failures are recorded per stock and day; known data gaps are listed.

Changes in v0.3 (2026-11-13, before any data): the universe is fixed at 10 stocks (enlargement clause removed); the rule for choosing between the two Gemini Flash-Lite models is stated; a failed day is defined.

Changes in v0.2 (2026-11-13, owner budget, before any data): the monthly LLM cost cap in section 10 is lowered from €40 to €15.

Changes from v0: ai-hedge-fund moved out of the first run (its data provider is paid and its licence may not allow public use); model choice now favours Gemini Flash-Lite on cost; rules added for TradingAgents' REVIEW label and its memory file.

---

## 1. Question

Does the default configuration of the most-starred open-source AI trading agent on GitHub (TauricResearch/TradingAgents) produce returns beyond plain market exposure over a 12-week forward paper test?

This tests software as an ordinary user would run it. It is not a recommendation to buy, sell or hold any financial instrument.

## 2. Participants

| ID | Participant | Configuration |
|---|---|---|
| A | TauricResearch/TradingAgents (Apache-2.0) | Default pipeline (4 analysts, 1 debate round, 1 risk round), memory on, version v0.7.1 at commit `c4544913a14ed3df5f1ed7b9e8483270ce20682a` (the version tested in the pilot; kept even if a newer release exists) |
| C | Buy-and-hold | Equal weight in every universe stock, bought on day 1, never rebalanced |
| D | Random agent | Each stock each day draws one of A's five labels with equal probability and is mapped with the same rule as A; seed 20261130 |

C is the primary benchmark. D shows what chance looks like under the same mapping and similar turnover.

**Possible later participant B (virattt/ai-hedge-fund, MIT):** added only if its data provider (Financial Datasets) confirms in writing that publishing results is allowed under an affordable plan. B would get its own amendment, committed before B's first scored day, with its own 60-day window and its own verdict. B's absence does not change A's test.

## 3. Model

- A uses one LLM for every role: **gemini-3.1-flash-lite** (Gemini Developer API, paid tier), with the project's default temperature and settings.
- Why this model (decided 2026-11-13 from a 3-day dry run of both Flash-Lite models, on cost and reliability only, with no returns or labels seen): gemini-3.5-flash-lite's projected cost (about $13–14 per month for 10 stocks) leaves too little headroom under the €15 cap once memory-settlement calls and failed runs are added; gemini-3.1-flash-lite projected about $6 per month. The free tier was rejected because its quota errors would create missing decisions.
- Fallback: Claude Haiku, only if Flash-Lite failed the pilot on reliability (more than 1 failed run in 5 days). Flash-Lite had 0 failed runs in the pilot, so the fallback is not used and no fallback model is fixed.
- The model is chosen in the pilot by cost and reliability only, never by results.
- If the provider retires the model during the test, the closest successor is used and logged as an amendment.

## 4. Universe

- Fixed for the whole test at these 10 stocks: AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, JPM, XOM, UNH.

## 5. Schedule

- **Scored period:** the 60 US trading days from Tuesday 2026-11-24 to Monday 2027-02-22 (NYSE calendar). The first scored decisions are made after the US close on Monday 2026-11-23 and filled at the open on 2026-11-24; C buys at that open.
- **Daily run:** after the US close on GitHub Actions. A receives the date and each ticker and produces one label per ticker for the next session.
- **Commitment:** all decisions are written to the ledger, hashed, and the hash is pushed to the public repo before the next US open. A decision committed after the open is void and counts as "hold".
- **Retries (infrastructure, not an agent change):** an LLM call that fails with a rate-limit (429) or server (5xx) error is sent again by the harness, at most 3 attempts per call in total, after waits of about 30 and 60 seconds. The identical request is repeated; prompts and the agent are unchanged. The Gemini client's own retries are set to 2 (3 attempts per request), so one call sends at most 9 requests. Every retry is logged in the ledger.

## 6. Turning decisions into positions

- A and D start with $100,000 of simulated cash. C invests $100,000 equally on day 1.
- **Long only.** No short positions.
- **Label → target weight per stock:** Buy 10%, Overweight 7.5%, Hold = keep current weight, Underweight 2.5%, Sell 0%.
- **REVIEW** (A could not read its own rating): treated as Hold and recorded. More than 10% REVIEW outputs over the test is reported as a reliability finding.
- **Fills:** at the next session's opening price.
- **Costs:** 10 basis points per side.
- Cash earns nothing.
- **Prices:** daily split-adjusted opening and closing prices from Yahoo Finance (via yfinance, TradingAgents' own default source), fetched when results are computed and never stored or published. Dividends are not credited. The S&P 500 comparison uses the index's daily closes from the same source.

## 7. Agent memory

- A, as published, stores past decisions with their realised returns and reads them back on later runs. Memory stays on, because the test measures A as published.
- The memory file is carried between runs as an encrypted file in the public repo. The decryption key is a repository secret.
- The key is published together with the final report, so anyone can verify the memory history afterwards.

## 8. Metrics

**Primary:** daily alpha of A against C (A − C), with a 95% confidence interval from a block bootstrap by week (10,000 resamples, seed 20270226).

**Secondary (reported, never decides the verdict):**
- Total return.
- Beta to C, and the share of return explained by beta.
- Max drawdown.
- Turnover.
- Alpha against the S&P 500 index.
- LLM cost per day.
- Share of REVIEW labels and failed runs.
- Reliability per stock and day: LLM retries and failed data sources (recorded in the ledger).
- The same comparison for D.

## 9. Verdict rules

- **PASS:** the whole 95% interval for A's alpha vs C is above 0.
- **FAIL:** the whole interval is below 0.
- **INCONCLUSIVE:** anything else.

**Expected precision, stated in advance:** 60 trading days is short. Before the start we publish the smallest alpha this test could detect, computed from the volatility of C, not from A's returns:

- **Data:** C's portfolio (equal weight in the 10 stocks, bought once, never rebalanced) over the 60 trading days ending Friday 2026-11-20, the last session closed before the freeze (61 split-adjusted daily closes, 2026-08-27 → 2026-11-20, Yahoo Finance via yfinance; the 60th prior session, 2026-11-23, had not closed at freeze). Close-to-close daily returns, n = 60.
- **Volatility:** standard deviation of C's daily return σ = 1.19% (0.011885).
- **Method:** the daily alpha's standard deviation is assumed equal to σ, and days are treated as independent. Smallest detectable mean daily alpha = (1.96 + 0.84) × σ / √60, for a two-sided 95% interval with 80% power.
- **Result:** **0.43% per day** (simple sum over 60 days ≈ 26%). For comparison, a mean daily alpha of 1.96 × σ / √60 = 0.30% per day (≈ 18% over 60 days) is what is needed for the interval to just exclude 0 on average (50% power).

The real spread of A − C may be smaller than σ (A holds the same stocks), which would make the test more precise; the weekly block bootstrap may make it less precise. INCONCLUSIVE is a likely outcome and a valid one.

## 10. Stop and failure rules

- **Cost:** if LLM spend exceeds €15 in any calendar month, A is stopped. Its verdict becomes INCONCLUSIVE ("stopped for cost"), and the stop is announced.
- **Data or run outages:**
  - A **failed day** is a day whose decisions were not committed before the next open, or on which A failed to produce a decision for 3 or more of the 10 stocks.
  - A failed day counts as "hold" for A on every stock.
  - On other days, a stock A failed to decide counts as "hold" for that stock; these single-stock failures are reported as a reliability metric and do not count as failed days.
  - More than 5 failed days makes A's verdict INCONCLUSIVE.
  - More than 3 failed days in a row is announced the same week.
- **Harness bugs:**
  - Past committed decisions are never edited.
  - A bug is fixed going forward, listed on the public corrections page, and the result is reported both with and without the affected days.

## 11. Publication

- **Weekly report (Mondays):** the metrics from section 8 so far, plus run reliability and cost. It shows only the numbers and the interval, labelled "interim — no verdict before the end"; no PASS, FAIL or INCONCLUSIVE wording appears before the final report.
- **Trades:** published only with a delay of at least 5 trading days and aggregated. No current positions are shown.
- **Final report:** within 7 days of the last scored day. It contains:
  - the verdict;
  - full ledgers;
  - the memory decryption key;
  - all amendments, with results shown with and without each one.
- Raw licensed prices are never published; only decisions, weights and computed returns.
- **How this is implemented:**
  - Each day the ledger, the decisions file and A's memory are committed to the public repo encrypted (age); only the decisions file's SHA-256 (the file carries a random nonce, so the hash cannot be reversed by trying every label combination) and the ledger's head hash are in plain text.
  - Every Monday before the open, a scheduled job decrypts and publishes in plain text under `arena-data/public/` the decisions files of every session that has at least 5 later trading days closed, with each file checked against its committed SHA-256.
  - In the same run it publishes the weekly report: the section 8 metrics computed through that same cutoff, trades aggregated per participant per week (number of buys and sells, turnover, costs), run reliability and LLM cost. Individual trades and current positions are not published.
  - Only scored data is published; pilot data never is.
- No investment recommendations, price targets or forward-looking statements about any stock.

## 12. Amendments

- Allowed only before data affected by them is seen.
- Each amendment is committed with a reason and a date.
- Results are reported both with and without every amendment.

## 13. Authenticity

- This document is committed with a signed commit.
- Its SHA-256 is timestamped with OpenTimestamps and published on the site and Substack before day 1.
- Each daily decision hash is pushed before the next open.
- Each week's ledger hash is timestamped.

## 14. Known limitations

- Paper fills at the open ignore spread and market impact beyond the fixed cost.
- Ten large stocks and 12 weeks cannot represent every market regime.
- One agent, one model and default settings. The authors might run it differently; this is deliberate, because the test measures what an ordinary user gets.
- LLM outputs vary between runs even with fixed settings.
- The model may have been trained on news about these stocks up to its training cutoff; a forward test after that cutoff limits, but does not remove, this effect.
- In the dry run Reddit refused TradingAgents' requests (HTTP 403) for every stock, so the social analyst ran without Reddit data. One FRED macro series was also missing. A runs with whatever its default data sources return; failed data sources are recorded per stock and day in the ledger as a reliability metric.

## 15. Pilot results (16–20 Nov 2026)

The pilot settled feasibility only. Labels and returns were not looked at; pilot output is never scored or published.

- **Runs:** 50 of 50 succeeded (10 stocks × 5 days); no failed days, no errors.
- **LLM cost:** $0.31–$0.32 per day ($1.59 for the week, $0.032 per stock per day); projected about $6.66 per month for 10 stocks and 21 trading days, under the €15 cap.
- **Retries:** 23 LLM retries (22 rate-limit, 1 server error), all recovered; no call gave up.
- **Failed data sources:** Reddit failed for every stock on every day (50 of 50), as in the dry run (section 14); no other source failed.
- **REVIEW:** 0.
