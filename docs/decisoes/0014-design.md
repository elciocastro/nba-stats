# 0014 — Acabamento visual e movimento

Data: 2026-11-15. Pedido: deixar o site mais moderno e elegante usando a
skill de design (tasteskill), transitions.dev e React Bits.

## O que se aproveitou de cada um
- **tasteskill**: foi feita para sites institucionais (hero de tela cheia,
  uma seção por tela, fotos, verificação final de landing page). O
  Garrafão é um painel de dados com login, então não seguimos a estrutura
  de página nem a verificação final. Aproveitado: a tipografia sugerida
  para software (Instrument Sans + DM Mono), a especificação de movimento
  (`references/motion.md`) e o cuidado com foco e movimento reduzido.
- **transitions.dev**: a ideia de números que rolam e de indicadores que
  deslizam. O código de lá é parte pago e sem licença clara, então nada
  foi copiado.
- **React Bits** (MIT + Commons Clause: uso dentro do site permitido,
  revenda proibida; `frontend/src/reactbits/LICENSE.md`): `CountUp` nos
  indicadores do Início e das Apostas e `LightRays` (refletores de arena)
  no login. Os dois carregam sob demanda e param com a aba em segundo plano.

## Regras de movimento
- Uma curva de UI (`cubic-bezier(.2,.8,.2,1)`), 150 ms na entrada e 120 ms
  na saída; só transform e opacity.
- Botão sobe 1px e afunda ao clicar; cartão clicável sobe 2px com sombra
  suave; foto de notícia aproxima 3%.
- Abas: um indicador por barra que desliza até a ativa
  (`frontend/src/indicador.ts`, desenhado no `::before`, sem mexer no DOM
  do React). Menu principal: barra de 2px sob a página atual.
- Troca de página: o conteúdo chega uma vez (8px, 320 ms). Nada se move
  por causa da rolagem.
- Carregamento: esqueletos no formato do conteúdo.
- Tudo para com `prefers-reduced-motion`; os refletores do login nem são
  carregados.

## Fontes
Empacotadas no site (`@fontsource`), sem chamar o Google a cada acesso.
