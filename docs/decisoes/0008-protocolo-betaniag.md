# 0008 — Protocolo BetânIAG: análise e proposta para o site

Data: 2026-11-14 · Status: proposta (aguardando o colega) · Fase 5 do backlog

## O protocolo, resumido

1. **Modelo de valor**: probabilidade estimada → odd justa (60% → 1,66);
   há valor (EV+) quando a casa paga mais que a odd justa.
2. **Unidades**: 0,5 u (especulativa), 1 u (L5, H2H e matchup alinhados),
   2 u (todas as bases convergem).
3. **Filtro de props**: na NBA, foco em PRA cruzado com o perfil defensivo
   do adversário.
4. **Breaking news**: análise só validada após a confirmação oficial das
   escalações.
5. **Fontes**: NBA Stats, Props.cash, Rotowire e outras; mandante/visitante,
   L10, L5, H2H, projeções e contexto.
6. **Tabela de probabilidades, cores e níveis** em toda análise formal.

## O que o site já cobre

| Pilar | No site hoje | Observação |
|---|---|---|
| 1. Valor | odd justa, valor esperado, chance calibrada | ✓ |
| 2. Unidades | registro com 0,5/1/2 u e desempenho por unidade | sem regra de sugestão |
| 3. PRA × matchup | PRA, DvP por posição | os dados apoiam: PRA teve a maior separação do DvP (1,93 ponto) |
| 4. Notícias | injury report a cada 15 min | falta o "selo" de análise validada |
| 5. Fontes | NBA Stats (nba_api), injury report oficial | Props.cash/Rotowire não são necessários para os números |
| 6. Tabela | — | o texto cita a tabela, mas não a traz |

## Pontos a melhorar (com base nos testes que fizemos)

**1. A probabilidade precisa vir do modelo, não da taxa de acerto.** Se os
60% do exemplo forem "6 dos últimos 10 jogos", isso não é uma
probabilidade: é uma amostra de 10 que exagera. No teste retroativo, com a
linha no L10, só 44% a 47% dos jogos passaram dela. A chance calibrada do
site (quando prevê 60%, dá ~60%) é a que deve entrar na odd justa; as taxas
de acerto ficam como contexto.

**2. Comparar com a casa sem a margem dela.** Com as duas odds (over e
under), dá para tirar a margem da casa e obter a chance que o mercado
precifica. A vantagem real é a diferença entre a nossa chance e essa. Ex.:
over 1,87 e under 1,93 → mercado ~51% no over; se calculamos 56%, a
vantagem é ~5 pontos.

**3. Exigir uma folga mínima de valor.** A chance calculada tem erro. Um EV
de +1% está dentro desse erro; faz sentido exigir, por exemplo, EV ≥ 4% para
1 u e ≥ 8% para 2 u (números a calibrar com o registro de apostas).

**4. Critérios de unidade objetivos.** "L5, H2H e matchup alinhados" e
"todas as bases convergem" são subjetivos e, pelos nossos testes, fracos:
- **L5** não ajudou a projeção (peso zero na calibração) e o critério
  "forma" não separou resultado (0003);
- **H2H** tem 1 a 4 jogos por temporada: é ruído;
- **"bases convergem"**: Props.cash, Rotowire e NBA Stats usam os mesmos dados
  de origem, então concordarem não é confirmação independente.
Proposta: unidade definida pela vantagem e pela chance (por faixas na
tabela do pilar 6, ou Kelly fracionado limitado a 2 u), e L5/H2H como
alertas, não como requisito.

**5. Selo de análise validada.** "Pré-análise" até o injury report final do
jogo; "validada" quando o último relatório saiu perto do horário e nenhum
jogador relevante do jogo segue Questionable/Doubtful.

**6. Gestão de banca** (ausente no texto): limite de exposição por dia e por
jogo, e cuidado com apostas correlacionadas no mesmo jogo (ex.: over de
pontos do armador e over de assistências do mesmo time).

**7. Medir o protocolo.** O registro de apostas (fase 4) já separa acerto e
ROI por unidade e por faixa de chance. Com dezenas de apostas dá para ver
se os 2 u realmente rendem mais. CLV (linha de fechamento) é a medida mais
rápida de vantagem e entra com a API de odds.

## Proposta para o site

1. **Selo BetânIAG em cada cartão da lista**: cor e nível da tabela do
   pilar 6 e unidade sugerida (0,5 / 1 / 2 / sem valor).
2. **Checklist do protocolo no detalhe do jogador**: chance do modelo, odd
   justa, odd da casa, chance do mercado sem margem, vantagem, EV; L5/L10/H2H
   como contexto; DvP; status de lesão e selo de validação; unidade
   sugerida e por quê; botão "Registrar aposta" já com a unidade.
3. **Página Comparar**:
   - jogador × jogador no mesmo mercado (projeções, chances, barras lado a
     lado, com/sem desfalques);
   - time × time (ritmo, saldo, DvP por posição, desfalques, margem
     esperada e risco de blowout);
   - tendências (quem ganhou minutos e uso no L5 contra a temporada; defesas
     que pioraram nos últimos 15 dias).
4. **Relatório BetânIAG (opcional, com IA)**: botão que gera o texto da
   análise formal com a tabela do pilar 6, usando os números do site como
   dados (o modelo de linguagem escreve, não inventa números), e um campo de
   pergunta livre ("compare Murray e Brunson em PRA hoje"). Exige chave da
   API da Anthropic no `.env` e custa centavos por análise.

## Perguntas ao colega

1. A **tabela do pilar 6** (faixas de probabilidade, cores e níveis).
2. Aceitam **unidade por vantagem e chance** no lugar de "L5/H2H/bases
   alinhadas"? Se sim, quais limites (ou começamos com os propostos e
   ajustamos pelo registro)?
3. Querem o **relatório com IA** (item 4)? Se sim, a chave da API.
4. **Banca**: valor da unidade e limite de exposição por dia.
5. O protocolo cita futebol e MMA: o site continua só NBA?
