from market_horizon import asset_types
from market_horizon.asset_types import classify


def test_symbol_shape_rules_override_quote_type() -> None:
    # Yahoo often returns EQUITY (or nothing) for these — the shape must win.
    assert classify("^IXIC", "EQUITY") == asset_types.INDEX
    assert classify("^GSPC", None) == asset_types.INDEX
    assert classify("GC=F", "") == asset_types.FUTURE
    assert classify("EURUSD=X", None) == asset_types.FOREX


def test_quote_type_mapping() -> None:
    assert classify("QQQM", "ETF") == asset_types.ETF
    assert classify("VFIAX", "MUTUALFUND") == asset_types.FUND
    assert classify("AAPL", "EQUITY") == asset_types.STOCK
    assert classify("BTC-USD", "CRYPTOCURRENCY") == asset_types.CRYPTOCURRENCY


def test_quote_type_takes_precedence_over_hyphen_fallback() -> None:
    # A hyphenated equity (e.g. Berkshire B shares) must not be read as crypto.
    assert classify("BRK-B", "EQUITY") == asset_types.STOCK


def test_falls_back_to_symbol_shape_without_quote_type() -> None:
    assert classify("BTC-EUR", None) == asset_types.CRYPTOCURRENCY
    assert classify("AAPL", "") == asset_types.STOCK


def test_is_continuous_only_for_crypto() -> None:
    assert asset_types.is_continuous(asset_types.CRYPTOCURRENCY) is True
    assert asset_types.is_continuous(asset_types.STOCK) is False
    assert asset_types.is_continuous(asset_types.FOREX) is False


def test_pill_helpers() -> None:
    assert asset_types.pill_label(asset_types.CRYPTOCURRENCY) == "Crypto"
    assert asset_types.pill_css(asset_types.INDEX) == "t-index"
    # Unknown type degrades gracefully.
    assert asset_types.pill_css("Mystery") == "t-default"
    assert asset_types.pill_label("Mystery") == "Mystery"
