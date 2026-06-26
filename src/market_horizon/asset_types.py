"""Canonical asset-type classification, independent of the data provider.

Yahoo Finance is inconsistent: it returns ``quoteType = EQUITY`` (or nothing) for
indices, FX pairs, and futures. This module normalizes those into a small, stable
taxonomy used across the provider, analytics, and UI so the rest of the app never
has to reason about provider quirks.
"""

STOCK = "Stock"
ETF = "ETF"
FUND = "Fund"
INDEX = "Index"
CRYPTOCURRENCY = "Cryptocurrency"
FOREX = "Forex"
FUTURE = "Future"

ASSET_TYPES = (STOCK, ETF, FUND, INDEX, CRYPTOCURRENCY, FOREX, FUTURE)

# quoteType (lower-cased) -> canonical type. Symbol-shape rules in ``classify``
# take precedence over this for the instruments Yahoo systematically mislabels.
_QUOTE_TYPE_MAP = {
    "etf": ETF,
    "mutualfund": FUND,
    "equity": STOCK,
    "stock": STOCK,
    "cryptocurrency": CRYPTOCURRENCY,
    "crypto": CRYPTOCURRENCY,
    "index": INDEX,
    "currency": FOREX,
    "future": FUTURE,
}

# canonical type -> (display label, css class for the UI pill)
_DISPLAY = {
    STOCK: ("Stock", "t-stock"),
    ETF: ("ETF", "t-etf"),
    FUND: ("Fund", "t-fund"),
    INDEX: ("Index", "t-index"),
    CRYPTOCURRENCY: ("Crypto", "t-crypto"),
    FOREX: ("Forex", "t-forex"),
    FUTURE: ("Future", "t-future"),
}

# Toolbar chip label -> canonical type ("All" means no filtering).
FILTER_OPTIONS = {
    "Stocks": STOCK,
    "ETFs": ETF,
    "Funds": FUND,
    "Indices": INDEX,
    "Crypto": CRYPTOCURRENCY,
}


def classify(symbol: str, quote_type: str | None) -> str:
    """Map a symbol and Yahoo ``quoteType`` to a canonical asset type."""

    # Symbol-shape rules first — Yahoo mislabels these as EQUITY / empty.
    if symbol.startswith("^"):
        return INDEX
    if symbol.endswith("=F"):
        return FUTURE
    if symbol.endswith("=X"):
        return FOREX

    mapped = _QUOTE_TYPE_MAP.get((quote_type or "").lower())
    if mapped is not None:
        return mapped

    # Last-resort shape: hyphenated pairs are crypto (BTC-EUR), but only when
    # quoteType gave nothing — keeps BRK-B (quoteType=EQUITY) as Stock above.
    if "-" in symbol:
        return CRYPTOCURRENCY
    return STOCK


def pill_label(asset_type: str) -> str:
    """Return the short display label for an asset type."""

    label, _ = _DISPLAY.get(asset_type, (asset_type, "t-default"))
    return label


def pill_css(asset_type: str) -> str:
    """Return the CSS class for an asset type's pill."""

    _, css = _DISPLAY.get(asset_type, (asset_type, "t-default"))
    return css


def is_continuous(asset_type: str) -> bool:
    """Whether the asset trades every calendar day (365-day annualization)."""

    return asset_type == CRYPTOCURRENCY
