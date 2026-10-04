"""Painel web local do DOT Trader com mercado ao vivo em Paper Trading."""

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import html
from datetime import datetime

from dot_trader import carregar, dinheiro, pct, fechar_posicao_preco
from market_data import ticker


HOST = "0.0.0.0"
PORT = 8080


def monitorar():
    cfg, positions, trades = carregar()
    market = None
    erro = None
    evento = None

    if positions:
        try:
            market = ticker(positions[0].symbol)
            p = positions[0]
            current = market["price"]

            if current <= p.stop_price:
                if fechar_posicao_preco(cfg, positions, trades, current, "stop"):
                    evento = f"STOP acionado em {dinheiro(current)}"
            elif current >= p.target_price:
                if fechar_posicao_preco(cfg, positions, trades, current, "alvo"):
                    evento = f"ALVO acionado em {dinheiro(current)}"
        except Exception as exc:
            erro = str(exc)

    if market is None and positions == []:
        return cfg, positions, trades, market, erro, evento

    if positions and market is None:
        try:
            market = ticker(positions[0].symbol)
        except Exception as exc:
            erro = str(exc)

    return cfg, positions, trades, market, erro, evento


def pagina():
    cfg, positions, trades, market, erro, evento = monitorar()

    lucro = sum(t.net for t in trades)
    taxas = sum(t.fees for t in trades)
    impostos = sum(t.estimated_tax for t in trades)
    aberto = sum(p.quantity * p.entry_price for p in positions)
    patrimonio = cfg.capital + aberto
    retorno = ((patrimonio / cfg.capital_inicial) - 1) * 100 if cfg.capital_inicial else 0

    market_html = "Sem posição para monitorar."
    if market and positions:
        p = positions[0]
        variacao = market["change_pct"]
        signal = "COMPRA" if variacao >= 0.50 else "VENDA/EVITAR" if variacao <= -0.50 else "HOLD"
        market_html = (
            f"<div class='price'>{dinheiro(market['price'])}</div>"
            f"<div>{html.escape(p.symbol)} | 24h: {variacao:+.2f}% | Sinal: <b>{signal}</b></div>"
            f"<div class='note'>Mín: {dinheiro(market['low'])} | Máx: {dinheiro(market['high'])}</div>"
        )

    if evento:
        market_html = f"<div class='event'>{html.escape(evento)}</div>" + market_html
    if erro:
        market_html += f"<div class='error'>Mercado: {html.escape(erro)}</div>"

    pos_html = "Nenhuma posição aberta."
    if positions:
        p = positions[0]
        pos_html = (
            f"<b>{html.escape(p.symbol)}</b> — {p.quantity:.8f} unidades<br>"
            f"Entrada: {dinheiro(p.entry_price)} | Stop: {dinheiro(p.stop_price)} | "
            f"Alvo: {dinheiro(p.target_price)}"
        )

    rows = ""
    for t in reversed(trades[-20:]):
        classe = "profit" if t.net >= 0 else "loss"
        rows += (
            f"<tr><td>{html.escape(t.symbol)}</td>"
            f"<td>{dinheiro(t.entry_price)}</td><td>{dinheiro(t.exit_price)}</td>"
            f"<td class='{classe}'>{dinheiro(t.net)}</td>"
            f"<td>{dinheiro(t.estimated_tax)}</td></tr>"
        )
    if not rows:
        rows = "<tr><td colspan='5'>Nenhuma operação encerrada.</td></tr>"

    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="10">
<title>DOT Trader</title>
<style>
body{{font-family:Arial,sans-serif;background:#0f1115;color:#eee;margin:0;padding:20px}}
h1{{margin:0}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}}
.card{{background:#191d24;border-radius:12px;padding:16px;margin-top:12px}}
.label,.note{{color:#9da5b4;font-size:13px}} .value,.price{{font-size:24px;font-weight:bold;margin-top:6px}}
table{{width:100%;border-collapse:collapse;margin-top:12px;background:#191d24}}
th,td{{padding:10px;text-align:left;border-bottom:1px solid #2a303a}}
.profit{{color:#54d68a}} .loss{{color:#ff6b6b}} .event{{padding:12px;background:#173d2a;border-radius:8px;margin-bottom:10px}}
.error{{padding:10px;background:#402020;border-radius:8px;margin-top:10px;color:#ff9b9b}}
</style></head>
<body>
<h1>DOT Trader</h1>
<div class="note">PAPER TRADING — mercado ao vivo, sem envio de ordens reais.</div>
<div class="note">Atualizado: {agora} | O painel verifica stop/alvo a cada 10 segundos.</div>

<div class="card"><div class="label">Mercado</div>{market_html}</div>

<div class="grid">
<div class="card"><div class="label">Capital disponível</div><div class="value">{dinheiro(cfg.capital)}</div></div>
<div class="card"><div class="label">Patrimônio</div><div class="value">{dinheiro(patrimonio)}</div></div>
<div class="card"><div class="label">Lucro líquido</div><div class="value">{dinheiro(lucro)}</div></div>
<div class="card"><div class="label">Retorno</div><div class="value">{pct(retorno)}</div></div>
<div class="card"><div class="label">Taxas</div><div class="value">{dinheiro(taxas)}</div></div>
<div class="card"><div class="label">Impostos estimados</div><div class="value">{dinheiro(impostos)}</div></div>
</div>

<div class="card"><h2>Posição atual</h2>{pos_html}</div>
<div class="card"><h2>Últimas operações</h2>
<table><tr><th>Ativo</th><th>Entrada</th><th>Saída</th><th>Líquido</th><th>Imposto</th></tr>{rows}</table>
</div>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if urlparse(self.path).path != "/":
            self.send_response(404); self.end_headers(); return
        body = pagina().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    print(f"DOT Trader disponível em http://localhost:{PORT}")
    print("Paper Trading ativo. Ctrl+C para encerrar.")
    HTTPServer((HOST, PORT), Handler).serve_forever()
