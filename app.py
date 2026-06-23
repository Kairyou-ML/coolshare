"""
app.py
------
CoolShare Planner — decision-support & impact-simulation prototype for
Solar-Powered Cold Chain Micro-Hubs for Smallholder Farmers and Fishery
Communities.

Run with:  streamlit run app.py

Architecture: this file only handles layout/UI wiring. All calculation
logic lives in modules/ (scoring, sizing, allocation, impact) and is
fully transparent / formula-based (see the "Assumptions" tab in-app).
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium

from modules import config, scoring, sizing, allocation, impact, utils

st.set_page_config(page_title="CoolShare Planner", page_icon="🧊", layout="wide")
utils.inject_css()

if "scenarios" not in st.session_state:
    st.session_state["scenarios"] = {}

# ============================================================================
# HEADER
# ============================================================================
st.markdown("# 🧊 CoolShare Planner")
st.caption(
    "Solar-Powered Cold Chain Micro-Hubs for Smallholder Farmers & Fishery Communities — "
    "decision-support & impact-simulation prototype. All formulas are transparent and editable; "
    "see the **Assumptions** tab for every default value used."
)
utils.gradient_divider()

tab_names = [
    "📍 Site Scoring", "🔆 Hub Sizing", "📦 Booking & Allocation",
    "🌍 Impact Calculator", "📊 Dashboard", "📐 Assumptions",
]
tabs = st.tabs(tab_names)

WEIGHT_LABELS = {
    "solar_irradiance": "Solar Irradiance",
    "proximity_road": "Road Proximity",
    "density": "Beneficiary Density",
    "aspect": "Aspect (vs. true South)",
    "max_temp": "Max Temperature",
    "avg_temp": "Avg Temperature",
    "rainfall": "Rainfall",
}

# ============================================================================
# TAB 1 — SITE SCORING
# ============================================================================
with tabs[0]:
    st.subheader("Site Scoring")
    st.write(
        "Upload a CSV of candidate sites, or use the bundled sample dataset (8 sites across "
        "coastal/agricultural provinces of Vietnam). Adjust the weights below — rankings update live."
    )

    up_col, _ = st.columns([2, 3])
    with up_col:
        site_upload = st.file_uploader(
            "Upload site CSV (columns: site_id, site_name, region, latitude, longitude, aspect_deg, "
            "solar_irradiance_kwh_m2_day, max_temp_c, avg_temp_c, proximity_road_km, density_people_km2, rainfall_mm_year)",
            type="csv", key="site_upload",
        )

    try:
        sites_df = pd.read_csv(site_upload) if site_upload else pd.read_csv("data/sample_sites.csv")
    except Exception as e:
        st.error(f"Could not read uploaded file ({e}). Falling back to sample dataset.")
        sites_df = pd.read_csv("data/sample_sites.csv")

    required_cols = {"site_name", "aspect_deg", "solar_irradiance_kwh_m2_day", "max_temp_c",
                      "avg_temp_c", "proximity_road_km", "density_people_km2", "rainfall_mm_year"}
    missing = required_cols - set(sites_df.columns)
    if missing:
        st.error(f"Uploaded CSV is missing required columns: {sorted(missing)}. Using sample dataset instead.")
        sites_df = pd.read_csv("data/sample_sites.csv")

    st.markdown("**Scoring weights** *(any values — auto re-normalized to 100% before scoring)*")
    weight_cols = st.columns(4)
    weights = {}
    for i, k in enumerate(WEIGHT_LABELS):
        with weight_cols[i % 4]:
            weights[k] = st.slider(WEIGHT_LABELS[k], 0, 100, config.DEFAULT_WEIGHTS[k], key=f"w_{k}")
    norm_total = sum(weights.values()) or 1
    st.caption(f"Raw weight sum: {sum(weights.values())} → normalized to 100% internally.")

    scored_sites = scoring.compute_site_scores(sites_df, weights)
    st.session_state["scored_sites"] = scored_sites

    st.markdown("### 🏆 Top 3 Candidate Sites")
    top3 = scored_sites.head(3)
    top_cols = st.columns(3)
    for i, (_, row) in enumerate(top3.iterrows()):
        with top_cols[i]:
            utils.metric_card(f"#{int(row['rank'])} · {row['site_name']}", f"{row['total_score']:.1f} / 100")

    for line in scoring.explain_top_site(scored_sites, weights, top_n=3):
        st.write("•", line)

    with st.expander("Full ranking & sub-scores (0–100 per criterion)", expanded=False):
        display_cols = ["rank", "site_name", "region", "total_score"] + [f"{k}_subscore" for k in WEIGHT_LABELS]
        st.dataframe(scored_sites[display_cols].round(1), use_container_width=True, hide_index=True)
        utils.df_to_csv_download(scored_sites, "site_scores.csv", "⬇ Download Site Scores (CSV)")

    fig_scores = px.bar(
        scored_sites, x="site_name", y="total_score", color="total_score",
        color_continuous_scale=[config.COLORS["sky_blue"], config.COLORS["teal_deep"], config.COLORS["amber"]],
        labels={"site_name": "Site", "total_score": "Composite Score"},
        title="Composite Site Score by Candidate",
    )
    fig_scores.update_layout(showlegend=False, coloraxis_showscale=False, plot_bgcolor="white", paper_bgcolor="white")
    st.plotly_chart(fig_scores, use_container_width=True)

# ============================================================================
# TAB 2 — SOLAR COLD-HUB SIZING
# ============================================================================
with tabs[1]:
    st.subheader("Solar Cold-Hub Sizing")
    st.write("Physics-based sizing — every output below traces to an explicit formula (see Assumptions tab).")

    d = config.SIZING_DEFAULTS
    with st.expander("Load & Cooling Inputs", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            max_loading = st.number_input("Maximum Daily Product Loading (kg/day)", 10.0, 20000.0, d["max_daily_product_loading_kg"], step=10.0)
            intake_temp = st.number_input("Intake (Ambient) Temperature (°C)", 0.0, 50.0, d["intake_temp_c"])
        with c2:
            target_temp = st.number_input("Target Storage Temperature (°C)", -20.0, 20.0, d["target_storage_temp_c"])
            specific_heat = st.number_input("Specific Heat Capacity (kJ/kg·°C)", 0.5, 6.0, d["specific_heat_kj_kgC"])
        with c3:
            cop = st.slider("Coefficient of Performance (COP)", 1.0, 5.0, d["cop"], step=0.1)
            standby_load = st.number_input("Standby/Housekeeping Load (kWh/day)", 0.0, 50.0, d["standby_load_kwh_day"])

    with st.expander("PV & Battery Inputs", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            peak_sun_hours = st.number_input("Peak Sun Hours (h/day)", 2.0, 8.0, d["peak_sun_hours"], step=0.1)
            system_derate = st.slider("System Derate (%)", 50, 95, int(d["system_derate_pct"]))
        with c2:
            temp_coeff = st.number_input("Temperature Coefficient of Power (%/°C above 25°C)", 0.1, 1.0, d["temp_coeff_pct_per_C"], step=0.05)
            days_autonomy = st.slider("Days of Autonomy", 0.5, 5.0, d["days_of_autonomy"], step=0.5)
        with c3:
            battery_dod = st.slider("Battery Depth of Discharge (%)", 40, 100, int(d["battery_dod_pct"]))
            backup_pct = st.slider("Backup Requirement (% of daily demand)", 0, 100, int(d["backup_requirement_pct"]))

    with st.expander("Approximate Cost Assumptions ($)", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            cost_pv = st.number_input("PV cost ($/Wp)", 0.1, 2.0, d["cost_pv_usd_per_wp"], step=0.05)
            cost_battery = st.number_input("Battery cost ($/kWh)", 50.0, 1000.0, d["cost_battery_usd_per_kwh"], step=10.0)
        with c2:
            cost_refrig = st.number_input("Refrigeration unit cost ($)", 500.0, 20000.0, d["cost_refrigeration_unit_usd"], step=100.0)
            cost_install = st.number_input("Installation & misc. cost ($)", 0.0, 10000.0, d["cost_install_misc_usd"], step=100.0)

    sizing_inputs = {
        "max_daily_product_loading_kg": max_loading, "intake_temp_c": intake_temp,
        "target_storage_temp_c": target_temp, "specific_heat_kj_kgC": specific_heat,
        "cop": cop, "standby_load_kwh_day": standby_load, "peak_sun_hours": peak_sun_hours,
        "system_derate_pct": system_derate, "temp_coeff_pct_per_C": temp_coeff,
        "days_of_autonomy": days_autonomy, "battery_dod_pct": battery_dod,
        "backup_requirement_pct": backup_pct, "cost_pv_usd_per_wp": cost_pv,
        "cost_battery_usd_per_kwh": cost_battery, "cost_refrigeration_unit_usd": cost_refrig,
        "cost_install_misc_usd": cost_install,
    }
    sizing_outputs = sizing.run_sizing(sizing_inputs)
    st.session_state["sizing_inputs"] = sizing_inputs
    st.session_state["sizing_outputs"] = sizing_outputs

    st.markdown("### Sizing Results")
    r1 = st.columns(4)
    with r1[0]: utils.metric_card("Hub Size Class", sizing_outputs["hub_size_label"])
    with r1[1]: utils.metric_card("Daily Energy Demand", f"{sizing_outputs['daily_energy_demand_kwh']:.1f} kWh/day")
    with r1[2]: utils.metric_card("PV Array (field-adjusted)", f"{sizing_outputs['pv_field_adjusted_kwp']:.2f} kWp")
    with r1[3]: utils.metric_card("Battery Capacity", f"{sizing_outputs['battery_capacity_kwh']:.1f} kWh")

    r2 = st.columns(4)
    with r2[0]: utils.metric_card("Backup Energy Target", f"{sizing_outputs['backup_energy_kwh']:.1f} kWh/day")
    with r2[1]: utils.metric_card("Cooling Load", f"{sizing_outputs['cooling_load_kwh_day']:.1f} kWh/day")
    with r2[2]: utils.metric_card("PV Temp. Derate Loss", f"{sizing_outputs['pv_temp_loss_fraction']*100:.1f}%")
    with r2[3]: utils.metric_card("Total Capital Cost", f"${sizing_outputs['total_capital_cost_usd']:,.0f}")

    c1, c2 = st.columns(2)
    with c1:
        fig_energy = go.Figure(data=[go.Bar(
            x=["Cooling Load", "Standby Load"],
            y=[sizing_outputs["cooling_load_kwh_day"], sizing_inputs["standby_load_kwh_day"]],
            marker_color=[config.COLORS["teal_deep"], config.COLORS["sky_blue"]],
        )])
        fig_energy.update_layout(title="Daily Energy Demand Breakdown (kWh/day)", plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig_energy, use_container_width=True)
    with c2:
        cost_labels = ["PV", "Battery", "Refrigeration Unit", "Install/Misc"]
        cost_values = [sizing_outputs["pv_cost_usd"], sizing_outputs["battery_cost_usd"],
                       sizing_outputs["refrigeration_unit_usd"], sizing_outputs["install_misc_usd"]]
        fig_cost = px.pie(names=cost_labels, values=cost_values, title="Capital Cost Breakdown",
                          color_discrete_sequence=[config.COLORS["teal_deep"], config.COLORS["amber"], config.COLORS["sky_blue"], config.COLORS["text_muted"]])
        st.plotly_chart(fig_cost, use_container_width=True)

    st.caption(
        f"ΔT used for cooling load = intake ({intake_temp:.0f}°C) − target ({target_temp:.0f}°C) = "
        f"{sizing_outputs['delta_t_c']:.0f}°C. PV nameplate (STC) before temperature derate: "
        f"{sizing_outputs['pv_nameplate_kwp']:.2f} kWp."
    )

# ============================================================================
# TAB 3 — BOOKING & ALLOCATION
# ============================================================================
with tabs[2]:
    st.subheader("Booking & Allocation")
    st.write("Simulates how today's cold-room space is shared across competing bookings, prioritized transparently.")

    booking_upload = st.file_uploader(
        "Upload bookings CSV (columns: booking_id, product_name, category, volume_m3, weight_kg, "
        "storage_duration_days, decay_rate_pct_per_day, value_class [High/Medium/Low], price_usd_per_kg, "
        "cost_overestimate_usd_per_unit_day, cost_underestimate_usd_per_unit_day)",
        type="csv", key="booking_upload",
    )
    try:
        bookings_df = pd.read_csv(booking_upload) if booking_upload else pd.read_csv("data/sample_bookings.csv")
    except Exception as e:
        st.error(f"Could not read uploaded file ({e}). Falling back to sample dataset.")
        bookings_df = pd.read_csv("data/sample_bookings.csv")

    default_weight_cap = st.session_state.get("sizing_outputs", {}).get("daily_energy_demand_kwh") and \
        st.session_state.get("sizing_inputs", {}).get("max_daily_product_loading_kg", config.ALLOCATION_DEFAULTS["capacity_weight_kg"])
    default_weight_cap = default_weight_cap or config.ALLOCATION_DEFAULTS["capacity_weight_kg"]

    c1, c2 = st.columns(2)
    with c1:
        capacity_volume = st.number_input("Hub Volume Capacity (m³)", 1.0, 200.0, config.ALLOCATION_DEFAULTS["capacity_volume_m3"], step=0.5)
    with c2:
        capacity_weight = st.number_input(
            "Hub Weight Capacity (kg/day)", 10.0, 20000.0, float(default_weight_cap), step=10.0,
            help="Defaults to the 'Maximum Daily Product Loading' you set in the Hub Sizing tab.",
        )

    alloc_result = allocation.allocate_bookings(bookings_df, capacity_volume, capacity_weight)
    alloc_table = alloc_result["allocation_table"]
    alloc_summary = alloc_result["summary"]
    st.session_state["allocation_summary"] = alloc_summary

    if alloc_summary["overload"]:
        st.markdown(
            utils.status_badge_html(f"⚠ Overload — {alloc_summary['n_waitlisted']} booking(s) waitlisted", "critical"),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(utils.status_badge_html("✓ All bookings allocated within capacity", "ok"), unsafe_allow_html=True)

    m1, m2, m3, m4 = st.columns(4)
    with m1: utils.metric_card("Volume Fill Rate", f"{alloc_summary['fill_rate_volume_pct']:.0f}%")
    with m2: utils.metric_card("Weight Fill Rate", f"{alloc_summary['fill_rate_weight_pct']:.0f}%")
    with m3: utils.metric_card("Allocated / Waitlisted", f"{alloc_summary['n_allocated']} / {alloc_summary['n_waitlisted']}")
    with m4: utils.metric_card("Est. Cost of Mis-sizing", f"${alloc_summary['cost_overestimate_total_usd']+alloc_summary['cost_underestimate_total_usd']:,.0f}/day")

    st.markdown("### Allocation Schedule (priority high → low)")
    display_cols = ["booking_id", "product_name", "category", "value_class", "decay_rate_pct_per_day",
                     "priority_score", "volume_m3", "weight_kg", "status", "allocation_reason"]
    st.dataframe(alloc_table[display_cols].round(2), use_container_width=True, hide_index=True)
    utils.df_to_csv_download(alloc_table, "allocation_schedule.csv", "⬇ Download Allocation Schedule (CSV)")

    fig_alloc = go.Figure()
    fig_alloc.add_trace(go.Bar(name="Allocated", x=["Volume (m³)", "Weight (kg)"],
                                y=[alloc_summary["allocated_volume_m3"], alloc_summary["allocated_weight_kg"]],
                                marker_color=config.COLORS["teal_deep"]))
    fig_alloc.add_trace(go.Bar(name="Remaining Capacity", x=["Volume (m³)", "Weight (kg)"],
                                y=[max(capacity_volume - alloc_summary["allocated_volume_m3"], 0),
                                   max(capacity_weight - alloc_summary["allocated_weight_kg"], 0)],
                                marker_color=config.COLORS["border"]))
    fig_alloc.update_layout(barmode="stack", title="Capacity Utilization", plot_bgcolor="white", paper_bgcolor="white")
    st.plotly_chart(fig_alloc, use_container_width=True)

    st.caption(
        "Priority score = decay rate (%/day) × value-class multiplier (High=1.5, Medium=1.0, Low=0.6) × "
        "(1 + cost-of-underestimating ÷ cost-of-overestimating, capped at 10×). Higher score is served first."
    )

# ============================================================================
# TAB 4 — IMPACT CALCULATOR
# ============================================================================
with tabs[3]:
    st.subheader("Impact Calculator")
    st.write("Estimates the economic, environmental and operational impact of the cold hub vs. a no-hub baseline.")

    di = config.IMPACT_DEFAULTS
    with st.expander("Spoilage & Market Inputs", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            monthly_vol = st.number_input("Monthly Input Volume (kg/month)", 100.0, 200000.0, di["monthly_input_volume_kg"], step=100.0)
        with c2:
            baseline_spoil = st.slider("Baseline Spoilage Rate (%, no hub)", 0.0, 80.0, di["baseline_spoilage_pct"])
            coldhub_spoil = st.slider("Cold-Hub Spoilage Rate (%, with hub)", 0.0, 80.0, di["coldhub_spoilage_pct"])
        with c3:
            market_price = st.number_input("Market Price ($/kg)", 0.05, 20.0, di["market_price_usd_per_kg"], step=0.05)

    with st.expander("Energy & Emissions Inputs", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            utilized_solar = st.number_input("Utilized Solar Energy (kWh/month)", 0.0, 50000.0, di["utilized_solar_energy_kwh_month"], step=10.0)
        with c2:
            emission_factor = st.number_input("Grid/Diesel Emission Factor (kg CO₂/kWh)", 0.1, 1.5, di["grid_diesel_emission_factor_kg_co2_per_kwh"], step=0.05)
            refrig_charge = st.number_input("Refrigerant Charge (kg)", 0.1, 20.0, di["refrigerant_charge_kg"], step=0.1)
        with c3:
            refrig_gwp = st.number_input("Refrigerant GWP (100-yr)", 1.0, 5000.0, di["refrigerant_gwp"], step=10.0)
            leak_rate = st.slider("Refrigerant Leakage Rate (%/year)", 0.0, 30.0, di["refrigerant_leak_rate_pct_year"])

    with st.expander("Cost & Savings Inputs", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            capex = st.number_input("Total Capital Cost ($)", 100.0, 200000.0, di["total_capital_cost_usd"], step=100.0)
        with c2:
            om_cost = st.number_input("Monthly O&M & Depreciation Cost ($/month)", 0.0, 5000.0, di["monthly_om_depreciation_usd"], step=10.0)
        with c3:
            energy_savings = st.number_input("Energy Cost Savings ($/month)", 0.0, 5000.0, di["energy_cost_savings_usd_month"], step=10.0)

    impact_inputs = {
        "monthly_input_volume_kg": monthly_vol, "baseline_spoilage_pct": baseline_spoil,
        "coldhub_spoilage_pct": coldhub_spoil, "market_price_usd_per_kg": market_price,
        "utilized_solar_energy_kwh_month": utilized_solar,
        "grid_diesel_emission_factor_kg_co2_per_kwh": emission_factor,
        "refrigerant_charge_kg": refrig_charge, "refrigerant_gwp": refrig_gwp,
        "refrigerant_leak_rate_pct_year": leak_rate, "total_capital_cost_usd": capex,
        "monthly_om_depreciation_usd": om_cost, "energy_cost_savings_usd_month": energy_savings,
    }
    impact_outputs = impact.run_impact(impact_inputs)
    st.session_state["impact_inputs"] = impact_inputs
    st.session_state["impact_outputs"] = impact_outputs

    st.markdown("### Monthly Impact Results")
    r1 = st.columns(4)
    with r1[0]: utils.metric_card("Food Saved", f"{impact_outputs['spoilage_avoided_kg']:.0f} kg/mo")
    with r1[1]: utils.metric_card("Income Protected", f"${impact_outputs['income_protected_usd']:,.0f}/mo")
    with r1[2]: utils.metric_card("Renewable Energy Used", f"{impact_outputs['kwh_renewable_used']:.0f} kWh/mo")
    with r1[3]: utils.metric_card("Net CO₂ Avoided", f"{impact_outputs['net_co2_avoided_kg']:.0f} kg/mo")

    r2 = st.columns(4)
    payback_display = f"{impact_outputs['payback_months']:.1f} mo" if impact_outputs["payback_months"] != float("inf") else "N/A"
    with r2[0]: utils.metric_card("Simple Payback", payback_display)
    with r2[1]: utils.metric_card("Simple ROI", f"{impact_outputs['simple_roi_pct_year']:.1f}%/yr")
    with r2[2]: utils.metric_card("Grid/Diesel Avoided", f"{impact_outputs['grid_diesel_avoided_kwh']:.0f} kWh/mo")
    with r2[3]: utils.metric_card("Refrigerant CO₂", f"{impact_outputs['co2_refrigerant_kg']:.1f} kg/mo")

    ba = impact_outputs["before_after"]
    c1, c2 = st.columns(2)
    with c1:
        fig_spoil = go.Figure(data=[go.Bar(x=["Before (no hub)", "After (cold hub)"],
                                            y=[ba["spoilage_pct"]["before"], ba["spoilage_pct"]["after"]],
                                            marker_color=[config.COLORS["status_critical"], config.COLORS["status_ok"]])])
        fig_spoil.update_layout(title="Spoilage Rate: Before vs After (%)", plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig_spoil, use_container_width=True)
    with c2:
        fig_loss = go.Figure(data=[go.Bar(x=["Before (no hub)", "After (cold hub)"],
                                           y=[ba["loss_usd_month"]["before"], ba["loss_usd_month"]["after"]],
                                           marker_color=[config.COLORS["status_critical"], config.COLORS["status_ok"]])])
        fig_loss.update_layout(title="Monthly Spoilage Loss: Before vs After ($)", plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig_loss, use_container_width=True)

    st.caption(
        "Assumption: utilized solar energy displaces an equal amount of grid/diesel energy 1:1. "
        "Net CO₂ avoided = CO₂ avoided from displaced grid/diesel energy − CO₂-equivalent from refrigerant leakage."
    )

# ============================================================================
# TAB 5 — DASHBOARD
# ============================================================================
with tabs[4]:
    scored_sites = st.session_state.get("scored_sites")
    sizing_outputs = st.session_state.get("sizing_outputs")
    impact_outputs = st.session_state.get("impact_outputs")
    alloc_summary = st.session_state.get("allocation_summary")

    if scored_sites is None or sizing_outputs is None or impact_outputs is None or alloc_summary is None:
        st.info("Visit the other tabs first (even briefly) so the dashboard has data to summarize.")
    else:
        top_site = scored_sites.iloc[0]
        utils.banner(
            "Recommended Pilot Site",
            f"📍 {top_site['site_name']} ({top_site['region']})",
            f"Composite score {top_site['total_score']:.1f}/100 · Suggested hub class: {sizing_outputs['hub_size_label']} · "
            f"Est. capital cost ${sizing_outputs['total_capital_cost_usd']:,.0f}",
        )

        st.markdown("### Key Indicators")
        fr_status = utils.fill_rate_status(alloc_summary["fill_rate_volume_pct"])
        sp_status = utils.spoilage_status(st.session_state["impact_inputs"]["coldhub_spoilage_pct"])
        co2_status = "ok" if impact_outputs["net_co2_avoided_kg"] > 0 else "critical"

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            utils.metric_card("Volume Fill Rate", f"{alloc_summary['fill_rate_volume_pct']:.0f}%",
                              fr_status.upper(), fr_status)
        with k2:
            utils.metric_card("Net CO₂ Avoided", f"{impact_outputs['net_co2_avoided_kg']:.0f} kg/mo",
                              co2_status.upper(), co2_status)
        with k3:
            utils.metric_card("Cold-Hub Spoilage Rate", f"{st.session_state['impact_inputs']['coldhub_spoilage_pct']:.1f}%",
                              sp_status.upper(), sp_status)
        with k4:
            pv_now = utils.simulated_pv_power_kw(sizing_outputs["pv_field_adjusted_kwp"])
            utils.metric_card("Simulated PV Power (now)", f"{pv_now:.2f} kW",
                              "LIVE-STYLE DEMO", "ok")

        st.caption("⚡ 'Simulated PV Power' uses a daylight sine curve scaled to the sized PV array — it is a demo visual, not live telemetry.")

        c1, c2 = st.columns([3, 2])
        with c1:
            st.markdown("#### Before vs After — Monthly Spoilage Loss ($)")
            ba = impact_outputs["before_after"]
            fig = go.Figure(data=[go.Bar(x=["Before (no hub)", "After (cold hub)"],
                                          y=[ba["loss_usd_month"]["before"], ba["loss_usd_month"]["after"]],
                                          marker_color=[config.COLORS["status_critical"], config.COLORS["status_ok"]])])
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white", height=320)
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.markdown("#### Hub Capacity Status")
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=alloc_summary["fill_rate_volume_pct"],
                title={"text": "Volume Fill Rate (%)"},
                gauge={"axis": {"range": [0, 100]},
                       "bar": {"color": config.COLORS["teal_deep"]},
                       "steps": [
                           {"range": [0, 30], "color": "#FCE9D8"},
                           {"range": [30, 60], "color": "#FCE9D8"},
                           {"range": [60, 95], "color": "#DCEFE1"},
                           {"range": [95, 100], "color": "#F6D6D2"},
                       ]},
            ))
            fig_gauge.update_layout(height=320)
            st.plotly_chart(fig_gauge, use_container_width=True)

        st.markdown("### Pilot Location Comparison")
        compare_cols = ["rank", "site_name", "region", "total_score", "solar_irradiance_kwh_m2_day",
                        "proximity_road_km", "density_people_km2"]
        compare_df = scored_sites[compare_cols].copy()
        compare_df["suggested_hub_class"] = sizing_outputs["hub_size_label"]
        compare_df["est_capital_cost_usd"] = round(sizing_outputs["total_capital_cost_usd"], 0)
        st.dataframe(compare_df.round(1), use_container_width=True, hide_index=True)
        st.caption("Hub class & capital cost shown here reflect the single hub design currently configured in the Hub Sizing tab, applied hypothetically to every site for comparison.")

        if {"latitude", "longitude"}.issubset(scored_sites.columns):
            st.markdown("### Site Map")
            center_lat, center_lon = scored_sites["latitude"].mean(), scored_sites["longitude"].mean()
            m = folium.Map(location=[center_lat, center_lon], zoom_start=6, tiles="CartoDB positron")
            for _, row in scored_sites.iterrows():
                is_top = row["rank"] == 1
                folium.CircleMarker(
                    location=[row["latitude"], row["longitude"]],
                    radius=12 if is_top else 8,
                    popup=f"{row['site_name']} — score {row['total_score']:.1f} (rank {int(row['rank'])})",
                    tooltip=row["site_name"],
                    color=config.COLORS["amber"] if is_top else config.COLORS["teal_deep"],
                    fill=True, fill_opacity=0.85,
                    fill_color=config.COLORS["amber"] if is_top else config.COLORS["sky_blue"],
                ).add_to(m)
            st_folium(m, width=None, height=420, returned_objects=[])
        else:
            st.info("Map unavailable — uploaded site data has no latitude/longitude columns.")

        st.markdown("### Scenario Analysis")
        st.write("Save the current configuration as a named scenario, then compare up to several side by side.")
        sc1, sc2 = st.columns([2, 1])
        with sc1:
            scenario_name = st.text_input("Scenario name", value=f"Scenario {len(st.session_state['scenarios']) + 1}")
        with sc2:
            st.write("")
            if st.button("📌 Save current as scenario"):
                st.session_state["scenarios"][scenario_name] = {
                    "Top Site": top_site["site_name"],
                    "Site Score": round(top_site["total_score"], 1),
                    "Hub Class": sizing_outputs["hub_size_label"],
                    "Capital Cost ($)": round(sizing_outputs["total_capital_cost_usd"], 0),
                    "PV Size (kWp)": round(sizing_outputs["pv_field_adjusted_kwp"], 2),
                    "Battery (kWh)": round(sizing_outputs["battery_capacity_kwh"], 1),
                    "Net CO2 Avoided (kg/mo)": round(impact_outputs["net_co2_avoided_kg"], 1),
                    "Payback (months)": round(impact_outputs["payback_months"], 1) if impact_outputs["payback_months"] != float("inf") else "N/A",
                    "Volume Fill Rate (%)": round(alloc_summary["fill_rate_volume_pct"], 0),
                }
                st.success(f"Saved '{scenario_name}'.")

        if st.session_state["scenarios"]:
            scen_df = pd.DataFrame(st.session_state["scenarios"]).T
            st.dataframe(scen_df, use_container_width=True)
            if st.button("🗑 Clear all saved scenarios"):
                st.session_state["scenarios"] = {}
                st.rerun()

        st.markdown("### Export")
        exp1, exp2 = st.columns(2)
        with exp1:
            try:
                pdf_bytes = utils.build_pdf_summary(
                    top_site["site_name"], top_site["total_score"], sizing_outputs, impact_outputs, alloc_summary
                )
                st.download_button("⬇ Download Executive Summary (PDF)", data=pdf_bytes,
                                   file_name="coolshare_executive_summary.pdf", mime="application/pdf")
            except Exception as e:
                st.warning(f"PDF export unavailable ({e}).")
        with exp2:
            utils.df_to_csv_download(scored_sites, "dashboard_site_comparison.csv", "⬇ Download Site Comparison (CSV)")

# ============================================================================
# TAB 6 — ASSUMPTIONS / HOW IT WORKS
# ============================================================================
with tabs[5]:
    st.subheader("Assumptions & How It Works")
    st.write("Every number the app uses by default is listed here. Change any input in its tab — these are starting points, not hidden constants.")

    st.markdown("#### 1. Site Scoring")
    st.markdown("""
