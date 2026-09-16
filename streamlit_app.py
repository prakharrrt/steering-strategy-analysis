import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Steering Strategy Analysis", layout="wide")

WINDFARMS = {
    "Vauban": {
        "file": "vauban_15mins_production.csv",
        "timestamp_col": "start_time_lb_utc",
        "spot_col": "Spot trade (Planned production) MW",
        "metered_col": "Total metered MW",
        "timestamp_format": None,
        "peak_mw": 42.7,
        "windfarm_name": "Lake",
        "company_name": "Vauban",
        "region": "Unknown (Price Area SE3)",
    },
    "Volkswind": {
        "file": "lalax_volkswind_15mins_production.csv",
        "timestamp_col": "TIMESTAMP",
        "spot_col": "Day Ahead Planned MW",
        "metered_col": "Net Export MW",
        "timestamp_format": "mixed",
        "peak_mw": 24.8,
        "windfarm_name": "Lalax",
        "company_name": "Volkswind",
        "region": "Vörå (Price Area FI)",
    },
}

INTERVAL_HOURS = 0.25


@st.cache_data
def load_data(windfarm: str) -> pd.DataFrame:
    cfg = WINDFARMS[windfarm]
    raw = pd.read_csv(cfg["file"])
    raw = raw.dropna(subset=[cfg["timestamp_col"]])

    df = pd.DataFrame()
    df["timestamp"] = pd.to_datetime(raw[cfg["timestamp_col"]], format=cfg["timestamp_format"])
    df["spot_mw"] = raw[cfg["spot_col"]].astype(float)
    df["metered_mw"] = raw[cfg["metered_col"]].astype(float)

    return df.sort_values("timestamp").reset_index(drop=True)


def find_instances(df: pd.DataFrame) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    instances = []
    in_span = False
    span_start = None
    timestamps = df["timestamp"].tolist()
    flags = df["edge_case"].tolist()
    for ts, flag in zip(timestamps, flags):
        if flag and not in_span:
            span_start = ts
            in_span = True
        elif not flag and in_span:
            instances.append((span_start, ts))
            in_span = False
    if in_span:
        instances.append((span_start, timestamps[-1] + pd.Timedelta(minutes=15)))
    return instances


st.title("Steering Strategy Analysis")
st.caption(
    "Strategy 1 ramps the gridbox to a static level equal to the predicted surplus "
    "(diff = metered − day-ahead), capped at the gridbox's own capacity T, and backs any "
    "shortfall from the day-ahead delivery itself. Strategy 2 (the fallback, dynamic ramp) is "
    "required when that static target exceeds the day-ahead volume — i.e. min(diff, T) > day-ahead "
    "— meaning even redirecting the entire day-ahead commitment isn't enough to hold the target "
    "statically through the interval. Figures below are an *upper bound* on Strategy-2 time — see "
    "the Documentation page for the full method, assumptions, and windfarm details."
)

with st.sidebar:
    st.header("Inputs")
    windfarm = st.selectbox("Windfarm", list(WINDFARMS.keys()))

    df_all = load_data(windfarm)
    min_ts = df_all["timestamp"].min()
    max_ts = df_all["timestamp"].max()

    start_date, end_date = st.date_input(
        "Date range",
        value=(min_ts.date(), max_ts.date()),
        min_value=min_ts.date(),
        max_value=max_ts.date(),
    )

    peak_mw = WINDFARMS[windfarm]["peak_mw"]
    default_t = round(0.10 * peak_mw, 2)
    gridbox_capacity = st.number_input(
        "Gridbox capacity target T (MW)", min_value=0.0, value=default_t, step=0.5,
        help=f"Defaults to 10% of {windfarm}'s peak capacity ({peak_mw} MW).",
    )

meta = WINDFARMS[windfarm]
m1, m2, m3, m4 = st.columns(4)
m1.metric("Windfarm", meta["windfarm_name"])
m2.metric("Company", meta["company_name"])
m3.metric("Region", meta["region"])
m4.metric("Peak capacity", f"{meta['peak_mw']} MW")
st.divider()

start_ts = pd.Timestamp(start_date)
end_ts = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

