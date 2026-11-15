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

- **Início**: destaques do dia. Cartões dos jogos (favorito, blowout,
  ritmo, desfalques, maior chance), melhores oportunidades e jogadores em
  alta; tocar num jogador abre a página dele.
- **Props**: no computador, tabela de calor no estilo das planilhas de
  props (taxa de over na temporada, **H2H**, L5, L10, L20 e temporada
  anterior; projeção, diferença para a linha, chance, DvP e barras); no
  celular, cartões compactos. O layout segue o navegador ou a escolha em
  Preferências. Abas de mercado, chips dos jogos (com risco de blowout),
  janela e filtros.
- **Página do jogador** (clique na linha ou ›): linha e odds, chance de
  over/under, odd justa, valor esperado, **"e se jogar X minutos"**,
  gráfico grande com valor e adversário em cada barra, janelas e recortes
  (casa, fora, vitória, derrota, sem descanso), minutos e posses usadas,
  certas × tentadas, H2H de todas as temporadas, desfalques e com/sem o
  companheiro, de onde vem a projeção, zonas e **registrar aposta**.
- **Protocolo BetânIAG** (desligado; liga em Preferências ou no YAML): selo
  colorido por nível em cada jogador, checklist (chance, odd justa, mercado
  sem margem, vantagem, valor esperado, L5/L10/H2H, DvP, lesão, validação)
  e relatório com IA opcional.
- **Comparar**: jogador × jogador no mesmo mercado, time × time (ritmo,
  saldo, pontos feitos/cedidos, DvP por posição) e tendências (quem ganhou
  minutos e uso, defesas que pioraram).
- **Notícias**: o que mudou entre os dois últimos injury reports e quem
  pode voltar hoje, com a produção esperada para X minutos.
- **Apostas**: registro com conferência automática depois do jogo (ganha,
  perdida, devolvida, anulada se o jogador não entrou). Mostra acerto real
  contra a chance média calculada, lucro em unidades e em dinheiro, ROI,
  curva de lucro e desempenho por mercado, por unidades e por faixa de
  chance.
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
| Apostas | fotografia do momento (chance, projeção, valor esperado) e conferência automática | 0007 |
| BetânIAG | selo por chance e valor esperado, mercado sem margem, validação pelo injury report | 0008, 0009 |
| H2H | jogador contra o adversário em todas as temporadas da base (contexto) | 0009 |

## Instalação

Python 3.10+.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[web,nbaapi,injury,dev]"
cp .env.example .env      # NBASTATS_FONTE; senha do site; chave da BALLDONTLIE se usar
```

Relatório com IA (opcional, desligado): `pip install -e ".[ia]"`,
`ANTHROPIC_API_KEY` no `.env` e `ia.habilitado: true` em
`config/betaniag.yaml`. O modelo só escreve: recebe os números do site e
não pode inventar dados. Custa centavos por relatório.

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
nbastats apostar "Jamal Murray" pts over 24.5 --odd 1.90 --unidades 1 --casa X
nbastats apostas                      # confere resultados e mostra o desempenho
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

### Acessar pelo celular (mesma rede Wi-Fi)

O site roda dentro do WSL, que fica numa rede interna do Windows; por isso
o celular não alcança o endereço que o Streamlit mostra. Antes de abrir para
a rede, defina uma senha em `NBASTATS_PASSWORD` no `.env`.

Opção 1, Windows 11 (mais simples): rede espelhada do WSL. Crie
`%UserProfile%\.wslconfig` com:

```
[wsl2]
networkingMode=mirrored
```

No PowerShell (como administrador): `wsl --shutdown`, depois libere a porta
no firewall:

```
New-NetFirewallRule -DisplayName "nba-stats 8501" -Direction Inbound -LocalPort 8501 -Protocol TCP -Action Allow
```

Suba o site de novo e abra no celular `http://<IP do Windows>:8501`
(o IP aparece em `ipconfig`, no adaptador Wi-Fi).

