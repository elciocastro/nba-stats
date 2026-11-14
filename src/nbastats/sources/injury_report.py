"""Injury report oficial da NBA (PDF publicado a cada 15 minutos).

Página com a lista: https://official.nba.com/nba-injury-report-2026-27-season/
Cada PDF é uma tabela: GameDate, GameTime, Matchup, Team, PlayerName,
CurrentStatus, Reason. Células vazias repetem o valor da linha de cima, e um
motivo longo quebra em duas linhas centralizadas na altura do jogador. Por
isso a leitura usa a posição de cada palavra na página, não o texto corrido.

Os nomes vêm sem espaço ('MurphyIII,Trey', 'NewOrleansPelicans'); quem
liga com a base é a ingestão (normalize_name).
"""

from __future__ import annotations

import io
import re
import time
import unicodedata
from datetime import datetime
from typing import Any, Callable

import requests

LIST_URL = "https://official.nba.com/nba-injury-report-{start}-{end}-season/"
_PDF_RE = re.compile(r"https?://[^\"']+?Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{2})_(\d{2})(AM|PM)\.pdf")
_TITLE_RE = re.compile(r"Injury Report:\s*(\d{2}/\d{2}/\d{2})\s+(\d{2}:\d{2})\s*(AM|PM)")

COLUMNS = ("GameDate", "GameTime", "Matchup", "Team", "PlayerName", "CurrentStatus", "Reason")
_KEYS = ("game_date", "game_time", "matchup", "team", "player_name", "status", "reason")
STATUSES = ("Out", "Doubtful", "Questionable", "Probable", "Available")
# distância máxima (em pontos do PDF) entre um pedaço de motivo e a linha do jogador
_MAX_GAP = 14


def normalize_name(text: str | None) -> str:
    """'Murphy III, Trey', 'MurphyIII,Trey' e 'Dëmin' viram chaves comparáveis."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if c.isalnum()).lower()


def season_page(season: int) -> str:
    return LIST_URL.format(start=season, end=str(season + 1)[-2:])


def latest_pdf_url(html: str) -> tuple[str, str] | None:
    """O PDF mais recente citado na página: (url, 'AAAA-MM-DDTHH:MM' em ET)."""
    best = None
    for m in _PDF_RE.finditer(html):
        day, hh, mm, ampm = m.groups()
        hour = int(hh) % 12 + (12 if ampm == "PM" else 0)
        stamp = f"{day}T{hour:02d}:{mm}"
        if best is None or stamp > best[1]:
            best = (m.group(0), stamp)
    return best


def _published_at(text: str) -> str | None:
    m = _TITLE_RE.search(text)
    if not m:
        return None
    d = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%m/%d/%y %I:%M %p")
    return d.strftime("%Y-%m-%dT%H:%M")


def _column_edges(words: list[dict[str, Any]]) -> list[float] | None:
    header = {w["text"]: w["x0"] for w in words if w["text"] in COLUMNS}
    if len(header) < len(COLUMNS):
        return None
    return [header[c] - 2 for c in COLUMNS]


def _column(x0: float, edges: list[float]) -> int:
    col = 0
    for i, edge in enumerate(edges):
        if x0 >= edge:
            col = i
    return col


def _lines(words: list[dict[str, Any]], edges: list[float]) -> list[dict[str, Any]]:
    """Agrupa palavras pela altura e separa por coluna."""
    lines: list[dict[str, Any]] = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if lines and abs(lines[-1]["top"] - w["top"]) < 2:
            line = lines[-1]
        else:
            line = {"top": w["top"], "cells": [""] * len(COLUMNS)}
            lines.append(line)
        i = _column(w["x0"], edges)
        line["cells"][i] = (line["cells"][i] + " " + w["text"]).strip()
    return lines


def parse_pages(pages: list[list[dict[str, Any]]], first_text: str = "") -> dict[str, Any]:
    """Palavras de cada página (formato do pdfplumber) -> linhas do relatório."""
    rows: list[dict[str, Any]] = []
    edges = None
    carry = {k: "" for k in _KEYS[:4]}
    for words in pages:
        edges = _column_edges(words) or edges
        if edges is None:
            continue
        players: list[dict[str, Any]] = []
        orphans: list[tuple[float, str]] = []
        for line in _lines(words, edges):
            cells = dict(zip(_KEYS, line["cells"]))
            if cells["game_date"] == "GameDate" or "Injury Report:" in " ".join(line["cells"]):
                continue
            if cells["game_date"].startswith("Page"):
                continue
            for k in _KEYS[:4]:  # célula vazia repete a de cima
                if cells[k]:
                    carry[k] = cells[k]
                    if k == "game_date":  # novo dia: hora e jogo também mudam
                        carry.update({"game_time": "", "matchup": "", "team": ""})
            if cells["player_name"]:
                players.append({"top": line["top"], **carry,
                                "player_name": cells["player_name"],
                                "status": cells["status"], "reason": [cells["reason"]] if cells["reason"] else []})
            elif cells["reason"]:
                orphans.append((line["top"], cells["reason"]))
        # pedaço de motivo quebrado vai para o jogador mais próximo na altura
        for top, text in orphans:
            near = min(players, key=lambda p: abs(p["top"] - top), default=None)
            if near is not None and abs(near["top"] - top) <= _MAX_GAP:
                near["reason"].append((top, text))
        for p in players:
            parts = [x for x in p["reason"] if isinstance(x, str)]
            pieces = sorted((x for x in p["reason"] if isinstance(x, tuple)), key=lambda t: t[0])
            above = [t for top, t in pieces if top < p["top"]]
            below = [t for top, t in pieces if top >= p["top"]]
            p["reason"] = "".join(above + parts + below) or None
            p.pop("top")
            rows.append(p)
    for r in rows:
        r["game_date"] = _iso_date(r["game_date"])
    return {"published_at": _published_at(first_text), "rows": rows}


def _iso_date(us: str) -> str | None:
    try:
        return datetime.strptime(us, "%m/%d/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_pdf(content: bytes) -> dict[str, Any]:
    import pdfplumber  # dependência opcional (extra "injury")

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        pages = [p.extract_words() for p in pdf.pages]
        first = pdf.pages[0].extract_text() or "" if pdf.pages else ""
    return parse_pages(pages, first)


class NbaInjuryReport:
    """Busca o relatório mais recente da temporada."""

    def __init__(self, season: int, get: Callable[[str], requests.Response] | None = None) -> None:
        self._season = season
        self._get = get or (lambda url: requests.get(
            url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (nbastats)"}))

    def latest(self) -> dict[str, Any] | None:
        page = self._get(season_page(self._season))
        page.raise_for_status()
        found = latest_pdf_url(page.text)
        if not found:
            return None
        url, stamp = found
        time.sleep(0.5)
        pdf = self._get(url)
        pdf.raise_for_status()
        report = parse_pdf(pdf.content)
        report["url"] = url
        report["published_at"] = report["published_at"] or stamp
        return report
