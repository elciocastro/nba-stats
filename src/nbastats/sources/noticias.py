"""Notícias (ESPN) e transações (NBA) para a página inicial.

- Manchetes: API pública do site da ESPN (``site.api.espn.com``), em inglês.
  Traz matérias, resumos e prévias de jogos e vídeos, com link e imagem.
- Transações: o JSON que alimenta nba.com/players/transactions (contratações,
  dispensas e trocas), com ids de time e jogador iguais aos da nba_api.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

import requests

ESPN_NEWS = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/news?limit=50"
NBA_MOVEMENT = "https://stats.nba.com/js/data/playermovement/NBA_Player_Movement.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (nbastats)", "Referer": "https://www.nba.com/"}

Get = Callable[[str], dict[str, Any]]


def _default_get(url: str) -> dict[str, Any]:
    r = requests.get(url, timeout=30, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def _int(v: Any) -> int | None:
    try:
        return int(v) if v not in (None, "", 0, 0.0) else None
    except (TypeError, ValueError):
        return None


def normalize_article(a: dict[str, Any]) -> dict[str, Any] | None:
    url = ((a.get("links") or {}).get("web") or {}).get("href")
    if not a.get("headline") or not url:
        return None
    imgs = [i.get("url") for i in a.get("images") or [] if i.get("url")]
    return {
        "id": str(a.get("id") or hashlib.sha1(url.encode()).hexdigest()[:16]),
        "published_at": a.get("published"),
        "tipo": a.get("type"),
        "titulo": a["headline"].strip(),
        "resumo": (a.get("description") or "").lstrip("— ").strip() or None,
        "url": url.replace("http://", "https://", 1),
        "imagem": imgs[0] if imgs else None,
        "times": [c.get("description") for c in a.get("categories") or []
                  if c.get("type") == "team" and c.get("description")],
    }


def normalize_movement(r: dict[str, Any]) -> dict[str, Any]:
    date = (r.get("TRANSACTION_DATE") or "")[:10]
    team, player = _int(r.get("TEAM_ID")), _int(r.get("PLAYER_ID"))
    grupo = r.get("GroupSort") or ""
    marca = hashlib.sha1((r.get("TRANSACTION_DESCRIPTION") or "").encode()).hexdigest()[:8]
    return {
        "id": f"{grupo}:{team or 0}:{player or 0}:{marca}",
        "date": date, "tipo": r.get("Transaction_Type"), "team_id": team, "player_id": player,
        "grupo": grupo, "descricao": (r.get("TRANSACTION_DESCRIPTION") or "").strip(),
    }


class NbaNewsFeed:
    def __init__(self, get: Get | None = None) -> None:
        self._get = get or _default_get

    def news(self) -> list[dict[str, Any]]:
        arts = (self._get(ESPN_NEWS) or {}).get("articles") or []
        return [n for n in (normalize_article(a) for a in arts) if n]

    def transactions(self, *, since: str) -> list[dict[str, Any]]:
        rows = ((self._get(NBA_MOVEMENT) or {}).get("NBA_Player_Movement") or {}).get("rows") or []
        return [m for m in (normalize_movement(r) for r in rows) if m["date"] >= since]
