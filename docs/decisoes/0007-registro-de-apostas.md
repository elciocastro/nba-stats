# 0007 — Fase 4: registro e conferência de apostas

Data: 2026-11-14 · Status: aceito · Complementa a 0006

## Contexto

A projeção (0005) e a chance de over/under (0006) foram validadas contra o
resultado dos jogos, mas não contra o que importa para quem aposta: odd,
stake e lucro. Para saber se o método (e depois o Protocolo BetânIAG) ganha
dinheiro, é preciso registrar cada aposta e conferir o resultado.

## Decisões

- Tabela `bets` com a **fotografia do momento**: chance calculada do lado
  apostado, projeção e valor esperado. Mudanças futuras no modelo não
  reescrevem o que se sabia quando a aposta foi feita.
- Conferência automática (`settle_bets`) quando o jogo tem estatística:
  over ganha se real > linha; under se real < linha; real = linha →
  devolvida; jogador sem minutos → anulada (configurável em
  `config/apostas.yaml`, como na maioria das casas). Roda no `atualizar`, no
  botão "Atualizar agora", em "Conferir resultados" e em `nbastats apostas`.
- Unidades oferecidas 0,5 / 1 / 2, como no protocolo; valor da unidade no
  YAML para mostrar o lucro em dinheiro.
- Desempenho: acerto real contra a **chance média calculada** (se o acerto
  fica sistematicamente abaixo, o método está otimista), lucro em unidades,
  ROI e curva; por mercado, por unidades, por faixa de chance e por lado.

## Consequências

- Com algumas dezenas de apostas dá para ver se a faixa de 60%+ realmente
  acerta ~60% e se as apostas de 2 u rendem mais que as de 1 u.
- O ROI de poucas apostas é quase só sorte: com 50 apostas a odd 1,90, um
  ROI de +10% ainda é compatível com nenhuma vantagem real. A tela avisa.
- CLV (linha de fechamento) fica para quando houver API de odds (4d).
