# nba-stats

Site privado de análise de props da NBA. Para cada jogo do dia e cada
mercado (pontos, rebotes, PRA, bolas de 3...), mostra a projeção de cada
jogador, a chance de passar da linha da casa e o histórico contra a linha.
A projeção considera a defesa adversária na posição, o ritmo, os desfalques
do injury report oficial e o risco de blowout.

```
nba_api / BALLDONTLIE ─┐
injury report (PDF) ───┼─> ingestão (upsert) ─> SQLite ─> métricas ─> site Streamlit / CLI
zonas de arremesso ────┘                                    ▲
                    config/matchup.yaml · config/projecao.yaml · config/potencial.yaml
```

## O que já faz

**Site** (`streamlit run src/nbastats/web/app.py`, tema escuro):

- **Props**: lista dinâmica do dia. Abas de mercado, chips dos jogos (com
  risco de blowout), janela L5/L10/L20/temporada, busca e ordenação. Cada
  jogador mostra foto, linha, projeção (verde acima da linha, vermelha
  abaixo), lado e chance, e as barras dos últimos jogos coloridas contra a
  linha. Ao tocar no jogador abre o detalhe: campo para a linha e as odds,
  chance de over/under, odd justa, valor esperado, gráfico dos últimos 20
  jogos, taxa de acerto por janela (casa, fora, contra o adversário), de
  onde vem a projeção, com e sem o companheiro desfalcado e zonas de
  arremesso.
- **Linhas**: tabela para digitar várias linhas e odds de uma vez.
- **Matchups (tabela)**: a mesma análise em tabela, com os critérios da
  anotação do colega (✓/✗) opcionais.
- **DvP**: ranking das 30 defesas por posição, temporada ou últimos 15 dias.
- **Ranking, Jogador, Potenciais, Jogo**: médias, ficha com gráfico, ranking
  de potencial configurável e box score.
- Botão **Atualizar agora**, que avisa quando a última atualização é recente.

**Análise** (método e números em `docs/decisoes/`):

| O quê | Como | Decisão |
|---|---|---|
| 18 mercados | pts, reb, ast, PRA, PR, PA, RA, 2FM/2FA, 3FM/3FA, FTM/FTA, roubos, tocos, turnovers, duplo e triplo-duplo | 0004 |
| DvP | quanto cada defesa cede por jogo à posição (G/F/C); rank 30 = cede mais | 0003 |
| Posição | PG/SG/SF/PF/C **estimada** pela altura e pelo perfil (nenhuma fonte grátis traz) | 0004 |
| Injury report | PDF oficial a cada 15 min; Out sai da lista, Doubtful/Questionable ficam marcados | 0004 |
| Projeção | taxa por minuto × minutos × DvP × ritmo × ajuste por desfalques; erra 2% a 4% menos que o L10 fora da amostra | 0005 |
| Blowout | margem esperada (saldo, mando, desfalques) e chance de decisão por 15+ | 0005 |
| Zonas | de onde o jogador arremessa × o que o adversário cede em cada zona | 0005 |
| Chance de over | binomial negativa ou normal por mercado, calibrada; quando prevê 40%, deu ~40% | 0006 |

## Instalação

Python 3.10+.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[web,nbaapi,injury,dev]"
cp .env.example .env      # NBASTATS_FONTE; senha do site; chave da BALLDONTLIE se usar
```

Fontes de dados:

- **nba_api** (padrão, grátis): lê o stats.nba.com. Funciona da sua casa/WSL,
  mas o site bloqueia IPs de nuvem, então não serve para rodar em servidor.
- **BALLDONTLIE** (paga): chave em [app.balldontlie.io](https://app.balldontlie.io).
  Estatísticas por jogador exigem o plano ALL-STAR. Não tem zonas de arremesso.
- **Injury report**: PDF oficial de official.nba.com (sem chave).

## Uso

Primeira carga e atualização:

```bash
nbastats sync-season 2025     # temporada 2025-26 (ano de início), com zonas
nbastats sync-season 2026     # temporada atual
nbastats atualizar            # recentes + agenda + injury report (+ zonas a cada 12 h)
nbastats atualizar --forcar   # refaz mesmo se a última tiver menos de 15 min
nbastats sync-daily           # últimos 3 dias + agenda de hoje e amanhã
nbastats lesoes               # só o injury report
```

Análise pela linha de comando:

```bash
nbastats matchup                      # jogos de hoje, pontos: projeção, DvP, desfalques
nbastats matchup --stat pra --data 2026-11-13   # data passada mostra o real
nbastats linha "Jamal Murray" pts 24.5 --over 1.90 --under 1.90
nbastats linha "Jamal Murray" pts     # sem valor: apaga
nbastats jogo GSW CHI [--data 2026-11-10]
nbastats ranking 2026 --stat reb
nbastats potencial 2026
```

Calibração (refazer de tempos em tempos, quando houver amostra):

```bash
nbastats calibrar 2025 --desde 2025-12-01 --validar 2026-02-15
nbastats backtest 2025 --desde 2025-12-01    # critérios da anotação (ver 0003)
```

`calibrar` mede o erro fora da amostra e regrava `config/projecao.yaml`.

### Atualização automática (cron no WSL)

```
0 11 * * *       cd /caminho/nba-stats && .venv/bin/nbastats sync-daily >> logs/sync.log 2>&1
*/15 10-23 * * * cd /caminho/nba-stats && .venv/bin/nbastats atualizar >> logs/sync.log 2>&1
```

Cada execução fica registrada na tabela `sync_log`.

## Estrutura

```
config/
  matchup.yaml             critérios do cruzamento, posições, lesões, mercados
  projecao.yaml            parâmetros da projeção (gerado por `nbastats calibrar`)
  potencial.yaml           regras do ranking de potencial
.streamlit/config.toml     tema do site
src/nbastats/
  sources/                 DataSource (contrato), nba_api, BALLDONTLIE, injury report
  ingest/                  carga idempotente (upsert) e atualização com intervalo mínimo
  db/                      conexão e schema.sql
  metrics/
    matchup.py             L5/L10, uso, DvP, ritmo, desfalques, posição estimada
    projecao.py            projeção, margem/blowout, com/sem, calibração
    linhas.py              linhas, chance de over/under, valor esperado, acerto
    zonas.py               zonas de arremesso e encaixe
    queries.py, potencial.py
  web/app.py, web/props.py site Streamlit (só apresentação)
  cli.py                   comando nbastats
tests/                     pytest com fontes falsas e respostas reais gravadas
docs/decisoes/             0001 a 0006: decisões, métodos e resultados
docs/BACKLOG.md            o que foi feito e o que falta, em fases
```

## Testes

```bash
pytest
```

## Limitações conhecidas

- Posição: as fontes só trazem G/F/C; PG/SG/SF/PF/C é estimado.
- Injury report guardado a partir de 14/11/2026; datas anteriores usam "não
  jogou a última partida".
- Zonas de arremesso são uma fotografia da temporada (sem histórico dia a
  dia), por isso ainda não foram validadas no teste retroativo.
- Sem linha da casa, a referência é o L10 arredondado, que favorece o under.
- Linhas são digitadas; a busca automática depende de escolher as casas
  (fase 3b do backlog).
- Fotos dos jogadores vêm do CDN da NBA (ids da nba_api); com a BALLDONTLIE
  os ids são outros e as fotos não aparecem.
- Login é uma senha única (`NBASTATS_PASSWORD`).
- O time do jogador é o mais recente informado pela API, não o da época de
  cada jogo (o box score usa o time correto da partida).
