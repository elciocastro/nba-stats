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

    def shot_zones(self, *, season: int) -> Iterable[dict[str, Any]]:
        """Arremessos por zona na temporada até hoje: {kind: 'player' | 'team_opp',
        entity_id, zone, fgm, fga}. Pode vir vazio se a fonte não tiver."""
        ...


class InjurySource(Protocol):
    """Relatório de lesões. Independe da fonte de estatísticas."""

    def latest(self) -> dict[str, Any] | None:
        """{'published_at': 'AAAA-MM-DDTHH:MM', 'url': ..., 'rows': [{game_date,
        matchup, team, player_name, status, reason}]} ou None se não houver."""
        ...


class LiveSource(Protocol):
    """Placar ao vivo (só leitura; nada é gravado no banco).

    ``live_games`` devolve os jogos do dia da NBA (data ET) já normalizados:
    {game_id, data, status (1 agendado, 2 em andamento, 3 final), status_texto,
    periodo, relogio_seg, casa, fora, casa_id, fora_id, placar_casa,
    placar_fora, jogadores: [{player_id, team_id, nome, minutos, pts, reb, ast,
    fg3m, fg3a, ftm, fta, stl, blk, turnover, faltas, em_quadra, titular}]}.
    Jogadores só vêm para jogos em andamento ou encerrados.
    """

    def live_games(self) -> list[dict[str, Any]]: ...
