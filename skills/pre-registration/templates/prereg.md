# Pre-registration — <study name>

**Frozen on:** <YYYY-MM-DD>, before any data is downloaded or results are seen.
**Commit / timestamp:** <fill in after committing>
Later changes go in the Amendments section below; the sections above it are never edited.

## 1. Hypothesis
<One or two sentences that can be wrong. Name the edge: which price relationship or mechanism
produces the profit, and for whom.>

## 2. Window
Events whose <deciding date, e.g. first public announcement> falls between <start> and <end>
(<N> months).

## 3. Universe and discovery
- Sources: <databases, filings, feeds>
- Discovery: <queries, filters, keyword lists>
- Event definition: <how related records are grouped into one event; which date counts>
- Report how many records each source returned and their overlap.

## 4. Eligibility (all must hold)
- **E1** <the condition that creates the edge>
- **E2** <…>
- **E3** <size / affordability, e.g. entry cost ≤ budget>
- **E4** <tradability, e.g. listed venue>
- **E5** <data availability for entry and exit>

## 5. Trade rules (no look-ahead)
- **Entry:** <date rule, price, position size>. **Condition on the edge:** <e.g. enter only if the
  entry price is below the payoff price>.
- **Exit — completed:** <proceeds, cash date>
- **Exit — cancelled / withdrawn:** <sale rule>
- **Exit — partial:** <proration handling>
- **Sensitivity run:** <e.g. later entry date> (information only)

## 6. Costs (constants)
<commission per order, fees, FX, slippage — conservative>

## 7. Gates (decided now; see gate_table.md)
<copy the gate table here>

## 8. Early stop
<cheap check that ends the study early, e.g. fewer than N candidates means the frequency gate
cannot pass>

## 9. Validation
<sample size, seed, how it is drawn, fields checked, accuracy threshold, **how a correct "absent /
not stated" value is verified**, what happens if accuracy fails>

## Amendments
_None._ (Add with templates/amendment.md.)