Opção 2 (Windows 10 ou sem rede espelhada): redirecionar a porta. No WSL,
pegue o IP com `hostname -I`; no PowerShell como administrador:

```
netsh interface portproxy add v4tov4 listenport=8501 listenaddress=0.0.0.0 connectport=8501 connectaddress=<IP do WSL>
New-NetFirewallRule -DisplayName "nba-stats 8501" -Direction Inbound -LocalPort 8501 -Protocol TCP -Action Allow
```

O IP do WSL muda quando o Windows reinicia; aí refaça o `portproxy`.

Fora de casa: use uma VPN privada entre os seus aparelhos (ex.: Tailscale),
em vez de abrir a porta para a internet.

### Site novo (API + React), em migração

O site novo convive com o Streamlit até cobrir todas as páginas. Hoje:
Início (destaques e favoritos), Jogador (gráficos interativos, tabela jogo a
jogo ordenável e colorida, "e se jogar X minutos", linha da casa) e **Props
integrado**: abas Props, Linhas, Matchups, DvP e Potenciais com o mesmo dia,
mercado, jogos, busca e filtro de favoritos. **Favoritos** (★) em jogadores,
times e jogos, guardados no banco e compartilhados entre quem usa o site.

```bash
pip install -e ".[api]"
cd frontend && npm install && npm run build && cd ..
uvicorn nbastats.api.app:app --port 8100     # API + site em http://localhost:8100
# desenvolvimento do front com recarga: (cd frontend && npm run dev) -> :5173
```

API documentada em `/api/docs`. Com `NBASTATS_PASSWORD`, a API pede a senha
(cabeçalho `X-Senha`; o site pede na entrada).

### Subir numa VPS para testar (Docker)

```bash
nbastats atualizar                 # dados novos no data/nba.db local
deploy/vps.sh subir                # site novo (:8100) e antigo (:8501); gera a senha na 1ª vez
deploy/vps.sh dados                # só troca o banco e reinicia
deploy/vps.sh senha                # mostra a senha (fica só na VPS)
deploy/vps.sh desativar            # remove tudo da VPS
```

Padrão: `root@45.159.173.222` com a chave `~/.ssh/netsentinel-vps`, portas
8100 (novo) e 8501 (antigo; `PORTA_ANTIGO=` vazio não sobe o antigo). Na nuvem o "Atualizar agora"
não funciona (o stats.nba.com bloqueia IPs de servidor): os dados são os do
banco enviado. É HTTP sem cadeado: só para teste; para ficar no ar, usar um
subdomínio com HTTPS.

### Atualização automática (cron no WSL)

```
0 11 * * *       cd /caminho/nba-stats && .venv/bin/nbastats sync-daily >> logs/sync.log 2>&1
*/15 10-23 * * * cd /caminho/nba-stats && .venv/bin/nbastats atualizar >> logs/sync.log 2>&1
```

Cada execução fica registrada na tabela `sync_log`.

## Estrutura

```
config/
  apostas.yaml             valor da unidade, unidades oferecidas, regra de anulação
  betaniag.yaml            protocolo (liga/desliga, faixas e cores do selo, validação, IA, esportes)
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
    apostas.py             registro, conferência e desempenho das apostas
    historico.py           várias temporadas: H2H, janelas, recortes, minutos
    betaniag.py            selo, mercado sem margem, validação e checklist
    noticias.py            mudanças no injury report e retornos
    comparar.py            jogador x jogador, time x time, tendências
    destaques.py           página inicial: jogos, oportunidades, em alta
    queries.py, potencial.py
  web/app.py, inicio.py, props.py, comparar.py  site Streamlit (só apresentação)
  ia.py                    relatório BetânIAG com IA (opcional)
  cli.py                   comando nbastats
tests/                     pytest com fontes falsas e respostas reais gravadas
docs/decisoes/             0001 a 0009: decisões, métodos e resultados
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
