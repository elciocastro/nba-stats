# nba-stats

Site privado de estatísticas da NBA. Contexto e decisões em `docs/decisoes/`. O que fazer a seguir: `docs/BACKLOG.md`.

## Comandos

- Instalar: `pip install -e ".[web,nbaapi,injury,dev]"`
- Testes: `pytest`
- Site: `streamlit run src/nbastats/web/app.py`
- Carga: `nbastats sync-season <ano>` / `nbastats sync-daily` / `nbastats atualizar` (a cada 15 min)
- Matchups: `nbastats matchup [--data AAAA-MM-DD]` / `nbastats backtest <ano>`

## Regras do projeto

- Ingestão só fala com a interface `DataSource` (`src/nbastats/sources/base.py`).
- Toda escrita no banco é upsert idempotente; mudança na ingestão vem com teste.
- Regra de negócio fica em `metrics/`, nunca em `web/`.
- Critérios de "potencial" vão em `config/potencial.yaml`, e os de matchup em
  `config/matchup.yaml`, não em código.
- Segredos só no `.env`. Dados (`data/`, `*.db`, `*.csv`) não vão para o Git.
- Commits e PRs sem co-author nem assinatura de IA.
