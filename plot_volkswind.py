import argparse
import pandas as pd
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()
parser.add_argument("--start", help="Start time, e.g. 2025-08-09 or '2025-08-09 00:00:00'", default=None)
parser.add_argument("--end", help="End time, e.g. 2026-02-28 or '2026-02-28 23:45:00'", default=None)
parser.add_argument("--gridbox-capacity", type=float, default=None,
                     help="Gridbox full ramp-up target T (MW). Flags intervals where the fallback "
                          "'partial ramp' strategy is required: Imbalance is SURPLUS but Net Export MW "
                          "is still below T, so the deficit (T - Net Export) cannot be fully covered by "
                          "pulling the rest from the day-ahead planned volume.")
args = parser.parse_args()

df = pd.read_csv("lalax_volkswind_15mins_production.csv")
df = df.dropna(subset=["TIMESTAMP"])
df["TIMESTAMP"] = pd.to_datetime(df["TIMESTAMP"], format="mixed")
df["Imbalance "] = df["Imbalance "].str.strip()

if args.start:
    df = df[df["TIMESTAMP"] >= pd.Timestamp(args.start)]
if args.end:
    df = df[df["TIMESTAMP"] <= pd.Timestamp(args.end)]

fig, ax = plt.subplots(figsize=(14, 6))

if args.gridbox_capacity is not None:
    T = args.gridbox_capacity
    net_export = df["Net Export MW"]
    is_surplus = df["Imbalance "] == "SURPLUS"

    edge_case = is_surplus & (net_export < T)

    instances = []
    in_span = False
    span_start = None
    timestamps = df["TIMESTAMP"].tolist()
    for i, (ts, flag) in enumerate(zip(timestamps, edge_case)):
        if flag and not in_span:
            span_start = ts
            in_span = True
        elif not flag and in_span:
            ax.axvspan(span_start, ts, color="purple", alpha=0.15, zorder=0)
            instances.append((span_start, ts))
            in_span = False
    if in_span:
        end_ts = timestamps[-1] + pd.Timedelta(minutes=15)
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

ax.plot(df["TIMESTAMP"], df["Day Ahead Planned MW"], label="Day Ahead Planned MW", linewidth=1.5, zorder=2)
ax.plot(df["TIMESTAMP"], df["Net Export MW"], label="Net Export MW", linewidth=1, zorder=1)
ax.set_xlabel("Time")
ax.set_ylabel("MW")

title = "Volkswind: Day Ahead Planned vs Net Export"
if args.gridbox_capacity is not None:
    title += f"\n(Purple: partial-ramp strategy required, T={args.gridbox_capacity} MW, {pct:.1f}% of interval)"
ax.set_title(title)

ax.legend()
fig.autofmt_xdate()
fig.tight_layout()

fig.savefig("volkswind_production.png", dpi=150)
plt.show()
