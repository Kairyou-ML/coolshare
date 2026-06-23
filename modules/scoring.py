"""
scoring.py
----------
Module 1: Site Scoring.

Every raw variable is converted to a 0-100 "sub-score" using a transparent,
documented rule (min-max scaling, inverse min-max, or a distance-from-ideal
curve). The weighted sum of sub-scores is the final ranking score. No part
of this is a black box -- compute_site_scores() returns the sub-scores
alongside the total so the UI can show exactly why a site ranks where it
does.
"""

import pandas as pd
from modules.config import IDEAL_ASPECT_DEG, IDEAL_RAINFALL_RANGE_MM


def _minmax(series, higher_is_better=True):
    """Scale a numeric series to 0-100. Flat series (no variance) -> all 100."""
    lo, hi = series.min(), series.max()
    if hi == lo:
        return pd.Series([100.0] * len(series), index=series.index)
    scaled = (series - lo) / (hi - lo) * 100.0
    return scaled if higher_is_better else (100.0 - scaled)


def _aspect_score(aspect_deg, ideal=IDEAL_ASPECT_DEG):
    """Score peaks at the ideal aspect (default true South) and falls off
    linearly with circular angular distance. 0° away -> 100, 180° away -> 0."""
    diff = (aspect_deg - ideal).abs() % 360
    diff = diff.apply(lambda d: min(d, 360 - d))  # shortest angular distance
    return (100.0 - (diff / 180.0) * 100.0).clip(lower=0)


def _rainfall_score(rainfall_mm, ideal_range=IDEAL_RAINFALL_RANGE_MM):
    """Trapezoidal curve: full score inside the ideal band (enough water
    access, low flood/road-washout risk); score decays outside it in either
    direction (too dry -> access/dust problems, too wet -> flooding risk)."""
    lo, hi = ideal_range
    span = hi - lo

    def score_one(v):
        if lo <= v <= hi:
            return 100.0
        elif v < lo:
            return max(0.0, 100.0 - (lo - v) / span * 100.0)
        else:
            return max(0.0, 100.0 - (v - hi) / span * 100.0)

    return rainfall_mm.apply(score_one)


SUBSCORE_EXPLANATIONS = {
    "solar_irradiance": "Higher daily irradiance (kWh/m²/day) = more PV yield. Scaled min-max, higher is better.",
    "proximity_road":   "Closer to roads/transit (km) = cheaper logistics & faster spoiled-product turnaround. Inverse min-max, lower distance is better.",
    "density":          "Higher nearby farmer/fisher density = more beneficiaries served per hub. Scaled min-max, higher is better.",
    "aspect":           f"Closer to {IDEAL_ASPECT_DEG}° (true South) = better year-round solar exposure. Distance-from-ideal curve.",
    "max_temp":         "Lower max temperature = less thermal stress on panels & smaller cooling load spikes. Inverse min-max, lower is better.",
    "avg_temp":         "Lower average temperature = better refrigeration COP and less heat ingress. Inverse min-max, lower is better.",
    "rainfall":         f"Best within {IDEAL_RAINFALL_RANGE_MM[0]}-{IDEAL_RAINFALL_RANGE_MM[1]} mm/yr (water access without flood/access risk). Trapezoidal band score.",
}


def compute_site_scores(df: pd.DataFrame, weights: dict) -> pd.DataFrame:
    """
    df must contain columns: aspect_deg, solar_irradiance_kwh_m2_day, max_temp_c,
    avg_temp_c, proximity_road_km, density_people_km2, rainfall_mm_year.

    weights: dict with keys matching SUBSCORE_EXPLANATIONS, values are
    percentages that will be re-normalized to sum to 100 before use.

    Returns a copy of df with one *_subscore column per criterion, plus
    total_score (0-100) and rank (1 = best).
    """
    out = df.copy()

    out["solar_irradiance_subscore"] = _minmax(out["solar_irradiance_kwh_m2_day"], higher_is_better=True)
    out["proximity_road_subscore"]   = _minmax(out["proximity_road_km"], higher_is_better=False)
    out["density_subscore"]          = _minmax(out["density_people_km2"], higher_is_better=True)
    out["aspect_subscore"]           = _aspect_score(out["aspect_deg"])
    out["max_temp_subscore"]         = _minmax(out["max_temp_c"], higher_is_better=False)
    out["avg_temp_subscore"]         = _minmax(out["avg_temp_c"], higher_is_better=False)
    out["rainfall_subscore"]         = _rainfall_score(out["rainfall_mm_year"])

    # Re-normalize weights to sum to 100 so the UI sliders never have to be
    # forced to add up exactly -- the math always stays consistent.
    total_w = sum(weights.values()) or 1.0
    norm_w = {k: v / total_w for k, v in weights.items()}

    out["total_score"] = (
        out["solar_irradiance_subscore"] * norm_w["solar_irradiance"]
        + out["proximity_road_subscore"] * norm_w["proximity_road"]
        + out["density_subscore"] * norm_w["density"]
        + out["aspect_subscore"] * norm_w["aspect"]
        + out["max_temp_subscore"] * norm_w["max_temp"]
        + out["avg_temp_subscore"] * norm_w["avg_temp"]
        + out["rainfall_subscore"] * norm_w["rainfall"]
    )

    out["rank"] = out["total_score"].rank(ascending=False, method="min").astype(int)
    out = out.sort_values("rank").reset_index(drop=True)
    return out


def explain_top_site(scored_df: pd.DataFrame, weights: dict, top_n: int = 1):
    """Return a short, human-readable explanation of why the #1 (or top_n) site
    ranks where it does, naming its two strongest weighted contributors."""
    total_w = sum(weights.values()) or 1.0
    norm_w = {k: v / total_w for k, v in weights.items()}

    explanations = []
    top_rows = scored_df[scored_df["rank"] <= top_n]
    for _, row in top_rows.iterrows():
        contributions = {
            crit: row[f"{crit}_subscore"] * norm_w[crit]
            for crit in norm_w
        }
        ranked_crit = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
        top_two = ranked_crit[:2]
        names = {
            "solar_irradiance": "solar irradiance",
            "proximity_road": "road proximity",
            "density": "beneficiary density",
            "aspect": "panel-friendly aspect",
            "max_temp": "moderate peak temperature",
            "avg_temp": "moderate average temperature",
            "rainfall": "balanced rainfall",
        }
        reason = f"{row['site_name']} (score {row['total_score']:.1f}/100) is driven mainly by strong {names[top_two[0][0]]} and {names[top_two[1][0]]}."
        explanations.append(reason)
    return explanations
