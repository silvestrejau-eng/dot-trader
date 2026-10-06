"""Relogio de sessoes do DOT Trader. Nao envia ordens."""
from datetime import datetime, time
from zoneinfo import ZoneInfo

SESSIONS = {
    "B3": {"tz":"America/Sao_Paulo", "regular":[("10:00","16:55")], "after":[("17:30","18:00")]},
    "NYSE": {"tz":"America/New_York", "pre":[("04:00","09:30")], "regular":[("09:30","16:00")], "after":[("16:00","20:00")]},
    "NASDAQ": {"tz":"America/New_York", "pre":[("04:00","09:30")], "regular":[("09:30","16:00")], "after":[("16:00","20:00")]},
    "LONDON": {"tz":"Europe/London", "regular":[("08:00","16:30")]},
    "XETRA": {"tz":"Europe/Berlin", "regular":[("09:00","17:30")]},
    "TOKYO": {"tz":"Asia/Tokyo", "regular":[("09:00","11:30"),("12:30","15:30")]},
    "HONG_KONG": {"tz":"Asia/Hong_Kong", "regular":[("09:30","12:00"),("13:00","16:00")]},
    "CRYPTO": {"tz":"UTC", "regular":[("00:00","23:59")]},
}

def _inside(now, windows):
    t=now.time()
    for a,b in windows:
        if time.fromisoformat(a) <= t < time.fromisoformat(b): return True
    return False

def session_status(market, now=None):
    key = market if market in SESSIONS else "CRYPTO"
    cfg=SESSIONS[key]
    now=now or datetime.now(ZoneInfo(cfg["tz"]))
    if now.weekday() >= 5 and key != "CRYPTO":
        return {"market":key,"state":"FECHADO","timezone":cfg["tz"],"local_time":now.isoformat()}
    for state in ("pre","regular","after"):
        if _inside(now,cfg.get(state,[])):
            return {"market":key,"state":state.upper(),"timezone":cfg["tz"],"local_time":now.isoformat()}
    return {"market":key,"state":"FECHADO","timezone":cfg["tz"],"local_time":now.isoformat()}

def all_sessions():
    return {k: session_status(k) for k in SESSIONS}
