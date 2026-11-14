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

**Seção 1 concluída em 2026-11-14**: nba_api validada contra o nba.com, duas
temporadas carregadas. Próximo passo: seção 2.

---

## 1. Validar a fonte de dados (no WSL) — [P0]

- [x] **1.1 Instalar e rodar os testes**
  `pip install -e ".[web,nbaapi,dev]" && pytest`
  *Feito em 2026-11-14:* 26 testes passando.
- [x] **1.2 Primeira carga pequena com nba_api**
  `nbastats sync-daily --days 7`. Pronto quando: `nbastats jogo GSW CHI` (ou
  outro confronto da semana) mostrar o placar e os jogadores batendo com o site
  da NBA.
  *Feito em 2026-11-14:* 51 jogos e 1145 linhas em ~5 s (07/11 a 14/11),
  `sync_log` com `status = 'ok'`. Conferido `nbastats jogo SAS GSW`
  (13/11, GSW 85 @ SAS 123): a soma dos pontos bate com o placar dos dois
  times, os minutos somam 240 e o +/- soma −190 (5 × −38). Observações para
  o 1.3: os minutos vêm inteiros e jogadores DNP não aparecem.
- [x] **1.3 Conferir os dados contra uma fonte oficial**
  Escolher 2 ou 3 jogos e comparar pontos, rebotes, assistências e minutos com
  o box score do nba.com. Atenção: jogo com prorrogação, jogador que não
  entrou (DNP) e jogo adiado.
  *Feito em 2026-11-14:* comparados com o `BoxScoreTraditionalV3` (o box
  score da página do jogo no nba.com) WAS 140 × DET 144 (12/11, duas
  prorrogações, 290 min), IND 106 × NYK 104 e ORL 107 × MIL 99 (13/11).
  Placar, pontos, rebotes e assistências de todos os jogadores idênticos;
  minutos batem, mas gravados inteiros (perde os segundos). DNP: não entram
  na base (18 nos 3 jogos), o que é o certo para as médias. Adiado: o
  `LeagueGameLog` só traz jogo disputado, então não há registro a corrigir;
  todos os 1498 jogos estão `Final`.
- [x] **1.4 Carga das duas temporadas**
  `nbastats sync-season 2025` e `nbastats sync-season 2026`. Medir o tempo e
  anotar aqui. Se o stats.nba.com der timeout, aumentar a pausa em
  `nba_api_source._default_fetcher` (hoje 0,7 s).
  *Feito em 2026-11-14:* 2025 → 1315 jogos e 28 572 linhas em 6,4 s;
  2026 → 183 jogos e 4126 linhas em 4,5 s. Sem timeout; a pausa ficou como
  está.
- [x] **1.5 Se algo falhar**, o erro fica em `sync_log` (`status = 'error'`).
  Ajustar o mapeamento em `sources/nba_api_source.py` e criar um teste com a
  resposta real que quebrou.
  *2026-11-14:* nenhuma falha; `sync_log` sem nenhum `status = 'error'`.

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

- [x] **3.1 Draft e posição com nba_api**
  O `LeagueGameLog` não traz. Buscar uma vez por jogador
  (`commonplayerinfo` ou `commonallplayers`) e gravar em `players`. Sem isso o
  filtro de anos de liga não funciona com nba_api.
  *Feito em 2026-11-14:* `PlayerIndex`, uma chamada por carga. Posição só em
  G/F/C (ver `docs/decisoes/0003-matchup-dvp.md`).
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

## 3b. Matchups (L5/L10 × DvP) — [P0]

Pedido do colega em 2026-11-14. Método em `docs/decisoes/0003-matchup-dvp.md`
e `0004-dados-fase1.md`. Uma fase por PR.

**Fase 0 — base (PR #2, feito)**: L5/L10, uso, DvP temporada e 15 dias,
ritmo, saldo, desfalques, nota por critério, agenda, telas Matchups e DvP,
`nbastats matchup` e `backtest`.

**Fase 1 — dados**
- [x] 1a. Mercados: PRA, PR, PA, RA, 2FM/2FA, 3FM/3FA, FTM/FTA, roubos,
  tocos, turnovers, duplo e triplo-duplo.
- [x] 1b. Injury report oficial: Out sai da lista; Doubtful, Questionable e
  Probable ficam marcados; desfalques do relatório.
- [x] 1c. 5 posições estimadas (o DvP segue G/F/C; ver 0004).
- [x] 1d. `nbastats atualizar` com intervalo mínimo e botão "Atualizar agora".
- [ ] 1e. Instalar o cron a cada 15 min no WSL (exemplo no README).

**Fase 2 — análise**
- [ ] 2a. Projeção com número (média recente × fator DvP × ritmo × minutos)
  no lugar da nota; teste retroativo mede o erro contra o L10.
- [ ] 2b. Com e sem o companheiro: rendimento nos jogos em que o desfalque
  do dia ficou fora.
- [ ] 2c. Blowout pelos desfalques: peso de cada ausente (minutos, saldo com
  e sem ele) e diferença esperada.
- [ ] 2d. Amostra pequena: misturar DvP e médias com a temporada anterior
  no começo da temporada.
- [ ] 2e. Zonas de arremesso: de onde o jogador arremessa e onde o
  adversário cede (`LeagueDashTeamShotLocations`).

**Fase 3 — linhas de aposta**
- [ ] 3a. Linha digitada no site; taxa de acerto (L5, L10, temporada, casa e
  fora, contra o adversário) e diferença para a projeção.
- [ ] 3b. API de odds. **Pendente: quais casas** (o colega informa).

**Fase 4 — registro de apostas**
- [ ] 4a. Guardar aposta (jogador, mercado, linha, over/under, odd) e
  conferir o resultado sozinho; acompanhamento de acerto e retorno.

**Fase 5 — Protocolo BetânIAG**
- [ ] 5a. Assistente no site: escolher jogo, jogador ou time e pedir a
  análise do protocolo sobre os dados da base. **Pendente: texto do
  protocolo** (o usuário envia quando chegarmos aqui).

**Fase 6 — visual**
- [ ] 6a. Redesenhar as telas em torno do fluxo de análise, depois das
  fases 2 a 5.

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
