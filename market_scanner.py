"""DOT Trader - scanner de mercado em Paper Trading.
Busca candles públicos e gera sinal. NÃO envia ordens.
"""
from urllib.request import urlopen
from urllib.parse import urlencode
from pathlib import Path
from datetime import datetime, timezone
import json
import math

BASE = "https://data-api.binance.vision/api/v3/klines"
SYMBOL = "DOTUSDT"
INTERVAL = "1m"
LIMIT = 100
OUTS = [Path("docs/sinal.json"), Path("sinal.json")]

def fetch():
    q = urlencode({"symbol": SYMBOL, "interval": INTERVAL, "limit": LIMIT})
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
        gains.append(max(d,0))
        losses.append(max(-d,0))
    ag=sum(gains)/period
    al=sum(losses)/period
    if al == 0: return 100.0
    return 100 - (100/(1+ag/al))

def main():
    raw=fetch()
    closes=[float(x[4]) for x in raw]
    price=closes[-1]
    fast=ema(closes[-30:],9)
    slow=ema(closes[-50:],21)
    r=rsi(closes)
    momentum=(price/closes[-5]-1)*100

    score=50
    reasons=[]
    if fast > slow:
        score += 20; reasons.append("EMA9 acima da EMA21")
    else:
        score -= 20; reasons.append("EMA9 abaixo da EMA21")
    if 50 <= r <= 70:
        score += 15; reasons.append("RSI favorável")
    elif r < 30:
        score += 5; reasons.append("RSI sobrevendido")
    elif r > 70:
        score -= 10; reasons.append("RSI sobrecomprado")
    if momentum > 0.25:
        score += 15; reasons.append("momentum positivo")
    elif momentum < -0.25:
        score -= 15; reasons.append("momentum negativo")

    score=max(0,min(100,score))
    signal="COMPRA" if score >= 75 else "VENDA/EVITAR" if score <= 35 else "HOLD"

    out={
      "updated_at":datetime.now(timezone.utc).isoformat(),
      "symbol":SYMBOL,"interval":INTERVAL,"price":price,
      "ema9":fast,"ema21":slow,"rsi14":r,"momentum_pct":momentum,
      "score":score,"signal":signal,"reasons":reasons,
      "paper_trading":True,"real_orders":False
    }
    for OUT in OUTS:
        OUT.parent.mkdir(parents=True,exist_ok=True)
        OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(out,indent=2,ensure_ascii=False))

if __name__=="__main__":
    main()
