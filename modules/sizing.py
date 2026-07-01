"""
sizing.py
---------
Module 2: Solar Cold-Hub Sizing.

All formulas are standard, textbook refrigeration / PV sizing relations.
Nothing here is fitted or learned -- every output line traces to one
explicit equation, shown to the user in the "Assumptions" tab and inline
as captions.
"""

from modules.config import HUB_SIZE_BANDS


def compute_cooling_load_kwh_day(max_daily_product_loading_kg, specific_heat_kj_kgC,
                                  intake_temp_c, target_storage_temp_c, cop):
    """
    Sensible-heat cooling load to bring incoming product from intake temp
    down to storage temp, converted to electrical energy via COP.

        Q_thermal (kJ/day) = mass(kg) * c_p(kJ/kg·°C) * ΔT(°C)
        E_cooling (kWh/day) = Q_thermal / 3600 / COP
    """
    delta_t = max(intake_temp_c - target_storage_temp_c, 0.0)
    q_thermal_kj = max_daily_product_loading_kg * specific_heat_kj_kgC * delta_t
    e_cooling_kwh = (q_thermal_kj / 3600.0) / cop
    return e_cooling_kwh, delta_t


def compute_pv_size_kwp(daily_energy_demand_kwh, peak_sun_hours, system_derate_pct,
                         temp_coeff_pct_per_C, avg_module_temp_c=45.0, ref_temp_c=25.0):
    """
    Standard PV array sizing:
        PV_kWp (nameplate, STC) = Daily Energy Demand / (PSH * Derate)

    Then we additionally inflate the nameplate size to compensate for the
    real-world power loss caused by hot module temperatures in the field
    (Temperature Coefficient of Power, %/°C above 25°C reference):
        loss_fraction = temp_coeff_%/°C * (avg_module_temp - 25°C) / 100
        PV_kWp_field_adjusted = PV_kWp / (1 - loss_fraction)
    """
    derate = system_derate_pct / 100.0
    pv_nameplate = daily_energy_demand_kwh / (peak_sun_hours * derate)

    loss_fraction = (temp_coeff_pct_per_C / 100.0) * max(avg_module_temp_c - ref_temp_c, 0.0)
    loss_fraction = min(loss_fraction, 0.5)  # sanity clamp, avoid divide blow-up
    pv_field_adjusted = pv_nameplate / (1 - loss_fraction)
    return pv_nameplate, pv_field_adjusted, loss_fraction


def compute_battery_capacity_kwh(daily_energy_demand_kwh, days_of_autonomy, battery_dod_pct):
    """
    Usable battery sizing:
        Battery_kWh = (Daily Demand * Days of Autonomy) / DoD
    DoD < 100% because batteries are not discharged fully to protect lifespan.
    """
    dod = battery_dod_pct / 100.0
    return (daily_energy_demand_kwh * days_of_autonomy) / dod


def compute_backup_energy_kwh(daily_energy_demand_kwh, backup_requirement_pct):
    """Backup generator/grid sizing target, expressed as a % of one day's
    demand the system should be able to cover during extended low-sun runs."""
    return daily_energy_demand_kwh * (backup_requirement_pct / 100.0)


def compute_storage_volume_m3(max_daily_product_loading_kg, storage_turnover_days, bulk_density_kg_m3):
    """
    Estimated physical cold-room volume needed:
        Volume (m3) = (Max Daily Loading(kg) * Storage Turnover(days)) / Bulk Density(kg/m3)

    Storage Turnover = how many days' worth of product is typically sitting in
    the room at once (today's batch may still be there when tomorrow's batch
    arrives). Bulk Density accounts for crates/packaging air gaps, not the
    density of the product itself.
    """
    if bulk_density_kg_m3 <= 0:
        return 0.0
    return (max_daily_product_loading_kg * storage_turnover_days) / bulk_density_kg_m3


def classify_hub_size(max_daily_product_loading_kg):
    for threshold, label in HUB_SIZE_BANDS:
        if max_daily_product_loading_kg <= threshold:
            return label
    return HUB_SIZE_BANDS[-1][1]


def compute_capital_cost(pv_kwp, battery_kwh, cost_pv_usd_per_wp, cost_battery_usd_per_kwh,
                          cost_refrigeration_unit_usd, cost_install_misc_usd):
    pv_cost = pv_kwp * 1000 * cost_pv_usd_per_wp
    battery_cost = battery_kwh * cost_battery_usd_per_kwh
    total = pv_cost + battery_cost + cost_refrigeration_unit_usd + cost_install_misc_usd
    return {
        "pv_cost_usd": pv_cost,
        "battery_cost_usd": battery_cost,
        "refrigeration_unit_usd": cost_refrigeration_unit_usd,
        "install_misc_usd": cost_install_misc_usd,
        "total_capital_cost_usd": total,
    }


def run_sizing(inputs: dict) -> dict:
    """
    Orchestrates the full Module 2 pipeline from raw inputs to all outputs.
    `inputs` keys mirror modules.config.SIZING_DEFAULTS.
    """
    cooling_kwh, delta_t = compute_cooling_load_kwh_day(
        inputs["max_daily_product_loading_kg"],
        inputs["specific_heat_kj_kgC"],
        inputs["intake_temp_c"],
        inputs["target_storage_temp_c"],
        inputs["cop"],
    )
    daily_energy_demand_kwh = cooling_kwh + inputs["standby_load_kwh_day"]

    pv_nameplate, pv_field_adjusted, pv_temp_loss_fraction = compute_pv_size_kwp(
        daily_energy_demand_kwh,
        inputs["peak_sun_hours"],
        inputs["system_derate_pct"],
        inputs["temp_coeff_pct_per_C"],
    )

    battery_kwh = compute_battery_capacity_kwh(
        daily_energy_demand_kwh, inputs["days_of_autonomy"], inputs["battery_dod_pct"]
    )

    backup_kwh = compute_backup_energy_kwh(daily_energy_demand_kwh, inputs["backup_requirement_pct"])

    cost_breakdown = compute_capital_cost(
        pv_field_adjusted, battery_kwh,
        inputs["cost_pv_usd_per_wp"], inputs["cost_battery_usd_per_kwh"],
        inputs["cost_refrigeration_unit_usd"], inputs["cost_install_misc_usd"],
    )

    hub_size_label = classify_hub_size(inputs["max_daily_product_loading_kg"])

    storage_volume_m3 = compute_storage_volume_m3(
        inputs["max_daily_product_loading_kg"], inputs["storage_turnover_days"], inputs["bulk_density_kg_m3"]
    )

    return {
        "cooling_load_kwh_day": cooling_kwh,
        "delta_t_c": delta_t,
        "daily_energy_demand_kwh": daily_energy_demand_kwh,
        "pv_nameplate_kwp": pv_nameplate,
        "pv_field_adjusted_kwp": pv_field_adjusted,
        "pv_temp_loss_fraction": pv_temp_loss_fraction,
        "battery_capacity_kwh": battery_kwh,
        "backup_energy_kwh": backup_kwh,
        "hub_size_label": hub_size_label,
        "estimated_storage_volume_m3": storage_volume_m3,
        **cost_breakdown,
    }
