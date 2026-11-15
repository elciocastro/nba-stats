// Comparar: jogador × jogador (mesmo mercado), time × time e tendências da liga.
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, api2, Jogador, TeamSide } from "../api";
import { usePrefs } from "../App";
import { heat, num, Photo } from "../components";
import { MARKETS } from "./Props";

export default function Comparar() {
  const [sp, setSp] = useSearchParams();
  const aba = sp.get("aba") ?? "jogadores";
  const tabs: Record<string, string> = { jogadores: "Jogador × jogador", times: "Time × time", tendencias: "Tendências" };
  return (
    <>
      <h1>Comparar</h1>
      <nav className="areatabs">{Object.entries(tabs).map(([k, v]) =>
        <a key={k} className={k === aba ? "on" : ""} href="#" onClick={(e) => { e.preventDefault(); setSp({ aba: k }); }}>{v}</a>)}</nav>
      <div style={{ marginTop: 12 }}>
        {aba === "jogadores" && <Jogadores />}
        {aba === "times" && <Times />}
        {aba === "tendencias" && <Tendencias />}
      </div>
    </>
  );
}

function Jogadores() {
  const { data, betaniag } = usePrefs();
  const [mercado, setMercado] = useState("pra");
  const q = useQuery({ queryKey: ["props", data, mercado, betaniag], queryFn: () => api.props(data, mercado, betaniag) });
  const players = q.data?.jogadores ?? [];
  const [a, setA] = useState<number | null>(null);
  const [b, setB] = useState<number | null>(null);
  const pa = players.find((p) => p.player_id === a) ?? players[0];
  const pb = players.find((p) => p.player_id === b) ?? players[1];
  const opts = useMemo(() => [...players].sort((x, y) => x.jogador.localeCompare(y.jogador)), [players]);

  return (
    <>
      <div className="tabs" style={{ marginBottom: 10 }}>{Object.entries(MARKETS).map(([k, v]) =>
        <button key={k} className={`tab ${k === mercado ? "on" : ""}`} onClick={() => setMercado(k)}>{v}</button>)}</div>
      {q.isLoading && <div className="loading">Calculando…</div>}
      {pa && pb && (
        <>
          <div className="row" style={{ marginBottom: 12 }}>
            <select className="input" value={pa.player_id} onChange={(e) => setA(Number(e.target.value))}>
              {opts.map((p) => <option key={p.player_id} value={p.player_id}>{p.jogador} ({p.time} x {p.adversario})</option>)}</select>
            <span className="muted">×</span>
            <select className="input" value={pb.player_id} onChange={(e) => setB(Number(e.target.value))}>
              {opts.map((p) => <option key={p.player_id} value={p.player_id}>{p.jogador} ({p.time} x {p.adversario})</option>)}</select>
          </div>
          <div className="grid2">
            <Side a={pa} b={pb} />
            <div className="chart">
              <div className="small muted" style={{ padding: "0 8px" }}>Últimos 10 jogos (mais antigo à esquerda) · linhas tracejadas = linha de cada um</div>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={Array.from({ length: 10 }, (_, i) => ({
                  i: i + 1, [pa.jogador]: pa.valores.slice(-10)[i]?.valor, [pb.jogador]: pb.valores.slice(-10)[i]?.valor }))}
                  margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke="#1d2632" />
                  <XAxis dataKey="i" tick={{ fill: "#8b98a9", fontSize: 11 }} /><YAxis tick={{ fill: "#8b98a9", fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: "#121821", border: "1px solid #263040" }} />
                  <Legend />
                  {pa.linha != null && <ReferenceLine y={pa.linha} stroke="#3b82f6" strokeDasharray="4 3" />}
                  {pb.linha != null && <ReferenceLine y={pb.linha} stroke="#f59e0b" strokeDasharray="4 3" />}
                  <Bar dataKey={pa.jogador} fill="#3b82f6" radius={[2, 2, 0, 0]} />
                  <Bar dataKey={pb.jogador} fill="#f59e0b" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </>
  );
}

function Side({ a, b }: { a: Jogador; b: Jogador }) {
  const nav = useNavigate();
  const rows: [string, (p: Jogador) => string | number | null, ((p: Jogador) => number | null)?][] = [
    ["Jogo", (p) => `${p.time} x ${p.adversario}`],
    ["Linha", (p) => p.linha == null ? "—" : `${p.linha}${p.linha_ref ? " ref" : ""}`],
    ["Projeção", (p) => num(p.proj), (p) => p.proj],
    ["Proj. − linha", (p) => p.diff == null ? "—" : `${p.diff > 0 ? "+" : ""}${p.diff.toFixed(1)}`, (p) => p.diff],
    ["Chance over", (p) => p.p_over == null ? "—" : `${Math.round(100 * p.p_over)}%`, (p) => p.p_over],
    ["L5 / L10 / Temp.", (p) => `${num(p.l5)} / ${num(p.l10)} / ${num(p.temporada)}`],
    ["Over L10", (p) => p.janelas?.L10?.pct == null ? "—" : `${p.janelas.L10.pct}%`],
    ["H2H", (p) => p.janelas?.H2H?.jogos ? `${p.janelas.H2H.pct}% (${p.janelas.H2H.jogos} j)` : "—"],
    ["Minutos L5 / L10", (p) => `${num(p.min_l5, 0)} / ${num(p.min_l10, 0)}`, (p) => p.min_l10],
    ["Uso L5 / L10", (p) => `${num(p.usg_l5, 0)} / ${num(p.usg_l10, 0)}`, (p) => p.usg_l10],
    ["DvP do adversário", (p) => p.dvp_rank ? `${p.dvp_rank}º` : "—", (p) => p.dvp_rank],
    ["Lesão", (p) => p.lesao ?? "—"],
  ];
  const better = (f: ((p: Jogador) => number | null) | undefined, x: Jogador, y: Jogador) =>
    f && f(x) != null && f(y) != null && f(x)! > f(y)! ? { color: "var(--over)", fontWeight: 700 } : undefined;
  return (
    <div className="tw"><table className="t">
      <thead><tr><th></th>
        {[a, b].map((p) => <th key={p.player_id} style={{ cursor: "pointer" }} onClick={() => nav(`/jogador/${p.player_id}`)}>
          <div className="row" style={{ justifyContent: "flex-end" }}><Photo id={p.player_id} /> {p.jogador}</div></th>)}</tr></thead>
      <tbody>{rows.map(([k, f, cmp]) => (
        <tr key={k}><td className="muted">{k}</td><td style={better(cmp, a, b)}>{f(a)}</td><td style={better(cmp, b, a)}>{f(b)}</td></tr>))}
      </tbody></table></div>
  );
}

function Times() {
  const { data } = usePrefs();
  const teams = useQuery({ queryKey: ["times"], queryFn: api2.times });
  const games = useQuery({ queryKey: ["props", data, "pts", false], queryFn: () => api.props(data, "pts", false) });
  const [pair, setPair] = useState<[number, number] | null>(null);
  const first = games.data?.jogos[0];
  const [a, b] = pair ?? (first ? [first.fora_id, first.casa_id] : [teams.data?.[0]?.id ?? 0, teams.data?.[1]?.id ?? 0]);
  const [stat, setStat] = useState("pra");
  const q = useQuery({ queryKey: ["cmpTimes", a, b, data], enabled: !!a && !!b, queryFn: () => api2.compararTimes(a, b, data) });
  const sel = (v: number, other: number, i: 0 | 1) => (
    <select className="input" value={v} onChange={(e) => setPair(i === 0 ? [Number(e.target.value), other] : [other, Number(e.target.value)])}>
      {teams.data?.map((t) => <option key={t.id} value={t.id}>{t.sigla} · {t.nome}</option>)}</select>);
  const line = (k: string, f: (s: TeamSide) => number | null, higherBetter = true) => {
    if (!q.data) return null;
    const x = f(q.data.a), y = f(q.data.b);
    const best = x == null || y == null || x === y ? null : (x > y) === higherBetter ? "a" : "b";
    return <tr key={k}><td className="muted">{k}</td>
      <td style={best === "a" ? { color: "var(--over)", fontWeight: 700 } : undefined}>{x ?? "—"}</td>
      <td style={best === "b" ? { color: "var(--over)", fontWeight: 700 } : undefined}>{y ?? "—"}</td></tr>;
  };
  return (
    <>
      {games.data && <div className="tabs" style={{ marginBottom: 10 }}>{games.data.jogos.map((g) =>
        <button key={g.id} className={`tab ${a === g.fora_id && b === g.casa_id ? "on" : ""}`} onClick={() => setPair([g.fora_id, g.casa_id])}>{g.fora} @ {g.casa}</button>)}</div>}
      <div className="row" style={{ marginBottom: 12 }}>{sel(a, b, 0)}<span className="muted">×</span>{sel(b, a, 1)}</div>
      {q.data && (
        <div className="grid2">
          <div className="tw"><table className="t">
            <thead><tr><th></th><th>{q.data.a.time}</th><th>{q.data.b.time}</th></tr></thead>
            <tbody>
              {line("Jogos", (s) => s.jogos)}
              {line(`Ritmo (liga ${q.data.liga_ritmo})`, (s) => s.ritmo)}
              {line("Saldo médio", (s) => s.saldo)}
              {line("Pontos feitos", (s) => s.pts_feitos)}
              {line("Pontos cedidos", (s) => s.pts_cedidos, false)}
            </tbody></table></div>
          <div>
            <div className="tabs" style={{ marginBottom: 8 }}>{["pts", "reb", "ast", "pra", "fg3m"].map((k) =>
              <button key={k} className={`tab ${k === stat ? "on" : ""}`} onClick={() => setStat(k)}>{MARKETS[k]}</button>)}</div>
            <div className="tw"><table className="t">
              <thead><tr><th>Defesa por posição</th><th>{q.data.a.time} cede</th><th>rank</th><th>15d</th><th>{q.data.b.time} cede</th><th>rank</th><th>15d</th></tr></thead>
              <tbody>{q.data.a.dvp.filter((d) => d.stat === stat).map((da) => {
                const db = q.data!.b.dvp.find((d) => d.stat === stat && d.grupo === da.grupo)!;
                const rk = (r: number | null) => r == null ? undefined : r >= 26 ? { background: "var(--h-good)", color: "#dcfce7" } : r <= 5 ? { background: "var(--h-bad)", color: "#fee2e2" } : undefined;
                return <tr key={da.grupo}><td>{da.grupo}</td>
                  <td>{num(da.media)}</td><td style={rk(da.rank)}>{da.rank}º</td><td style={rk(da.rank_rec)}>{da.rank_rec}º</td>
                  <td>{num(db.media)}</td><td style={rk(db.rank)}>{db.rank}º</td><td style={rk(db.rank_rec)}>{db.rank_rec}º</td></tr>;
              })}</tbody></table></div>
            <p className="muted small">Rank 30 = defesa que mais cede (verde = alvo bom para quem ataca).</p>
          </div>
        </div>
      )}
    </>
  );
}

function Tendencias() {
  const { data } = usePrefs();
  const nav = useNavigate();
  const q = useQuery({ queryKey: ["tendencias", data], queryFn: () => api2.tendencias(data) });
  if (q.isLoading) return <div className="loading">Calculando…</div>;
  const t = q.data!;
  const list = (title: string, rows: typeof t.minutos, unit: string) => (
    <div><div className="small muted" style={{ marginBottom: 4 }}>{title}</div>
      <div className="tw"><table className="t">
        <thead><tr><th>Jogador</th><th>L5</th><th>Temp.</th><th>Dif</th></tr></thead>
        <tbody>{rows.map((r) => (
          <tr key={r.player_id} style={{ cursor: "pointer" }} onClick={() => nav(`/jogador/${r.player_id}?mercado=pra`)}>
            <td><b>{r.jogador}</b> <span className="muted small">{r.time}</span></td><td>{r.l5}{unit}</td><td>{r.temporada}{unit}</td>
            <td style={{ color: r.dif > 0 ? "var(--over)" : "var(--under)", fontWeight: 700 }}>{r.dif > 0 ? "+" : ""}{r.dif}</td></tr>))}
        </tbody></table></div></div>);
  return (
    <div className="grid2">
      {list("Ganharam minutos (L5 − temporada)", t.minutos, "")}
      {list("Perderam minutos", t.minutos_queda, "")}
      {list("Ganharam uso (taxa de uso %, L5 − temporada)", t.uso, "%")}
      <div><div className="small muted" style={{ marginBottom: 4 }}>Defesas que pioraram (PRA cedido, recente − temporada)</div>
        <div className="tw"><table className="t">
          <thead><tr><th>Defesa</th><th>Posição</th><th>Temp.</th><th>Recente</th><th>Dif</th><th>Rank rec.</th></tr></thead>
          <tbody>{t.defesas.map((r) => (
            <tr key={`${r.time}${r.grupo}`}><td><b>{r.time}</b></td><td>{r.grupo}</td><td>{r.pra_temporada}</td><td>{r.pra_recente}</td>
              <td style={{ ...heat(r.dif >= 6 ? 75 : r.dif >= 3 ? 60 : 50) }}>+{r.dif}</td><td>{r.rank_recente}º</td></tr>))}
          </tbody></table></div></div>
    </div>
  );
}
