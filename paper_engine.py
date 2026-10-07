"""DOT Trader V1 - motor multi-estrategia de Paper Trading.
Melhorias: score mais seletivo, limite de exposicao, cooldown apos stop,
filtro de risco/retorno e sizing por risco. Nunca envia ordens reais.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import json, urllib.request, urllib.parse

CAPITAL_INICIAL = 10000.0
MAX_TOTAL_EXPOSURE_PCT = 55.0
COOLDOWN_MINUTES = 20

# HUNTER X: agressiva, mas com controle de qualidade.
RISCO_PCT = 0.5
MAX_POSICOES = 20
MAX_POSITION_PCT = 3.0
SCORE_MIN = 75
STOP_MULT = 1.0
TARGET_MULT = 2.0
MIN_RR = 1.6

# EXTREME: mais frequente, com risco maior, mas ainda limitado.
EXTREME_SCORE_MIN = 65
EXTREME_RISCO_PCT = 1.0
EXTREME_MAX_POSICOES = 20
EXTREME_MAX_POSITION_PCT = 4.0
EXTREME_STOP_MULT = 0.7
EXTREME_TARGET_MULT = 1.4
EXTREME_MIN_RR = 1.25

STATE = Path("docs/paper_state.json")
EXTREME_STATE = Path("docs/paper_state_extreme.json")
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
    with urllib.request.urlopen(req, timeout=10) as r:
        return float(json.loads(r.read().decode())["results"][0]["regularMarketPrice"])

def yahoo_price(symbol, market):
    y = symbol + ".SA" if market == "B3" else symbol
    u = "https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(y) + "?interval=5m&range=1d"
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read().decode())["chart"]["result"][0]
    return float(d["meta"]["regularMarketPrice"])

def crypto_price(symbol):
    u = "https://data-api.binance.vision/api/v3/ticker/price?" + urllib.parse.urlencode({"symbol": symbol})
    with urllib.request.urlopen(u, timeout=10) as r:
        return float(json.loads(r.read().decode())["price"])

def current_price(symbol, market):
    if market == "CRYPTO":
        return crypto_price(symbol)
    if market == "B3":
        return b3_price(symbol)
    return yahoo_price(symbol, market)

def run_strategy(s, state_path, strategy_name, score_min, risk_pct, max_positions,
                 max_position_pct, stop_mult, target_mult, min_rr):
    st = load(state_path, {"capital": CAPITAL_INICIAL, "positions": [], "trades": []})
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    positions = st.get("positions", [])
    trades = st.get("trades", [])
    closed, opened = [], []
    candidates = s.get("candidates", [])

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

    # 1) Gerencia posicoes abertas.
    remaining = []
    for pos in positions:
        p = cached_price(pos["symbol"], pos.get("market", "CRYPTO"), float(pos["entry_price"]))
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
        trade = {
            **pos, "exit_price": exit_price, "gross": gross, "fees": 0.0,
            "estimated_tax": 0.0, "net": gross, "reason": reason,
            "closed_at": now_iso
        }
        trades.append(trade)
        closed.append(trade)
    positions = remaining

    # 2) Cooldown: evita reentrada imediata no mesmo ativo, especialmente apos STOP.
    cooldown_symbols = set()
    cutoff = now - timedelta(minutes=COOLDOWN_MINUTES)
    for t in reversed(trades):
        if t.get("symbol") in cooldown_symbols:
            continue
        try:
            closed_at = datetime.fromisoformat(str(t.get("closed_at", "")).replace("Z", "+00:00"))
        except Exception:
            continue
        if closed_at >= cutoff:
            cooldown_symbols.add(t.get("symbol"))

    # 3) Novas entradas, limitadas por score, RR e exposicao total.
    current_exposure = sum(float(x.get("quantity", 0)) * float(x.get("entry_price", 0)) for x in positions)
    max_exposure = max(st["capital"] + current_exposure, CAPITAL_INICIAL) * (MAX_TOTAL_EXPOSURE_PCT / 100)

    for c in candidates:
        if len(positions) >= max_positions:
            break
        score = float(c.get("score", 0))
        if score < score_min:
            continue

        is_extreme = strategy_name == "DOT_HUNTER_EXTREME"
        if c.get("signal") != "COMPRA":
            if not (is_extreme and c.get("ema9", 0) > c.get("ema21", 0) and score >= score_min):
                continue

        symbol = c["symbol"]
        if any(x["symbol"] == symbol for x in positions) or symbol in cooldown_symbols:
            continue

        p = float(c["price"])
        atr_value = float(c.get("atr", 0.0))
        if p <= 0 or atr_value <= 0:
            continue

        stop_price = max(0.0, p - stop_mult * atr_value)
        target_price = p + target_mult * atr_value
        stop_distance = p - stop_price
        reward_distance = target_price - p
        rr = reward_distance / stop_distance if stop_distance > 0 else 0
        if rr < min_rr:
            continue

        risk = st["capital"] * (risk_pct / 100)
        qty_risk = risk / stop_distance
        max_value = st["capital"] * (max_position_pct / 100)
        remaining_exposure = max(0.0, max_exposure - current_exposure)
        qty_exposure = remaining_exposure / p if p else 0
        qty = min(qty_risk, max_value / p if p else 0, qty_exposure)
        value = qty * p

        if qty <= 0 or value > st["capital"] or value < 5:
            continue

        pos = {
            "symbol": symbol, "market": c.get("market", "CRYPTO"),
            "quantity": qty, "entry_price": p, "stop_price": stop_price,
            "target_price": target_price, "risk_value": risk,
            "risk_distance_pct": (stop_distance / p) * 100,
            "risk_reward": rr, "score": score, "strategy": strategy_name,
            "source": c.get("source"), "opened_at": now_iso
        }
        positions.append(pos)
        st["capital"] -= value
        current_exposure += value
        opened.append(pos)

    # Provisão fiscal: resultado líquido de cada dia positivo, não cada trade vencedor.
    brt = ZoneInfo("America/Sao_Paulo")
    def trade_day(t):
        try:
            return datetime.fromisoformat(str(t.get("closed_at", "")).replace("Z", "+00:00")).astimezone(brt).date().isoformat()
        except Exception:
            return str(t.get("closed_at", ""))[:10]

    by_day = {}
    for t in trades:
        d = trade_day(t)
        by_day[d] = by_day.get(d, 0.0) + float(t.get("gross", 0.0))

    daily_tax_base = {d: max(0.0, v) for d, v in by_day.items()}
    daily_tax = {d: v * 0.20 for d, v in daily_tax_base.items()}
    for d in by_day:
        day_winners = [t for t in trades if trade_day(t) == d and float(t.get("gross", 0.0)) > 0]
        winners_gross = sum(float(t.get("gross", 0.0)) for t in day_winners)
        for t in day_winners:
            alloc = (float(t.get("gross", 0.0)) / winners_gross * daily_tax[d]) if winners_gross > 0 else 0.0
            t["estimated_tax"] = alloc
            t["net"] = float(t.get("gross", 0.0)) - alloc

    st["positions"], st["trades"], st["updated_at"] = positions, trades, now_iso
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(st, indent=2, ensure_ascii=False), encoding="utf-8")

    aberto = 0.0
    for x in positions:
        p = cached_price(x["symbol"], x.get("market", "CRYPTO"), float(x["entry_price"]))
        aberto += float(x["quantity"]) * p

    lucro_bruto = sum(float(t.get("gross", 0)) for t in trades)
    imposto_estimado = sum(daily_tax.values())
    base_tributavel = sum(daily_tax_base.values())
    lucro = lucro_bruto - imposto_estimado
    patrimonio = st["capital"] + aberto
    wins = sum(1 for t in trades if float(t.get("net", 0)) > 0)

    result = {
        "strategy": strategy_name, "opened_now": len(opened),
        "opened_total": len(positions), "closed_now": len(closed),
        "closed": len(trades), "capital": st["capital"],
        "patrimonio": patrimonio,
        "retorno_pct": (patrimonio / CAPITAL_INICIAL - 1) * 100,
        "operacoes": len(trades), "posicoes": len(positions),
        "win_rate_pct": (wins / len(trades) * 100) if trades else 0,
        "last_event": (closed[-1] if closed else (opened[-1] if opened else None)),
        "opportunities": [
            {
                "symbol": c["symbol"], "market": c.get("market"),
                "score": c.get("score"), "signal": c.get("signal"),
                "price": c.get("price"), "momentum_pct": c.get("momentum_pct"),
                "volume_ratio": c.get("volume_ratio"), "reason": c.get("reasons", [])[:4]
            }
            for c in candidates if float(c.get("score", 0)) >= score_min
        ][:12]
    }

    data = {
        "updated_at": now_iso,
        "config": {
            "capital_inicial": CAPITAL_INICIAL, "capital": st["capital"],
            "max_position_pct": max_position_pct, "stop_mult_atr": stop_mult,
            "target_mult_atr": target_mult, "fee_pct": 0.0,
            "tax_rate_pct": 20.0, "paper_trading": True,
            "real_orders": False, "risk_per_trade_pct": risk_pct,
            "max_positions": max_positions, "score_min": score_min,
            "max_total_exposure_pct": MAX_TOTAL_EXPOSURE_PCT,
            "cooldown_minutes": COOLDOWN_MINUTES, "min_risk_reward": min_rr,
            "strategy": strategy_name,
            "tax_method": "20% sobre resultado líquido diário positivo (estimativa; apuração fiscal real é mensal)"
        },
        "positions": positions, "trades": trades,
        "tax": {"rate_pct": 20.0, "base_tributavel": base_tributavel, "imposto_estimado": imposto_estimado,
                "dias_positivos": sum(1 for v in daily_tax_base.values() if v > 0),
                "daily": [{"date": d, "net_result": by_day[d], "taxable_base": daily_tax_base[d], "estimated_tax": daily_tax[d]} for d in sorted(by_day)]},
        "market": {k: s.get(k) for k in ("symbol", "market", "price", "score", "signal")},
        "summary": {
            "lucro_bruto": lucro_bruto, "base_tributavel": base_tributavel,
            "imposto_estimado": imposto_estimado, "lucro_liquido": lucro,
            "patrimonio": patrimonio, "dias_positivos": sum(1 for v in daily_tax_base.values() if v > 0),
            "retorno_pct": result["retorno_pct"], "operacoes": len(trades),
            "win_rate_pct": result["win_rate_pct"]
        }
    }
    return result, data

def main():
    s = load(SINAL, {})
    hunter, hunter_data = run_strategy(
        s, STATE, "DOT_HUNTER_X", SCORE_MIN, RISCO_PCT,
        MAX_POSICOES, MAX_POSITION_PCT, STOP_MULT, TARGET_MULT, MIN_RR
    )
    extreme, extreme_data = run_strategy(
        s, EXTREME_STATE, "DOT_HUNTER_EXTREME", EXTREME_SCORE_MIN,
        EXTREME_RISCO_PCT, EXTREME_MAX_POSICOES, EXTREME_MAX_POSITION_PCT,
        EXTREME_STOP_MULT, EXTREME_TARGET_MULT, EXTREME_MIN_RR
    )

    for path, data in [
        (Path("docs/dados_hunter_x.json"), hunter_data),
        (Path("docs/dados_extreme.json"), extreme_data),
        (Path("dados.json"), hunter_data),
        (Path("docs/dados.json"), hunter_data),
    ]:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    combined = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "paper_trading": True, "real_orders": False,
        "comparison": {"hunter_x": hunter, "hunter_extreme": extreme},
        "extreme_opportunities": extreme["opportunities"],
        "hunter_opportunities": hunter["opportunities"]
    }
    Path("docs/comparativo.json").write_text(
        json.dumps(combined, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(combined, ensure_ascii=False))

if __name__ == "__main__":
    main()
