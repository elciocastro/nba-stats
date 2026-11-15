from nbastats import db


def test_banco_antigo_ganha_as_colunas_novas():
    c = db.connect(":memory:")
    c.execute("CREATE TABLE bets (id INTEGER PRIMARY KEY, created_at TEXT, date TEXT, player_id INTEGER,"
              " market TEXT, side TEXT, line REAL, odd REAL, units REAL, status TEXT)")
    c.execute("INSERT INTO bets VALUES (1, 'x', '2026-11-01', 7, 'pts', 'over', 20.5, 1.9, 1, 'pendente')")
    db.init_db(c)
    cols = {r[1] for r in c.execute("PRAGMA table_info(bets)")}
    assert {"tags", "user_id"} <= cols
    assert c.execute("SELECT player_id FROM bets").fetchone()[0] == 7  # dados preservados
    assert db.migrate(c) == []  # segunda vez não faz nada
