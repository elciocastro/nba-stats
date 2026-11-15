"""Cruzamento de matchups: forma do jogador (L5/L10) x defesa do adversário
por posição (DvP), com ritmo de jogo, risco de blowout e desfalques.

Tudo é calculado com jogos ANTERIORES à data analisada. Assim, analisar um
dia que já passou mostra o que se sabia antes do jogo, e o resultado real
aparece ao lado para conferir o método.

Critérios e limites em config/matchup.yaml. Método em
docs/decisoes/0003-matchup-dvp.md.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

import yaml

DEFAULT_MATCHUP_RULES = Path("config/matchup.yaml")

# Mercados que dá para cruzar com o DvP. Os combinados (pra, pr...) e os de
# 2 pontos são calculados a partir do box score; dd/td valem 1 ou 0 por jogo,
# então a "média" deles é a frequência (0,4 = 4 em cada 10 jogos).
MATCHUP_STATS = (
    "pts", "reb", "ast", "pra", "pr", "pa", "ra",
    "fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta",
    "stl", "blk", "turnover", "dd", "td",
)
POSITIONS_5 = ("PG", "SG", "SF", "PF", "C")
INJURY_STATUSES = ("Out", "Doubtful", "Questionable", "Probable", "Available")

CRITERIOS = (
    "forma", "consistencia", "minutos", "uso",
    "dvp_temporada", "dvp_recente", "ritmo", "blowout",
)


def load_matchup_rules(path: str | Path = DEFAULT_MATCHUP_RULES) -> dict[str, Any]:
    rules = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    unknown = set(rules.get("estatisticas", [])) - set(MATCHUP_STATS)
    if unknown:
        raise ValueError(f"Estatística desconhecida: {sorted(unknown)}. Válidas: {MATCHUP_STATS}")
    unknown = set(rules.get("criterios", {})) - set(CRITERIOS)
    if unknown:
        raise ValueError(f"Critério desconhecido: {sorted(unknown)}. Válidos: {CRITERIOS}")
    return rules


def position_group(position: str | None, mapping: dict[str, str]) -> str | None:
    """'G-F' -> 'G' (pelo mapa do YAML). Sem posição ou fora do mapa -> None."""
    if not position:
        return None
    return mapping.get(position.strip())


def height_inches(height: str | None) -> int | None:
    """'6-9' -> 81."""
    try:
        feet, inches = str(height).split("-")
        return int(feet) * 12 + int(inches)
    except (ValueError, AttributeError):
        return None


def estimate_position(position: str | None, height: str | None, ast36: float | None,
                      reb36: float | None, cfg: dict[str, Any]) -> str | None:
    """Estima PG/SG/SF/PF/C a partir da posição oficial (G/F/C), altura e perfil.

    Nenhuma fonte gratuita traz as 5 posições; a regra é simples e fica no YAML:
    - G: PG se distribui (assistências por 36 min), senão SG
    - G-F: SF se alto, senão SG · F-G: SF
    - F: PF se alto ou reboteiro, senão SF · F-C: C se muito alto, senão PF
    - C e C-F: C
    """
    if not position:
        return None
    pos = position.strip()
    h = height_inches(height)
    if pos == "G":
        return "PG" if (ast36 or 0) >= cfg.get("pg_min_ast36", 5.5) else "SG"
    if pos == "G-F":
        return "SF" if h is not None and h >= cfg.get("sf_min_altura_pol", 79) else "SG"
    if pos == "F-G":
        return "SF"
    if pos == "F":
        tall = h is not None and h >= cfg.get("pf_min_altura_pol", 81)
        return "PF" if tall or (reb36 or 0) >= cfg.get("pf_min_reb36", 8.5) else "SF"
    if pos == "F-C":
        return "C" if h is not None and h >= cfg.get("c_min_altura_pol", 84) else "PF"
    if pos in ("C", "C-F"):
        return "C"
    return None


def _derive(r: dict[str, Any]) -> dict[str, Any]:
    """Acrescenta os mercados calculados a uma linha de box score."""
    pts, reb, ast = r.get("pts") or 0, r.get("reb") or 0, r.get("ast") or 0
    r["pra"], r["pr"], r["pa"], r["ra"] = pts + reb + ast, pts + reb, pts + ast, reb + ast
    r["fg2m"] = (r.get("fgm") or 0) - (r.get("fg3m") or 0)
    r["fg2a"] = (r.get("fga") or 0) - (r.get("fg3a") or 0)
    tens = sum(1 for k in ("pts", "reb", "ast", "stl", "blk") if (r.get(k) or 0) >= 10)
    r["dd"], r["td"] = int(tens >= 2), int(tens >= 3)
    return r


# ---------- leitura da base ----------

_COLS = ("minutes", "pts", "reb", "ast", "fg3m", "fg3a", "stl", "blk", "turnover",
         "fgm", "fga", "ftm", "fta", "oreb")


def _player_rows(conn: sqlite3.Connection, season: int, before: str) -> list[dict[str, Any]]:
    """Uma linha por jogador por jogo, com o adversário, antes da data."""
    cols = ", ".join(f"COALESCE(s.{c}, 0) AS {c}" for c in _COLS)
    sql = f"""
        SELECT s.game_id, g.date, s.player_id, s.team_id,
               CASE WHEN s.team_id = g.home_team_id THEN g.visitor_team_id
                    ELSE g.home_team_id END AS opp_id,
               CASE WHEN s.team_id = g.home_team_id THEN 1 ELSE 0 END AS em_casa,
               p.first_name || ' ' || p.last_name AS jogador, p.position, p.height,
               {cols}
        FROM player_game_stats s
        JOIN games g ON g.id = s.game_id
        JOIN players p ON p.id = s.player_id
        WHERE g.season = ? AND g.date < ? AND s.minutes > 0
        ORDER BY g.date DESC, g.id DESC
    """
    return [_derive(dict(r)) for r in conn.execute(sql, (season, before))]


def _team_games(rows: list[dict[str, Any]]) -> dict[tuple[int, int], dict[str, Any]]:
    """Totais de cada time em cada jogo: (game_id, team_id) -> totais."""
    out: dict[tuple[int, int], dict[str, Any]] = {}
    for r in rows:
        key = (r["game_id"], r["team_id"])
        t = out.setdefault(key, {"date": r["date"], "opp_id": r["opp_id"],
                                 **{c: 0.0 for c in _COLS}})
        for c in _COLS:
            t[c] += r[c]
    return out


def _used(r: dict[str, Any]) -> float:
    """Posses usadas (fórmula da taxa de uso): FGA + 0,44*FTA + TOV."""
    return r["fga"] + 0.44 * r["fta"] + r["turnover"]


def _possessions(t: dict[str, Any]) -> float:
    """Estimativa de posses de um time no jogo: FGA + 0,44*FTA - OREB + TOV."""
    return t["fga"] + 0.44 * t["fta"] - t["oreb"] + t["turnover"]


# ---------- jogador: L5, L10, temporada e uso ----------

def _usage(games: list[dict[str, Any]], teams: dict) -> float | None:
    """Taxa de uso (%) somando a janela, para um jogo de 3 minutos não distorcer.

    USG = 100 * soma(posses usadas) / soma(min * posses usadas do time / (min do time / 5))
    """
    num = den = 0.0
    for g in games:
        t = teams[(g["game_id"], g["team_id"])]
        if t["minutes"] <= 0:
            continue
        num += _used(g)
        den += g["minutes"] * _used(t) / (t["minutes"] / 5)
    return round(100 * num / den, 1) if den else None


def _avg(games: list[dict[str, Any]], col: str) -> float | None:
    return round(mean(g[col] for g in games), 1) if games else None


def player_form(rows: list[dict[str, Any]], teams: dict) -> dict[int, dict[str, Any]]:
    """L5, L10 e temporada de cada jogador. ``rows`` vem do mais recente ao mais antigo."""
    by_player: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_player[r["player_id"]].append(r)

    out = {}
    for pid, games in by_player.items():
        l5, l10 = games[:5], games[:10]
        info = {
            "player_id": pid,
            "jogador": games[0]["jogador"],
            "position": games[0]["position"],
            "height": games[0]["height"],
            "team_id": games[0]["team_id"],  # time do jogo mais recente
            "jogos": len(games),
            "usg_l5": _usage(l5, teams), "usg_l10": _usage(l10, teams),
            "usg_temp": _usage(games, teams),
            # jogos da temporada (mais recente primeiro), para barras e taxa de acerto
            "historico": [
                {"data": g["date"], "opp_id": g["opp_id"], "em_casa": bool(g["em_casa"]),
                 "minutes": g["minutes"], **{s: g[s] for s in MATCHUP_STATS}}
                for g in games
            ],
        }
        for col in ("minutes", *MATCHUP_STATS):
            info[f"{col}_l5"] = _avg(l5, col)
            info[f"{col}_l10"] = _avg(l10, col)
            info[f"{col}_temp"] = _avg(games, col)
        out[pid] = info
    return out


# ---------- defesa: DvP, ritmo e saldo ----------

def dvp(rows: list[dict[str, Any]], teams: dict, group_of: dict[int, str | None],
        since: str | None = None) -> dict[int, dict[str, dict[str, dict[str, float]]]]:
    """Quanto cada defesa cede por jogo a cada grupo de posição.

    Devolve dvp[time][grupo][stat] = {"media": x, "rank": n}, com rank 1 = cede
    menos (melhor defesa) e rank 30 = cede mais (alvo favorável). Jogo em que
    o adversário não usou ninguém daquele grupo conta como zero.
    """
    allowed: dict[tuple[int, int], dict[str, dict[str, float]]] = {}
    for (game_id, team_id), t in teams.items():
        if since and t["date"] < since:
            continue
        # a defesa é o adversário de quem atacou
        allowed.setdefault((game_id, t["opp_id"]), {})
    for r in rows:
        key = (r["game_id"], r["opp_id"])
        if key not in allowed:
            continue
        group = group_of.get(r["player_id"])
        if group is None:
            continue
        acc = allowed[key].setdefault(group, defaultdict(float))
        for s in MATCHUP_STATS:
            acc[s] += r[s]

    groups = sorted({g for g in group_of.values() if g})
    per_team: dict[int, list[dict[str, dict[str, float]]]] = defaultdict(list)
    for (_, defense), by_group in allowed.items():
        per_team[defense].append(by_group)

    result: dict[int, dict[str, dict[str, dict[str, float]]]] = {}
    for defense, games in per_team.items():
        result[defense] = {
            g: {s: {"media": round(mean(gm.get(g, {}).get(s, 0.0) for gm in games), 1)}
                for s in MATCHUP_STATS}
            for g in groups
        }
    for g in groups:
        for s in MATCHUP_STATS:
            ordered = sorted(result, key=lambda d: result[d][g][s]["media"])
            for rank, defense in enumerate(ordered, start=1):
                result[defense][g][s]["rank"] = rank
    return result


def team_context(teams: dict) -> dict[str, Any]:
    """Ritmo (posses por 48 min) e saldo médio de pontos de cada time."""
    by_game: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for (game_id, team_id), t in teams.items():
        by_game[game_id].append({"team_id": team_id, **t})

    pace: dict[int, list[float]] = defaultdict(list)
    margin: dict[int, list[float]] = defaultdict(list)
    for sides in by_game.values():
        if len(sides) != 2:
            continue
        a, b = sides
        poss = (_possessions(a) + _possessions(b)) / 2
        minutes = (a["minutes"] + b["minutes"]) / 2
        if minutes <= 0:
            continue
        game_pace = 48 * poss / (minutes / 5)
        for me, other in ((a, b), (b, a)):
            pace[me["team_id"]].append(game_pace)
            margin[me["team_id"]].append(me["pts"] - other["pts"])

    ritmo = {t: round(mean(v), 1) for t, v in pace.items()}
    saldo = {t: round(mean(v), 1) for t, v in margin.items()}
    liga = round(mean(ritmo.values()), 1) if ritmo else None
    return {"ritmo": ritmo, "saldo": saldo, "ritmo_liga": liga}


def absences(rows: list[dict[str, Any]], form: dict[int, dict[str, Any]],
             team_id: int, min_minutes: float) -> list[str]:
    """Jogadores importantes do time que não entraram no último jogo dele."""
    last_game = next((r["game_id"] for r in rows if r["team_id"] == team_id), None)
    if last_game is None:
        return []
    played = {r["player_id"] for r in rows if r["game_id"] == last_game}
    return sorted(
        f["jogador"] for pid, f in form.items()
        if f["team_id"] == team_id and pid not in played
        and (f["minutes_l10"] or 0) >= min_minutes
    )


# ---------- o cruzamento ----------

def _checks(p: dict[str, Any], stat: str, d: dict | None, d_rec: dict | None,
            ctx: dict[str, Any], home: int, away: int, crit: dict[str, Any]) -> dict[str, bool | None]:
    def get(name: str, key: str, default: float) -> float:
        return (crit.get(name) or {}).get(key, default)

    l5, l10, temp = p[f"{stat}_l5"], p[f"{stat}_l10"], p[f"{stat}_temp"]
    out: dict[str, bool | None] = {
        "forma": l5 >= l10 * get("forma", "fator_l5_sobre_l10", 1.0),
        "consistencia": l10 >= temp * get("consistencia", "fator_l10_sobre_temporada", 1.0),
        "minutos": p["minutes_l5"] >= p["minutes_l10"] - get("minutos", "queda_max", 3.0),
        "uso": (None if p["usg_l5"] is None or p["usg_l10"] is None
                else p["usg_l5"] >= p["usg_l10"] - get("uso", "queda_max", 3.0)),
        "dvp_temporada": None if d is None else d["rank"] >= get("dvp_temporada", "rank_min", 26),
        "dvp_recente": None if d_rec is None else d_rec["rank"] >= get("dvp_recente", "rank_min", 26),
    }
    ritmo, liga = ctx["ritmo"], ctx["ritmo_liga"]
    if home in ritmo and away in ritmo and liga is not None:
        out["ritmo"] = (ritmo[home] + ritmo[away]) / 2 > liga
    else:
        out["ritmo"] = None
    saldo = ctx["saldo"]
    if home in saldo and away in saldo:
        out["blowout"] = abs(saldo[home] - saldo[away]) <= get("blowout", "diferenca_saldo_max", 8.0)
    else:
        out["blowout"] = None
    # só entram os critérios configurados no YAML
    return {k: v for k, v in out.items() if k in crit}


def _label(nota: int, rules: dict[str, Any]) -> str:
    cls = rules.get("classificacao", {})
    if nota >= cls.get("forte", 7):
        return "forte"
    if nota >= cls.get("bom", 5):
        return "bom"
    return "fraco"


def _actual(conn: sqlite3.Connection, game_id: int) -> dict[int, dict[str, Any]]:
    cols = ", ".join(f"COALESCE({c}, 0) AS {c}" for c in _COLS)
    cur = conn.execute(
        f"SELECT player_id, {cols} FROM player_game_stats WHERE game_id = ? AND minutes > 0",
        (game_id,))
    return {r["player_id"]: _derive(dict(r)) for r in cur}


def estimated_positions(form: dict[int, dict[str, Any]], rules: dict[str, Any]) -> dict[int, str | None]:
    """PG/SG/SF/PF/C estimada de cada jogador (perfil da temporada até a data)."""
    cfg = rules.get("posicao_estimada", {})
    out = {}
    for pid, f in form.items():
        m = f["minutes_temp"] or 0
        ast36 = f["ast_temp"] * 36 / m if m else None
        reb36 = f["reb_temp"] * 36 / m if m else None
        out[pid] = estimate_position(f["position"], f["height"], ast36, reb36, cfg)
    return out


def player_groups(form: dict[int, dict[str, Any]], rules: dict[str, Any]) -> dict[int, str | None]:
    """Grupo de posição de cada jogador para o DvP.

    posicao_modo 'estimada' usa PG/SG/SF/PF/C (estimate_position); 'oficial'
    usa o mapa G/F/C do YAML.
    """
    if rules.get("posicao_modo", "oficial") == "estimada":
        return estimated_positions(form, rules)
    mapping = rules.get("posicoes", {})
    return {pid: position_group(f["position"], mapping) for pid, f in form.items()}


def injury_status(conn: sqlite3.Connection, day: str) -> dict[str, Any]:
    """Status de cada jogador no injury report mais recente que cobre o dia.

    Devolve {'publicado': 'AAAA-MM-DDTHH:MM' ou None, 'jogadores': {player_id:
    {'status', 'motivo'}}}. Sem relatório para o dia (datas antigas, por
    exemplo), a análise usa só quem não jogou a última partida.
    """
    row = conn.execute(
        "SELECT r.id, r.published_at FROM injury_reports r WHERE EXISTS ("
        " SELECT 1 FROM injuries i WHERE i.report_id = r.id AND i.game_date = ?)"
        " ORDER BY r.id DESC LIMIT 1", (day,)).fetchone()
    if row is None:
        return {"publicado": None, "jogadores": {}}
    cur = conn.execute(
        "SELECT player_id, status, reason FROM injuries"
        " WHERE report_id = ? AND game_date = ? AND player_id IS NOT NULL", (row["id"], day))
    return {"publicado": row["published_at"],
            "jogadores": {r["player_id"]: {"status": r["status"], "motivo": r["reason"]}
                          for r in cur}}


def games_on(conn: sqlite3.Connection, day: str) -> list[dict[str, Any]]:
    sql = """
        SELECT g.*, h.abbreviation AS home, v.abbreviation AS visitor
        FROM games g
        JOIN teams h ON h.id = g.home_team_id
        JOIN teams v ON v.id = g.visitor_team_id
        WHERE g.date = ?
        ORDER BY g.id
    """
    return [dict(r) for r in conn.execute(sql, (day,))]


def matchup_report(conn: sqlite3.Connection, day: str, stat: str,
                   rules: dict[str, Any], params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Os jogos do dia com o cruzamento de cada jogador para ``stat``.

    Cada jogo traz contexto (ritmo, saldo, desfalques) e a lista de jogadores
    com L5/L10/temporada, uso, DvP do adversário, critérios, nota e, se o jogo
    já aconteceu, o valor real.

    Com ``params`` (config/projecao.yaml), cada jogador ganha a projeção e a
    comparação com/sem os companheiros desfalcados, e cada jogo ganha margem
    esperada e risco de blowout (metrics/projecao.py).
    """
    from . import projecao as pj  # importação tardia: projecao usa este módulo
    from . import zonas as zn
    if stat not in MATCHUP_STATS:
        raise ValueError(f"Estatística inválida: {stat}. Válidas: {MATCHUP_STATS}")
    games = games_on(conn, day)
    if not games:
        return []

    filtros = rules.get("filtros", {})
    crit = rules.get("criterios", {})
    lesoes = rules.get("lesoes", {})
    tirar = set(lesoes.get("tirar", ["Out"]))
    min_desf_lesao = lesoes.get("desfalque_min_minutos", 15)
    injuries = injury_status(conn, day)
    since = (date.fromisoformat(day) - timedelta(days=rules.get("dvp_recente_dias", 15))).isoformat()
    abbr = {r["id"]: r["abbreviation"] for r in conn.execute("SELECT id, abbreviation FROM teams")}

    report = []
    for season in sorted({g["season"] for g in games}):
        rows = _player_rows(conn, season, day)
        teams = _team_games(rows)
        form = player_form(rows, teams)
        group_of = player_groups(form, rules)
        pos_est = estimated_positions(form, rules)
        dvp_temp = dvp(rows, teams, group_of)
        dvp_rec = dvp(rows, teams, group_of, since=since)
        ctx = team_context(teams)
        if params is not None:
            prior = pj.previous_season(conn, season)
            aus_cfg = params.get("ausencia") or {}
            recent = pj.recent_players(rows, aus_cfg.get("jogos_recentes", 3))
            league = pj.league_allowed(dvp_temp)
            n_games: dict[int, int] = defaultdict(int)
            for (_, t) in teams:
                n_games[t] += 1
            last_played = {}
            for r in rows:
                last_played.setdefault(r["team_id"], r["game_id"])
            in_last = {(r["team_id"], r["player_id"]) for r in rows
                       if last_played.get(r["team_id"]) == r["game_id"]}
            zones = zn.load_zones(conn, season)
            only = zn.THREE if stat in ("fg3m", "fg3a") else (
                ("aro", "garrafao", "meia") if stat in ("fg2m", "fg2a") else None)

        for g in (x for x in games if x["season"] == season):
            home, away = g["home_team_id"], g["visitor_team_id"]
            actual = _actual(conn, g["id"])
            min_desf = rules.get("desfalque_min_minutos", 25)
            desf = {"casa": absences(rows, form, home, min_desf),
                    "fora": absences(rows, form, away, min_desf)}
            fora_ultimo = set(desf["casa"]) | set(desf["fora"])
            if injuries["publicado"]:
                # com relatório oficial, os desfalques vêm dele
                desf = {side: sorted(
                    f"{form[pid]['jogador']} ({inj['status']})"
                    for pid, inj in injuries["jogadores"].items()
                    if pid in form and form[pid]["team_id"] == team
                    and inj["status"] in ("Out", "Doubtful", "Questionable")
                    and (form[pid]["minutes_l10"] or 0) >= min_desf_lesao)
                    for side, team in (("casa", home), ("fora", away))}
            proj_ctx: dict[str, Any] = {}
            if params is not None:
                # ausências novas (quem estava jogando): relatório oficial, box score
                # do jogo se já aconteceu, ou quem não jogou a última partida
                min_aus = aus_cfg.get("min_minutos_l10", 15)
                status_fora = set(aus_cfg.get("status", ["Out", "Doubtful"]))
                absent = {}
                for t in (home, away):
                    cand = [q for q in recent.get(t, set())
                            if q in form and (form[q]["minutes_l10"] or 0) >= min_aus]
                    if injuries["publicado"]:
                        absent[t] = [q for q in cand
                                     if (injuries["jogadores"].get(q) or {}).get("status") in status_fora]
                    elif actual:
                        absent[t] = [q for q in cand if q not in actual]
                    else:
                        absent[t] = [q for q in cand if (t, q) not in in_last]
                share = {t: pj.absence_share(form, recent.get(t, set()), absent[t]) for t in absent}
                lost = {t: pj.absent_production(form, absent[t]) for t in absent}
                margin = pj.expected_margin(ctx["saldo"].get(home), ctx["saldo"].get(away), True,
                                            lost[home], lost[away], params)
                proj_ctx = {"absent": absent, "share": share, "lost": lost, "margin": margin,
                            "blowout": pj.blowout_probability(margin, params)}
            players = []
            for p in form.values():
                if p["team_id"] not in (home, away):
                    continue
                inj = injuries["jogadores"].get(p["player_id"])
                if inj and inj["status"] in tirar and actual.get(p["player_id"]) is None:
                    continue  # fora pelo relatório (se jogou mesmo assim, aparece)
                if p["jogos"] < filtros.get("min_jogos", 5):
                    continue
                if (p["minutes_l10"] or 0) < filtros.get("min_minutos_l10", 20):
                    continue
                opp = away if p["team_id"] == home else home
                group = group_of.get(p["player_id"])
                d = dvp_temp.get(opp, {}).get(group, {}).get(stat) if group else None
                d_rec = dvp_rec.get(opp, {}).get(group, {}).get(stat) if group else None
                checks = _checks(p, stat, d, d_rec, ctx, home, away, crit)
                nota = sum(1 for v in checks.values() if v)
                real = actual.get(p["player_id"])
                extra: dict[str, Any] = {}
                if params is not None:
                    team = p["team_id"]
                    pr = pj.project(p, stat, params, prior=prior.get(p["player_id"]),
                                    dvp_media=d["media"] if d else None,
                                    liga_media=league.get(group, {}).get(stat) if group else None,
                                    opp_games=n_games[opp], ritmo_time=ctx["ritmo"].get(team),
                                    ritmo_adv=ctx["ritmo"].get(opp),
                                    ausencia=proj_ctx["share"].get(team, 0.0))
                    mates = sorted((q for q in proj_ctx["absent"].get(team, []) if q != p["player_id"]),
                                   key=lambda q: form[q]["pra_l10"] or 0, reverse=True)[:2]
                    ww = pj.with_without(rows, p["player_id"], mates, stat)
                    zm = zn.zone_matchup(zones, p["player_id"], opp, only)
                    extra = {
                        "zonas": zm,
                        "encaixe_zonas": zm["encaixe_pp"] if zm else None,
                        "proj": pr["valor"] if pr else None,
                        "proj_detalhe": pr,
                        "proj_vs_l10": round(pr["valor"] - p[f"{stat}_l10"], 2) if pr else None,
                        "com_sem": [{"companheiro": form[q]["jogador"], **ww[q]} for q in mates if q in ww],
                    }
                players.append({
                    **extra,
                    "historico": p["historico"],
                    "adversario_id": opp,
                    "game_id": g["id"],
                    "time_id": p["team_id"],
                    "player_id": p["player_id"],
                    "jogador": p["jogador"],
                    "time": abbr.get(p["team_id"]),
                    "adversario": abbr.get(opp),
                    "posicao": p["position"],
                    "grupo": group,
                    "posicao_est": pos_est.get(p["player_id"]),
                    "jogos": p["jogos"],
                    "min_l5": p["minutes_l5"], "min_l10": p["minutes_l10"],
                    "usg_l5": p["usg_l5"], "usg_l10": p["usg_l10"],
                    "temporada": p[f"{stat}_temp"], "l10": p[f"{stat}_l10"], "l5": p[f"{stat}_l5"],
                    "dvp": d["media"] if d else None, "dvp_rank": d["rank"] if d else None,
                    "dvp_rec": d_rec["media"] if d_rec else None,
                    "dvp_rec_rank": d_rec["rank"] if d_rec else None,
                    "criterios": checks,
                    "nota": nota,
                    "nota_max": sum(1 for v in checks.values() if v is not None),
                    "classificacao": _label(nota, rules),
                    # não jogou a última partida do time: confirmar se joga hoje
                    "fora_ultimo_jogo": p["jogador"] in fora_ultimo,
                    "lesao": inj["status"] if inj else None,
                    "lesao_motivo": inj["motivo"] if inj else None,
                    "real": real[stat] if real else None,
                    "min_real": real["minutes"] if real else None,
                })
            if params is not None:
                # quem a projeção põe mais acima da própria média recente
                players.sort(key=lambda r: (r.get("proj_vs_l10") or 0) / max(r["l10"] or 0, 1),
                             reverse=True)
            else:
                players.sort(key=lambda r: (r["nota"], r["dvp_rank"] or 0, r["l5"] or 0), reverse=True)
            report.append({
                "jogo": g,
                "ritmo": {"casa": ctx["ritmo"].get(home), "fora": ctx["ritmo"].get(away),
                          "liga": ctx["ritmo_liga"]},
                "saldo": {"casa": ctx["saldo"].get(home), "fora": ctx["saldo"].get(away)},
                "desfalques": desf,
                "injury_report": injuries["publicado"],
                "margem_esperada": (round(proj_ctx["margin"], 1)
                                    if proj_ctx.get("margin") is not None else None),
                "risco_blowout": (round(proj_ctx["blowout"], 2)
                                  if proj_ctx.get("blowout") is not None else None),
                "producao_fora": ({"casa": round(proj_ctx["share"][home], 2),
                                   "fora": round(proj_ctx["share"][away], 2)} if proj_ctx else None),
                "jogadores": players,
            })
    return report


