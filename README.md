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
| 🔆 Hub Sizing | **Site selector** (defaults to #1 ranked site) + physics-based sizing: cooling load → daily energy demand → PV array (with temperature derate) → battery capacity → backup target → cold-room volume → capital cost. Loading defaults auto-fill from the selected site's own data. |
| 📦 Booking & Allocation | Priority-based greedy allocation of cold-room capacity (volume capacity now defaults from Hub Sizing's computed cold-room volume). Flags overload. |
| 🌍 Impact Calculator | Monthly input volume auto-fills from the selected site's data. Spoilage avoided, income protected, renewable kWh used, net CO₂ avoided, simple payback & ROI, before/after comparison. |
| 📊 Dashboard | **Executive recommendation card** (reasons / risks / expected impact / suggested hub) for the currently-selected site, with an honest note if it isn't the #1-ranked candidate. Key indicator cards, before/after chart, capacity gauge, pilot-site comparison table, map, scenario save/compare, PDF + CSV export. |
| 📐 Assumptions | Every formula and every default value used anywhere in the app, including how the Site→Hub→Impact pipeline and Recommendation Engine work. |

## Site → Hub → Impact pipeline

The site selector at the top of **Hub Sizing** is the single source of truth for the rest of the app:
- It defaults to your #1 ranked site from **Site Scoring**, but you can point it at any candidate.
- **Maximum Daily Product Loading** auto-fills from that site's `expected_daily_volume_kg` column, so a 3,000 kg/day site and a 500 kg/day site genuinely produce different PV/battery/cost results.
- The computed cold-room volume becomes **Booking & Allocation**'s default volume capacity.
- **Impact Calculator**'s monthly input volume auto-fills from the same site's data × 30 days.
- **Dashboard**'s recommendation card always reflects whichever site is currently selected, and tells you plainly if that isn't the top-ranked pick.

All of these are editable defaults, not locks — every auto-filled number is a normal widget you can override.

## Recommendation Engine

The Dashboard's executive recommendation card narrates results that are already computed elsewhere — it doesn't introduce new modeling:
- **Reasons** = the top weighted scoring sub-criteria for that site, plus one line generated from its `dominant_category` column (Fishery/Produce/Mixed) if supplied.
- **Risks** = read directly from `flood_risk` / `grid_reliability` columns if supplied, otherwise inferred from a low rainfall/temperature sub-score (and the UI says so).
- **Expected Impact** / **Suggested Hub** = pulled straight from the Impact Calculator and Hub Sizing outputs for that site.

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

## Deploying

**Streamlit Community Cloud (fastest, free):**
1. Push this folder to a public (or private, with your account) GitHub repo.
2. Go to [share.streamlit.io](https://share.streamlit.io) → "New app".
3. Point it at the repo, branch, and `app.py` as the entry file.
4. Done — Streamlit Cloud installs `requirements.txt` automatically.

**Alternative hosts** (if you outgrow the free tier or need always-on):
- **Render** or **Railway**: add a `Procfile`/start command
  `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`.
- **Hugging Face Spaces**: choose the "Streamlit" SDK when creating a Space,
  push the same files.
- **Docker** anywhere: a minimal Dockerfile would be
  `FROM python:3.11-slim`, `COPY . .`, `RUN pip install -r requirements.txt`,
  `CMD ["streamlit","run","app.py","--server.port=8501","--server.address=0.0.0.0"]`.

## Extending after the hackathon

- `modules/scoring.py` and `modules/impact.py` are pure functions — easy to
  unit test or swap formulas without touching UI code.
- To add a new scoring criterion: add a default weight in `config.py`, a
  `_xxx_score()` helper and one line in `compute_site_scores()`.
- To persist real bookings instead of CSV demo data, swap the
  `pd.read_csv(...)` calls in `app.py` for a database/API call — the
  `allocation.allocate_bookings()` function itself is storage-agnostic.
- The PDF export (`utils.build_pdf_summary`) currently uses fpdf2's built-in
  Helvetica font with Unicode text sanitized to ASCII/latin-1 for safety; for
  a production version, bundling a Unicode TTF (e.g. Noto Sans) would let
  Vietnamese names render with full diacritics in the PDF too.
