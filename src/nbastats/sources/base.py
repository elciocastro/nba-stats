"""Contrato de uma fonte de dados.

A ingestão só conhece esta interface. Trocar de provedor (ou usar dados
falsos nos testes) é escrever outra classe com estes três métodos, que
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
