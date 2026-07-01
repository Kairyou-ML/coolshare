"""
app.py — CoolShare Planner
Pipeline: Site Scoring → Hub Design → Booking → Impact → Dashboard
All calculation logic lives in modules/; this file is pure UI wiring.
Run: streamlit run app.py
"""

import uuid
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium

from modules import config, scoring, sizing, allocation, impact, recommendation, utils

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="CoolShare Planner", page_icon="🧊", layout="wide")
utils.inject_css()

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────────────────────────────────────
_ss = st.session_state
for k, v in [
    ("scored_sites",       None),
    ("site_weights",       config.DEFAULT_WEIGHTS.copy()),
    ("saved_hubs",         {}),           # hub_id → hub dict
    ("hub_counter",        0),
    ("bookings_df",        None),
    ("manual_bookings",    []),           # list of dicts — manual entry form rows
    ("next_booking_id",    1),            # auto-increment for manual booking IDs
    ("hub_allocations",    {}),           # hub_id → {"allocation_table", "summary"}
    ("impact_mkt",         {ky: config.IMPACT_DEFAULTS[ky]
                            for ky in config.IMPACT_MARKET_PARAM_KEYS}),
    ("hub_impact_outputs", {}),           # hub_id → impact_outputs dict
    ("scenarios",          {}),
]:
    if k not in _ss:
        _ss[k] = v

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
hc1, hc2 = st.columns([3, 1])
with hc1:
    st.markdown("# 🧊 CoolShare Planner")
    st.caption(
        "Solar-Powered Cold Chain Micro-Hubs · Decision-Support & Investment Coordination Platform · "
        "All formulas transparent — see the **Assumptions** tab."
    )
with hc2:
    n_hubs  = len(_ss["saved_hubs"])
    n_sites = len(_ss["scored_sites"]) if _ss["scored_sites"] is not None else 0
    st.metric("Sites Scored", n_sites)
    st.metric("Hubs in Portfolio", n_hubs)

utils.gradient_divider()

# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
TABS = st.tabs([
    "① Site Scoring",
    "② Hub Design",
    "③ Booking & Allocation",
    "④ Impact Analysis",
    "⑤ Portfolio Dashboard",
    "📐 Assumptions",
])

WEIGHT_LABELS = {
    "solar_irradiance": "Solar Irradiance",
    "proximity_road":   "Road Proximity",
    "density":          "Beneficiary Density",
    "aspect":           "Aspect (vs. true South)",
    "max_temp":         "Max Temperature",
    "avg_temp":         "Avg Temperature",
    "rainfall":         "Rainfall",
}

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — SITE SCORING   (fully editable, outputs scored_sites)
# ─────────────────────────────────────────────────────────────────────────────
with TABS[0]:
    utils.pipeline_step_bar(current=1, n_done=0)
    st.subheader("① Site Scoring")
    st.write("Rank candidate sites using an adjustable weighted model. "
             "Results flow automatically into Hub Design → Booking → Impact.")

    up_col, _ = st.columns([2, 3])
    with up_col:
        site_upload = st.file_uploader(
            "Upload site CSV (required cols: site_id, site_name, region, latitude, longitude, "
            "aspect_deg, solar_irradiance_kwh_m2_day, max_temp_c, avg_temp_c, proximity_road_km, "
            "density_people_km2, rainfall_mm_year  |  optional: expected_daily_volume_kg, "
            "dominant_category, flood_risk, grid_reliability)",
            type="csv", key="site_upload",
        )

    try:
        sites_df = pd.read_csv(site_upload) if site_upload else pd.read_csv("data/sample_sites.csv")
    except Exception as e:
        st.error(f"Could not read file ({e}). Falling back to sample dataset.")
        sites_df = pd.read_csv("data/sample_sites.csv")

    required_cols = {"site_name","aspect_deg","solar_irradiance_kwh_m2_day","max_temp_c",
                     "avg_temp_c","proximity_road_km","density_people_km2","rainfall_mm_year"}
    if missing := required_cols - set(sites_df.columns):
        st.error(f"CSV missing required columns: {sorted(missing)}. Using sample data.")
        sites_df = pd.read_csv("data/sample_sites.csv")

    st.markdown("**Scoring weights** *(values auto-normalized to 100% before use)*")
    wc = st.columns(4)
    weights = {}
    for i, k in enumerate(WEIGHT_LABELS):
        with wc[i % 4]:
            weights[k] = st.slider(WEIGHT_LABELS[k], 0, 100,
                                    config.DEFAULT_WEIGHTS[k], key=f"w_{k}")
    st.caption(f"Weight sum: {sum(weights.values())} → normalized to 100% internally.")

    scored_sites = scoring.compute_site_scores(sites_df, weights)
    _ss["scored_sites"] = scored_sites
    _ss["site_weights"]  = weights

    st.markdown("### 🏆 Top 3 Candidate Sites")
    top3 = scored_sites.head(3)
    cols3 = st.columns(3)
    for i, (_, row) in enumerate(top3.iterrows()):
        with cols3[i]:
            utils.metric_card(f"#{int(row['rank'])} · {row['site_name']}",
                              f"{row['total_score']:.1f}/100")

    for line in scoring.explain_top_site(scored_sites, weights, top_n=3):
        st.write("•", line)

    with st.expander("Full ranking & sub-scores (0–100 per criterion)"):
        disp = (["rank","site_name","region","total_score"]
                + [f"{k}_subscore" for k in WEIGHT_LABELS])
        st.dataframe(scored_sites[disp].round(1), use_container_width=True, hide_index=True)
        utils.df_to_csv_download(scored_sites, "site_scores.csv", "⬇ Download Site Scores (CSV)")

    fig_scores = px.bar(
        scored_sites, x="site_name", y="total_score", color="total_score",
        color_continuous_scale=[config.COLORS["sky_blue"],
                                config.COLORS["teal_deep"],
                                config.COLORS["amber"]],
        labels={"site_name": "Site", "total_score": "Score"},
        title="Composite Site Score — All Candidates",
    )
    fig_scores.update_layout(showlegend=False, coloraxis_showscale=False,
                             plot_bgcolor="white", paper_bgcolor="white",
                             xaxis_tickangle=-25)
    st.plotly_chart(fig_scores, use_container_width=True)

    st.success(f"✓ {len(scored_sites)} sites scored. Proceed to **② Hub Design** to size a hub for any candidate.")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — HUB DESIGN   (inherited site data → editable engineering → save hubs)
