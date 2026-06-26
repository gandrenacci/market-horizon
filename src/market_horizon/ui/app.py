"""Streamlit user interface for Market Horizon."""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from html import escape
from math import sqrt
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from market_horizon import asset_types
from market_horizon.analytics.metrics import (
    MetricsSnapshot,
    TrendSnapshot,
    add_indicators,
    compute_metrics,
    normalized_performance,
)
from market_horizon.config import Settings, load_settings
from market_horizon.data.yfinance_provider import YFinanceProvider, normalize_symbol
from market_horizon.db import create_session_factory, init_db
from market_horizon.db.models import Asset
from market_horizon.db.repository import MarketRepository
from market_horizon.services.sync import SyncService, TickerSyncResult

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ASSETS_DIR = _REPO_ROOT / "assets"
_BANNER_PATH = _ASSETS_DIR / "mh-banner.png"
_LOGO_PATH = _ASSETS_DIR / "mh-logo.png"
_EXPLAINER_PATH = _ASSETS_DIR / "finance-explanations.md"

# Price-chart series styling. Only the adjusted-close price is a solid line; every moving
# average uses a distinct non-solid dash pattern. (label, color, dash, width)
_SERIES_STYLE: dict[str, tuple[str, str, str, float]] = {
    "price": ("Adjusted close", "#0b63f6", "solid", 2.4),  # brand blue
    "ema_20": ("EMA 20", "#7c3aed", "dash", 1.6),  # purple
    "sma_50": ("SMA 50", "#f59e0b", "dot", 1.6),  # amber
    "sma_200": ("SMA 200", "#38bdf8", "dashdot", 1.6),  # azure / sky
}

# Brand-aligned qualitative palette for multi-asset comparison lines.
_COMPARE_COLORWAY = ["#0b63f6", "#7c3aed", "#f59e0b", "#38bdf8", "#039855"]

_INK = "#111827"
_MUTED = "#667085"
_GRID = "rgba(16, 24, 40, 0.06)"


def run_app() -> None:
    """Run the Streamlit dashboard."""

    page_icon = str(_LOGO_PATH) if _LOGO_PATH.is_file() else "MH"
    st.set_page_config(page_title="Market Horizon", page_icon=page_icon, layout="wide")
    _inject_styles()
    settings, repository, sync_service = _bootstrap()

    assets = repository.list_watchlist_assets()
    _render_sidebar_brand()
    page = st.sidebar.radio("Page", ["Watchlist", "Asset Analysis", "Compare", "Learn"])
    _render_sidebar_footer(settings)
    _render_page_banner()

    if page == "Watchlist":
        _render_watchlist(repository, sync_service, settings, assets)
    elif page == "Asset Analysis":
        _render_asset_analysis(repository, settings, assets)
    elif page == "Compare":
        _render_compare(repository, assets)
    else:
        _render_learn()


