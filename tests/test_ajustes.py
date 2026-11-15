import pytest

from nbastats import ajustes as aj
from nbastats.metrics.apostas import load_bet_config
from nbastats.metrics.potencial import load_rules


def test_ajuste_por_cima_do_padrao_e_restaurar():
    base = load_bet_config()
    assert aj.definir("apostas", "jogo_responsavel.limite_unidades_dia", "7,5") == 7.5
    cfg = load_bet_config()
    assert cfg["jogo_responsavel"]["limite_unidades_dia"] == 7.5
    assert cfg["jogo_responsavel"]["limite_unidades_semana"] == base["jogo_responsavel"]["limite_unidades_semana"]
    assert load_bet_config(ajustes=False) == base
    aj.restaurar("apostas", "jogo_responsavel.limite_unidades_dia")
    assert load_bet_config() == base and not (aj.pasta() / "apostas.yaml").exists()


def test_validacao_dos_campos():
    with pytest.raises(ValueError, match="entre"):
        aj.definir("apostas", "jogo_responsavel.limite_unidades_dia", 99999)
    with pytest.raises(ValueError, match="não pode"):
        aj.definir("projecao", "mercados.pts.nivel", 2)
    with pytest.raises(ValueError, match="#RRGGBB"):
        aj.definir("site", "cor_destaque", "laranja")
    with pytest.raises(ValueError):
        aj.definir("alertas", "status_alerta", ["Out", "Talvez"])
    assert aj.definir("apostas", "unidades", [2, "0,5", 1, 1]) == [0.5, 1.0, 2.0]
    assert aj.definir("apostas", "etiquetas", [" H2H ", "H2H", "", "a,b"]) == ["H2H", "a b"]


def test_nulo_conta_como_ajuste():
    aj.definir("potencial", "filtros.max_anos_de_liga", "")
    assert load_rules()["filtros"]["max_anos_de_liga"] is None
    secao = next(s for s in aj.painel({"potencial": load_rules(ajustes=False)}) if s["arquivo"] == "potencial")
    campo = next(c for c in secao["campos"] if c["caminho"] == "filtros.max_anos_de_liga")
    assert campo["mudado"] and campo["valor"] is None and campo["padrao"] == 4


def test_site():
    assert aj.load_site()["nome"]
    aj.definir("site", "nome", "Meu Site")
    assert aj.load_site()["nome"] == "Meu Site"
