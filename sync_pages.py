"""Sincroniza o estado local do DOT Trader com o arquivo usado pelo GitHub Pages.
Nao envia ordens. Apenas copia dot_trader_data.json para docs/dados.json.
"""
from pathlib import Path
import json

ORIGEM = Path("dot_trader_data.json")
DESTINO = Path("docs/dados.json")

def sincronizar():
    if not ORIGEM.exists():
        print("Nenhum dot_trader_data.json encontrado.")
        return 1

    data = json.loads(ORIGEM.read_text(encoding="utf-8"))
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Dados sincronizados: {DESTINO}")
    return 0

if __name__ == "__main__":
    raise SystemExit(sincronizar())
