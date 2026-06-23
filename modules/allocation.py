"""
allocation.py
-------------
Module 3: Booking & Allocation.

Priority-based greedy allocation -- fully explainable, no optimizer black
box. Each booking gets a priority_score from three transparent ingredients:
decay rate (urgency), product value class (economic stakes), and cost of
underestimating relative to cost of overestimating (asymmetry of risk).
Bookings are then allocated to hub capacity highest-priority-first until
either volume or weight capacity runs out; anything left over is waitlisted
with a plain-language reason.
"""

import pandas as pd
from modules.config import VALUE_CLASS_MULTIPLIER


def compute_priority_score(row) -> float:
    """
    priority = decay_rate(%/day) * value_multiplier * (1 + underestimate_risk_ratio)

    - decay_rate: more perishable => more urgent => higher priority.
    - value_multiplier: High/Medium/Low value class scales the economic stake.
    - underestimate_risk_ratio = cost_underestimate / max(cost_overestimate, 0.01):
      if running out of space for this booking is much costlier than holding
      empty space for it, that pushes priority up further.
    """
    value_mult = VALUE_CLASS_MULTIPLIER.get(row["value_class"], 1.0)
    risk_ratio = row["cost_underestimate_usd_per_unit_day"] / max(row["cost_overestimate_usd_per_unit_day"], 0.01)
    return row["decay_rate_pct_per_day"] * value_mult * (1 + min(risk_ratio, 10))  # cap ratio to avoid runaway scores


def allocate_bookings(bookings_df: pd.DataFrame, capacity_volume_m3: float, capacity_weight_kg: float) -> dict:
    """
    Returns dict with:
      - allocation_table: bookings_df + priority_score, status, reason, running totals
      - summary: fill rates, overload flag, total cost of over/under-estimating
    """
    df = bookings_df.copy()
    df["priority_score"] = df.apply(compute_priority_score, axis=1)
    df = df.sort_values("priority_score", ascending=False).reset_index(drop=True)

    statuses, reasons = [], []
    running_vol, running_wt = 0.0, 0.0
    allocated_vol_col, allocated_wt_col = [], []

    for _, row in df.iterrows():
        fits_volume = running_vol + row["volume_m3"] <= capacity_volume_m3
        fits_weight = running_wt + row["weight_kg"] <= capacity_weight_kg

        if fits_volume and fits_weight:
            running_vol += row["volume_m3"]
            running_wt += row["weight_kg"]
            statuses.append("Allocated")
            reasons.append(
                f"Fits within remaining capacity; priority {row['priority_score']:.1f} "
                f"({row['value_class']} value, {row['decay_rate_pct_per_day']:.1f}%/day decay)."
            )
            allocated_vol_col.append(row["volume_m3"])
            allocated_wt_col.append(row["weight_kg"])
        else:
            limiting = "volume" if not fits_volume else "weight"
            statuses.append("Waitlisted")
            reasons.append(f"Hub {limiting} capacity reached before this booking's turn (priority {row['priority_score']:.1f}).")
            allocated_vol_col.append(0.0)
            allocated_wt_col.append(0.0)

    df["status"] = statuses
    df["allocation_reason"] = reasons
    df["allocated_volume_m3"] = allocated_vol_col
    df["allocated_weight_kg"] = allocated_wt_col

    total_requested_vol = bookings_df["volume_m3"].sum()
    total_requested_wt = bookings_df["weight_kg"].sum()

    fill_rate_volume_pct = min(running_vol / capacity_volume_m3, 1.0) * 100 if capacity_volume_m3 else 0
    fill_rate_weight_pct = min(running_wt / capacity_weight_kg, 1.0) * 100 if capacity_weight_kg else 0

    waitlisted = df[df["status"] == "Waitlisted"]
    allocated = df[df["status"] == "Allocated"]

    # Cost of overestimating: capacity left empty (only meaningful if nothing waitlisted,
    # i.e. true unused slack) -- approximate using allocated bookings' own daily rate as proxy.
    unused_vol = max(capacity_volume_m3 - running_vol, 0)
    cost_overestimate_total = unused_vol * (allocated["cost_overestimate_usd_per_unit_day"].mean() if len(allocated) else 0) \
        if not allocated.empty else 0
    cost_underestimate_total = (waitlisted["volume_m3"] * waitlisted["cost_underestimate_usd_per_unit_day"]).sum()

    overload = len(waitlisted) > 0

    summary = {
        "fill_rate_volume_pct": fill_rate_volume_pct,
        "fill_rate_weight_pct": fill_rate_weight_pct,
        "total_requested_volume_m3": total_requested_vol,
        "total_requested_weight_kg": total_requested_wt,
        "allocated_volume_m3": running_vol,
        "allocated_weight_kg": running_wt,
        "capacity_volume_m3": capacity_volume_m3,
        "capacity_weight_kg": capacity_weight_kg,
        "n_allocated": len(allocated),
        "n_waitlisted": len(waitlisted),
        "overload": overload,
        "cost_overestimate_total_usd": cost_overestimate_total,
        "cost_underestimate_total_usd": cost_underestimate_total,
    }

    return {"allocation_table": df, "summary": summary}
