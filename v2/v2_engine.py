import json
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).parent
CFG=json.loads((ROOT/"v2_config.json").read_text())
SNAP=json.loads((ROOT/"market_snapshot.json").read_text())
STATE=ROOT/"state.json"; DASH=ROOT/"dashboard.json"

def load():
    if STATE.exists():
        try:return json.loads(STATE.read_text())
        except:pass
    return {"capital":CFG["capital_inicial"],"positions":{"HUNTER_X":[],"HUNTER_EXTREME":[]},
            "trades":{"HUNTER_X":[],"HUNTER_EXTREME":[]},"equity_peak":CFG["capital_inicial"]}

def run(name,cfg,st):
    pos=st["positions"][name]; trades=st["trades"][name]; now=datetime.now(timezone.utc).isoformat()
    by={(x["market"],x["symbol"]):x for x in SNAP["candidates"]}
    closed=[]
    keep=[]
    for p in pos:
        c=by.get((p["market"],p["symbol"]))
        price=float(c["price"]) if c else p["entry"]
        reason=None;exitp=None
        if price<=p["stop"]:reason,exitp="STOP",p["stop"]
        elif price>=p["target"]:reason,exitp="ALVO",p["target"]
        if reason:
            gross=(exitp-p["entry"])*p["qty"]; tax=max(gross,0)*CFG["tax_rate_pct"]/100
            st["capital"]+=p["qty"]*exitp
            t={**p,"exit":exitp,"gross":gross,"tax":tax,"net":gross-tax,"reason":reason,"closed_at":now}
            trades.append(t);closed.append(t)
        else:keep.append(p)
    pos=keep
    for c in SNAP["candidates"]:
        if len(pos)>=cfg["max_positions"] or c.get("score",0)<cfg["score_min"] or c.get("signal")!="COMPRA":continue
        if any(p["symbol"]==c["symbol"] for p in pos):continue
        price=float(c["price"]);atr=max(float(c.get("atr",0)),price*0.001)
        stop=max(price-cfg["stop_atr"]*atr,price*0.985);target=price+cfg["target_atr"]*atr
        risk=st["capital"]*cfg["risk_pct"]/100; qty=min(risk/max(price-stop,price*0.001),st["capital"]*cfg["max_position_pct"]/100/price)
        value=qty*price
        if qty<=0 or value>st["capital"]:continue
        pos.append({"symbol":c["symbol"],"market":c["market"],"qty":qty,"entry":price,"stop":stop,"target":target,"score":c["score"],"opened_at":now})
        st["capital"]-=value
    st["positions"][name]=pos;st["trades"][name]=trades
    marked=sum(p["qty"]*float(by.get((p["market"],p["symbol"]),{}).get("price",p["entry"])) for p in pos)
    equity=st["capital"]+marked
    st["equity_peak"]=max(st.get("equity_peak",CFG["capital_inicial"]),equity)
    pnl=sum(t.get("net",0) for t in trades)
    return {"capital":st["capital"],"equity":equity,"pnl_net":pnl,"return_pct":(equity/CFG["capital_inicial"]-1)*100,
            "positions":len(pos),"trades":len(trades),"closed_now":len(closed),
            "win_rate":(sum(t.get("net",0)>0 for t in trades)/len(trades)*100 if trades else 0),
            "drawdown_pct":(1-equity/st["equity_peak"])*100}

def main():
    st=load()
    x=run("HUNTER_X",CFG["hunter_x"],st);e=run("HUNTER_EXTREME",CFG["hunter_extreme"],st)
    now=datetime.now(timezone.utc).isoformat()
    st["updated_at"]=now;STATE.write_text(json.dumps(st,indent=2,ensure_ascii=False))
    candidates=sorted(SNAP["candidates"],key=lambda c:c.get("score",0),reverse=True)[:12]
    DASH.write_text(json.dumps({"version":"V2","updated_at":now,"paper_trading":True,"real_orders":False,
      "scanner_updated_at":SNAP["updated_at"],"markets_scanned":SNAP["markets_scanned"],
      "strategies":{"HUNTER_X":x,"HUNTER_EXTREME":e},"opportunities":candidates},indent=2,ensure_ascii=False))
    print(json.dumps({"updated_at":now,"hunter_x":x,"hunter_extreme":e},ensure_ascii=False))
if __name__=="__main__":main()
