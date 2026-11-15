// Jogos de uma data e o box score completo de cada um.
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api3, BoxTime } from "../api";
import { usePrefs, Esqueleto } from "../App";
import { ddmm } from "../components";

export default function Jogos() {
  const { id } = useParams();
  const { data } = usePrefs();
  const nav = useNavigate();
  const q = useQuery({ queryKey: ["jogos", data], queryFn: () => api3.jogos(data) });
  const sel = id ? Number(id) : q.data?.jogos.find((j) => j.tem_box)?.id;
  return (
    <>
      <h1>Jogos</h1>
      {q.isLoading && <Esqueleto />}
      {q.data && (
        <>
          {q.data.data !== q.data.pedida && <p className="muted small" style={{ marginTop: 0 }}>
            Sem box score em {ddmm(q.data.pedida)}; mostrando {ddmm(q.data.data)}, a última data com jogos encerrados.</p>}
          {!q.data.jogos.length ? <p className="muted">Nenhum jogo na base para esta data.</p> : (
            <div className="tabs" style={{ marginBottom: 12 }}>{q.data.jogos.map((g) => (
              <button key={g.id} className={`tab ${g.id === sel ? "on" : ""}`} disabled={!g.tem_box}
                title={g.tem_box ? "" : "Ainda sem box score"} onClick={() => nav(`/jogos/${g.id}`)}>
                {g.fora} {g.placar_fora ?? ""} @ {g.casa} {g.placar_casa ?? ""}</button>))}
            </div>)}
        </>
      )}
      {sel && <Box id={sel} />}
    </>
  );
}

function Box({ id }: { id: number }) {
  const q = useQuery({ queryKey: ["jogo", id], queryFn: () => api3.jogo(id) });
  if (q.isLoading) return <Esqueleto />;
  if (q.error) return <div className="err">{String((q.error as Error).message)}</div>;
  const g = q.data!;
  const [fora, casa] = g.times;
  const win = (t: BoxTime, o: BoxTime) => (t.placar ?? 0) > (o.placar ?? 0);
  return (
    <>
      <div className="panel" style={{ display: "flex", justifyContent: "center", gap: 28, alignItems: "center", marginBottom: 14 }}>
        <Score t={fora} w={win(fora, casa)} />
        <div className="muted small" style={{ textAlign: "center" }}>{ddmm(g.data)}<br />{g.status ?? ""}{g.playoffs ? " · playoffs" : ""}</div>
        <Score t={casa} w={win(casa, fora)} />
      </div>
      {g.times.map((t) => <TeamBox key={t.time_id} t={t} />)}
    </>
  );
}

function Score({ t, w }: { t: BoxTime; w: boolean }) {
  return <div style={{ textAlign: "center" }}><div className="muted small">{t.nome}</div>
    <div style={{ fontSize: "1.8rem", fontWeight: 800, color: w ? "var(--text)" : "var(--muted)" }}>{t.time} {t.placar ?? "—"}</div></div>;
}

const ma = (m: number | null, a: number | null) => `${m ?? 0}-${a ?? 0}`;

function TeamBox({ t }: { t: BoxTime }) {
  const tot = t.totais;
  return (
    <>
      <h2>{t.nome}</h2>
      <div className="tw"><table className="t">
        <thead><tr><th>Jogador</th><th>Min</th><th>PTS</th><th>REB</th><th>AST</th><th>PRA</th><th>FG</th><th>3P</th><th>FT</th>
          <th>OREB</th><th>ROU</th><th>TOC</th><th>TOV</th><th>PF</th><th>+/−</th></tr></thead>
        <tbody>
          {t.jogadores.map((p) => (
            <tr key={p.player_id}>
              <td><Link to={`/jogador/${p.player_id}?mercado=pra`}><b>{p.jogador}</b></Link> <span className="muted small">{p.posicao ?? ""}</span></td>
              <td>{Math.round(p.min)}</td><td><b>{p.pts}</b></td><td>{p.reb}</td><td>{p.ast}</td><td>{p.pra}</td>
              <td>{ma(p.fgm, p.fga)}</td><td>{ma(p.fg3m, p.fg3a)}</td><td>{ma(p.ftm, p.fta)}</td>
              <td>{p.oreb}</td><td>{p.stl}</td><td>{p.blk}</td><td>{p.turnover}</td><td>{p.pf}</td>
              <td className={p.plus_minus == null ? "" : p.plus_minus > 0 ? "over" : p.plus_minus < 0 ? "under" : ""}>
                {p.plus_minus == null ? "—" : p.plus_minus > 0 ? `+${p.plus_minus}` : p.plus_minus}</td>
            </tr>))}
          <tr style={{ fontWeight: 700 }}><td>Total</td><td></td><td>{tot.pts}</td><td>{tot.reb}</td><td>{tot.ast}</td>
            <td>{(tot.pts ?? 0) + (tot.reb ?? 0) + (tot.ast ?? 0)}</td>
            <td>{ma(tot.fgm, tot.fga)} <span className="muted small">{tot.fg_pct ?? "—"}%</span></td>
            <td>{ma(tot.fg3m, tot.fg3a)} <span className="muted small">{tot.fg3_pct ?? "—"}%</span></td>
            <td>{ma(tot.ftm, tot.fta)} <span className="muted small">{tot.ft_pct ?? "—"}%</span></td>
            <td>{tot.oreb}</td><td>{tot.stl}</td><td>{tot.blk}</td><td>{tot.turnover}</td><td>{tot.pf}</td><td></td></tr>
        </tbody></table></div>
      {t.nao_jogaram.length > 0 && <p className="muted small">Não jogaram: {t.nao_jogaram.join(", ")}</p>}
    </>
  );
}
