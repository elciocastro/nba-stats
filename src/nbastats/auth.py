"""Acesso ao site: usuários, sessões e registro de entradas.

Três modos, escolhidos pelo que existe:
- **usuarios**: há ao menos um usuário na tabela ``users``. Cada pessoa entra
  com login e senha e recebe um token de sessão;
- **senha**: sem usuários, mas com ``NBASTATS_PASSWORD``: senha única (como
  antes); serve até o primeiro admin ser criado (``nbastats usuario criar``);
- **aberto**: nem um nem outro (uso local).

Senhas com PBKDF2-SHA256 e sal por usuário; o banco guarda só o hash do token
de sessão. Depois de ``MAX_FALHAS`` senhas erradas em ``JANELA_MIN`` minutos
para o mesmo login (ou IP), novas tentativas são recusadas até a janela passar.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any

ITERACOES = 240_000
SESSAO_DIAS = 30
MAX_FALHAS = 5
JANELA_MIN = 15
SENHA_MIN = 8
PAPEIS = ("admin", "usuario")


class AcessoNegado(Exception):
    """Login recusado; a mensagem pode ir para a tela."""


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(d: datetime) -> str:
    return d.isoformat().replace("+00:00", "Z")


def hash_senha(senha: str, sal: str | None = None, iteracoes: int = ITERACOES) -> str:
    sal = sal or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(sal), iteracoes).hex()
    return f"pbkdf2_sha256${iteracoes}${sal}${h}"


def confere_senha(senha: str, guardado: str) -> bool:
    try:
        algo, it, sal, h = guardado.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    return hmac.compare_digest(hash_senha(senha, sal, int(it)).split("$")[3], h)


def gerar_senha() -> str:
    """Senha provisória legível (o admin repassa; o usuário troca no 1º acesso)."""
    return secrets.token_urlsafe(9)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def modo(conn: sqlite3.Connection, senha_unica: str | None) -> str:
    if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        return "usuarios"
    return "senha" if senha_unica else "aberto"


# ---------- usuários ----------

def _valida_senha(senha: str) -> None:
    if len(senha) < SENHA_MIN:
        raise ValueError(f"A senha precisa de pelo menos {SENHA_MIN} caracteres.")


def criar_usuario(conn: sqlite3.Connection, login: str, senha: str, nome: str | None = None,
                  papel: str = "usuario", expira_em: str | None = None, trocar_senha: bool = False) -> int:
    login = login.strip().lower()
    if not login or not login.replace(".", "").replace("_", "").replace("-", "").isalnum():
        raise ValueError("Login: só letras, números, ponto, hífen e sublinhado.")
    if papel not in PAPEIS:
        raise ValueError(f"Papel deve ser um de {PAPEIS}.")
    _valida_senha(senha)
    if conn.execute("SELECT 1 FROM users WHERE login = ?", (login,)).fetchone():
        raise ValueError(f"O login {login} já existe.")
    cur = conn.execute(
        "INSERT INTO users (login, nome, senha_hash, papel, expira_em, trocar_senha, criado_em)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (login, nome or login, hash_senha(senha), papel, expira_em or None, int(trocar_senha), _iso(_agora())))
    conn.commit()
    return int(cur.lastrowid)


def listar_usuarios(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    agora = _iso(_agora())
    sql = """
        SELECT u.id, u.login, u.nome, u.papel, u.ativo, u.expira_em, u.trocar_senha, u.criado_em, u.ultimo_acesso,
               (SELECT COUNT(*) FROM sessions s WHERE s.user_id = u.id AND s.expira_em > ?) AS sessoes
        FROM users u ORDER BY u.papel, u.login
    """
    return [dict(r) | {"ativo": bool(r["ativo"]), "trocar_senha": bool(r["trocar_senha"])}
            for r in conn.execute(sql, (agora,))]


def _admins_ativos(conn: sqlite3.Connection, exceto: int | None = None) -> int:
    return conn.execute("SELECT COUNT(*) FROM users WHERE papel = 'admin' AND ativo = 1 AND id != ?",
                        (exceto or -1,)).fetchone()[0]


def alterar_usuario(conn: sqlite3.Connection, user_id: int, *, nome: str | None = None,
                    papel: str | None = None, ativo: bool | None = None,
                    expira_em: str | None | bool = False) -> None:
    """``expira_em=False`` = não mexe; ``None``/"" = sem validade."""
    u = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if u is None:
        raise ValueError("Usuário não encontrado.")
    perde_admin = (papel is not None and papel != "admin") or ativo is False
    if u["papel"] == "admin" and perde_admin and not _admins_ativos(conn, exceto=user_id):
        raise ValueError("Precisa ficar pelo menos um admin ativo.")
    if papel is not None and papel not in PAPEIS:
        raise ValueError(f"Papel deve ser um de {PAPEIS}.")
    sets: dict[str, Any] = {}
    if nome is not None:
        sets["nome"] = nome
    if papel is not None:
        sets["papel"] = papel
    if ativo is not None:
        sets["ativo"] = int(ativo)
    if expira_em is not False:
        sets["expira_em"] = expira_em or None
    if sets:
        conn.execute(f"UPDATE users SET {', '.join(f'{k} = ?' for k in sets)} WHERE id = ?",
                     (*sets.values(), user_id))
    if ativo is False:
        encerrar_sessoes(conn, user_id)
    conn.commit()


def definir_senha(conn: sqlite3.Connection, user_id: int, senha: str, trocar_senha: bool = False) -> None:
    _valida_senha(senha)
    n = conn.execute("UPDATE users SET senha_hash = ?, trocar_senha = ? WHERE id = ?",
                     (hash_senha(senha), int(trocar_senha), user_id)).rowcount
    if not n:
        raise ValueError("Usuário não encontrado.")
    conn.commit()


def apagar_usuario(conn: sqlite3.Connection, user_id: int) -> None:
    u = conn.execute("SELECT papel, ativo FROM users WHERE id = ?", (user_id,)).fetchone()
    if u is None:
        raise ValueError("Usuário não encontrado.")
    if u["papel"] == "admin" and not _admins_ativos(conn, exceto=user_id):
        raise ValueError("Precisa ficar pelo menos um admin ativo.")
    encerrar_sessoes(conn, user_id)
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()


# ---------- sessões ----------

def _bloqueado(conn: sqlite3.Connection, login: str, ip: str | None) -> bool:
    desde = _iso(_agora() - timedelta(minutes=JANELA_MIN))
    por_login = conn.execute("SELECT COUNT(*) FROM access_log WHERE ok = 0 AND login = ? AND quando > ?",
                             (login, desde)).fetchone()[0]
    por_ip = conn.execute("SELECT COUNT(*) FROM access_log WHERE ok = 0 AND ip = ? AND quando > ?",
                          (ip, desde)).fetchone()[0] if ip else 0
    return por_login >= MAX_FALHAS or por_ip >= 3 * MAX_FALHAS


def _log(conn: sqlite3.Connection, login: str | None, user_id: int | None, ok: bool, ip: str | None,
         motivo: str | None) -> None:
    conn.execute("INSERT INTO access_log (quando, login, user_id, ok, ip, motivo) VALUES (?, ?, ?, ?, ?, ?)",
                 (_iso(_agora()), login, user_id, int(ok), ip, motivo))
    conn.commit()


def entrar(conn: sqlite3.Connection, login: str, senha: str, ip: str | None = None,
           agente: str | None = None, hoje: date | None = None) -> dict[str, Any]:
    """Confere login e senha e abre uma sessão. Devolve token e usuário."""
    login = (login or "").strip().lower()
    if _bloqueado(conn, login, ip):
        _log(conn, login, None, False, ip, "bloqueado")
        raise AcessoNegado(f"Muitas tentativas. Tente de novo em {JANELA_MIN} minutos.")
    u = conn.execute("SELECT * FROM users WHERE login = ?", (login,)).fetchone()
    if u is None or not confere_senha(senha, u["senha_hash"]):
        _log(conn, login, u["id"] if u else None, False, ip, "senha")
        raise AcessoNegado("Login ou senha incorretos.")
    if not u["ativo"]:
        _log(conn, login, u["id"], False, ip, "inativo")
        raise AcessoNegado("Acesso desativado. Fale com o administrador.")
    if u["expira_em"] and u["expira_em"] < (hoje or date.today()).isoformat():
        _log(conn, login, u["id"], False, ip, "expirado")
        raise AcessoNegado("Acesso expirado. Fale com o administrador.")
    token = secrets.token_urlsafe(32)
    agora = _agora()
    conn.execute("INSERT INTO sessions (token_hash, user_id, criado_em, expira_em, ultimo_uso, ip, agente)"
                 " VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (_token_hash(token), u["id"], _iso(agora), _iso(agora + timedelta(days=SESSAO_DIAS)),
                  _iso(agora), ip, (agente or "")[:200]))
    conn.execute("UPDATE users SET ultimo_acesso = ? WHERE id = ?", (_iso(agora), u["id"]))
    _log(conn, login, u["id"], True, ip, None)
    return {"token": token, "usuario": _publico(u)}


def _publico(u: sqlite3.Row) -> dict[str, Any]:
    return {"id": u["id"], "login": u["login"], "nome": u["nome"], "papel": u["papel"],
            "trocar_senha": bool(u["trocar_senha"]), "expira_em": u["expira_em"]}


def sessao(conn: sqlite3.Connection, token: str | None, hoje: date | None = None) -> dict[str, Any] | None:
    """Usuário dono do token, se a sessão e o acesso ainda valem."""
    if not token:
        return None
    agora = _agora()
    r = conn.execute("""SELECT u.*, s.ultimo_uso AS s_uso FROM sessions s JOIN users u ON u.id = s.user_id
                        WHERE s.token_hash = ? AND s.expira_em > ?""", (_token_hash(token), _iso(agora))).fetchone()
    if r is None or not r["ativo"] or (r["expira_em"] and r["expira_em"] < (hoje or date.today()).isoformat()):
        return None
    if not r["s_uso"] or r["s_uso"] < _iso(agora - timedelta(minutes=5)):  # não grava a cada requisição
        conn.execute("UPDATE sessions SET ultimo_uso = ? WHERE token_hash = ?", (_iso(agora), _token_hash(token)))
        conn.execute("UPDATE users SET ultimo_acesso = ? WHERE id = ?", (_iso(agora), r["id"]))
        conn.commit()
    return _publico(r)


def sair(conn: sqlite3.Connection, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
    conn.commit()


def encerrar_sessoes(conn: sqlite3.Connection, user_id: int) -> int:
    n = conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,)).rowcount
    conn.commit()
    return n


def trocar_propria_senha(conn: sqlite3.Connection, user_id: int, atual: str, nova: str) -> None:
    u = conn.execute("SELECT senha_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    if u is None or not confere_senha(atual, u["senha_hash"]):
        raise AcessoNegado("Senha atual incorreta.")
    if atual == nova:
        raise ValueError("A nova senha precisa ser diferente da atual.")
    definir_senha(conn, user_id, nova)


def acessos(conn: sqlite3.Connection, limite: int = 100) -> list[dict[str, Any]]:
    return [dict(r) | {"ok": bool(r["ok"])} for r in conn.execute(
        "SELECT quando, login, ok, ip, motivo FROM access_log ORDER BY id DESC LIMIT ?", (limite,))]


def limpar(conn: sqlite3.Connection, dias_log: int = 90) -> None:
    """Remove sessões vencidas e registros de acesso antigos."""
    agora = _agora()
    conn.execute("DELETE FROM sessions WHERE expira_em <= ?", (_iso(agora),))
    conn.execute("DELETE FROM access_log WHERE quando < ?", (_iso(agora - timedelta(days=dias_log)),))
    conn.commit()
