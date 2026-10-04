"""
DOT Trader V2 - Paper Trading
Nao envia ordens reais.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
import json
from pathlib import Path

ARQUIVO = Path("dot_trader_data.json")


@dataclass
class Config:
    capital_inicial: float = 10000.0
    capital: float = 10000.0
    max_position_pct: float = 10.0
    stop_loss_pct: float = 1.0
    take_profit_pct: float = 2.0
    fee_pct: float = 0.0
    tax_rate_pct: float = 15.0
    paper_trading: bool = True


@dataclass
class Position:
    symbol: str
    quantity: float
    entry_price: float
    stop_price: float
    target_price: float
    opened_at: str


@dataclass
class Trade:
    symbol: str
    quantity: float
    entry_price: float
    exit_price: float
    gross: float
    fees: float
    estimated_tax: float
    net: float
    opened_at: str
    closed_at: str


def carregar():
    if not ARQUIVO.exists():
        return Config(), [], []

    try:
        data = json.loads(ARQUIVO.read_text(encoding="utf-8"))
        cfg = Config(**data.get("config", {}))
        positions = [
            Position(**x)
            for x in data.get("positions", [])
        ]

        trades = []
        for x in data.get("trades", []):
            trades.append(Trade(**x))

        return cfg, positions, trades

    except Exception:
        print("Dados invalidos. Nova carteira criada.")
        return Config(), [], []


def salvar(cfg, positions, trades):
    data = {
        "config": asdict(cfg),
        "positions": [asdict(x) for x in positions],
        "trades": [asdict(x) for x in trades],
    }

    ARQUIVO.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


def dinheiro(v):
    return (
        f"R$ {v:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def pct(v):
    return f"{v:.2f}%"


def sinal(anterior, atual):
    if anterior <= 0 or atual <= 0:
        return "HOLD", "Preco invalido."

    variacao = (atual / anterior - 1) * 100

    if variacao >= 0.50:
        return "COMPRA", f"Alta de {variacao:.2f}%"

    if variacao <= -0.50:
        return "VENDA/EVITAR", f"Queda de {variacao:.2f}%"

    return "HOLD", f"Variacao de {variacao:+.2f}%"


def abrir_posicao(cfg, positions, trades):

    if positions:
        print("Ja existe uma posicao aberta.")
        return

    symbol = input(
        "Ativo (ex.: DOT/BRL): "
    ).strip().upper()

    try:
        price = float(
            input("Preco atual: ").replace(",", ".")
        )
    except ValueError:
        print("Preco invalido.")
        return

    if price <= 0:
        print("Preco invalido.")
        return

    valor = (
        cfg.capital
        * cfg.max_position_pct
        / 100
    )

    taxa = valor * cfg.fee_pct / 100
    total = valor + taxa

    if total > cfg.capital:
        print("Capital insuficiente.")
        return

    quantidade = valor / price

    cfg.capital -= total

    pos = Position(
        symbol=symbol,
        quantity=quantidade,
        entry_price=price,
        stop_price=price * (
            1 - cfg.stop_loss_pct / 100
        ),
        target_price=price * (
            1 + cfg.take_profit_pct / 100
        ),
        opened_at=datetime.now().isoformat(
            timespec="seconds"
        )
    )

    positions.append(pos)

    # Preserva o historico.
    salvar(cfg, positions, trades)

    print("\n===== POSICAO ABERTA =====")
    print(f"Ativo: {symbol}")
    print(f"Quantidade: {quantidade:.8f}")
    print(f"Valor: {dinheiro(valor)}")
    print(f"Taxa: {dinheiro(taxa)}")
    print(f"Entrada: {dinheiro(price)}")
    print(f"Stop: {dinheiro(pos.stop_price)}")
    print(f"Alvo: {dinheiro(pos.target_price)}")


def fechar_posicao(cfg, positions, trades):

    if not positions:
        print("Nenhuma posicao aberta.")
        return

    pos = positions[0]

    try:
        price = float(
            input(
                f"Preco de saida de {pos.symbol}: "
            ).replace(",", ".")
        )
    except ValueError:
        print("Preco invalido.")
        return

    if price <= 0:
        print("Preco invalido.")
        return

    compra = pos.quantity * pos.entry_price
    venda = pos.quantity * price

    taxa_compra = compra * cfg.fee_pct / 100
    taxa_venda = venda * cfg.fee_pct / 100
    taxas = taxa_compra + taxa_venda

    bruto = venda - compra

    lucro_tributavel = max(
        0.0,
        bruto - taxas
    )

    imposto = (
        lucro_tributavel
        * cfg.tax_rate_pct
        / 100
    )

    liquido = bruto - taxas - imposto

    cfg.capital += (
        venda
        - taxa_venda
        - imposto
    )

    trade = Trade(
        symbol=pos.symbol,
        quantity=pos.quantity,
        entry_price=pos.entry_price,
        exit_price=price,
        gross=bruto,
        fees=taxas,
        estimated_tax=imposto,
        net=liquido,
        opened_at=pos.opened_at,
        closed_at=datetime.now().isoformat(
            timespec="seconds"
        )
    )

    trades.append(trade)
    positions.clear()

    salvar(cfg, positions, trades)

    print("\n===== OPERACAO ENCERRADA =====")
    print(f"Resultado bruto: {dinheiro(bruto)}")
    print(f"Taxas: {dinheiro(taxas)}")
    print(f"Imposto estimado: {dinheiro(imposto)}")
    print(f"Resultado liquido: {dinheiro(liquido)}")
    print(f"Capital atual: {dinheiro(cfg.capital)}")


def carteira(cfg, positions, trades):

    lucro = sum(t.net for t in trades)
    taxas = sum(t.fees for t in trades)
    impostos = sum(
        t.estimated_tax for t in trades
    )

    aberto = sum(
        p.quantity * p.entry_price
        for p in positions
    )

    patrimonio = cfg.capital + aberto

    retorno = (
        (patrimonio / cfg.capital_inicial - 1)
        * 100
    )

    print("\n========== CARTEIRA ==========")
    print(
        f"Capital inicial: "
        f"{dinheiro(cfg.capital_inicial)}"
    )
    print(
        f"Capital disponivel: "
        f"{dinheiro(cfg.capital)}"
    )
    print(
        f"Posicoes abertas: "
        f"{dinheiro(aberto)}"
    )
    print(
        f"Patrimonio: "
        f"{dinheiro(patrimonio)}"
    )
    print(
        f"Lucro liquido: "
        f"{dinheiro(lucro)}"
    )
    print(
        f"Taxas: {dinheiro(taxas)}"
    )
    print(
        f"Impostos estimados: "
        f"{dinheiro(impostos)}"
    )
    print(
        f"Retorno: {pct(retorno)}"
    )
    print(
        f"Operacoes: {len(trades)}"
    )

    if positions:
        p = positions[0]

        print("\n===== POSICAO =====")
        print(f"Ativo: {p.symbol}")
        print(
            f"Quantidade: "
            f"{p.quantity:.8f