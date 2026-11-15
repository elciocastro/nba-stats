# 0013 — Página inicial da liga, Lesões e Conferência

Data: 2026-11-15. Pedido depois de avaliar o site: página inicial com
notícias, transações, últimos jogos e destaques; login com mais cara de
basquete; "Notícias" era na verdade lesões; calibração não precisa ficar
no menu.

## Página inicial
- Duas partes que carregam separadas: o **panorama da liga** (`/api/liga`,
  ~40 ms, só consultas no banco) aparece na hora; o **Hoje** (projeções,
  oportunidades, em alta) é o cálculo pesado e mostra a bola quicando
  enquanto monta. Antes a página inteira esperava o cálculo.
- Panorama (`metrics/liga.py`): última rodada com placar e cestinhas;
  destaques pelo **Game Score** de Hollinger (com duplo/triplo-duplo e
  recorde do jogador na temporada); classificação por conferência (V-D,
  jogos atrás, últimos 10, sequência, zonas de playoff e play-in); líderes
  por média (mínimo de 70% dos jogos do time, regra da NBA); manchetes e
  transações.
- Páginas carregadas sob demanda (`React.lazy`): o pacote inicial caiu de
  808 kB para 293 kB (91 kB comprimido).

## Fontes de notícias (`NewsSource`)
- Manchetes: API pública do site da ESPN (em inglês; matérias, resumos,
  prévias; vídeos ficam de fora da página). Não há fonte pública
  equivalente em português com a mesma cobertura.
- Transações: o JSON que alimenta nba.com/players/transactions (mesmos ids
  da nba_api). Os textos viram português pelo tipo e por modelos de frase
  (`liga.translate`); o que não reconhecer fica no original. As linhas de
  uma troca viram um item.
- Gravadas com upsert (`news`, `transactions`) pelo `nbastats atualizar`:
  manchetes a cada execução, transações (~4 MB) a cada 3 h. Se a fonte
  falhar, o erro fica no `sync_log` e a carga das estatísticas segue.
  Manual: `nbastats noticias`. Como o stats.nba.com, o JSON de transações
  pode não responder de servidores na nuvem.

## Organização do menu
- "Notícias" virou **Lesões** (`/lesoes`, segunda posição do menu): é o
  injury report, o efeito cascata e quem pode voltar, que pesam direto nos
  props. O endereço antigo redireciona.
- "Calibração" saiu do menu e virou **Conferência das estatísticas**
  (`/conferencia`), no menu da conta e em "Mais" no celular: é auditoria do
  modelo, não uso diário.

## Login
- Meia quadra desenhada ao fundo (linhas na cor de destaque, movimento
  lento), brilho radial e a bola quicando. Quem pede menos movimento no
  sistema (`prefers-reduced-motion`) vê tudo parado.

## CI
- Actions em Node 24 (`checkout`, `setup-python`, `setup-node` v7) e build
  do front em Node 24: some o aviso de Node 20 descontinuado.

## Jogador sem jogo na data
- Antes, abrir um jogador que não jogava no dia (Ranking, transações,
  líderes) dava "não encontrado". Agora a página mostra o perfil
  (`historico.player_profile`): histórico, médias, janelas contra a linha de
  referência (L10 arredondado), playoffs e o próximo jogo do time, com um
  botão que leva à data dele. Sem projeção, linha da casa nem aposta.
- O time atual vem da transação mais recente quando ela é posterior ao último
  jogo (contratado, trocado ou dispensado), porque o banco só sabe o time
  pelo último jogo. Quem chegou a um time novo só entra nas projeções do dia
  depois de jogar por ele (limitação conhecida).

## VPS: o site é dono do uso, o computador manda as estatísticas
- Com logins, copiar o banco inteiro a cada envio apagaria sessões, apostas,
  linhas e favoritos feitos na VPS. `db.import_data` (CLI `importar-dados`)
  faz upsert só das tabelas de dados (`DATA_TABLES`; `shot_zones` é trocada
  inteira por ser fotografia) numa transação; as de uso ficam intactas.
  `deploy/vps.sh` manda o banco inteiro só na primeira subida.
- Cópia do banco pela API de backup do SQLite (consistente com o cron
  gravando), sem depender do `sqlite3` de linha de comando.
- HTTPS pelo Caddy que já roda na VPS (do NetSentinel), num subdomínio
  próprio: o contêiner entra na rede do Caddy com o nome `nba-stats`.
  `suporte.elciocastro.com` é o endereço do NetSentinel e fica como está.
