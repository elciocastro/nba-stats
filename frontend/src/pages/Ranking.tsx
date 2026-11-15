// Ranking de jogadores: médias da temporada, da janela recente ou a diferença,
// por jogo ou por 36 minutos, e porcentagens de arremesso. Exporta CSV.
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { ColumnDef, createColumnHelper } from "@tanstack/react-table";
import { api3, RankRow } from "../api";
import { usePrefs } from "../App";
import { DataTable, Photo, useMobile } from "../components";

const STATS: [string, string][] = [["min", "Min"], ["pts", "PTS"], ["reb", "REB"], ["ast", "AST"], ["pra", "PRA"],
  ["fg3m", "3PM"], ["stl", "ROU"], ["blk", "TOC"], ["turnover", "TOV"], ["pm", "+/−"]];
const SHOOT: [string, string, string][] = [["fg_pct", "FG%", "fga"], ["fg3_pct", "3P%", "fg3a"], ["ft_pct", "FT%", "fta"],
  ["ts_pct", "TS%", ""]];
const ch = createColumnHelper<RankRow>();

export default function Ranking() {
  const { data } = usePrefs();
  const nav = useNavigate();
  const mobile = useMobile();
  const [janela, setJanela] = useState(10);
  const [minJ, setMinJ] = useState(5);
  const [por36, setPor36] = useState(false);
  const [playoffs, setPlayoffs] = useState(false);
  const [modo, setModo] = useState<"temp" | "janela" | "dif">("temp");
  const [vista, setVista] = useState<"medias" | "arremesso">("medias");
  const [busca, setBusca] = useState("");
  const [time, setTime] = useState("");
  const q = useQuery({ queryKey: ["ranking", data, janela, minJ, por36, playoffs],
                       queryFn: () => api3.ranking(data, janela, minJ, por36, playoffs) });
  const rows = q.data?.jogadores ?? [];
  const times = useMemo(() => [...new Set(rows.flatMap((r) => r.time.split("/")))].filter(Boolean).sort(), [rows]);
  const shown = useMemo(() => rows.filter((r) =>
    (!busca || r.jogador.toLowerCase().includes(busca.toLowerCase())) && (!time || r.time.split("/").includes(time))), [rows, busca, time]);

  const val = (r: RankRow, k: string) => {
    const t = r[k] as number | null, n = r[`${k}_n`] as number | null;
    if (modo === "temp") return t;
    if (modo === "janela") return n;
    return t == null || n == null ? null : Math.round((n - t) * 10) / 10;
  };
  const columns = useMemo<ColumnDef<RankRow, any>[]>(() => [
    ch.accessor("jogador", { header: "Jogador", cell: (c) => (
      <span className="row" style={{ flexWrap: "nowrap", gap: 8 }}>{!mobile && <Photo id={c.row.original.player_id} />}
        <span><b>{c.getValue()}</b> <span className="muted small">{c.row.original.posicao ?? ""}</span></span></span>) }),
    ch.accessor("time", { header: "Time", meta: "Mais recente primeiro (trocado: GSW/CHI)" }),
    ch.accessor("jogos", { header: "J" }),
    ...(vista === "medias"
      ? STATS.map(([k, label]) => ch.accessor((r) => val(r, k), { id: k, header: label,
          cell: (c) => { const v = c.getValue() as number | null; return v == null ? "—" : modo === "dif" && v > 0 ? `+${v}` : v; } }))
      : SHOOT.map(([k, label, att]) => ch.accessor((r) => r[k] as number | null, { id: k, header: label,
          cell: (c) => { const v = c.getValue() as number | null;
            return v == null ? "—" : <>{v}%{att && <span className="muted small"> {c.row.original[att]}</span>}</>; },
          meta: att ? `${label} (tentativas por jogo ao lado)` : "True shooting: pontos ÷ (2 × (FGA + 0,44 × FTA))" }))),
  ], [vista, modo, mobile]);

  const cls = (r: RankRow, col: string) => {
    if (vista !== "medias" || modo !== "dif") return undefined;
    const v = val(r, col);
    if (v == null || col === "min" && Math.abs(v) < 2) return undefined;
    const good = col === "turnover" ? v < 0 : v > 0;
    return Math.abs(v) >= (col === "min" || col === "pts" || col === "pra" ? 3 : 1.5) ? (good ? "over" : "under") : undefined;
  };

  const csv = () => {
    const keys = ["jogador", "time", "posicao", "jogos", ...STATS.flatMap(([k]) => [k, `${k}_n`]), ...SHOOT.map(([k]) => k), "fga", "fg3a", "fta"];
    const esc = (v: unknown) => { const s = v == null ? "" : String(v); return /[",;\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
    const body = [keys.join(","), ...shown.map((r) => keys.map((k) => esc(r[k])).join(","))].join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + body], { type: "text/csv;charset=utf-8" }));
    a.download = `ranking-${data}${por36 ? "-por36" : ""}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1>Ranking</h1>
        <button className="btn" onClick={csv} disabled={!shown.length}>⤓ CSV</button>
      </div>
      <div className="row" style={{ marginBottom: 10 }}>
        <div className="seg">{([["temp", "Temporada"], ["janela", `Últimos ${janela}`], ["dif", "Diferença"]] as const).map(([k, l]) =>
          <button key={k} className={k === modo ? "on" : ""} onClick={() => setModo(k)}>{l}</button>)}</div>
        <div className="seg">{[5, 10, 20].map((n) => <button key={n} className={n === janela ? "on" : ""} onClick={() => setJanela(n)}>L{n}</button>)}</div>
        <div className="seg">{([["medias", "Médias"], ["arremesso", "Arremesso"]] as const).map(([k, l]) =>
          <button key={k} className={k === vista ? "on" : ""} onClick={() => setVista(k)}>{l}</button>)}</div>
      </div>
      <div className="row" style={{ marginBottom: 12 }}>
        <input className="input" placeholder="Buscar jogador" value={busca} onChange={(e) => setBusca(e.target.value)} />
        <select className="input" value={time} onChange={(e) => setTime(e.target.value)}>
          <option value="">Todos os times</option>{times.map((t) => <option key={t}>{t}</option>)}</select>
        <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>Mín. jogos
          <input className="input" type="number" min={1} max={82} value={minJ} style={{ width: 64 }} onChange={(e) => setMinJ(Math.max(1, Number(e.target.value)))} /></label>
        <label className="toggle"><input type="checkbox" checked={por36} onChange={(e) => setPor36(e.target.checked)} />Por 36 min</label>
        <label className="toggle"><input type="checkbox" checked={playoffs} onChange={(e) => setPlayoffs(e.target.checked)} />Playoffs</label>
      </div>
      {q.isLoading && <div className="loading">Calculando…</div>}
      {q.error && <div className="err">{String((q.error as Error).message)}</div>}
      {q.data && (
        <div className="fixa1">
          <p className="muted small" style={{ marginTop: 0 }}>
            {shown.length} jogadores · temporada {q.data.temporada}/{String(q.data.temporada + 1).slice(2)}
            {por36 ? " · contagens por 36 minutos (reservas comparáveis a titulares)" : ""}
            {modo === "dif" ? ` · últimos ${janela} menos a temporada (verde = subindo)` : ""}. Clique no cabeçalho para ordenar.</p>
          <DataTable key={vista} data={shown} columns={columns} cellClass={cls} onRow={(r) => nav(`/jogador/${r.player_id}?mercado=pts`)}
            initialSort={[{ id: vista === "medias" ? "pts" : "ts_pct", desc: true }]} maxHeight={900} />
        </div>
      )}
    </>
  );
}
