import pytest

from nbastats.sources.balldontlie import BallDontLie, BallDontLieError


class FakeResponse:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body or {}
        self.text = str(body)

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def get(self, url, headers, params, timeout):
        self.requests.append((url, dict(headers), dict(params)))
        return self.responses.pop(0)


def _client(responses):
    session = FakeSession(responses)
    return BallDontLie("chave", rpm=6000, session=session, sleep=lambda _: None), session


def test_paginacao_por_cursor_e_header():
    client, session = _client([
        FakeResponse(200, {"data": [{"id": 1}], "meta": {"next_cursor": 50}}),
        FakeResponse(200, {"data": [{"id": 2}], "meta": {}}),
    ])
    assert [g["id"] for g in client.games(season=2026)] == [1, 2]
    url, headers, params = session.requests[0]
    assert url.endswith("/v1/games")
    assert headers == {"Authorization": "chave"}
    assert params == {"seasons[]": [2026], "per_page": 100}
    assert session.requests[1][2]["cursor"] == 50


def test_429_tenta_de_novo():
    client, session = _client([FakeResponse(429), FakeResponse(200, {"data": [{"id": 1}]})])
    assert list(client.stats(start_date="2026-11-01", end_date="2026-11-02")) == [{"id": 1}]
    assert len(session.requests) == 2


def test_401_explica_o_plano():
    client, _ = _client([FakeResponse(401)])
    with pytest.raises(BallDontLieError, match="ALL-STAR"):
        list(client.stats(season=2026))


def test_sem_chave_falha_cedo():
    with pytest.raises(BallDontLieError):
        BallDontLie("")
