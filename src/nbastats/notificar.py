"""Envio pelo Telegram (Bot API, só biblioteca padrão). Token e chat no .env."""

from __future__ import annotations

import json
import os
import urllib.request

LIMITE = 4000  # o Telegram aceita até 4096 caracteres por mensagem


class NaoConfigurado(Exception):
    pass


def telegram_config() -> tuple[str, str]:
    token, chat = os.getenv("NBASTATS_TELEGRAM_TOKEN", ""), os.getenv("NBASTATS_TELEGRAM_CHAT", "")
    if not token or not chat:
        raise NaoConfigurado("Defina NBASTATS_TELEGRAM_TOKEN e NBASTATS_TELEGRAM_CHAT no .env.")
    return token, chat


def partes(texto: str, limite: int = LIMITE) -> list[str]:
    """Quebra em mensagens menores, nas linhas."""
    out, cur = [], ""
    for line in texto.splitlines():
        if len(cur) + len(line) + 1 > limite and cur:
            out.append(cur)
            cur = ""
        cur = f"{cur}\n{line}" if cur else line[:limite]
    return out + ([cur] if cur else [])


def enviar(texto: str, opener=urllib.request.urlopen) -> int:
    token, chat = telegram_config()
    n = 0
    for p in partes(texto):
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                     data=json.dumps({"chat_id": chat, "text": p, "disable_web_page_preview": True}).encode(),
                                     headers={"Content-Type": "application/json"})
        with opener(req, timeout=20) as r:
            if json.loads(r.read() or b"{}").get("ok") is not True:
                raise RuntimeError("Telegram recusou a mensagem.")
        n += 1
    return n
