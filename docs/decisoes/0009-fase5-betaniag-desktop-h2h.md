# 0009 — Fase 5: BetânIAG configurável, H2H, computador e notícias

Data: 2026-11-14 · Status: aceito · Responde à 0008

## Contexto

O colega respondeu às perguntas da 0008:

1. Tabela do pilar 6: "uma paleta de cores que transmita a diferença e
   destaque as boas".
2. Unidade por vantagem e chance: **em espera** até validar com as casas.
3. Relatório com IA: deixar **configurado, sem executar** por enquanto.
4. Banca: não é preciso; o site é de estatística, não casa de apostas.
5. Futebol e MMA: deixar preparado, sem usar.
6. Casas: ainda sendo levantadas (segue a fase 3b).

Pedidos novos: **H2H** (jogador contra o adversário de hoje, em todas as
temporadas), o site **bom no computador** (estava pensado só para o
celular), visual mais rico no estilo das planilhas de props e **notícias de
lesão** (quem volta, com quantos minutos).

## Decisões

- **Protocolo desligado por padrão** (`config/betaniag.yaml`,
  `habilitado: false`), com botão na barra lateral (Preferências) que liga
  só para a sessão.
- **Selo por faixas** da chance do modelo no lado favorito e do valor
  esperado quando há odd: Forte (verde forte, ≥ 62% e EV ≥ 8%), Boa (verde,
  ≥ 57% e EV ≥ 4%), Especulativa (âmbar, ≥ 53% e EV ≥ 0), Neutra (cinza) e
  Sem valor (vermelho escuro, EV negativo). Faixas e cores no YAML.
- **Linha de referência limita o selo** a Especulativa
  (`linha_ref_max`): sem linha da casa, a referência (L10 arredondado)
  favorece o under (0006) e o selo "Forte" seria enganoso.
- **Unidade sugerida existe mas fica desligada** (`unidades.habilitado:
  false`); o registro de apostas continua oferecendo 0,5/1/2 u.
- **Mercado sem margem e vantagem**: com as duas odds, a chance da casa sem
  a margem (método proporcional); vantagem = nossa chance − a do mercado.
- **Selo de validação**: "pré-análise" até um injury report publicado a
  até 90 min do jogo sem jogadores relevantes (20+ min no L10) em
  Questionable/Doubtful; então "validada".
- **H2H em todas as temporadas da base**; as janelas seguem a ordem das
  planilhas de props: temporada atual, H2H, L5, L10, L20, temporada
  anterior. H2H é contexto (com menos de 3 jogos, "só curiosidade").
- **Layout por aparelho**: o navegador decide (user agent), com escolha
  manual na barra lateral. Computador: tabela de calor; celular: cartões.
- **Página do jogador** no lugar do diálogo: gráfico grande com rótulos e
  adversário, janelas e recortes (casa/fora/vitória/derrota/sem descanso),
  minutos e posses usadas, certas × tentadas, H2H, "e se jogar X minutos"
  (mesma taxa por minuto e mesmos ajustes), checklist e desfalques.
- **Notícias** a partir do que já guardamos: diferença entre os dois
  últimos injury reports do dia e quem pode voltar (ficou fora do último
  jogo e não está Out/Doubtful), com a produção por minuto.
- **IA opcional** (`nbastats/ia.py`): Claude Opus 5.5 pela biblioteca
  oficial da Anthropic, com fallback do servidor ligado para pedidos
  recusados. Recebe só os números do site em JSON; a instrução proíbe
  inventar números. Desligada, com chave ausente ou sem a biblioteca, nada é
  enviado e a tela explica o que falta.
- **Página inicial (Início)**: cartões dos jogos (favorito e margem,
  blowout, ritmo contra a liga, desfalques, props boas, maior chance),
  melhores oportunidades (com odd: por valor esperado; sem odd: pela chance,
  uma por jogador e só com média L10 relevante, `destaques.min_media` no
  YAML, para não destacar "under 0,5 bola de 3" de pivô) e jogadores em alta
  (PRA no L5 acima da temporada, com minutos e uso). Tocar abre o jogador.
- **Cores nos valores** da tabela jogo a jogo e do H2H: verde quando atingiu
  a média dele na temporada (no mercado escolhido, a linha), âmbar até 80%,
  vermelho abaixo. Média do próprio jogador em vez de cortes fixos (20/10),
  porque serve para qualquer mercado e qualquer jogador.
- **Banca fora do escopo** (pedido do colega); o item 5h sai do backlog.
- **Esportes**: `esportes` no YAML com futebol e MMA inativos; o site só
  mostra a NBA.

## Consequências

- O computador ganha uma visão densa; o celular continua com cartões.
- As faixas do selo são um ponto de partida: o registro de apostas (0007)
  mostra o acerto por faixa de chance para recalibrá-las.
- "E se jogar X minutos" é linear; não aumenta a taxa por minuto quando o
  jogador ganha uso com companheiros fora (isso já entra no ajuste por
  desfalques da projeção).
- Notícias dependem do injury report a cada 15 min (`nbastats atualizar`);
  o retorno "provável" é inferido, não uma notícia publicada.
