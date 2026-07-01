"""
utils.py — shared UI helpers, CSS, inherited-field displays,
pipeline step bar, PDF/CSV export, and simulated PV gauge.
"""

import io, math, unicodedata
from datetime import datetime

import pandas as pd
import streamlit as st

from modules.config import COLORS, FONT_DISPLAY, FONT_BODY, FONT_MONO


# ─────────────────────────────────────────────────────────────────────────────
# CSS INJECTION
# ─────────────────────────────────────────────────────────────────────────────
def inject_css():
    C = COLORS
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap');

    /* ── Base ── */
    .stApp {{ background:{C['paper']}; font-family:{FONT_BODY}; color:{C['text_dark']}; }}
    h1,h2,h3 {{ font-family:{FONT_DISPLAY}; color:{C['teal_deep']}; letter-spacing:-0.01em; }}

    /* ── Pipeline step bar ── */
    .csp-steps {{ display:flex; gap:6px; margin-bottom:20px; flex-wrap:wrap; }}
    .csp-step  {{ flex:1; min-width:90px; padding:8px 10px; border-radius:8px; text-align:center; }}
    .csp-step.done    {{ background:#E6F4EF; border:1px solid {C['teal_deep']}; }}
    .csp-step.active  {{ background:{C['teal_deep']}; border:1px solid {C['teal_deep']}; }}
    .csp-step.pending {{ background:#EEF1F5; border:1px dashed #CBD5E1; }}
    .csp-step .sn {{ font-family:{FONT_MONO}; font-size:0.65rem; display:block;
                     color:{C['teal_deep']}; }}
    .csp-step.active .sn  {{ color:{C['amber']}; }}
    .csp-step.pending .sn {{ color:#94A3B8; }}
    .csp-step .sl {{ font-size:0.75rem; font-weight:600; color:{C['teal_deep']}; }}
    .csp-step.active  .sl {{ color:#fff; }}
    .csp-step.pending .sl {{ color:#94A3B8; }}

    /* ── Header banner ── */
    .csp-banner {{ background:linear-gradient(100deg,{C['teal_deep']} 0%,#145C46 60%,{C['amber']} 130%);
                   border-radius:14px; padding:22px 28px; color:#fff; margin-bottom:18px; }}
    .csp-banner .eyebrow {{ font-family:{FONT_MONO}; font-size:0.72rem; letter-spacing:.12em;
                            text-transform:uppercase; color:{C['amber']}; }}
    .csp-banner h2 {{ color:#fff; margin:4px 0 6px; }}

    /* ── Metric card ── */
    .csp-card {{ background:{C['surface']}; border:1px solid {C['border']};
                 border-radius:10px; padding:14px 16px; margin-bottom:10px; }}
    .csp-metric-label {{ font-family:{FONT_MONO}; font-size:0.68rem; text-transform:uppercase;
                         letter-spacing:.08em; color:{C['text_muted']}; }}
    .csp-metric-value {{ font-family:{FONT_MONO}; font-size:1.5rem; font-weight:600;
                         color:{C['teal_deep']}; }}

    /* ── Inherited / locked field block ── */
    .csp-inherit {{ background:{C['bg_inherit']}; border:1px solid {C['border_inherit']};
                    border-left:4px solid {C['amber']}; border-radius:8px;
                    padding:12px 16px; margin-bottom:12px; }}
    .csp-inherit-title {{ font-family:{FONT_MONO}; font-size:0.68rem; text-transform:uppercase;
                           letter-spacing:.1em; color:{C['status_warning']}; font-weight:700;
                           margin-bottom:8px; }}
    .csp-inherit-row {{ display:flex; justify-content:space-between; padding:3px 0;
                        border-bottom:1px dashed {C['border']}; }}
    .csp-inherit-row:last-child {{ border-bottom:none; }}
    .csp-inherit-lbl {{ color:{C['text_muted']}; font-size:0.85rem; }}
    .csp-inherit-val {{ color:{C['teal_deep']}; font-weight:600; font-family:{FONT_MONO};
                        font-size:0.85rem; }}

    /* ── Hub portfolio card ── */
    .csp-hub-card {{ background:{C['surface']}; border:1px solid {C['teal_deep']}33;
                     border-left:4px solid {C['teal_deep']}; border-radius:8px;
                     padding:10px 14px; margin-bottom:8px;
                     display:flex; justify-content:space-between; align-items:center; }}
    .csp-hub-name {{ font-weight:700; color:{C['teal_deep']}; font-size:0.92rem; }}
    .csp-hub-meta {{ color:{C['text_muted']}; font-size:0.78rem; font-family:{FONT_MONO}; }}

    /* ── Coordinator story ── */
    .csp-story {{ background:linear-gradient(135deg,{C['teal_deep']}08 0%,{C['amber']}0D 100%);
                  border:1px solid {C['teal_deep']}22; border-radius:14px; padding:22px; }}
    .csp-story-flow {{ display:flex; align-items:center; gap:12px; margin:16px 0; flex-wrap:wrap; }}
    .csp-story-node {{ flex:1; min-width:120px; background:#fff; border-radius:10px;
                       padding:14px; text-align:center; border:1px solid {C['border']}; }}
    .csp-story-node.hub {{ background:{C['teal_deep']}; }}
    .node-title {{ font-weight:700; font-size:0.88rem; color:{C['text_dark']}; }}
    .csp-story-node.hub .node-title {{ color:#fff; }}
    .node-sub {{ font-size:0.72rem; color:{C['text_muted']}; margin-top:4px; }}
    .csp-story-node.hub .node-sub {{ color:{C['amber']}; }}
    .csp-arrow {{ font-size:1.4rem; color:{C['teal_deep']}; flex-shrink:0; }}

    /* ── Recommendation card ── */
    .csp-reco {{ background:{C['surface']}; border:1px solid {C['border']};
                 border-radius:14px; padding:20px 24px; margin-bottom:16px; }}
    .csp-reco-title {{ font-family:{FONT_DISPLAY}; font-size:1.25rem;
                       color:{C['teal_deep']}; margin:0 0 2px; }}
    .csp-reco-sub {{ font-family:{FONT_MONO}; font-size:0.78rem;
                     color:{C['text_muted']}; margin-bottom:14px; }}
    .csp-reco-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:22px; }}
    .csp-reco-col h4 {{ font-family:{FONT_MONO}; font-size:0.68rem; text-transform:uppercase;
                         letter-spacing:.08em; color:{C['text_muted']}; margin:0 0 6px; }}
    .csp-reco-list {{ list-style:none; padding-left:0; margin:0 0 14px; }}
    .csp-reco-list li {{ padding:3px 0; color:{C['text_dark']}; font-size:0.9rem; }}
    .csp-reco-list.reasons li::before {{ content:"✓ "; color:{C['status_ok']}; font-weight:700; }}
    .csp-reco-list.risks   li::before {{ content:"⚠ "; color:{C['status_warning']}; font-weight:700; }}
    .csp-reco-stat {{ display:flex; justify-content:space-between; padding:3px 0;
                      font-family:{FONT_MONO}; font-size:0.85rem;
                      border-bottom:1px dashed {C['border']}; }}
    .csp-reco-stat .v {{ color:{C['teal_deep']}; font-weight:600; }}

    /* ── Badge ── */
    .csp-badge {{ display:inline-block; font-family:{FONT_MONO}; font-size:0.68rem;
                  font-weight:600; padding:3px 10px; border-radius:20px;
                  text-transform:uppercase; letter-spacing:.05em; }}

    /* ── Gradient divider ── */
    .csp-gradient-bar {{ height:5px; border-radius:4px;
                         background:linear-gradient(90deg,{C['sky_blue']} 0%,{C['teal_deep']} 45%,{C['amber']} 100%);
                         margin:6px 0 18px; }}

    /* ── Native Streamlit contrast overrides ── */
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li {{ color:{C['text_dark']} !important; }}
    [data-testid="stCaptionContainer"] p  {{ color:{C['text_muted']} !important; opacity:1 !important; }}
    [data-testid="stWidgetLabel"] p       {{ color:{C['text_dark']} !important; font-weight:500; }}
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary p  {{ color:{C['teal_deep']} !important; }}
    button[data-baseweb="tab"]                       {{ color:{C['text_muted']} !important; }}
    button[data-baseweb="tab"][aria-selected="true"] {{ color:{C['teal_deep']} !important; font-weight:700; }}
    [data-testid="stAlert"] p             {{ color:{C['text_dark']} !important; }}
    div[data-testid="stMetricValue"]      {{ font-family:{FONT_MONO}; color:{C['teal_deep']}; }}
    .csp-banner, .csp-banner p, .csp-banner div, .csp-banner span {{ color:#fff !important; }}
    .csp-banner .eyebrow {{ color:{C['amber']} !important; }}
    </style>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE STEP BAR
# ─────────────────────────────────────────────────────────────────────────────
STEP_DEFS = [
    ("①", "Site Scoring"),
    ("②", "Hub Design"),
    ("③", "Booking"),
    ("④", "Impact"),
    ("⑤", "Dashboard"),
]

def pipeline_step_bar(current: int, n_done: int):
    """Renders the 5-step pipeline breadcrumb. current=1-5, n_done=steps completed."""
    html = '<div class="csp-steps">'
    for i, (num, label) in enumerate(STEP_DEFS, start=1):
        if i < current:
            cls = "done";    tick = " ✓"
        elif i == current:
            cls = "active";  tick = ""
        else:
            cls = "pending"; tick = ""
        html += (f'<div class="csp-step {cls}">'
                 f'<span class="sn">{num}</span>'
                 f'<span class="sl">{label}{tick}</span>'
                 f'</div>')
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# INHERITED FIELD BLOCK
# ─────────────────────────────────────────────────────────────────────────────
def inherited_block(rows: list, source_label: str):
    """
    Renders a locked 'Inherited from …' box.
    rows = list of (label, formatted_value) tuples.
    """
    rows_html = "".join(
        f'<div class="csp-inherit-row">'
        f'<span class="csp-inherit-lbl">{lbl}</span>'
        f'<span class="csp-inherit-val">{val}</span>'
        f'</div>'
        for lbl, val in rows
    )
    st.markdown(f"""
    <div class="csp-inherit">
      <div class="csp-inherit-title">🔒 Inherited from {source_label}</div>
      {rows_html}
    </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# COORDINATOR STORY HTML
# ─────────────────────────────────────────────────────────────────────────────
def coordinator_story():
    st.markdown(f"""
    <div class="csp-story">
      <div style="font-family:{FONT_DISPLAY};font-size:1.1rem;font-weight:700;
                  color:{COLORS['teal_deep']};margin-bottom:6px;">
        Why a Third-Party Coordinator is Essential
      </div>
      <div style="color:{COLORS['text_muted']};font-size:0.88rem;margin-bottom:4px;">
        Without coordination, 50+ smallholder farmers and fishers negotiate individually — 
        no cold chain, no leverage, and 25–35% of produce lost to spoilage before reaching market.
        <strong style="color:{COLORS['text_dark']}"> CoolShare acts as the neutral coordination layer</strong>
        that aggregates demand, ranks investment sites, runs allocation, and delivers investment-ready data.
      </div>
      <div class="csp-story-flow">
        <div class="csp-story-node">
          <div class="node-title">🌾 Farmers &amp; Fishers</div>
          <div class="node-sub">50+ smallholders<br>fragmented, no cold chain</div>
        </div>
        <div class="csp-arrow">→</div>
        <div class="csp-story-node hub">
          <div class="node-title">CoolShare Hub</div>
          <div class="node-sub">Rank · Design · Allocate · Track</div>
        </div>
        <div class="csp-arrow">→</div>
        <div class="csp-story-node">
          <div class="node-title">🏪 Markets</div>
          <div class="node-sub">premium buyers<br>reduced spoilage losses</div>
        </div>
      </div>
      <div class="csp-story-flow" style="margin-top:0;">
        <div class="csp-story-node" style="border-color:{COLORS['amber']}44;">
          <div class="node-title">💰 Investors &amp; Aid Orgs</div>
          <div class="node-sub">impact capital seeking<br>bankable projects</div>
        </div>
        <div class="csp-arrow" style="transform:rotate(180deg);">→</div>
        <div class="csp-story-node hub">
          <div class="node-title">Investment-Ready Data</div>
          <div class="node-sub">ROI · CO₂ · payback<br>portfolio ranking</div>
        </div>
        <div class="csp-arrow" style="transform:rotate(180deg);">→</div>
        <div class="csp-story-node" style="border-color:{COLORS['sky_blue']}44;">
          <div class="node-title">🔧 Hub Operators</div>
          <div class="node-sub">booking schedule<br>fill-rate targets</div>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# EXISTING HELPERS (unchanged)
# ─────────────────────────────────────────────────────────────────────────────
def pipeline_default(site_row, col: str, fallback):
    if site_row is None:
        return fallback
    val = site_row.get(col)
    if val is None:
        return fallback
    try:
        if pd.isna(val):
            return fallback
    except (TypeError, ValueError):
        pass
    return val


def status_badge_html(label: str, status: str) -> str:
    color_map = {
        "ok":       COLORS["status_ok"],
        "warning":  COLORS["status_warning"],
        "critical": COLORS["status_critical"],
    }
    color = color_map.get(status, COLORS["text_muted"])
    return (f'<span class="csp-badge" style="background:{color}20;'
            f'color:{color};border:1px solid {color}55;">{label}</span>')


def fill_rate_status(pct):
    if pct >= 95: return "critical"
    if pct >= 60: return "ok"
    return "warning"


def spoilage_status(pct):
    if pct <= 10: return "ok"
    if pct <= 20: return "warning"
    return "critical"


def metric_card(label, value, badge_label=None, badge_status=None):
    badge = status_badge_html(badge_label, badge_status) if badge_label else ""
    st.markdown(f"""
    <div class="csp-card">
      <div class="csp-metric-label">{label}</div>
      <div class="csp-metric-value">{value}</div>
      {badge}
    </div>""", unsafe_allow_html=True)


def banner(eyebrow, title, subtitle):
    st.markdown(f"""
    <div class="csp-banner">
      <div class="eyebrow">{eyebrow}</div>
      <h2>{title}</h2>
      <div>{subtitle}</div>
    </div>""", unsafe_allow_html=True)


def recommendation_card(reco, is_top_rank, top_site_name=None):
    reasons_html = "".join(f"<li>{r}</li>" for r in reco["reasons"])
    risks_html   = "".join(f"<li>{r}</li>" for r in reco["risks"])
    ei, sh = reco["expected_impact"], reco["suggested_hub"]
    vol_txt = f"{sh['storage_volume_m3']:.1f} m³" if sh["storage_volume_m3"] else "—"
    if is_top_rank:
        title = f"✅ Recommended Pilot: {reco['site_name']}"
        sub   = f"{reco['region']} · Rank #1 · Score {reco['score']:.1f}/100"
    else:
        title = f"📋 Plan for: {reco['site_name']} (Rank #{reco['rank']})"
        sub   = f"{reco['region']} · Score {reco['score']:.1f}/100"
        if top_site_name:
            sub += f" · Top-ranked candidate is <b>{top_site_name}</b>"
    st.markdown(f"""
    <div class="csp-reco">
      <div class="csp-reco-title">{title}</div>
      <div class="csp-reco-sub">{sub}</div>
      <div class="csp-reco-grid">
        <div class="csp-reco-col">
          <h4>Why this site</h4>
          <ul class="csp-reco-list reasons">{reasons_html}</ul>
          <h4>Risks</h4>
          <ul class="csp-reco-list risks">{risks_html}</ul>
        </div>
        <div class="csp-reco-col">
          <h4>Expected monthly impact</h4>
          <div class="csp-reco-stat"><span>Food saved</span><span class="v">{ei['food_saved_tonnes']:.2f} t</span></div>
          <div class="csp-reco-stat"><span>Income protected</span><span class="v">${ei['income_protected_usd']:,.0f}</span></div>
          <div class="csp-reco-stat"><span>Net CO₂ avoided</span><span class="v">{ei['net_co2_avoided_tonnes']:.2f} t</span></div>
          <h4 style="margin-top:14px;">Suggested hub spec</h4>
          <div class="csp-reco-stat"><span>Cold room volume</span><span class="v">{vol_txt}</span></div>
          <div class="csp-reco-stat"><span>PV array</span><span class="v">{sh['pv_kwp']:.2f} kWp</span></div>
          <div class="csp-reco-stat"><span>Battery</span><span class="v">{sh['battery_kwh']:.1f} kWh</span></div>
          <div class="csp-reco-stat"><span>Capital cost</span><span class="v">${sh['capital_cost_usd']:,.0f}</span></div>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)


def gradient_divider():
    st.markdown('<div class="csp-gradient-bar"></div>', unsafe_allow_html=True)


def df_to_csv_download(df, filename, label="⬇ Download CSV"):
    st.download_button(label, data=df.to_csv(index=False).encode("utf-8"),
                       file_name=filename, mime="text/csv")


def simulated_pv_power_kw(pv_capacity_kwp, hour=None):
    if hour is None:
        hour = datetime.now().hour + datetime.now().minute / 60.0
    if hour < 6 or hour > 18:
        return 0.0
    return max(pv_capacity_kwp * math.sin((hour - 6) / 12.0 * math.pi), 0.0)


# ─────────────────────────────────────────────────────────────────────────────
# PDF EXPORT
# ─────────────────────────────────────────────────────────────────────────────
_VN_MAP  = str.maketrans({"đ":"d","Đ":"D","ư":"u","Ư":"U","ơ":"o","Ơ":"O"})
_SYM_MAP = {"≤":"<=","≥":">=","₂":"2","→":"->","–":"-","—":"-",
            "\u2018":"'","\u2019":"'","\u201C":'"',"\u201D":'"',"…":"...",
            "✓":"[+]","⚠":"[!]","✅":"[OK]","📋":"","📍":"","🔒":"[locked]"}

def _t(text):
    text = str(text)
    for s, r in _SYM_MAP.items():
        text = text.replace(s, r)
    text = text.translate(_VN_MAP)
    text = "".join(c for c in unicodedata.normalize("NFKD", text)
                   if unicodedata.category(c) != "Mn")
    return text.encode("latin-1", "ignore").decode("latin-1")


def build_pdf_summary(site_name, site_score, sizing_outputs, impact_outputs,
                      allocation_summary, reasons=None, risks=None):
    from fpdf import FPDF
    pdf = FPDF(); pdf.add_page()
    pdf.set_font("Helvetica","B",16)
    pdf.cell(0,10,_t("CoolShare Planner - Executive Summary"),ln=True)
    pdf.set_font("Helvetica","",10)
    pdf.cell(0,6,_t(f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}"),ln=True)
    pdf.ln(4)

    def section(title): pdf.ln(2); pdf.set_font("Helvetica","B",12); pdf.cell(0,8,_t(title),ln=True); pdf.set_font("Helvetica","",10)

    section("Recommended Pilot Site")
    pdf.multi_cell(0,6,_t(f"{site_name} -- composite score {site_score:.1f}/100"))
    if reasons:
        pdf.set_font("Helvetica","B",10); pdf.cell(0,6,_t("Reasons:"),ln=True); pdf.set_font("Helvetica","",10)
        pdf.multi_cell(0,6,_t("\n".join(f"+ {r}" for r in reasons)))
    if risks:
        pdf.set_font("Helvetica","B",10); pdf.cell(0,6,_t("Risks:"),ln=True); pdf.set_font("Helvetica","",10)
        pdf.multi_cell(0,6,_t("\n".join(f"! {r}" for r in risks)))

    section("Hub Sizing")
    pdf.multi_cell(0,6,_t(
        f"Hub class: {sizing_outputs['hub_size_label']}\n"
        f"Daily energy demand: {sizing_outputs['daily_energy_demand_kwh']:.1f} kWh/day\n"
        f"PV array (field-adjusted): {sizing_outputs['pv_field_adjusted_kwp']:.2f} kWp\n"
        f"Battery: {sizing_outputs['battery_capacity_kwh']:.1f} kWh\n"
        f"Total capital cost: ${sizing_outputs['total_capital_cost_usd']:,.0f}"))

    section("Monthly Impact")
    pb = f"{impact_outputs['payback_months']:.1f} months" if impact_outputs['payback_months'] != float('inf') else "N/A"
    pdf.multi_cell(0,6,_t(
        f"Food saved: {impact_outputs['spoilage_avoided_kg']:.0f} kg/month\n"
        f"Income protected: ${impact_outputs['income_protected_usd']:,.0f}/month\n"
        f"Net CO2 avoided: {impact_outputs['net_co2_avoided_kg']:.1f} kg/month\n"
        f"Simple payback: {pb}\nSimple ROI: {impact_outputs['simple_roi_pct_year']:.1f}%/year"))

    section("Booking & Allocation Snapshot")
    pdf.multi_cell(0,6,_t(
        f"Volume fill rate: {allocation_summary['fill_rate_volume_pct']:.0f}%\n"
        f"Allocated: {allocation_summary['n_allocated']} | Waitlisted: {allocation_summary['n_waitlisted']}"))

    return bytes(pdf.output(dest="S"))
