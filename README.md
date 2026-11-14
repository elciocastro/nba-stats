# nba-stats

Base de dados e site privado de estatísticas da NBA: médias, tendência
recente, box score por jogo e um ranking configurável de jogadores em
potencial.

```
BALLDONTLIE API ──> ingestão (upsert) ──> SQLite ──> métricas ──> CLI / site Streamlit
                                                        ▲
                                           config/potencial.yaml
```

## Pré-requisitos

- Python 3.10+
- Uma das fontes de dados:
  - **nba_api** (padrão, grátis): lê o stats.nba.com. Funciona da sua casa/WSL,
    mas o site bloqueia IPs de nuvem, então não serve para rodar em servidor.
  - **BALLDONTLIE** (paga): chave em [app.balldontlie.io](https://app.balldontlie.io).
    Estatísticas por jogador exigem o plano ALL-STAR.

## Instalação

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[web,nbaapi,dev]"
cp .env.example .env      # escolha NBASTATS_FONTE; para balldontlie, a chave
```

## Uso

```bash
nbastats sync-season 2025     # temporada 2025-26 (ano de início)
nbastats sync-season 2026     # temporada atual
nbastats sync-daily           # últimos 3 dias; é o que vai no cron
nbastats --fonte balldontlie sync-season 2026   # força uma fonte

nbastats jogo GSW CHI                 # box score do confronto mais recente
nbastats jogo GSW CHI --data 2026-11-10
nbastats ranking 2026 --stat reb
nbastats potencial 2026

streamlit run src/nbastats/web/app.py
```

Atualização diária pelo cron (11h, depois dos jogos da noite anterior):

```
0 11 * * * cd /caminho/nba-stats && .venv/bin/nbastats sync-daily >> logs/sync.log 2>&1
```

Cada execução fica registrada na tabela `sync_log`.

## Estrutura

```
config/potencial.yaml      regras do ranking de potencial
src/nbastats/
  sources/                 DataSource (contrato), nba_api e BALLDONTLIE
  ingest/                  carga idempotente no banco
  db/                      conexão e schema.sql
  metrics/                 consultas, tendência e nota de potencial
  web/app.py               site Streamlit
  cli.py                   comando nbastats
tests/                     pytest com fonte de dados falsa
docs/decisoes/             registro das decisões de arquitetura
```

## Backlog

Tarefas, pendências e melhorias em [`docs/BACKLOG.md`](docs/BACKLOG.md).

## Testes

```bash
pytest
```

## Limitações conhecidas

- A ingestão contra as APIs reais ainda não foi executada: os testes usam
  respostas simuladas no formato documentado de cada fonte.
- Com nba_api não há draft nem posição, então o filtro de anos de liga do
  ranking de potencial não tem efeito.
- Médias e ranking consideram só temporada regular.
- Login é uma senha única (`NBASTATS_PASSWORD`).
- O time do jogador é o mais recente informado pela API, não o da época de
  cada jogo (o box score usa o time correto da partida).
