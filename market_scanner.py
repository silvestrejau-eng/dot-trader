"""DOT Trader - scanner multi-mercado para Paper Trading.
Dados públicos. Nunca envia ordens reais.
"""
from urllib.request import urlopen, Request
from urllib.parse import urlencode, quote
from pathlib import Path
from datetime import datetime, timezone
import json, time

INTERVAL="5m"
LIMIT=100
OUTS=[Path("docs/sinal.json"),Path("sinal.json")]

UNIVERSE=[
 # B3
 ("PETR4","B3"),("VALE3","B3"),("ITUB4","B3"),("BBDC4","B3"),("BBAS3","B3"),
 ("B3SA3","B3"),("WEGE3","B3"),("ABEV3","B3"),("MGLU3","B3"),("RENT3","B3"),
 ("PRIO3","B3"),("SUZB3","B3"),("EMBR3","B3"),("ELET3","B3"),("JBSS3","B3"),
 # ETFs / proxies
 ("BOVA11","B3"),("SMAL11","B3"),("IVVB11","B3"),("GOLD11","B3"),("DOLA11","B3"),
 ("CMDB11","B3"),("BBOI11","B3"),("CORN11","B3"),
 # EUA / global
 ("SPY","GLOBAL"),("QQQ","GLOBAL"),("IWM","GLOBAL"),("GLD","GLOBAL"),
 ("SLV","GLOBAL"),("USO","GLOBAL"),("UUP","GLOBAL"),("TLT","GLOBAL"),
 # crypto
 ("BTCUSDT","CRYPTO"),("ETHUSDT","CRYPTO"),("BNBUSDT","CRYPTO"),
 ("SOLUSDT","CRYPTO"),("XRPUSDT","CRYPTO"),("ADAUSDT","CRYPTO"),
 ("DOGEUSDT","CRYPTO"),("AVAXUSDT","CRYPTO"),("LINKUSDT","CRYPTO"),("DOTUSDT","CRYPTO")
]

def yahoo(symbol):
    ysym = symbol + ".SA" if any(x[0]==symbol and x[1]=="B3" for x in UNIVERSE) else symbol
    url="https://query1.finance.yahoo.com/v8/finance/chart/"+quote(ysym)+"?"+urlencode({"interval":INTERVAL,"range":"5d"})
    req=Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urlopen(req,timeout=15) as r: data=json.loads(r.read().decode())
    res=data["chart"]["result"][0]
    q=res["indicators"]["quote"][0]
    closes=[float(x) for x in q["close"] if x is not None]
    if len(closes)<60: raise RuntimeError("historico insuficiente")
    return closes[-LIMIT:], "Yahoo Finance"

def crypto(symbol):
    url="https://data-api.binance.vision/api/v3/klines?"+urlencode({"symbol":symbol,"interval":"1m","limit":LIMIT})
    with urlopen(url,timeout=15) as r: raw=json.loads(r.read().decode())
    return [float(x[4]) for x in raw], "Binance public"

def b3_quote(symbol):
    url="https://brapi.dev/api/quote/"+quote(symbol)
    req=Request(url,headers={"User-Agent":"DOT-Trader-Paper"})
    with urlopen(req,timeout=15) as r: data=json.loads(r.read().decode())
    q=data["results"][0]
    p=float(q["regularMarketPrice"])
    # B3 quote is used as current-price confirmation; Yahoo supplies technical history.
    closes,_=yahoo(symbol)
    closes[-1]=p
    return closes, "B3 + Yahoo"

def ema(values, period):
    k=2/(period+1); e=values[0]
    for v in values[1:]: e=v*k+e*(1-k)
    return e

def rsi(values, period=14):
    gains=[]; losses=[]
    for a,b in zip(values[-period-1:-1],values[-period:]):
        d=b-a; gains.append(max(d,0)); losses.append(max(-d,0))
    ag=sum(gains)/period; al=sum(losses)/period
    if al==0: return 100.0
    return 100-(100/(1+ag/al))

def evaluate(symbol,market):
    if market=="CRYPTO": closes,source=crypto(symbol)
    elif market=="B3": closes,source=b3_quote(symbol)
    else: closes,source=yahoo(symbol)
    p=closes[-1]
    fast=ema(closes[-30:],9); slow=ema(closes[-50:],21)
    r=rsi(closes); momentum=(p/closes[-5]-1)*100
    score=50; reasons=[]
    if fast>slow: score+=20; reasons.append("tendência EMA9>EMA21")
    else: score-=20; reasons.append("EMA9<EMA21")
    if 50<=r<=70: score+=15; reasons.append("RSI favorável")
    elif r<30: score+=5; reasons.append("RSI sobrevendido")
    elif r>70: score-=10; reasons.append("RSI sobrecomprado")
    if momentum>0.25: score+=15; reasons.append("momentum positivo")
    elif momentum<-0.25: score-=15; reasons.append("momentum negativo")
    score=max(0,min(100,score))
    signal="COMPRA" if score>=75 else "VENDA/EVITAR" if score<=35 else "HOLD"
    return {"symbol":symbol,"market":market,"source":source,"interval":INTERVAL,
            "price":p,"ema9":fast,"ema21":slow,"rsi14":r,"momentum_pct":momentum,
            "score":score,"signal":signal,"reasons":reasons}

def main():
    candidates=[]; errors=[]
    for symbol,market in UNIVERSE:
        try: candidates.append(evaluate(symbol,market))
        except Exception as exc: errors.append({"symbol":symbol,"market":market,"error":str(exc)})
        time.sleep(0.15)
    candidates.sort(key=lambda x:(x["score"],x["momentum_pct"]),reverse=True)
    top=candidates[0] if candidates else {"symbol":"N/A","market":"N/A","price":0,"score":0,"signal":"HOLD","reasons":[]}
    out={"updated_at":datetime.now(timezone.utc).isoformat(),**top,
         "candidates":candidates,"errors":errors,"universe":[{"symbol":s,"market":m} for s,m in UNIVERSE],
         "paper_trading":True,"real_orders":False}
    for path in OUTS:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"top":top,"candidates":len(candidates),"errors":len(errors)},ensure_ascii=False))

if __name__=="__main__": main()