df = df_all[(df_all["timestamp"] >= start_ts) & (df_all["timestamp"] <= end_ts)].copy()

if df.empty:
    st.warning("No data in the selected range.")
    st.stop()

df["diff"] = df["metered_mw"] - df["spot_mw"]
df["target"] = df["diff"].clip(upper=gridbox_capacity)
df["edge_case"] = (df["diff"] > 0) & (df["target"] > df["spot_mw"])

n_total = len(df)
n_edge = int(df["edge_case"].sum())
overall_pct = 100 * n_edge / n_total
overall_hours = n_edge * INTERVAL_HOURS
instances = find_instances(df)

col1, col2, col3 = st.columns(3)
col1.metric("Strategy 2 required", f"{overall_pct:.2f}%")
col2.metric("Total duration", f"{overall_hours:.1f} h")
col3.metric("Number of instances", f"{len(instances)}")

st.divider()

st.subheader("Daily breakdown")
daily = (
    df.assign(date=df["timestamp"].dt.date)
    .groupby("date")["edge_case"]
    .mean()
    .mul(100)
    .reset_index(name="pct")
)
fig_daily = go.Figure()
fig_daily.add_bar(x=daily["date"], y=daily["pct"], marker_color="#4a3aa7")
fig_daily.update_layout(
    xaxis_title="Date",
    yaxis_title="% of day requiring Strategy 2",
    height=350,
    margin=dict(l=10, r=10, t=10, b=10),
)
st.plotly_chart(fig_daily, use_container_width=True)

st.subheader("Hour-of-day pattern (averaged across selected range)")
hourly = (
    df.assign(hour=df["timestamp"].dt.hour)
    .groupby("hour")["edge_case"]
    .mean()
    .mul(100)
    .reindex(range(24), fill_value=0)
    .reset_index(name="pct")
)
fig_hourly = go.Figure()
fig_hourly.add_bar(x=hourly["hour"], y=hourly["pct"], marker_color="#2a78d6")
fig_hourly.update_layout(
    xaxis_title="Hour of day",
    yaxis_title="% of intervals requiring Strategy 2",
    xaxis=dict(dtick=1),
    height=350,
    margin=dict(l=10, r=10, t=10, b=10),
)
st.plotly_chart(fig_hourly, use_container_width=True)

st.divider()

st.subheader("Drill into a single day")
available_dates = sorted(daily["date"].tolist())
if available_dates:
    pick_date = st.selectbox("Day", available_dates, index=len(available_dates) - 1)
    day_df = df[df["timestamp"].dt.date == pick_date]

    fig_day = go.Figure()
    fig_day.add_trace(
        go.Scatter(
            x=day_df["timestamp"], y=day_df["spot_mw"],
            name="Spot / Day-ahead MW", line=dict(color="#2a78d6", width=1.5),
        )
    )
    fig_day.add_trace(
        go.Scatter(
            x=day_df["timestamp"], y=day_df["metered_mw"],
            name="Metered / Net export MW", line=dict(color="#1baf7a", width=1.5),
        )
    )
    fig_day.add_hline(y=gridbox_capacity, line_dash="dot", line_color="#e34948",
                       annotation_text=f"Gridbox capacity T = {gridbox_capacity} MW")

    for span_start, span_end in find_instances(day_df):
        fig_day.add_vrect(x0=span_start, x1=span_end, fillcolor="#4a3aa7", opacity=0.15, line_width=0)

    day_pct = 100 * day_df["edge_case"].mean() if len(day_df) else 0
    fig_day.update_layout(
        title=f"{pick_date} — Strategy 2 required {day_pct:.1f}% of the day",
        xaxis_title="Time", yaxis_title="MW",
        height=420, margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(fig_day, use_container_width=True)

st.divider()

st.subheader("Instances requiring Strategy 2")
if instances:
    inst_df = pd.DataFrame(instances, columns=["start", "end"])
    inst_df["duration_hours"] = (inst_df["end"] - inst_df["start"]).dt.total_seconds() / 3600
    st.dataframe(inst_df, use_container_width=True, hide_index=True)
else:
    st.info("No instances in the selected range.")