@st.cache_resource
def _bootstrap() -> tuple[Settings, MarketRepository, SyncService]:
    settings = load_settings()
    session_factory = create_session_factory(settings.resolved_database_path)
    init_db(session_factory)
    repository = MarketRepository(session_factory)
    provider = YFinanceProvider()
    sync_service = SyncService(provider=provider, repository=repository, settings=settings)
    return settings, repository, sync_service


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --mh-blue: #0b63f6;
            --mh-blue-dark: #0758d7;
            --mh-blue-soft: #eaf2ff;
            --mh-ink: #111827;
            --mh-muted: #667085;
            --mh-border: #e4e9f2;
            --mh-panel: #ffffff;
            --mh-green: #039855;
            --mh-orange: #dc6803;
            --mh-red: #d92d20;
        }

        .block-container {
            max-width: 1600px;
            padding-top: 1.5rem;
            padding-bottom: 2.5rem;
        }

        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at top right, rgba(11, 99, 246, 0.08), transparent 30rem),
                #fbfcff;
        }

        [data-testid="stSidebar"] {
            border-right: 1px solid var(--mh-border);
            background: #ffffff;
        }

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            color: var(--mh-ink);
        }

        [data-testid="stSidebar"] [role="radiogroup"] label {
            border-radius: 10px;
            margin: 0.2rem 0;
            padding: 0.45rem 0.65rem;
        }

        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
            background: var(--mh-blue-soft);
            color: var(--mh-blue);
            font-weight: 700;
        }

        .mh-brand {
            display: flex;
            align-items: center;
            gap: 0.7rem;
            margin: 0 0 1.2rem;
        }

        .mh-brand-mark {
            align-items: center;
            background: linear-gradient(135deg, #0758d7, #2078ff);
            border-radius: 8px;
            color: #fff;
            display: inline-flex;
            font-weight: 800;
            height: 34px;
            justify-content: center;
            width: 34px;
        }

        .mh-brand-title {
            color: var(--mh-ink);
            font-size: 1.05rem;
            font-weight: 800;
            line-height: 1;
        }

        .mh-sidebar-footer {
            border-top: 1px solid var(--mh-border);
            color: var(--mh-muted);
            font-size: 0.82rem;
            margin-top: 2rem;
            padding-top: 1rem;
            word-break: break-word;
        }

        .mh-status-dot {
            background: var(--mh-green);
            border-radius: 999px;
            display: inline-block;
            height: 0.48rem;
            margin: 0 0.25rem 0 0.65rem;
            width: 0.48rem;
        }

        .mh-hero {
            background:
                radial-gradient(circle at 78% 18%, rgba(255, 255, 255, 0.28), transparent 13rem),
                radial-gradient(circle at 55% 105%, rgba(29, 213, 146, 0.22), transparent 18rem),
                linear-gradient(112deg, #0759d6 0%, #0a6af6 42%, #6658ff 100%);
            border: 1px solid rgba(255, 255, 255, 0.32);
            border-radius: 14px;
            box-shadow: 0 20px 48px rgba(11, 99, 246, 0.24);
            color: #fff;
            display: grid;
            grid-template-columns: minmax(0, 1.1fr) minmax(280px, 0.9fr);
            gap: 2rem;
            margin-bottom: 1.2rem;
            min-height: 218px;
            overflow: hidden;
            padding: 2.35rem 2.65rem;
            position: relative;
        }

        .mh-hero::before {
            background:
                linear-gradient(rgba(255, 255, 255, 0.12) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255, 255, 255, 0.12) 1px, transparent 1px);
            background-size: 76px 46px;
            content: "";
            inset: 0;
            mask-image: linear-gradient(90deg, transparent 0%, #000 30%, #000 100%);
            opacity: 0.55;
            position: absolute;
        }

        .mh-hero::after {
            background:
                linear-gradient(
                    100deg,
                    transparent 0 58%,
                    rgba(255,255,255,0.15) 58.2% 58.6%,
                    transparent 59%
                ),
                linear-gradient(
                    118deg,
                    transparent 0 68%,
                    rgba(255,255,255,0.22) 68.2% 68.6%,
                    transparent 69%
                );
            content: "";
            inset: 0;
            position: absolute;
        }

        .mh-hero-copy,
        .mh-hero-visual {
            position: relative;
            z-index: 1;
        }

        .mh-hero h1 {
            color: #fff;
            font-size: clamp(2.15rem, 4vw, 3.35rem);
            line-height: 1.05;
            margin: 0 0 0.65rem;
            max-width: 640px;
        }

        .mh-hero p {
            color: rgba(255, 255, 255, 0.9);
            font-size: 1.08rem;
            line-height: 1.55;
            margin: 0 0 1.45rem;
            max-width: 610px;
        }

        .mh-hero-kickers {
            display: flex;
            flex-wrap: wrap;
            gap: 0.65rem;
        }

        .mh-hero-chip {
            align-items: center;
            background: rgba(255, 255, 255, 0.14);
            border: 1px solid rgba(255, 255, 255, 0.24);
            border-radius: 999px;
            color: rgba(255, 255, 255, 0.94);
            display: inline-flex;
            font-size: 0.84rem;
            font-weight: 750;
            gap: 0.4rem;
            padding: 0.45rem 0.72rem;
        }

        .mh-hero-chip-dot {
            background: #31d18c;
            border-radius: 999px;
            box-shadow: 0 0 0 4px rgba(49, 209, 140, 0.18);
            display: inline-block;
            height: 0.45rem;
            width: 0.45rem;
        }

        .mh-hero-visual {
            align-self: stretch;
            min-height: 154px;
            position: relative;
        }

        .mh-market-card {
            backdrop-filter: blur(16px);
            background: rgba(255, 255, 255, 0.15);
            border: 1px solid rgba(255, 255, 255, 0.26);
            border-radius: 13px;
            box-shadow: 0 18px 34px rgba(5, 30, 93, 0.2);
            inset: 0 0 auto auto;
            max-width: 420px;
            min-height: 156px;
            padding: 1.1rem;
            position: absolute;
            right: 0;
            top: 0.2rem;
            width: min(100%, 420px);
        }

        .mh-market-card-head {
            align-items: center;
            display: flex;
            justify-content: space-between;
            margin-bottom: 1.2rem;
        }

        .mh-market-card-title {
            color: rgba(255, 255, 255, 0.72);
            font-size: 0.78rem;
            font-weight: 750;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .mh-market-card-value {
            color: #fff;
            font-size: 1.48rem;
            font-weight: 850;
            line-height: 1.1;
        }

        .mh-market-card-badge {
            background: rgba(49, 209, 140, 0.18);
            border: 1px solid rgba(49, 209, 140, 0.36);
            border-radius: 999px;
            color: #c8ffe5;
            font-size: 0.8rem;
            font-weight: 800;
            padding: 0.28rem 0.55rem;
        }

        .mh-market-line {
            height: 74px;
            position: relative;
        }

        .mh-market-bars {
            align-items: end;
            display: grid;
            gap: 0.42rem;
            grid-template-columns: repeat(16, 1fr);
            height: 58px;
            opacity: 0.45;
        }

        .mh-market-bars span {
            background: rgba(255, 255, 255, 0.76);
            border-radius: 999px 999px 2px 2px;
            min-height: 12px;
        }

        .mh-card, .mh-panel {
            background: var(--mh-panel);
            border: 1px solid var(--mh-border);
            border-radius: 10px;
            box-shadow: 0 7px 22px rgba(16, 24, 40, 0.06);
        }

        .mh-card {
            align-items: center;
            display: flex;
            gap: 1rem;
            min-height: 94px;
            padding: 1.05rem 1.2rem;
        }

        .mh-card-icon {
            align-items: center;
            border-radius: 999px;
            display: inline-flex;
            flex: 0 0 auto;
            font-weight: 800;
            height: 48px;
            justify-content: center;
            width: 48px;
        }

        .mh-card-icon.blue { background: #e8f1ff; color: var(--mh-blue); }
        .mh-card-icon.green { background: #e6f8ef; color: var(--mh-green); }
        .mh-card-icon.purple { background: #f0ecff; color: #6d42e8; }
        .mh-card-icon.orange { background: #fff3df; color: #f79009; }

        .mh-card-label, .mh-card-caption {
            color: var(--mh-muted);
            font-size: 0.82rem;
        }

        .mh-card-value {
            color: var(--mh-ink);
            font-size: 1.45rem;
            font-weight: 800;
            line-height: 1.1;
            margin: 0.25rem 0;
        }

        .mh-panel {
            margin: 1rem 0 1.2rem;
            padding: 1rem 1.15rem;
        }

        .mh-panel-title {
            color: var(--mh-ink);
            font-size: 1rem;
            font-weight: 800;
            margin-bottom: 0.15rem;
        }

        .mh-panel-copy {
            color: var(--mh-muted);
            font-size: 0.84rem;
        }

        .mh-section-title {
            color: var(--mh-ink);
            font-size: 1.35rem;
            font-weight: 850;
            margin: 0.35rem 0 0.2rem;
        }

        .mh-muted {
            color: var(--mh-muted);
        }

        .mh-stat {
            background: var(--mh-panel);
            border: 1px solid var(--mh-border);
            border-radius: 10px;
            box-shadow: 0 7px 22px rgba(16, 24, 40, 0.06);
            min-height: 92px;
            padding: 0.95rem 1.1rem;
        }

        .mh-stat-label {
            color: var(--mh-muted);
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
        }

        .mh-stat-value {
            color: var(--mh-ink);
            font-size: 1.4rem;
            font-weight: 800;
            line-height: 1.15;
            margin: 0.3rem 0 0.1rem;
            word-break: break-word;
        }

        .mh-stat-delta {
            font-size: 0.84rem;
            font-weight: 700;
        }

        .mh-stat-delta.up { color: var(--mh-green); }
        .mh-stat-delta.down { color: var(--mh-red); }
        .mh-stat-delta.flat { color: var(--mh-muted); }

        .mh-trend-card {
            background: var(--mh-panel);
            border: 1px solid var(--mh-border);
            border-left: 4px solid var(--mh-muted);
            border-radius: 10px;
            box-shadow: 0 7px 22px rgba(16, 24, 40, 0.06);
            min-height: 118px;
            padding: 1rem 1.1rem;
        }

        .mh-trend-card.is-positive { border-left-color: var(--mh-green); }
        .mh-trend-card.is-negative { border-left-color: var(--mh-red); }
        .mh-trend-card.is-mixed { border-left-color: var(--mh-orange); }

        .mh-trend-title {
            color: var(--mh-muted);
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
        }

        .mh-trend-row {
            align-items: baseline;
            display: flex;
            gap: 0.6rem;
            margin: 0.35rem 0 0.3rem;
        }

        .mh-trend-badge {
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 800;
            padding: 0.15rem 0.6rem;
        }

        .mh-trend-badge.is-positive { background: #e6f8ef; color: var(--mh-green); }
        .mh-trend-badge.is-negative { background: #fdecea; color: var(--mh-red); }
        .mh-trend-badge.is-mixed { background: #fff3df; color: #b54708; }
        .mh-trend-badge.is-unavailable { background: #f1f3f7; color: var(--mh-muted); }

        .mh-trend-distance {
            font-size: 0.92rem;
            font-weight: 700;
        }

        .mh-trend-distance.up { color: var(--mh-green); }
        .mh-trend-distance.down { color: var(--mh-red); }
        .mh-trend-distance.flat { color: var(--mh-muted); }

        .mh-trend-caption {
            color: var(--mh-muted);
            font-size: 0.82rem;
            line-height: 1.4;
        }

        .mh-metrics-grid {
            display: grid;
            gap: 1rem;
            grid-template-columns: repeat(auto-fit, minmax(290px, 1fr));
            margin: 0.4rem 0 1rem;
        }

        .mh-metric-card {
            background: var(--mh-panel);
            border: 1px solid var(--mh-border);
            border-radius: 12px;
            box-shadow: 0 7px 22px rgba(16, 24, 40, 0.05);
            overflow: hidden;
        }

        .mh-metric-card-title {
            background: #f7f9fc;
            border-bottom: 1px solid var(--mh-border);
            color: var(--mh-muted);
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            padding: 0.62rem 0.9rem;
            text-transform: uppercase;
        }

        .mh-metric-row {
            align-items: baseline;
            border-bottom: 1px solid #f0f3f8;
            display: flex;
            gap: 1rem;
            justify-content: space-between;
            padding: 0.6rem 0.9rem;
        }

        .mh-metric-row:last-child { border-bottom: none; }
        .mh-metric-row:hover { background: #f7faff; }

        .mh-metric-name { color: var(--mh-ink); font-size: 0.92rem; font-weight: 600; }

        .mh-metric-value {
            font-variant-numeric: tabular-nums;
            font-weight: 700;
            text-align: right;
            white-space: nowrap;
        }

        .mh-metric-value.up { color: var(--mh-green); }
        .mh-metric-value.down { color: var(--mh-red); }
        .mh-metric-value.flat { color: var(--mh-muted); }

        .mh-momentum-card {
            background: var(--mh-panel);
            border: 1px solid var(--mh-border);
            border-radius: 12px;
            box-shadow: 0 7px 22px rgba(16, 24, 40, 0.05);
            margin: 0.5rem 0 0.75rem;
            overflow: hidden;
        }

        .mh-momentum-body { padding: 0.9rem 1rem 1rem; }

        .mh-rsi-label {
            color: var(--mh-muted);
            font-size: 0.82rem;
            font-weight: 600;
        }

        .mh-rsi-value {
            color: var(--mh-ink);
            font-size: 2rem;
            font-variant-numeric: tabular-nums;
            font-weight: 800;
            line-height: 1.2;
        }

        .mh-rsi-value.flat { color: var(--mh-muted); font-size: 1.2rem; }

        .mh-rsi-bar {
            background: #eef2f8;
            border-radius: 999px;
            height: 8px;
            margin-top: 0.55rem;
            overflow: hidden;
        }

        .mh-rsi-fill {
            background: var(--mh-blue);
            border-radius: 999px;
            height: 100%;
        }

        .mh-rsi-scale {
            color: var(--mh-muted);
            display: flex;
            font-size: 0.72rem;
            justify-content: space-between;
            margin-top: 0.3rem;
        }

        .mh-wl-wrap {
            border: 1px solid var(--mh-border);
            border-radius: 12px;
            box-shadow: 0 7px 22px rgba(16, 24, 40, 0.05);
            overflow-x: auto;
        }

        .mh-wl {
            border-collapse: collapse;
            font-size: 0.95rem;
            width: 100%;
        }

        .mh-wl thead th {
            background: #f7f9fc;
            border-bottom: 1px solid var(--mh-border);
            color: var(--mh-muted);
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            padding: 0.6rem 0.6rem;
            text-align: left;
            text-transform: uppercase;
            white-space: nowrap;
        }

        .mh-wl thead th.num { text-align: right; }

        .mh-wl thead th.sortable a {
            color: inherit;
            cursor: pointer;
            text-decoration: none;
            white-space: nowrap;
        }
        .mh-wl thead th.sortable a:hover { color: var(--mh-blue); }
        .mh-wl thead th.active a { color: var(--mh-blue); }

        .mh-wl tbody td {
            border-bottom: 1px solid #f0f3f8;
            color: var(--mh-ink);
            padding: 0.6rem 0.6rem;
            vertical-align: middle;
            white-space: nowrap;
        }

        .mh-wl tbody tr:last-child td { border-bottom: none; }
        .mh-wl tbody tr:hover { background: #f7faff; }

        .mh-wl .num { font-variant-numeric: tabular-nums; text-align: right; }
        .mh-wl .sym { color: var(--mh-ink); font-weight: 800; }
        .mh-wl .name { color: var(--mh-muted); max-width: 230px; overflow: hidden;
            text-overflow: ellipsis; }
        .mh-wl .price { font-weight: 700; }
        .mh-wl .upd { color: var(--mh-muted); font-size: 0.86rem; }
        .mh-wl .up { color: var(--mh-green); font-weight: 700; }
        .mh-wl .down { color: var(--mh-red); font-weight: 700; }
        .mh-wl .flat { color: var(--mh-muted); }

        .mh-pill {
            border-radius: 999px;
            display: inline-block;
            font-size: 0.78rem;
            font-weight: 700;
            padding: 0.2rem 0.62rem;
        }

        .mh-pill.is-positive { background: #e6f8ef; color: var(--mh-green); }
        .mh-pill.is-negative { background: #fdecea; color: var(--mh-red); }
        .mh-pill.is-mixed { background: #fff3df; color: #b54708; }
        .mh-pill.is-unavailable { background: #f1f3f7; color: var(--mh-muted); }

        .mh-type {
            border-radius: 999px;
            display: inline-block;
            font-size: 0.76rem;
            font-weight: 700;
            padding: 0.18rem 0.58rem;
        }

        .mh-type.t-stock { background: #e8f1ff; color: var(--mh-blue); }
        .mh-type.t-etf { background: #f0ecff; color: #6d42e8; }
        .mh-type.t-fund { background: #eaf0fb; color: #3a4fb8; }
        .mh-type.t-index { background: #e6f7f1; color: #0f7a5a; }
        .mh-type.t-crypto { background: #fff3df; color: #b54708; }
        .mh-type.t-forex { background: #fdeef5; color: #b03570; }
        .mh-type.t-future { background: #eef1f4; color: #4a5568; }
        .mh-type.t-default { background: #f1f3f7; color: var(--mh-muted); }

        .mh-vol { align-items: center; display: flex; gap: 0.55rem; min-width: 130px; }

        .mh-vol-track {
            background: #eef1f6;
            border-radius: 999px;
            flex: 1;
            height: 7px;
            overflow: hidden;
        }

        .mh-vol-fill {
            background: linear-gradient(90deg, var(--mh-blue), #38bdf8);
            border-radius: 999px;
            height: 100%;
        }

        .mh-vol-val {
            color: var(--mh-muted);
            font-size: 0.82rem;
            font-variant-numeric: tabular-nums;
            min-width: 44px;
            text-align: right;
        }

        .mh-spark { display: block; }

        div[data-testid="stButton"] > button[kind="primary"],
        div[data-testid="stButton"] > button[kind="secondary"] {
            border-radius: 8px;
            font-weight: 700;
        }

        div[data-testid="stTextInput"] input,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
            border-radius: 8px;
        }

        [data-testid="stDataFrame"] {
            border: 1px solid var(--mh-border);
            border-radius: 10px;
            box-shadow: 0 7px 22px rgba(16, 24, 40, 0.05);
            overflow: hidden;
        }

        @media (max-width: 760px) {
            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
            }

            .mh-hero {
                display: block;
                padding: 1.6rem;
            }

            .mh-hero-visual {
                display: none;
            }

            .mh-card {
                min-height: 84px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar_brand() -> None:
    st.sidebar.markdown(
        """
        <div class="mh-brand">
            <div class="mh-brand-mark">MH</div>
            <div class="mh-brand-title">Market Horizon</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar_footer(settings: Settings) -> None:
    st.sidebar.markdown(
        f"""
        <div class="mh-sidebar-footer">
            <div><strong>Database</strong><span class="mh-status-dot"></span>Connected</div>
            <div>{escape(str(settings.resolved_database_path))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_page_banner() -> None:
    if _BANNER_PATH.is_file():
        st.image(str(_BANNER_PATH), use_container_width=True)


def _render_watchlist(
    repository: MarketRepository,
    sync_service: SyncService,
    settings: Settings,
    assets: list[Asset],
) -> None:
    summary = _watchlist_summary(repository, settings, assets)
    _render_summary_cards(summary)
    _render_add_symbols_panel(sync_service)
    _render_sync_results(st.session_state.get("add_symbols_results"))

    st.markdown('<div class="mh-section-title">Watchlist</div>', unsafe_allow_html=True)
    table = _watchlist_table(repository, settings, assets)
    toolbar_cols = st.columns([1.6, 1.5, 0.8, 0.8])
    filter_type = toolbar_cols[0].segmented_control(
        "Filter",
        options=["All", "Stocks", "ETFs", "Funds", "Indices", "Crypto"],
        default="All",
        label_visibility="collapsed",
    )
    search = toolbar_cols[1].text_input(
        "Search symbols",
        placeholder="Search symbols...",
        label_visibility="collapsed",
    )
    if toolbar_cols[2].button("Sync all", disabled=not assets, use_container_width=True):
        st.session_state["add_symbols_results"] = sync_service.sync_all(assets)
        st.rerun()

    if toolbar_cols[3].button("Refresh", disabled=not assets, use_container_width=True):
        st.session_state["add_symbols_results"] = sync_service.sync_all(assets)
        st.rerun()

    sort_by, ascending = _watchlist_sort_state()
    table = _filter_table(table, str(filter_type), search)
    if table.empty:
        st.warning("Your watchlist is empty or no assets match the current filters.")
    else:
        table = _sort_table(table, sort_by, ascending)
        _render_watchlist_table(table, sort_by, ascending)

    if not assets:
        return

    action_col, refresh_col, remove_col = st.columns([1.5, 0.85, 1.15])
    selected = action_col.selectbox("Asset action", [asset.symbol for asset in assets])
    if refresh_col.button("Refresh selected", use_container_width=True):
        asset = next(asset for asset in assets if asset.symbol == selected)
        st.session_state["add_symbols_results"] = [
            sync_service.sync_asset(asset, initial=False, run_id=None)
        ]
        st.rerun()
    if remove_col.button("Remove selected", use_container_width=True):
        repository.remove_from_default_watchlist(selected)
        st.rerun()


def _render_watchlist_hero() -> None:
    st.markdown(
        """
        <section class="mh-hero">
            <div class="mh-hero-copy">
                <h1>Market Horizon</h1>
                <p>
                    Local-first market monitoring across short, medium and long-term horizons,
                    with transparent metrics for stocks, ETFs and crypto.
                </p>
                <div class="mh-hero-kickers">
                    <span class="mh-hero-chip">
                        <span class="mh-hero-chip-dot"></span>
                        Local database connected
                    </span>
                    <span class="mh-hero-chip">Daily OHLCV history</span>
                    <span class="mh-hero-chip">Informational analysis only</span>
                </div>
            </div>
            <div class="mh-hero-visual" aria-hidden="true">
                <div class="mh-market-card">
                    <div class="mh-market-card-head">
                        <div>
                            <div class="mh-market-card-title">Horizon Signal</div>
                            <div class="mh-market-card-value">Multi-asset view</div>
                        </div>
                        <div class="mh-market-card-badge">Live local</div>
                    </div>
                    <div class="mh-market-line">
                        <div class="mh-market-bars">
                            <span style="height: 18px"></span>
                            <span style="height: 26px"></span>
                            <span style="height: 20px"></span>
                            <span style="height: 38px"></span>
                            <span style="height: 32px"></span>
                            <span style="height: 44px"></span>
                            <span style="height: 30px"></span>
                            <span style="height: 52px"></span>
                            <span style="height: 42px"></span>
                            <span style="height: 56px"></span>
                            <span style="height: 36px"></span>
                            <span style="height: 48px"></span>
                            <span style="height: 58px"></span>
                            <span style="height: 46px"></span>
                            <span style="height: 62px"></span>
                            <span style="height: 54px"></span>
                        </div>
                    </div>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_summary_cards(summary: dict[str, str]) -> None:
    cards = [
        ("blue", "A", "Assets", summary["assets"], "Tracked instruments"),
        ("green", "T", "Positive Trends", summary["positive_trends"], "Across all horizons"),
        ("purple", "D", "52W Avg Drawdown", summary["avg_drawdown"], "Across all assets"),
        ("orange", "S", "Last Sync", summary["last_sync"], summary["last_sync_detail"]),
    ]
    for column, (color, icon, label, value, caption) in zip(st.columns(4), cards, strict=True):
        with column:
            st.markdown(
                f"""
                <div class="mh-card">
                    <div class="mh-card-icon {color}">{escape(icon)}</div>
                    <div>
                        <div class="mh-card-label">{escape(label)}</div>
                        <div class="mh-card-value">{escape(value)}</div>
                        <div class="mh-card-caption">{escape(caption)}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_add_symbols_panel(sync_service: SyncService) -> None:
    st.markdown(
        """
        <div class="mh-panel">
            <div class="mh-panel-title">Add symbols to watchlist</div>
            <div class="mh-panel-copy">Enter one or more tickers separated by commas</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    input_col, button_col = st.columns([4.4, 0.95])
    symbols = input_col.text_input(
        "Add symbols to watchlist",
        placeholder="AAPL, CSSX5E.MI, BTC-EUR",
        label_visibility="collapsed",
    )
    if button_col.button(
        "Add to Watchlist",
        type="primary",
        disabled=not symbols.strip(),
        use_container_width=True,
    ):
        st.session_state["add_symbols_results"] = _add_symbols(symbols, sync_service)
        st.rerun()


def _watchlist_summary(
    repository: MarketRepository,
    settings: Settings,
    assets: list[Asset],
) -> dict[str, str]:
    if not assets:
        return {
            "assets": "0",
            "positive_trends": "0",
            "avg_drawdown": "Unavailable",
            "last_sync": "Never",
            "last_sync_detail": "Add symbols to begin",
        }

    positive_trends = 0
    drawdowns: list[float] = []
    for asset in assets:
        metrics = compute_metrics(
            repository.load_prices(asset.id),
            asset_type=asset.asset_type,
            stock_annualization_factor=settings.stock_annualization_factor,
            crypto_annualization_factor=settings.crypto_annualization_factor,
        )
        positive_trends += sum(
            trend.label == "Positive"
            for trend in (metrics.short_trend, metrics.medium_trend, metrics.long_trend)
        )
        if metrics.drawdown_52w is not None:
            drawdowns.append(metrics.drawdown_52w)

    syncs = repository.latest_sync_for_symbols(asset.symbol for asset in assets)
    last_sync = max((sync.created_at for sync in syncs.values()), default=None)
    return {
        "assets": str(len(assets)),
        "positive_trends": str(positive_trends),
        "avg_drawdown": _pct(sum(drawdowns) / len(drawdowns)) if drawdowns else "Unavailable",
        "last_sync": _relative_time(last_sync),
        "last_sync_detail": _format_datetime(last_sync),
    }


def _filter_table(table: pd.DataFrame, filter_type: str, search: str) -> pd.DataFrame:
    filtered = table
    canonical = asset_types.FILTER_OPTIONS.get(filter_type)
    if canonical is not None:
        filtered = filtered[filtered["Type"] == canonical]

    query = search.strip().casefold()
    if query:
        filtered = filtered[filtered["_Search"].str.casefold().str.contains(query, regex=False)]
    return filtered


_WATCHLIST_HEADERS = [
    ("Symbol", ""),
    ("Name", ""),
    ("Type", ""),
    ("Price", "num"),
    ("Trend", ""),
    ("1D", "num"),
    ("1M", "num"),
    ("1Y", "num"),
    ("3Y", "num"),
    ("Short", ""),
    ("Medium", ""),
    ("Long", ""),
    ("Volatility (1Y)", ""),
    ("Drawdown (1Y)", "num"),
    ("Updated", ""),
]


def _render_watchlist_table(table: pd.DataFrame, sort_by: str, ascending: bool) -> None:
    head = _watchlist_header_html(sort_by, ascending)
    body = "".join(_watchlist_row_html(row) for _, row in table.iterrows())
    st.markdown(
        f'<div class="mh-wl-wrap"><table class="mh-wl">'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>",
        unsafe_allow_html=True,
    )


def _watchlist_header_html(sort_by: str, ascending: bool) -> str:
    cells = []
    for label, css in _WATCHLIST_HEADERS:
        token = _WL_HEADER_TOKEN.get(label)
        if token is None:
            cells.append(f'<th class="{css}">{escape(label)}</th>')
            continue
        active = token == sort_by
        if active:
            arrow = " ▲" if ascending else " ▼"
            next_dir = "desc" if ascending else "asc"
        else:
            arrow = ""
            next_dir = "asc"
        classes = " ".join(part for part in (css, "sortable", "active" if active else "") if part)
        href = f"?wl_sort={token}&amp;wl_dir={next_dir}"
        cells.append(
            f'<th class="{classes}"><a href="{href}" target="_self">{escape(label)}{arrow}</a></th>'
        )
    return "".join(cells)


def _watchlist_row_html(row: pd.Series) -> str:
    cells = [
        f'<td class="sym">{escape(str(row["Symbol"]))}</td>',
        f'<td class="name">{escape(str(row["Name"]))}</td>',
        f"<td>{_type_pill(str(row['Type']))}</td>",
        f'<td class="num price">{escape(str(row["Price"]))}</td>',
        f"<td>{_sparkline_svg(row['Sparkline'])}</td>",
        _return_cell(str(row["1D"])),
        _return_cell(str(row["1M"])),
        _return_cell(str(row["1Y"])),
        _return_cell(str(row["3Y"])),
        f"<td>{_trend_pill(str(row['Short']))}</td>",
        f"<td>{_trend_pill(str(row['Medium']))}</td>",
        f"<td>{_trend_pill(str(row['Long']))}</td>",
        f"<td>{_vol_bar(row['Volatility (1Y)'])}</td>",
        _return_cell(str(row["52W Drawdown"])),
        f'<td class="upd">{escape(str(row["Updated"]))}</td>',
    ]
    return f"<tr>{''.join(cells)}</tr>"


def _return_cell(text: str) -> str:
    return f'<td class="num {_sign_class(text)}">{escape(text)}</td>'


def _sign_class(text: str) -> str:
    if not text or text == "Unavailable":
        return "flat"
    try:
        value = float(text.replace("%", "").replace("+", "").replace(",", ""))
    except ValueError:
        return ""
    return "up" if value > 0 else "down" if value < 0 else "flat"


def _trend_pill(label: str) -> str:
    return f'<span class="mh-pill {_trend_status_class(label)}">{escape(label)}</span>'


def _type_pill(asset_type: str) -> str:
    css = asset_types.pill_css(asset_type)
    label = asset_types.pill_label(asset_type)
    return f'<span class="mh-type {css}">{escape(label)}</span>'


def _vol_bar(value: float) -> str:
    if value is None or pd.isna(value):
        return '<span class="flat">Unavailable</span>'
    width = max(0.0, min(100.0, float(value)))
    return (
        '<div class="mh-vol"><div class="mh-vol-track">'
        f'<div class="mh-vol-fill" style="width: {width:.1f}%"></div></div>'
        f'<span class="mh-vol-val">{float(value):.1f}%</span></div>'
    )


def _sparkline_svg(points: object) -> str:
    if not isinstance(points, (list, tuple)) or len(points) < 2:
        return '<span class="flat">—</span>'
    width, height, pad = 84.0, 26.0, 3.0
    count = len(points)
    clamped = [max(0.0, min(100.0, float(p))) for p in points]
    coords = [
        (
            index / (count - 1) * width,
            height - pad - (value / 100.0) * (height - 2 * pad),
        )
        for index, value in enumerate(clamped)
    ]
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    color = "#039855" if clamped[-1] >= clamped[0] else "#d92d20"
    return (
        f'<svg class="mh-spark" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" fill="none">'
        f'<polyline points="{polyline}" stroke="{color}" stroke-width="1.6" '
        'stroke-linecap="round" stroke-linejoin="round" /></svg>'
    )


def _render_asset_analysis(
    repository: MarketRepository,
    settings: Settings,
    assets: list[Asset],
) -> None:
    st.markdown('<div class="mh-section-title">Asset Analysis</div>', unsafe_allow_html=True)
    if not assets:
        st.warning("Add an asset before opening the analysis page.")
        return
    selected = st.selectbox("Symbol", [asset.symbol for asset in assets])
    asset = next(asset for asset in assets if asset.symbol == selected)
    prices = repository.load_prices(asset.id)
    metrics = compute_metrics(
        prices,
        asset_type=asset.asset_type,
        stock_annualization_factor=settings.stock_annualization_factor,
        crypto_annualization_factor=settings.crypto_annualization_factor,
    )
    _render_asset_header(asset, metrics, repository)
    _render_trend_cards(metrics)
    _render_momentum_card(metrics)
    _render_price_chart(prices, asset)
    _render_metrics(metrics)


def _render_compare(repository: MarketRepository, assets: list[Asset]) -> None:
    st.markdown('<div class="mh-section-title">Compare</div>', unsafe_allow_html=True)
    if len(assets) < 2:
        st.warning("Add at least two assets to compare normalized performance.")
        return
    selected = st.multiselect(
        "Assets",
        [asset.symbol for asset in assets],
        default=[],
        max_selections=5,
    )
    if len(selected) < 2:
        st.warning("Select two to five assets.")
        return
    asset_by_symbol = {asset.symbol: asset for asset in assets}
    price_map = {symbol: repository.load_prices(asset_by_symbol[symbol].id) for symbol in selected}
    normalized = normalized_performance(price_map)
    if normalized.empty:
        st.warning("The selected assets do not have enough overlapping history.")
        return
    figure = go.Figure()
    for symbol in normalized.columns:
        figure.add_trace(
            go.Scatter(
                x=normalized.index,
                y=normalized[symbol] * 100,
                mode="lines",
                name=symbol,
                line={"width": 2.0},
            )
        )
    _style_chart(figure, y_title="Normalized return (%)", colorway=_COMPARE_COLORWAY)
    st.plotly_chart(figure, use_container_width=True)
    st.caption("Comparison forward-fills display data only; stored source prices are unchanged.")


def _render_learn() -> None:
    st.markdown('<div class="mh-section-title">Learn</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="mh-panel"><div class="mh-panel-title">Understand every metric</div>'
        '<div class="mh-panel-copy">Plain-language explanations of how each indicator is '
        "calculated and how to read it — informational only, never a trading signal.</div></div>",
        unsafe_allow_html=True,
    )
    if not _EXPLAINER_PATH.is_file():
        st.warning("Explanations document is unavailable.")
        return
    st.markdown(_EXPLAINER_PATH.read_text(encoding="utf-8"))


def _add_symbols(symbols: str, sync_service: SyncService) -> list[TickerSyncResult]:
    results: list[TickerSyncResult] = []
    for raw_symbol in symbols.replace("\n", ",").split(","):
        symbol = raw_symbol.strip()
        if symbol:
            if normalize_symbol(symbol) == "BTCEUR":
                symbol = "BTC-EUR"
            results.append(sync_service.add_symbol(symbol))
    return results


def _render_sync_results(results: list[TickerSyncResult] | None) -> None:
    """Render the outcome of the last add operation; persists across reruns."""

    if not results:
        return
    loaded = [r.symbol for r in results if r.status in ("success", "skipped")]
    errored = [r.symbol for r in results if r.status == "failed"]
    if loaded:
        st.success(f"Loaded ({len(loaded)}): {', '.join(loaded)}")
    if errored:
        st.error(f"Could not load ({len(errored)}): {', '.join(errored)}")
    for result in results:
        if result.status == "success":
            st.caption(
                f"✓ {result.symbol}: {result.inserted_rows} inserted, "
                f"{result.updated_rows} updated."
            )
        elif result.status == "skipped":
            st.caption(f"• {result.symbol}: {result.reason}")
        else:
            st.caption(f"✗ {result.symbol}: {result.reason}")


def _watchlist_table(
    repository: MarketRepository,
    settings: Settings,
    assets: list[Asset],
) -> pd.DataFrame:
    columns = [
        "Symbol",
        "Name",
        "Type",
        "Price",
        "Currency",
        "Sparkline",
        "1D",
        "1M",
        "3M",
        "YTD",
        "1Y",
        "3Y",
        "Short",
        "Medium",
        "Long",
        "Volatility (1Y)",
        "52W Drawdown",
        "Updated",
        "_Search",
        "_Price",
        "_1D",
        "_1M",
        "_1Y",
        "_3Y",
        "_Volatility",
        "_52W Drawdown",
        "_Updated",
    ]
    syncs = repository.latest_sync_for_symbols(asset.symbol for asset in assets)
    rows = []
    for asset in assets:
        prices = repository.load_prices(asset.id)
        metrics = compute_metrics(
            prices,
            asset_type=asset.asset_type,
            stock_annualization_factor=settings.stock_annualization_factor,
            crypto_annualization_factor=settings.crypto_annualization_factor,
        )
        sync = syncs.get(asset.symbol)
        volatility_1y = _annualized_volatility(
            prices,
            asset_type=asset.asset_type,
            stock_annualization_factor=settings.stock_annualization_factor,
            crypto_annualization_factor=settings.crypto_annualization_factor,
        )
        rows.append(
            {
                "Symbol": asset.symbol,
                "Name": asset.name or "",
                "Type": asset.asset_type,
                "Price": _money(metrics.latest_price, asset.currency),
                "Currency": asset.currency or "",
                "Sparkline": _price_sparkline(prices),
                "1D": _pct(metrics.daily_return),
                "1M": _pct(metrics.one_month_return),
                "3M": _pct(metrics.three_month_return),
                "YTD": _pct(metrics.ytd_return),
                "1Y": _pct(metrics.one_year_return),
                "3Y": _pct(metrics.three_year_return),
                "Short": metrics.short_trend.label,
                "Medium": metrics.medium_trend.label,
                "Long": metrics.long_trend.label,
                "Volatility (1Y)": _num_pct(volatility_1y),
                "52W Drawdown": _pct(metrics.drawdown_52w),
                "Updated": _relative_time(sync.created_at if sync else None),
                "_Search": f"{asset.symbol} {asset.name or ''} {asset.asset_type}",
                "_Price": _num(metrics.latest_price),
                "_1D": _num(metrics.daily_return),
                "_1M": _num(metrics.one_month_return),
                "_1Y": _num(metrics.one_year_return),
                "_3Y": _num(metrics.three_year_return),
                "_Volatility": _num(volatility_1y),
                "_52W Drawdown": _num(metrics.drawdown_52w),
                "_Updated": sync.created_at if sync else None,
            }
        )
    return pd.DataFrame(rows, columns=columns)


# Watchlist columns the user can sort by, keyed by URL token:
# token -> (header label, DataFrame sort key). Non-listed columns are not sortable.
_WL_SORTABLE: dict[str, tuple[str, str]] = {
    "symbol": ("Symbol", "Symbol"),
    "price": ("Price", "_Price"),
    "1d": ("1D", "_1D"),
    "1m": ("1M", "_1M"),
    "1y": ("1Y", "_1Y"),
    "3y": ("3Y", "_3Y"),
    "volatility": ("Volatility (1Y)", "_Volatility"),
}
_WL_DEFAULT_SORT = "symbol"
_WL_HEADER_TOKEN: dict[str, str] = {label: token for token, (label, _) in _WL_SORTABLE.items()}


def _watchlist_sort_state() -> tuple[str, bool]:
    """Read the active watchlist sort column/direction from the URL query params."""
    params = st.query_params
    sort_by = params.get("wl_sort", _WL_DEFAULT_SORT)
    if sort_by not in _WL_SORTABLE:
        sort_by = _WL_DEFAULT_SORT
    ascending = params.get("wl_dir", "asc") != "desc"
    return sort_by, ascending


def _sort_table(table: pd.DataFrame, sort_by: str, ascending: bool) -> pd.DataFrame:
    key = _WL_SORTABLE[sort_by][1]
    sorted_table = table.sort_values(key, ascending=ascending, na_position="last")
    return sorted_table[[column for column in sorted_table.columns if not column.startswith("_")]]


def _filter_assets(assets: list[Asset], filter_type: str) -> list[Asset]:
    canonical = asset_types.FILTER_OPTIONS.get(filter_type)
    if canonical is None:
        return assets
    return [asset for asset in assets if asset.asset_type == canonical]


def _render_asset_header(
    asset: Asset,
    metrics: MetricsSnapshot,
    repository: MarketRepository,
) -> None:
    latest_sync = repository.latest_sync_for_symbols([asset.symbol]).get(asset.symbol)
    latest_date = metrics.latest_date.isoformat() if metrics.latest_date else "Unavailable"
    stats = [
        ("Symbol", asset.symbol, None),
        ("Price", _money(metrics.latest_price, asset.currency), metrics.daily_change),
        ("1D", _pct(metrics.daily_return), None),
        ("Currency", asset.currency or "Unavailable", None),
        ("Latest date", latest_date, None),
    ]
    for column, (label, value, delta) in zip(st.columns(5), stats, strict=True):
        with column:
            st.markdown(_stat_card(label, value, delta), unsafe_allow_html=True)
    st.caption(
        f"{asset.name or asset.symbol} | {asset.asset_type} | "
        f"Exchange: {asset.exchange or 'Unavailable'} | "
        f"Last sync: {latest_sync.created_at if latest_sync else 'Unavailable'}"
    )


def _stat_card(label: str, value: str, delta: float | None) -> str:
    delta_html = ""
    if delta is not None:
        direction = "up" if delta > 0 else "down" if delta < 0 else "flat"
        delta_html = f'<div class="mh-stat-delta {direction}">{escape(_signed(delta))}</div>'
    return (
        '<div class="mh-stat">'
        f'<div class="mh-stat-label">{escape(label)}</div>'
        f'<div class="mh-stat-value">{escape(value)}</div>'
        f"{delta_html}"
        "</div>"
    )


def _signed(value: float) -> str:
    return f"{value:+,.2f}"


def _render_trend_cards(metrics: MetricsSnapshot) -> None:
    cards = [
        ("Short term", metrics.short_trend),
        ("Medium term", metrics.medium_trend),
        ("Long term", metrics.long_trend),
    ]
    for column, (title, trend) in zip(st.columns(3), cards, strict=True):
        with column:
            st.markdown(_trend_card(title, trend), unsafe_allow_html=True)


def _trend_card(title: str, trend: TrendSnapshot) -> str:
    status = _trend_status_class(trend.label)
    distance = trend.price_distance
    direction = "flat"
    if distance is not None:
        direction = "up" if distance > 0 else "down" if distance < 0 else "flat"
    distance_html = (
        f'<span class="mh-trend-distance {direction}">{escape(_pct(distance))}</span>'
        if distance is not None
        else ""
    )
    return (
        f'<div class="mh-trend-card {status}">'
        f'<div class="mh-trend-title">{escape(title)}</div>'
        '<div class="mh-trend-row">'
        f'<span class="mh-trend-badge {status}">{escape(trend.label)}</span>'
        f"{distance_html}"
        "</div>"
        f'<div class="mh-trend-caption">{escape(_trend_caption(trend))}</div>'
        "</div>"
    )


def _trend_status_class(label: str) -> str:
    return {
        "Positive": "is-positive",
        "Negative": "is-negative",
        "Mixed": "is-mixed",
    }.get(label, "is-unavailable")


def _trend_caption(trend: TrendSnapshot) -> str:
    return (
        f"{trend.explanation} Performance: {_pct(trend.performance)}. "
        f"{trend.moving_average_name}: {_number(trend.moving_average_value)}."
    )


def _render_price_chart(prices: pd.DataFrame, asset: Asset) -> None:
    if prices.empty:
        st.warning("No stored price history for this asset.")
        return
    periods: dict[str, Callable[[date], date | None]] = {
        "1M": lambda end: end - timedelta(days=31),
        "3M": lambda end: end - timedelta(days=93),
        "6M": lambda end: end - timedelta(days=186),
        "1Y": lambda end: end - timedelta(days=365),
        "3Y": lambda end: end - timedelta(days=365 * 3),
        "MAX": lambda end: None,
    }
    selected_period = st.radio("Range", list(periods), horizontal=True, index=3)
    frame = add_indicators(prices)
    end_date = frame.index[-1]
    start = periods[selected_period](end_date)
    if start is not None:
        frame = frame[frame.index >= start]
    figure = go.Figure()
    for column, (name, color, dash, width) in _SERIES_STYLE.items():
        figure.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame[column],
                mode="lines",
                name=name,
                line={"color": color, "dash": dash, "width": width},
            )
        )
    _style_chart(
        figure,
        title=f"{asset.symbol} price history",
        y_title=f"Price ({asset.currency or 'currency unavailable'})",
    )
    st.plotly_chart(figure, use_container_width=True)


def _style_chart(
    figure: go.Figure,
    *,
    title: str | None = None,
    y_title: str,
    x_title: str = "Date",
    colorway: list[str] | None = None,
) -> None:
    """Apply the shared Market Horizon look to a Plotly figure (in place)."""

    # With a title, place the legend vertically on the right so it never collides with the
    # title; without a title, a compact horizontal legend along the top reads best.
    if title:
        legend = {"orientation": "v", "yanchor": "top", "y": 1, "xanchor": "left", "x": 1.02}
        margin = {"l": 12, "r": 24, "t": 48, "b": 12}
    else:
        legend = {"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0}
        margin = {"l": 12, "r": 12, "t": 36, "b": 12}
    figure.update_layout(
        title={"text": title, "font": {"color": _INK, "size": 16}} if title else None,
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)",
        font={"color": _MUTED, "family": "system-ui, -apple-system, sans-serif"},
        colorway=colorway,
        hovermode="x unified",
        hoverlabel={"bgcolor": "#ffffff", "bordercolor": _GRID, "font": {"color": _INK}},
        legend={**legend, "title": None},
        margin=margin,
    )
    figure.update_xaxes(
        title_text=x_title,
        gridcolor=_GRID,
        zeroline=False,
        showspikes=True,
        spikemode="across",
        spikethickness=1,
        spikecolor=_MUTED,
        spikedash="dot",
        title_font={"color": _MUTED},
    )
    figure.update_yaxes(
        title_text=y_title,
        gridcolor=_GRID,
        zeroline=False,
        title_font={"color": _MUTED},
    )


def _render_momentum_card(metrics: MetricsSnapshot) -> None:
    st.markdown(_momentum_card_html(metrics.rsi_14), unsafe_allow_html=True)


def _momentum_card_html(rsi: float | None) -> str:
    value = _number(rsi)
    if rsi is None:
        body = f'<div class="mh-rsi-value flat">{escape(value)}</div>'
    else:
        fill = max(0.0, min(100.0, rsi))
        bar = f'<div class="mh-rsi-fill" style="width:{fill:.1f}%"></div>'
        body = (
            f'<div class="mh-rsi-value">{escape(value)}</div>'
            f'<div class="mh-rsi-bar">{bar}</div>'
            '<div class="mh-rsi-scale"><span>0</span><span>100</span></div>'
        )
    return (
        '<div class="mh-momentum-card">'
        '<div class="mh-metric-card-title">Momentum</div>'
        '<div class="mh-momentum-body">'
        '<div class="mh-rsi-label">RSI 14</div>'
        f"{body}"
        "</div></div>"
    )


def _render_metrics(metrics: MetricsSnapshot) -> None:
    sections = {
        "Performance": {
            "1D": metrics.daily_return,
            "1M": metrics.one_month_return,
            "3M": metrics.three_month_return,
            "YTD": metrics.ytd_return,
            "1Y": metrics.one_year_return,
            "3Y": metrics.three_year_return,
        },
        "Trend": {
            "Price vs EMA 20": metrics.short_trend.price_distance,
            "Price vs SMA 50": metrics.medium_trend.price_distance,
            "Price vs SMA 200": metrics.long_trend.price_distance,
        },
        "Risk": {
            "30-observation volatility": metrics.volatility_30,
            "90-observation volatility": metrics.volatility_90,
            "52W drawdown": metrics.drawdown_52w,
            "Maximum drawdown": metrics.max_drawdown,
        },
        "Range": {
            "52W low": metrics.low_52w,
            "52W high": metrics.high_52w,
            "52W range position": metrics.range_position_52w,
        },
    }
    cards = "".join(_metric_card_html(title, values) for title, values in sections.items())
    st.markdown(f'<div class="mh-metrics-grid">{cards}</div>', unsafe_allow_html=True)


_SIGNED_METRIC_KEYS = {"52W drawdown", "Maximum drawdown"}


def _metric_is_signed(section: str, key: str) -> bool:
    """Whether a metric's value reads as a gain/loss worth green/red coloring.

    Performance and Trend distances are directional; drawdowns are always losses.
    Volatility, RSI, and range levels are neutral magnitudes and stay uncolored to
    avoid implying a positive/negative judgement.
    """
    return section in {"Performance", "Trend"} or key in _SIGNED_METRIC_KEYS


def _metric_card_html(section: str, values: dict[str, float | None]) -> str:
    rows = []
    for key, value in values.items():
        text = _format_metric(section, value)
        if _metric_is_signed(section, key):
            css = _sign_class(text)
        else:
            css = "flat" if text == "Unavailable" else ""
        rows.append(
            f'<div class="mh-metric-row"><span class="mh-metric-name">{escape(key)}</span>'
            f'<span class="mh-metric-value {css}">{escape(text)}</span></div>'
        )
    return (
        f'<div class="mh-metric-card"><div class="mh-metric-card-title">{escape(section)}</div>'
        f"{''.join(rows)}</div>"
    )


def _format_metric(section: str, value: float | None) -> str:
    if section in {"Performance", "Trend", "Risk"} and value is not None:
        return _pct(value)
    if section == "Range" and value is not None and 0 <= value <= 1:
        return _pct(value)
    return _number(value)


def _annualized_volatility(
    prices: pd.DataFrame,
    *,
    asset_type: str,
    stock_annualization_factor: int,
    crypto_annualization_factor: int,
) -> float | None:
    close = _close_series(prices)
    returns = close.pct_change().dropna().tail(252)
    if len(returns) < 2:
        return None
    annualization = (
        crypto_annualization_factor
        if asset_types.is_continuous(asset_type)
        else stock_annualization_factor
    )
    value = returns.std()
    return None if pd.isna(value) else float(value * sqrt(annualization))


def _price_sparkline(prices: pd.DataFrame) -> list[float]:
    close = _close_series(prices).tail(30)
    if close.empty:
        return []
    low = close.min()
    high = close.max()
    if high == low:
        return [50.0 for _ in close]
    return [float((value - low) / (high - low) * 100) for value in close]


def _close_series(prices: pd.DataFrame) -> pd.Series:
    if prices.empty:
        return pd.Series(dtype=float)
    column = "adj_close" if "adj_close" in prices.columns else "close"
    if column not in prices.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(prices[column], errors="coerce").dropna()


def _relative_time(value: datetime | None) -> str:
    if value is None:
        return "Unavailable"
    aware_value = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    delta = datetime.now(UTC) - aware_value.astimezone(UTC)
    if delta < timedelta(minutes=1):
        return "Just now"
    if delta < timedelta(hours=1):
        minutes = int(delta.total_seconds() // 60)
        return f"{minutes}m ago"
    if delta < timedelta(days=1):
        hours = int(delta.total_seconds() // 3600)
        return f"{hours}h ago"
    days = delta.days
    if days < 30:
        return f"{days}d ago"
    return aware_value.strftime("%b %-d, %Y")


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "No successful sync yet"
    aware_value = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware_value.astimezone(UTC).strftime("%b %-d, %Y %H:%M UTC")


def _money(value: float | None, currency: str | None = None) -> str:
    if value is None:
        return "Unavailable"
    suffix = f" {currency}" if currency else ""
    return f"{value:,.2f}{suffix}"


def _pct(value: float | None) -> str:
    if value is None:
        return "Unavailable"
    return f"{value * 100:+.2f}%"


def _number(value: float | None) -> str:
    if value is None:
        return "Unavailable"
    return f"{value:,.2f}"


def _num(value: float | None) -> float:
    return float("nan") if value is None else value


def _num_pct(value: float | None) -> float:
    return float("nan") if value is None else value * 100
