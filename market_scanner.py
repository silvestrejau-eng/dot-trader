"""DOT Trader - scanner multi-mercado / DOT HUNTER AGRESSIVA.
Dados publicos. Nunca envia ordens reais.

Estrategia HUNTER:
- Timeframe de entrada: 5m
- Tendencia: EMA 9 > EMA 21 > EMA 50
- Momentum: RSI 14 + variacao de 5 candles
- Rompimento: maxima dos ultimos 20 candles
- Volume: acima da media dos ultimos 20 candles
- Volatilidade: ATR 14 para stop/alvo
- Score minimo: 70
"""
from urllib.request import urlopen, Request
from urllib.parse import urlencode, quote
from pathlib import Path
from datetime import datetime, timezone
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed\nfrom market_sessions import session_status, all_sessions

INTERVAL = "5m"
LIMIT = 80
OUTS = [Path("docs/sinal.json"), Path("sinal.json")]
BREAKOUT_PERIOD = 20
SCORE_MIN = 70
ATR_PERIOD = 14

UNIVERSE = [
    ("PETR4","B3"),("VALE3","B3"),("ITUB4","B3"),("BBDC4","B3"),("BBAS3","B3"),
    ("B3SA3","B3"),("WEGE3","B3"),("ABEV3","B3"),("MGLU3","B3"),("RENT3","B3"),
    ("PRIO3","B3"),("SUZB3","B3"),("EMBR3","B3"),("ELET3","B3"),("JBSS3","B3"),
    ("BOVA11","B3"),("SMAL11","B3"),("IVVB11","B3"),("GOLD11","B3"),("DOLA11","B3"),
    ("CMDB11","B3"),("BBOI11","B3"),("CORN11","B3"),
    ("SPY","GLOBAL"),("QQQ","GLOBAL"),("IWM","GLOBAL"),("GLD","GLOBAL"),
    ("SLV","GLOBAL"),("USO","GLOBAL"),("UUP","GLOBAL"),("TLT","GLOBAL"),
    ("BTCUSDT","CRYPTO"),("ETHUSDT","CRYPTO"),("BNBUSDT","CRYPTO"),
    ("SOLUSDT","CRYPTO"),("XRPUSDT","CRYPTO"),("ADAUSDT","CRYPTO"),
    ("DOGEUSDT","CRYPTO"),("AVAXUSDT","CRYPTO"),("LINKUSDT","CRYPTO"),("DOTUSDT","CRYPTO")
]

def _clean(values):
    return [float(x) for x in values if x is not None]

def yahoo(symbol):
    ysym = symbol + ".SA" if any(x[0] == symbol and x[1] == "B3" for x in UNIVERSE) else symbol
    params = urlencode({"interval": INTERVAL, "range": "5d"})
    last_error = None
    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        url = "https://" + host + "/v8/finance/chart/" + quote(ysym) + "?" + params
        for attempt in range(2):
            try:
                req = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
                with urlopen(req, timeout=6) as r:
                    data = json.loads(r.read().decode())
                result = (data.get("chart") or {}).get("result") or []
                if not result:
                    raise RuntimeError("Yahoo sem resultado")
                res = result[0]
                break
            except Exception as exc:
                last_error = exc
                if attempt == 0:
                    time.sleep(0.35)
        else:
            continue
        break
    else:
        raise last_error or RuntimeError("Yahoo indisponivel")

    q = res["indicators"]["quote"][0]
    closes = _clean(q.get("close", []))
    highs = _clean(q.get("high", []))
    lows = _clean(q.get("low", []))
    volumes = _clean(q.get("volume", []))
    if len(closes) < 60:
        raise RuntimeError("historico insuficiente")
    return {"close": closes[-LIMIT:], "high": highs[-LIMIT:], "low": lows[-LIMIT:], "volume": volumes[-LIMIT:]}, "Yahoo Finance"

def crypto(symbol):
    url = "https://data-api.binance.vision/api/v3/klines?" + urlencode(
        {"symbol": symbol, "interval": INTERVAL, "limit": LIMIT}
    )
    with urlopen(url, timeout=6) as r:
        raw = json.loads(r.read().decode())
    return {
        "close": [float(x[4]) for x in raw],
        "high": [float(x[2]) for x in raw],
        "low": [float(x[3]) for x in raw],
        "volume": [float(x[5]) for x in raw],
    }, "Binance public"

def b3_quote(symbol):
    # Yahoo fornece historico e preco recente para os tickers .SA.
    # BRAPI deixa de ser dependencia obrigatoria para evitar 401/429 bloqueando o ciclo.
    candles, source = yahoo(symbol)
    return candles, source + " (B3)"

def ema(values, period):
    if len(values) < period:
        raise RuntimeError("dados insuficientes para EMA")
    k = 2 / (period + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1 - k)
    return e

def rsi(values, period=14):
    if len(values) < period + 1:
        raise RuntimeError("dados insuficientes para RSI")
    gains, losses = [], []
    for a, b in zip(values[-period-1:-1], values[-period:]):
        d = b - a
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag, al = sum(gains) / period, sum(losses) / period
    if al == 0:
        return 100.0
    return 100 - (100 / (1 + ag / al))

def atr(candles, period=14):
    highs, lows, closes = candles["high"], candles["low"], candles["close"]
    if len(closes) < period + 1:
        raise RuntimeError("dados insuficientes para ATR")
    trs = []
    for i in range(1, len(closes)):
        trs.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1]),
        ))
    return sum(trs[-period:]) / period

