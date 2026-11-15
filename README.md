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
o celular não alcança `localhost`. **Antes de abrir para a rede, crie os
usuários** (Administração ou `nbastats usuario criar`): com usuários, todo
acesso pede login.

Suba a API ouvindo em todas as interfaces:

```bash
uvicorn nbastats.api.app:app --host 0.0.0.0 --port 8100
```

Opção 1, Windows 11 (mais simples): rede espelhada do WSL. Crie
`%UserProfile%\.wslconfig` com:

```
[wsl2]
networkingMode=mirrored
```

No PowerShell (como administrador): `wsl --shutdown` e libere a porta no
firewall do Windows e no do WSL (Hyper-V):

```
New-NetFirewallRule -DisplayName "nba-stats 8100" -Direction Inbound -LocalPort 8100 -Protocol TCP -Action Allow
New-NetFirewallHyperVRule -Name nbastats -DisplayName "nba-stats 8100" -Direction Inbound -VMCreatorId '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -Protocol TCP -LocalPorts 8100
```

Abra no celular `http://<IP do Windows>:8100` (o IP aparece em `ipconfig`,
no adaptador Wi-Fi) e use "Adicionar à tela inicial" para virar app.

Opção 2 (Windows 10 ou sem rede espelhada): redirecionar a porta. No WSL,
pegue o IP com `hostname -I`; no PowerShell como administrador:

```
netsh interface portproxy add v4tov4 listenport=8100 listenaddress=0.0.0.0 connectport=8100 connectaddress=<IP do WSL>
New-NetFirewallRule -DisplayName "nba-stats 8100" -Direction Inbound -LocalPort 8100 -Protocol TCP -Action Allow
```

O IP do WSL muda quando o Windows reinicia; aí refaça o `portproxy`
(`netsh interface portproxy show all` lista o que está ativo). Para o
Streamlit antigo, troque 8100 por 8501.

Fora de casa: use uma VPN privada entre os seus aparelhos (ex.: Tailscale),
em vez de abrir a porta para a internet. O login é por HTTP simples; na
rede de casa serve, na internet precisa de HTTPS (6.4 do backlog).

### Site novo (API + React), em migração

O site novo convive com o Streamlit até cobrir todas as páginas. Hoje:
Início (destaques e favoritos), Jogador (gráficos interativos, tabela jogo a
jogo ordenável e colorida, "e se jogar X minutos", linha da casa) e **Props
integrado**: abas Props, Linhas, Matchups, DvP e Potenciais com o mesmo dia,
mercado, jogos, busca e filtro de favoritos. **Favoritos** (★) em jogadores,
times e jogos, guardados no banco e separados por usuário (no primeiro acesso\ncada um recebe uma cópia da lista que existia antes dos logins).
**Ao Vivo**: placar dos jogos e, por jogador, o parcial em pontos, rebotes,
assistências, bolas de 3 ou PRA contra a linha (ou a média), a projeção do
final no ritmo atual e a chance de bater; atualiza a cada 30 s.
**Apostas** (registro, conferência, acerto real × chance calculada, lucro,
ROI e desempenho por mercado/unidades/faixa de chance; registra-se pela página
do jogador), **Comparar** (jogador × jogador, time × time, tendências) e
**Lesões** (efeito cascata, o que mudou no injury report e quem pode voltar). O botão
"Atualizar dados" no topo faz a mesma carga do `nbastats atualizar`. Só no
**Ranking** (temporada, últimos N, diferença, por 36 minutos, playoffs,
arremesso) e **Jogos** (box score completo). O Streamlit ainda
sobe, mas tudo já existe no site novo.

```bash
pip install -e ".[api]"
cd frontend && npm install && npm run build && cd ..
uvicorn nbastats.api.app:app --port 8100     # API + site em http://localhost:8100
# desenvolvimento do front com recarga: (cd frontend && npm run dev) -> :5173
```

API documentada em `/api/docs`.

### Página inicial

