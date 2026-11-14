# 0001 — Base completa, fonte BALLDONTLIE, SQLite e Streamlit

Data: 2026-11-14 · Status: aceito (revisar após a primeira validação de uso)

## Contexto

Site privado de estatísticas da NBA. Havia duas dúvidas: baixar dados sob
demanda (escolher um jogo e buscar) ou manter uma base com a temporada
passada e a atual; e de onde vêm os dados.

## Decisões

1. **Base completa, não download sob demanda.** Carga de 2025-26 e 2026-27,
   mais uma atualização diária. "Ver Warriors x Bulls" é uma consulta na
   base. Motivo: ranking, tendência e "jogador em potencial" precisam de
   todos os jogos de todos os jogadores; buscar jogo a jogo nunca daria
   isso. O volume é pequeno (dezenas de milhares de linhas por temporada).
2. **Fonte: BALLDONTLIE, plano ALL-STAR.** API com chave, estável e sem
   bloqueio de IP de nuvem. O stats.nba.com (via `nba_api`) é gratuito, mas
   bloqueia datacenters e muda sem aviso. A ingestão depende só da
   interface `DataSource`, então a fonte pode ser trocada.
3. **SQLite.** Um arquivo, zero infraestrutura, suficiente para o volume e
   para dois usuários. Migrar para Postgres se houver escrita concorrente
   ou se a hospedagem exigir.
4. **Streamlit.** Tabelas, filtros e gráficos sem front-end separado. As
   telas só chamam `nbastats.metrics`; trocar por FastAPI + front depois
   não mexe em ingestão nem em métricas.
5. **Regras de "potencial" em YAML** (`config/potencial.yaml`), para quem
   analisa ajustar sem mexer em código.

## Fora do escopo por enquanto

Dados ao vivo, odds, acesso público, métricas avançadas, ML.

## Em aberto

- Onde hospedar (o coletor e o site podem rodar na mesma VM).
- Login: hoje é uma senha única por variável de ambiente.
- Critérios reais de "potencial", a definir com quem vai usar.
