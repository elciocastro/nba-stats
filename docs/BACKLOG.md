# Backlog do nba-stats

Atualizado em 2026-11-14. Ordem de cima para baixo = ordem sugerida.
Legenda: **[P0]** bloqueia o resto · **[P1]** necessário para o MVP ·
**[P2]** melhoria · **[?]** depende de decisão com o colega.

## Estado atual

Atualizado em 2026-11-14 (118 testes). Detalhes do que o site faz no README.

- **Dados**: nba_api validada contra o nba.com (seção 1); duas temporadas na
  base; agenda, injury report oficial (a cada 15 min) e zonas de arremesso.
- **Análise**: 18 mercados, DvP, posição estimada, projeção calibrada (2% a
  4% melhor que o L10), margem e risco de blowout, com/sem companheiro,
  chance de over/under calibrada contra a linha.
- **Site**: Props com tabela de calor no computador e cartões no celular,
  página do jogador (H2H, recortes, minutos), Comparar, Notícias, Apostas,
  Linhas, Matchups (tabela), DvP e as antigas. Protocolo BetânIAG e IA
  configurados e desligados por padrão.
- **Feito por PR**: #1 fonte nba_api · #2 matchups e DvP · #3 fase 1 (dados)
  · #4 fase 2 (projeção) · #5 fase 3 (linhas e visual) · #6 fase 4
  (apostas) · fase 5 (BetânIAG, H2H, computador) no PR seguinte.

**Próximo**: fase 3b (API de odds, depende das casas), validar as faixas do
selo com o registro de apostas (5i) e mostrar ao colega (2.1).

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

**Fase 2 — análise** (método e números em `docs/decisoes/0005-projecao.md`)
- [x] 2a. Projeção com número; fora da amostra erra 2% a 4% menos que o L10
  em todos os mercados. `nbastats calibrar` refaz a calibração.
- [x] 2b. Com e sem o companheiro desfalcado.
- [x] 2c. Margem esperada e risco de blowout pelos saldos, mando e desfalques.
- [x] 2d. Amostra pequena: temporada anterior vale 5 jogos; DvP encolhido
  pela amostra.
- [x] 2e. Zonas de arremesso e encaixe com o adversário (ainda sem validação
  retroativa: é uma fotografia da temporada).
- [ ] 2f. Recalibrar com a temporada 2026-27 a partir de dezembro.
- [ ] 2g. Guardar a fotografia das zonas por dia, para validar o encaixe.

**Fase 3 — linhas de aposta e visual** (ver `docs/decisoes/0006-linhas-e-visual.md`)
- [x] 3a. Linha e odds digitadas (detalhe do jogador, página Linhas ou
  `nbastats linha`); taxa de acerto (L5, L10, L20, temporada, casa, fora,
  contra o adversário); diferença para a projeção.
- [x] 3c. Chance de over/under calibrada por mercado (binomial negativa ou
  normal), odd justa e valor esperado.
- [x] 3d. Página Props dinâmica: tema escuro, abas de mercado, chips dos
  jogos, janela L5/L10/L20/temporada, foto, barras contra a linha, detalhe.
- [ ] 3b. API de odds gravando na tabela `lines`. **Pendente: quais casas**
  (o colega informa).

**Fase 4 — registro de apostas** (ver `docs/decisoes/0007-registro-de-apostas.md`)
- [x] 4a. Guardar aposta (jogador, mercado, linha, lado, odd, unidades, casa)
  com a fotografia do momento (chance, projeção, valor esperado).
- [x] 4b. Conferência automática depois do jogo (ganha, perdida, devolvida,
  anulada se não jogou), no `atualizar`, no botão do site e em `nbastats apostas`.
- [x] 4c. Página Apostas: acerto real x chance média, lucro, ROI, curva e
  desempenho por mercado, unidades, faixa de chance e lado.
- [ ] 4d. CLV (closing line value): guardar a linha de fechamento e comparar
  com a linha apostada. Depende da API de odds (3b).

**Fase 5 — Protocolo BetânIAG** (0008 e `docs/decisoes/0009-fase5-betaniag-desktop-h2h.md`)
- [x] 5a. Texto do protocolo recebido e analisado.
- [x] 5b. Respostas do colega (0009): paleta de cores, unidades em espera,
  IA configurada sem executar, sem banca, futebol/MMA preparados.
