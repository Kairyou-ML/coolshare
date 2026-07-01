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


# ─────────────────────────────────────────────────────────────────────────────
# MULTI-HUB ALLOCATION
# ─────────────────────────────────────────────────────────────────────────────
def allocate_bookings_multi_hub(bookings_df: pd.DataFrame, hubs_dict: dict) -> dict:
    """
    Cross-hub priority allocation — assigns each booking to the *best available*
    hub rather than running each hub independently.

    Algorithm (fully rule-based, no black box):
    ① Compute priority_score for every booking (same formula as allocate_bookings).
    ② Sort bookings highest-priority-first.
    ③ Sort hubs highest-site-score-first (best hub gets first offer of capacity).
    ④ For each booking: try each hub in order; allocate to the first hub that has
       enough remaining volume AND weight capacity. If no hub fits → waitlisted.
    ⑤ Build per-hub allocation tables (compatible with allocate_bookings output
       format so downstream Impact/Dashboard tabs keep working unchanged).
    ⑥ Build a global assignment table showing every booking's assigned hub.

    Returns:
      "hub_tables":   {hub_id: {"allocation_table": df, "summary": dict}}
      "global_table": DataFrame — all bookings with assigned_hub_name & status
      "n_waitlisted": int
    """
    if bookings_df.empty or not hubs_dict:
        return {"hub_tables": {}, "global_table": pd.DataFrame(), "n_waitlisted": 0}

    df = bookings_df.copy()
    df["priority_score"] = df.apply(compute_priority_score, axis=1)
    df = df.sort_values("priority_score", ascending=False).reset_index(drop=True)

    # Order hubs: best site_score first so the highest-quality hub gets priority.
    ordered_hubs = sorted(
        hubs_dict.items(),
        key=lambda kv: kv[1].get("site_score", 0),
        reverse=True,
    )

    # Remaining capacity trackers (mutated as bookings are assigned)
    rem_vol = {hid: h["sizing_outputs"]["estimated_storage_volume_m3"]
               for hid, h in ordered_hubs}
    rem_wt  = {hid: h["sizing_inputs"]["max_daily_product_loading_kg"]
               for hid, h in ordered_hubs}

    hub_name_map = {hid: h["hub_name"] for hid, h in ordered_hubs}

    # ── Core assignment loop ──────────────────────────────────────────────
    assigned_hub_ids   = []   # parallel to df rows
    assignment_reasons = []

    for _, row in df.iterrows():
        placed = False
        for hid, hub in ordered_hubs:
            if rem_vol[hid] >= row["volume_m3"] and rem_wt[hid] >= row["weight_kg"]:
                rem_vol[hid] -= row["volume_m3"]
                rem_wt[hid]  -= row["weight_kg"]
                assigned_hub_ids.append(hid)
                assignment_reasons.append(
                    f"Assigned to {hub_name_map[hid]} "
                    f"(priority {row['priority_score']:.1f}, "
                    f"{row['value_class']} value, "
                    f"{row['decay_rate_pct_per_day']:.1f}%/day decay)."
                )
                placed = True
                break
        if not placed:
            assigned_hub_ids.append(None)
            cap_note = "; ".join(
                f"{hub_name_map[h]}: {rem_vol[h]:.1f} m³ / {rem_wt[h]:.0f} kg left"
                for h, _ in ordered_hubs
            )
            assignment_reasons.append(
                f"No hub had sufficient remaining capacity "
                f"(needs {row['volume_m3']:.1f} m³ & {row['weight_kg']:.0f} kg). "
                f"Remaining: {cap_note}."
            )

    df["assigned_hub_id"]   = assigned_hub_ids
    # pd.notna needed because pandas .map() converts Python None → np.nan,
    # and `np.nan is not None` evaluates to True (silent bug).
    df["assigned_hub_name"] = df["assigned_hub_id"].map(hub_name_map).fillna("Waitlisted")
    df["global_status"]     = df["assigned_hub_id"].apply(
        lambda x: "Allocated" if pd.notna(x) else "Waitlisted"
    )
    df["allocation_reason"] = assignment_reasons

    # ── Build per-hub tables (same structure as allocate_bookings output) ─
    hub_tables = {}
    for hid, hub in ordered_hubs:
        cap_vol = hub["sizing_outputs"]["estimated_storage_volume_m3"]
        cap_wt  = hub["sizing_inputs"]["max_daily_product_loading_kg"]

        hub_df = df.copy()
        hub_df["status"] = hub_df["assigned_hub_id"].apply(
            lambda x: "Allocated" if x == hid
                      else ("Taken by other hub" if x is not None
                            else "Waitlisted — no hub fit")
        )
        hub_df["allocated_volume_m3"] = hub_df.apply(
            lambda r: r["volume_m3"] if r["assigned_hub_id"] == hid else 0.0, axis=1)
        hub_df["allocated_weight_kg"] = hub_df.apply(
            lambda r: r["weight_kg"] if r["assigned_hub_id"] == hid else 0.0, axis=1)

        alloc_rows = hub_df[hub_df["assigned_hub_id"] == hid]
        alloc_vol  = alloc_rows["volume_m3"].sum()
        alloc_wt   = alloc_rows["weight_kg"].sum()

        n_alloc      = len(alloc_rows)
        n_waitlisted = len(hub_df[hub_df["global_status"] == "Waitlisted"])

        unused_vol = max(cap_vol - alloc_vol, 0)
        cost_over  = unused_vol * (alloc_rows["cost_overestimate_usd_per_unit_day"].mean()
                                   if n_alloc else 0)
        waitlisted_df = df[df["global_status"] == "Waitlisted"]
        cost_under = (waitlisted_df["volume_m3"]
                      * waitlisted_df["cost_underestimate_usd_per_unit_day"]).sum()

        summary = {
            "fill_rate_volume_pct":  min(alloc_vol / cap_vol, 1.0) * 100 if cap_vol else 0,
            "fill_rate_weight_pct":  min(alloc_wt  / cap_wt,  1.0) * 100 if cap_wt  else 0,
            "allocated_volume_m3":   alloc_vol,
            "allocated_weight_kg":   alloc_wt,
            "capacity_volume_m3":    cap_vol,
            "capacity_weight_kg":    cap_wt,
            "n_allocated":           n_alloc,
            "n_waitlisted":          n_waitlisted,
            "overload":              alloc_vol >= cap_vol or alloc_wt >= cap_wt,
            "cost_overestimate_total_usd":  cost_over,
            "cost_underestimate_total_usd": cost_under,
        }
        hub_tables[hid] = {"allocation_table": hub_df, "summary": summary}

    n_waitlisted_global = int((df["global_status"] == "Waitlisted").sum())
    return {
        "hub_tables":   hub_tables,
        "global_table": df,
        "n_waitlisted": n_waitlisted_global,
    }
