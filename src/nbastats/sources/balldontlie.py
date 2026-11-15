"""Cliente da API BALLDONTLIE (https://docs.balldontlie.io).

- Autenticação: header ``Authorization: <chave>`` (sem prefixo).
- Paginação por cursor: ``per_page`` até 100 e ``meta.next_cursor``.
- /teams e /games funcionam no plano Free; /stats exige ALL-STAR ou GOAT.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import requests

BASE_URL = "https://api.balldontlie.io/v1"


class BallDontLieError(RuntimeError):
    pass


class BallDontLie:
    def __init__(
        self,
        api_key: str,
        rpm: int = 60,
        session: requests.Session | None = None,
        base_url: str = BASE_URL,
        sleep=time.sleep,
    ) -> None:
        if not api_key:
            raise BallDontLieError(
                "BALLDONTLIE_API_KEY não definida. Copie .env.example para .env e preencha."
            )
        self._session = session or requests.Session()
        self._headers = {"Authorization": api_key}
        self._base_url = base_url.rstrip("/")
        self._interval = 60.0 / max(rpm, 1)
        self._sleep = sleep
        self._last_call = 0.0

    # ---------- HTTP ----------

    def _throttle(self) -> None:
        wait = self._interval - (time.monotonic() - self._last_call)
        if wait > 0:
            self._sleep(wait)
        self._last_call = time.monotonic()

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        for attempt in range(5):
            self._throttle()
            resp = self._session.get(url, headers=self._headers, params=params, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 401:
                raise BallDontLieError(
                    f"401 em {path}: chave inválida ou plano sem acesso a este endpoint "
                    "(/stats exige o plano ALL-STAR)."
                )
            if resp.status_code == 429 or resp.status_code >= 500:
                self._sleep(min(2**attempt * 5, 60))
                continue
            raise BallDontLieError(f"{resp.status_code} em {path}: {resp.text[:200]}")
        raise BallDontLieError(f"Sem sucesso em {path} após 5 tentativas")

    def _paginate(self, path: str, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
        params = {k: v for k, v in params.items() if v is not None}
        params["per_page"] = 100
        while True:
            body = self._get(path, params)
            yield from body.get("data", [])
            cursor = (body.get("meta") or {}).get("next_cursor")
            if not cursor:
                return
            params["cursor"] = cursor

    # ---------- DataSource ----------

    def teams(self) -> Iterator[dict[str, Any]]:
        yield from self._get("/teams", {}).get("data", [])

    def games(self, *, season=None, start_date=None, end_date=None):
        return self._paginate("/games", self._filters(season, start_date, end_date))

    def stats(self, *, season=None, start_date=None, end_date=None):
        return self._paginate("/stats", self._filters(season, start_date, end_date))

    def players(self, *, season=None, start_date=None, end_date=None):
        # o perfil completo (posição, draft) já vem dentro de cada linha de /stats
        return iter(())

    def schedule(self, *, date: str):
        # /games traz jogos futuros com placar zerado e o horário em status
        return self._paginate("/games", self._filters(None, date, date))

    def shot_zones(self, *, season: int):
        # a BALLDONTLIE não tem zonas de arremesso
        return iter(())

    @staticmethod
    def _filters(season, start_date, end_date) -> dict[str, Any]:
        return {
            "seasons[]": [season] if season is not None else None,
            "start_date": start_date,
            "end_date": end_date,
        }
