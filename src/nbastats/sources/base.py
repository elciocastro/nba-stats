"""Contrato de uma fonte de dados.

A ingestão só conhece esta interface. Trocar de provedor (ou usar dados
falsos nos testes) é escrever outra classe com estes métodos, que
devolvem dicionários no formato da BALLDONTLIE.
"""

from __future__ import annotations

from typing import Any, Iterable, Protocol


class DataSource(Protocol):
    def teams(self) -> Iterable[dict[str, Any]]: ...

    def games(
        self,
        *,
        season: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Iterable[dict[str, Any]]: ...

    def stats(
        self,
        *,
        season: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Iterable[dict[str, Any]]: ...

    def players(
        self,
        *,
        season: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Iterable[dict[str, Any]]:
        """Perfil dos jogadores (posição, draft). Pode vir vazio se a fonte já
        manda o perfil junto das estatísticas."""
        ...

    def schedule(self, *, date: str) -> Iterable[dict[str, Any]]:
        """Jogos de um dia, inclusive os que ainda não começaram (placar vazio)."""
        ...
