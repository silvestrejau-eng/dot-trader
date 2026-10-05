import json, math, time, urllib.request, urllib.parse
from datetime import datetime, timezone
from pathlib import Path

CONFIG=Path(__file__).with_name("v2_config.json")
OUT=Path(__file__).with_name("market_snapshot.json")

UNIVERSE=[
("CRYPTO","BTCUSDT"),("CRYPTO","ETHUSDT"),("CRYPTO","BNBUSDT"),("CRYPTO","SOLUSDT"),
("CRYPTO","XRPUSDT"),("CRYPTO","ADAUSDT"),("CRYPTO","DOGEUSDT"),("CRYPTO","AVAXUSDT"),
("CRYPTO","LINKUSDT"),("CRYPTO","DOTUSDT"),("CRYPTO","TRXUSDT"),("CRYPTO","LTCUSDT"),
("CRYPTO","BCHUSDT"),("CRYPTO","ATOMUSDT"),("CRYPTO","NEARUSDT"),("CRYPTO","APTUSDT"),
("CRYPTO","SUIUSDT"),("CRYPTO","PEPEUSDT"),("CRYPTO","FILUSDT"),("CRYPTO","ETCUSDT")
]

def get_json(url):
    req=urllib.request.Request(url,headers={"User-Agent":"DOT-Trader-V2"})
    with urllib.request.urlopen(req,timeout=10) as r:return json.loads(r.read().decode())

def candles(symbol):
    d=get_json("https://data-api.binance.vision/api/v3/klines?symbol="+urllib.parse.quote(symbol)+"&interval=5m&limit=60")
    return [(float(x[1]),float(x[2]),float(x[3]),float(x[4]),float(x[5])) for x in d]

def ema(vals,n):
    k=2/(n+1); e=vals[0]
    for v in vals[1:]: e=v*k+e*(1-k)
    return e

def rsi(vals,n=14):
    gains=[];loss=[]
    for a,b in zip(vals[-n-1:-1],vals[-n:]):
        d=b-a;gains.append(max(d,0));loss.append(max(-d,0))
    ag=sum(gains)/n; al=sum(loss)/n
    return 100 if al==0 else 100-(100/(1+ag/al))

def scan(item):
    market,symbol=item
    try:
        c=candles(symbol); closes=[x[3] for x in c]; vols=[x[4] for x in c]
        p=closes[-1]; e9=ema(closes,9); e21=ema(closes,21); e50=ema(closes,50)
        rv=rsi(closes); mom=(p/closes[-6]-1)*100
        avgvol=sum(vols[-21:-1])/20; vr=vols[-1]/avgvol if avgvol else 0
        tr=[max(h-l,abs(h-closes[i-1]),abs(l-closes[i-1])) for i,(o,h,l,cl,v) in enumerate(c[1:],1)]
        atr=sum(tr[-14:])/14
        score=0
        reasons=[]
        if e9>e21: score+=20;reasons.append("EMA9>EMA21")
        if e21>e50: score+=15;reasons.append("tendencia")
        if 50<=rv<=72: score+=15;reasons.append("RSI")
        if mom>0.25: score+=20;reasons.append("momentum")
        if vr>1.1: score+=15;reasons.append("volume")
        if p>=max(closes[-21:-1]): score+=15;reasons.append("rompimento")
        signal="COMPRA" if score>=55 else "HOLD"
        return {"market":market,"symbol":symbol,"price":p,"ema9":e9,"ema21":e21,"ema50":e50,
          "rsi":rv,"momentum_pct":mom,"volume_ratio":vr,"atr":atr,"score":score,
          "signal":signal,"reasons":reasons}
    except Exception as e:
        return {"market":market,"symbol":symbol,"error":str(e),"score":0,"signal":"ERROR"}

def main():
    started=datetime.now(timezone.utc).isoformat()
    results=[scan(x) for x in UNIVERSE]
    results.sort(key=lambda x:x.get("score",0),reverse=True)
    data={"updated_at":started,"interval":"5m","scanner":"DOT Trader V2","markets_scanned":len(results),
          "candidates":[x for x in results if "price" in x]}
    OUT.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"updated_at":started,"markets":len(results),"top":results[:5]},ensure_ascii=False))
if __name__=="__main__": main()
