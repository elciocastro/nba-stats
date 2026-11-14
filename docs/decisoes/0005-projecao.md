# 0005 — Fase 2: projeção com número, desfalques, blowout e zonas

Data: 2026-11-14 · Status: aceito · Complementa a 0003 e a 0004

## Contexto

A 0003 mostrou que a nota por critérios (✓/✗) quase não separa quem vai
render acima da média. O DvP sozinho separa, mas não diz "quanto". A fase 2
troca a nota por uma **projeção com número** para cada mercado, mede o erro
contra o simples L10 e incorpora desfalques, blowout e zonas de arremesso.

## Como calibramos

Para cada jogador em cada jogo de 2025-26 (desde dezembro), montamos o que
se sabia **antes** do jogo e o resultado real (`build_dataset`). Os
parâmetros foram escolhidos de dezembro a meados de fevereiro e medidos de
meados de fevereiro a abril (fora da amostra). O comando
`nbastats calibrar <ano> --validar <data>` refaz isso; ele regrava
`config/projecao.yaml`.

## Decisões

**Projeção** (`metrics/projecao.py`):

```
taxa por minuto  = L10 × 1 + temporada × 3          (L5 não ajudou)
                   + temporada anterior valendo 5 jogos, no começo da temporada
minutos          = L5 × 2 + L10 × 1 + temporada × 1
projeção         = taxa × minutos × fator DvP × fator ritmo × (nível + ausência × fração fora)
```

- **Fator DvP** = 1 + amostra × (cedido / média da liga − 1), com amostra =
  jogos / (jogos + 80). O DvP oscila muito de jogo para jogo; sem esse
  encolhimento ele piora a projeção.
- **Ritmo**: efeito quase nulo; ficou com peso 0,5.
- **Nível** (0,85 a 0,97, por mercado): a projeção crua superestima, porque
  quem está jogando 20+ minutos tende a vir de uma boa fase e depois volta
  para a média.
- **Ausência**: fração da produção recente (PRA no L10) do time que está
  fora, contando só ausências **novas** (quem jogou algum dos 3 últimos
  jogos). Quem está fora há semanas já está no L10 dos companheiros. Com 30%
  ou mais da produção fora, o jogador que fica fez em média +2,2 pontos e
  jogou 8% mais minutos que no L10.
- Fonte das ausências: injury report (Out e Doubtful); sem relatório, o box
  score do jogo se ele já aconteceu; senão, quem não jogou a última partida.

**Resultado fora da amostra** (2.679 jogador-jogo, de 15/02 a abril de 2026):

| Mercado | Erro do L10 | Erro da projeção | Ganho |
|---|---|---|---|
| Pontos | 5,35 | 5,22 | 2,4% |
| Rebotes | 2,08 | 2,01 | 3,3% |
| Assistências | 1,62 | 1,58 | 2,5% |
| PRA | 6,73 | 6,58 | 2,2% |
| 2FM | 1,62 | 1,57 | 3,5% |
| 3FM | 1,05 | 1,02 | 2,6% |
| FTM | 1,64 | 1,59 | 3,4% |
| Roubos / tocos | 0,83 / 0,60 | 0,80 / 0,58 | 3,6% / 3,7% |

Todos os 18 mercados melhoram de 2% a 4% (duplo e triplo-duplo um pouco
mais, por serem raros). É um ganho pequeno e consistente: o resultado de um
jogo tem muito ruído, e nenhuma fórmula o elimina. O "erro típico" de cada
mercado aparece na tela.

**Margem esperada e blowout**:
`margem = 0,83 × (saldo do time − saldo do adversário) + 2,1 (mando)
− 0,12 × PRA ausente do time + 0,12 × PRA ausente do adversário`.
A chance de o jogo terminar decidido por 15+ vem de uma regressão logística
sobre a margem esperada: cerca de 30% quando a margem esperada é pequena e
60% quando passa de 15. Os titulares jogaram de 12% a 15% menos minutos nos
jogos decididos por 20+, mas a margem **esperada** quase não prevê isso
(−3%), então a projeção não desconta minutos por blowout. O risco aparece
como informação.

**Com e sem o companheiro**: para os desfalques do dia, a média do jogador
nos jogos da temporada sem e com cada um. É informação para o julgamento,
com o número de jogos ao lado, porque a amostra costuma ser pequena.

**Zonas de arremesso** (`metrics/zonas.py`, LeagueDash*ShotLocations): de
onde o jogador arremessa (aro, garrafão, meia distância, 3 da zona morta,
3 de frente) e o aproveitamento que o adversário cede em cada zona. O
**encaixe** é o aproveitamento cedido acima da liga, ponderado pelas zonas
do jogador. Em 3FM/3FA conta só as zonas de 3 e em 2FM/2FA só as de 2. É
uma fotografia da temporada até a última carga, então **não foi validado**
no teste retroativo; fica como informação até termos histórico.

## Consequências

- A tela de Matchups passa a ordenar pela projeção contra o L10. Os
  critérios ✓/✗ da anotação ficam atrás de uma opção.
- Recalibrar de tempos em tempos (`nbastats calibrar 2026 --desde ...`)
  quando a temporada atual tiver amostra (a partir de dezembro).
- Para comparar com a **linha da casa** (fase 3), o erro típico por mercado
  é o ponto de partida da probabilidade de over/under.
