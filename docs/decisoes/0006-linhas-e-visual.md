# 0006 — Fase 3: linhas, chance de over/under e a página Props

Data: 2026-11-14 · Status: aceito · Complementa a 0005

## Contexto

O colega precisa comparar a análise com a linha que o mercado precifica,
digitada à mão por enquanto e, depois, buscada de uma API (as casas ainda
serão informadas). Ele também pediu uma tela mais dinâmica, com a referência
de um app de props: lista por mercado, linha, um número de destaque e barras
dos últimos jogos coloridas contra a linha.

## Decisões

**Linha.** Tabela `lines` (data, jogador, mercado, linha, odd over, odd
under, fonte). Digitada no detalhe do jogador, na página Linhas ou com
`nbastats linha`. Sem linha, usa-se uma **referência**: o L10 arredondado
para x,5, marcada como "ref". A fonte fica registrada, então a futura API de
odds grava na mesma tabela com `source` = nome da casa.

**Chance de over/under.** A projeção dá a média. A distribuição em volta
dela é escolhida por mercado na calibração, pela de menor erro de
probabilidade (Brier) contra a linha de referência:

- **binomial negativa** (contagens baixas e assimétricas: rebotes, 3FM,
  FTM, roubos, tocos...);
- **normal** com desvio crescente com a média (pontos, PRA e combinados).

Calibração fora da amostra (2025-26, de 15/02 a abril), chance prevista →
frequência real:

| Mercado | ~30% | ~40% | ~50% | ~60% | ~70% |
|---|---|---|---|---|---|
| Pontos (normal) | 30 → 33 | 41 → 41 | 50 → 49 | 59 → 57 | 69 → 68 |
| 3FM (binomial neg.) | 24 → 26 | 40 → 41 | 49 → 49 | 59 → 60 | 69 → 65 |
| Roubos (binomial neg.) | 27 → 26 | 40 → 40 | 50 → 50 | 59 → 57 | 68 → 66 |

A normal, testada antes para todos os mercados, superestimava o over nos de
contagem baixa (3FM: previa 40%, deu 36%; previa 29%, deu 18%).

**Valor esperado** = chance × odd decimal − 1; **odd justa** = 1 / chance.

**Referência favorece o under.** Com a linha no L10, só 39% a 47% dos jogos
passaram dela (médias recentes altas tendem a voltar). Isso é real e a
chance mostra, mas a decisão de aposta depende da linha da casa. A tela
avisa enquanto não houver linha informada.

**Página Props** (`web/props.py`). Continua em Streamlit, que já tem os
recursos necessários: abas (`st.pills`), seleção de linha na tabela, janela
de detalhe (`st.dialog`), imagens nas células (foto do CDN da NBA e barras
em SVG gerado na hora) e tema escuro (`.streamlit/config.toml`). O visual é
próprio, inspirado na dinâmica da referência, sem copiar marca nem layout.
Trocar o front para outra tecnologia fica para quando o site for ao ar
(fase 6), se o Streamlit limitar.

## Consequências

- `nbastats calibrar` agora também grava a distribuição de cada mercado.
- A API de odds (fase 3b) só precisa gravar na tabela `lines`.
- O registro de apostas (fase 4) usa a mesma chance e o mesmo valor
  esperado para acompanhar o resultado.
