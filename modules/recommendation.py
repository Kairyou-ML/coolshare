"""
recommendation.py
------------------
Module: Pilot Recommendation Engine.

This file does not introduce any new modeling -- it only narrates results
that scoring.py / sizing.py / impact.py already computed, plus a few
qualitative data columns the site CSV may supply (dominant_category,
flood_risk, grid_reliability). If those optional columns are missing, the
engine falls back to deriving a risk note from the numeric sub-scores
already on hand, and says so via the UI caption in app.py.
"""

CRITERION_LABELS = {
    "solar_irradiance": "Highest solar potential among the candidates",
    "proximity_road": "Close to the road/transport network",
    "density": "Serves a high-density farmer/fisher community",
    "aspect": "Near-ideal panel orientation for year-round solar exposure",
    "max_temp": "Moderate peak temperature keeps cooling load manageable",
    "avg_temp": "Moderate average temperature supports refrigeration efficiency",
    "rainfall": "Rainfall within the ideal water-access / low-flood-risk band",
}

CATEGORY_REASON = {
    "Fishery": "Serves highly perishable fishery catch — cold storage has the largest spoilage-reduction upside",
    "Produce": "Serves high-value perishable produce that benefits strongly from consistent cold storage",
    "Mixed": "Serves a mix of perishable produce and fishery catch, broadening hub utilization",
}


def generate_reasons(site_row, weights: dict, max_reasons: int = 3) -> list:
    """
    Re-uses the same weighted sub-score contributions as scoring.explain_top_site,
    but returns them as individual bullet strings (one per criterion) instead of
    one combined sentence, plus an optional qualitative bullet from
    dominant_category if that column was supplied.
    """
    total_w = sum(weights.values()) or 1.0
    norm_w = {k: v / total_w for k, v in weights.items()}
    contributions = {
        crit: site_row.get(f"{crit}_subscore", 0) * norm_w.get(crit, 0)
        for crit in CRITERION_LABELS
    }
    ranked = sorted(contributions.items(), key=lambda x: x[1], reverse=True)

    category = site_row.get("dominant_category")
    has_category_reason = category in CATEGORY_REASON
    n_numeric = (max_reasons - 1) if has_category_reason else max_reasons

    reasons = [CRITERION_LABELS[crit] for crit, _ in ranked[:n_numeric]]
    if has_category_reason:
        reasons.append(CATEGORY_REASON[category])
    return reasons


def generate_risks(site_row) -> list:
    """
    Prefers the qualitative flood_risk / grid_reliability columns when present;
    falls back to flagging a low rainfall/temperature sub-score otherwise.
    """
    risks = []
    flood = site_row.get("flood_risk")
    grid = site_row.get("grid_reliability")

    if flood in ("Medium", "High"):
        risks.append(f"Seasonal flooding risk: {flood}")
    if grid in ("Low", "Medium"):
        risks.append(f"Grid reliability: {grid} — lean on the sized battery/backup for gaps")

    if flood is None and site_row.get("rainfall_subscore", 100) < 50:
        risks.append("Rainfall outside the ideal water-access / flood-risk band")
    if grid is None and site_row.get("max_temp_subscore", 100) < 50:
        risks.append("High peak temperature increases cooling load and panel derate")

    if not risks:
        risks.append("No major site-level risk flagged in the available data")
    return risks


def build_recommendation(site_row, weights: dict, sizing_outputs: dict, impact_outputs: dict) -> dict:
    """Combines scoring + sizing + impact results for ONE site into one
    structured executive-recommendation dict, ready for app.py to render."""
    return {
        "site_name": site_row["site_name"],
        "region": site_row.get("region", ""),
        "score": site_row["total_score"],
        "rank": int(site_row["rank"]),
        "reasons": generate_reasons(site_row, weights),
        "risks": generate_risks(site_row),
        "expected_impact": {
            "food_saved_tonnes": impact_outputs["spoilage_avoided_kg"] / 1000.0,
            "income_protected_usd": impact_outputs["income_protected_usd"],
            "net_co2_avoided_tonnes": impact_outputs["net_co2_avoided_kg"] / 1000.0,
        },
        "suggested_hub": {
            "storage_volume_m3": sizing_outputs.get("estimated_storage_volume_m3"),
            "pv_kwp": sizing_outputs["pv_field_adjusted_kwp"],
            "battery_kwh": sizing_outputs["battery_capacity_kwh"],
            "hub_class": sizing_outputs["hub_size_label"],
            "capital_cost_usd": sizing_outputs["total_capital_cost_usd"],
        },
    }
