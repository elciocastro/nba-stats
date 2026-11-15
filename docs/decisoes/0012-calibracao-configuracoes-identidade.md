# 0012 — Fase 10: calibração por encolhimento, configurações e identidade

Data: 2026-11-15.

## Otimismo na faixa 70–80% (9m)
- O "72% prometido × 61% real" de 0011 vinha de poucos palpites: só 13 de
  pontos caíam na faixa. Rebotes, assistências e bolas de 3 já estavam
  calibrados ali.
- Com amostra maior (2025, de 15/02 em diante, fora do período de ajuste),
  os mercados de pontuação (pts, pr, pa, pra) prometiam ~73% e acertavam
  ~66–68% nas faixas altas: excesso real de confiança, menor que o visto.
- Correção: **encolhimento** por mercado, `p' = σ(b · logit(p))`
  (`linhas.shrink`), com `b` ajustado pelo `nbastats calibrar` (grade
  0,50–1,30, menor Brier) e gravado em `config/projecao.yaml`
  (`mercados.<m>.encolhimento`). Ficou pts 0,80, pra 0,80, pr 0,81, pa 0,83,
  ast 0,85, reb 0,96, fg3m 0,90, ftm 0,71, fta 0,63.
- Fora da amostra o Brier quase não muda (o grosso dos palpites está em
  50–65%); o ganho é nas faixas altas, que deixam de prometer demais.
- Backtest de 2026 recalculado (1.188 palpites desde 01/11): pontos 55,3% ×
  57,2%, rebotes 59,1 × 60,4, PRA 55,3 × 56,6, bolas de 3 63,0 × 63,0. A
  página marca com * as faixas com menos de 30 palpites.
- O selo/unidade automático (5i) continua desligado até haver previsões com
  linha da casa suficientes.

## Minutos em lavadas (9l): testado, não aplicado
- Razão minutos reais / L10 em jogos decididos por 20+: titulares de 30+ min
  0,878; 24–30 min 0,910; 16–24 min 0,964; menos de 16 min 0,960.
- Aplicar esse corte ponderado pelo risco de blowout do jogo mudou o erro
  médio em menos de 0,1% em 2025 e 2026: o risco projetado raramente é alto
  o bastante, e a margem real é pouco previsível. Não entra na projeção; o
  dataset guarda `min_l10` e `risco_blowout` para rever depois.

## Configurações pela Administração
- Os YAML continuam sendo o padrão versionado. O site grava só as
  diferenças em `data/ajustes/<arquivo>.yaml` (fora do Git; caminho em
  `NBASTATS_AJUSTES`), aplicadas por cima ao carregar.
- Cada campo editável tem tipo, descrição e limites em `ajustes.CAMPOS`
  (sim/não, número, inteiro, texto, cor, opção, listas). Valor fora do tipo
  é recusado pela API; "Restaurar" apaga o ajuste.
- `nbastats calibrar` lê e regrava só o YAML (sem ajustes), para o resultado
  da calibração não depender do que alguém mexeu no site.

## Identidade: Garrafão
- Nome curto, do basquete, que não lembra casa de apostas. Logo de bola em
  SVG, cor de destaque laranja `#f97316`, subtítulo "Estatística da NBA para
  quem analisa props". Tudo em `config/site.yaml` e editável pelo site.
- Tema escuro (padrão), claro e "do sistema"; cores em variáveis CSS, a cor
  de destaque gera as variações (`--brand-soft`, `--brand-ink`).

## Outros itens
- Favoritos por usuário (8d): na primeira vez cada usuário recebe uma cópia
  da lista compartilhada (`user_seeds` evita repetir); alertas usam todos.
- Alertas ao vivo (9k): "a caminho de bater" (chance ≥ `ao_vivo_chance_min`)
  e "bateu", só para favoritos e só uma vez por jogador/mercado/dia.
- Playoffs na página do jogador (4.6/5.6), CSV em Props/Apostas (5.3), foto
  diária das zonas (2g), ruff no CI (7.2) e teste de contrato opcional (7.3).

## Ideias de gráficos (10d, a escolher)
- **Leque de distribuição** na página do jogador: a curva da projeção com a
  linha marcada e a área over/under, em vez de só o número da chance.
- **Minutos × produção**: dispersão jogo a jogo, para ver se a linha depende
  de minutos.
- **Calibração por mercado** em pequenos múltiplos.
- **Curva de lucro** das apostas com a banca e o pior rebaixamento.
- **Mapa de chutes** com as zonas do jogador contra a defesa adversária.