- **Solar Irradiance, Beneficiary Density** → min-max scaled 0–100, *higher is better*.
- **Road Proximity, Max/Avg Temperature** → inverse min-max scaled 0–100, *lower is better*.
- **Aspect** → 100 at true South (180°), linearly falling to 0 at 180° away (due North).
- **Rainfall** → 100 inside the 1,000–2,000 mm/year band (enough water access, low flood/road-washout risk), decaying outside it.
- **Total score** = Σ(weight% × sub-score), weights re-normalized to sum to 100%.
""")

    st.markdown("#### 2. Solar Cold-Hub Sizing")
    st.markdown("""
- Cooling load (kWh/day) = `loading(kg) × specific_heat(kJ/kg·°C) × ΔT(°C) / 3600 / COP`
- Daily Energy Demand = Cooling load + Standby load
- PV nameplate (kWp) = `Daily Energy Demand / (Peak Sun Hours × System Derate)`, then inflated by the Temperature Coefficient of Power to get the field-adjusted size
- Battery capacity (kWh) = `Daily Energy Demand × Days of Autonomy / Battery DoD`
- Backup energy target (kWh) = `Daily Energy Demand × Backup Requirement %`
- Total Capital Cost = PV cost + Battery cost + Refrigeration unit + Install/misc
""")

    st.markdown("#### 3. Booking & Allocation")
    st.markdown("""
