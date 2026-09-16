import argparse
import pandas as pd
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()
parser.add_argument("--start", help="Start time, e.g. 2025-03-05 or '2025-03-05 00:00:00'", default=None)
parser.add_argument("--end", help="End time, e.g. 2025-09-01 or '2025-09-01 00:00:00'", default=None)
parser.add_argument("--gridbox-capacity", type=float, default=None,
                     help="Gridbox full ramp-up target T (MW). Flags intervals where the fallback "
                          "'partial ramp' strategy is required: there is surplus (metered > spot trade) "
                          "but total metered production is still below T, so the deficit (T - surplus) "
                          "cannot be fully covered by pulling the rest from spot trade.")
args = parser.parse_args()

df = pd.read_csv("vauban_15mins_production.csv")
df = df.dropna(subset=["start_time_lb_utc"])
df["start_time_lb_utc"] = pd.to_datetime(df["start_time_lb_utc"])
df["stop_time_lb_utc"] = pd.to_datetime(df["stop_time_lb_utc"])

if args.start:
    df = df[df["start_time_lb_utc"] >= pd.Timestamp(args.start)]
if args.end:
    df = df[df["start_time_lb_utc"] <= pd.Timestamp(args.end)]

fig, ax = plt.subplots(figsize=(14, 6))

if args.gridbox_capacity is not None:
    T = args.gridbox_capacity
    spot = df["Spot trade (Planned production) MW"]
    metered = df["Total metered MW"]
    surplus = metered - spot

    edge_case = (surplus > 0) & (metered < T)

    instances = []
    in_span = False
    span_start = None
    for ts, stop, flag in zip(df["start_time_lb_utc"], df["stop_time_lb_utc"], edge_case):
        if flag and not in_span:
            span_start = ts
            in_span = True
        elif not flag and in_span:
            ax.axvspan(span_start, ts, color="purple", alpha=0.15, zorder=0)
            instances.append((span_start, ts))
            in_span = False
    if in_span:
        end_ts = df["stop_time_lb_utc"].iloc[-1]
        ax.axvspan(span_start, end_ts, color="purple", alpha=0.15, zorder=0)
        instances.append((span_start, end_ts))

    n_intervals = int(edge_case.sum())
    n_total = len(df)
    pct = 100 * n_intervals / n_total if n_total else 0.0
    duration_hours = n_intervals * 0.25

    print(f"Gridbox target T: {T} MW")
    print(f"Partial-ramp strategy required in {n_intervals} / {n_total} intervals ({pct:.2f}%)")
    print(f"Total duration: {duration_hours:.2f} hours, across {len(instances)} instance(s):")
    for start, end in instances:
        dur_h = (end - start).total_seconds() / 3600
        print(f"  {start} -> {end}  ({dur_h:.2f} h)")

ax.plot(df["start_time_lb_utc"], df["Spot trade (Planned production) MW"], label="Spot trade (Planned production) MW", linewidth=1.5, zorder=2)
ax.plot(df["start_time_lb_utc"], df["Total metered MW"], label="Total metered MW", linewidth=1, zorder=1)
ax.plot(df["start_time_lb_utc"], df["Total Fcst MW"], label="Total Fcst MW", linewidth=1.5, linestyle="-.", zorder=3)
ax.set_xlabel("Time")
ax.set_ylabel("MW")

title = "Vauban Production: Forecast vs Spot Trade vs Metered"
if args.gridbox_capacity is not None:
    title += f"\n(Purple: partial-ramp strategy required, T={args.gridbox_capacity} MW, {pct:.1f}% of interval)"
ax.set_title(title)

ax.legend()
fig.autofmt_xdate()
fig.tight_layout()

fig.savefig("vauban_production.png", dpi=150)
plt.show()
