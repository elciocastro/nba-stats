# nba-stats

Base de dados e site privado de estatísticas da NBA: médias, tendência
recente, box score por jogo, cruzamento de matchups (L5/L10 × defesa por
posição) e um ranking configurável de jogadores em potencial.

```
BALLDONTLIE API ──> ingestão (upsert) ──> SQLite ──> métricas ──> CLI / site Streamlit
                                                        ▲
                                 config/potencial.yaml, config/matchup.yaml
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
pip install -e ".[web,nbaapi,injury,dev]"
cp .env.example .env      # escolha NBASTATS_FONTE; para balldontlie, a chave
```

## Uso

```bash
nbastats sync-season 2025     # temporada 2025-26 (ano de início)
nbastats sync-season 2026     # temporada atual
nbastats sync-daily           # últimos 3 dias + agenda de hoje e amanhã; vai no cron
nbastats sync-agenda          # só a agenda (jogos ainda não disputados)
nbastats lesoes               # só o injury report oficial mais recente
nbastats atualizar            # recentes + agenda + injury report; pula se < 15 min
nbastats atualizar --forcar   # refaz mesmo assim
nbastats --fonte balldontlie sync-season 2026   # força uma fonte

nbastats jogo GSW CHI                 # box score do confronto mais recente
nbastats jogo GSW CHI --data 2026-11-10
nbastats ranking 2026 --stat reb
nbastats potencial 2026

nbastats matchup                      # jogos de hoje: L5/L10 x DvP, pontos
nbastats matchup --data 2026-11-13 --stat reb   # data passada mostra o real
nbastats matchup --stat pra           # mercados: pts reb ast pra pr pa ra fg2m fg2a
                                      # fg3m fg3a ftm fta stl blk turnover dd td
nbastats backtest 2025 --desde 2025-12-01       # o método acerta? (ver 0003)

streamlit run src/nbastats/web/app.py
```

Atualização pelo cron: a carga diária às 11h (depois dos jogos da noite
anterior) e o injury report a cada 15 minutos, das 10h às 23h:

```
0 11 * * *       cd /caminho/nba-stats && .venv/bin/nbastats sync-daily >> logs/sync.log 2>&1
*/15 10-23 * * * cd /caminho/nba-stats && .venv/bin/nbastats atualizar >> logs/sync.log 2>&1
```

No site, o botão "Atualizar agora" faz o mesmo que `nbastats atualizar` e
avisa quando a última atualização é recente.

Cada execução fica registrada na tabela `sync_log`.

## Estrutura

```
config/potencial.yaml      regras do ranking de potencial
config/matchup.yaml        critérios do cruzamento de matchups, posições e lesões
src/nbastats/
  sources/                 DataSource (contrato), nba_api, BALLDONTLIE e injury report
  ingest/                  carga idempotente no banco
  db/                      conexão e schema.sql
  metrics/                 consultas, tendência, potencial e matchups
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

- Posição: as fontes só trazem G/F/C. PG/SG/SF/PF/C é estimado pela altura
  e pelo perfil (`config/matchup.yaml`).
- O injury report é guardado a partir de quando o projeto começou a buscá-lo
  (14/11/2026); datas anteriores usam "não jogou a última partida".
- Médias e ranking consideram só temporada regular.
- Login é uma senha única (`NBASTATS_PASSWORD`).
- O time do jogador é o mais recente informado pela API, não o da época de
  cada jogo (o box score usa o time correto da partida).
