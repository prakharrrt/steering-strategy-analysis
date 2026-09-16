import streamlit as st

st.set_page_config(page_title="Documentation — Steering Strategy Analysis", layout="wide")

st.title("Documentation")

st.markdown(
    """
This page explains the windfarms behind the data, the two ramp-up strategies
being compared, and the exact condition used to flag when the fallback
strategy is required.
"""
)

st.header("1. Windfarms & data")

st.markdown(
    """
| | **Vauban** | **Volkswind** |
|---|---|---|
| Windfarm | Lake | Lalax |
| Company | Vauban | Volkswind |
| Region | Unknown (Price Area SE3) | Vörå, Finland (Price Area FI) |
| Peak capacity | 42.7 MW | 24.8 MW |
| Turbines | 10 | 4 |
| Source file | `vauban_15mins_production.csv` | `lalax_volkswind_15mins_production.csv` |
| Interval | 15 minutes | 15 minutes |

Both datasets are 15-minute interval averages. The Volkswind source file was
originally in energy units (`...MWh` per interval); it was converted to power
(`...MW`) by multiplying by 4, since a 15-minute interval is a quarter hour.

**Imbalance column reliability (Volkswind).** The raw `Imbalance` label
(`SURPLUS` / `DEFICIT` / `FALSE`) was checked against
`Net Export MW − Day Ahead Planned MW` across all 20,356 rows and matched
exactly, with zero mismatches. It's derived from *Net Export* vs.
*Day Ahead Planned* — not from *Metered Production* vs. *Bid Capacity*, which
is why a naive check against the latter pair can look inconsistent.

**All-zero rows are kept, not deleted.** Both datasets contain an early
window where every metric reads 0 (commissioning/startup, not corrupted
data). Deleting these rows would shrink the true elapsed-time denominator and
silently inflate every "% of period" statistic — so they stay in, and can be
excluded from a specific view instead via the date range picker.

**Rows where `day_ahead = 0` but production > 0 are also kept.** These are
not an artifact: they're spread across dozens of separate days at meaningful
power levels (Vauban: 11.0% of rows, 81 days, up to 7.6 MW; Volkswind: 3.9% of
rows, 52 days, up to 24 MW — near full capacity). This is consistent with
normal wind-producer behavior of not bidding into day-ahead for some
intervals (e.g. negative prices). These intervals are near-automatic edge
cases in the model below, since there is zero day-ahead buffer to draw on —
making them the highest-risk, most operationally relevant scenario in the
data, not one to discard.
"""
)

st.header("2. The two strategies")

st.markdown(
    """
**Strategy 1 — static ramp.** The gridbox is held at one constant power draw
for the whole 15-minute interval:

```
diff   = metered_mw − day_ahead_mw     # predicted surplus over the interval
target = min(diff, T)                  # capped by the gridbox's own capacity T
```

Any moment production runs below `target`, the shortfall is covered by
redirecting power that was otherwise committed to the day-ahead delivery
(export drops below the committed volume for that moment); any moment
production runs above `target`, the excess is exported. Averaged over the
whole interval this nets out to zero extra imbalance, because `target = diff`
by construction — the gridbox effectively soaks up exactly the average
surplus.

**Strategy 2 — dynamic ramp (the fallback).** Used when Strategy 1 is not
physically achievable: the static `target` would need more backup from the
day-ahead delivery than actually exists. In that case the gridbox instead
tracks production's real-time ups and downs directly, rather than holding one
static level — e.g. running at 1 MW, then 2, then 5, then 3 across the
interval instead of a flat number.
"""
)

st.header("3. Edge-case condition (when Strategy 2 is required)")

st.code("edge_case = (diff > 0) AND (target > day_ahead_mw)", language="text")

st.markdown(
    """
In words: there is a surplus, but even redirecting the **entire** day-ahead
committed volume isn't enough to hold `target` for the whole interval.

**Why `T` still matters.** Even though `target ≤ diff` always, `T` is not
redundant with the `diff > day_ahead` test. A small gridbox capacity can cap
`target` below `day_ahead`, keeping an interval safely in Strategy 1 even when
the raw surplus is huge (example: `diff = 10 MW`, `T = 3 MW`,
`day_ahead = 5 MW` → `target = 3 MW`, which is well under the 5 MW buffer, so
no edge case — whereas testing `diff > day_ahead` alone would wrongly flag it).

**Default `T`.** 10% of the windfarm's peak capacity (Vauban → 4.27 MW,
Volkswind → 2.48 MW), adjustable in the sidebar of the main dashboard.
"""
)

st.header("4. Assumptions & known limitations")

st.markdown(
    """
**The interval-floor assumption.** The data is only available as 15-minute
*averages* — there's no intra-interval production trace. The edge-case test
implicitly assumes the lowest point production reaches within the interval is
roughly the day-ahead accepted volume (a reasonable proxy, since day-ahead
bids are usually conservative forecasts), not something lower. If real
production occasionally dips below the day-ahead floor intra-interval,
Strategy 1 could still fail on some intervals this method marks as safe.
Validating this properly would need higher-resolution (e.g. 1-minute)
production data.

**The edge-case flag is an upper bound on Strategy-2 *duration*, not an exact
measurement.** When an interval is flagged, it means the static target would
have broken down *at some point* in that 15 minutes — not that the entire
interval needed dynamic tracking. In reality, only the sub-portion where
instantaneous production dipped too low would have required Strategy 2; the
rest of that same interval may have had enough production to hold the static
level fine. Because the dashboard counts the **full interval** toward the
Strategy-2 percentage/duration whenever it's flagged, those figures should be
read as **"% of intervals where Strategy 2 was triggered at some point,"**
not as a precise measurement of total time spent running dynamically — the
true dynamic-control time is likely somewhat less than what's reported.
"""
)
