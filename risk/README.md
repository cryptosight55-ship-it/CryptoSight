# risk/

Not yet populated. Stop-loss/take-profit math currently lives inline in
`signals/generator.py` (relocated `src/signal_generator.py`), keyed off
the per-timeframe percentages in `config/settings.py`. Future work per
the brief: ATR-based dynamic stops, position sizing, max exposure,
liquidity/volatility filters, trade invalidation -- as their own module
that the signal aggregator calls into, not inline percentage math.
