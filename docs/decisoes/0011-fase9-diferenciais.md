# 0011 — Fase 9: diferenciais

Data: 2026-11-15. Itens da pesquisa em 0010.

## Calibração pública (9a)
- Pergunta respondida: "quando o site deu X% para um lado, acertou quanto?".
  Lado escolhido = o mais provável; faixas 50–55, 55–60, 60–65, 65–70,
  70–80, 80–100%; Brier score junto.
- Três fontes: **backtest** da temporada atual (fora da amostra usada no
  `calibrar`, linha = L10 arredondado), **previsões** guardadas antes de cada
  jogo (tabela `predictions`, foto até o início; `nbastats previsoes` de hora
  em hora e a própria página Props do dia) e **apostas** registradas.
- Primeiro resultado (2026-11-15, 1.188 palpites desde 01/11): pontos 56,5%
  prometido × 57,2% real; rebotes 59,4 × 60,4; PRA 56,6 × 56,6. Na faixa
  70–80% o site está otimista (~72 × ~61): fica como 9m no backlog.

## Efeito cascata (9b)
- Reorganiza o que o relatório do dia já tem (média com/sem o companheiro
  desfalcado e projeção) por desfalque, com pelo menos 2 jogos "sem". O que
  mudou no último injury report vem primeiro (🆕).

## Alertas e resumo (9c, 9d)
- Telegram pela Bot API, só biblioteca padrão. Token e chat no `.env`
  (`NBASTATS_TELEGRAM_TOKEN`, `NBASTATS_TELEGRAM_CHAT`); liga em
  `config/alertas.yaml` (`habilitado`). Desligado por padrão.
- Alertas (a cada 15 min): mudança de status de jogador/time favorito e linha
  da casa com valor esperado ≥ 5%. Cada alerta sai uma vez (`alerts_sent`).
  Resumo às 17h. `--simular` mostra sem enviar.

## Sem lavadas (9e)
- Jogo decidido por 20+ pontos (`lavada.margem` em `config/projecao.yaml`).
  Recorte "Sem lavada" na página do jogador e opção no Ranking. Sem dados por
  quarto, a margem final é a aproximação possível.

## Diário e jogo responsável (9f, 9g)
- Etiquetas (motivo) e nota por aposta; desempenho "Por motivo". Lista em
  `config/apostas.yaml`.
- Apostas passam a ter dona (`user_id`); com login, a página mostra as suas
  (ou todas).
- Limites de unidades por dia e por 7 dias e aviso de derrotas seguidas
  (`jogo_responsavel` em `config/apostas.yaml`). Passando, a API responde 409
  e o site pede confirmação: avisa, não proíbe.
- Primeira migração de banco (`db.migrate`): colunas novas em tabelas
  antigas, idempotente.

## Filtros salvos (9h) e PWA (9i)
- Filtros novos na Props (chance mínima, lado, só linha da casa, sem dúvida
  de lesão) e "Meus filtros", guardados no servidor por usuário.
- Manifest, ícones e service worker que guarda só o casco do site (HTML, JS,
  CSS, ícones); `/api` nunca vai para o cache.
