import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent
CFG = json.loads((ROOT / "v2_config.json").read_text(encoding="utf-8"))
SNAP = json.loads((ROOT / "market_snapshot.json").read_text(encoding="utf-8"))
STATE = ROOT / "state.json"
DASH = ROOT / "dashboard.json"
INITIAL = float(CFG["capital_inicial"])


def default_state():
    return {
        "version": "2.1",
        "strategies": {
            "HUNTER_X": {"capital": INITIAL, "positions": [], "trades": [], "equity_peak": INITIAL},
            "HUNTER_EXTREME": {"capital": INITIAL, "positions": [], "trades": [], "equity_peak": INITIAL},
        },
        "updated_at": None,
    }


def load_state():
    if not STATE.exists():
        return default_state()
    try:
        raw = json.loads(STATE.read_text(encoding="utf-8"))
        if "strategies" in raw and all(k in raw["strategies"] for k in ("HUNTER_X", "HUNTER_EXTREME")):
            return raw
    except Exception:
        pass
    return default_state()


def run_strategy(name, cfg, state):
    st = state["strategies"][name]
    positions = list(st.get("positions", []))
    trades = list(st.get("trades", []))
    capital = float(st.get("capital", INITIAL))
    now = datetime.now(timezone.utc).isoformat()

    by = {(x["market"], x["symbol"]): x for x in SNAP.get("candidates", [])}
    closed = []
    kept = []

    for p in positions:
        c = by.get((p["market"], p["symbol"]))
        price = float(c["price"]) if c and c.get("price") is not None else float(p["entry"])
        exit_price = None
        reason = None
        if price <= p["stop"]:
            exit_price, reason = float(p["stop"]), "STOP"
        elif price >= p["target"]:
            exit_price, reason = float(p["target"]), "ALVO"

        if exit_price is None:
            kept.append(p)
            continue

        gross = (exit_price - p["entry"]) * p["qty"]
        tax = max(gross, 0.0) * float(CFG["tax_rate_pct"]) / 100.0
        capital += p["qty"] * exit_price
        trade = {
            **p,
            "exit": exit_price,
            "gross": gross,
            "tax": tax,
            "net": gross - tax,
            "reason": reason,
            "closed_at": now,
        }
        trades.append(trade)
        closed.append(trade)

    positions = kept

    for c in SNAP.get("candidates", []):
        if len(positions) >= int(cfg["max_positions"]):
            break
        score = float(c.get("score", 0))
        if score < float(cfg["score_min"]):
            continue
        if c.get("signal") != "COMPRA":
            continue
        if any(p["symbol"] == c["symbol"] for p in positions):
            continue

        price = float(c["price"])
        atr = max(float(c.get("atr", 0)), price * 0.001)
        stop = max(price - float(cfg["stop_atr"]) * atr, price * 0.985)
        target = price + float(cfg["target_atr"]) * atr
        risk_value = capital * float(cfg["risk_pct"]) / 100.0
        risk_distance = max(price - stop, price * 0.001)
        qty_risk = risk_value / risk_distance
        qty_cap = (capital * float(cfg["max_position_pct"]) / 100.0) / price
        qty = min(qty_risk, qty_cap)
        value = qty * price

        if qty <= 0 or value <= 0 or value > capital:
            continue

        positions.append({
            "symbol": c["symbol"],
            "market": c["market"],
            "qty": qty,
            "entry": price,
            "stop": stop,
            "target": target,
            "score": score,
            "opened_at": now,
        })
        capital -= value

    marked = 0.0
    for p in positions:
        c = by.get((p["market"], p["symbol"]))
        mark = float(c["price"]) if c and c.get("price") is not None else float(p["entry"])
        marked += p["qty"] * mark

    equity = capital + marked
    peak = max(float(st.get("equity_peak", INITIAL)), equity)
    pnl = sum(float(t.get("net", 0)) for t in trades)

    st.update({
        "capital": capital,
        "positions": positions,
        "trades": trades,
        "equity_peak": peak,
    })

    return {
        "capital": capital,
        "equity": equity,
        "pnl_net": pnl,
        "return_pct": (equity / INITIAL - 1) * 100,
        "positions": len(positions),
        "trades": len(trades),
        "closed_now": len(closed),
        "win_rate": (sum(float(t.get("net", 0)) > 0 for t in trades) / len(trades) * 100) if trades else 0,
        "drawdown_pct": max(0.0, (1 - equity / peak) * 100),
        "opened_now": max(0, len(positions) - (len(positions) - 0)),
    }


def main():
    if not SNAP.get("candidates"):
        raise RuntimeError("Scanner sem candidatos: ciclo abortado para não publicar dados vazios.")

    state = load_state()
    hx = run_strategy("HUNTER_X", CFG["hunter_x"], state)
    he = run_strategy("HUNTER_EXTREME", CFG["hunter_extreme"], state)
    now = datetime.now(timezone.utc).isoformat()

    state["updated_at"] = now
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    candidates = sorted(
        SNAP.get("candidates", []),
        key=lambda c: (float(c.get("score", 0)), float(c.get("momentum_pct", 0))),
        reverse=True,
    )[:12]

    dashboard = {
        "version": "V2.1",
        "updated_at": now,
        "paper_trading": True,
        "real_orders": False,
        "scanner_updated_at": SNAP.get("updated_at"),
        "markets_scanned": int(SNAP.get("markets_scanned", len(SNAP.get("candidates", [])))),
        "strategies": {"HUNTER_X": hx, "HUNTER_EXTREME": he},
        "opportunities": candidates,
    }
    DASH.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(dashboard, ensure_ascii=False))


if __name__ == "__main__":
    main()
