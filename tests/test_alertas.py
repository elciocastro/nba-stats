import io
import json

import pytest

from nbastats import notificar
from nbastats.metrics import alertas as al

FAVS = {"jogador": [{"entity_id": 7}], "time": [{"entity_id": 99}], "jogo": []}


def test_alerta_de_lesao_so_de_favoritos():
    changes = [{"tipo": "entrou", "player_id": 7, "jogador": "Ana", "time": "AAA", "antes": None, "agora": "Out", "motivo": "joelho"},
               {"tipo": "entrou", "player_id": 8, "jogador": "Beto", "time": "BBB", "antes": None, "agora": "Out", "motivo": None},
               {"tipo": "piorou", "player_id": 9, "jogador": "Caio", "time": "CCC", "antes": "Probable", "agora": "Questionable", "motivo": None},
               {"tipo": "saiu", "player_id": 7, "jogador": "Ana", "time": "AAA", "antes": "Out", "agora": None, "motivo": None}]
    out = al.injury_alerts(changes, FAVS, {"CCC": 99}, {}, "2026-11-15")
    textos = [t for _, t in out]
    assert len(out) == 3 and "Ana (AAA): Out" in textos[0] and "Caio" in textos[1] and "saiu" in textos[2]
    assert len(al.injury_alerts(changes, FAVS, {}, {"so_favoritos": False}, "2026-11-15")) == 4


def test_alerta_de_valor():
    opps = [{"player_id": 7, "jogador": "Ana", "time": "AAA", "adversario": "BBB", "mercado": "pts", "linha": 20.5,
             "linha_ref": False, "lado": "over", "chance": 0.6, "ev": 0.08, "proj": 23.1},
            {"player_id": 7, "jogador": "Ana", "time": "AAA", "adversario": "BBB", "mercado": "reb", "linha": 5.5,
             "linha_ref": False, "lado": "under", "chance": 0.55, "ev": 0.01, "proj": 5.0},
            {"player_id": 8, "jogador": "Beto", "time": "BBB", "adversario": "AAA", "mercado": "pts", "linha": 10.5,
             "linha_ref": False, "lado": "over", "chance": 0.7, "ev": 0.2, "proj": 13.0}]
    out = al.value_alerts(opps, FAVS, {"ev_minimo": 0.05}, "2026-11-15")
    assert len(out) == 1 and "over 20.5 pontos" in out[0][1] and "+8.0%" in out[0][1]


def test_nao_repete(conn):
    alerts = [("a", "x"), ("b", "y"), ("a", "x")]
    assert al.pending(conn, alerts) == [("a", "x"), ("b", "y")]
    al.mark_sent(conn, ["a"])
    assert al.pending(conn, alerts) == [("b", "y")]


def test_resumo_do_dia():
    cards = [{"fora": "AAA", "casa": "BBB", "status": "7:30 pm ET", "favorito": "BBB", "margem": 6.2,
              "desfalques": {"fora": ["Ana"], "casa": []}}]
    opps = {"com_odd": [], "sem_odd": [{"jogador": "Caio", "lado": "over", "linha": 20.5, "linha_ref": True,
                                         "mercado": "pra", "chance": 0.66, "ev": None}]}
    txt = al.daily_summary("2026-11-15", cards, opps, "Dados desatualizados")
    assert "15/11: 1 jogos" in txt and "desfalques: Ana" in txt and "Caio over 20.5 (linha ref.) PRA: 66%" in txt
    assert "⚠ Dados" in txt
    assert "sem jogos" in al.daily_summary("2026-11-15", [], {}, None)


def test_telegram(monkeypatch):
    monkeypatch.delenv("NBASTATS_TELEGRAM_TOKEN", raising=False)
    with pytest.raises(notificar.NaoConfigurado):
        notificar.enviar("oi")
    monkeypatch.setenv("NBASTATS_TELEGRAM_TOKEN", "t")
    monkeypatch.setenv("NBASTATS_TELEGRAM_CHAT", "c")
    sent = []

    class Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def opener(req, timeout):
        sent.append(json.loads(req.data))
        return Resp(b'{"ok": true}')
    assert notificar.enviar("a\n" * 3000, opener=opener) == 2 and sent[0]["chat_id"] == "c"
    assert all(len(p) <= notificar.LIMITE for p in notificar.partes("x" * 10 + "\n" + "y" * 5000))