Abre na hora com a liga: última rodada (placar e cestinhas), destaques pelo
Game Score, classificação, líderes, manchetes da ESPN e transações da NBA em
português. As projeções do dia ("Hoje") carregam à parte. Manchetes e
transações vêm junto do `nbastats atualizar`; para buscar só elas:
`nbastats noticias`. Clicar num jogador que não joga na data (Ranking,
transações, líderes) abre o perfil dele, sem projeção, com o próximo jogo.

### Calibração, cascata, alertas e app no celular

- **Conferência das estatísticas** (menu da conta ou "Mais"): "quando o site disse X%, acertou quanto?", com o
  backtest da temporada (`nbastats calibracao`, diário no cron), as previsões
  guardadas antes de cada jogo (`nbastats previsoes`, de hora em hora) e as
  apostas registradas.
- **Lesões → Efeito cascata**: quem ganha com cada desfalque do dia (média
  com/sem o companheiro e projeção contra a linha).
- **Apostas**: motivo (etiquetas) e nota em cada aposta, desempenho por
  motivo, "Minhas/Todas" com login e **jogo responsável** (limites por dia e
  por 7 dias e aviso de derrotas seguidas, em `config/apostas.yaml`).
- **Props**: chance mínima, lado, só linha da casa, sem dúvida de lesão e
  **Meus filtros** (salvos por usuário). Ranking e jogador: **sem lavadas**.
- **Telegram** (desligado): crie um bot no @BotFather, ponha
  `NBASTATS_TELEGRAM_TOKEN` e `NBASTATS_TELEGRAM_CHAT` no `.env` e
  `habilitado: true` em `config/alertas.yaml`. O cron manda alertas dos
  favoritos (lesão, linha com valor) a cada 15 min e o resumo às 17h. Teste
  sem enviar: `nbastats resumo --simular` / `nbastats alertas --simular`.
  Durante os jogos (até 2h) também avisa quando um favorito está **a caminho
  de bater** (chance ≥ 70% no ritmo atual, `ao_vivo_chance_min`) e quando
  **bateu** a linha.
- **CSV**: Props, Apostas e Ranking exportam a tabela filtrada.
- **Playoffs**: a página do jogador tem a janela "PO" (jogos de playoffs).
- **App no celular**: no Chrome/Safari, "Adicionar à tela inicial" (PWA).

### Configurações e identidade

- **Administração → Configurações**: os parâmetros dos YAML (projeção, BetânIAG,
  jogo responsável, alertas, matchup, potencial e a identidade do site) com
  descrição, tipo e o valor padrão. O que muda pelo site vai para
  `data/ajustes/<arquivo>.yaml` (fora do Git) e vale por cima do YAML;
  "Restaurar" volta ao padrão. `nbastats calibrar` ignora os ajustes e regrava
  só o YAML.
- **Garrafão**: nome, subtítulo, cor de destaque e tema padrão em
  `config/site.yaml` (também editáveis pelo site). Tema **escuro, claro ou do
  sistema** no botão ◐ do topo; a escolha fica no navegador.
- **Calibração por encolhimento**: a chance de cada mercado é "puxada" para
  50% pelo fator `encolhimento` de `config/projecao.yaml`, ajustado fora da
  amostra (0012). Faixas com menos de 30 palpites aparecem marcadas.

### Acesso e administração

- Sem usuários e sem `NBASTATS_PASSWORD`: aberto (uso local).
- Só com `NBASTATS_PASSWORD`: senha única (cabeçalho `X-Senha`).
- Com usuários: cada pessoa entra com login e senha. Para criar o primeiro
  admin, abra **⚙ → Administração** (pede a senha única, se houver) ou rode
  `nbastats usuario criar <login> --admin`. A partir daí a senha única
  deixa de valer.

Na **Administração**: criar usuário (gera senha provisória, mostrada uma vez;
a pessoa cria a própria no 1º acesso), ativar/desativar, admin/usuário,
"acesso até" uma data, nova senha, desconectar aparelhos, registro de
acessos (5 senhas erradas em 15 min bloqueiam o login por 15 min) e
**Sistema** (cargas, backups, botão de backup). Pela linha de comando:

```bash
nbastats usuario listar
nbastats usuario criar coni [--nome Coni] [--admin] [--expira 2027-06-30]
nbastats usuario senha coni          # digita a nova; derruba as sessões
nbastats usuario desativar coni      # ou ativar
```

