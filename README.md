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
- Chave da [BALLDONTLIE](https://app.balldontlie.io). Times e jogos
  funcionam no plano Free; estatísticas por jogador exigem o ALL-STAR.

## Instalação

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[web,dev]"
cp .env.example .env      # preencha BALLDONTLIE_API_KEY e BALLDONTLIE_RPM
```

## Uso

```bash
nbastats sync-season 2025     # temporada 2025-26 (ano de início)
nbastats sync-season 2026     # temporada atual
nbastats sync-daily           # últimos 3 dias; é o que vai no cron

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
  sources/                 DataSource (contrato) e cliente BALLDONTLIE
  ingest/                  carga idempotente no banco
  db/                      conexão e schema.sql
  metrics/                 consultas, tendência e nota de potencial
  web/app.py               site Streamlit
  cli.py                   comando nbastats
tests/                     pytest com fonte de dados falsa
docs/decisoes/             registro das decisões de arquitetura
```

## Testes

```bash
pytest
```

## Limitações conhecidas

- A ingestão contra a API real ainda não foi executada: os testes usam uma
  fonte falsa no formato documentado da BALLDONTLIE.
- Médias e ranking consideram só temporada regular.
- Login é uma senha única (`NBASTATS_PASSWORD`).
- O time do jogador é o mais recente informado pela API, não o da época de
  cada jogo (o box score usa o time correto da partida).
