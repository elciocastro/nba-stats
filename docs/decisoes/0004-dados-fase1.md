# 0004 — Fase 1: mercados, injury report, posições e atualização

Data: 2026-11-14 · Status: aceito · Complementa a 0003

## Contexto

Respostas do colega (14/11/2026) às perguntas da 0003:

- Posição: quer as 5 posições (armador, ala, pivô...).
- Mercados: pontos, rebotes, assistências, PRA, PR, PA, RA, duplo-duplo,
  triplo-duplo, FTM, FTA, 2FM, 2FA, 3FM, 3FA, roubos, tocos e turnovers.
- Lesões: usar o injury report oficial. Questionable e Doubtful "marcam
  mas não tiram".
- Análises ao longo do dia, mais cedo de preferência; atualizar a cada 15
  ou 30 min, com opção de atualizar na hora e aviso se já estiver em dia.
- Blowout: acontece quando um time vem completo e o outro desfalcado.

O plano completo está em fases no `docs/BACKLOG.md` (seção 3b).

## Decisões

**Mercados.** Todos calculados do box score que já temos: 2 pontos =
total − 3 pontos; combinados somados por jogo; duplo/triplo-duplo vale 1 ou
0 por jogo, então a "média" é a frequência.

**Injury report.** PDF oficial (official.nba.com), lido pela posição das
palavras na página (`sources/injury_report.py`, dependência `pdfplumber`).
Guardado por relatório (`injury_reports`, `injuries`), então dá para ver a
evolução ao longo do dia. Na análise vale o relatório mais recente que cobre
a data: **Out** sai da lista e entra nos desfalques; **Doubtful,
Questionable e Probable** ficam marcados. No relatório real de 14/11, os 59
nomes bateram com a base.

**5 posições.** Nenhuma fonte grátis traz PG/SG/SF/PF/C: nba_api e ESPN
trazem G/F/C, e o Basketball-Reference (que estima a posição jogada a
jogada) bloqueia acesso automático. Estimamos a partir da posição oficial,
da altura e do perfil (assistências e rebotes por 36 min), com limites no
YAML. No teste retroativo, o DvP com 5 posições **não separou melhor** que
com 3:

| Separação DvP (5 piores − 5 melhores) | G/F/C | 5 estimadas |
|---|---|---|
| Pontos | 1,52 | 1,36 |
| Rebotes | 0,43 | 0,27 |
| Assistências | 0,33 | 0,26 |
| 3FM | 0,13 | 0,20 |
| PRA | 1,93 | 2,14 |

O DvP fica em G/F/C (`posicao_modo: oficial`). A posição estimada aparece na
tela como informação. Trocar é uma linha no YAML.

**Atualização.** `nbastats atualizar` busca estatísticas dos últimos 2 dias,
agenda de hoje e amanhã e o injury report. Se a última atualização completa
tiver menos de 15 min, avisa e não refaz (`--forcar` refaz). O site tem o
botão "Atualizar agora" com a mesma regra. Cron sugerido no README.

## Consequências

- Datas anteriores a 14/11/2026 não têm injury report guardado; a análise
  usa "não jogou a última partida" como antes. O teste retroativo, portanto,
  não mede o efeito do injury report.
- O blowout pelos desfalques fica para a fase 2 (precisa medir o peso de
  cada jogador ausente).
