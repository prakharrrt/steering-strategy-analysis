# Steering Strategy Analysis

Determines how often a colocated gridbox (data center) can be ramped up using a
**static** power draw for a full 15-min interval (Strategy 1), versus how often
it needs a **dynamic**, up/down-tracking draw instead (Strategy 2), across two
windfarms: Vauban (Lake, SE3) and Volkswind (Lalax, FI).

## Data

| Windfarm | File | Notes |
|---|---|---|
| Vauban | `vauban_15mins_production.csv` | Native units already MW. |
| Volkswind | `input_data_clean_mw.csv` | Converted from the raw `input_data_clean.csv`: all `...MWh` columns (15-min energy) were multiplied by 4 to get `...MW` (power), since each interval is 15 minutes. |

Both are 15-minute interval data. Rows where every metric is 0 (an initial
commissioning window, not missing/corrupt data) are kept, not deleted —
removing them would shrink the true elapsed-time denominator and silently
inflate every "% of period" statistic.

The `Imbalance` column in the Volkswind data (`SURPLUS` / `DEFICIT` / `FALSE`)
was checked against `Net Export MWh − Day Ahead Planned MWh` across all 20,356
rows and matched with **zero mismatches** — it's reliable, just derived from
`Net Export` vs `Day Ahead Planned`, not `Metered Production` vs `Bid Capacity`.

## The two strategies

**Strategy 1 (static ramp).** The gridbox is set to consume a constant power
level for the whole interval:

```
diff   = metered_mw − day_ahead_mw        # predicted surplus over the interval
target = min(diff, T)                     # capped by the gridbox's own capacity T
```

Any shortfall between real-time production and `target` is covered by
redirecting power that was otherwise committed to the day-ahead delivery; any
excess production above `target` is exported. Averaged over the interval this
nets out to zero extra imbalance, since `target = diff` by construction.

**Strategy 2 (dynamic ramp, the fallback).** Used when Strategy 1 isn't
physically achievable — the static `target` would need more backup than the
day-ahead commitment can supply, so the gridbox instead tracks production's
ups and downs directly rather than holding one static level.

### Edge-case condition (when Strategy 2 is required)

```
edge_case = (diff > 0) AND (target > day_ahead_mw)
```

i.e. there's a surplus, but even redirecting the *entire* day-ahead volume
isn't enough to hold `target` for the whole interval.

- `T` (gridbox capacity) still matters even though `target ≤ diff` always —
  a small `T` can cap `target` below `day_ahead`, keeping an interval safely
  in Strategy 1 even when the raw surplus is huge. Dropping `T` and testing
  `diff > day_ahead` directly gives false positives in that case.
- Default `T` = 10% of the windfarm's peak capacity (Vauban 42.7 MW → 4.27 MW;
  Volkswind 24.8 MW → 2.48 MW), adjustable in the app.

### Key assumption (and its limitation)

The data is only available as 15-min **averages** — there's no intra-interval
production trace. The edge-case test implicitly assumes the *lowest* point
production reaches within the interval is roughly the day-ahead accepted
volume (a reasonable proxy, since day-ahead bids are usually conservative
forecasts) rather than something lower. If real production occasionally dips
below the day-ahead floor intra-interval, Strategy 1 could still fail on some
intervals this method marks as safe; conversely the method may over-flag some
intervals where production never actually got that low. This is a worst-case
heuristic, not an intra-interval simulation — validating it would need
higher-resolution (e.g. 1-min) production data.

### Rows with `day_ahead = 0` and production > 0

These are **kept in the analysis, not filtered out**. They aren't a data
artifact — they're spread across dozens of separate days at meaningful power
levels (Vauban: 11.0% of rows, 81 days, up to 7.6 MW; Volkswind: 3.9% of rows,
52 days, up to 24 MW near full capacity), consistent with normal wind-producer
behavior of not bidding into day-ahead for some intervals (e.g. negative
prices). Under the model these are near-automatic edge cases, since there's
zero day-ahead buffer to draw on — which makes them the highest-risk, most
operationally relevant scenario in the dataset, not one to discard.

## App

`streamlit_app.py` — pick a windfarm, date range, and `T`; see overall %
duration in Strategy 2, a daily breakdown, an hour-of-day pattern (diurnal
tendency, averaged across the range), a single-day drilldown chart, and a
table of every contiguous Strategy-2 instance with start/end/duration.

```
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```
