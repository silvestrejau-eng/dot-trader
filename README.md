# DOT Trader

Sistema de **Paper Trading** para acompanhamento de operações, carteira, taxas e impostos estimados.

> **Importante:** o projeto atualmente não envia ordens reais.

## Arquivos

- `dot_trader.py` — núcleo do paper trading.
- `dashboard.py` — painel web local.
- `dot_trader_data.json` — dados da carteira, criado automaticamente quando o programa é executado.

## Executar o trader

```bash
python dot_trader.py
```

## Executar o painel

```bash
python dashboard.py
```

Depois abra no navegador:

`http://localhost:8080`

O painel atualiza automaticamente a cada 15 segundos.

## Próximas etapas

1. Dados de mercado em tempo real.
2. Monitoramento de stop e alvo.
3. Sinais técnicos.
4. Gestão de risco.
5. Relatório de desempenho.
6. Interface otimizada para celular Android.

O projeto deve permanecer em Paper Trading até que todas as regras de risco e validações sejam testadas.
