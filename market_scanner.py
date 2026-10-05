"""DOT Trader - scanner multiativo para Paper Trading.
Dados públicos. Nunca envia ordens reais.
"""
from urllib.request import urlopen
from urllib.parse import urlencode
from pathlib import Path
from datetime import datetime, timezone
import json

BASE = "https://data-api.binance.vision/api/v3/klines"
SYMBOLS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT","DOTUSDT"]
INTERVAL = "1m"
LIMIT = 100
OUTS = [Path("docs/sinal.json"), Path("sinal.json")]

def fetch(symbol):
    q = urlencode({"symbol": symbol, "interval": INTERVAL, "limit": LIMIT})
    with urlopen(BASE + "?" + q, timeout=15) as r:
        return json.loads(r.read().decode())

def ema(values, period):
    k = 2 / (period + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1-k)
    return e

def rsi(values, period=14):
    gains, losses = [], []
    for a,b in zip(values[-period-1:-1], values[-period:]):
        d=b-a
        gains.append(max(d,0)); losses.append(max(-d,0))
    ag=sum(gains)/period; al=sum(losses)/period
    if al == 0: return 100.0
    return 100 - (100/(1+ag/al))

def evaluate(symbol):
    raw=fetch(symbol)
    closes=[float(x[4]) for x in raw]
    price=closes[-1]
    fast=ema(closes[-30:],9); slow=ema(closes[-50:],21)
    r=rsi(closes); momentum=(price/closes[-5]-1)*100
    score=50; reasons=[]
    if fast > slow: score += 20; reasons.append("EMA9 acima da EMA21")
    else: score -= 20; reasons.append("EMA9 abaixo da EMA21")
    if 50 <= r <= 70: score += 15; reasons.append("RSI favorável")
    elif r < 30: score += 5; reasons.append("RSI sobrevendido")
    elif r > 70: score -= 10; reasons.append("RSI sobrecomprado")
    if momentum > 0.25: score += 15; reasons.append("momentum positivo")
    elif momentum < -0.25: score -= 15; reasons.append("momentum negativo")
    score=max(0,min(100,score))
    signal="COMPRA" if score >= 75 else "VENDA/EVITAR" if score <= 35 else "HOLD"
    return {"symbol":symbol,"interval":INTERVAL,"price":price,"ema9":fast,"ema21":slow,
            "rsi14":r,"momentum_pct":momentum,"score":score,"signal":signal,"reasons":reasons}

def main():
    candidates=[]
    errors=[]
    for symbol in SYMBOLS:
        try:
            candidates.append(evaluate(symbol))
        except Exception as exc:
            errors.append({"symbol":symbol,"error":str(exc)})
    candidates.sort(key=lambda x:(x["score"], x["momentum_pct"]), reverse=True)
    top=candidates[0] if candidates else {"symbol":"N/A","price":0,"score":0,"signal":"HOLD","reasons":[]}
    out={"updated_at":datetime.now(timezone.utc).isoformat(),
         **top,"candidates":candidates,"errors":errors,
         "universe":SYMBOLS,"paper_trading":True,"real_orders":False}
    for path in OUTS:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(out,indent=2,ensure_ascii=False))

if __name__=="__main__":
    main()
