# 0010 — Acesso por usuário, operação automática e diferenciais

Data: 2026-11-15. Pedido: "executar tudo que você consiga fazer sozinho",
pesquisar os sites de estatística para achar diferenciais e "ter um painel
de administração para controlar o acesso".

## Acesso

- **Três modos**, escolhidos pelo que existe no banco: `usuarios` (há pelo
  menos um usuário), `senha` (sem usuários, com `NBASTATS_PASSWORD`, como
  antes) e `aberto` (uso local). A migração é feita pelo próprio site: em
  **Administração**, quem tem a senha única cria o primeiro admin; a partir
  daí a senha única deixa de valer. Também dá pela linha de comando:
  `nbastats usuario criar <login> --admin` (a senha é digitada, não fica no
  histórico do shell).
- **Senhas** com PBKDF2-SHA256 (240 mil iterações, sal por usuário), só da
  biblioteca padrão. **Sessões** de 30 dias com token aleatório; o banco
  guarda só o hash do token.
- **Senha provisória**: o admin cria o usuário ou gera uma nova senha; a
  senha aparece uma vez na tela e a pessoa é obrigada a criar a própria no
  primeiro acesso (a API recusa tudo até lá).
- **Controle**: ativar/desativar (derruba as sessões na hora), papel
  (admin/usuário), **acesso até** uma data, desconectar todos os aparelhos,
  apagar. Sempre fica pelo menos um admin ativo.
- **Registro de acessos** (certos e errados, com IP) e **bloqueio**: 5 senhas
  erradas em 15 minutos para o mesmo login (ou 15 do mesmo IP) bloqueiam por
  15 minutos.
- Não entrou: favoritos e apostas por usuário (hoje são compartilhados) e
  login com Google/Cloudflare Access. Estão no backlog.

## Operação

- `deploy/cron.sh instalar` grava no crontab: `atualizar` a cada 15 min das
  10h às 02h (horário de Brasília), `sync-daily` às 06:00, `backup` às 06:30
  e `saude` às 12:00. `flock` impede duas cargas ao mesmo tempo; log em
  `logs/cron.log`. Só roda com o WSL ligado.
- **Backup** pela API de backup do SQLite (cópia consistente com o site
  aberto) em `data/backup/nba-AAAAMMDD.db`, 14 cópias.
- **Alerta de carga**: sem carga boa há mais de 36 h, ou com falha depois da
  última boa, aparece uma faixa no topo do site e `nbastats saude` sai com
  código 1. A aba **Sistema** da administração mostra as últimas cargas,
  backups e o tamanho do banco.

## Diferenciais (pesquisa de 2026-11-15)

O que os apps de props pagos (Props.Cash, Outlier, Stat Pick, Toad,
PropsMadness, StatSharp) oferecem e o site **já tem**: taxa de acerto em
L5/L10/temporada/anterior/H2H com a linha ajustável, com/sem companheiro,
recortes (casa/fora, descanso), odd justa sem a margem e valor esperado,
contexto de lesão e registro das próprias apostas com ROI.

O que eles têm e **falta**: comparação de linhas entre casas (depende da API
de odds, 3b), alertas/notificações e filtros salvos. Cleaning the Glass
(estatística avançada) tira o garbage time das médias por padrão e mostra
on/off de quintetos.

O que quase ninguém mostra e pode ser **nosso diferencial**:
1. **Calibração pública**: "quando o site disse 60%, bateu quanto?" (curva
   de calibração com os jogos já disputados e com as apostas registradas).
   Os apps divulgam taxas de acerto escolhidas a dedo; mostrar a calibração
   honesta é o que ajuda a pessoa a confiar (ou não) no número.
2. **Efeito cascata da lesão**: quando o injury report muda (ex.: um titular
   vira Out), recalcular e avisar quem ganha minutos/uso, já com a nova
   projeção e a diferença contra a linha.
3. **Médias sem garbage time** (jogos decididos por 20+ no 4º quarto) e
   risco de blowout já entrando na projeção de minutos.
4. **Alertas** (Telegram/e-mail/push) para favoritos: mudança de status,
   linha nova com valor, jogador "a caminho" no Ao Vivo.
5. **Resumo do dia** às 17h: jogos, desfalques, 5 melhores oportunidades.
6. **Diário de apostas melhor**: motivo/etiqueta de cada aposta, CLV (linha
   de fechamento) e quais motivos dão lucro.
7. **Mercado brasileiro**: linhas das casas que vocês usam, em decimal e
   reais, tudo em português.
8. **Jogo responsável**: limite de unidades por dia/semana e aviso de
   sequência de perdas (o site é de estatística; isso protege quem usa).
9. **Instalar no celular** (PWA) e funcionar com conexão ruim.

Fontes: [Props.Cash (App Store)](https://apps.apple.com/app/id1606752641),
[Props.Cash vs outras ferramentas](https://bettoredge.com/post/props-cash-vs-other-prop-betting-tools),
[Stat Pick (App Store)](https://apps.apple.com/us/app/stat-pick-player-props-ai/id6752438355),
[Toad Sports (App Store)](https://apps.apple.com/us/app/toad-sports-prop-pick-finder/id6476698112),
[PropsMadness](https://propsmadness.pages.dev/blog/getting-started-with-propsmadness),
[StatSharp](https://statsharp.kit.com/posts/introducing-new-nba-player-prop-stats-and-trends),
[Stat Sniper](https://statsniper.com/),
[Cleaning the Glass](https://www.cleaningtheglass.com/stats),
[Props.Cash: filtro de descanso](https://propsdotcash.beehiiv.com/p/propscash-newsletter-simple-nhl-spots-using-days-rest-filter-nba).
A maior parte é página do próprio fornecedor: são as funções que eles
anunciam, não uma avaliação de qualidade.
