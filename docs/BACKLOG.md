# Backlog do nba-stats

Atualizado em 2026-11-14. Ordem de cima para baixo = ordem sugerida.
Legenda: **[P0]** bloqueia o resto · **[P1]** necessário para o MVP ·
**[P2]** melhoria · **[?]** depende de decisão com o colega.

## Estado atual

Pronto e testado com dados simulados (26 testes):

- Duas fontes atrás da interface `DataSource`: `nba_api` (padrão, grátis) e BALLDONTLIE (paga)
- Ingestão idempotente em SQLite, com registro de cada execução em `sync_log`
- CLI: `sync-season`, `sync-daily`, `jogo`, `ranking`, `potencial`
- Site Streamlit: ranking, ficha do jogador, potenciais, box score; senha opcional
- Ranking de potencial configurável em `config/potencial.yaml`

**Nada rodou ainda contra uma API real.** Esse é o primeiro passo.

---

## 1. Validar a fonte de dados (no WSL) — [P0]

- [ ] **1.1 Instalar e rodar os testes**
  `pip install -e ".[web,nbaapi,dev]" && pytest`
- [ ] **1.2 Primeira carga pequena com nba_api**
  `nbastats sync-daily --days 7`. Pronto quando: `nbastats jogo GSW CHI` (ou
  outro confronto da semana) mostrar o placar e os jogadores batendo com o site
  da NBA.
- [ ] **1.3 Conferir os dados contra uma fonte oficial**
  Escolher 2 ou 3 jogos e comparar pontos, rebotes, assistências e minutos com
  o box score do nba.com. Atenção: jogo com prorrogação, jogador que não
  entrou (DNP) e jogo adiado.
- [ ] **1.4 Carga das duas temporadas**
  `nbastats sync-season 2025` e `nbastats sync-season 2026`. Medir o tempo e
  anotar aqui. Se o stats.nba.com der timeout, aumentar a pausa em
  `nba_api_source._default_fetcher` (hoje 0,7 s).
- [ ] **1.5 Se algo falhar**, o erro fica em `sync_log` (`status = 'error'`).
  Ajustar o mapeamento em `sources/nba_api_source.py` e criar um teste com a
  resposta real que quebrou.

## 2. Validar com o colega — [P0] [?]

- [ ] **2.1 Mostrar o site rodando** (`streamlit run src/nbastats/web/app.py`)
  e anotar o que ele usaria e o que falta.
- [ ] **2.2 Definir os critérios reais de "jogador em potencial"**
  Hoje os pesos em `config/potencial.yaml` são um chute. Pedir 3 a 5
  critérios concretos (ex.: "até 3 anos de liga, minutos subindo e +20% de
  rebotes nos últimos 10 jogos").
- [ ] **2.3 Listar as 3 perguntas que ele mais quer responder** com o site.
  Elas viram as próximas telas.
- [ ] **2.4 Decidir: seguir com nba_api ou assinar a BALLDONTLIE**
  Assinar quando: o site for para um servidor, ou o nba_api ficar instável,
  ou faltar dado que só a BALLDONTLIE tem. Ao trocar, recarregar o banco do
  zero (ver `docs/decisoes/0002-validar-com-nba-api.md`).

## 3. Dados — [P1]

- [ ] **3.1 Draft e posição com nba_api**
  O `LeagueGameLog` não traz. Buscar uma vez por jogador
  (`commonplayerinfo` ou `commonallplayers`) e gravar em `players`. Sem isso o
  filtro de anos de liga não funciona com nba_api.
- [ ] **3.2 Time do jogador por jogo**
  Hoje `players.team_id` é o time mais recente; quem foi trocado aparece no
  time novo em toda a temporada no ranking. Usar `player_game_stats.team_id`
  nas médias ou mostrar "GSW/CHI".
- [ ] **3.3 Conferência e divisão com nba_api** (vêm vazias). Tabela fixa
  dos 30 times resolve.
- [ ] **3.4 Atualização diária automática**
  Cron no WSL (exemplo no README). Verificar que o WSL está ligado no
  horário; se não, Agendador de Tarefas do Windows chamando `wsl -e`.
- [ ] **3.5 Alerta de falha da carga**
  Se o último `sync_log` for erro ou tiver mais de 36 h, avisar
  (e-mail, Telegram ou só um aviso no topo do site).
- [ ] **3.6 Backup do `data/nba.db`** (cópia diária; o arquivo é pequeno).

## 4. Métricas e análises — [P1] [?]

Dependem do item 2.3. Candidatas:

- [ ] **4.1 Médias por 36 minutos** (compara reservas com titulares).
- [ ] **4.2 Porcentagens de arremesso** (FG%, 3P%, FT%, TS%) nas tabelas.
- [ ] **4.3 Comparar dois jogadores** lado a lado.
- [ ] **4.4 Desempenho contra um adversário** (jogador X contra o time Y).
- [ ] **4.5 Casa e fora, e últimos N jogos por time**.
- [ ] **4.6 Filtro de playoffs**: hoje as médias só usam temporada regular.
- [ ] **4.7 Métricas avançadas** (usage, PER, on/off). Exigem outros
  endpoints; só se o colega pedir.

## 5. Site — [P1]

- [ ] **5.1 Busca de jogo por time e data** com lista dos jogos do dia, em
  vez de digitar as siglas.
- [ ] **5.2 Nomes de colunas legíveis** (hoje aparecem `pts_n`, `minutes`).
- [ ] **5.3 Exportar tabela em CSV**.
- [ ] **5.4 Mostrar a data da última atualização** (do `sync_log`).
- [ ] **5.5 Editar os critérios de potencial pelo site** (hoje é o YAML).
  Só depois que os critérios estabilizarem.

## 6. Colocar no ar — [P1]

Pré-requisito: item 2.4 decidido (no servidor, só BALLDONTLIE funciona).

- [ ] **6.1 Dockerfile** com o site e o job diário.
- [ ] **6.2 Onde hospedar**: uma VM pequena (o SQLite fica no disco) ou
  container com volume. Decidir e registrar em `docs/decisoes/`.
- [ ] **6.3 Acesso privado de verdade**: a senha única atual serve para
  teste. Para ir ao ar, colocar atrás de um proxy com autenticação
  (ex.: Cloudflare Access) ou criar login por usuário.
- [ ] **6.4 HTTPS e domínio** (pode usar o domínio do site pessoal).
- [ ] **6.5 CI no GitHub Actions** rodando `pytest` a cada PR.
- [ ] **6.6 Logs e monitoramento**: saúde do site e da carga diária.

## 7. Qualidade técnica — [P2]

- [ ] **7.1 Migrations do schema**: hoje `schema.sql` só cria tabelas.
  Quando mudar uma coluna, precisa de migração (Alembic ou script versionado).
- [ ] **7.2 Lint e formatação** (ruff) no CI.
- [ ] **7.3 Teste de contrato das fontes**: teste opcional (marcado, fora do
  CI) que chama a API real e confere os campos esperados.
- [ ] **7.4 Postgres** se houver escrita concorrente ou hospedagem sem disco
  persistente.

## Ideias para depois (fora do MVP)

- Dados ao vivo durante os jogos
- Histórico de várias temporadas e comparação entre épocas
- Modelo de previsão (ML) para "potencial"
- Acesso público
