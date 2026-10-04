"""
DOT Trader V1 - Paper Trading
Autor: silvestrejau-eng
Uso: simulacao educacional. Nao envia ordens reais.

Execute:
    python dot_trader.py

Comandos no menu:
    1 - Nova cotacao / analisar
    2 - Abrir posicao simulada
    3 - Fechar posicao simulada
    4 - Ver carteira
    5 - Historico
    6 - Configuracoes
    0 - Sair
"""

from dataclasses import dataclass, asdict
from datetime import datetime
import json
from pathlib import Path


ARQUIVO = Path("dot_trader_data.json")


@dataclass
class Config:
    capital_inicial: float = 10000.00
    capital: float = 10000.00
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
        positions = [Position(**x) for x in data.get("positions", [])]
        trades = [Trade(**x) for x in data.get("trades", [])]
        return cfg, positions, trades
    except Exception:
        print("Aviso: dados invalidos. Iniciando uma nova carteira.")
        return Config(), [], []


def salvar(cfg, positions, trades):
    data = {
        "config": asdict(cfg),
        "positions": [asdict(x) for x in positions],
        "trades": [asdict(x) for x in trades],
    }
    ARQUIVO.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def dinheiro(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def percentual(v):
    return f"{v:.2f}%"


def sinal(preco_anterior, preco_atual):
    if preco_anterior <= 0 or preco_atual <= 0:
        return "HOLD", "Preco invalido."

    variacao = (preco_atual / preco_anterior - 1) * 100

    if variacao >= 0.50:
        return "COMPRA", f"Momentum positivo: +{variacao:.2f}%"
    if variacao <= -0.50:
        return "VENDA/EVITAR", f"Momentum negativo: {variacao:.2f}%"
    return "HOLD", f"Movimento pequeno: {variacao:+.2f}%"

def abrir_posicao(cfg, positions, trades):
    if not cfg.paper_trading:
        print("Operacao real bloqueada nesta V1.")
        return

    if positions:
        print("Ja existe uma posicao aberta nesta V1.")
        return

    symbol = input("Ativo (ex.: DOT/BRL): ").strip().upper()
    try:
        price = float(input("Preco atual: ").replace(",", "."))
    except ValueError:
        print("Preco invalido.")
        return

    if price <= 0:
        print("Preco deve ser maior que zero.")
        return

    limite = cfg.capital * cfg.max_position_pct / 100
    quantidade = limite / price

    if quantidade <= 0:
        print("Capital insuficiente.")
        return

    custo = limite * cfg.fee_pct / 100
    total = limite + custo

    if total > cfg.capital:
        print("Capital insuficiente para taxas.")
        return

    cfg.capital -= total

    pos = Position(
        symbol=symbol,
        quantity=quantidade,
        entry_price=price,
        stop_price=price * (1 - cfg.stop_loss_pct / 100),
        target_price=price * (1 + cfg.take_profit_pct / 100),
        opened_at=datetime.now().isoformat(timespec="seconds"),
    )

    positions.append(pos)
    salvar(cfg, positions, [])
    print("\nPOSICAO ABERTA - PAPER TRADING")
    print(f"Ativo: {symbol}")
    print(f"Quantidade: {quantidade:.8f}")
    print(f"Entrada: {dinheiro(price)}")
    print(f"Stop: {dinheiro(pos.stop_price)}")
    print(f"Alvo: {dinheiro(pos.target_price)}")


def fechar_posicao(cfg, positions, trades):
    if not positions:
        print("Nenhuma posicao aberta.")
        return

    pos = positions[0]

    try:
        price = float(input(f"Preco de saida de {pos.symbol}: ").replace(",", "."))
    except ValueError:
        print("Preco invalido.")
        return

    if price <= 0:
        print("Preco deve ser maior que zero.")
        return

    buy_value = pos.quantity * pos.entry_price
    sell_value = pos.quantity * price
    fees = (buy_value + sell_value) * cfg.fee_pct / 100
    gross = sell_value - buy_value

    taxable = max(0.0, gross - fees)
    estimated_tax = taxable * cfg.tax_rate_pct / 100
    net = gross - fees - estimated_tax

  cfg.capital += sell_value - (sell_value * cfg.fee_pct / 100) - estimated_tax

    trade = Trade(
        symbol=pos.symbol,
        quantity=pos.quantity,
        entry_price=pos.entry_price,
        exit_price=price,
        gross=gross,
        fees=fees,
        estimated_tax=estimated_tax,
        net=net,
        opened_at=pos.opened_at,
        closed_at=datetime.now().isoformat(timespec="seconds"),
    )

    trades.append(trade)
    positions.clear()
    salvar(cfg, positions, trades)

    print("\nOPERACAO ENCERRADA")
    print(f"Resultado bruto: {dinheiro(gross)}")
    print(f"Taxas estimadas: {dinheiro(fees)}")
    print(f"Imposto estimado: {dinheiro(estimated_tax)}")
    print(f"Resultado liquido: {dinheiro(net)}")


def carteira(cfg, positions, trades):
    lucro = sum(t.net for t in trades)

    print("\n========== CARTEIRA ==========")
    print(f"Capital disponivel: {dinheiro(cfg.capital)}")
    print(f"Capital inicial:    {dinheiro(cfg.capital_inicial)}")
    print(f"Lucro/prejuizo:     {dinheiro(lucro)}")
    print(f"Operacoes fechadas: {len(trades)}")
    print(f"Posicoes abertas:   {len(positions)}")
    print(f"Modo:               {'PAPER TRADING' if cfg.paper_trading else 'REAL'}")

    if positions:
        p = positions[0]
        print("\nPOSICAO ABERTA")
        print(f"{p.symbol} | qtd. {p.quantity:.8f}")
        print(f"Entrada: {dinheiro(p.entry_price)}")
        print(f"Stop:    {dinheiro(p.stop_price)}")
        print(f"Alvo:    {dinheiro(p.target_price)}")


def historico(trades):
    print("\n========== HISTORICO ==========")
    if not trades:
        print("Nenhuma operacao encerrada.")
        return

    for i, t in enumerate(trades, 1):
        print(
            f"{i}. {t.symbol} | "
            f"entrada {dinheiro(t.entry_price)} | "
            f"saida {dinheiro(t.exit_price)} | "
            f"liquido {dinheiro(t.net)}"
        )


def configuracoes(cfg, positions, trades):
    print("\n========== CONFIGURACOES ==========")
    print(f"Capital: {dinheiro(cfg.capital)}")
    print(f"Risco por operacao: {percentual(cfg.max_position_pct)}")
    print(f"Stop-loss: {percentual(cfg.stop_loss_pct)}")
    print(f"Take-profit: {percentual(cfg.take_profit_pct)}")
    print(f"Taxa: {percentual(cfg.fee_pct)}")
    print(f"Imposto estimado: {percentual(cfg.tax_rate_pct)}")

    resposta = input("Alterar parametros? (s/n): ").strip().lower()
    if resposta != "s":
        return

    try:
        cfg.max_position_pct = float(input("Risco % [10]: ").replace(",", "."))
        cfg.stop_loss_pct = float(input("Stop-loss % [1]: ").replace(",", "."))
        cfg.take_profit_pct = float(input("Take-profit % [2]: ").replace(",", "."))
        cfg.fee_pct = float(input("Taxa % [0]: ").replace(",", "."))
        cfg.tax_rate_pct = float(input("Imposto estimado % [15]: ").replace(",", "."))
    except ValueError:
        print("Valor invalido. Mantendo configuracoes anteriores.")
        return

    salvar(cfg, positions, trades)
    print("Configuracoes salvas.")


def main():
    cfg, positions, trades = carregar()

    print("====================================")
    print("       DOT TRADER V1")
    print("       PAPER TRADING")
    print("====================================")

    while True:
        print("\n1 - Analisar preco")
        print("2 - Abrir posicao simulada")
        print("3 - Fechar posicao simulada")
        print("4 - Ver carteira")
        print("5 - Historico")
        print("6 - Configuracoes")
        print("0 - Sair")

        opcao = input("\nEscolha: ").strip()

        if opcao == "1":
            try:
                anterior = float(input("Preco anterior: ").replace(",", "."))
                atual = float(input("Preco atual: ").replace(",", "."))
                acao, motivo = sinal(anterior, atual)
                print(f"\nSINAL: {acao}")
                print(f"MOTIVO: {motivo}")
            except ValueError:
                print("Valores invalidos.")

        elif opcao == "2":
            abrir_posicao(cfg, positions)
            # preservar historico existente
            salvar(cfg, positions, trades)

        elif opcao == "3":
            fechar_posicao(cfg, positions, trades)

        elif opcao == "4":
            carteira(cfg, positions, trades)

        elif opcao == "5":
            historico(trades)

        elif opcao == "6":
            configuracoes(cfg, positions, trades)

        elif opcao == "0":
            salvar(cfg, positions, trades)
            print("DOT Trader encerrado.")
            break

        else:
            print("Opcao invalida.")


if __name__ == "__main__":
    main()
