# CoolShare Planner

Decision-support & impact-simulation prototype for **Solar-Powered Cold Chain
Micro-Hubs for Smallholder Farmers and Fishery Communities**.

Built for hackathon demo purposes: transparent, formula-based logic (no
black-box ML), editable assumptions, sample data included, runs locally in
minutes.

## What's inside

| Tab | What it does |
|---|---|
| 📍 Site Scoring | Weighted, explainable scoring of candidate micro-hub sites (solar irradiance, aspect, temperature, road proximity, density, rainfall). Adjustable weights, live ranking, top-3 callout. |
| 🔆 Hub Sizing | Physics-based sizing: cooling load → daily energy demand → PV array (with temperature derate) → battery capacity → backup target → capital cost. |
| 📦 Booking & Allocation | Priority-based greedy allocation of cold-room capacity across competing bookings (perishability, value class, over/under-estimation cost). Flags overload. |
| 🌍 Impact Calculator | Spoilage avoided, income protected, renewable kWh used, net CO₂ avoided (energy displacement minus refrigerant leakage), simple payback & ROI, before/after comparison. |
| 📊 Dashboard | Recommended pilot site banner, key indicator cards with status badges, before/after chart, capacity gauge, pilot-site comparison table, map, scenario save/compare, PDF + CSV export. |
| 📐 Assumptions | Every formula and every default value used anywhere in the app, in one place. |

## Architecture

```
coolshare_planner/
├── app.py                  # UI only — layout, widgets, wiring between tabs
├── requirements.txt
├── data/
│   ├── sample_sites.csv     # 8 sample candidate sites (Vietnam coastal/agri provinces)
│   └── sample_bookings.csv  # 10 sample produce/fishery bookings
└── modules/
    ├── config.py            # All default assumptions, weights, costs, color/font design tokens
    ├── scoring.py            # Module 1 — site scoring formulas
    ├── sizing.py              # Module 2 — solar cold-hub sizing formulas
    ├── allocation.py         # Module 3 — booking & allocation priority logic
    ├── impact.py              # Module 4 — economic/environmental impact formulas
    └── utils.py                # CSS theme, status badges, CSV/PDF export, simulated PV gauge
```

Design choice: **calculation logic and UI are fully separated.** Every
number-producing function in `modules/` is a plain Python function that
takes a dict of inputs and returns a dict of outputs — no Streamlit
dependency, no hidden state. That means:
- Every formula is unit-testable on its own (see "Verifying it works" below).
- Anything in `modules/config.py` is the single source of truth for default
  assumptions — change a number once, it updates everywhere (sliders,
  calculations, and the **Assumptions** tab, which reads `config.py` live).
- `app.py` only ever calls a `run_*()` / `compute_*()` function and renders
  the dict it gets back — there is no calculation buried in UI code.

Visual design: a "Coldhub Teal → Harvest Amber" gradient (cold storage →
solar energy) is used as a recurring signature element across the
recommended-site banner and progress bars, with IBM Plex Mono for data/metric
figures to give the dashboard an instrument-panel feel appropriate to an
engineering decision-support tool.

## Running locally

Requires Python 3.10+.

```bash
cd coolshare_planner
pip install -r requirements.txt
streamlit run app.py
```

Then open the URL Streamlit prints (usually `http://localhost:8501`).
The app works immediately with bundled sample data — no setup required for
a first demo. Use the file-uploaders in the Site Scoring / Booking &
Allocation tabs to swap in your own CSVs (the app validates required columns
and falls back to sample data with an on-screen warning if something's
missing).

### Verifying it works (optional, for judges/devs who want to confirm the logic)

```bash
python3 -c "
from modules import config, sizing, impact, allocation
print(sizing.run_sizing(config.SIZING_DEFAULTS))
print(impact.run_impact(config.IMPACT_DEFAULTS))
"
```

This calls the calculation modules directly with zero UI — useful for
confirming the math independently of Streamlit.

## CSV schemas

**Sites** (`data/sample_sites.csv`): `site_id, site_name, region, latitude,
longitude, aspect_deg, solar_irradiance_kwh_m2_day, max_temp_c, avg_temp_c,
proximity_road_km, density_people_km2, rainfall_mm_year`

**Bookings** (`data/sample_bookings.csv`): `booking_id, product_name,
category, volume_m3, weight_kg, storage_duration_days, decay_rate_pct_per_day,
value_class [High/Medium/Low], price_usd_per_kg,
cost_overestimate_usd_per_unit_day, cost_underestimate_usd_per_unit_day`

  Vietnamese names render with full diacritics in the PDF too.
