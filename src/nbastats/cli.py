"""Linha de comando: nbastats <comando>."""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from . import db
from .config import get_settings
from .ingest import (
    refresh,
    sync_injuries,
    sync_range,
    sync_schedule,
    sync_season,
    sync_shot_zones,
)
from .metrics import (
    MATCHUP_STATS,
    backtest,
    boxscore,
    build_dataset,
    calibrate,
    evaluate,
    load_matchup_rules,
    load_projection_params,
    load_rules,
    matchup_report,
    player_trends,
    rank_potenciais,
    save_projection_params,
)
from .sources import FONTES, build_injury_source, build_news_source, build_source


def _table(rows: list[dict], cols: list[str], limit: int = 25) -> None:
    if not rows:
        print("(sem dados)")
        return
    rows = rows[:limit]
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    print("  ".join(c.ljust(widths[c]) for c in cols))
    for r in rows:
        print("  ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols))


def _next_days(n: int) -> list[str]:
    today = date.today()
    return [(today + timedelta(days=i)).isoformat() for i in range(n)]


def _print_matchup(item: dict, stat: str, limit: int) -> None:
    g, r, s, d = item["jogo"], item["ritmo"], item["saldo"], item["desfalques"]
    placar = (f"{g['visitor_team_score']}-{g['home_team_score']}"
              if g["home_team_score"] is not None else g["status"] or "")
    print(f"\n=== {g['visitor']} @ {g['home']}  {g['date']}  {placar}")
    print(f"ritmo {g['visitor']} {r['fora']} / {g['home']} {r['casa']} (liga {r['liga']})  "
          f"saldo {g['visitor']} {s['fora']:+} / {g['home']} {s['casa']:+}"
          if r["casa"] is not None and r["fora"] is not None else "sem histórico de ritmo")
    origem = (f"injury report {item['injury_report']}" if item["injury_report"]
              else "não jogaram a última partida")
    for side, team in (("fora", g["visitor"]), ("casa", g["home"])):
        if d[side]:
            print(f"desfalques {team} ({origem}): {', '.join(d[side])}")
    if item.get("margem_esperada") is not None:
        m = item["margem_esperada"]
        fav = g["home"] if m >= 0 else g["visitor"]
        print(f"margem esperada: {fav} por {abs(m):.1f}  ·  risco de blowout (15+): "
              f"{100 * item['risco_blowout']:.0f}%")
    rows = [{**p, "nota": f"{p['nota']}/{p['nota_max']}",
             "dvp": f"{p['dvp']} ({p['dvp_rank']}º)" if p["dvp_rank"] else "-",
             "dvp_15d": f"{p['dvp_rec']} ({p['dvp_rec_rank']}º)" if p["dvp_rec_rank"] else "-",
             "min_l5/l10": f"{p['min_l5']}/{p['min_l10']}",
             "real": "" if p["real"] is None else p["real"],
             "jogador": p["jogador"] + (f" [{p['lesao']}]" if p["lesao"] else "")
                        + (" *" if p["fora_ultimo_jogo"] and not p["lesao"] else ""),
             "pos": f"{p['grupo'] or '?'}/{p['posicao_est'] or '?'}",
             "proj": p.get("proj", ""),
             "vs_l10": f"{p['proj_vs_l10']:+.1f}" if p.get("proj_vs_l10") is not None else "",
             "zonas": f"{p['encaixe_zonas']:+.1f}" if p.get("encaixe_zonas") is not None else "",
             "com/sem": "; ".join(f"sem {c['companheiro'].split()[-1]} {c['sem']} ({c['jogos_sem']}j)"
                                  for c in p.get("com_sem", []) if c["jogos_sem"])}
            for p in item["jogadores"]]
    _table(rows, ["jogador", "time", "pos", "min_l5/l10", "temporada", "l10", "l5",
                  "proj", "vs_l10", "dvp", "zonas", "nota", "real", "com/sem"], limit)
    if any(p["fora_ultimo_jogo"] for p in item["jogadores"][:limit]):
        print("* não jogou a última partida do time: confirmar se joga")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nbastats", description=__doc__)
    parser.add_argument("--fonte", choices=FONTES,
                        help="fonte de dados (padrão: NBASTATS_FONTE ou nba_api)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="cria as tabelas")

    p = sub.add_parser("sync-season", help="carga completa de uma temporada")
    p.add_argument("season", type=int, help="ano de início (2025 = temporada 2025-26)")

    p = sub.add_parser("sync-daily", help="atualiza os últimos dias (para o cron)")
    p.add_argument("--days", type=int, default=3)

    p = sub.add_parser("jogo", help="box score de um confronto, ex.: jogo GSW CHI")
    p.add_argument("time_a")
    p.add_argument("time_b")
    p.add_argument("--data", help="AAAA-MM-DD; sem data, o mais recente")

    p = sub.add_parser("ranking", help="líderes de uma estatística")
    p.add_argument("season", type=int)
    p.add_argument("--stat", default="pts")
    p.add_argument("--min-jogos", type=int, default=10)

    p = sub.add_parser("potencial", help="ranking de jogadores em potencial")
    p.add_argument("season", type=int)
    p.add_argument("--regras", default="config/potencial.yaml")

    p = sub.add_parser("sync-agenda", help="grava os jogos agendados de hoje e amanhã")
    p.add_argument("--dias", type=int, default=2, help="quantos dias a partir de hoje")

    p = sub.add_parser("importar-dados", help="traz as estatísticas de outro banco sem mexer em usuários e apostas")
    p.add_argument("arquivo", help="banco SQLite de origem (ex.: cópia do data/nba.db do computador)")
    sub.add_parser("noticias", help="grava as manchetes (ESPN) e as transações da temporada (NBA)")
    p = sub.add_parser("lesoes", help="grava o injury report oficial mais recente")

    p = sub.add_parser("atualizar",
                       help="estatísticas recentes + agenda + injury report (para rodar a cada 15 min)")
    p.add_argument("--intervalo", type=float, default=15,
                   help="não refaz se a última atualização tiver menos de N minutos")
    p.add_argument("--forcar", action="store_true", help="atualiza mesmo se for recente")

    p = sub.add_parser("matchup", help="cruzamento L5/L10 x DvP dos jogos de um dia")
    p.add_argument("--data", default=None, help="AAAA-MM-DD (padrão: hoje)")
    p.add_argument("--stat", default="pts", choices=MATCHUP_STATS)
    p.add_argument("--regras", default="config/matchup.yaml")
    p.add_argument("--limite", type=int, default=8, help="jogadores por jogo")
    p.add_argument("--params", default="config/projecao.yaml")

    p = sub.add_parser("linha", help="grava a linha da casa: linha \"Jamal Murray\" pts 24.5 --over 1.9")
    p.add_argument("jogador", help="nome ou parte do nome")
    p.add_argument("mercado", choices=MATCHUP_STATS)
    p.add_argument("linha", type=float, nargs="?", help="sem valor: apaga a linha")
    p.add_argument("--over", type=float, help="odd decimal do over")
    p.add_argument("--under", type=float, help="odd decimal do under")
    p.add_argument("--data", default=None, help="AAAA-MM-DD (padrão: hoje)")

    p = sub.add_parser("apostar", help="registra aposta: apostar \"Jamal Murray\" pts over 24.5 --odd 1.9")
    p.add_argument("jogador")
    p.add_argument("mercado", choices=MATCHUP_STATS)
    p.add_argument("lado", choices=["over", "under"])
    p.add_argument("linha", type=float)
    p.add_argument("--odd", type=float, required=True)
    p.add_argument("--unidades", type=float, default=1.0)
    p.add_argument("--casa")
    p.add_argument("--data", default=None, help="AAAA-MM-DD (padrão: hoje)")

    p = sub.add_parser("apostas", help="confere resultados e mostra o desempenho")
    p.add_argument("--desde", help="AAAA-MM-DD")

    p = sub.add_parser("calibrar", help="recalcula os parâmetros da projeção com os jogos já disputados")
    p.add_argument("season", type=int)
    p.add_argument("--desde", help="AAAA-MM-DD; o começo da temporada tem pouca amostra")
    p.add_argument("--passo", type=int, default=2, help="usa 1 dia a cada N (mais rápido)")
    p.add_argument("--validar", help="AAAA-MM-DD: calibra antes desta data e mede o erro depois")
    p.add_argument("--regras", default="config/matchup.yaml")
    p.add_argument("--params", default="config/projecao.yaml")
    p.add_argument("--nao-salvar", action="store_true")

    p = sub.add_parser("backtest", help="testa o cruzamento nos jogos que já aconteceram")
    p.add_argument("season", type=int)
    p.add_argument("--stat", default="pts", choices=MATCHUP_STATS)
    p.add_argument("--regras", default="config/matchup.yaml")
    p.add_argument("--passo", type=int, default=3, help="usa 1 dia a cada N (mais rápido)")
    p.add_argument("--desde", help="AAAA-MM-DD; o começo da temporada tem pouca amostra")

    p = sub.add_parser("usuario", help="usuários do site: criar, listar, senha, ativar, desativar")
    p.add_argument("acao", choices=("criar", "listar", "senha", "ativar", "desativar"))
    p.add_argument("login", nargs="?")
    p.add_argument("--nome")
    p.add_argument("--admin", action="store_true", help="cria como administrador")
    p.add_argument("--expira", help="AAAA-MM-DD: acesso até esta data")

    p = sub.add_parser("backup", help="cópia do banco em data/backup (mantém as 14 mais novas)")
    p.add_argument("--pasta", help="padrão: NBASTATS_BACKUP_DIR ou data/backup")
    p.add_argument("--manter", type=int, default=14)

    sub.add_parser("saude", help="avisa (código 1) se a carga falhou ou está velha")

    p = sub.add_parser("alertas", help="envia pelo Telegram mudanças de lesão e linhas com valor (favoritos)")
    p.add_argument("--simular", action="store_true", help="só mostra, não envia nem marca como enviado")
    p.add_argument("--data")

    p = sub.add_parser("resumo", help="resumo do dia pelo Telegram (jogos, desfalques, melhores chances)")
    p.add_argument("--simular", action="store_true", help="só mostra, não envia")
    p.add_argument("--data")

    p = sub.add_parser("previsoes", help="guarda a chance de cada jogador antes dos jogos (calibração)")
    p.add_argument("--data", help="AAAA-MM-DD (padrão: hoje)")

    p = sub.add_parser("calibracao", help="calibração pública: backtest de uma temporada fora da amostra")
    p.add_argument("season", type=int, nargs="?", help="padrão: a temporada mais recente da base")
    p.add_argument("--desde", help="AAAA-MM-DD; use datas depois do período calibrado")
    p.add_argument("--passo", type=int, default=1, help="usa 1 dia a cada N (mais rápido)")
    p.add_argument("--regras", default="config/matchup.yaml")

    args = parser.parse_args(argv)
    settings = get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)

    if args.cmd == "init-db":
        print(f"Banco pronto em {settings.db_path}")

    elif args.cmd in ("sync-season", "sync-daily"):
        fonte = args.fonte or settings.fonte
        print(f"Fonte: {fonte}")
        source = build_source(fonte, settings)
        if args.cmd == "sync-season":
            result = sync_season(conn, source, args.season)
            sync_shot_zones(conn, source, args.season)
        else:
            today = date.today()
            start = today - timedelta(days=args.days)
            result = sync_range(conn, source, start.isoformat(), today.isoformat())
        print(f"OK: {result['games']} jogos, {result['stats']} linhas de estatística, "
              f"{result['players']} perfis de jogador")
        if args.cmd == "sync-daily":
            agenda = sync_schedule(conn, source, _next_days(2))
            print(f"Agenda: {agenda['games']} jogos de hoje e amanhã")

    elif args.cmd == "sync-agenda":
        source = build_source(args.fonte or settings.fonte, settings)
        result = sync_schedule(conn, source, _next_days(args.dias))
        print(f"Agenda: {result['games']} jogos")

    elif args.cmd == "importar-dados":
        from .db import import_data
        n = import_data(conn, args.arquivo)
        print("Importado: " + ", ".join(f"{t} {k}" for t, k in n.items()))

    elif args.cmd == "noticias":
        from .ingest import sync_news
        result = sync_news(conn, build_news_source())
        print(f"Manchetes: {result['noticias']} · transações: {result['transacoes']}")

    elif args.cmd == "lesoes":
        result = sync_injuries(conn, build_injury_source())
        print(f"Injury report {result.get('report')}: {result['injuries']} jogadores, "
              f"{result['unmatched']} sem correspondência na base")

    elif args.cmd == "atualizar":
        source = build_source(args.fonte or settings.fonte, settings)
        result = refresh(conn, source, build_injury_source(),
                         min_interval_min=args.intervalo, force=args.forcar, news_source=build_news_source())
        if result["pulado"]:
            print(f"Já atualizado há {result['minutos']} min ({result['ultima']} UTC). "
                  "Use --forcar para refazer.")
        else:
            print(f"OK: {result['games']} jogos, {result['stats']} linhas, "
                  f"injury report {result['relatorio']} ({result['lesoes']} jogadores)")
        from .metrics.apostas import load_bet_config, settle_bets
        done = settle_bets(conn, load_bet_config())
        if done:
            print("Apostas conferidas: " + ", ".join(f"{v} {k}" for k, v in done.items()))

    elif args.cmd == "matchup":
        day = args.data or date.today().isoformat()
        report = matchup_report(conn, day, args.stat, load_matchup_rules(args.regras),
                                load_projection_params(args.params))
        if not report:
            print(f"Nenhum jogo em {day}. Rode `nbastats sync-agenda` para jogos futuros.")
            return 1
        for item in report:
            _print_matchup(item, args.stat, args.limite)

    elif args.cmd == "linha":
        from .metrics.linhas import find_player, save_line
        found = find_player(conn, args.jogador)
        if len(found) != 1:
            names = ", ".join(f"{f['first_name']} {f['last_name']}" for f in found[:8])
            print(f"{len(found)} jogadores com esse nome{': ' + names if names else ''}. Seja mais específico.")
            return 1
        pl, day = found[0], args.data or date.today().isoformat()
        save_line(conn, day, pl["id"], args.mercado, args.linha, args.over, args.under)
        acao = f"{args.linha:g}" if args.linha is not None else "apagada"
        print(f"{pl['first_name']} {pl['last_name']} · {args.mercado} · {day}: linha {acao}")

    elif args.cmd == "apostar":
        from .metrics.apostas import add_bet
        from .metrics.linhas import find_player, prob_over
        found = find_player(conn, args.jogador)
        if len(found) != 1:
            print(f"{len(found)} jogadores com esse nome. Seja mais específico.")
            return 1
        pl, day = found[0], args.data or date.today().isoformat()
        # fotografia do momento: projeção e chance do lado apostado
        params = load_projection_params()
        prob = proj = game_id = None
        for g in matchup_report(conn, day, args.mercado, load_matchup_rules(), params):
            for p in g["jogadores"]:
                if p["player_id"] == pl["id"]:
                    proj, game_id = p.get("proj"), g["jogo"]["id"]
                    po = prob_over(proj, args.linha, (params.get("mercados") or {}).get(args.mercado) or {})
                    prob = None if po is None else (po if args.lado == "over" else 1 - po)
        if game_id is None:
            print(f"Aviso: nenhum jogo de {pl['first_name']} {pl['last_name']} em {day} na base "
                  "(confira a data ou rode `nbastats atualizar`). A aposta fica pendente sem chance calculada.")
        bid = add_bet(conn, day=day, player_id=pl["id"], market=args.mercado, side=args.lado,
                      line=args.linha, odd=args.odd, units=args.unidades, game_id=game_id,
                      bookmaker=args.casa, prob=prob, proj=proj)
        extra = f" · chance {100 * prob:.0f}% · valor esperado {100 * (prob * args.odd - 1):+.1f}%" if prob else ""
        print(f"Aposta #{bid}: {pl['first_name']} {pl['last_name']} {args.lado} {args.linha:g} "
              f"{args.mercado} @ {args.odd} ({args.unidades:g} u){extra}")

    elif args.cmd == "apostas":
        from .metrics.apostas import load_bet_config, performance, settle_bets
        done = settle_bets(conn, load_bet_config())
        if done:
            print("Conferidas agora: " + ", ".join(f"{v} {k}" for k, v in done.items()))
        perf = performance(conn, since=args.desde)
        g = perf["geral"]
        print(f"{g['apostas']} apostas ({g['pendentes']} pendentes) · acerto {g['acerto_pct']}% "
              f"(chance média {g['chance_media_pct']}%) · lucro {g['lucro_unidades']:+} u · ROI {g['roi_pct']}%")
        for key in ("mercado", "unidades", "faixa_chance"):
            print(f"\npor {key}:")
            _table([{"grupo": k, **v} for k, v in perf[key].items()],
                   ["grupo", "conferidas", "acerto_pct", "chance_media_pct", "lucro_unidades", "roi_pct"])

    elif args.cmd == "calibrar":
        # sem os ajustes da Administração: o resultado é regravado em config/
        rules, params = load_matchup_rules(args.regras), load_projection_params(args.params, ajustes=False)
        print("Montando o histórico (pode levar alguns minutos)...", flush=True)
        data = build_dataset(conn, args.season, rules, params, start=args.desde, step=args.passo)
        if not data:
            print("Sem jogos suficientes.")
            return 1
        if args.validar:
            treino = [r for r in data if r["day"] < args.validar]
            teste = [r for r in data if r["day"] >= args.validar]
            print(f"Validação: calibra com {len(treino)} e mede em {len(teste)} jogador-jogo "
                  f"(desde {args.validar})\n")
            _table(evaluate(teste, calibrate(treino, params)),
                   ["mercado", "n", "erro_l10", "erro_projecao", "ganho_pct"], 30)
            print()
        new = calibrate(data, params)
        print(f"Calibrado com {len(data)} jogador-jogo. Erro no próprio período:")
        _table(evaluate(data, new), ["mercado", "n", "erro_l10", "erro_projecao", "ganho_pct"], 30)
        if not args.nao_salvar:
            save_projection_params(new, args.params,
                                   f"Calibrado em {date.today()} com a temporada {args.season} "
                                   f"({len(data)} jogador-jogo, desde {args.desde or 'o início'}).")
            print(f"\nParâmetros salvos em {args.params}")

    elif args.cmd == "backtest":
        res = backtest(conn, args.season, args.stat, load_matchup_rules(args.regras),
                       step=args.passo, start=args.desde)
        print(f"{args.stat}: {res['dias']} dias. real - L10 = quanto o jogador fez acima "
              "da própria média dos últimos 10 jogos.\n")
        rows = [{"grupo": f"nota {k}", **v} for k, v in res["classificacao"].items()]
        rows += [{"grupo": f"DvP {k}", **v} for k, v in res["dvp"].items()]
        _table(rows, ["grupo", "n", "real_menos_l10", "acima_do_l10"])

    elif args.cmd == "jogo":
        found = boxscore(conn, args.time_a, args.time_b, args.data)
        if not found:
            print("Jogo não encontrado na base. Já rodou o sync desse período?")
            return 1
        g = found["jogo"]
        print(f"{g['date']}  {g['visitor']} {g['visitor_team_score']} @ "
              f"{g['home']} {g['home_team_score']}  ({g['status']})\n")
        _table(found["jogadores"],
               ["time", "jogador", "min", "pts", "reb", "ast", "stl", "blk", "plus_minus"], 60)

    elif args.cmd == "ranking":
        rows = player_trends(conn, args.season, min_games=args.min_jogos)
        if rows and args.stat not in rows[0]:
            print(f"Estatística inválida: {args.stat}", file=sys.stderr)
            return 2
        rows.sort(key=lambda r: r[args.stat] or 0, reverse=True)
        _table(rows, ["jogador", "time", "jogos", "minutes", "pts", "reb", "ast", "stl", "blk"])

    elif args.cmd == "potencial":
        rows = rank_potenciais(conn, args.season, load_rules(args.regras))
        _table(rows, ["jogador", "time", "anos_de_liga", "jogos", "nota",
                      "pts", "pts_n", "reb", "reb_n", "ast", "ast_n"])

    elif args.cmd == "usuario":
        return _usuario(conn, args)

    elif args.cmd in ("alertas", "resumo"):
        return _alertas(conn, args)

    elif args.cmd == "previsoes":
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from .ingest import last_refresh
        from .metrics import calibracao as cb
        from .metrics.betaniag import tipoff
        from .metrics.painel import day_report
        day = args.data or date.today().isoformat()
        now_et = datetime.now(ZoneInfo("America/New_York")).replace(tzinfo=None)
        total = 0
        for stat in cb.MERCADOS_PREVISAO:
            report = day_report(conn, day, stat, last_refresh(conn), None)
            total += cb.save_predictions(conn, day, stat, report, now_et, tipoff)
        print(f"Previsões guardadas/atualizadas: {total} ({day})")

    elif args.cmd == "calibracao":
        from .metrics import calibracao as cb
        rules, params = load_matchup_rules(args.regras), load_projection_params()
        season = args.season or conn.execute("SELECT MAX(season) FROM games").fetchone()[0]
        print(f"Montando o histórico de {season} (pode levar alguns minutos)...", flush=True)
        data = build_dataset(conn, season, rules, params, start=args.desde, step=args.passo)
        if not data:
            print("Sem jogos suficientes.")
            return 1
        result = {s: cb.resumo(cb.backtest_points(data, params, s)) for s in MATCHUP_STATS}
        cb.save_backtest(conn, season, args.desde, result)
        rows = [{"mercado": s, "n": r["n"], "chance_media": r["chance_media_pct"], "acerto": r["acerto_pct"],
                 "brier": r["brier"]} for s, r in result.items() if r["n"]]
        _table(rows, ["mercado", "n", "chance_media", "acerto", "brier"], 50)

    elif args.cmd == "backup":
        import os
        from pathlib import Path

        from .metrics.sistema import backup
        pasta = args.pasta or os.getenv("NBASTATS_BACKUP_DIR") or str(Path(settings.db_path).parent / "backup")
        print(f"Backup: {backup(conn, pasta, args.manter)}")

    elif args.cmd == "saude":
        from .metrics.sistema import status_carga
        st = status_carga(conn)
        if st["alerta"]:
            print(f"ALERTA: {st['alerta']}", file=sys.stderr)
            return 1
        print(f"OK: última carga boa há {st['horas']} h ({st['ultima_ok']}).")
    return 0


def _alertas(conn, args) -> int:
    from . import notificar
    from .ingest import last_refresh
    from .metrics import alertas as al
    from .metrics import destaques as dq
    from .metrics import favoritos as fv
    from .metrics import noticias as nt
    from .metrics.painel import day_report
    from .metrics.sistema import status_carga

    cfg = al.load_alert_config()
    if not cfg.get("habilitado") and not args.simular:
        print("Alertas desligados (config/alertas.yaml: habilitado: false).")
        return 0
    day = args.data or date.today().isoformat()
    version = last_refresh(conn)
    reports = {s: day_report(conn, day, s, version, None) for s in dq.HOME_MARKETS}
    opps = dq.opportunities(reports, None)
    if args.cmd == "resumo":
        texto = al.daily_summary(day, dq.game_cards(reports, None), opps, status_carga(conn)["alerta"],
                                 cfg.get("resumo_top", 5))
        if args.simular:
            print(texto)
            return 0
        try:
            notificar.enviar(texto)
        except notificar.NaoConfigurado as exc:
            print(exc, file=sys.stderr)
            return 1
        print("Resumo enviado.")
        return 0
    favs = fv.list_favorites(conn, todos=True)  # o chat é um só: favoritos de todos
    team_ids = {r["abbreviation"]: r["id"] for r in conn.execute("SELECT id, abbreviation FROM teams")}
    alerts = al.injury_alerts(nt.changes(conn, day)["mudancas"], favs, team_ids, cfg, day)
    alerts += al.value_alerts(opps["com_odd"], favs, cfg, day)
    try:  # jogos em andamento (placar ao vivo do CDN da NBA)
        from .metrics import aovivo as av
        from .metrics.projecao import load_projection_params
        from .sources.nba_live import NbaLiveSource
        games = NbaLiveSource().live_games()
        if any(g["status"] == 2 for g in games):
            params = load_projection_params()
            live = {s: av.live_report(games, av.pre_from_report(reports[s]), s, params, "linha") for s in reports}
            alerts += al.live_alerts(live, favs, cfg, day)
    except Exception as exc:  # placar fora do ar: segue com os outros alertas
        print(f"Ao vivo indisponível: {exc}", file=sys.stderr)
    novos = al.pending(conn, alerts)
    if args.simular:
        print("\n".join(t for _, t in novos) or "(nenhum alerta novo)")
        return 0
    if not novos:
        print("Nenhum alerta novo.")
        return 0
    try:
        notificar.enviar("\n\n".join(t for _, t in novos))
    except notificar.NaoConfigurado as exc:
        print(exc, file=sys.stderr)
        return 1
    al.mark_sent(conn, [k for k, _ in novos])
    print(f"{len(novos)} alerta(s) enviado(s).")
    return 0


def _usuario(conn, args) -> int:
    """Usuários pela linha de comando. A senha é digitada (não aparece na tela
    nem fica no histórico do shell)."""
    from getpass import getpass

    from . import auth

    if args.acao == "listar":
        _table(auth.listar_usuarios(conn), ["id", "login", "nome", "papel", "ativo", "expira_em", "ultimo_acesso"], 200)
        return 0
    if not args.login:
        print("Informe o login.", file=sys.stderr)
        return 2
    row = conn.execute("SELECT id FROM users WHERE login = ?", (args.login.strip().lower(),)).fetchone()
    try:
        if args.acao == "criar":
            senha = getpass("Senha: ")
            if senha != getpass("Repita a senha: "):
                print("As senhas não conferem.", file=sys.stderr)
                return 2
            auth.criar_usuario(conn, args.login, senha, args.nome, "admin" if args.admin else "usuario", args.expira)
            print(f"Usuário {args.login} criado{' (admin)' if args.admin else ''}.")
            return 0
        if row is None:
            print(f"Usuário {args.login} não existe.", file=sys.stderr)
            return 1
        if args.acao == "senha":
            senha = getpass("Nova senha: ")
            if senha != getpass("Repita a senha: "):
                print("As senhas não conferem.", file=sys.stderr)
                return 2
            auth.definir_senha(conn, row["id"], senha)
            auth.encerrar_sessoes(conn, row["id"])
            print("Senha trocada; sessões abertas foram encerradas.")
        else:
            auth.alterar_usuario(conn, row["id"], ativo=args.acao == "ativar")
            print(f"Usuário {args.login} {'ativado' if args.acao == 'ativar' else 'desativado'}.")
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
