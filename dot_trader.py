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
        cfg_data = data.get("config", {})
        cfg = Config(**cfg_data)

        positions = [Position(**x) for x in data.get("positions", [])]
        trades = [Trade(**x) for x in data.get("trades", [])]

        return cfg, positions, trades
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        print("Dados invalidos. Nova carteira criada.")
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
    return (
        f"R$ {v:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def pct(v):
    return f"{v:.2f}%"


def ler_float(prompt):
    try:
        valor = float(input(prompt).strip().replace(",", "."))
        if valor <= 0:
            raise ValueError
        return valor
    except ValueError:
        print("Valor invalido.")
        return None


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

    symbol = input("Ativo (ex.: DOT/BRL): ").strip().upper()
    if not symbol:
        print("Ativo invalido.")
        return

    price = ler_float("Preco de entrada: ")
    if price is None:
        return

    valor = cfg.capital * cfg.max_position_pct / 100
    taxa = valor * cfg.fee_pct / 100
    total = valor + taxa

    if valor <= 0 or total > cfg.capital:
        print("Capital insuficiente para abrir a posicao.")
        return

    quantidade = valor / price

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
    salvar(cfg, positions, trades)

    print("\n===== POSICAO ABERTA =====")
    print(f"Ativo:       {symbol}")
    print(f"Quantidade:  {quantidade:.8f}")
    print(f"Valor:       {dinheiro(valor)}")
    print(f"Taxa:        {dinheiro(taxa)}")
    print(f"Entrada:     {dinheiro(price)}")
    print(f"Stop:        {dinheiro(pos.stop_price)}")
    print(f"Alvo:        {dinheiro(pos.target_price)}")


def fechar_posicao(cfg, positions, trades):
    if not positions:
        print("Nenhuma posicao aberta.")
        return

    pos = positions[0]
    price = ler_float(f"Preco de saida de {pos.symbol}: ")
    if price is None:
        return

    compra = pos.quantity * pos.entry_price
    venda = pos.quantity * price

    taxa_compra = compra * cfg.fee_pct / 100
    taxa_venda = venda * cfg.fee_pct / 100
    taxas = taxa_compra + taxa_venda

    bruto = venda - compra
    lucro_tributavel = max(0.0, bruto - taxas)
    imposto = lucro_tributavel * cfg.tax_rate_pct / 100
    liquido = bruto - taxas - imposto

    cfg.capital += venda - taxa_venda - imposto

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
        closed_at=datetime.now().isoformat(timespec="seconds"),
    )

    trades.append(trade)
    positions.clear()
    salvar(cfg, positions, trades)

    print("\n===== OPERACAO ENCERRADA =====")
    print(f"Resultado bruto:    {dinheiro(bruto)}")
    print(f"Taxas:              {dinheiro(taxas)}")
    print(f"Imposto estimado:   {dinheiro(imposto)}")
    print(f"Resultado liquido:  {dinheiro(liquido)}")
    print(f"Capital atual:      {dinheiro(cfg.capital)}")


def carteira(cfg, positions, trades):
    lucro = sum(t.net for t in trades)
    taxas = sum(t.fees for t in trades)
    impostos = sum(t.estimated_tax for t in trades)
    aberto = sum(p.quantity * p.entry_price for p in positions)
    patrimonio = cfg.capital + aberto

    if cfg.capital_inicial:
        retorno = (patrimonio / cfg.capital_inicial - 1) * 100
    else:
        retorno = 0.0

    print("\n========== CARTEIRA ==========")
    print(f"Capital inicial:    {dinheiro(cfg.capital_inicial)}")
    print(f"Capital disponivel: {dinheiro(cfg.capital)}")
    print(f"Posicoes abertas:   {dinheiro(aberto)}")
    print(f"Patrimonio:         {dinheiro(patrimonio)}")
    print(f"Lucro liquido:      {dinheiro(lucro)}")
    print(f"Taxas:              {dinheiro(taxas)}")
    print(f"Impostos estimados: {dinheiro(impostos)}")
    print(f"Retorno:            {pct(retorno)}")
    print(f"Operacoes:          {len(trades)}")

    if positions:
        p = positions[0]
        print("\n===== POSICAO =====")
        print(f"Ativo:       {p.symbol}")
        print(f"Quantidade:  {p.quantity:.8f}")
        print(f"Entrada:     {dinheiro(p.entry_price)}")
        print(f"Stop:        {dinheiro(p.stop_price)}")
        print(f"Alvo:        {dinheiro(p.target_price)}")
        print(f"Abertura:    {p.opened_at}")


