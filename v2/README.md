# DOT Trader V2.2 — Aziz Playbook

Paper Trading only. Never sends real orders.

The V2.2 engine is a fresh paper-trading baseline starting at R$10,000 per strategy. The previous V2 state is preserved in `state_pre_aziz_20261005.json`.

Methodology:
- VWAP as dynamic support/reference
- Opening Range Breakout (UTC crypto session proxy)
- Momentum and volume confirmation
- Bull Flag, ABCD and VWAP pullback heuristics
- Trend alignment with EMA 9/21/50
- Support/resistance and risk/reward filter
- Score from 0–100
- HUNTER_X entry score >= 70
- HUNTER_EXTREME entry score >= 82
- Risk-based position sizing
- Partial at +1R, runner at +2R
- Stop moves to breakeven after first partial
- 20 crypto markets scanned every cycle
- 5-minute scanner with five rapid paper cycles per scheduled run
- Real orders permanently disabled

The book by Andrew Aziz emphasizes tactics, capital management, discipline and trading psychology; this implementation converts those principles into explicit, testable rules rather than treating them as a guarantee of profitability.