"""Comandos usuario, backup e saude (banco temporário)."""

from nbastats import cli, db


def test_usuario_backup_e_saude(tmp_path, monkeypatch, capsys):
    path = tmp_path / "nba.db"
    monkeypatch.setenv("NBASTATS_DB", str(path))
    monkeypatch.setenv("NBASTATS_BACKUP_DIR", str(tmp_path / "bk"))
    senhas = iter(["senha-forte", "senha-forte", "outra-senha", "diferente"])
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": next(senhas))
    assert cli.main(["usuario", "criar", "chefe", "--admin"]) == 0
    assert cli.main(["usuario", "senha", "chefe"]) == 2          # repetição não confere
    assert cli.main(["usuario", "desativar", "chefe"]) == 2      # último admin
    assert cli.main(["usuario", "senha", "ninguem"]) == 1
    assert cli.main(["usuario", "listar"]) == 0
    assert "chefe" in capsys.readouterr().out
    assert cli.main(["backup"]) == 0 and list((tmp_path / "bk").glob("nba-*.db"))
    assert cli.main(["saude"]) == 1                              # base sem carga
    conn = db.connect(str(path))
    assert conn.execute("SELECT papel FROM users WHERE login = 'chefe'").fetchone()[0] == "admin"
