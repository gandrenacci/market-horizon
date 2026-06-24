from market_horizon.data.yfinance_provider import _asset_type, normalize_symbol


def test_normalize_symbol_uppercases_and_trims() -> None:
    assert normalize_symbol(" btc-eur ") == "BTC-EUR"


def test_asset_type_prefers_quote_type_over_symbol_shape() -> None:
    # A hyphenated equity (e.g. Berkshire B shares) must not be read as crypto.
    assert _asset_type({"quoteType": "EQUITY"}, "BRK-B") == "Stock"
    assert _asset_type({"quoteType": "ETF"}, "SPY") == "ETF"
    assert _asset_type({"quoteType": "MUTUALFUND"}, "VFIAX") == "ETF"
    assert _asset_type({"quoteType": "CRYPTOCURRENCY"}, "BTC-EUR") == "Cryptocurrency"


def test_asset_type_falls_back_to_symbol_shape_without_quote_type() -> None:
    assert _asset_type({}, "BTC-EUR") == "Cryptocurrency"
    assert _asset_type({}, "AAPL") == "Stock"