### Subir numa VPS (Docker)

```bash
deploy/vps.sh subir        # código do último commit; banco inteiro só na 1ª vez
deploy/vps.sh dados        # só as estatísticas do computador (o site não reinicia)
deploy/vps.sh ajustes      # configurações da Administração (data/ajustes)
deploy/vps.sh status       # contêiner e hora dos dados na VPS
deploy/vps.sh desativar    # remove tudo da VPS
```

- **Banco**: na primeira subida vai o `data/nba.db` inteiro, com os usuários.
  Depois a VPS é dona do que se faz no site (logins, sessões, apostas, linhas,
  favoritos) e do computador só vão as estatísticas: `nbastats importar-dados
  <arquivo>` faz upsert das tabelas de dados e não toca nas de uso.
- **Dados**: na nuvem o stats.nba.com bloqueia o IP, então o "Atualizar"
  não funciona lá. Para enviar sozinho, instale o cron com
  `VPS_SYNC=1 deploy/cron.sh instalar` (10 min depois de cada atualização).
- **HTTPS**: com `DOMINIO=nba.exemplo.com`, o contêiner entra na rede do Caddy
  (`REDE`, padrão `netsentinel_default`) com o nome `nba-stats` e a porta fica
  só em `127.0.0.1`; o Caddy precisa de um bloco
  `nba.exemplo.com { reverse_proxy nba-stats:8000 }`. Sem `DOMINIO`, é HTTP na
  porta 8100, só para teste.
- O Streamlit antigo não sobe mais por padrão (`PORTA_ANTIGO=8501` para subir).
- **No ar**: https://nba.elciocastro.com (Caddy do NetSentinel, que importa
  `/config/sites/*.caddy`; o bloco do site está em
  `/var/lib/docker/volumes/netsentinel_caddy-config/_data/sites/nba.caddy`).
  Para tirar do ar: apagar esse arquivo e recarregar o Caddy, depois
  `deploy/vps.sh desativar`.

Padrão: `root@45.159.173.222` com a chave `~/.ssh/netsentinel-vps`.

### Atualização automática, backup e alerta (cron no WSL)

```bash
deploy/cron.sh instalar    # grava no crontab (remover / mostrar)
nbastats backup            # cópia do banco em data/backup (14 mais novas)
nbastats saude             # código 1 + ALERTA se a carga falhou ou tem mais de 36 h
```

O `cron.sh` agenda `atualizar` a cada 15 min das 10h às 02h, `sync-daily`
às 06:00, `backup` às 06:30 e `saude` às 12:00 (log em `logs/cron.log`). Só
roda com o WSL ligado. Se a carga falhar ou ficar velha, o site mostra uma
faixa no topo. Exemplo manual, se preferir:

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
docs/decisoes/             0001 a 0013: decisões, métodos e resultados
docs/BACKLOG.md            o que foi feito e o que falta, em fases
```

## Testes

```bash
pytest
ruff check src tests
# contrato com as APIs reais da NBA (fora do CI; ~10 s):
NBASTATS_CONTRATO=1 pytest -m contrato
```

## Limitações conhecidas

- Posição: as fontes só trazem G/F/C; PG/SG/SF/PF/C é estimado.
- Injury report guardado a partir de 14/11/2026; datas anteriores usam "não
  jogou a última partida".
- Zonas de arremesso: a foto diária (`shot_zones_daily`) começou em
  15/11/2026; o encaixe só poderá ser validado no retroativo com meses dela.
- Sem linha da casa, a referência é o L10 arredondado, que favorece o under.
- Linhas são digitadas; a busca automática depende de escolher as casas
  (fase 3b do backlog).
- Fotos dos jogadores vêm do CDN da NBA (ids da nba_api); com a BALLDONTLIE
  os ids são outros e as fotos não aparecem.
- Login por HTTP simples: fora da rede de casa, só atrás de HTTPS ou VPN.
- O time do jogador é o mais recente informado pela API, não o da época de
  cada jogo (o box score usa o time correto da partida).