- [x] 5c. Chance do mercado sem a margem da casa e vantagem no checklist.
- [x] 5d. Selo BetânIAG na lista (cor e nível; unidade sugerida desligada).
- [x] 5e. Checklist do protocolo na página do jogador e selo de validação.
- [x] 5f. Página Comparar: jogador × jogador, time × time, tendências.
- [x] 5g. Relatório BetânIAG com IA e pergunta livre (desligado:
  `ia.habilitado`, `ANTHROPIC_API_KEY`, `pip install -e ".[ia]"`).
- [x] 5j. H2H em todas as temporadas; janelas temporada/H2H/L5/L10/L20/anterior.
- [x] 5k. Notícias: mudanças entre injury reports e quem pode voltar, com
  "PRA com X minutos".
- [x] 5m. Página inicial com destaques: jogos do dia, melhores
  oportunidades e jogadores em alta.
- [x] 5n. Cores nos valores (jogo a jogo e H2H) contra a média do jogador.
- [ ] 5i. Validar as faixas do selo e ligar a unidade sugerida quando o
  registro de apostas tiver amostra (dezenas de apostas por faixa).
- ~~5h. Gestão de banca~~: fora do escopo (o site é de estatística).
- [ ] 5l. Futebol e MMA: só quando houver fonte de dados (YAML pronto).

**Fase 6 — visual**
- [x] 6a. Primeira versão dinâmica (página Props, fase 3d).
- [x] 6b. Props no celular: cartões compactos, abas com rolagem lateral,
  filtros recolhidos, detalhe enxuto (conferido em 390 px e 1280 px).
- [ ] 6d. Acesso pelo celular: rede espelhada do WSL ou `portproxy` (passo a
  passo no README); senha obrigatória antes de abrir para a rede.
- [x] 6e. Computador: tabela de calor (temporada, H2H, L5, L10, L20,
  anterior, projeção, DvP), layout escolhido pelo navegador ou na barra
  lateral, página do jogador em duas colunas (conferido em 1280 e 390 px).
- [ ] 6c. **Trocar o front** (Streamlit limita interação: cada clique
  recarrega a página, sem hover, tabelas e gráficos pouco customizáveis).
  Proposta: API FastAPI sobre `metrics/` + front React, página a página
  (Início e Jogador primeiro). Aguardando decisão.

**Fase 7 — API + site novo** (pedido em 2026-11-14, com sugestões do Coni)
- [x] 7a. API FastAPI (`src/nbastats/api/`) sobre `metrics/`, sem regra nova:
  jogos do dia, props por mercado (com linhas), jogador (histórico, H2H,
  janelas, recortes, minutos), destaques, notícias, DvP, linhas (gravar),
  apostas, favoritos.
- [x] 7b. Front React (Vite + TypeScript, TanStack Table, gráficos
  interativos), servido pela própria API; Streamlit segue até cobrir tudo.
- [x] 7c. Início e Jogador primeiro.
- [x] 7d. **Props integrado** (Coni): Props, Linhas, Matchups, DvP, Jogador
  e Potenciais como abas de uma só área, com o mesmo jogo/mercado/filtro.
- [ ] 7e. **Ao Vivo**: jogos em andamento com placar e, por jogador, o
  parcial de pontos/rebotes/assistências/3 pts contra a média e a linha
  (ritmo atual → projeção do final); destaca quem está a caminho de bater.
  Fonte: placar ao vivo do nba_api (`live` endpoints), a validar.
- [x] 7f. **Favoritos**: jogadores, times e jogos (tabela `favorites`),
  filtro "só favoritos" e destaque no Início.
- [x] 7g. Docker com API + front num contêiner; `deploy/vps.sh` igual.

## 4. Métricas e análises — [P1] [?]

Dependem do item 2.3. Candidatas:

- [ ] **4.1 Médias por 36 minutos** (compara reservas com titulares).
- [ ] **4.2 Porcentagens de arremesso** (FG%, 3P%, FT%, TS%) nas tabelas.
- [x] **4.3 Comparar dois jogadores** lado a lado (página Comparar).
- [x] **4.4 Desempenho contra um adversário** (H2H na página do jogador).
- [x] **4.5 Casa e fora** (recortes na página do jogador).
- [ ] **4.6 Filtro de playoffs**: hoje as médias só usam temporada regular.
- [ ] **4.7 Métricas avançadas** (usage, PER, on/off). Exigem outros
  endpoints; só se o colega pedir.

## 5. Site — [P1]

- [x] **5.1 Busca de jogo por time e data**: chips dos jogos do dia na
  página Props (o box score ainda usa siglas).
- [ ] **5.2 Nomes de colunas legíveis** (hoje aparecem `pts_n`, `minutes`).
- [ ] **5.3 Exportar tabela em CSV**.
- [x] **5.4 Mostrar a data da última atualização** (do `sync_log`).
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
