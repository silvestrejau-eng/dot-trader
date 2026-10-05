import json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).parent;CFG=json.loads((ROOT/"v2_config.json").read_text());SNAP=json.loads((ROOT/"market_snapshot.json").read_text());STATE=ROOT/"state.json";DASH=ROOT/"dashboard.json";INITIAL=float(CFG["capital_inicial"])

def default_state():
 return {"version":"2.2","strategies":{"HUNTER_X":{"capital":INITIAL,"positions":[],"trades":[],"equity_peak":INITIAL,"equity_history":[]},"HUNTER_EXTREME":{"capital":INITIAL,"positions":[],"trades":[],"equity_peak":INITIAL,"equity_history":[]}},"updated_at":None}

def load_state():
 if not STATE.exists():return default_state()
 try:
  s=json.loads(STATE.read_text())
  if "strategies" in s and all(k in s["strategies"] for k in ("HUNTER_X","HUNTER_EXTREME")):return s
 except Exception:pass
 return default_state()

def close_piece(st,p,qty,px,reason,now):
 gross=(px-float(p["entry"]))*qty;tax=max(gross,0)*float(CFG["tax_rate_pct"])/100;st["capital"]+=qty*px
 t={"symbol":p["symbol"],"market":p["market"],"qty":qty,"entry":p["entry"],"exit":px,"gross":gross,"tax":tax,"net":gross-tax,"score":p.get("score",0),"strategy":p.get("strategy"),"reason":reason,"opened_at":p["opened_at"],"closed_at":now}
 st["trades"].append(t);return t

def run(name,cfg,state):
 st=state["strategies"][name];st.setdefault("trades",[]);pos=list(st.get("positions",[]));cap=float(st.get("capital",INITIAL));now=datetime.now(timezone.utc).isoformat();by={(x["market"],x["symbol"]):x for x in SNAP["candidates"]};closed=0
 kept=[]
 for p in pos:
  p.setdefault("partial_taken",False);p.setdefault("target1",p.get("target",p["entry"]));p.setdefault("target2",p.get("target",p["entry"]))
  c=by.get((p["market"],p["symbol"]));px=float(c["price"]) if c else float(p["entry"])
  if not p["partial_taken"] and px>=p["target1"]:
   q=p["qty"]*.5;close_piece(st,p,q,float(p["target1"]),"PARCIAL_1R",now);p["qty"]-=q;p["partial_taken"]=True;p["stop"]=max(float(p["stop"]),float(p["entry"]));closed+=1
  if p["qty"]>0 and px<=float(p["stop"]):
   close_piece(st,p,p["qty"],float(p["stop"]),"STOP_BE" if p["partial_taken"] else "STOP",now);p["qty"]=0;closed+=1
  elif p["qty"]>0 and px>=float(p["target2"]):
   close_piece(st,p,p["qty"],float(p["target2"]),"ALVO_2R",now);p["qty"]=0;closed+=1
  if p["qty"]>0:kept.append(p)
 pos=kept;opened=0
 for c in SNAP["candidates"]:
  if len(pos)>=int(cfg["max_positions"]):break
  if float(c.get("score",0))<float(cfg["score_min"]) or c.get("signal")!="COMPRA":continue
  if any(p["symbol"]==c["symbol"] for p in pos):continue
  px=float(c["price"]);a=max(float(c.get("atr",0)),px*.001);stop=max(px-float(cfg["stop_atr"])*a,px*float(cfg["hard_stop_floor_pct"]));risk=cap*float(cfg["risk_pct"])/100;dist=max(px-stop,px*.001);qty=min(risk/dist,(cap*float(cfg["max_position_pct"])/100)/px);value=qty*px
  if qty<=0 or value<=0 or value>cap:continue
  t1=px+dist*float(cfg["target1_r"]);t2=px+dist*float(cfg["target2_r"])
  pos.append({"symbol":c["symbol"],"market":c["market"],"qty":qty,"initial_qty":qty,"entry":px,"stop":stop,"target":t2,"target1":t1,"target2":t2,"score":c["score"],"strategy":name,"opened_at":now,"partial_taken":False,"setup":c.get("reasons",[])})
  cap-=value;opened+=1
 st["capital"]=cap;st["positions"]=pos;openp=0;marked=0
 for p in pos:
  c=by.get((p["market"],p["symbol"]));mark=float(c["price"]) if c else float(p["entry"]);p["mark"]=mark;p["unrealized_pnl"]=(mark-float(p["entry"]))*float(p["qty"]);openp+=p["unrealized_pnl"];marked+=p["qty"]*mark
 equity=cap+marked;peak=max(float(st.get("equity_peak",INITIAL)),equity);st["equity_peak"]=peak;hist=list(st.get("equity_history",[]));hist.append({"timestamp":now,"equity":equity,"capital":cap,"positions":len(pos)});st["equity_history"]=hist[-500:];tr=st["trades"]
 return {"capital":cap,"equity":equity,"pnl_net":sum(float(t.get("net",0)) for t in tr),"return_pct":(equity/INITIAL-1)*100,"positions":len(pos),"trades":len(tr),"closed_now":closed,"opened_now":opened,"win_rate":sum(float(t.get("net",0))>0 for t in tr)/len(tr)*100 if tr else 0,"drawdown_pct":max(0,(1-equity/peak)*100),"open_pnl":openp,"risk_per_trade_pct":float(cfg["risk_pct"])}

def main():
 if not SNAP.get("candidates"):raise RuntimeError("Scanner sem candidatos")
 s=load_state();hx=run("HUNTER_X",CFG["hunter_x"],s);he=run("HUNTER_EXTREME",CFG["hunter_extreme"],s);now=datetime.now(timezone.utc).isoformat();s["updated_at"]=now;s["version"]="2.2";STATE.write_text(json.dumps(s,indent=2,ensure_ascii=False))
 ops=sorted(SNAP["candidates"],key=lambda x:(x.get("score",0),x.get("momentum_pct",0)),reverse=True)[:12]
 d={"version":"V2.2 • AZIZ PLAYBOOK","updated_at":now,"paper_trading":True,"real_orders":False,"scanner_updated_at":SNAP.get("updated_at"),"markets_scanned":SNAP.get("markets_scanned",0),"score_model":SNAP.get("score_model",{}),"strategies":{"HUNTER_X":{**hx,"positions_detail":s["strategies"]["HUNTER_X"]["positions"],"trades_detail":s["strategies"]["HUNTER_X"]["trades"],"equity_history":s["strategies"]["HUNTER_X"]["equity_history"]},"HUNTER_EXTREME":{**he,"positions_detail":s["strategies"]["HUNTER_EXTREME"]["positions"],"trades_detail":s["strategies"]["HUNTER_EXTREME"]["trades"],"equity_history":s["strategies"]["HUNTER_EXTREME"]["equity_history"]}},"opportunities":ops}
 DASH.write_text(json.dumps(d,indent=2,ensure_ascii=False));print(json.dumps(d,ensure_ascii=False))
if __name__=="__main__":main()