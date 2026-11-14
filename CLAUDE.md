# nba-stats

Site privado de estatísticas da NBA. Contexto e decisões em `docs/decisoes/`.

## Comandos

- Instalar: `pip install -e ".[web,dev]"`
- Testes: `pytest`
- Site: `streamlit run src/nbastats/web/app.py`
- Carga: `nbastats sync-season <ano>` / `nbastats sync-daily`

## Regras do projeto

- Ingestão só fala com a interface `DataSource` (`src/nbastats/sources/base.py`).
- Toda escrita no banco é upsert idempotente; mudança na ingestão vem com teste.
- Regra de negócio fica em `metrics/`, nunca em `web/`.
- Critérios de "potencial" vão em `config/potencial.yaml`, não em código.
- Segredos só no `.env`. Dados (`data/`, `*.db`, `*.csv`) não vão para o Git.
- Commits e PRs sem co-author nem assinatura de IA.
