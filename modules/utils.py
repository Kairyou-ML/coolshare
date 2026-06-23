"""
utils.py
--------
Shared helpers: CSS theme injection, status-badge logic for the dashboard
traffic lights, CSV export, a lightweight PDF executive summary, and a
simulated real-time PV power curve (clearly labeled as simulated -- this
is a demo, not a live telemetry feed).
"""

import io
import math
import unicodedata
from datetime import datetime

import streamlit as st

from modules.config import COLORS, FONT_DISPLAY, FONT_BODY, FONT_MONO


def inject_css():
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap');

    .stApp {{
        background-color: {COLORS['paper']};
        font-family: {FONT_BODY};
        color: {COLORS['text_dark']};
    }}
    h1, h2, h3 {{
        font-family: {FONT_DISPLAY};
        color: {COLORS['teal_deep']};
        letter-spacing: -0.01em;
    }}
    .csp-banner {{
        background: linear-gradient(90deg, {COLORS['teal_deep']} 0%, {COLORS['teal_deep']} 60%, {COLORS['amber']} 100%);
        border-radius: 14px;
        padding: 22px 28px;
        color: white;
        margin-bottom: 18px;
    }}
    .csp-banner .eyebrow {{
        font-family: {FONT_MONO};
        font-size: 0.75rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        opacity: 0.85;
        color: {COLORS['amber']};
    }}
    .csp-banner h2 {{
        color: white;
        margin: 4px 0 6px 0;
    }}
    .csp-card {{
        background: {COLORS['surface']};
        border: 1px solid {COLORS['border']};
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 10px;
    }}
    .csp-metric-label {{
        font-family: {FONT_MONO};
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: {COLORS['text_muted']};
    }}
    .csp-metric-value {{
        font-family: {FONT_MONO};
        font-size: 1.6rem;
        font-weight: 600;
        color: {COLORS['teal_deep']};
    }}
    .csp-badge {{
        display: inline-block;
        font-family: {FONT_MONO};
        font-size: 0.72rem;
        font-weight: 600;
        padding: 3px 10px;
        border-radius: 20px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    .csp-gradient-bar {{
        height: 6px;
        border-radius: 4px;
        background: linear-gradient(90deg, {COLORS['sky_blue']} 0%, {COLORS['teal_deep']} 45%, {COLORS['amber']} 100%);
        margin: 6px 0 18px 0;
    }}
    div[data-testid="stMetricValue"] {{
        font-family: {FONT_MONO};
        color: {COLORS['teal_deep']};
    }}

    /* --- Contrast safety net -----------------------------------------------
       Streamlit's own text elements (captions, widget labels, tab labels,
       expander headers, alert boxes) sometimes keep a theme-dependent color
       that doesn't track our custom background, which is what makes text
       look "sunk" against the page. These rules force a legible color on
       Streamlit's native elements specifically (matched by data-testid /
       baseweb attributes), without touching our own .csp-* components above. */
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] span:not(.csp-badge):not(.eyebrow) {{
        color: {COLORS['text_dark']} !important;
    }}
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p,
    [data-testid="stMarkdownContainer"] small {{
        color: {COLORS['text_muted']} !important;
        opacity: 1 !important;
    }}
    [data-testid="stWidgetLabel"] p,
    [data-testid="stWidgetLabel"] label {{
        color: {COLORS['text_dark']} !important;
        font-weight: 500;
    }}
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary p,
    [data-testid="stExpander"] svg {{
        color: {COLORS['teal_deep']} !important;
        fill: {COLORS['teal_deep']} !important;
    }}
    button[data-baseweb="tab"] {{
        color: {COLORS['text_muted']} !important;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: {COLORS['teal_deep']} !important;
        font-weight: 600;
    }}
    [data-testid="stAlert"] p,
    [data-testid="stAlert"] span {{
        color: {COLORS['text_dark']} !important;
    }}
    [data-testid="stDataFrame"] {{
        color: {COLORS['text_dark']};
    }}
    .csp-banner, .csp-banner p, .csp-banner div, .csp-banner span {{
        color: white !important;
    }}
    .csp-banner .eyebrow {{
        color: {COLORS['amber']} !important;
    }}
    </style>
    """, unsafe_allow_html=True)


def status_badge_html(label: str, status: str) -> str:
    """status in {'ok','warning','critical'}"""
    color_map = {"ok": COLORS["status_ok"], "warning": COLORS["status_warning"], "critical": COLORS["status_critical"]}
    color = color_map.get(status, COLORS["text_muted"])
    return f'<span class="csp-badge" style="background:{color}20; color:{color}; border:1px solid {color}55;">{label}</span>'


def fill_rate_status(pct: float) -> str:
    if pct >= 95:
        return "critical"
    if pct < 30:
        return "warning"
    if pct >= 60:
        return "ok"
    return "warning"


def spoilage_status(pct: float) -> str:
    if pct <= 10:
        return "ok"
    if pct <= 20:
        return "warning"
    return "critical"


def metric_card(label: str, value: str, badge_label: str = None, badge_status: str = None):
    badge_html = status_badge_html(badge_label, badge_status) if badge_label else ""
    st.markdown(f"""
    <div class="csp-card">
        <div class="csp-metric-label">{label}</div>
        <div class="csp-metric-value">{value}</div>
        {badge_html}
    </div>
    """, unsafe_allow_html=True)


def banner(eyebrow: str, title: str, subtitle: str):
    st.markdown(f"""
    <div class="csp-banner">
        <div class="eyebrow">{eyebrow}</div>
        <h2>{title}</h2>
        <div>{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)


def gradient_divider():
    st.markdown('<div class="csp-gradient-bar"></div>', unsafe_allow_html=True)


def df_to_csv_download(df, filename: str, label: str = "Download CSV"):
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(label, data=csv_bytes, file_name=filename, mime="text/csv")


def simulated_pv_power_kw(pv_capacity_kwp: float, hour: float = None) -> float:
    """
    Simulated (NOT live telemetry) instantaneous PV output using a simple
    daylight sine model peaking at solar noon (12:00) between 06:00-18:00.
    Used only to give the dashboard a 'realtime-style' gauge for the demo.
    """
    if hour is None:
        hour = datetime.now().hour + datetime.now().minute / 60.0
    if hour < 6 or hour > 18:
        return 0.0
    fraction_of_day = (hour - 6) / 12.0  # 0 at 6am, 1 at 6pm
    output = pv_capacity_kwp * math.sin(fraction_of_day * math.pi)
    return max(output, 0.0)


_VN_BASE_LETTER_MAP = str.maketrans({
    "đ": "d", "Đ": "D", "ư": "u", "Ư": "U", "ơ": "o", "Ơ": "O",
})
_PDF_SYMBOL_MAP = {
    "≤": "<=", "≥": ">=", "₂": "2", "→": "->", "–": "-", "—": "-",
    "’": "'", "‘": "'", "“": '"', "”": '"', "…": "...",
}


def safe_pdf_text(text) -> str:
    """
    fpdf2's built-in core fonts (Helvetica etc.) only support latin-1, so any
    character outside that range -- math symbols like '≤'/'≥', Vietnamese
    letters with a horn/stroke like 'ư'/'ơ'/'đ', smart quotes, etc. -- raises
    FPDFUnicodeEncodingException and crashes the export. Rather than ship a
    bundled Unicode font, this normalizes text down to a safe ASCII/latin-1
    approximation: known symbols get a literal substitute, Vietnamese letters
    that don't decompose get an explicit base-letter mapping, and ordinary
    accented vowels (á, ệ, ộ, ...) are decomposed and have their diacritic
    marks stripped via NFKD. Anything still left over is dropped rather than
    crashing the whole PDF. This sanitization only affects the PDF export --
    the live Streamlit UI always shows full, correct Unicode text.
    """
    text = str(text)
    for sym, repl in _PDF_SYMBOL_MAP.items():
        text = text.replace(sym, repl)
    text = text.translate(_VN_BASE_LETTER_MAP)
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.encode("latin-1", "ignore").decode("latin-1")


def build_pdf_summary(site_name, site_score, sizing_outputs, impact_outputs, allocation_summary) -> bytes:
    """Builds a one-page PDF executive summary using fpdf2 (pure-python, no
    system dependencies). Returns raw PDF bytes for st.download_button."""
    from fpdf import FPDF

    t = safe_pdf_text  # shorthand

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, t("CoolShare Planner - Executive Summary"), ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, t(f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}"), ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, t("Recommended Pilot Site"), ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, t(f"{site_name} -- composite score {site_score:.1f}/100"))
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, t("Hub Sizing"), ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, t(
        f"Hub size class: {sizing_outputs['hub_size_label']}\n"
        f"Daily energy demand: {sizing_outputs['daily_energy_demand_kwh']:.1f} kWh/day\n"
        f"PV array (field-adjusted): {sizing_outputs['pv_field_adjusted_kwp']:.2f} kWp\n"
        f"Battery capacity: {sizing_outputs['battery_capacity_kwh']:.1f} kWh\n"
        f"Total capital cost: ${sizing_outputs['total_capital_cost_usd']:,.0f}"
    ))
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, t("Monthly Impact"), ln=True)
    pdf.set_font("Helvetica", "", 10)
    payback_txt = f"{impact_outputs['payback_months']:.1f} months" if impact_outputs['payback_months'] != float('inf') else "N/A (net benefit not yet positive)"
    pdf.multi_cell(0, 6, t(
        f"Food saved: {impact_outputs['spoilage_avoided_kg']:.0f} kg/month\n"
        f"Income protected: ${impact_outputs['income_protected_usd']:,.0f}/month\n"
        f"Net CO2 avoided: {impact_outputs['net_co2_avoided_kg']:.1f} kg/month\n"
        f"Simple payback: {payback_txt}\n"
        f"Simple ROI: {impact_outputs['simple_roi_pct_year']:.1f}%/year"
    ))
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, t("Booking & Allocation Snapshot"), ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, t(
        f"Volume fill rate: {allocation_summary['fill_rate_volume_pct']:.0f}%\n"
        f"Bookings allocated: {allocation_summary['n_allocated']} | Waitlisted: {allocation_summary['n_waitlisted']}"
    ))

    return bytes(pdf.output(dest="S"))
