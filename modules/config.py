"""
config.py — single source of truth for all defaults, constants, and design
tokens. The Assumptions tab reads this file directly, so a value only lives
in one place.
"""

# ─────────────────────────────────────────────────────────────────────────────
# DESIGN TOKENS
# ─────────────────────────────────────────────────────────────────────────────
COLORS = {
    # Brand
    "teal_deep":   "#0A3D2B",   # Deep Forest — primary / trust
    "amber":       "#F5A623",   # Solar Gold  — accent / energy
    "sky_blue":    "#1A6B9A",   # Ocean Blue  — secondary / fishery
    # Backgrounds
    "paper":       "#F4F7FA",   # App background (clean slate)
    "surface":     "#FFFFFF",   # Card surface
    "bg_inherit":  "#FFF9ED",   # Inherited/locked field highlight
    # Text
    "text_dark":   "#1A2332",   # Body copy
    "text_muted":  "#6B7A90",   # Labels, captions
    # Borders
    "border":      "#E1E8EF",   # Default border
    "border_inherit": "#F5A623", # Border for inherited fields
    # Status
    "status_ok":       "#0A875B",
    "status_warning":  "#D97706",
    "status_critical": "#DC2626",
}

FONT_DISPLAY = "'Space Grotesk', sans-serif"
FONT_BODY    = "'IBM Plex Sans', sans-serif"
FONT_MONO    = "'IBM Plex Mono', monospace"

# ─────────────────────────────────────────────────────────────────────────────
# MODULE 1 — SITE SCORING
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_WEIGHTS = {
    "solar_irradiance":   25,
    "proximity_road":     20,
    "density":            20,
    "aspect":             10,
    "max_temp":           10,
    "avg_temp":            8,
    "rainfall":            7,
}

IDEAL_ASPECT_DEG        = 180          # true South
IDEAL_RAINFALL_RANGE_MM = (1000, 2000) # water access, low flood risk

# ─────────────────────────────────────────────────────────────────────────────
# MODULE 2 — HUB SIZING
# ─────────────────────────────────────────────────────────────────────────────
SIZING_DEFAULTS = {
    "max_daily_product_loading_kg": 500.0,
    "intake_temp_c":                32.0,
    "target_storage_temp_c":         4.0,
    "specific_heat_kj_kgC":          3.6,
    "cop":                           2.5,
    "standby_load_kwh_day":          4.0,
    "days_of_autonomy":              1.5,
    "battery_dod_pct":              80.0,
    "peak_sun_hours":                5.0,
    "system_derate_pct":            80.0,
    "temp_coeff_pct_per_C":          0.4,
    "backup_requirement_pct":       20.0,
    "cost_pv_usd_per_wp":           0.45,
    "cost_battery_usd_per_kwh":    250.0,
    "cost_refrigeration_unit_usd": 3500.0,
    "cost_install_misc_usd":       1500.0,
    "storage_turnover_days":         2.5,
    "bulk_density_kg_m3":          280.0,
}

HUB_SIZE_BANDS = [
    (150,          "Micro Hub (≤150 kg/day)"),
    (500,          "Small Hub (≤500 kg/day)"),
    (1500,         "Medium Hub (≤1,500 kg/day)"),
    (float("inf"), "Large Hub (>1,500 kg/day)"),
]

# Fraction of daily demand assumed to come from the PV+battery system
# (used to auto-derive utilized_solar for Impact without requiring re-entry)
SOLAR_FRACTION = 0.90

# ─────────────────────────────────────────────────────────────────────────────
# MODULE 3 — BOOKING & ALLOCATION
# ─────────────────────────────────────────────────────────────────────────────
VALUE_CLASS_MULTIPLIER = {"High": 1.5, "Medium": 1.0, "Low": 0.6}

ALLOCATION_DEFAULTS = {
    "capacity_volume_m3":  12.0,
    "capacity_weight_kg": 1500.0,
}

# ─────────────────────────────────────────────────────────────────────────────
# MODULE 4 — IMPACT CALCULATOR
# ─────────────────────────────────────────────────────────────────────────────
IMPACT_DEFAULTS = {
    "monthly_input_volume_kg":                  12000.0,   # overridden by pipeline
    "baseline_spoilage_pct":                       30.0,
    "coldhub_spoilage_pct":                         8.0,
    "market_price_usd_per_kg":                      0.55,
    "utilized_solar_energy_kwh_month":            450.0,   # overridden by pipeline
    "grid_diesel_emission_factor_kg_co2_per_kwh":   0.70,
    "refrigerant_charge_kg":                        1.2,
    "refrigerant_gwp":                           2088.0,
    "refrigerant_leak_rate_pct_year":               8.0,
    "total_capital_cost_usd":                    9000.0,   # overridden by pipeline
    "monthly_om_depreciation_usd":                120.0,
    "energy_cost_savings_usd_month":               90.0,
}

# Market params that are editable in Impact tab (all others are inherited)
IMPACT_MARKET_PARAM_KEYS = [
    "baseline_spoilage_pct",
    "coldhub_spoilage_pct",
    "market_price_usd_per_kg",
    "grid_diesel_emission_factor_kg_co2_per_kwh",
    "refrigerant_charge_kg",
    "refrigerant_gwp",
    "refrigerant_leak_rate_pct_year",
    "monthly_om_depreciation_usd",
    "energy_cost_savings_usd_month",
]

# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD THRESHOLDS
# ─────────────────────────────────────────────────────────────────────────────
FILL_RATE_THRESHOLDS = {"warning": 60, "critical_low": 30, "critical_high": 95}
SPOILAGE_THRESHOLDS  = {"ok": 10, "warning": 20}