def evaluate(symbol, market):
    candles, source = crypto(symbol) if market == "CRYPTO" else (
        b3_quote(symbol) if market == "B3" else yahoo(symbol)
    )
    closes = candles["close"]
    volumes = candles["volume"]
    p = closes[-1]

    e9 = ema(closes[-60:], 9)
    e21 = ema(closes[-60:], 21)
    e50 = ema(closes[-60:], 50)
    r = rsi(closes, 14)
    momentum = (p / closes[-6] - 1) * 100
    a = atr(candles, ATR_PERIOD)

    prior_high = max(closes[-(BREAKOUT_PERIOD+1):-1])
    breakout_pct = (p / prior_high - 1) * 100 if prior_high > 0 else 0
    avg_volume = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else 0
    volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 0

    score = 0
    reasons = []

    # Tendencia - 30 pontos
    if e9 > e21 > e50:
        score += 30
        reasons.append("EMA9>EMA21>EMA50")
    elif e9 > e21:
        score += 18
        reasons.append("EMA9>EMA21")
    elif e9 < e21 < e50:
        score -= 20
        reasons.append("tendencia de baixa")
    else:
        score += 5
        reasons.append("tendencia indefinida")

    # Momentum/RSI - 20 pontos
    if 55 <= r <= 68:
        score += 20
        reasons.append("RSI momentum ideal")
    elif 50 <= r < 55:
        score += 12
        reasons.append("RSI positivo")
    elif 68 < r <= 72:
        score += 8
        reasons.append("RSI forte, proximo da sobrecompra")
    elif r > 72:
        score -= 8
        reasons.append("RSI sobrecomprado")
    elif r < 35:
        score += 2
        reasons.append("RSI muito baixo")

    # Momentum de curto prazo - 15 pontos
    if momentum >= 0.40:
        score += 15
        reasons.append("aceleracao positiva")
    elif momentum >= 0.15:
        score += 8
        reasons.append("momentum positivo")
    elif momentum <= -0.40:
        score -= 15
        reasons.append("aceleracao negativa")

    # Breakout - 20 pontos
    if p > prior_high:
        score += 20
        reasons.append("rompimento da maxima de 20 candles")
    elif breakout_pct >= -0.20:
        score += 8
        reasons.append("preco comprimido na maxima")
    else:
        score += 0

    # Volume - 10 pontos
    if volume_ratio >= 1.50:
        score += 10
        reasons.append("volume >= 1.5x media")
    elif volume_ratio >= 1.15:
        score += 6
        reasons.append("volume acima da media")
    elif volume_ratio < 0.70:
        score -= 5
        reasons.append("volume fraco")

    # Penaliza volatilidade extrema para evitar entradas tardias.
    atr_pct = (a / p) * 100 if p > 0 else 0
    if atr_pct > 4.0:
        score -= 8
        reasons.append("ATR muito alto")
    elif 0 < atr_pct <= 2.5:
        score += 5
        reasons.append("volatilidade controlada")

    score = max(0, min(100, int(round(score))))
    signal = "COMPRA" if score >= SCORE_MIN and e9 > e21 else (
        "VENDA/EVITAR" if score <= 35 else "HOLD"
    )

    stop_price = max(0.0, p - 1.0 * a)
    target_price = p + 2.0 * a

    return {
        "symbol": symbol, "market": market, "source": source, "interval": INTERVAL,
        "price": p, "ema9": e9, "ema21": e21, "ema50": e50, "rsi14": r,
        "momentum_pct": momentum, "breakout_pct": breakout_pct,
        "volume_ratio": volume_ratio, "atr": a, "atr_pct": atr_pct,
        "stop_price": stop_price, "target_price": target_price,
        "score": score, "signal": signal, "strategy": "DOT_HUNTER_X",
        "reasons": reasons,
    }

def main():
    cycle_started = time.perf_counter()
    candidates, errors = [], []

    def run(item):
        symbol, market = item
        try:
            return evaluate(symbol, market), None
        except Exception as exc:
            return None, {"symbol": symbol, "market": market, "error": str(exc)}

    # Paralelismo reduz o tempo do scanner e aumenta a frequencia efetiva de ciclos.
    priority = {"REGULAR": 0, "PRE": 1, "AFTER": 1, "FECHADO": 2}
    ordered_universe = sorted(UNIVERSE, key=lambda item: (priority.get(session_status(item[1])["state"], 2), 0 if item[1] == "B3" else 1))

    with ThreadPoolExecutor(max_workers=28) as pool:
        futures = [pool.submit(run, item) for item in ordered_universe]
        for future in as_completed(futures):
            candidate, error = future.result()
            if candidate:
                candidates.append(candidate)
            if error:
                errors.append(error)

    candidates.sort(key=lambda x: (x["score"], x["momentum_pct"], x["volume_ratio"]), reverse=True)
    top = candidates[0] if candidates else {
        "symbol": "N/A", "market": "N/A", "price": 0, "score": 0,
        "signal": "HOLD", "reasons": []
    }

    cycle_duration_ms = int((time.perf_counter() - cycle_started) * 1000)
    out = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "cycle_duration_ms": cycle_duration_ms,
        "cycle_duration_seconds": round(cycle_duration_ms / 1000, 2),
        "successful_assets": len(candidates),
        "failed_assets": len(errors),
        "scanner_heartbeat": datetime.now(timezone.utc).isoformat(),
        **top,
        "candidates": candidates,
        "errors": errors,
        "performance": {
            "cycle_duration_ms": cycle_duration_ms,
            "assets_total": len(UNIVERSE),
            "successful_assets": len(candidates),
            "failed_assets": len(errors),
            "workers": 28
        },
        "universe": [{"symbol": s, "market": m} for s, m in UNIVERSE],
        "paper_trading": True,
        "real_orders": False,
        "score_min": SCORE_MIN,
        "strategy": "DOT_HUNTER_AGRESSIVA",
    }
    for path in OUTS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "top": top, "candidates": len(candidates), "errors": len(errors), "cycle_duration_ms": cycle_duration_ms
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
