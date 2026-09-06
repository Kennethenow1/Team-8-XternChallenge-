#!/usr/bin/env python3
"""Build the PIT withdrawal EDA notebook (source of truth for cell text)."""

from __future__ import annotations

import nbformat as nbf
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "notebooks" / "eda_pit_withdrawal.ipynb"


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(text.strip())


def build() -> nbf.NotebookNode:
    cells: list[nbf.NotebookNode] = []

    cells.append(
        md(
            """
# Point-in-time withdrawal dataset — exploratory analysis

Read-only EDA over existing Gold / Silver PIT tables. **No model training. No writes under `data/gold/`.**

| Artifact | Path |
|----------|------|
| Enriched panel | `data/gold/withdrawal_panel_enriched.parquet` |
| Survival intervals | `data/gold/survival_training/survival_training.parquet` |
| Current MISO scoring | `data/gold/current_miso_scoring_enriched.parquet` |
| Snapshots / outcomes | `data/silver/snapshots`, `data/silver/outcomes` |
| Figures | `reports/eda/figures/` |
| HTML export | `reports/eda/eda_report.html` |

Re-run: `python scripts/run_eda_report.py`
"""
        )
    )

    cells.append(
        code(
            """
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
from IPython.display import HTML, display
from lifelines import KaplanMeierFitter
from scipy import stats

warnings.filterwarnings("ignore", category=FutureWarning)

REPO = Path.cwd()
if not (REPO / "data" / "gold").exists():
    REPO = Path.cwd().parent
sys.path.insert(0, str(REPO))

from src.eda.utils import (
    FIG_DIR,
    LOG1P_PLOT_COLS,
    MIN_RATE_N,
    REPORTS_EDA_DIR,
    ensure_eda_dirs,
    log1p_plot_series,
    rate_table,
    save_mpl,
    save_plotly,
    year_of,
)

ensure_eda_dirs()
sns.set_theme(style="whitegrid", context="notebook")
plt.rcParams["figure.figsize"] = (9, 4.5)
pd.set_option("display.max_columns", 40)
pd.set_option("display.width", 120)

import plotly.io as pio

# Embed JS-friendly HTML so nbconvert HTML export keeps interactive charts
pio.renderers.default = "notebook_connected"


def show_plotly(fig: go.Figure, stem: str | None = None):
    # Save figure artifacts and embed HTML for notebook + nbconvert.
    if stem:
        save_plotly(fig, stem)
    display(HTML(fig.to_html(full_html=False, include_plotlyjs="cdn")))


print("REPO:", REPO)
print("Figures →", FIG_DIR)
print(f"Rate charts suppress groups with n < {MIN_RATE_N}; denominators shown on labels.")
"""
        )
    )

    cells.append(
        code(
            """
# Load existing datasets (read-only)
panel = pd.read_parquet(REPO / "data/gold/withdrawal_panel_enriched.parquet")
annual = pd.read_parquet(REPO / "data/gold/annual_withdrawal_training/annual_withdrawal_training.parquet")
surv = pd.read_parquet(REPO / "data/gold/survival_training/survival_training.parquet")
score = pd.read_parquet(REPO / "data/gold/current_miso_scoring_enriched.parquet")
snaps = pd.read_parquet(REPO / "data/silver/snapshots/project_snapshots.parquet")
outcomes = pd.read_parquet(REPO / "data/silver/outcomes/project_outcomes.parquet")
geo = pd.read_parquet(REPO / "data/silver/crosswalks/geo_crosswalk.parquet")
split_manifest = json.loads((REPO / "data/gold/split_manifest.json").read_text())
cov_path = REPO / "data/quality_reports/enrichment/enrichment_coverage_by_feature.csv"
coverage = pd.read_csv(cov_path) if cov_path.exists() else None
leak_path = REPO / "data/quality_reports/enrichment/leakage_audit_enrichment.csv"
leak_audit = pd.read_csv(leak_path) if leak_path.exists() else None

for df in (panel, annual, surv, score, snaps, outcomes):
    for c in df.columns:
        if "date" in c.lower():
            df[c] = pd.to_datetime(df[c], errors="coerce")

panel["obs_year"] = year_of(panel["observation_date"])
snaps["obs_year"] = year_of(snaps["observation_date"])
train = panel.loc[panel["split"] == "train"].copy()
train_lab = train.loc[train["complete_followup"] == True].copy()  # noqa: E712

print("panel", panel.shape, "train", train.shape, "train+followup", train_lab.shape)
print("score", score.shape, "snaps", snaps.shape, "outcomes", outcomes.shape, "surv", surv.shape)
"""
        )
    )

    # ---- 1 ----
    cells.append(md("## 1. Dataset counts and status composition"))
    cells.append(
        code(
            """
counts = pd.DataFrame(
    {
        "dataset": [
            "withdrawal_panel_enriched",
            "annual_withdrawal_training",
            "survival_training",
            "current_miso_scoring_enriched",
            "project_snapshots",
            "project_outcomes",
        ],
        "n_rows": [len(panel), len(annual), len(surv), len(score), len(snaps), len(outcomes)],
        "n_projects": [
            panel["project_key"].nunique(),
            annual["project_key"].nunique(),
            surv["project_key"].nunique(),
            score["project_key"].nunique(),
            snaps["project_key"].nunique(),
            outcomes["project_key"].nunique(),
        ],
    }
)
display(counts)

split_counts = (
    panel.groupby(["split", "obs_year"], dropna=False)
    .size()
    .rename("n")
    .reset_index()
)
fig = px.bar(
    split_counts,
    x="obs_year",
    y="n",
    color="split",
    barmode="stack",
    title="Panel rows by observation year and split",
)
fig.update_layout(xaxis_title="Observation year", yaxis_title="Rows")
show_plotly(fig, "01_panel_counts_by_year_split")

status_year = (
    snaps.groupby(["obs_year", "status_clean"], dropna=False)
    .size()
    .rename("n")
    .reset_index()
)
fig = px.area(
    status_year,
    x="obs_year",
    y="n",
    color="status_clean",
    title="Snapshot status composition over time",
)
show_plotly(fig, "01_snapshot_status_composition")

outcome_counts = outcomes["outcome_type"].value_counts(dropna=False).rename_axis("outcome_type").reset_index(name="n")
fig, ax = plt.subplots()
sns.barplot(data=outcome_counts, x="outcome_type", y="n", ax=ax, color="#3d5a80")
ax.set_title("Project outcomes (unique projects)")
ax.tick_params(axis="x", rotation=30)
save_mpl(fig, "01_outcome_type_counts")
"""
        )
    )

    # ---- 2 ----
    cells.append(md("## 2. Queue entries, withdrawals and completions over time"))
    cells.append(
        code(
            """
# Entry ≈ first snapshot observation; events from outcomes (calendar year of outcome_date)
first_obs = (
    snaps.sort_values("observation_date")
    .groupby("project_key", as_index=False)
    .agg(entry_date=("observation_date", "min"), queue_date=("queue_date", "min"))
)
first_obs["entry_year"] = year_of(first_obs["entry_date"].fillna(first_obs["queue_date"]))

entries = first_obs["entry_year"].value_counts().sort_index().rename("entries")
wd = outcomes.loc[outcomes["outcome_type"] == "withdrawn"].copy()
wd["event_year"] = year_of(wd["outcome_date"])
withdrawals = wd["event_year"].value_counts().sort_index().rename("withdrawals")
comp = outcomes.loc[outcomes["outcome_type"].isin(["operational", "completed"])].copy()
comp["event_year"] = year_of(comp["outcome_date"])
completions = comp["event_year"].value_counts().sort_index().rename("completions")

timeline = pd.concat([entries, withdrawals, completions], axis=1).fillna(0).astype(int)
timeline.index.name = "year"
timeline = timeline.reset_index()
display(timeline)

fig = go.Figure()
for col, color in [
    ("entries", "#2a9d8f"),
    ("withdrawals", "#e76f51"),
    ("completions", "#264653"),
]:
    fig.add_trace(go.Scatter(x=timeline["year"], y=timeline[col], mode="lines+markers", name=col, line=dict(color=color)))
fig.update_layout(title="Queue entries, withdrawals, and completions by year", xaxis_title="Year", yaxis_title="Count")
show_plotly(fig, "02_entries_withdrawals_completions_timeline")

# Active stock from snapshots
active_stock = (
    snaps.loc[snaps["status_clean"] == "active"]
    .groupby("obs_year")
    .size()
    .rename("active_snapshots")
    .reset_index()
)
fig = px.bar(active_stock, x="obs_year", y="active_snapshots", title="Active-status snapshots by year")
show_plotly(fig, "02_active_snapshot_stock")
"""
        )
    )

    # ---- 3 ----
    cells.append(md("## 3. Capacity by year, status and technology"))
    cells.append(
        code(
            """
cap = snaps.assign(mw=pd.to_numeric(snaps["capacity_mw"], errors="coerce")).dropna(subset=["mw"])
cap_year_status = cap.groupby(["obs_year", "status_clean"], as_index=False)["mw"].sum()
fig = px.bar(
    cap_year_status,
    x="obs_year",
    y="mw",
    color="status_clean",
    title="Total capacity (MW) in snapshots by year and status",
)
fig.update_layout(yaxis_title="MW")
show_plotly(fig, "03_capacity_by_year_status")

cap_year_tech = (
    panel.groupby(["obs_year", "technology_primary"], as_index=False)["capacity_mw"]
    .sum()
)
fig = px.bar(
    cap_year_tech,
    x="obs_year",
    y="capacity_mw",
    color="technology_primary",
    title="Panel capacity (MW) by year and technology (active annual rows)",
)
show_plotly(fig, "03_capacity_by_year_technology")

# Distribution: log1p for plotting only
plot_df = panel[["obs_year", "technology_primary", "capacity_mw"]].copy()
plot_df["log1p_capacity_mw_plot"] = log1p_plot_series(plot_df["capacity_mw"])
fig, ax = plt.subplots(figsize=(10, 4.5))
sns.boxplot(data=plot_df, x="obs_year", y="log1p_capacity_mw_plot", ax=ax, color="#8ecae6")
ax.set_title("Capacity distribution by year (log1p for plot only)")
ax.set_ylabel("log1p(capacity_mw)")
save_mpl(fig, "03_capacity_log1p_boxplot_by_year")
"""
        )
    )

    # ---- 4 ----
    cells.append(
        md(
            """
## 4. Withdrawal outcomes (training data only)

Uses `split == 'train'` with `complete_followup` for supervised rates. Groups with **n < 30** are suppressed on rate plots; labels always show **n**.
"""
        )
    )
    cells.append(
        code(
            """
print("Train withdrawal rate (complete follow-up):",
      f"{train_lab['withdraw_next_12m'].mean():.3f} (n={len(train_lab)})")

for group_col, stem in [
    ("technology_primary", "04_withdraw_rate_by_technology"),
    ("state_code", "04_withdraw_rate_by_state"),
    ("study_phase", "04_withdraw_rate_by_study_phase"),
]:
    rt = rate_table(train_lab, group_col, "withdraw_next_12m", min_n=MIN_RATE_N)
    display(rt.head(20))
    plot_rt = rt.loc[~rt["suppressed"]].copy()
    if plot_rt.empty:
        print(f"No groups with n>={MIN_RATE_N} for {group_col}")
        continue
    fig, ax = plt.subplots(figsize=(10, max(3.5, 0.28 * len(plot_rt))))
    sns.barplot(data=plot_rt, y="label", x="rate_plot", ax=ax, color="#e76f51")
    ax.set_xlim(0, max(0.05, plot_rt["rate_plot"].max() * 1.15))
    ax.set_xlabel(f"P(withdraw_next_12m)  |  suppressed if n < {MIN_RATE_N}")
    ax.set_title(f"Train withdrawal rate by {group_col} (denominator on label)")
    save_mpl(fig, stem)

# Capacity vs outcome (log1p plot only)
tmp = train_lab.copy()
tmp["log1p_mw_plot"] = log1p_plot_series(tmp["capacity_mw"])
tmp["outcome"] = tmp["withdraw_next_12m"].map({0: "remain/other", 1: "withdraw_12m"})
fig, ax = plt.subplots()
sns.violinplot(data=tmp, x="outcome", y="log1p_mw_plot", ax=ax, inner="quartile", color="#90be6d")
ax.set_title("Train: capacity (log1p plot) by 12m withdrawal label")
save_mpl(fig, "04_capacity_vs_withdraw_label")
"""
        )
    )

    # ---- 5 ----
    cells.append(
        md(
            """
## 5. Kaplan–Meier curves

Project-level time-to-withdrawal from first observation (or queue date) to outcome date.
Event = withdrawn; operational/completed/active_censored are right-censored. Fit with **lifelines**.
"""
        )
    )
    cells.append(
        code(
            """
entry = first_obs.merge(
    snaps.sort_values("observation_date")
    .groupby("project_key", as_index=False)
    .agg(technology_primary=("technology_primary", "first"), state_code=("state_code", "first")),
    on="project_key",
    how="left",
)
km_base = entry.merge(outcomes, on="project_key", how="left")
km_base["start"] = km_base["queue_date"].fillna(km_base["entry_date"])
km_base["stop"] = km_base["outcome_date"].fillna(snaps["observation_date"].max())
# For still-active / unknown without outcome_date, censor at last snapshot
last_snap = snaps.groupby("project_key")["observation_date"].max().rename("last_obs")
km_base = km_base.merge(last_snap, on="project_key", how="left")
km_base["stop"] = np.where(
    km_base["outcome_type"].isin(["withdrawn", "operational", "completed"]) & km_base["outcome_date"].notna(),
    km_base["outcome_date"],
    km_base["last_obs"],
)
km_base["duration_months"] = (km_base["stop"] - km_base["start"]).dt.days / 30.4375
km_base["event"] = (km_base["outcome_type"] == "withdrawn").astype(int)
km_base = km_base.loc[km_base["duration_months"].notna() & (km_base["duration_months"] >= 0)].copy()
km_base["duration_months"] = km_base["duration_months"].clip(lower=0.01)

print(km_base["event"].value_counts())
print("median duration months", km_base["duration_months"].median())

fig, ax = plt.subplots(figsize=(9, 5))
kmf = KaplanMeierFitter()
kmf.fit(km_base["duration_months"], event_observed=km_base["event"], label="All projects")
kmf.plot_survival_function(ax=ax, ci_show=True)
ax.set_title("Kaplan–Meier: time in queue until withdrawal")
ax.set_xlabel("Months since queue/entry")
ax.set_ylabel("P(still not withdrawn)")
save_mpl(fig, "05_km_overall")

# Stratify by technology (only strata with enough events/n)
fig, ax = plt.subplots(figsize=(9, 5))
for tech, g in km_base.groupby("technology_primary"):
    if len(g) < MIN_RATE_N or g["event"].sum() < 5:
        continue
    kmf = KaplanMeierFitter()
    kmf.fit(g["duration_months"], event_observed=g["event"], label=f"{tech} (n={len(g)})")
    kmf.plot_survival_function(ax=ax, ci_show=False)
ax.set_title(f"KM by technology (n ≥ {MIN_RATE_N})")
ax.set_xlabel("Months since queue/entry")
ax.set_ylabel("P(still not withdrawn)")
ax.legend(fontsize=8)
save_mpl(fig, "05_km_by_technology")

# Also: annual-interval withdrawal hazard proxy from survival_training (train years only)
surv_tr = surv.loc[year_of(surv["start_date"]).isin(split_manifest["train_years"])].copy()
surv_tr["dur_m"] = (surv_tr["stop_date"] - surv_tr["start_date"]).dt.days / 30.4375
surv_tr = surv_tr.loc[surv_tr["dur_m"] > 0]
fig, ax = plt.subplots(figsize=(9, 5))
kmf = KaplanMeierFitter()
kmf.fit(surv_tr["dur_m"], event_observed=surv_tr["withdrawal_event"], label="Train-year intervals")
kmf.plot_survival_function(ax=ax)
ax.set_title("KM on survival_training intervals (train years; interval length ≈ follow-up)")
ax.set_xlabel("Interval length (months)")
save_mpl(fig, "05_km_survival_training_intervals_train")
"""
        )
    )

    # ---- 6 ----
    cells.append(md("## 6. DPP phase, delay, restudy and upgrade-cost distributions"))
    cells.append(
        code(
            """
dpp_cols = [
    "latest_study_phase",
    "study_phase",
    "study_delay_days",
    "restudy_count",
    "network_upgrade_cost",
    "upgrade_cost_per_mw",
    "dpp_event_count_to_date",
]
present = [c for c in dpp_cols if c in panel.columns]
print("DPP-related non-null rates (panel):")
display(panel[present].notna().mean().rename("nonnull_rate").to_frame())

phase = panel["latest_study_phase"].fillna("(missing)").value_counts().rename_axis("latest_study_phase").reset_index(name="n")
fig, ax = plt.subplots()
sns.barplot(data=phase, x="latest_study_phase", y="n", ax=ax, color="#457b9d")
ax.set_title("Latest DPP study phase (panel)")
ax.tick_params(axis="x", rotation=30)
save_mpl(fig, "06_dpp_latest_study_phase")

fig, axes = plt.subplots(1, 2, figsize=(11, 4))
sns.histplot(panel["study_delay_days"].dropna(), bins=30, ax=axes[0], color="#1d3557")
axes[0].set_title("study_delay_days")
sns.histplot(panel["restudy_count"].dropna(), bins=10, ax=axes[1], color="#1d3557", discrete=True)
axes[1].set_title("restudy_count")
save_mpl(fig, "06_delay_restudy_hist")

# Costs: log1p for plot only
cost_plot = panel[["network_upgrade_cost", "upgrade_cost_per_mw"]].copy()
for c in cost_plot.columns:
    cost_plot[f"log1p_{c}"] = log1p_plot_series(cost_plot[c])
fig, axes = plt.subplots(1, 2, figsize=(11, 4))
sns.histplot(cost_plot["log1p_network_upgrade_cost"].dropna(), bins=30, ax=axes[0], color="#e9c46a")
axes[0].set_title("log1p(network_upgrade_cost) — plot only")
sns.histplot(cost_plot["log1p_upgrade_cost_per_mw"].dropna(), bins=30, ax=axes[1], color="#e9c46a")
axes[1].set_title("log1p(upgrade_cost_per_mw) — plot only")
save_mpl(fig, "06_upgrade_cost_log1p_hist")

# Train withdrawal rate by DPP phase
rt = rate_table(
    train_lab.assign(latest_study_phase=train_lab["latest_study_phase"].fillna("(missing)")),
    "latest_study_phase",
    "withdraw_next_12m",
)
display(rt)
plot_rt = rt.loc[~rt["suppressed"]]
if not plot_rt.empty:
    fig, ax = plt.subplots()
    sns.barplot(data=plot_rt, x="label", y="rate_plot", ax=ax, color="#e76f51")
    ax.set_title(f"Train withdraw rate by DPP phase (n on label; hide n<{MIN_RATE_N})")
    ax.tick_params(axis="x", rotation=25)
    save_mpl(fig, "06_withdraw_rate_by_dpp_phase")
"""
        )
    )

    # ---- 7 ----
    cells.append(md("## 7. Enrichment-coverage heatmap by year"))
    cells.append(
        code(
            """
# Prefer quality-report coverage table; else compute non-null rates from panel
enrich_features = [
    "fema_risk_score",
    "population",
    "energy_community_eligible",
    "storm_events_12m",
    "storm_property_damage_12m",
    "interest_rate_at_observation",
    "miso_mean_demand_mw",
    "developer_prior_withdrawal_rate",
    "network_upgrade_cost",
    "study_delay_days",
    "restudy_count",
    "distance_to_transmission_km",
    "nearby_mtep_upgrade_count",
    "news_count_90d",
    "county_fips",
]
if coverage is not None and not coverage.empty:
    cov = coverage.copy()
    # keep high-signal features if present
    keep = [f for f in enrich_features if f in set(cov["feature"])]
    if keep:
        cov = cov.loc[cov["feature"].isin(keep)]
    heat = cov.pivot_table(index="feature", columns="year", values="coverage_pct", aggfunc="mean")
else:
    rows = []
    for y, g in panel.groupby("obs_year"):
        for f in enrich_features:
            if f not in g.columns:
                continue
            rows.append({"year": y, "feature": f, "coverage_pct": 100 * g[f].notna().mean()})
    heat = pd.DataFrame(rows).pivot(index="feature", columns="year", values="coverage_pct")

fig, ax = plt.subplots(figsize=(10, max(4, 0.35 * len(heat))))
sns.heatmap(heat, annot=True, fmt=".0f", cmap="YlGnBu", vmin=0, vmax=100, ax=ax)
ax.set_title("Enrichment coverage % by feature and observation year")
save_mpl(fig, "07_enrichment_coverage_heatmap")

# Status-flag availability for sparse families
status_cols = [c for c in panel.columns if c.endswith("_status")]
if status_cols:
    st = []
    for y, g in panel.groupby("obs_year"):
        for c in status_cols:
            ok = (g[c].astype(str).str.lower() == "ok").mean() * 100
            st.append({"year": int(y), "feature_status": c.replace("_status", ""), "ok_pct": ok})
    st_df = pd.DataFrame(st)
    # Show families with incomplete coverage
    low = st_df.groupby("feature_status")["ok_pct"].min().sort_values()
    focus = list(low.head(12).index)
    heat2 = st_df.loc[st_df["feature_status"].isin(focus)].pivot(
        index="feature_status", columns="year", values="ok_pct"
    )
    fig, ax = plt.subplots(figsize=(10, max(4, 0.35 * len(heat2))))
    sns.heatmap(heat2, annot=True, fmt=".0f", cmap="RdYlGn", vmin=0, vmax=100, ax=ax)
    ax.set_title("Share of rows with status==ok (lowest-coverage families)")
    save_mpl(fig, "07_enrichment_status_ok_heatmap")
"""
        )
    )

    # ---- 8 ----
    cells.append(md("## 8. State / county geographic summaries"))
    cells.append(
        code(
            """
geo_use = geo.dropna(subset=["latitude", "longitude"]).copy()
# Panel join for latest active-ish view: train+score mix — use unique projects from panel
proj_meta = (
    panel.sort_values("observation_date")
    .groupby("project_key", as_index=False)
    .agg(
        state_code=("state_code", "last"),
        county_fips=("county_fips", "last"),
        technology_primary=("technology_primary", "last"),
        capacity_mw=("capacity_mw", "last"),
        withdraw_next_12m=("withdraw_next_12m", "max"),
    )
)
map_df = proj_meta.merge(
    geo_use[["project_key", "latitude", "longitude", "county_name"]],
    on="project_key",
    how="inner",
)

map_sample = map_df.sample(n=min(len(map_df), 4000), random_state=0).copy()
map_sample["size_plot"] = np.log1p(map_sample["capacity_mw"].clip(lower=0))
fig = px.scatter_geo(
    map_sample,
    lat="latitude",
    lon="longitude",
    color="technology_primary",
    size="size_plot",
    hover_name="project_key",
    hover_data=["state_code", "county_name", "capacity_mw"],
    scope="usa",
    title="Projects with geo coordinates (size ∝ log1p MW for display)",
)
fig.update_geos(fitbounds="locations", visible=False, showcountries=True, showsubunits=True)
show_plotly(fig, "08_project_scatter_geo")

state_mw = (
    panel.groupby("state_code", dropna=False)
    .agg(n=("project_key", "size"), mw=("capacity_mw", "sum"))
    .reset_index()
    .sort_values("mw", ascending=False)
)
fig = px.bar(state_mw.head(20), x="state_code", y="mw", hover_data=["n"], title="Panel MW by state (top 20)")
show_plotly(fig, "08_mw_by_state")

# Train withdrawal rate by state with n on label
rt = rate_table(train_lab.dropna(subset=["state_code"]), "state_code", "withdraw_next_12m")
display(rt.head(25))
plot_rt = rt.loc[~rt["suppressed"]].sort_values("rate_plot", ascending=False)
if not plot_rt.empty:
    fig, ax = plt.subplots(figsize=(10, max(3.5, 0.28 * len(plot_rt))))
    sns.barplot(data=plot_rt, y="label", x="rate_plot", ax=ax, color="#457b9d")
    ax.set_title(f"Train withdraw rate by state (n on label; hide n<{MIN_RATE_N})")
    save_mpl(fig, "08_withdraw_rate_by_state")

county_n = (
    panel.dropna(subset=["county_fips"])
    .groupby(["state_code", "county_fips"], as_index=False)
    .size()
    .rename(columns={"size": "n"})
    .sort_values("n", ascending=False)
)
display(county_n.head(15))
fig, ax = plt.subplots(figsize=(9, 4))
sns.histplot(county_n["n"], bins=40, ax=ax, color="#2a9d8f")
ax.set_title("Projects per county (panel rows aggregated)")
ax.set_xlabel("n rows in county")
save_mpl(fig, "08_projects_per_county_hist")
"""
        )
    )

    # ---- 9 ----
    cells.append(md("## 9. Numeric distributions and outlier review"))
    cells.append(
        code(
            """
num_cols = [
    "queue_age_months",
    "capacity_mw",
    "years_in_queue",
    "months_until_service",
    "other_active_projects_same_poi",
    "study_delay_days",
    "network_upgrade_cost",
    "storm_property_damage_12m",
    "fema_risk_score",
    "interest_rate_at_observation",
    "distance_to_transmission_km",
]
num_cols = [c for c in num_cols if c in panel.columns]

rows = []
for c in num_cols:
    s = pd.to_numeric(panel[c], errors="coerce")
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    rows.append(
        {
            "feature": c,
            "n_nonnull": int(s.notna().sum()),
            "mean": s.mean(),
            "p50": s.median(),
            "p95": s.quantile(0.95),
            "p99": s.quantile(0.99),
            "max": s.max(),
            "iqr_outlier_share": float(((s < lo) | (s > hi)).mean()),
        }
    )
outlier_tbl = pd.DataFrame(rows)
display(outlier_tbl.round(3))

# Histograms: use log1p for skewed cost/MW/damage cols (plot only)
fig, axes = plt.subplots(3, 3, figsize=(12, 9))
axes = axes.ravel()
for i, c in enumerate(num_cols[:9]):
    s = pd.to_numeric(panel[c], errors="coerce")
    if c in LOG1P_PLOT_COLS or c in ("capacity_mw", "network_upgrade_cost", "storm_property_damage_12m"):
        plot_s = log1p_plot_series(s)
        title = f"log1p({c})"
    else:
        plot_s = s
        title = c
    sns.histplot(plot_s.dropna(), bins=35, ax=axes[i], color="#6d597a")
    axes[i].set_title(title, fontsize=9)
for j in range(i + 1, len(axes)):
    axes[j].axis("off")
fig.suptitle("Numeric distributions (log1p only for skewed cost/MW/damage plots)")
fig.tight_layout()
save_mpl(fig, "09_numeric_distributions")

# Outlier strip for capacity and upgrade cost (log1p plot)
fig, axes = plt.subplots(1, 2, figsize=(10, 4))
sns.boxplot(y=log1p_plot_series(panel["capacity_mw"]), ax=axes[0], color="#8ecae6")
axes[0].set_ylabel("log1p(capacity_mw)")
axes[0].set_title("Capacity outliers (plot scale)")
sns.boxplot(y=log1p_plot_series(panel["network_upgrade_cost"]), ax=axes[1], color="#e9c46a")
axes[1].set_ylabel("log1p(network_upgrade_cost)")
axes[1].set_title("Upgrade-cost outliers (plot scale)")
save_mpl(fig, "09_outlier_boxplots_log1p")
"""
        )
    )

    # ---- 10 ----
    cells.append(md("## 10. Correlations among continuous features"))
    cells.append(
        code(
            """
corr_cols = [
    "queue_age_months",
    "log1p_capacity_mw",
    "years_in_queue",
    "months_until_service",
    "other_active_projects_same_poi",
    "other_active_mw_same_poi",
    "prior_12m_withdrawal_count",
    "developer_prior_withdrawal_rate",
    "fema_risk_score",
    "population",
    "interest_rate_at_observation",
    "study_delay_days",
    "network_upgrade_cost",
    "distance_to_transmission_km",
    "news_count_90d",
    "storm_events_12m",
]
corr_cols = [c for c in corr_cols if c in train_lab.columns]
# Correlation on train complete-followup rows (no labels in matrix)
X = train_lab[corr_cols].apply(pd.to_numeric, errors="coerce")
# For highly skewed raw $ / damage if present without log1p twin, correlate on log1p *copy*
corr_plot = X.copy()
for c in ["network_upgrade_cost", "other_active_mw_same_poi", "storm_property_damage_12m"]:
    if c in corr_plot.columns:
        corr_plot[c] = log1p_plot_series(corr_plot[c])
        corr_plot = corr_plot.rename(columns={c: f"log1p_{c}_plot"})

cmat = corr_plot.corr(method="spearman")
fig, ax = plt.subplots(figsize=(10, 8))
sns.heatmap(cmat, cmap="vlag", center=0, vmin=-1, vmax=1, ax=ax, square=True)
ax.set_title("Spearman correlations (train + complete follow-up; log1p copies for skewed $)")
save_mpl(fig, "10_spearman_correlation_heatmap")

# Top |corr| pairs
pairs = (
    cmat.where(np.triu(np.ones(cmat.shape), k=1).astype(bool))
    .stack()
    .rename("rho")
    .reset_index()
    .rename(columns={"level_0": "a", "level_1": "b"})
)
pairs["abs_rho"] = pairs["rho"].abs()
display(pairs.sort_values("abs_rho", ascending=False).head(15))
"""
        )
    )

    # ---- 11 ----
    cells.append(md("## 11. Current-MISO versus historical-training drift"))
    cells.append(
        code(
            """
shared = [
    c
    for c in [
        "queue_age_months",
        "capacity_mw",
        "years_in_queue",
        "months_until_service",
        "other_active_projects_same_poi",
        "other_active_mw_same_poi",
        "developer_prior_withdrawal_rate",
        "fema_risk_score",
        "interest_rate_at_observation",
        "distance_to_transmission_km",
        "news_count_90d",
        "study_delay_days",
        "network_upgrade_cost",
    ]
    if c in train.columns and c in score.columns
]

drift_rows = []
for c in shared:
    a = pd.to_numeric(train[c], errors="coerce").dropna()
    b = pd.to_numeric(score[c], errors="coerce").dropna()
    if len(a) < 30 or len(b) < 30:
        continue
    # KS on log1p for skewed features (plot/compare scale only)
    if c in LOG1P_PLOT_COLS or c in ("capacity_mw", "network_upgrade_cost", "other_active_mw_same_poi"):
        a_c, b_c = np.log1p(a.clip(lower=0)), np.log1p(b.clip(lower=0))
        scale = "log1p"
    else:
        a_c, b_c = a, b
        scale = "raw"
    ks = stats.ks_2samp(a_c, b_c)
    drift_rows.append(
        {
            "feature": c,
            "scale": scale,
            "train_n": len(a),
            "score_n": len(b),
            "train_mean": float(a.mean()),
            "score_mean": float(b.mean()),
            "mean_shift": float(b.mean() - a.mean()),
            "ks_stat": float(ks.statistic),
            "ks_pvalue": float(ks.pvalue),
        }
    )
drift = pd.DataFrame(drift_rows).sort_values("ks_stat", ascending=False)
display(drift.round(4))

fig, ax = plt.subplots(figsize=(9, max(3.5, 0.35 * len(drift))))
sns.barplot(data=drift, y="feature", x="ks_stat", ax=ax, color="#264653")
ax.set_title("Train vs current-MISO KS statistic (higher = more drift)")
ax.set_xlabel("KS statistic")
save_mpl(fig, "11_train_vs_score_ks")

# Overlay distributions for top-drift features
top = drift.head(4)["feature"].tolist()
fig, axes = plt.subplots(2, 2, figsize=(10, 7))
axes = axes.ravel()
for i, c in enumerate(top):
    a = pd.to_numeric(train[c], errors="coerce")
    b = pd.to_numeric(score[c], errors="coerce")
    if c in LOG1P_PLOT_COLS or c in ("capacity_mw", "network_upgrade_cost", "other_active_mw_same_poi"):
        a, b = log1p_plot_series(a), log1p_plot_series(b)
        label = f"log1p({c})"
    else:
        label = c
    sns.kdeplot(a.dropna(), ax=axes[i], label=f"train (n={a.notna().sum()})", color="#2a9d8f")
    sns.kdeplot(b.dropna(), ax=axes[i], label=f"current MISO (n={b.notna().sum()})", color="#e76f51")
    axes[i].set_title(label, fontsize=9)
    axes[i].legend(fontsize=7)
fig.suptitle("Distribution drift: train vs current MISO scoring")
fig.tight_layout()
save_mpl(fig, "11_drift_kde_overlays")

# Categorical tech mix
tech = pd.concat(
    [
        train["technology_primary"].value_counts(normalize=True).rename("train"),
        score["technology_primary"].value_counts(normalize=True).rename("score"),
    ],
    axis=1,
).fillna(0)
tech = tech.reset_index().rename(columns={"index": "technology_primary"})
fig = px.bar(
    tech.melt(id_vars="technology_primary", var_name="cohort", value_name="share"),
    x="technology_primary",
    y="share",
    color="cohort",
    barmode="group",
    title="Technology mix: train vs current MISO",
)
show_plotly(fig, "11_technology_mix_drift")
"""
        )
    )

    # ---- 12 ----
    cells.append(md("## 12. Data-quality and leakage warnings"))
    cells.append(
        code(
            """
warnings_rows = []

# Incomplete follow-up by split
fu = panel.groupby("split").agg(
    n=("project_key", "size"),
    complete_followup_rate=("complete_followup", "mean"),
    label_rate=("withdraw_next_12m", "mean"),
).reset_index()
display(fu)
warnings_rows.append(
    {
        "severity": "high",
        "issue": "Score/partial splits have incomplete 12m follow-up; do not treat label rates there as supervised truth.",
        "evidence": fu.to_dict(orient="records"),
    }
)

# Label leakage columns must stay out of X
leak_cols = split_manifest.get("excluded_outcome_columns", [])
present_leak = [c for c in leak_cols if c in panel.columns]
warnings_rows.append(
    {
        "severity": "critical",
        "issue": "Outcome / label columns present on panel — never use as features.",
        "evidence": present_leak,
    }
)

# System-wide prior_12m features (known year-grain)
if "prior_12m_withdrawal_count" in train.columns:
    nunq = train.groupby("obs_year")["prior_12m_withdrawal_count"].nunique()
    warnings_rows.append(
        {
            "severity": "high",
            "issue": "prior_12m_withdrawal_count is effectively system/year-grain (not project-local).",
            "evidence": {"unique_values_per_train_year": nunq.to_dict()},
        }
    )

# Sparse DPP
dpp_cov = float(panel["network_upgrade_cost"].notna().mean()) if "network_upgrade_cost" in panel.columns else 0.0
warnings_rows.append(
    {
        "severity": "medium",
        "issue": "DPP upgrade costs are sparse; missingness is informative — do not zero-fill.",
        "evidence": {"network_upgrade_cost_nonnull_rate": dpp_cov},
    }
)

# years_since_last_change sparsity
if "years_since_last_change" in train.columns:
    ysc = float(train["years_since_last_change"].notna().mean())
    warnings_rows.append(
        {
            "severity": "medium",
            "issue": "years_since_last_change is very sparse on train (policy v1 drops it).",
            "evidence": {"train_nonnull_rate": ysc},
        }
    )

# Geo = county centroids
if "coord_source" in geo.columns:
    warnings_rows.append(
        {
            "severity": "low",
            "issue": "Map coordinates are mostly county centroids, not site GPS — treat geo plots as approximate.",
            "evidence": geo["coord_source"].value_counts(dropna=False).to_dict(),
        }
    )

# Enrichment leakage audit file (available_date after observation)
if leak_audit is not None and len(leak_audit):
    warnings_rows.append(
        {
            "severity": "high",
            "issue": "Enrichment leakage audit has rows with available_date after observation_date (see quality report).",
            "evidence": {
                "n_flagged_rows": int(len(leak_audit)),
                "top_sources": leak_audit["feature_source"].value_counts().head(5).to_dict()
                if "feature_source" in leak_audit.columns
                else {},
            },
        }
    )

# never_in_training
if "never_in_training" in panel.columns:
    warnings_rows.append(
        {
            "severity": "medium",
            "issue": "Some panel rows flagged never_in_training (current MISO / non-Berkeley lineage).",
            "evidence": panel["never_in_training"].value_counts(dropna=False).to_dict(),
        }
    )

warn_df = pd.DataFrame(
    [{"severity": w["severity"], "issue": w["issue"], "evidence": json.dumps(w["evidence"], default=str)[:300]} for w in warnings_rows]
)
display(warn_df)

fig, ax = plt.subplots(figsize=(8, max(3, 0.5 * len(warn_df))))
order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
warn_df = warn_df.assign(_o=warn_df["severity"].map(order)).sort_values("_o")
colors = {"critical": "#9b2226", "high": "#ee9b00", "medium": "#ca6702", "low": "#aeaeae"}
ax.barh(warn_df["issue"].str.slice(0, 60), [1] * len(warn_df), color=[colors.get(s, "#999") for s in warn_df["severity"]])
ax.set_title("Data-quality / leakage warning severities")
ax.set_xticks([])
save_mpl(fig, "12_quality_leakage_warnings")

# Write a short markdown sidecar (not Gold)
summary_path = REPORTS_EDA_DIR / "warnings_summary.md"
lines = ["# EDA data-quality and leakage warnings", ""]
for w in warnings_rows:
    lines.append(f"- **{w['severity']}**: {w['issue']}")
    lines.append(f"  - evidence: `{json.dumps(w['evidence'], default=str)[:400]}`")
summary_path.write_text("\\n".join(lines) + "\\n")
print("Wrote", summary_path)
print("Figures in", FIG_DIR)
print("Done. Export HTML via: python scripts/run_eda_report.py")
"""
        )
    )

    nb = nbf.v4.new_notebook()
    nb["cells"] = cells
    nb["metadata"] = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python", "pygments_lexer": "ipython3"},
    }
    return nb


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    nb = build()
    nbf.write(nb, OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
