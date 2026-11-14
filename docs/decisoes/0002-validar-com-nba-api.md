# 0002 — Validar com nba_api antes de pagar a BALLDONTLIE

Data: 2026-11-14 · Status: aceito · Complementa a 0001

## Contexto

A 0001 escolheu a BALLDONTLIE (paga) como fonte. Antes de assinar, queremos
confirmar que os dados e as análises atendem ao que o colega precisa.

## Decisão

- Adicionar o `nba_api` (gratuito, lê o stats.nba.com) como segunda fonte,
  atrás da mesma interface `DataSource`. Ele vira o padrão enquanto o projeto
  roda no WSL.
- A escolha é por configuração: `NBASTATS_FONTE=nba_api|balldontlie` ou
  `nbastats --fonte ...`. Ingestão, banco, métricas e site não mudam.
- Quando o site for para um servidor, migrar para a BALLDONTLIE: o
  stats.nba.com bloqueia IPs de nuvem.

## Consequências

- Com `nba_api` não há draft, posição nem conferência. O filtro
  `max_anos_de_liga` do ranking de potencial não tem efeito.
- Os IDs de jogo e de jogador das duas fontes são diferentes. **Não misturar
  as duas fontes no mesmo banco:** ao trocar, apagar `data/nba.db` e fazer a
  carga de novo (ou usar `NBASTATS_DB` com outro arquivo).