# ─────────────────────────────────────────────────────────────────────────────
with TABS[1]:
    utils.pipeline_step_bar(current=2, n_done=1 if _ss["scored_sites"] is not None else 0)
    st.subheader("② Hub Design")

    if _ss["scored_sites"] is None:
        st.info("Complete **① Site Scoring** first — it supplies the site data that drives hub sizing.")
        st.stop()

    scored = _ss["scored_sites"]
    site_options = [f"#{int(r['rank'])} · {r['site_name']} ({r['region']}) — {r['total_score']:.1f}/100"
                    for _, r in scored.iterrows()]
    chosen_label = st.selectbox("📍 Design a hub for:", site_options, index=0)
    site_row = scored.iloc[site_options.index(chosen_label)]

    # ── INHERITED site block ──────────────────────────────────────────────
    daily_vol_default = utils.pipeline_default(site_row, "expected_daily_volume_kg",
                                               config.SIZING_DEFAULTS["max_daily_product_loading_kg"])
    dom_cat  = utils.pipeline_default(site_row, "dominant_category", "—")
    fl_risk  = utils.pipeline_default(site_row, "flood_risk", "—")
    gr_rel   = utils.pipeline_default(site_row, "grid_reliability", "—")

    utils.inherited_block([
        ("Site",                      site_row["site_name"]),
        ("Region",                    site_row.get("region","—")),
        ("Composite score",           f"{site_row['total_score']:.1f} / 100  (rank #{int(site_row['rank'])})"),
        ("Expected daily volume",     f"{daily_vol_default:.0f} kg/day  → pre-fills Max Loading below"),
        ("Dominant category",         str(dom_cat)),
        ("Flood risk",                str(fl_risk)),
        ("Grid reliability",          str(gr_rel)),
    ], source_label="Site Scoring")

    # ── EDITABLE engineering parameters ──────────────────────────────────
    d = config.SIZING_DEFAULTS
    site_key = site_row.get("site_id", site_row["site_name"])

    st.markdown("#### Engineering Parameters *(editable)*")
    with st.expander("Load & Cooling", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            max_loading  = st.number_input("Max Daily Product Loading (kg/day)", 10.0, 20000.0,
                                           float(daily_vol_default), step=10.0, key=f"ml_{site_key}",
                                           help="Auto-filled from site's expected volume; editable.")
            intake_temp  = st.number_input("Intake Temperature (°C)", 0.0, 50.0, d["intake_temp_c"])
        with c2:
            target_temp  = st.number_input("Target Storage Temp (°C)", -20.0, 20.0, d["target_storage_temp_c"])
            specific_heat = st.number_input("Specific Heat (kJ/kg·°C)", 0.5, 6.0, d["specific_heat_kj_kgC"])
        with c3:
            cop          = st.slider("COP", 1.0, 5.0, d["cop"], 0.1)
            standby_load = st.number_input("Standby Load (kWh/day)", 0.0, 50.0, d["standby_load_kwh_day"])
        c4, c5 = st.columns(2)
        with c4:
            turnover     = st.slider("Storage Turnover (days)", 0.5, 10.0, d["storage_turnover_days"], 0.5)
        with c5:
            bulk_density = st.number_input("Bulk Density (kg/m³)", 50.0, 800.0, d["bulk_density_kg_m3"], step=10.0)

    with st.expander("PV & Battery", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            psh          = st.number_input("Peak Sun Hours (h/day)", 2.0, 8.0, d["peak_sun_hours"], 0.1)
            derate       = st.slider("System Derate (%)", 50, 95, int(d["system_derate_pct"]))
        with c2:
            temp_coeff   = st.number_input("Temp Coeff (%/°C above 25°C)", 0.1, 1.0, d["temp_coeff_pct_per_C"], 0.05)
            days_auto    = st.slider("Days of Autonomy", 0.5, 5.0, d["days_of_autonomy"], 0.5)
        with c3:
            batt_dod     = st.slider("Battery DoD (%)", 40, 100, int(d["battery_dod_pct"]))
            backup_pct   = st.slider("Backup Requirement (%)", 0, 100, int(d["backup_requirement_pct"]))

    with st.expander("Cost Assumptions ($)", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            cost_pv      = st.number_input("PV ($/Wp)", 0.1, 2.0, d["cost_pv_usd_per_wp"], 0.05)
            cost_batt    = st.number_input("Battery ($/kWh)", 50.0, 1000.0, d["cost_battery_usd_per_kwh"], 10.0)
        with c2:
            cost_refrig  = st.number_input("Refrigeration unit ($)", 500.0, 20000.0, d["cost_refrigeration_unit_usd"], 100.0)
            cost_install = st.number_input("Installation & misc ($)", 0.0, 10000.0, d["cost_install_misc_usd"], 100.0)

    sizing_inputs = {
        "max_daily_product_loading_kg": max_loading,
        "intake_temp_c": intake_temp, "target_storage_temp_c": target_temp,
        "specific_heat_kj_kgC": specific_heat, "cop": cop,
        "standby_load_kwh_day": standby_load, "peak_sun_hours": psh,
        "system_derate_pct": derate, "temp_coeff_pct_per_C": temp_coeff,
        "days_of_autonomy": days_auto, "battery_dod_pct": batt_dod,
        "backup_requirement_pct": backup_pct,
        "cost_pv_usd_per_wp": cost_pv, "cost_battery_usd_per_kwh": cost_batt,
        "cost_refrigeration_unit_usd": cost_refrig, "cost_install_misc_usd": cost_install,
        "storage_turnover_days": turnover, "bulk_density_kg_m3": bulk_density,
    }
    so = sizing.run_sizing(sizing_inputs)

    # ── Results ───────────────────────────────────────────────────────────
    st.markdown("#### Sizing Results")
    st.caption(f"🔗 Computed for **{site_row['site_name']}** — change site selector above to re-size.")
    r1 = st.columns(4)
    with r1[0]: utils.metric_card("Hub Class",          so["hub_size_label"])
    with r1[1]: utils.metric_card("Daily Energy Demand", f"{so['daily_energy_demand_kwh']:.1f} kWh/day")
    with r1[2]: utils.metric_card("PV (field-adjusted)", f"{so['pv_field_adjusted_kwp']:.2f} kWp")
    with r1[3]: utils.metric_card("Battery",            f"{so['battery_capacity_kwh']:.1f} kWh")
    r2 = st.columns(4)
    with r2[0]: utils.metric_card("Cold Room Volume",   f"{so['estimated_storage_volume_m3']:.1f} m³")
    with r2[1]: utils.metric_card("Cooling Load",       f"{so['cooling_load_kwh_day']:.1f} kWh/day")
    with r2[2]: utils.metric_card("Backup Target",      f"{so['backup_energy_kwh']:.1f} kWh/day")
    with r2[3]: utils.metric_card("Total Capital Cost", f"${so['total_capital_cost_usd']:,.0f}")

    ch1, ch2 = st.columns(2)
    with ch1:
        fig_e = go.Figure(go.Bar(
            x=["Cooling Load", "Standby Load"],
            y=[so["cooling_load_kwh_day"], sizing_inputs["standby_load_kwh_day"]],
            marker_color=[config.COLORS["teal_deep"], config.COLORS["sky_blue"]],
            text=[f"{so['cooling_load_kwh_day']:.1f}", f"{sizing_inputs['standby_load_kwh_day']:.1f}"],
            textposition="outside",
        ))
        fig_e.update_layout(title="Daily Energy Demand (kWh/day)",
                            plot_bgcolor="white", paper_bgcolor="white", height=300)
        st.plotly_chart(fig_e, use_container_width=True)
    with ch2:
        fig_c = px.pie(
            names=["PV", "Battery", "Refrigeration", "Install/Misc"],
            values=[so["pv_cost_usd"], so["battery_cost_usd"],
                    so["refrigeration_unit_usd"], so["install_misc_usd"]],
            title="Capital Cost Breakdown",
            color_discrete_sequence=[config.COLORS["teal_deep"], config.COLORS["amber"],
                                     config.COLORS["sky_blue"], config.COLORS["text_muted"]],
        )
        fig_c.update_layout(height=300)
        st.plotly_chart(fig_c, use_container_width=True)

    st.caption(
        f"ΔT = {so['delta_t_c']:.0f}°C · PV nameplate (STC) {so['pv_nameplate_kwp']:.2f} kWp "
        f"({so['pv_temp_loss_fraction']*100:.1f}% temp-derate applied) → field-adjusted {so['pv_field_adjusted_kwp']:.2f} kWp. "
        f"Cold room = ({max_loading:.0f} kg × {turnover:.1f} d) / {bulk_density:.0f} kg/m³ = {so['estimated_storage_volume_m3']:.1f} m³."
    )

    # ── Save hub to portfolio ─────────────────────────────────────────────
    st.divider()
    st.markdown("### 💾 Save Hub to Portfolio")
    st.write("A portfolio lets you design hubs for multiple sites and compare them side-by-side "
             "in the Dashboard. Booking & Allocation and Impact will run automatically for every saved hub.")
    sc1, sc2 = st.columns([3, 1])
    with sc1:
        hub_name = st.text_input(
            "Hub name",
            value=f"Hub {_ss['hub_counter']+1} — {site_row['site_name']}",
            key=f"hub_name_{site_key}",
        )
    with sc2:
        st.write("")
        st.write("")
        if st.button("➕ Add to Portfolio", type="primary"):
            hid = str(uuid.uuid4())[:8]
            _ss["saved_hubs"][hid] = {
                "hub_name":     hub_name,
                "site_name":    site_row["site_name"],
                "site_row":     site_row.to_dict(),
                "site_score":   float(site_row["total_score"]),
                "sizing_inputs": sizing_inputs.copy(),
                "sizing_outputs": so.copy(),
            }
            _ss["hub_counter"] += 1
            st.success(f"✓ '{hub_name}' added to portfolio ({len(_ss['saved_hubs'])} hub(s) total).")

    # ── Saved hubs table ──────────────────────────────────────────────────
    if _ss["saved_hubs"]:
        st.markdown("#### 📁 Current Hub Portfolio")
        rows = []
        del_keys = []
        for hid, h in _ss["saved_hubs"].items():
            sout = h["sizing_outputs"]
            rows.append({
                "Hub Name":          h["hub_name"],
                "Site":              h["site_name"],
                "Site Score":        round(h["site_score"], 1),
                "Class":             sout["hub_size_label"],
                "PV (kWp)":          round(sout["pv_field_adjusted_kwp"], 2),
                "Battery (kWh)":     round(sout["battery_capacity_kwh"], 1),
                "Volume (m³)":       round(sout["estimated_storage_volume_m3"], 1),
                "CapEx ($)":         round(sout["total_capital_cost_usd"], 0),
            })
        port_df = pd.DataFrame(rows)
        st.dataframe(port_df, use_container_width=True, hide_index=True)

        # ── Individual hub delete ─────────────────────────────────────────
        del_options = {"— keep all —": None} | {
            h["hub_name"]: hid for hid, h in _ss["saved_hubs"].items()
        }
        dl1, dl2 = st.columns([3, 1])
        with dl1:
            del_choice = st.selectbox("Remove a hub from portfolio:",
                                      list(del_options.keys()), key="hub_del_select")
        with dl2:
            st.write(""); st.write("")
            if st.button("🗑 Remove selected hub") and del_options[del_choice]:
                hid_to_del = del_options[del_choice]
                del _ss["saved_hubs"][hid_to_del]
                _ss["hub_allocations"].pop(hid_to_del, None)
                _ss["hub_impact_outputs"].pop(hid_to_del, None)
                st.rerun()

        if st.button("🗑 Clear entire portfolio"):
            _ss["saved_hubs"] = {}
            _ss["hub_allocations"] = {}
            _ss["hub_impact_outputs"] = {}
            st.rerun()
    else:
        st.info("No hubs saved yet. Design a hub above and click **Add to Portfolio**.")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — BOOKING & ALLOCATION
# Section A: Booking Dataset  (CSV upload + manual entry form + combined table)
# Section B: Multi-hub allocation (cross-hub greedy) + per-hub results + charts
# ─────────────────────────────────────────────────────────────────────────────
with TABS[2]:
    n_done_3 = 2 if _ss["saved_hubs"] else (1 if _ss["scored_sites"] is not None else 0)
    utils.pipeline_step_bar(current=3, n_done=n_done_3)
    st.subheader("③ Booking & Allocation")

    if not _ss["saved_hubs"]:
        st.info("Design and save at least one hub in **② Hub Design** first.")
        st.stop()

    # ═════════════════════════════════════════════════════════════════════
    # SECTION A — BOOKING DATASET
    # ═════════════════════════════════════════════════════════════════════
    st.markdown("### 📋 Section A — Booking Dataset")
    st.write("Combine a CSV upload with manually entered rows. "
             "The merged dataset feeds into cross-hub allocation below.")

    # ── A1: CSV upload ────────────────────────────────────────────────────
    with st.expander("📂 Upload booking CSV (optional — sample data used if omitted)", expanded=False):
        booking_upload = st.file_uploader(
            "Columns: booking_id, product_name, category, volume_m3, weight_kg, "
            "storage_duration_days, decay_rate_pct_per_day, value_class [High/Medium/Low], "
            "price_usd_per_kg, cost_overestimate_usd_per_unit_day, cost_underestimate_usd_per_unit_day",
            type="csv", key="booking_upload",
        )
        use_sample = st.checkbox("Use sample bookings CSV as base dataset", value=True,
                                  key="use_sample_bookings")

    try:
        if booking_upload:
            csv_bookings_df = pd.read_csv(booking_upload)
        elif use_sample:
            csv_bookings_df = pd.read_csv("data/sample_bookings.csv")
        else:
            csv_bookings_df = pd.DataFrame(columns=[
                "booking_id","product_name","category","farmer_or_fisher",
                "volume_m3","weight_kg","storage_duration_days",
                "decay_rate_pct_per_day","value_class","price_usd_per_kg",
                "cost_overestimate_usd_per_unit_day","cost_underestimate_usd_per_unit_day",
            ])
    except Exception as e:
        st.error(f"Could not read CSV ({e}). Using sample.")
        csv_bookings_df = pd.read_csv("data/sample_bookings.csv")

    # ── A2: Manual entry form ─────────────────────────────────────────────
    st.markdown("#### ✏️ Add a Booking Manually")
    with st.form("manual_booking_form", clear_on_submit=True):
        mf1, mf2, mf3 = st.columns(3)
        with mf1:
            b_product    = st.text_input("Product name", "Fish (fresh catch)")
            b_category   = st.selectbox("Category", ["Fishery","Produce","Mixed"])
            b_value      = st.selectbox("Value class", ["High","Medium","Low"])
        with mf2:
            b_vol        = st.number_input("Volume (m³)", 0.1, 100.0, 1.0, step=0.1)
            b_wt         = st.number_input("Weight (kg)", 1.0, 10000.0, 150.0, step=10.0)
            b_dur        = st.number_input("Storage duration (days)", 1, 30, 2)
        with mf3:
            b_decay      = st.number_input("Decay rate (%/day)", 0.1, 50.0, 10.0, step=0.5)
            b_price      = st.number_input("Market price ($/kg)", 0.05, 50.0, 1.5, step=0.05)
            b_overest    = st.number_input("Cost of over-estimating ($/unit/day)", 0.0, 10.0, 0.30, step=0.05)
            b_underest   = st.number_input("Cost of under-estimating ($/unit/day)", 0.0, 10.0, 1.50, step=0.05)
        add_submitted = st.form_submit_button("➕ Add booking to list", type="primary")
        if add_submitted:
            bid = f"M{_ss['next_booking_id']:03d}"
            _ss["manual_bookings"].append({
                "booking_id":                         bid,
                "product_name":                       b_product,
                "category":                           b_category,
                "farmer_or_fisher":                   "Manual entry",
                "volume_m3":                          round(b_vol, 2),
                "weight_kg":                          round(b_wt, 1),
                "storage_duration_days":              int(b_dur),
                "decay_rate_pct_per_day":             round(b_decay, 2),
                "value_class":                        b_value,
                "price_usd_per_kg":                   round(b_price, 2),
                "cost_overestimate_usd_per_unit_day": round(b_overest, 2),
                "cost_underestimate_usd_per_unit_day":round(b_underest, 2),
            })
            _ss["next_booking_id"] += 1
            st.success(f"Booking {bid} added.")

    # ── A3: Show / manage manual rows ─────────────────────────────────────
    if _ss["manual_bookings"]:
        st.markdown(f"**{len(_ss['manual_bookings'])} manually added booking(s):**")
        manual_df_show = pd.DataFrame(_ss["manual_bookings"])
        st.dataframe(manual_df_show, use_container_width=True, hide_index=True)

        rm_options = ["— keep all —"] + [b["booking_id"] for b in _ss["manual_bookings"]]
        rm1, rm2 = st.columns([3, 1])
        with rm1:
            rm_sel = st.selectbox("Remove a manually added booking:", rm_options,
                                   key="remove_manual_booking")
        with rm2:
            st.write(""); st.write("")
            if st.button("🗑 Remove") and rm_sel != "— keep all —":
                _ss["manual_bookings"] = [b for b in _ss["manual_bookings"]
                                           if b["booking_id"] != rm_sel]
                st.rerun()
        if st.button("🗑 Clear all manual bookings"):
            _ss["manual_bookings"] = []
            st.rerun()

    # ── A4: Merged dataset ────────────────────────────────────────────────
    manual_df = pd.DataFrame(_ss["manual_bookings"]) if _ss["manual_bookings"] else pd.DataFrame()
    bookings_df = pd.concat([csv_bookings_df, manual_df], ignore_index=True) if not manual_df.empty else csv_bookings_df.copy()
    _ss["bookings_df"] = bookings_df

    n_csv    = len(csv_bookings_df)
    n_manual = len(_ss["manual_bookings"])
    st.info(f"**Total booking dataset: {len(bookings_df)} rows** "
            f"({n_csv} from CSV, {n_manual} manually added)")

    with st.expander("Preview combined booking dataset", expanded=False):
        st.dataframe(bookings_df, use_container_width=True, hide_index=True)

    # ═════════════════════════════════════════════════════════════════════
    # SECTION B — MULTI-HUB ALLOCATION
    # ═════════════════════════════════════════════════════════════════════
    st.markdown("---\n### 🔄 Section B — Cross-Hub Allocation")
    st.write(
        "Bookings are assigned across **all hubs simultaneously** using a priority-first, "
        "quality-first rule: the highest-priority booking goes to the highest-scored hub "
        "that has capacity for it. If a hub is full, the booking moves to the next best hub. "
        "This simulates the CoolShare coordinator's role as a neutral allocator."
    )

    # Hub capacity summary (inherited, read-only)
    hub_cap_rows = []
    for hid, hub in _ss["saved_hubs"].items():
        sout = hub["sizing_outputs"]
        hub_cap_rows.append({
            "Hub":             hub["hub_name"],
            "Site Score":      round(hub["site_score"], 1),
            "Vol capacity (m³)": round(sout["estimated_storage_volume_m3"], 1),
            "Wt capacity (kg)":  round(hub["sizing_inputs"]["max_daily_product_loading_kg"], 0),
            "Hub Class":       sout["hub_size_label"],
        })
    utils.inherited_block(
        [(f"{r['Hub']}",
          f"Vol: {r['Vol capacity (m³)']} m³  |  Wt: {r['Wt capacity (kg)']:.0f} kg  "
          f"|  Score: {r['Site Score']}")
         for r in sorted(hub_cap_rows, key=lambda x: x["Site Score"], reverse=True)],
        source_label="Hub Design (capacities locked)"
    )

    # ── Run multi-hub allocation ──────────────────────────────────────────
    multi_result = allocation.allocate_bookings_multi_hub(bookings_df, _ss["saved_hubs"])

    # Store per-hub results in session state (same format as before — Impact/Dashboard unchanged)
    for hid, hub_result in multi_result["hub_tables"].items():
        _ss["hub_allocations"][hid] = hub_result

    global_table = multi_result["global_table"]
    n_waitlisted_global = multi_result["n_waitlisted"]

    # ── Global assignment overview ────────────────────────────────────────
    st.markdown("#### 🌐 Global Booking Assignment")
    if n_waitlisted_global > 0:
        st.markdown(utils.status_badge_html(
            f"⚠ {n_waitlisted_global} booking(s) waitlisted — total hub capacity insufficient",
            "critical"), unsafe_allow_html=True)
    else:
        st.markdown(utils.status_badge_html(
            "✓ All bookings allocated across the hub portfolio", "ok"), unsafe_allow_html=True)

    if not global_table.empty:
        global_disp_cols = ["booking_id","product_name","value_class",
                            "decay_rate_pct_per_day","priority_score",
                            "volume_m3","weight_kg",
                            "assigned_hub_name","global_status","allocation_reason"]
        available_cols = [c for c in global_disp_cols if c in global_table.columns]
        st.dataframe(global_table[available_cols].round(2),
                     use_container_width=True, hide_index=True)
        utils.df_to_csv_download(global_table, "multi_hub_allocation.csv",
                                 "⬇ Download global assignment (CSV)")

    # ── Per-hub results ───────────────────────────────────────────────────
    st.markdown("#### 🏭 Per-Hub Breakdown")
    combined_alloc = []

    for hid, hub in _ss["saved_hubs"].items():
        sout     = hub["sizing_outputs"]
        cap_vol  = sout["estimated_storage_volume_m3"]
        cap_wt   = hub["sizing_inputs"]["max_daily_product_loading_kg"]
        hub_res  = multi_result["hub_tables"].get(hid, {})
        alloc_sum = hub_res.get("summary", {})
        alloc_tbl = hub_res.get("allocation_table", pd.DataFrame())

        if not alloc_sum:
            continue

        st.markdown(f"---\n##### 🏭 {hub['hub_name']}")

        badge_lbl = (f"⚠ Overload — {alloc_sum['n_allocated']} allocated, hub at capacity"
                     if alloc_sum["overload"]
                     else f"✓ {alloc_sum['n_allocated']} bookings assigned to this hub")
        badge_st  = "warning" if alloc_sum["overload"] else "ok"
        st.markdown(utils.status_badge_html(badge_lbl, badge_st), unsafe_allow_html=True)

        m1, m2, m3, m4 = st.columns(4)
        with m1: utils.metric_card("Volume Fill Rate",
                                    f"{alloc_sum['fill_rate_volume_pct']:.0f}%")
        with m2: utils.metric_card("Weight Fill Rate",
                                    f"{alloc_sum['fill_rate_weight_pct']:.0f}%")
        with m3: utils.metric_card("Bookings Assigned",
                                    str(alloc_sum["n_allocated"]))
        with m4: utils.metric_card("Mis-sizing Cost",
                                    f"${alloc_sum['cost_overestimate_total_usd']+alloc_sum['cost_underestimate_total_usd']:,.0f}/day")

        if not alloc_tbl.empty:
            disp_cols = [c for c in ["booking_id","product_name","category","value_class",
                                     "decay_rate_pct_per_day","priority_score","volume_m3",
                                     "weight_kg","status","allocation_reason"]
                         if c in alloc_tbl.columns]
            with st.expander(f"Assignment detail — {hub['hub_name']}", expanded=False):
                st.dataframe(alloc_tbl[disp_cols].round(2),
                             use_container_width=True, hide_index=True)
                utils.df_to_csv_download(alloc_tbl,
                                         f"alloc_{hub['hub_name'][:18]}.csv",
                                         "⬇ Download (CSV)")

        # Stacked bar — volume & weight utilisation for this hub
        fig_hu = go.Figure()
        fig_hu.add_trace(go.Bar(
            name="Used",
            x=["Volume (m³)", "Weight (kg)"],
            y=[alloc_sum["allocated_volume_m3"], alloc_sum["allocated_weight_kg"]],
            marker_color=config.COLORS["teal_deep"],
            text=[f"{alloc_sum['allocated_volume_m3']:.1f}",
                  f"{alloc_sum['allocated_weight_kg']:.0f}"],
            textposition="inside", textfont=dict(color="white"),
        ))
        fig_hu.add_trace(go.Bar(
            name="Remaining",
            x=["Volume (m³)", "Weight (kg)"],
            y=[max(cap_vol - alloc_sum["allocated_volume_m3"], 0),
               max(cap_wt  - alloc_sum["allocated_weight_kg"], 0)],
            marker_color=config.COLORS["border"],
        ))
        fig_hu.update_layout(
            barmode="stack", height=240,
            title=f"Capacity Utilisation — {hub['hub_name']}",
            plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=40),
            legend=dict(orientation="h", y=-0.25),
        )
        st.plotly_chart(fig_hu, use_container_width=True)

        combined_alloc.append({
            "Hub":             hub["hub_name"],
            "Vol cap (m³)":   round(cap_vol, 1),
            "Wt cap (kg)":    round(cap_wt, 0),
            "Vol used (m³)":  round(alloc_sum["allocated_volume_m3"], 1),
            "Wt used (kg)":   round(alloc_sum["allocated_weight_kg"], 0),
            "Vol fill %":     round(alloc_sum["fill_rate_volume_pct"], 0),
            "Wt fill %":      round(alloc_sum["fill_rate_weight_pct"], 0),
            "Assigned":       alloc_sum["n_allocated"],
            "Overload":       "⚠" if alloc_sum["overload"] else "✓",
        })

    # ── Portfolio comparison charts ───────────────────────────────────────
    if len(combined_alloc) > 1:
        st.markdown("---\n#### 📊 Portfolio Comparison Charts")
        cdf = pd.DataFrame(combined_alloc)

        cc1, cc2 = st.columns(2)
        with cc1:
            # Grouped bar: volume capacity vs volume used per hub
            fig_cv = go.Figure()
            fig_cv.add_trace(go.Bar(
                name="Capacity (m³)",
                x=cdf["Hub"], y=cdf["Vol cap (m³)"],
                marker_color=config.COLORS["border"],
            ))
            fig_cv.add_trace(go.Bar(
                name="Used (m³)",
                x=cdf["Hub"], y=cdf["Vol used (m³)"],
                marker_color=config.COLORS["teal_deep"],
            ))
            fig_cv.update_layout(
                barmode="group", title="Volume: Capacity vs Used (m³)",
                plot_bgcolor="white", paper_bgcolor="white", height=300,
                xaxis_tickangle=-20, legend=dict(orientation="h", y=-0.3),
            )
            st.plotly_chart(fig_cv, use_container_width=True)

        with cc2:
            # Grouped bar: weight capacity vs weight used per hub
            fig_cw = go.Figure()
            fig_cw.add_trace(go.Bar(
                name="Capacity (kg)",
                x=cdf["Hub"], y=cdf["Wt cap (kg)"],
                marker_color=config.COLORS["border"],
            ))
            fig_cw.add_trace(go.Bar(
                name="Used (kg)",
                x=cdf["Hub"], y=cdf["Wt used (kg)"],
                marker_color=config.COLORS["sky_blue"],
            ))
            fig_cw.update_layout(
                barmode="group", title="Weight: Capacity vs Used (kg)",
                plot_bgcolor="white", paper_bgcolor="white", height=300,
                xaxis_tickangle=-20, legend=dict(orientation="h", y=-0.3),
            )
            st.plotly_chart(fig_cw, use_container_width=True)

        # Fill-rate comparison bar
        fig_fr = go.Figure()
        fig_fr.add_trace(go.Bar(
            name="Volume fill %",
            x=cdf["Hub"], y=cdf["Vol fill %"],
            marker_color=config.COLORS["teal_deep"],
            text=cdf["Vol fill %"].astype(str) + "%",
            textposition="outside",
        ))
        fig_fr.add_trace(go.Bar(
            name="Weight fill %",
            x=cdf["Hub"], y=cdf["Wt fill %"],
            marker_color=config.COLORS["amber"],
            text=cdf["Wt fill %"].astype(str) + "%",
            textposition="outside",
        ))
        fig_fr.update_layout(
            barmode="group", title="Fill Rate Comparison across All Hubs (%)",
            plot_bgcolor="white", paper_bgcolor="white", height=300,
            xaxis_tickangle=-20, yaxis_range=[0, 115],
            legend=dict(orientation="h", y=-0.3),
        )
        st.plotly_chart(fig_fr, use_container_width=True)

        # Bookings count per hub
        fig_bk = go.Figure(go.Bar(
            x=cdf["Hub"], y=cdf["Assigned"],
            marker_color=[config.COLORS["status_ok"] if o == "✓"
                          else config.COLORS["status_warning"]
                          for o in cdf["Overload"]],
            text=cdf["Assigned"], textposition="outside",
        ))
        fig_bk.update_layout(
            title="Number of Bookings Assigned per Hub",
            plot_bgcolor="white", paper_bgcolor="white", height=280,
            xaxis_tickangle=-20,
        )
        st.plotly_chart(fig_bk, use_container_width=True)

    # ── Combined summary table ────────────────────────────────────────────
    st.markdown("---\n#### 📋 Combined Portfolio Allocation Summary")
    if combined_alloc:
        st.dataframe(pd.DataFrame(combined_alloc), use_container_width=True, hide_index=True)
    st.caption(
        "Algorithm: bookings sorted by priority (decay rate × value multiplier × risk-asymmetry ratio). "
        "Hubs sorted by site score (best hub gets first offer). Each booking assigned to the "
        "highest-quality hub with enough remaining capacity. If no hub fits → waitlisted."
    )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — IMPACT ANALYSIS   (inherited volume/cost/solar; market params editable)
# ─────────────────────────────────────────────────────────────────────────────
with TABS[3]:
    n_done_4 = 2 if _ss["saved_hubs"] else (1 if _ss["scored_sites"] is not None else 0)
    utils.pipeline_step_bar(current=4, n_done=n_done_4)
    st.subheader("④ Impact Analysis")

    if not _ss["saved_hubs"]:
        st.info("Design and save at least one hub in **② Hub Design** first.")
        st.stop()

    st.write("Monthly volume, capital cost, and utilized solar energy are inherited from each hub's design. "
             "Set the **market & operational parameters** once — they apply uniformly across all hubs "
             "so you can compare apples to apples.")

    # ── Editable market params (global, stored in session) ───────────────
    mkt = _ss["impact_mkt"]
    with st.expander("⚙ Market & Operational Parameters *(editable — applied to all hubs)*", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            mkt["baseline_spoilage_pct"] = st.slider(
                "Baseline Spoilage Rate (%, no hub)", 0.0, 80.0, mkt["baseline_spoilage_pct"])
            mkt["coldhub_spoilage_pct"]  = st.slider(
                "Cold-Hub Spoilage Rate (%, with hub)", 0.0, 80.0, mkt["coldhub_spoilage_pct"])
        with c2:
            mkt["market_price_usd_per_kg"] = st.number_input(
                "Market Price ($/kg)", 0.05, 20.0, mkt["market_price_usd_per_kg"], step=0.05)
            mkt["grid_diesel_emission_factor_kg_co2_per_kwh"] = st.number_input(
                "Grid/Diesel Emission Factor (kg CO₂/kWh)", 0.1, 1.5,
                mkt["grid_diesel_emission_factor_kg_co2_per_kwh"], step=0.05)
        with c3:
            mkt["monthly_om_depreciation_usd"]   = st.number_input(
                "Monthly O&M & Depreciation ($)", 0.0, 5000.0, mkt["monthly_om_depreciation_usd"], step=10.0)
            mkt["energy_cost_savings_usd_month"] = st.number_input(
                "Energy Cost Savings ($/month)", 0.0, 5000.0, mkt["energy_cost_savings_usd_month"], step=10.0)
        with st.expander("Refrigerant parameters", expanded=False):
            rc1, rc2, rc3 = st.columns(3)
            with rc1:
                mkt["refrigerant_charge_kg"] = st.number_input(
                    "Refrigerant Charge (kg)", 0.1, 20.0, mkt["refrigerant_charge_kg"], step=0.1)
            with rc2:
                mkt["refrigerant_gwp"] = st.number_input(
                    "Refrigerant GWP (100-yr)", 1.0, 5000.0, mkt["refrigerant_gwp"], step=10.0)
            with rc3:
                mkt["refrigerant_leak_rate_pct_year"] = st.slider(
                    "Leakage Rate (%/year)", 0.0, 30.0, mkt["refrigerant_leak_rate_pct_year"])
    _ss["impact_mkt"] = mkt

    # ── Per-hub impact (inherited inputs) ────────────────────────────────
    all_impact_rows = []
    for hid, hub in _ss["saved_hubs"].items():
        sout = hub["sizing_outputs"]
        sinp = hub["sizing_inputs"]

        monthly_vol    = sinp["max_daily_product_loading_kg"] * 30
        capex          = sout["total_capital_cost_usd"]
        solar_monthly  = sout["daily_energy_demand_kwh"] * 30 * config.SOLAR_FRACTION

        st.markdown(f"---\n#### 🏭 {hub['hub_name']}")
        utils.inherited_block([
            ("Monthly Input Volume",       f"{monthly_vol:,.0f} kg  = {sinp['max_daily_product_loading_kg']:.0f} kg/day × 30"),
            ("Total Capital Cost",         f"${capex:,.0f}"),
            ("Utilized Solar (est.)",      f"{solar_monthly:,.0f} kWh/mo = daily demand × 30 × {config.SOLAR_FRACTION:.0%} solar fraction"),
        ], source_label="Hub Design")

        impact_inputs = {
            "monthly_input_volume_kg":                    monthly_vol,
            "total_capital_cost_usd":                     capex,
            "utilized_solar_energy_kwh_month":            solar_monthly,
            **mkt,
        }
        imp_out = impact.run_impact(impact_inputs)
        _ss["hub_impact_outputs"][hid] = imp_out

        r1 = st.columns(4)
        payback_txt = f"{imp_out['payback_months']:.1f} mo" if imp_out["payback_months"] != float("inf") else "N/A"
        with r1[0]: utils.metric_card("Food Saved",       f"{imp_out['spoilage_avoided_kg']:.0f} kg/mo")
        with r1[1]: utils.metric_card("Income Protected", f"${imp_out['income_protected_usd']:,.0f}/mo")
        with r1[2]: utils.metric_card("Net CO₂ Avoided",  f"{imp_out['net_co2_avoided_kg']:.0f} kg/mo")
        with r1[3]: utils.metric_card("Simple Payback",   payback_txt)

        ba = imp_out["before_after"]
        bc1, bc2 = st.columns(2)
        with bc1:
            fig_sp = go.Figure(go.Bar(
                x=["Before (no hub)", "After (cold hub)"],
                y=[ba["spoilage_pct"]["before"], ba["spoilage_pct"]["after"]],
                marker_color=[config.COLORS["status_critical"], config.COLORS["status_ok"]],
                text=[f"{ba['spoilage_pct']['before']:.1f}%", f"{ba['spoilage_pct']['after']:.1f}%"],
                textposition="outside",
            ))
            fig_sp.update_layout(title="Spoilage Rate (%)", height=260,
                                 plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig_sp, use_container_width=True, key=f"spoilage_chart_{str(hid)}")
        with bc2:
            fig_ls = go.Figure(go.Bar(
                x=["Before (no hub)", "After (cold hub)"],
                y=[ba["loss_usd_month"]["before"], ba["loss_usd_month"]["after"]],
                marker_color=[config.COLORS["status_critical"], config.COLORS["status_ok"]],
                text=[f"${ba['loss_usd_month']['before']:,.0f}", f"${ba['loss_usd_month']['after']:,.0f}"],
                textposition="outside",
            ))
            fig_ls.update_layout(title="Monthly Spoilage Loss ($)", height=260,
                                 plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig_ls, use_container_width=True, key=f"loss_chart_{str(hid)}")

        roi = imp_out["simple_roi_pct_year"]
        eff  = imp_out["income_protected_usd"] / capex * 100 if capex > 0 else 0
        all_impact_rows.append({
            "Hub":                hub["hub_name"],
            "CapEx ($)":          round(capex, 0),
            "Food Saved (kg/mo)": round(imp_out["spoilage_avoided_kg"], 0),
            "Income Saved ($/mo)":round(imp_out["income_protected_usd"], 0),
            "CO₂ Avoided (kg/mo)":round(imp_out["net_co2_avoided_kg"], 1),
            "Simple ROI (%/yr)":  round(roi, 1),
            "Payback (mo)":       round(imp_out["payback_months"], 1) if imp_out["payback_months"] != float("inf") else "N/A",
            "$ Income / $100 CapEx": round(eff, 2),
        })

    # ── Aggregate portfolio comparison ───────────────────────────────────
    if len(all_impact_rows) > 1:
        st.markdown("---\n#### 📊 Portfolio Impact Comparison *(ranked by Investment Efficiency)*")
        cmp = pd.DataFrame(all_impact_rows).sort_values("$ Income / $100 CapEx", ascending=False)
        st.dataframe(cmp, use_container_width=True, hide_index=True)
        st.caption("Investment Efficiency = monthly income protected ÷ total capital cost × 100.  "
                   "Higher = more $ of food value saved per dollar invested.")

    st.caption("Solar fraction assumption: utilized solar = daily energy demand × 30 days × "
               f"{config.SOLAR_FRACTION:.0%}. Refrigerant CO₂ = Charge × Leak%/yr × GWP / 12.")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — PORTFOLIO DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
with TABS[4]:
    utils.pipeline_step_bar(current=5, n_done=min(4, 1 if _ss["scored_sites"] is not None else 0
                                                        + (2 if _ss["saved_hubs"] else 0)))
    st.subheader("⑤ Portfolio Dashboard")

    scored_sites = _ss["scored_sites"]
    saved_hubs   = _ss["saved_hubs"]
    hub_impacts  = _ss["hub_impact_outputs"]
    hub_allocs   = _ss["hub_allocations"]
    site_weights = _ss["site_weights"]

    if scored_sites is None:
        st.info("Complete **① Site Scoring** first.")
        st.stop()

    # ── Coordinator story ─────────────────────────────────────────────────
    utils.coordinator_story()

    # ── Recommended pilot (top-scored site, linked to hub if saved) ──────
    top_site = scored_sites.iloc[0]
    st.markdown("### 🎯 Recommended Pilot Site")

    # Find a saved hub for the top site (if any)
    top_hub = next(
        (h for h in saved_hubs.values() if h["site_name"] == top_site["site_name"]),
        list(saved_hubs.values())[0] if saved_hubs else None,
    )
    if top_hub:
        imp_out_top  = hub_impacts.get(
            next(k for k, v in saved_hubs.items() if v is top_hub), {}
        ) or {}
        alloc_top = hub_allocs.get(
            next((k for k, v in saved_hubs.items() if v is top_hub), None), {}
        )
        alloc_sum_top = alloc_top.get("summary", {}) if alloc_top else {}

        reco = recommendation.build_recommendation(
            top_site, site_weights, top_hub["sizing_outputs"],
            imp_out_top if imp_out_top else config.IMPACT_DEFAULTS,
        )
        is_top = int(top_site["rank"]) == 1
        utils.recommendation_card(reco, is_top_rank=is_top)

        # Key indicator cards
        st.markdown("### Key Performance Indicators")
        fill_pct = alloc_sum_top.get("fill_rate_volume_pct", 0) if alloc_sum_top else 0
        co2_kg   = imp_out_top.get("net_co2_avoided_kg", 0) if imp_out_top else 0
        spoil_pct = _ss["impact_mkt"].get("coldhub_spoilage_pct", 8)
        pv_now    = utils.simulated_pv_power_kw(top_hub["sizing_outputs"]["pv_field_adjusted_kwp"])

        k1, k2, k3, k4 = st.columns(4)
        fr_st = utils.fill_rate_status(fill_pct)
        sp_st = utils.spoilage_status(spoil_pct)
        co_st = "ok" if co2_kg > 0 else "critical"
        with k1: utils.metric_card("Volume Fill Rate",      f"{fill_pct:.0f}%",     fr_st.upper(), fr_st)
        with k2: utils.metric_card("Net CO₂ Avoided",      f"{co2_kg:.0f} kg/mo",  co_st.upper(), co_st)
        with k3: utils.metric_card("Cold-Hub Spoilage",     f"{spoil_pct:.1f}%",    sp_st.upper(), sp_st)
        with k4: utils.metric_card("Simulated PV (now)",   f"{pv_now:.2f} kW",     "DEMO GAUGE",  "ok")
        st.caption("⚡ Simulated PV uses a daylight sine curve — demo visual, not live telemetry.")

    else:
        st.info("Design and save at least one hub in **② Hub Design** to see a full recommendation.")

    # ── Portfolio comparison table ────────────────────────────────────────
    st.markdown("### 📊 Hub Portfolio — Investment Ranking")
    if saved_hubs:
        port_rows = []
        for hid, hub in saved_hubs.items():
            sout = hub["sizing_outputs"]
            imp  = hub_impacts.get(hid, {})
            alloc_sum = hub_allocs.get(hid, {}).get("summary", {}) or {}
            capex = sout["total_capital_cost_usd"]
            inc   = imp.get("income_protected_usd", 0) if imp else 0
            eff   = inc / capex * 100 if capex > 0 else 0
            port_rows.append({
                "Hub":               hub["hub_name"],
                "Site Score":        round(hub["site_score"], 1),
                "Hub Class":         sout["hub_size_label"],
                "CapEx ($)":         round(capex, 0),
                "PV (kWp)":          round(sout["pv_field_adjusted_kwp"], 2),
                "Battery (kWh)":     round(sout["battery_capacity_kwh"], 1),
                "Food Saved (kg/mo)":round(imp.get("spoilage_avoided_kg", 0), 0) if imp else "—",
                "CO₂ Avoided (kg/mo)":round(imp.get("net_co2_avoided_kg", 0), 1) if imp else "—",
                "Payback (mo)":      (round(imp["payback_months"], 1)
                                      if imp and imp.get("payback_months") != float("inf")
                                      else "—") if imp else "—",
                "Efficiency Score":  round(eff, 2),
                "Vol Fill %":        round(alloc_sum.get("fill_rate_volume_pct", 0), 0),
            })
        port_df = pd.DataFrame(port_rows).sort_values("Efficiency Score", ascending=False)
        st.dataframe(port_df, use_container_width=True, hide_index=True)
        st.caption("Efficiency Score = (monthly income protected / total CapEx) × 100. "
                   "Use this to rank which site deserves the first dollar of investment.")

        # Aggregate totals
        total_capex = sum(h["sizing_outputs"]["total_capital_cost_usd"] for h in saved_hubs.values())
        total_food  = sum(hub_impacts[hid].get("spoilage_avoided_kg", 0)
                          for hid in saved_hubs if hid in hub_impacts)
        total_income = sum(hub_impacts[hid].get("income_protected_usd", 0)
                           for hid in saved_hubs if hid in hub_impacts)
        total_co2   = sum(hub_impacts[hid].get("net_co2_avoided_kg", 0)
                          for hid in saved_hubs if hid in hub_impacts)
        at1, at2, at3, at4 = st.columns(4)
        with at1: utils.metric_card("Total Portfolio CapEx", f"${total_capex:,.0f}")
        with at2: utils.metric_card("Total Food Saved/mo",   f"{total_food/1000:.1f} t")
        with at3: utils.metric_card("Total Income Saved/mo", f"${total_income:,.0f}")
        with at4: utils.metric_card("Total CO₂ Avoided/mo",  f"{total_co2/1000:.2f} t")

    else:
        st.info("No hubs saved yet. Go to **② Hub Design** to build your portfolio.")

    # ── Map ───────────────────────────────────────────────────────────────
    if {"latitude","longitude"}.issubset(scored_sites.columns):
        st.markdown("### 🗺 Candidate Site Map")
        center = [scored_sites["latitude"].mean(), scored_sites["longitude"].mean()]
        m = folium.Map(location=center, zoom_start=6, tiles="CartoDB positron")
        saved_site_names = {h["site_name"] for h in saved_hubs.values()}
        for _, row in scored_sites.iterrows():
            is_top    = row["rank"] == 1
            is_saved  = row["site_name"] in saved_site_names
            clr = (config.COLORS["amber"] if is_top
                   else config.COLORS["teal_deep"] if is_saved
                   else "#94A3B8")
            rad = 13 if is_top else (10 if is_saved else 7)
            pop = (f"{row['site_name']} — score {row['total_score']:.1f} "
                   f"(rank #{int(row['rank'])})")
            if is_saved:
                pop += " · 📁 In portfolio"
            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=rad, popup=pop, tooltip=row["site_name"],
                color=clr, fill=True, fill_opacity=0.85, fill_color=clr,
            ).add_to(m)
        st_folium(m, width=None, height=440, returned_objects=[])
        st.caption("🟡 Gold = recommended pilot  |  🟢 Teal = saved in portfolio  |  ⚪ Gray = candidate")

    # ── Scenario comparison ───────────────────────────────────────────────
    st.markdown("### 💾 Scenario Snapshots")
    st.write("Save the current portfolio state as a named scenario to compare different "
             "weight/parameter configurations side by side.")
    sn1, sn2 = st.columns([3, 1])
    with sn1:
        scen_name = st.text_input("Scenario name",
                                   value=f"Scenario {len(_ss['scenarios'])+1}")
    with sn2:
        st.write(""); st.write("")
        if st.button("📌 Save snapshot"):
            if saved_hubs:
                best = port_rows[0] if saved_hubs else {}
                _ss["scenarios"][scen_name] = {
                    "Sites scored":        len(scored_sites),
                    "Hubs in portfolio":   len(saved_hubs),
                    "Best hub":            best.get("Hub","—"),
                    "Best CapEx ($)":      best.get("CapEx ($)","—"),
                    "Best Efficiency":     best.get("Efficiency Score","—"),
                    "Total CapEx ($)":     round(total_capex, 0) if saved_hubs else "—",
                    "Total Food (kg/mo)":  round(total_food, 0)  if saved_hubs else "—",
                    "Total CO₂ (kg/mo)":  round(total_co2, 0)   if saved_hubs else "—",
                }
                st.success(f"Saved '{scen_name}'.")
            else:
                st.warning("Add hubs to the portfolio before saving a snapshot.")

    if _ss["scenarios"]:
        st.dataframe(pd.DataFrame(_ss["scenarios"]).T, use_container_width=True)
        if st.button("🗑 Clear all snapshots"):
            _ss["scenarios"] = {}; st.rerun()

    # ── Export ────────────────────────────────────────────────────────────
    st.markdown("### ⬇ Export")
    ex1, ex2, ex3 = st.columns(3)
    with ex1:
        if saved_hubs and hub_impacts:
            first_hid = next(iter(saved_hubs))
            top_h     = saved_hubs[first_hid]
            top_imp   = hub_impacts.get(first_hid, config.IMPACT_DEFAULTS)
            top_alloc = hub_allocs.get(first_hid, {}).get("summary",
                        {"fill_rate_volume_pct":0,"n_allocated":0,"n_waitlisted":0})
            reco_pdf  = recommendation.build_recommendation(
                scored_sites.iloc[0], site_weights,
                top_h["sizing_outputs"], top_imp,
            )
            try:
                pdf_bytes = utils.build_pdf_summary(
                    top_h["site_name"], top_h["site_score"],
                    top_h["sizing_outputs"], top_imp, top_alloc,
                    reasons=reco_pdf["reasons"], risks=reco_pdf["risks"],
                )
                st.download_button("⬇ Executive Summary (PDF)", data=pdf_bytes,
                                   file_name="coolshare_summary.pdf", mime="application/pdf")
            except Exception as e:
                st.warning(f"PDF unavailable: {e}")
    with ex2:
        utils.df_to_csv_download(scored_sites, "site_comparison.csv", "⬇ Site Scores (CSV)")
    with ex3:
        if saved_hubs:
            utils.df_to_csv_download(pd.DataFrame(port_rows) if port_rows else pd.DataFrame(),
                                     "portfolio.csv", "⬇ Portfolio (CSV)")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 6 — ASSUMPTIONS
# ─────────────────────────────────────────────────────────────────────────────
with TABS[5]:
    st.subheader("📐 Assumptions & Formulas")
    st.write("Every number used anywhere in the app traces back to a formula listed here. "
             "Defaults are starting points, not locked values.")

    st.markdown("#### 1 · Site Scoring")
    st.markdown("""
- **Solar Irradiance / Beneficiary Density** — min-max scaled 0–100, higher is better.
- **Road Proximity / Max & Avg Temperature** — inverse min-max, lower is better.
- **Aspect** — 100 at true South (180°); falls linearly to 0 at due North.
- **Rainfall** — 100 inside 1,000–2,000 mm/yr band; trapezoidal decay outside it.
- **Total score** = Σ(weight × sub-score), weights auto-normalized to sum to 100%.
""")

    st.markdown("#### 2 · Hub Sizing")
    st.markdown("""
- Cooling load (kWh/day) = `mass × specific_heat × ΔT / 3600 / COP`
- Daily Energy = Cooling load + Standby load
- PV nameplate (kWp) = `Daily Energy / (Peak Sun Hours × Derate)`, then inflated by Temperature Coefficient
- Battery (kWh) = `Daily Energy × Days of Autonomy / DoD`
- Cold Room Volume (m³) = `(Max Loading × Storage Turnover) / Bulk Density`
- Capital Cost = PV + Battery + Refrigeration unit + Install/misc
""")

    st.markdown("#### 3 · Booking & Allocation")
    st.markdown("""
- Priority = `decay_rate(%/day) × value_multiplier × (1 + min(underestimate_cost / overestimate_cost, 10))`
- Value multipliers: High=1.5, Medium=1.0, Low=0.6
- Greedy allocation: highest priority first until volume **or** weight capacity reached; remainder waitlisted.
- Hub capacity inherited directly from Hub Design (volume = estimated cold-room m³; weight = max daily loading kg).
""")

    st.markdown("#### 4 · Impact Analysis")
    st.markdown("""
- Spoilage avoided (kg/mo) = `Monthly Volume × (Baseline% − Cold-hub%)`
- Income protected ($/mo) = `Spoilage avoided × Market price`
- **Assumption A:** Utilized solar = daily energy demand × 30 days × 90% solar fraction  
  *(10% assumed from battery-stored daytime charge, not from grid/diesel)*
- **Assumption B:** Utilized solar displaces grid/diesel 1:1 for emissions accounting.
- CO₂ avoided (energy) = `Solar kWh × Emission factor`
- CO₂ from refrigerant = `Charge × Leak%/yr × GWP / 12`
- Net CO₂ = Energy CO₂ avoided − Refrigerant CO₂
- Simple Payback (mo) = `CapEx / (Total monthly benefit − O&M cost)`
- Investment Efficiency = `Monthly income protected / CapEx × 100`
""")

    st.markdown("#### 5 · Pipeline Data Flow")
    st.markdown("""
- **Site Scoring → Hub Design:** site's `expected_daily_volume_kg` pre-fills Max Daily Loading.
- **Hub Design → Booking:** `estimated_storage_volume_m3` → volume capacity; `max_daily_product_loading_kg` → weight capacity.
- **Hub Design → Impact:** `max_daily_product_loading_kg × 30` → monthly volume; `total_capital_cost_usd` → CapEx; `daily_energy_demand_kwh × 30 × 90%` → utilized solar.
- Downstream values are displayed as **locked / inherited** (amber border) — they cannot be re-entered manually, ensuring the pipeline stays consistent.
""")

    with st.expander("Scoring weights (defaults)"):
        st.json(config.DEFAULT_WEIGHTS)
    with st.expander("Hub sizing defaults"):
        st.json(config.SIZING_DEFAULTS)
    with st.expander("Impact defaults"):
        st.json(config.IMPACT_DEFAULTS)

    st.info("Missing optional site columns (expected_daily_volume_kg, dominant_category, "
            "flood_risk, grid_reliability)? The app falls back to the defaults above and notes it in-UI.")
