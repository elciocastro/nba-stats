from datetime import date

import pytest

from nbastats import auth


def test_hash_tem_sal_e_confere():
    a, b = auth.hash_senha("segredo123"), auth.hash_senha("segredo123")
    assert a != b and auth.confere_senha("segredo123", a) and not auth.confere_senha("outra", a)
    assert not auth.confere_senha("x", "lixo")


def test_modos(conn):
    assert auth.modo(conn, None) == "aberto"
    assert auth.modo(conn, "abc") == "senha"
    auth.criar_usuario(conn, "admin", "senha-forte", papel="admin")
    assert auth.modo(conn, "abc") == "usuarios"


def test_criar_valida_login_senha_e_duplicado(conn):
    with pytest.raises(ValueError):
        auth.criar_usuario(conn, "ana", "curta")
    with pytest.raises(ValueError):
        auth.criar_usuario(conn, "ana silva", "senha-forte")
    auth.criar_usuario(conn, "Ana", "senha-forte")
    with pytest.raises(ValueError):
        auth.criar_usuario(conn, "ana", "senha-forte")


def test_entrar_sessao_e_sair(conn):
    uid = auth.criar_usuario(conn, "ana", "senha-forte", nome="Ana")
    r = auth.entrar(conn, "ANA", "senha-forte", ip="1.2.3.4")
    assert r["usuario"]["login"] == "ana"
    # o banco não guarda o token em claro
    assert not conn.execute("SELECT 1 FROM sessions WHERE token_hash = ?", (r["token"],)).fetchone()
    assert auth.sessao(conn, r["token"])["id"] == uid
    auth.sair(conn, r["token"])
    assert auth.sessao(conn, r["token"]) is None
    assert auth.sessao(conn, None) is None


def test_desativar_derruba_sessao_e_bloqueia_login(conn):
    auth.criar_usuario(conn, "admin", "senha-forte", papel="admin")
    uid = auth.criar_usuario(conn, "ana", "senha-forte")
    tok = auth.entrar(conn, "ana", "senha-forte")["token"]
    auth.alterar_usuario(conn, uid, ativo=False)
    assert auth.sessao(conn, tok) is None
    with pytest.raises(auth.AcessoNegado, match="desativado"):
        auth.entrar(conn, "ana", "senha-forte")


def test_validade_do_acesso(conn):
    uid = auth.criar_usuario(conn, "ana", "senha-forte", expira_em="2026-11-30")
    tok = auth.entrar(conn, "ana", "senha-forte", hoje=date(2026, 11, 15))["token"]
    assert auth.sessao(conn, tok, hoje=date(2026, 12, 1)) is None
    with pytest.raises(auth.AcessoNegado, match="expirado"):
        auth.entrar(conn, "ana", "senha-forte", hoje=date(2026, 12, 1))
    auth.alterar_usuario(conn, uid, expira_em=None)
    assert auth.entrar(conn, "ana", "senha-forte", hoje=date(2027, 1, 1))


def test_bloqueio_depois_de_varias_senhas_erradas(conn):
    auth.criar_usuario(conn, "ana", "senha-forte")
    for _ in range(auth.MAX_FALHAS):
        with pytest.raises(auth.AcessoNegado, match="incorretos"):
            auth.entrar(conn, "ana", "errada")
    with pytest.raises(auth.AcessoNegado, match="Muitas tentativas"):
        auth.entrar(conn, "ana", "senha-forte")
    assert [a["motivo"] for a in auth.acessos(conn)][:2] == ["bloqueado", "senha"]


def test_sempre_fica_um_admin(conn):
    a = auth.criar_usuario(conn, "admin", "senha-forte", papel="admin")
    with pytest.raises(ValueError, match="admin"):
        auth.alterar_usuario(conn, a, papel="usuario")
    with pytest.raises(ValueError, match="admin"):
        auth.apagar_usuario(conn, a)
    b = auth.criar_usuario(conn, "admin2", "senha-forte", papel="admin")
    auth.alterar_usuario(conn, a, ativo=False)
    with pytest.raises(ValueError):
        auth.alterar_usuario(conn, b, ativo=False)


def test_trocar_a_propria_senha(conn):
    uid = auth.criar_usuario(conn, "ana", "provisoria", trocar_senha=True)
    assert auth.entrar(conn, "ana", "provisoria")["usuario"]["trocar_senha"]
    with pytest.raises(auth.AcessoNegado):
        auth.trocar_propria_senha(conn, uid, "errada", "nova-senha")
    auth.trocar_propria_senha(conn, uid, "provisoria", "nova-senha")
    assert not auth.entrar(conn, "ana", "nova-senha")["usuario"]["trocar_senha"]
