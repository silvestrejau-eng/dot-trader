"""DOT Trader - motor multi-mercado de Paper Trading.
Dados públicos. Nunca envia ordens reais.
"""
from pathlib import Path
from datetime import datetime, timezone
import json, urllib.request, urllib.parse

CAPITAL_INICIAL=10000.0
RISCO_PCT=0.5
MAX_POSICOES=20
MAX_POSITION_PCT=5.0
STOP_PCT=0.5
ALVO_PCT=1.0
STATE=Path("docs/paper_state.json")
DADOS_OUTS=[Path("docs/dados.json"),Path("dados.json")]
SINAL=Path("docs/sinal.json")

def load(path,default):
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default

def yahoo_price(symbol,market):
    y=symbol+".SA" if market=="B3" else symbol
    u="https://query1.finance.yahoo.com/v8/finance/chart/"+urllib.parse.quote(y)+"?interval=5m&range=1d"
    req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=15) as r:
        d=json.loads(r.read().decode())["chart"]["result"][0]
    return float(d["meta"]["regularMarketPrice"])

def b3_price(symbol):
    u="https://brapi.dev/api/quote/"+urllib.parse.quote(symbol)
    req=urllib.request.Request(u,headers={"User-Agent":"DOT-Trader-Paper"})
    with urllib.request.urlopen(req,timeout=15) as r:
        return float(json.loads(r.read().decode())["results"][0]["regularMarketPrice"])

def crypto_price(symbol):
    u="https://data-api.binance.vision/api/v3/ticker/price?"+urllib.parse.urlencode({"symbol":symbol})
    with urllib.request.urlopen(u,timeout=15) as r:
        return float(json.loads(r.read().decode())["price"])

def current_price(symbol,market):
    if market=="CRYPTO": return crypto_price(symbol)
    if market=="B3": return b3_price(symbol)
    return yahoo_price(symbol,market)

def main():
    s=load(SINAL,{})
    st=load(STATE,{"capital":CAPITAL_INICIAL,"positions":[],"trades":[]})
    now=datetime.now(timezone.utc).isoformat()
    positions=st.get("positions",[]); trades=st.get("trades",[]); closed=[]

    # Stops/alvos para TODAS as posições abertas.
    remaining=[]
    for pos in positions:
        try: p=current_price(pos["symbol"],pos.get("market","CRYPTO"))
        except Exception: p=pos["entry_price"]
        exit_price=None; reason=None
        if p<=pos["stop_price"]: exit_price=pos["stop_price"]; reason="STOP"
        elif p>=pos["target_price"]: exit_price=pos["target_price"]; reason="ALVO"
        if exit_price is None: remaining.append(pos); continue
        gross=(exit_price-pos["entry_price"])*pos["quantity"]
        st["capital"]+=pos["quantity"]*exit_price
        tax=max(0.0,gross)*0.15; net=gross-tax
        trade={**pos,"exit_price":exit_price,"gross":gross,"fees":0.0,
               "estimated_tax":tax,"net":net,"reason":reason,"closed_at":now}
        trades.append(trade); closed.append(trade)
    positions=remaining

    # Seleciona o melhor candidato >=75 ainda não aberto.
    candidates=s.get("candidates",[])
    selected=None
    for c in candidates:
        if c.get("signal")=="COMPRA" and float(c.get("score",0))>=75:
            if not any(x["symbol"]==c["symbol"] for x in positions):
                selected=c; break

    if selected and len(positions)<MAX_POSICOES:
        symbol=selected["symbol"]; market=selected.get("market","CRYPTO"); p=float(selected["price"])
        risk=st["capital"]*(RISCO_PCT/100)
        stop_distance=p*(STOP_PCT/100)
        qty_risk=risk/stop_distance if stop_distance>0 else 0
        max_value=st["capital"]*(MAX_POSITION_PCT/100)
        qty=min(qty_risk,max_value/p if p>0 else 0)
        value=qty*p
        if qty>0 and value<=st["capital"]:
            positions.append({"symbol":symbol,"market":market,"quantity":qty,
              "entry_price":p,"stop_price":p*(1-STOP_PCT/100),
              "target_price":p*(1+ALVO_PCT/100),"risk_value":risk,
              "score":float(selected["score"]),"source":selected.get("source"),
              "opened_at":now})
            st["capital"]-=value

    st["positions"]=positions; st["trades"]=trades; st["updated_at"]=now
    STATE.parent.mkdir(parents=True,exist_ok=True)
    STATE.write_text(json.dumps(st,indent=2,ensure_ascii=False),encoding="utf-8")

    lucro=sum(float(t.get("net",0)) for t in trades)
    taxas=sum(float(t.get("fees",0)) for t in trades)
    impostos=sum(float(t.get("estimated_tax",0)) for t in trades)
    aberto=0.0
    for x in positions:
        try: aberto+=float(x["quantity"])*current_price(x["symbol"],x.get("market","CRYPTO"))
        except Exception: aberto+=float(x["quantity"])*float(x["entry_price"])
    patrimonio=st["capital"]+aberto
    dados={"config":{"capital_inicial":CAPITAL_INICIAL,"capital":st["capital"],
      "max_position_pct":MAX_POSITION_PCT,"stop_loss_pct":STOP_PCT,"take_profit_pct":ALVO_PCT,
      "fee_pct":0.0,"tax_rate_pct":15.0,"paper_trading":True,"risk_per_trade_pct":RISCO_PCT,
      "max_positions":MAX_POSICOES,"score_min":75,"rr_min":2.0},
      "positions":positions,"trades":trades,
      "market":{"symbol":s.get("symbol"),"market":s.get("market"),"price":s.get("price"),
        "score":s.get("score"),"signal":s.get("signal"),"candidates":candidates},
      "summary":{"lucro_liquido":lucro,"taxas":taxas,"impostos_estimados":impostos,
        "patrimonio":patrimonio,"retorno_pct":(patrimonio/CAPITAL_INICIAL-1)*100,
        "operacoes":len(trades)}}
    for path in DADOS_OUTS:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(dados,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"selected":selected,"opened":len(positions),"closed":len(closed),
      "capital":st["capital"]},ensure_ascii=False))

if __name__=="__main__": main()
