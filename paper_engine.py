"""DOT Trader - motor de Paper Trading.
Usa apenas dados públicos e nunca envia ordens reais.
"""
from pathlib import Path
from datetime import datetime, timezone
import json
import urllib.request
import urllib.parse

SYMBOL="DOTUSDT"
INTERVAL="15m"
CAPITAL_INICIAL=10000.0
RISCO_PCT=0.5
MAX_POSICOES=3
STOP_PCT=1.0
ALVO_PCT=2.0
STATE=Path("docs/paper_state.json")
DADOS_OUTS=[Path("docs/dados.json"),Path("dados.json")]
SINAL=Path("docs/sinal.json")
API="https://data-api.binance.vision/api/v3/ticker/price"

def load(path, default):
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default

def price():
    q=urllib.parse.urlencode({"symbol":SYMBOL})
    with urllib.request.urlopen(API+"?"+q,timeout=15) as r:
        return float(json.loads(r.read().decode())["price"])

def main():
    s=load(SINAL,{})
    st=load(STATE,{"capital":CAPITAL_INICIAL,"positions":[],"trades":[]})
    now=datetime.now(timezone.utc).isoformat()
    p=price()

    positions=st.get("positions",[])
    trades=st.get("trades",[])
    closed=[]

    # Primeiro verifica stop/alvo das posições existentes.
    remaining=[]
    for pos in positions:
        exit_price=None
        reason=None
        if p <= pos["stop_price"]:
            exit_price=pos["stop_price"]; reason="STOP"
        elif p >= pos["target_price"]:
            exit_price=pos["target_price"]; reason="ALVO"
        if exit_price is None:
            remaining.append(pos)
            continue
        gross=(exit_price-pos["entry_price"])*pos["quantity"]
        st["capital"] += pos["quantity"]*exit_price
        tax=max(0.0,gross)*0.15
        net=gross-tax
        trade={**pos,"exit_price":exit_price,"gross":gross,"fees":0.0,
               "estimated_tax":tax,"net":net,"reason":reason,"closed_at":now}
        trades.append(trade); closed.append(trade)
    positions=remaining

    # Entrada virtual somente com score >= 80 e sem duplicar o mesmo ativo.
    score=float(s.get("score",0) or 0)
    signal=s.get("signal","HOLD")
    if signal=="COMPRA" and score>=80 and len(positions)<MAX_POSICOES and not any(x["symbol"]==SYMBOL for x in positions):
        risk=st["capital"]*(RISCO_PCT/100)
        stop_distance=p*(STOP_PCT/100)
        qty=risk/stop_distance if stop_distance>0 else 0
        value=qty*p
        if qty>0 and value<=st["capital"]:
            pos={"symbol":SYMBOL,"quantity":qty,"entry_price":p,
                 "stop_price":p*(1-STOP_PCT/100),
                 "target_price":p*(1+ALVO_PCT/100),
                 "risk_value":risk,"score":score,"opened_at":now}
            st["capital"]-=value
            positions.append(pos)

    st["positions"]=positions
    st["trades"]=trades
    st["updated_at"]=now
    STATE.parent.mkdir(parents=True,exist_ok=True)
    STATE.write_text(json.dumps(st,indent=2,ensure_ascii=False),encoding="utf-8")

    lucro=sum(float(t.get("net",0)) for t in trades)
    taxas=sum(float(t.get("fees",0)) for t in trades)
    impostos=sum(float(t.get("estimated_tax",0)) for t in trades)
    aberto=sum(float(x["quantity"])*p for x in positions)
    patrimonio=st["capital"]+aberto
    dados={"config":{"capital_inicial":CAPITAL_INICIAL,"capital":st["capital"],
        "max_position_pct":5.0,"stop_loss_pct":STOP_PCT,"take_profit_pct":ALVO_PCT,
        "fee_pct":0.0,"tax_rate_pct":15.0,"paper_trading":True,
        "risk_per_trade_pct":RISCO_PCT,"max_positions":MAX_POSICOES},
        "positions":positions,"trades":trades,
        "market":{"symbol":SYMBOL,"price":p,"score":score,"signal":signal},
        "summary":{"lucro_liquido":lucro,"taxas":taxas,"impostos_estimados":impostos,
                   "patrimonio":patrimonio,"retorno_pct":(patrimonio/CAPITAL_INICIAL-1)*100,
                   "operacoes":len(trades)}}
    for DADOS in DADOS_OUTS:
        DADOS.parent.mkdir(parents=True,exist_ok=True)
        DADOS.write_text(json.dumps(dados,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"price":p,"signal":signal,"score":score,
        "opened":len(positions),"closed":len(closed),"capital":st["capital"]},ensure_ascii=False))

if __name__=="__main__":
    main()
