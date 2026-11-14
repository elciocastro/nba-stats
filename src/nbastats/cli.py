"""Linha de comando: nbastats <comando>."""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from . import db
from .config import get_settings
from .ingest import sync_range, sync_season
from .metrics import boxscore, load_rules, player_trends, rank_potenciais
from .sources import FONTES, build_source


def _table(rows: list[dict], cols: list[str], limit: int = 25) -> None:
    if not rows:
        print("(sem dados)")
        return
    rows = rows[:limit]
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    print("  ".join(c.ljust(widths[c]) for c in cols))
    for r in rows:
        print("  ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols))


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
        else:
            today = date.today()
            start = today - timedelta(days=args.days)
            result = sync_range(conn, source, start.isoformat(), today.isoformat())
        print(f"OK: {result['games']} jogos, {result['stats']} linhas de estatística")

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
