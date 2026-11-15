import pytest

from nbastats.metrics import filtros as fl


def test_salva_substitui_lista_e_apaga_por_usuario(conn):
    a = fl.save_filter(conn, "PRA forte", {"mercado": "pra", "chance_min": 60, "lixo": "x", "so_casa": "sim"}, user_id=1)
    assert fl.list_filters(conn, 1) == [{"id": a, "nome": "PRA forte", "params": {"mercado": "pra", "chance_min": 60}}]
    assert fl.save_filter(conn, "PRA forte", {"mercado": "pts"}, user_id=1) == a  # mesmo nome substitui
    assert fl.list_filters(conn, 1)[0]["params"] == {"mercado": "pts"}
    fl.save_filter(conn, "PRA forte", {"mercado": "reb"})  # sem login: outro conjunto
    assert fl.list_filters(conn, 2) == [] and fl.list_filters(conn)[0]["params"] == {"mercado": "reb"}
    fl.delete_filter(conn, a, user_id=2)  # de outra pessoa: não apaga
    assert fl.list_filters(conn, 1)
    fl.delete_filter(conn, a, user_id=1)
    assert fl.list_filters(conn, 1) == []
    with pytest.raises(ValueError):
        fl.save_filter(conn, "  ", {})
