"""Importação das estatísticas de outro banco (computador -> VPS)."""

from nbastats import db


def _db(path, users):
    c = db.connect(str(path))
    db.init_db(c)
    c.execute("INSERT INTO teams (id, abbreviation) VALUES (1, 'AAA')")
    c.execute("INSERT INTO games (id, date, season, postseason) VALUES (1, '2026-11-01', 2026, 0)")
    c.execute("INSERT INTO shot_zones (id, season, kind, entity_id, zone, fgm, fga)"
               " VALUES ('velha', 2026, 'player', 1, 'z', 1, 2)")
    for login in users:
        c.execute("INSERT INTO users (login, nome, senha_hash, papel, criado_em) VALUES (?, ?, 'x', 'admin', 'agora')",
                  (login, login))
    c.commit()
    return c


def test_importa_estatisticas_e_preserva_o_uso(tmp_path):
    vps = _db(tmp_path / "vps.db", ["elcio", "coni"])
    vps.execute("INSERT INTO bets (created_at, date, player_id, market, side, line, odd, units)"
                " VALUES ('agora', '2026-11-01', 1, 'pts', 'over', 10.5, 1.9, 1)")
    vps.commit()
    pc = _db(tmp_path / "pc.db", ["so-no-pc"])
    pc.execute("UPDATE games SET home_team_score = 110 WHERE id = 1")
    pc.execute("INSERT INTO games (id, date, season, postseason) VALUES (2, '2026-11-02', 2026, 0)")
    pc.execute("DELETE FROM shot_zones")
    pc.execute("INSERT INTO shot_zones (id, season, kind, entity_id, zone, fgm, fga)"
               " VALUES ('nova', 2026, 'player', 1, 'z', 3, 4)")
    pc.commit()

    first = db.import_data(vps, tmp_path / "pc.db")
    again = db.import_data(vps, tmp_path / "pc.db")
    assert first == again and first["games"] == 2
    assert [r[0] for r in vps.execute("SELECT home_team_score FROM games ORDER BY id")] == [110, None]
    assert [r[0] for r in vps.execute("SELECT id FROM shot_zones")] == ["nova"]
    assert sorted(r[0] for r in vps.execute("SELECT login FROM users")) == ["coni", "elcio"]
    assert vps.execute("SELECT COUNT(*) FROM bets").fetchone()[0] == 1
