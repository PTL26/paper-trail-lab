# Gate table (decided before any data)

| Gate | Measures | Threshold | Computed on |
|---|---|---|---|
| G1 | Frequency | ≥ <N> eligible events (≥ <n> per year) | events passing all eligibility conditions |
| G2 | Typical result | median net result per event ≥ <amount> | resolved eligible events |
| G3 | Tail risk | worst single event ≥ <−amount> | resolved eligible events |

- **PASS** = every gate met.
- **FAIL** = any gate missed.
- **INCONCLUSIVE** = <e.g. more than 20% of eligible events lack the data needed to price them>,
  regardless of the gates.

Reported as information only (they never change the verdict): <mean, hit rate, sensitivity runs,
capital-constrained simulation, post-hoc views>.
