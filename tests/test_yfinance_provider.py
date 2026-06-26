from market_horizon.data.yfinance_provider import normalize_symbol


def test_normalize_symbol_uppercases_and_trims() -> None:
    assert normalize_symbol(" btc-eur ") == "BTC-EUR"
