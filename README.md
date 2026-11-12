# Paper Trail Lab

Independent testing of AI trading tools — including the results that fail.

Every experiment here is pre-registered: the hypothesis, the data window, the eligibility rules,
the trade rules, the costs and the pass/fail gates are written down and committed **before** any
data is looked at. Changes after that are amendments with a stated reason, and results are reported
both with and without them. A clean FAIL is a result worth publishing. Nothing here is investment
advice.

Site: https://ptl26.github.io/paper-trail-lab/

## What is here

- `site/` — the public site, including the Backtest Lie Detector (`site/lie-detector/`).
- `skills/` — free Claude skills, starting with `pre-registration`.
- `t1-explorer/` — an interactive explorer of the first study (T1: small-holder tender offers).
- `docs/` — write-ups.
- `tools/` — the privacy guard and sanitiser used for every commit.

## Install the pre-registration skill (Claude Code)

```
/plugin marketplace add PTL26/paper-trail-lab
/plugin install pre-registration@paper-trail-lab
```

## Coming next

**Honest Arena** — a pre-registered forward test of popular open-source AI trading agents.

## Licences

Code: MIT (`LICENSE`). Text and data: CC BY 4.0 (`LICENSE-CONTENT`). Results are derived from public
SEC EDGAR filings; no third-party market price data is republished.
