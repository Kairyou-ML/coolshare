"""
impact.py
---------
Module 4: Impact Calculator.

Every output is a direct, named formula -- no hidden coefficients. Where an
assumption is required (e.g. that utilized solar energy displaces an equal
amount of grid/diesel energy 1:1), it is stated explicitly in the docstring
and surfaced again in the UI's "Assumptions" tab.
"""


def run_impact(inputs: dict) -> dict:
    """
    inputs keys mirror modules.config.IMPACT_DEFAULTS.

    Core formulas:
      spoilage_avoided_kg   = monthly_input_volume_kg * (baseline_spoilage_pct - coldhub_spoilage_pct) / 100
      income_protected_usd  = spoilage_avoided_kg * market_price_usd_per_kg
      grid_diesel_avoided_kwh = utilized_solar_energy_kwh_month
          (ASSUMPTION: solar energy used by the hub is energy that would
          otherwise have been drawn from grid/diesel -- a 1:1 displacement.)
      co2_avoided_energy_kg = grid_diesel_avoided_kwh * grid_diesel_emission_factor_kg_co2_per_kwh
      co2_refrigerant_kg    = refrigerant_charge_kg * (refrigerant_leak_rate_pct_year/100) * GWP / 12
      net_co2_avoided_kg    = co2_avoided_energy_kg - co2_refrigerant_kg
      total_monthly_benefit_usd = income_protected_usd + energy_cost_savings_usd_month
      net_monthly_benefit_usd   = total_monthly_benefit_usd - monthly_om_depreciation_usd
      payback_months        = total_capital_cost_usd / net_monthly_benefit_usd   (if > 0)
      simple_roi_pct_year    = net_monthly_benefit_usd * 12 / total_capital_cost_usd * 100
    """
    spoilage_avoided_kg = inputs["monthly_input_volume_kg"] * (
        (inputs["baseline_spoilage_pct"] - inputs["coldhub_spoilage_pct"]) / 100.0
    )
    income_protected_usd = spoilage_avoided_kg * inputs["market_price_usd_per_kg"]

    grid_diesel_avoided_kwh = inputs["utilized_solar_energy_kwh_month"]
    co2_avoided_energy_kg = grid_diesel_avoided_kwh * inputs["grid_diesel_emission_factor_kg_co2_per_kwh"]

    co2_refrigerant_kg = (
        inputs["refrigerant_charge_kg"]
        * (inputs["refrigerant_leak_rate_pct_year"] / 100.0)
        * inputs["refrigerant_gwp"]
        / 12.0
    )
    net_co2_avoided_kg = co2_avoided_energy_kg - co2_refrigerant_kg

    total_monthly_benefit_usd = income_protected_usd + inputs["energy_cost_savings_usd_month"]
    net_monthly_benefit_usd = total_monthly_benefit_usd - inputs["monthly_om_depreciation_usd"]

    if net_monthly_benefit_usd > 0:
        payback_months = inputs["total_capital_cost_usd"] / net_monthly_benefit_usd
        simple_roi_pct_year = (net_monthly_benefit_usd * 12 / inputs["total_capital_cost_usd"]) * 100
    else:
        payback_months = float("inf")
        simple_roi_pct_year = (net_monthly_benefit_usd * 12 / inputs["total_capital_cost_usd"]) * 100

    baseline_loss_kg = inputs["monthly_input_volume_kg"] * inputs["baseline_spoilage_pct"] / 100.0
    coldhub_loss_kg = inputs["monthly_input_volume_kg"] * inputs["coldhub_spoilage_pct"] / 100.0
    baseline_loss_usd = baseline_loss_kg * inputs["market_price_usd_per_kg"]
    coldhub_loss_usd = coldhub_loss_kg * inputs["market_price_usd_per_kg"]

    return {
        "spoilage_avoided_kg": spoilage_avoided_kg,
        "income_protected_usd": income_protected_usd,
        "kwh_renewable_used": inputs["utilized_solar_energy_kwh_month"],
        "grid_diesel_avoided_kwh": grid_diesel_avoided_kwh,
        "co2_avoided_energy_kg": co2_avoided_energy_kg,
        "co2_refrigerant_kg": co2_refrigerant_kg,
        "net_co2_avoided_kg": net_co2_avoided_kg,
        "total_monthly_benefit_usd": total_monthly_benefit_usd,
        "net_monthly_benefit_usd": net_monthly_benefit_usd,
        "payback_months": payback_months,
        "simple_roi_pct_year": simple_roi_pct_year,
        "before_after": {
            "spoilage_pct": {"before": inputs["baseline_spoilage_pct"], "after": inputs["coldhub_spoilage_pct"]},
            "loss_kg_month": {"before": baseline_loss_kg, "after": coldhub_loss_kg},
            "loss_usd_month": {"before": baseline_loss_usd, "after": coldhub_loss_usd},
        },
    }
