# DOT Trader V2

Paper Trading only. Never sends real orders.

Architecture:
- v2_scanner.py: one market snapshot per cycle
- v2_engine.py: independent HUNTER X and HUNTER EXTREME simulations
- state.json: persistent V2 state
- dashboard.json: single source of truth for the dashboard
- index.html: mobile dashboard
- GitHub Actions: one cycle every 5 minutes

The V2 engine is intentionally independent from the legacy engine.
