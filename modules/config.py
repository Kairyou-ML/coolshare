"""
config.py
---------
Single source of truth for default assumptions, constants and visual design
tokens used across CoolShare Planner. Centralizing these here means every
number the judges see in the UI traces back to one editable place, and the
"Assumptions" tab can simply print this file's contents.
"""

# ----------------------------------------------------------------------------
# DESIGN TOKENS  (used by utils.inject_css)
# ----------------------------------------------------------------------------
COLORS = {
    "teal_deep":   "#0E3B36",   # primary / nav / headers   ("Coldhub Teal")
    "amber":       "#E8A33D",   # accent / solar / highlight ("Harvest Amber")
    "sky_blue":    "#2E86AB",   # secondary accent (water / fishery)
    "paper":       "#A9E1FC",   # app background (warm paper, not pure white)
    "surface":     "#FFFFFF",   # card surface
    "text_dark":   "#16241F",
    "text_muted":  "#5B6B66",
    "status_ok":       "#3F8F5C",   # Normal
    "status_warning":  "#D98C2B",   # Warning
    "status_critical": "#C0392B",   # Critical
    "border":      "#E2DFD3",
}

FONT_DISPLAY = "'Space Grotesk', sans-serif"
FONT_BODY    = "'IBM Plex Sans', sans-serif"
FONT_MONO    = "'IBM Plex Mono', monospace"

# ----------------------------------------------------------------------------
# MODULE 1 — SITE SCORING DEFAULTS
# ----------------------------------------------------------------------------
DEFAULT_WEIGHTS = {
    "solar_irradiance":   25,
    "proximity_road":     20,
    "density":            20,
    "aspect":             10,
    "max_temp":           10,
    "avg_temp":            8,
    "rainfall":            7,
}  # must sum to 100 (UI re-normalizes if user changes sliders)

IDEAL_ASPECT_DEG = 180     # true South — best year-round solar exposure (N. hemisphere)
IDEAL_RAINFALL_RANGE_MM = (1000, 2000)  # enough water access, low flood/road-washout risk

# ----------------------------------------------------------------------------
# MODULE 2 — SOLAR COLD-HUB SIZING DEFAULTS
# ----------------------------------------------------------------------------
SIZING_DEFAULTS = {
    "max_daily_product_loading_kg": 500.0,   # kg of fresh produce/fish loaded per day
    "intake_temp_c": 32.0,                   # ambient temp of incoming product
    "target_storage_temp_c": 4.0,            # cold room set-point
    "specific_heat_kj_kgC": 3.6,              # avg specific heat of fresh produce/fish
    "cop": 2.5,                              # coefficient of performance of refrigeration unit
    "standby_load_kwh_day": 4.0,             # lighting, fans, controller, door-open losses
    "days_of_autonomy": 1.5,                 # days battery must cover with zero sun
    "battery_dod_pct": 80.0,                 # usable depth of discharge
    "peak_sun_hours": 5.0,                   # PSH for the region
    "system_derate_pct": 80.0,               # wiring, inverter, dust, mismatch losses
    "temp_coeff_pct_per_C": 0.4,             # PV power loss per °C above 25°C ref
    "backup_requirement_pct": 20.0,          # % of daily demand to size diesel/grid backup for
    "cost_pv_usd_per_wp": 0.45,
    "cost_battery_usd_per_kwh": 250.0,
    "cost_refrigeration_unit_usd": 3500.0,
    "cost_install_misc_usd": 1500.0,
}

HUB_SIZE_BANDS = [
    # (max daily loading kg, label)
    (150,  "Micro Hub (≤150 kg/day)"),
    (500,  "Small Hub (≤500 kg/day)"),
    (1500, "Medium Hub (≤1,500 kg/day)"),
    (float("inf"), "Large Hub (>1,500 kg/day)"),
]

# ----------------------------------------------------------------------------
# MODULE 3 — BOOKING & ALLOCATION DEFAULTS
# ----------------------------------------------------------------------------
VALUE_CLASS_MULTIPLIER = {"High": 1.5, "Medium": 1.0, "Low": 0.6}

ALLOCATION_DEFAULTS = {
    "capacity_volume_m3": 12.0,
    "capacity_weight_kg": 1500.0,
}

# ----------------------------------------------------------------------------
# MODULE 4 — IMPACT CALCULATOR DEFAULTS
# ----------------------------------------------------------------------------
IMPACT_DEFAULTS = {
    "monthly_input_volume_kg": 12000.0,
    "baseline_spoilage_pct": 30.0,
    "coldhub_spoilage_pct": 8.0,
    "market_price_usd_per_kg": 0.55,
    "utilized_solar_energy_kwh_month": 450.0,
    "grid_diesel_emission_factor_kg_co2_per_kwh": 0.70,   # diesel genset typical
    "refrigerant_charge_kg": 1.2,
    "refrigerant_gwp": 2088.0,     # R134a GWP (100-yr)
    "refrigerant_leak_rate_pct_year": 8.0,
    "total_capital_cost_usd": 9000.0,
    "monthly_om_depreciation_usd": 120.0,
    "energy_cost_savings_usd_month": 90.0,
}

# ----------------------------------------------------------------------------
# DASHBOARD THRESHOLDS
# ----------------------------------------------------------------------------
FILL_RATE_THRESHOLDS = {"warning": 60, "critical_low": 30, "critical_high": 95}
SPOILAGE_THRESHOLDS = {"ok": 10, "warning": 20}  # % spoilage rate
