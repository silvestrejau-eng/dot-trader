"""Dados públicos de mercado para o DOT Trader.

Nenhuma chave de API e nenhuma permissão de negociação são usadas.
Fonte principal: Binance Spot REST pública.
"""

from json import loads
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://api.binance.com/api/v3"


def ticker(symbol):
    params = urlencode({"symbol": symbol.replace("/", "").upper()})
    req = Request(
        f"{BASE_URL}/ticker/24hr?{params}",
        headers={"User-Agent": "DOT-Trader/1.0"},
    )

    with urlopen(req, timeout=8) as response:
        data = loads(response.read().decode("utf-8"))

    return {
        "symbol": data["symbol"],
        "price": float(data["lastPrice"]),
        "open": float(data["openPrice"]),
        "high": float(data["highPrice"]),
        "low": float(data["lowPrice"]),
        "volume": float(data["volume"]),
        "change_pct": float(data["priceChangePercent"]),
    }


def price(symbol):
    params = urlencode({"symbol": symbol.replace("/", "").upper()})
    req = Request(
        f"{BASE_URL}/ticker/price?{params}",
        headers={"User-Agent": "DOT-Trader/1.0"},
    )

    with urlopen(req, timeout=8) as response:
        data = loads(response.read().decode("utf-8"))

    return float(data["price"])