def historico(trades):
    print("\n========== HISTORICO ==========")

    if not trades:
        print("Nenhuma operacao encerrada.")
        return

    for i, trade in enumerate(trades, start=1):
        resultado = "LUCRO" if trade.net >= 0 else "PREJUIZO"
        print(
            f"#{i} {trade.symbol} | "
            f"Entrada {dinheiro(trade.entry_price)} | "
            f"Saida {dinheiro(trade.exit_price)} | "
            f"{resultado}: {dinheiro(trade.net)}"
        )


def testar_sinal():
    anterior = ler_float("Preco anterior: ")
    if anterior is None:
        return

    atual = ler_float("Preco atual: ")
    if atual is None:
        return

    resultado, motivo = sinal(anterior, atual)
    print(f"\nSINAL: {resultado}")
    print(f"Motivo: {motivo}")


def configuracoes(cfg, positions, trades):
    print("\n========== CONFIGURACOES ==========")
    print(f"Capital inicial:    {dinheiro(cfg.capital_inicial)}")
    print(f"Capital atual:      {dinheiro(cfg.capital)}")
    print(f"% por operacao:     {pct(cfg.max_position_pct)}")
    print(f"Stop loss:          {pct(cfg.stop_loss_pct)}")
    print(f"Take profit:        {pct(cfg.take_profit_pct)}")
    print(f"Taxa:               {pct(cfg.fee_pct)}")
    print(f"Imposto estimado:   {pct(cfg.tax_rate_pct)}")
    print(f"Paper trading:      {cfg.paper_trading}")

    print("\nPressione ENTER para manter o valor atual.")

    def opcional_float(prompt, atual, minimo=0.0):
        entrada = input(f"{prompt} [{atual}]: ").strip().replace(",", ".")
        if not entrada:
            return atual
        try:
            valor = float(entrada)
            if valor < minimo:
                raise ValueError
            return valor
        except ValueError:
            print("Valor invalido. Mantido o atual.")
            return atual

    cfg.max_position_pct = opcional_float(
        "Percentual por operacao", cfg.max_position_pct
    )
    cfg.stop_loss_pct = opcional_float(
        "Stop loss (%)", cfg.stop_loss_pct
    )
    cfg.take_profit_pct = opcional_float(
        "Take profit (%)", cfg.take_profit_pct
    )
    cfg.fee_pct = opcional_float("Taxa (%)", cfg.fee_pct)
    cfg.tax_rate_pct = opcional_float(
        "Imposto estimado (%)", cfg.tax_rate_pct
    )

    salvar(cfg, positions, trades)
    print("Configuracoes salvas.")


def menu():
    cfg, positions, trades = carregar()

    while True:
        print("\n================================")
        print("          DOT TRADER V2")
        print("        PAPER TRADING")
        print("================================")
        print("1 - Testar sinal")
        print("2 - Abrir posicao")
        print("3 - Fechar posicao")
        print("4 - Ver carteira")
        print("5 - Historico")
        print("6 - Configuracoes")
        print("0 - Sair")
        print("================================")

        opcao = input("Escolha: ").strip()

        if opcao == "1":
            testar_sinal()
        elif opcao == "2":
            abrir_posicao(cfg, positions, trades)
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
    menu()
