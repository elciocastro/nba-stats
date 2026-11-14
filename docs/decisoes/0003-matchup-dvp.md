# 0003 — Cruzamento de matchups (L5/L10 × DvP)

Data: 2026-11-14 · Status: em validação com o colega · Complementa a 0002

## Contexto

O colega mandou uma anotação com o método que usa para analisar mercados de
jogador: cruzar a fase recente do atleta (média dos últimos 5 e 10 jogos) com
a fragilidade da defesa adversária naquela posição (DvP, *defense vs.
position*), e filtrar por ritmo de jogo, risco de *blowout*, desfalques e
estilo. O pedido foi aplicar esse método aos dados da base e levar para a tela.

## Decisão

Implementar em `metrics/matchup.py`, com todos os limites em
`config/matchup.yaml`:

| Pilar da anotação | Como calculamos | Origem |
|---|---|---|
| L5 / L10 / temporada | média dos jogos com minuto > 0, só **antes** da data analisada | base |
| Minutos L5 × L10 | idem, critério `minutos` (queda máxima) | base |
| Taxa de uso | `100 · Σ(FGA + 0,44·FTA + TOV) / Σ(min · posses usadas do time / (min do time/5))` na janela | base |
| DvP temporada e recente | média por jogo do que a defesa cedeu ao grupo de posição; rank 1 a 30 (30 = cede mais); recente = últimos 15 dias | base |
| Ritmo (pace) | posses por 48 min, posses ≈ `FGA + 0,44·FTA − OREB + TOV` | base |
| Risco de blowout | **aproximação**: diferença entre o saldo médio dos dois times (não temos *spread*) | base |
| Desfalques | quem tem 25+ min no L10 e não jogou a última partida do time | base |
| Lesões confirmadas, *spread*, estilo (zona de arremesso, proteção de aro) | **não calculado**; exige outras fontes | — |

Cada critério vira ✓/✗ e a **nota** é quantos passaram. A análise de uma data
passada usa só os jogos anteriores, então o valor **real** aparece ao lado
para conferir o método (`nbastats backtest`).

### Posição

A nba_api (PlayerIndex) e a BALLDONTLIE só trazem **G, F e C** (com híbridos
como `G-F`), e não PG/SG/SF/PF/C. O DvP usa 3 grupos, e o mapa dos híbridos
fica no YAML. A "posição real" da anotação (onde o jogador passa os minutos)
precisaria de dados de escalação por posse, que não temos.

## Resultado do teste retroativo (2025-26, dez–abr, 1 dia a cada 3)

Pergunta: quem o método aponta supera a própria média L10 mais do que os outros?

| Pontos | n | real − L10 | % acima do L10 |
|---|---|---|---|
| DvP entre os 5 piores | 632 | **+0,76** | 53% |
| DvP no meio | 2788 | −0,11 | 46% |
| DvP entre os 5 melhores | 766 | **−0,76** | 44% |
| Nota "forte" (7–8 critérios) | 188 | +0,23 | 49% |
| Nota "bom" | 1850 | −0,15 | 47% |
| Nota "fraco" | 2148 | −0,07 | 46% |

Em rebotes e assistências o DvP aponta na mesma direção, mais fraco (±0,2).

**Leitura:** o DvP sozinho separa bem (cerca de 1,5 ponto entre as pontas).
A nota com todos os critérios, como estão hoje, quase não separa: os
critérios de "forma" (L5 ≥ L10) e "consistência" puxam para a média, como
esperado (fase quente costuma voltar para a média). Ficam como informação na
tela, mas o peso do julgamento deve ir para o DvP até o colega calibrar.

## Consequências

- `sync-daily` agora também grava a agenda de hoje e amanhã (jogos ainda sem
  placar), e cada carga busca o perfil dos jogadores (posição e draft) no
  PlayerIndex. Isso resolve o item 3.1 do backlog.
- O `boxscore` passou a ignorar jogos sem estatística (os agendados).
- Encontrado e corrigido durante o trabalho: em quadra neutra (México,
  Europa, Copa em Las Vegas) o LeagueGameLog marca os dois times com "@", e
  o jogo ficava sem mandante. Eram 6 jogos; teste criado com a resposta real.
- Calibrar com o colega: limites no YAML, se a nota deve ter pesos (hoje
  todos valem 1) e quais critérios saem. Cada ajuste se mede com
  `nbastats backtest 2025 --desde 2025-12-01`.
