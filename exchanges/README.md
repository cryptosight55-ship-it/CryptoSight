# exchanges/

Not yet populated. Today, exchange access (CCXT/Binance) is embedded
directly inside `data/fetcher.py`, and duplicated again inside
`database/trade_verifier.py` (its own separate `ccxt.binance()` client).

Future work: extract a small exchange-abstraction interface here so
`data/fetcher.py` and `database/trade_verifier.py` share one client, and
so adding a second exchange doesn't mean touching every caller.
