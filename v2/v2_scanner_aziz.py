import json, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

OUT=Path(__file__).with_name("market_snapshot.json")
UNIVERSE=[("CRYPTO",s) for s in ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT","DOTUSDT","TRXUSDT","LTCUSDT","BCHUSDT","ATOMUSDT","NEARUSDT","APTUSDT","SUIUSDT","PEPEUSDT","FILUSDT","ETCUSDT"]]

def get_json(url):
    req=urllib.request.Request(url,headers={"User-Agent":"DOT-Trader-V2.2"})
    with urllib.request.urlopen(req,timeout=8) as r:return json.loads(r.read().decode())

def candles(symbol):
    d=get_json("https://data-api.binance.vision/api/v3/klines?symbol="+urllib.parse.quote(symbol)+"&interval=5m&limit=288")
    return [{"ts":int(x[0]),"open":float(x[1]),"high":float(x[2]),"low":float(x[3]),"close":float(x[4]),"volume":float(x[5])} for x in d]

def ema(v,n):
    k=2/(n+1);e=v[0]
    for x in v[1:]:e=x*k+e*(1-k)
    return e

def rsi(v,n=14):
    g=[];l=[]
    for a,b in zip(v[-n-1:-1],v[-n:]):
        d=b-a;g.append(max(d,0));l.append(max(-d,0))
    ag,al=sum(g)/n,sum(l)/n
    return 100 if al==0 else 100-100/(1+ag/al)

def atr(c,n=14):
    tr=[]
    for i in range(1,len(c)):
        x,p=c[i],c[i-1]["close"]
        tr.append(max(x["high"]-x["low"],abs(x["high"]-p),abs(x["low"]-p)))
    return sum(tr[-n:])/n

def scan(item):
    market,symbol=item
    try:
        c=candles(symbol);v=[x["close"] for x in c];vol=[x["volume"] for x in c];p=v[-1];a=atr(c)
        e9,e21,e50=ema(v,9),ema(v,21),ema(v,50);rv=rsi(v)
        mom5=(p/v[-6]-1)*100;mom15=(p/v[-16]-1)*100
        vr=vol[-1]/(sum(vol[-21:-1])/20 or 1)
        today=datetime.now(timezone.utc).date()
        sess=[x for x in c if datetime.fromtimestamp(x["ts"]/1000,timezone.utc).date()==today] or c[-96:]
        vw=sum(((x["high"]+x["low"]+x["close"])/3)*x["volume"] for x in sess)/(sum(x["volume"] for x in sess) or 1)
        hi=max(x["high"] for x in c[-21:-1]);lo=min(x["low"] for x in c[-21:-1])
        orb=sess[:3];orbhi=max(x["high"] for x in orb) if len(orb)>=3 else hi
        near=abs(p-vw)/p<=.006
        pull=v[-4]<v[-3]<=v[-2]<=v[-1] and p>=vw
        flag=(v[-10]<v[-5] and v[-5]/v[-10]-1>.006 and max(v[-4:])/min(v[-4:])-1<.006 and p>=max(v[-4:]))
        abcd=v[-12]<v[-8]<v[-4] and p>=max(v[-4:-1]) and mom15>0
        orbbr=p>orbhi and len(sess)>3
        stop=min(p-.9*a,p*.985);rr=(hi-p)/max(p-stop,p*.001)
        score=0;re=[]
        if e9>e21>e50:score+=15;re+=["TENDÊNCIA"]
        elif e9>e21:score+=8;re+=["EMA9>EMA21"]
        if p>=vw and near:score+=15;re+=["VWAP_SUPORTE"]
        elif p>=vw:score+=8;re+=["ACIMA_VWAP"]
        if mom5>.35 and mom15>.5:score+=15;re+=["MOMENTUM"]
        elif mom5>.15:score+=7;re+=["MOMENTUM_LEVE"]
        if vr>=1.8:score+=15;re+=["VOLUME_FORTE"]
        elif vr>=1.25:score+=8;re+=["VOLUME"]
        setup=0
        if orbbr:setup=max(setup,15);re+=["ORB"]
        if flag:setup=max(setup,15);re+=["BULL_FLAG"]
        if abcd:setup=max(setup,12);re+=["ABCD"]
        if pull:setup=max(setup,10);re+=["PULLBACK_VWAP"]
        score+=setup
        if p>=hi:score+=10;re+=["ROMPIMENTO"]
        elif p>=hi*.995:score+=5;re+=["RESISTÊNCIA_PRÓXIMA"]
        if 52<=rv<=72:score+=5;re+=["RSI_SAUDÁVEL"]
        elif rv>72:score-=3;re+=["RSI_ESTICADO"]
        if rr>=1.8 or p>=hi:score+=10;re+=["RR_OK"]
        else:score=min(score,69)
        score=max(0,min(100,score))
        return {"market":market,"symbol":symbol,"price":p,"ema9":e9,"ema21":e21,"ema50":e50,"vwap":vw,"rsi":rv,"momentum_pct":mom5,"momentum_15m_pct":mom15,"volume_ratio":vr,"atr":a,"support":lo,"resistance":hi,"rr_to_resistance":rr,"orb_high":orbhi,"score":score,"signal":"COMPRA" if score>=70 else "HOLD","reasons":re}
    except Exception as e:
        return {"market":market,"symbol":symbol,"error":str(e),"score":0,"signal":"ERROR"}

def main():
    now=datetime.now(timezone.utc).isoformat();out=[]
    with ThreadPoolExecutor(max_workers=10) as ex:
        for f in as_completed([ex.submit(scan,x) for x in UNIVERSE]):out.append(f.result())
    out.sort(key=lambda x:x.get("score",0),reverse=True)
    data={"updated_at":now,"interval":"5m","scanner":"DOT Trader V2.2 • Aziz Playbook","markets_scanned":len(out),"score_model":{"trend":15,"vwap":15,"momentum":15,"volume":15,"setup":15,"structure":10,"rsi":5,"risk_reward":10},"candidates":[x for x in out if "price" in x]}
    OUT.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"updated_at":now,"markets":len(out),"top":out[:5]},ensure_ascii=False))
if __name__=="__main__":main()