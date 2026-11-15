// Jogos de uma data e o box score completo de cada um.
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api2, api3, BoxTime } from "../api";
import { usePrefs, Esqueleto } from "../App";
import { ddmm } from "../components";

const AO_VIVO_MS = 30_000; // como o Ao Vivo

const mudaDia = (d: string, n: number) => {
  const x = new Date(`${d}T12:00`); x.setDate(x.getDate() + n);
  return `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-${String(x.getDate()).padStart(2, "0")}`;
};

export default function Jogos() {
  const { id } = useParams();
  const { data: hoje } = usePrefs();
  const [sp, setSp] = useSearchParams();
  const modo = sp.get("time") ? "time" : "data";
  const dia = sp.get("dia") ?? hoje;
  const nav = useNavigate();
  const abrir = (gid: number) => nav(`/jogos/${gid}?${sp.toString()}`);
  return (
    <>
      <div className="secao" style={{ flexWrap: "wrap" }}>
        <h1>Jogos</h1>
        <div className="seg">
          <button className={modo === "data" ? "on" : ""} onClick={() => setSp({ dia })}>Por data</button>
          <button className={modo === "time" ? "on" : ""} onClick={() => setSp({ time: sp.get("time") ?? "1610612747" })}>Por time</button>
        </div>
      </div>
      {modo === "data" ? <PorData dia={dia} hoje={hoje} id={id} setDia={(d) => setSp({ dia: d })} abrir={abrir} />
        : <PorTime timeId={Number(sp.get("time"))} hoje={hoje} id={id} setTime={(t) => setSp({ time: String(t) })} abrir={abrir} />}
    </>
  );
}

function PorData({ dia, hoje, id, setDia, abrir }: { dia: string; hoje: string; id?: string; setDia: (d: string) => void;
  abrir: (id: number) => void }) {
  const q = useQuery({ queryKey: ["jogos", dia], queryFn: () => api3.jogos(dia),
    refetchInterval: (qq) => (qq.state.data?.jogos.some((j) => j.ao_vivo) ? AO_VIVO_MS : false) });
  const sel = id ? Number(id) : (q.data?.jogos.find((j) => j.ao_vivo) ?? q.data?.jogos.find((j) => j.tem_box))?.id;
  return (
    <>
      <div className="row" style={{ margin: "10px 0" }}>
        <button className="btn" onClick={() => setDia(mudaDia(dia, -1))} aria-label="Dia anterior">‹</button>
        <input className="input" type="date" value={dia} onChange={(e) => e.target.value && setDia(e.target.value)} />
        <button className="btn" onClick={() => setDia(mudaDia(dia, 1))} aria-label="Dia seguinte">›</button>
        {dia !== hoje && <button className="btn" onClick={() => setDia(hoje)}>Hoje</button>}
        {q.data?.jogos.some((j) => j.ao_vivo) && <span className="muted small"><span className="pulse">●</span> ao vivo · atualiza a cada 30 s</span>}
      </div>
      {q.isLoading && <Esqueleto linhas={2} />}
      {q.data && (
        <>
          {q.data.data !== q.data.pedida && <p className="muted small" style={{ marginTop: 0 }}>
            Sem jogos encerrados em {ddmm(q.data.pedida)}; mostrando {ddmm(q.data.data)}, a última data com jogos.</p>}
          {!q.data.jogos.length ? <p className="muted">Nenhum jogo na base para esta data.</p> : (
            <div className="tabs" style={{ marginBottom: 12 }}>{q.data.jogos.map((g) => (
              <button key={g.id} className={`tab ${g.id === sel ? "on" : ""}`} disabled={!g.tem_box}
                title={g.tem_box ? g.status ?? "" : `Ainda não começou (${g.status ?? ""})`} onClick={() => abrir(g.id)}>
                {g.ao_vivo && <span className="pulse">● </span>}{g.fora} {g.placar_fora ?? ""} @ {g.casa} {g.placar_casa ?? ""}
                {!g.tem_box && <span className="muted small"> {g.status}</span>}</button>))}
            </div>)}
        </>
      )}
      {sel && <Box id={sel} />}
    </>
  );
}

function PorTime({ timeId, hoje, id, setTime, abrir }: { timeId: number; hoje: string; id?: string; setTime: (t: number) => void;
  abrir: (id: number) => void }) {
  const times = useQuery({ queryKey: ["times"], queryFn: api2.times, staleTime: 3_600_000 });
  const q = useQuery({ queryKey: ["jogosTime", timeId, hoje], queryFn: () => api3.jogosDoTime(timeId, hoje), enabled: !!timeId });
  const sel = id ? Number(id) : q.data?.jogos.find((j) => j.tem_box)?.id;
  return (
    <>
      <div className="row" style={{ margin: "10px 0" }}>
        <select className="input" value={timeId} onChange={(e) => setTime(Number(e.target.value))} aria-label="Time">
          {(times.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.nome} ({t.sigla})</option>)}
        </select>
        {q.data && <span className="muted small">{q.data.temporada}/{String(q.data.temporada + 1).slice(2)} · {q.data.v}-{q.data.d}</span>}
      </div>
      {q.isLoading && <Esqueleto linhas={2} />}
      {q.data && (
        <div className="tw" style={{ maxHeight: 300, marginBottom: 14 }}><table className="t">
          <thead><tr><th>Data</th><th>Adversário</th><th>Placar</th><th>Res.</th></tr></thead>
          <tbody>{q.data.jogos.map((j) => (
            <tr key={j.id} onClick={() => j.tem_box && abrir(j.id)} style={{ cursor: j.tem_box ? "pointer" : "default" }}
              className={j.id === sel ? "sel" : ""}>
              <td>{ddmm(j.data)}{j.playoffs ? <span className="muted small"> PO</span> : ""}</td>
              <td style={{ textAlign: "left" }}>{j.em_casa ? "vs" : "@"} {j.adversario}</td>
              <td>{j.pro == null ? <span className="muted small">{j.status}</span> : `${j.pro}-${j.contra}`}</td>
              <td className={j.resultado === "V" ? "over" : j.resultado === "D" ? "under" : ""}>{j.resultado ?? "—"}</td>
            </tr>))}</tbody></table></div>)}
      {sel && <Box id={sel} />}
    </>
  );
}

function Box({ id }: { id: number }) {
  const q = useQuery({ queryKey: ["jogo", id], queryFn: () => api3.jogo(id),
    refetchInterval: (qq) => (qq.state.data?.ao_vivo ? AO_VIVO_MS : false) });
  if (q.isLoading) return <Esqueleto />;
  if (q.error) return <div className="err">{String((q.error as Error).message)}</div>;
  const g = q.data!;
  const [fora, casa] = g.times;
  const win = (t: BoxTime, o: BoxTime) => (t.placar ?? 0) > (o.placar ?? 0);
  return (
    <>
      <div className="panel" style={{ display: "flex", justifyContent: "center", gap: 28, alignItems: "center", marginBottom: 14 }}>
        <Score t={fora} w={win(fora, casa)} />
        <div className="muted small" style={{ textAlign: "center" }}>{ddmm(g.data)}<br />
          {g.ao_vivo && <span className="pulse">● </span>}{g.status ?? ""}{g.playoffs ? " · playoffs" : ""}</div>
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
