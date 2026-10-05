"""DOT Trader - motor multi-estrategia de Paper Trading.
Mantem HUNTER X e HUNTER EXTREME totalmente independentes.
Nunca envia ordens reais.
"""
from pathlib import Path
from datetime import datetime, timezone
import json, urllib.request, urllib.parse

CAPITAL_INICIAL = 10000.0
RISCO_PCT = 0.5
MAX_POSICOES = 50
MAX_POSITION_PCT = 2.0
SCORE_MIN = 70
STATE = Path("docs/paper_state.json")
EXTREME_STATE = Path("docs/paper_state_extreme.json")
EXTREME_SCORE_MIN = 50
EXTREME_RISCO_PCT = 2.0
EXTREME_MAX_POSICOES = 20
EXTREME_MAX_POSITION_PCT = 10.0
SINAL = Path("docs/sinal.json")

def load(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def b3_price(symbol):
    u = "https://brapi.dev/api/quote/" + urllib.parse.quote(symbol)
    req = urllib.request.Request(u, headers={"User-Agent": "DOT-Trader-Paper"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return float(json.loads(r.read().decode())["results"][0]["regularMarketPrice"])

def yahoo_price(symbol, market):
    y = symbol + ".SA" if market == "B3" else symbol
    u = "https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(y) + "?interval=5m&range=1d"
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read().decode())["chart"]["result"][0]
    return float(d["meta"]["regularMarketPrice"])

def crypto_price(symbol):
    u = "https://data-api.binance.vision/api/v3/ticker/price?" + urllib.parse.urlencode({"symbol": symbol})
    with urllib.request.urlopen(u, timeout=15) as r:
        return float(json.loads(r.read().decode())["price"])

def current_price(symbol, market):
    if market == "CRYPTO":
        return crypto_price(symbol)
    if market == "B3":
        return b3_price(symbol)
    return yahoo_price(symbol, market)

def run_strategy(s, state_path, strategy_name, score_min, risk_pct, max_positions, max_position_pct, stop_mult, target_mult):
    st = load(state_path, {"capital": CAPITAL_INICIAL, "positions": [], "trades": []})
    now = datetime.now(timezone.utc).isoformat()
    positions = st.get("positions", [])
    trades = st.get("trades", [])
    closed, opened = [], []
    candidates = s.get("candidates", [])

    # Reutiliza os preços já coletados pelo scanner. Isso evita dezenas de
    # consultas sequenciais por ciclo quando existem muitas posições.
    price_map = {
        (str(c.get("market", "CRYPTO")), str(c.get("symbol"))): float(c.get("price"))
        for c in candidates
        if c.get("symbol") and c.get("price") is not None
    }

    def cached_price(symbol, market, fallback):
        key = (str(market or "CRYPTO"), str(symbol))
        if key in price_map:
            return price_map[key]
        try:
            return current_price(symbol, market or "CRYPTO")
        except Exception:
            return fallback

    remaining = []
    for pos in positions:
        p = cached_price(
            pos["symbol"],
            pos.get("market", "CRYPTO"),
            float(pos["entry_price"]),
        )
        exit_price, reason = None, None
        if p <= pos["stop_price"]:
            exit_price, reason = pos["stop_price"], "STOP"
        elif p >= pos["target_price"]:
            exit_price, reason = pos["target_price"], "ALVO"
        if exit_price is None:
            remaining.append(pos)
            continue
        gross = (exit_price - pos["entry_price"]) * pos["quantity"]
        st["capital"] += pos["quantity"] * exit_price
        tax = max(0.0, gross) * 0.15
        trade = {**pos, "exit_price": exit_price, "gross": gross, "fees": 0.0,
                 "estimated_tax": tax, "net": gross - tax, "reason": reason, "closed_at": now}
        trades.append(trade)
        closed.append(trade)
    positions = remaining

    selected = []
    for c in candidates:
        if len(positions) >= max_positions:
            break
        is_extreme = strategy_name == "DOT_HUNTER_EXTREME"
        if float(c.get("score", 0)) < score_min:
            continue
        if c.get("signal") != "COMPRA" and not (is_extreme and c.get("ema9", 0) > c.get("ema21", 0)):
            continue
        symbol = c["symbol"]
        if any(x["symbol"] == symbol for x in positions):
            continue
        p = float(c["price"])
        atr_value = float(c.get("atr", 0.0))
        stop_price = max(0.0, p - stop_mult * atr_value) if atr_value > 0 else float(c.get("stop_price", p * 0.995))
        target_price = p + target_mult * atr_value if atr_value > 0 else float(c.get("target_price", p * 1.01))
        stop_distance = max(p - stop_price, p * 0.001)
        risk = st["capital"] * (risk_pct / 100)
        qty_risk = risk / stop_distance
        max_value = st["capital"] * (max_position_pct / 100)
        qty = min(qty_risk, max_value / p if p > 0 else 0)
        value = qty * p
        if qty <= 0 or value > st["capital"]:
            continue
        pos = {
            "symbol": symbol, "market": c.get("market", "CRYPTO"), "quantity": qty,
            "entry_price": p, "stop_price": stop_price, "target_price": target_price,
            "risk_value": risk, "risk_distance_pct": (stop_distance / p) * 100,
            "score": float(c["score"]), "strategy": strategy_name,
            "source": c.get("source"), "opened_at": now
        }
        positions.append(pos)
        st["capital"] -= value
        opened.append(pos)
        selected.append(c)

    st["positions"], st["trades"], st["updated_at"] = positions, trades, now
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(st, indent=2, ensure_ascii=False), encoding="utf-8")

    aberto = 0.0
    for x in positions:
        p = cached_price(
            x["symbol"],
            x.get("market", "CRYPTO"),
            float(x["entry_price"]),
        )
        aberto += float(x["quantity"]) * p
    lucro = sum(float(t.get("net", 0)) for t in trades)
    patrimonio = st["capital"] + aberto
    wins = sum(1 for t in trades if float(t.get("net", 0)) > 0)
    result = {
        "strategy": strategy_name, "selected": selected, "opened_now": len(opened),
        "opened_total": len(positions), "closed_now": len(closed), "closed": len(trades),
        "capital": st["capital"], "patrimonio": patrimonio,
        "retorno_pct": (patrimonio / CAPITAL_INICIAL - 1) * 100,
        "operacoes": len(trades), "posicoes": len(positions),
        "win_rate_pct": (wins / len(trades) * 100) if trades else 0,
        "last_event": (closed[-1] if closed else (opened[-1] if opened else None)),
        "opportunities": [
            {"symbol": c["symbol"], "market": c.get("market"), "score": c.get("score"),
             "signal": c.get("signal"), "price": c.get("price"),
             "momentum_pct": c.get("momentum_pct"), "volume_ratio": c.get("volume_ratio"),
             "reason": c.get("reasons", [])[:3]}
            for c in candidates if float(c.get("score", 0)) >= score_min
        ][:12]
    }
    data = {
        "updated_at": now,
        "config": {"capital_inicial": CAPITAL_INICIAL, "capital": st["capital"],
                   "max_position_pct": max_position_pct, "stop_mult_atr": stop_mult,
                   "target_mult_atr": target_mult, "fee_pct": 0.0, "tax_rate_pct": 15.0,
                   "paper_trading": True, "risk_per_trade_pct": risk_pct,
                   "max_positions": max_positions, "score_min": score_min,
                   "strategy": strategy_name},
        "positions": positions, "trades": trades,
        "market": {k: s.get(k) for k in ("symbol","market","price","score","signal")},
        "candidates": candidates, "summary": {
            "lucro_liquido": lucro, "patrimonio": patrimonio,
            "retorno_pct": result["retorno_pct"], "operacoes": len(trades),
            "win_rate_pct": result["win_rate_pct"]
        }
    }
    return result, data

def main():
    s = load(SINAL, {})
    hunter, hunter_data = run_strategy(s, STATE, "DOT_HUNTER_X", SCORE_MIN, RISCO_PCT, MAX_POSICOES, MAX_POSITION_PCT, 1.0, 2.0)
    extreme, extreme_data = run_strategy(s, EXTREME_STATE, "DOT_HUNTER_EXTREME", EXTREME_SCORE_MIN, EXTREME_RISCO_PCT, EXTREME_MAX_POSICOES, EXTREME_MAX_POSITION_PCT, 0.5, 1.0)

    Path("docs/dados_hunter_x.json").write_text(json.dumps(hunter_data, indent=2, ensure_ascii=False), encoding="utf-8")
    Path("docs/dados_extreme.json").write_text(json.dumps(extreme_data, indent=2, ensure_ascii=False), encoding="utf-8")
    # dados.json permanece como compatibilidade: agora aponta para HUNTER X.
    Path("dados.json").write_text(json.dumps(hunter_data, indent=2, ensure_ascii=False), encoding="utf-8")
    Path("docs/dados.json").write_text(json.dumps(hunter_data, indent=2, ensure_ascii=False), encoding="utf-8")

    combined = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "paper_trading": True, "real_orders": False,
        "comparison": {"hunter_x": hunter, "hunter_extreme": extreme},
        "extreme_opportunities": extreme["opportunities"],
        "hunter_opportunities": hunter["opportunities"]
    }
    Path("docs/comparativo.json").write_text(json.dumps(combined, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(combined, ensure_ascii=False))

if __name__ == "__main__":
    main()
