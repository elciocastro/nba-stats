"""Textos dos alertas e do resumo do dia (o envio fica em ``nbastats.notificar``).

- **alertas**: mudança no injury report de jogador favorito (ou do time
  favorito) e linha da casa com valor esperado alto; cada alerta sai uma vez
  (tabela ``alerts_sent``);
- **resumo do dia**: jogos, principais desfalques, melhores oportunidades e
  o aviso de carga, numa mensagem só.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .. import ajustes as _aj

DEFAULT_ALERT_CONFIG = Path("config/alertas.yaml")
MK = {"pts": "pontos", "reb": "rebotes", "ast": "assistências", "pra": "PRA", "fg3m": "bolas de 3"}


def load_alert_config(path: str | Path = DEFAULT_ALERT_CONFIG, ajustes: bool = True) -> dict[str, Any]:
    p = Path(path)
    data = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.exists() else {}
    return _aj.aplicar("alertas", data) if ajustes and p == Path(DEFAULT_ALERT_CONFIG) else data


def _fav_ids(favs: dict[str, list[dict[str, Any]]]) -> tuple[set[int], set[int]]:
    return ({f["entity_id"] for f in favs.get("jogador", [])}, {f["entity_id"] for f in favs.get("time", [])})


def injury_alerts(changes: list[dict[str, Any]], favs: dict[str, list[dict[str, Any]]],
                  team_ids: dict[str, int], cfg: dict[str, Any], day: str) -> list[tuple[str, str]]:
    """(chave, texto) para mudanças de status relevantes."""
    players, teams = _fav_ids(favs)
    so_fav = cfg.get("so_favoritos", True)
    status = set(cfg.get("status_alerta") or ["Out", "Doubtful", "Questionable"])
    out = []
    for c in changes:
        fav = c.get("player_id") in players or team_ids.get(c.get("time") or "") in teams
        if so_fav and not fav:
            continue
        if c["tipo"] == "saiu" or (c.get("agora") is None):
            texto = f"✅ {c['jogador']} ({c.get('time') or '?'}) saiu do injury report (antes: {c.get('antes')})."
        elif c.get("agora") in status or c["tipo"] in ("melhorou", "piorou"):
            antes = f" (antes: {c['antes']})" if c.get("antes") else ""
            texto = f"🩹 {c['jogador']} ({c.get('time') or '?'}): {c['agora']}{antes}."
            if c.get("motivo"):
                texto += f" {c['motivo']}"
        else:
            continue
        out.append((f"lesao:{day}:{c['jogador']}:{c.get('agora')}", texto))
    return out


def value_alerts(opps: list[dict[str, Any]], favs: dict[str, list[dict[str, Any]]], cfg: dict[str, Any],
                 day: str) -> list[tuple[str, str]]:
    """Linhas da casa com valor esperado acima do mínimo (oportunidades com odd)."""
    players, _ = _fav_ids(favs)
    ev_min = cfg.get("ev_minimo", 0.05)
    out = []
    for o in opps:
        if o.get("ev") is None or o["ev"] < ev_min or o.get("linha_ref"):
            continue
        if cfg.get("so_favoritos", True) and o["player_id"] not in players:
            continue
        lado = "over" if o["lado"] == "over" else "under"
        out.append((f"valor:{day}:{o['player_id']}:{o['mercado']}:{o['linha']}:{lado}",
                    f"💰 {o['jogador']} ({o['time']} x {o['adversario']}): {lado} {o['linha']} "
                    f"{MK.get(o['mercado'], o['mercado'])} · chance {round(100 * o['chance'])}% · "
                    f"valor esperado {100 * o['ev']:+.1f}% · projeção {o['proj']:.1f}"))
    return out


def pending(conn: sqlite3.Connection, alerts: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Só os que ainda não foram enviados."""
    sent = {r[0] for r in conn.execute("SELECT key FROM alerts_sent")}
    seen, out = set(), []
    for k, t in alerts:
        if k not in sent and k not in seen:
            seen.add(k)
            out.append((k, t))
    return out


def mark_sent(conn: sqlite3.Connection, keys: list[str]) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.executemany("INSERT OR IGNORE INTO alerts_sent (key, sent_at) VALUES (?, ?)", [(k, now) for k in keys])
    conn.commit()


def daily_summary(day: str, cards: list[dict[str, Any]], opps: dict[str, list[dict[str, Any]]],
                  alerta_carga: str | None, top: int = 5) -> str:
    """Mensagem única com o dia: jogos, desfalques, oportunidades."""
    d = f"{day[8:10]}/{day[5:7]}"
    if not cards:
        return f"🏀 NBA {d}: sem jogos hoje."
    lines = [f"🏀 NBA {d}: {len(cards)} jogos", ""]
    for c in cards:
        fav = f" · favorito {c['favorito']} por {c['margem']:.0f}" if c.get("favorito") and c.get("margem") is not None else ""
        lines.append(f"• {c['fora']} @ {c['casa']} {c.get('status') or ''}{fav}")
        desf = [n for side in ("fora", "casa") for n in ((c.get("desfalques") or {}).get(side) or [])]
        if desf:
            lines.append(f"   desfalques: {', '.join(desf[:4])}{'…' if len(desf) > 4 else ''}")
    best = (opps.get("com_odd") or []) + (opps.get("sem_odd") or [])
    if best:
        lines += ["", "Melhores chances:"]
        for o in best[:top]:
            ev = f" · valor {100 * o['ev']:+.1f}%" if o.get("ev") is not None else ""
            ref = " (linha ref.)" if o.get("linha_ref") else ""
            lines.append(f"• {o['jogador']} {o['lado']} {o['linha']}{ref} {MK.get(o['mercado'], o['mercado'])}: "
                         f"{round(100 * o['chance'])}%{ev}")
    if alerta_carga:
        lines += ["", f"⚠ {alerta_carga}"]
    return "\n".join(lines)
