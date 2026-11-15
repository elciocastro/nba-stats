"""Placar ao vivo da NBA (cdn.nba.com/static/json/liveData via nba_api.live).

Diferente do stats.nba.com, o CDN responde de servidores na nuvem. As
funções de busca são injetáveis para os testes usarem respostas gravadas.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

Fetch = Callable[[], dict[str, Any]]
FetchBox = Callable[[str], dict[str, Any]]


def _default_scoreboard() -> dict[str, Any]:
    from nba_api.live.nba.endpoints import scoreboard
    return scoreboard.ScoreBoard(timeout=20).get_dict()


def _default_boxscore(game_id: str) -> dict[str, Any]:
    from nba_api.live.nba.endpoints import boxscore
    return boxscore.BoxScore(game_id, timeout=20).get_dict()


_DUR = re.compile(r"PT(?:(\d+)M)?(?:([\d.]+)S)?")


def duration_seconds(text: str | None) -> float:
    """'PT07M31.00S' -> 451.0; vazio -> 0."""
    m = _DUR.fullmatch(text or "")
    if not m:
        return 0.0
    return int(m.group(1) or 0) * 60 + float(m.group(2) or 0)


def _player(p: dict[str, Any], team_id: int) -> dict[str, Any]:
    s = p.get("statistics") or {}
    return {
        "player_id": p["personId"], "team_id": team_id, "nome": p.get("name"),
        "minutos": round(duration_seconds(s.get("minutes")) / 60, 1),
        "pts": s.get("points", 0), "reb": s.get("reboundsTotal", 0), "ast": s.get("assists", 0),
        "fg3m": s.get("threePointersMade", 0), "fg3a": s.get("threePointersAttempted", 0),
        "ftm": s.get("freeThrowsMade", 0), "fta": s.get("freeThrowsAttempted", 0),
        "fgm": s.get("fieldGoalsMade", 0), "fga": s.get("fieldGoalsAttempted", 0),
        "stl": s.get("steals", 0), "blk": s.get("blocks", 0), "turnover": s.get("turnovers", 0),
        "faltas": s.get("foulsPersonal", 0), "em_quadra": p.get("oncourt") == "1",
        "titular": p.get("starter") == "1", "ativo": p.get("status") == "ACTIVE",
    }


def normalize_game(g: dict[str, Any], box: dict[str, Any] | None, day: str) -> dict[str, Any]:
    home, away = g["homeTeam"], g["awayTeam"]
    out = {
        "game_id": int(g["gameId"]), "data": day, "status": g["gameStatus"],
        "status_texto": (g.get("gameStatusText") or "").strip(), "periodo": g.get("period", 0),
        "relogio_seg": duration_seconds(g.get("gameClock")),
        "casa": home["teamTricode"], "fora": away["teamTricode"],
        "casa_id": home["teamId"], "fora_id": away["teamId"],
        "placar_casa": home.get("score"), "placar_fora": away.get("score"), "jogadores": [],
    }
    if box:
        game = box.get("game") or box
        # o box score de cada jogo costuma estar mais atual que o placar geral
        if game.get("gameClock") is not None:
            out["relogio_seg"] = duration_seconds(game["gameClock"])
        for k_out, k_in in (("periodo", "period"), ("status", "gameStatus")):
            if game.get(k_in) is not None:
                out[k_out] = game[k_in]
        if (game.get("gameStatusText") or "").strip():
            out["status_texto"] = game["gameStatusText"].strip()
        for k_out, side in (("placar_casa", "homeTeam"), ("placar_fora", "awayTeam")):
            if (game.get(side) or {}).get("score") is not None:
                out[k_out] = game[side]["score"]
        for side in ("homeTeam", "awayTeam"):
            t = game.get(side) or {}
            out["jogadores"] += [_player(p, t.get("teamId")) for p in t.get("players") or []]
    return out


class NbaLiveSource:
    def __init__(self, scoreboard: Fetch | None = None, boxscore: FetchBox | None = None):
        self._scoreboard = scoreboard or _default_scoreboard
        self._boxscore = boxscore or _default_boxscore

    def live_games(self) -> list[dict[str, Any]]:
        sb = self._scoreboard()["scoreboard"]
        day = sb.get("gameDate")
        out = []
        for g in sb.get("games") or []:
            box = self._boxscore(g["gameId"]) if g.get("gameStatus", 1) >= 2 else None
            out.append(normalize_game(g, box, day))
        return out
