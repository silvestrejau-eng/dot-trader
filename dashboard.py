"""
DOT Trader - painel web local.
Executa somente Paper Trading.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import html
import json

from dot_trader import carregar, dinheiro, pct, salvar, abrir_posicao, fechar_posicao


HOST = "0.0.0.0"
PORT = 8080


def resumo():
    cfg, positions, trades = carregar()

    lucro = sum(t.net for t in trades)
    taxas = sum(t.fees for t in trades)
    impostos = sum(t.estimated_tax for t in trades)
    aberto = sum(p.quantity * p.entry_price for p in positions)
    patrimonio = cfg.capital + aberto
    retorno = ((patrimonio / cfg.capital_inicial) - 1) * 100 if cfg.capital_inicial else 0

    return cfg, positions, trades, lucro, taxas, impostos, patrimonio, retorno


def pagina():
    cfg, positions, trades, lucro, taxas, impostos, patrimonio, retorno = resumo()

    pos_html = "Nenhuma posição aberta."
    if positions:
        p = positions[0]
        pos_html = (
            f"<b>{html.escape(p.symbol)}</b> — "
            f"{p.quantity:.8f} unidades<br>"
            f"Entrada: {dinheiro(p.entry_price)} | "
            f"Stop: {dinheiro(p.stop_price)} | "
            f"Alvo: {dinheiro(p.target_price)}"
        )

    rows = ""
    for t in reversed(trades[-20:]):
        classe = "profit" if t.net >= 0 else "loss"
        rows += (
            f"<tr><td>{html.escape(t.symbol)}</td>"
            f"<td>{dinheiro(t.entry_price)}</td>"
            f"<td>{dinheiro(t.exit_price)}</td>"
            f"<td class='{classe}'>{dinheiro(t.net)}</td>"
            f"<td>{dinheiro(t.estimated_tax)}</td></tr>"
        )

    if not rows:
        rows = "<tr><td colspan='5'>Nenhuma operação encerrada.</td></tr>"

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="15">
<title>DOT Trader</title>
<style>
body{{font-family:Arial,sans-serif;background:#0f1115;color:#eee;margin:0;padding:20px}}
h1{{margin-top:0}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}}
.card{{background:#191d24;border-radius:12px;padding:16px}}
.label{{color:#9da5b4;font-size:13px}} .value{{font-size:22px;font-weight:bold;margin-top:6px}}
table{{width:100%;border-collapse:collapse;margin-top:12px;background:#191d24}}
th,td{{padding:10px;text-align:left;border-bottom:1px solid #2a303a}}
.profit{{color:#54d68a}} .loss{{color:#ff6b6b}}
.note{{color:#9da5b4;margin:14px 0}}
</style>
</head>
<body>
<h1>DOT Trader</h1>
<div class="note">PAPER TRADING — nenhuma ordem real é enviada.</div>

<div class="grid">
<div class="card"><div class="label">Capital disponível</div><div class="value">{dinheiro(cfg.capital)}</div></div>
<div class="card"><div class="label">Patrimônio</div><div class="value">{dinheiro(patrimonio)}</div></div>
<div class="card"><div class="label">Lucro líquido</div><div class="value">{dinheiro(lucro)}</div></div>
<div class="card"><div class="label">Retorno</div><div class="value">{pct(retorno)}</div></div>
<div class="card"><div class="label">Taxas</div><div class="value">{dinheiro(taxas)}</div></div>
<div class="card"><div class="label">Impostos estimados</div><div class="value">{dinheiro(impostos)}</div></div>
</div>

<div class="card" style="margin-top:12px">
<h2>Posição atual</h2>
{pos_html}
</div>

<div class="card" style="margin-top:12px">
<h2>Últimas operações</h2>
<table>
<tr><th>Ativo</th><th>Entrada</th><th>Saída</th><th>Líquido</th><th>Imposto</th></tr>
{rows}
</table>
</div>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path != "/":
            self.send_response(404)
            self.end_headers()
            return

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
    print("Paper Trading ativo. Para encerrar, use Ctrl+C.")
    HTTPServer((HOST, PORT), Handler).serve_forever()