def backtest(conn: sqlite3.Connection, season: int, stat: str, rules: dict[str, Any],
             step: int = 1, start: str | None = None) -> dict[str, Any]:
    """Testa o método nos jogos que já aconteceram.

    Para cada dia (um a cada ``step``), roda o cruzamento como se fosse antes
    do jogo e compara com o que o jogador fez. A pergunta é: quem o método
    marca como favorável supera a própria média L10 mais do que os outros?
    """
    sql = "SELECT DISTINCT date FROM games WHERE season = ? AND postseason = 0"
    params: list[Any] = [season]
    if start:
        sql += " AND date >= ?"
        params.append(start)
    days = [r[0] for r in conn.execute(sql + " ORDER BY date", params)][::max(step, 1)]

    by_label: dict[str, list[float]] = defaultdict(list)
    by_dvp: dict[str, list[float]] = defaultdict(list)
    rank_min = (rules.get("criterios", {}).get("dvp_temporada") or {}).get("rank_min", 26)
    n_teams = 30
    for day in days:
        for g in matchup_report(conn, day, stat, rules):
            for p in g["jogadores"]:
                if p["real"] is None:
                    continue
                diff = p["real"] - p["l10"]
                by_label[p["classificacao"]].append(diff)
                r = p["dvp_rank"]
                if r is None:
                    continue
                faixa = ("piores" if r >= rank_min
                         else "melhores" if r <= n_teams + 1 - rank_min else "meio")
                by_dvp[faixa].append(diff)

    def resume(values: list[float]) -> dict[str, Any]:
        if not values:
            return {"n": 0, "real_menos_l10": None, "acima_do_l10": None}
        return {"n": len(values), "real_menos_l10": round(mean(values), 2),
                "acima_do_l10": round(100 * sum(v > 0 for v in values) / len(values))}

    return {
        "dias": len(days),
        "classificacao": {k: resume(by_label[k]) for k in ("forte", "bom", "fraco")},
        "dvp": {k: resume(by_dvp[k]) for k in ("piores", "meio", "melhores")},
    }


def dvp_table(conn: sqlite3.Connection, season: int, day: str, stat: str,
              rules: dict[str, Any], recent: bool = False) -> list[dict[str, Any]]:
    """Ranking das 30 defesas por grupo de posição (para a tela de DvP)."""
    rows = _player_rows(conn, season, day)
    teams = _team_games(rows)
    group_of = player_groups(player_form(rows, teams), rules)
    since = None
    if recent:
        since = (date.fromisoformat(day) - timedelta(days=rules.get("dvp_recente_dias", 15))).isoformat()
    table = dvp(rows, teams, group_of, since=since)
    abbr = {r["id"]: r["abbreviation"] for r in conn.execute("SELECT id, abbreviation FROM teams")}
    out = []
    for team_id, groups in table.items():
        row: dict[str, Any] = {"time": abbr.get(team_id)}
        for g, stats in groups.items():
            row[g] = stats[stat]["media"]
            row[f"{g}_rank"] = stats[stat]["rank"]
        out.append(row)
    return sorted(out, key=lambda r: r["time"] or "")