- Priority score = `decay_rate(%/day) × value_class_multiplier × (1 + min(cost_underestimate / cost_overestimate, 10))`
- Value class multipliers: High = 1.5, Medium = 1.0, Low = 0.6
- Bookings are allocated highest-priority-first until volume **or** weight capacity is reached; the rest are waitlisted with a stated reason.
""")

    st.markdown("#### 4. Impact Calculator")
    st.markdown("""
- Spoilage avoided (kg/mo) = `Monthly Input Volume × (Baseline Spoilage% − Cold-Hub Spoilage%)`
- Income protected ($/mo) = `Spoilage avoided × Market Price`
- **Assumption:** Utilized solar energy displaces an equal (1:1) amount of grid/diesel energy.
- CO₂ avoided from energy = `Grid/diesel avoided kWh × Emission Factor`
- CO₂ from refrigerant = `Refrigerant Charge × Leak Rate%/yr × GWP / 12`
- Net CO₂ Avoided = CO₂ avoided from energy − CO₂ from refrigerant leakage
- Simple Payback (months) = `Total Capital Cost / (Total Monthly Benefit − Monthly O&M)`
""")

    st.markdown("#### Default Values Currently Loaded")
    with st.expander("Site Scoring weights"):
        st.json(config.DEFAULT_WEIGHTS)
    with st.expander("Hub Sizing defaults"):
        st.json(config.SIZING_DEFAULTS)
    with st.expander("Allocation defaults"):
        st.json(config.ALLOCATION_DEFAULTS)
    with st.expander("Impact Calculator defaults"):
        st.json(config.IMPACT_DEFAULTS)

    st.info(
        "If any input field is left at its default, that value — not a blank — is what's used in every "
        "calculation. All defaults are clearly editable in their respective tabs."
    )
