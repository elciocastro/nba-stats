import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  Bar, BarChart, CartesianGrid, Cell, ComposedChart, LabelList, Line, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { createColumnHelper, flexRender, getCoreRowModel, getSortedRowModel, SortingState, useReactTable } from "@tanstack/react-table";
import { api, api2, Detalhe, JogoLog, LimiteError } from "../api";
import { usePrefs } from "../App";
import { ddmm, heat, num, pct, Photo, SealBadge, Star, useFavs } from "../components";

const MARKETS: Record<string, string> = {
  pts: "Pontos", reb: "Rebotes", ast: "Assist.", pra: "PRA", pr: "PR", pa: "PA", ra: "RA", fg3m: "3FM",
  fg3a: "3FA", fg2m: "2FM", fg2a: "2FA", ftm: "FTM", fta: "FTA", stl: "Roubos", blk: "Tocos", turnover: "Turnovers",
};
// "Sem lavada" usa a margem de config/projecao.yaml (lavada.margem, vem em /api/meta)
let LAVADA = 20;
const SPLITS: Record<string, (g: JogoLog) => boolean> = {
  Casa: (g) => g.em_casa, Fora: (g) => !g.em_casa, Vitória: (g) => g.resultado === "V",
  Derrota: (g) => g.resultado === "D", "Sem descanso": (g) => g.descanso === 0,
  "Sem lavada": (g) => g.margem == null || Math.abs(g.margem) < LAVADA,
};
const LOG_COLS: [string, string][] = [["minutes", "Min"], ["pts", "PTS"], ["reb", "REB"], ["ast", "AST"],
  ["pra", "PRA"], ["fg3m", "3PM"], ["stl", "ROU"], ["blk", "TOC"]];

export default function JogadorPage() {
  const { id } = useParams();
  const [sp, setSp] = useSearchParams();
  const mercado = sp.get("mercado") ?? "pts";
  const { data, betaniag } = usePrefs();
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta });
  if (meta.data?.lavada) LAVADA = meta.data.lavada;
  const q = useQuery({ queryKey: ["jogador", id, data, mercado, betaniag],
                       queryFn: () => api.jogador(Number(id), data, mercado, betaniag) });

  return (
    <>
      <Link to="/props" className="muted small">← Props</Link>
      <div className="tabs" style={{ margin: "10px 0" }}>
        {Object.entries(MARKETS).map(([k, v]) => (
          <button key={k} className={`tab ${k === mercado ? "on" : ""}`} onClick={() => setSp({ mercado: k })}>{v}</button>
        ))}
      </div>
      {q.isLoading && <div className="loading">Carregando…</div>}
      {q.error && <div className="err">{String((q.error as Error).message)}</div>}
      {q.data && <Body d={q.data} mercado={mercado} data={data} />}
    </>
  );
}

function Body({ d, mercado, data }: { d: Detalhe; mercado: string; data: string }) {
  const fav = useFavs();
  const { atual, anterior } = d.rotulos;
  const [win, setWin] = useState("L10");
  const [split, setSplit] = useState<string | null>(null);
  const [line, setLine] = useState(d.linha ?? 0.5);
  const [oo, setOo] = useState(d.odd_over ?? 0);
  const [ou, setOu] = useState(d.odd_under ?? 0);
  const expMin = d.proj_detalhe?.minutos ?? null;
  const [mins, setMins] = useState(expMin ? Math.round(expMin) : 30);
  useEffect(() => { setLine(d.linha ?? 0.5); setOo(d.odd_over ?? 0); setOu(d.odd_under ?? 0); }, [d.player_id, mercado, d.linha]);

  const proj = d.proj != null && expMin ? (d.proj * mins) / expMin : d.proj;
  const ch = useQuery({ queryKey: ["chance", mercado, proj?.toFixed(2), line], enabled: proj != null,
                        queryFn: () => api.chance(mercado, proj!, line) });
  const po = ch.data?.p_over ?? null;
  const qc = useQueryClient();
  const save = useMutation({
    mutationFn: () => api.salvarLinha({ data, player_id: d.player_id, mercado, linha: line,
                                        odd_over: oo || null, odd_under: ou || null }),
    onSuccess: () => qc.invalidateQueries(),
  });

  const games = useMemo(() => {
    let pool = d.log.filter((g) => !split || SPLITS[split](g));
    if (win === "H2H") return pool.filter((g) => g.opp_id === d.adversario_id).slice(0, 20);
    if (win === anterior) return pool.filter((g) => g.season === d.temporada_atual - 1).slice(0, 41);
    pool = pool.filter((g) => g.season === d.temporada_atual);
    return win === atual ? pool : pool.slice(0, Number(win.slice(1)));
  }, [d, win, split, atual, anterior]);

  const over = games.filter((g) => (g[mercado] as number) > line).length;
  const avg = games.length ? games.reduce((a, g) => a + (g[mercado] as number), 0) / games.length : 0;
  const ev = [["over", po, oo], ["under", po == null ? null : 1 - po, ou]]
    .filter(([, p, o]) => p != null && o)
    .map(([l, p, o]) => [l, (p as number) * (o as number) - 1] as const)
    .sort((a, b) => b[1] - a[1])[0];

  const chartData = [...games].reverse().map((g) => ({
    x: `${ddmm(g.data)} ${g.em_casa ? "vs" : "@"}${g.adv}`, v: g[mercado] as number,
    min: Math.round(g.minutes), usadas: g.usadas, res: g.resultado,
  }));

  return (
    <>
      <div className="hero">
        <Photo id={d.player_id} big />
        <div>
          <div className="n">{d.jogador} <SealBadge s={d.selo} />
            <Star on={fav.has("jogador", d.player_id)} onClick={() => fav.toggle("jogador", d.player_id, d.jogador)} /></div>
          <div className="muted">{d.time} x {d.adversario} · {MARKETS[mercado]} · {d.grupo ?? "?"} / {d.posicao_est ?? "?"} (estimada) · {d.jogo.status}
            {d.jogo.validacao && <span className={`chip ${d.jogo.validacao.status === "validada" ? "ok" : "hot"}`} style={{ marginLeft: 8 }}
              title={d.jogo.validacao.motivo}>{d.jogo.validacao.status}</span>}</div>
          {d.lesao && <div style={{ marginTop: 6 }}><span className="tag">{d.lesao}</span> <span className="muted small">{d.lesao_motivo}</span></div>}
        </div>
      </div>

      <div className="split">
        <div style={{ display: "flex", flexDirection: "column", gap: 14, minWidth: 0 }}>
          <div className="heat">
            {Object.entries(d.janelas).map(([k, w]) => (
              <div key={k} style={heat(w.pct)} onClick={() => setWin(k)}>
                <div className="l">{k}</div><div className="v">{w.pct == null ? "—" : `${w.pct}%`}</div>
                <div className="s">{w.jogos ? `${w.over}/${w.jogos} · méd ${w.media}` : "sem jogos"}</div>
              </div>
            ))}
          </div>
          <div className="row">
            <div className="seg">{["L5", "L10", "L20", atual, "H2H", anterior].map((w) => (
              <button key={w} className={w === win ? "on" : ""} onClick={() => setWin(w)}>{w}</button>))}</div>
            <div className="tabs">{Object.keys(SPLITS).map((s) => (
              <button key={s} className={`tab ${s === split ? "on" : ""}`} onClick={() => setSplit(s === split ? null : s)}>{s}</button>))}</div>
          </div>
          <div><b>{over}/{games.length} acima de {line}</b> <span className="muted">· média {avg.toFixed(1)}{split ? ` · ${split}` : ""}</span></div>
          <div className="chart">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData} margin={{ top: 18, right: 8, left: -18, bottom: 4 }}>
                <CartesianGrid vertical={false} stroke="#1d2632" />
                <XAxis dataKey="x" tick={{ fill: "#8b98a9", fontSize: 10 }} angle={-45} textAnchor="end" height={58} interval={0} />
                <YAxis tick={{ fill: "#8b98a9", fontSize: 11 }} />
                <Tooltip contentStyle={{ background: "#121821", border: "1px solid #263040" }}
                  formatter={(v, _n, p) => [`${v} · ${p.payload.min} min · ${p.payload.res ?? ""}`, MARKETS[mercado]]} />
                <ReferenceLine y={line} stroke="#e6edf3" strokeDasharray="5 3" />
                <Bar dataKey="v" radius={[3, 3, 0, 0]} isAnimationActive>
                  {chartData.map((c, i) => <Cell key={i} fill={c.v > line ? "var(--over)" : "var(--under)"} />)}
                  <LabelList dataKey="v" position="top" fill="#e6edf3" fontSize={11} fontWeight={700} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="chart">
            <div className="small muted" style={{ padding: "0 8px 4px" }}>Minutos (barras) e posses usadas (linha){expMin ? ` · esperado ${expMin} min` : ""}</div>
            <ResponsiveContainer width="100%" height={180}>
              <ComposedChart data={chartData} margin={{ top: 6, right: 0, left: -18, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="#1d2632" />
                <XAxis dataKey="x" hide />
                <YAxis yAxisId="m" tick={{ fill: "#8b98a9", fontSize: 11 }} />
                <YAxis yAxisId="u" orientation="right" tick={{ fill: "#8b98a9", fontSize: 11 }} />
                <Tooltip contentStyle={{ background: "#121821", border: "1px solid #263040" }} />
                <Bar yAxisId="m" dataKey="min" name="Minutos" fill="#3b82f6" opacity={0.75} radius={[2, 2, 0, 0]} />
                {expMin && <ReferenceLine yAxisId="m" y={expMin} stroke="#93c5fd" strokeDasharray="4 3" />}
                <Line yAxisId="u" dataKey="usadas" name="Posses usadas" stroke="#f59e0b" dot={{ r: 2 }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <h2 style={{ margin: "4px 0 0" }}>Jogo a jogo</h2>
          <LogTable rows={games} d={d} mercado={mercado} />
          <p className="muted small" style={{ margin: 0 }}>Verde = atingiu a média dele na temporada (no {MARKETS[mercado]}, a linha); âmbar = 80%; vermelho = abaixo. Clique no cabeçalho para ordenar.</p>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="panel">
            <b>Linha da casa</b>
            <div className="row" style={{ marginTop: 8, alignItems: "flex-end" }}>
              <label className="field">Linha<input className="input" type="number" step={0.5} value={line} onChange={(e) => setLine(Number(e.target.value))} /></label>
              <label className="field">Odd over<input className="input" type="number" step={0.01} value={oo} onChange={(e) => setOo(Number(e.target.value))} /></label>
              <label className="field">Odd under<input className="input" type="number" step={0.01} value={ou} onChange={(e) => setOu(Number(e.target.value))} /></label>
              <button className="btn primary" disabled={save.isPending} onClick={() => save.mutate()}>{save.isSuccess ? "Salva ✓" : "Salvar"}</button>
            </div>
            {d.linha_ref && <div className="muted small" style={{ marginTop: 6 }}>Linha "ref" = L10 arredondado (não é da casa).</div>}
          </div>
          {expMin && (
            <div className="panel">
              <div className="row" style={{ justifyContent: "space-between" }}><b>E se jogar {mins} minutos?</b><span className="muted small">esperado {expMin}</span></div>
              <input type="range" min={10} max={44} value={mins} onChange={(e) => setMins(Number(e.target.value))} />
            </div>
          )}
          <div className="kpis">
            <div className="kpi"><div className="l">Projeção</div><div className={`v ${proj != null && proj > line ? "over" : "under"}`}>{num(proj)}</div>
              <div className="s">{proj != null ? `${(proj - line > 0 ? "+" : "")}${(proj - line).toFixed(1)} vs linha` : ""}</div></div>
            <div className="kpi"><div className="l">Over</div><div className="v">{pct(po)}</div><div className="s">odd justa {po ? (1 / po).toFixed(2) : "—"}</div></div>
            <div className="kpi"><div className="l">Under</div><div className="v">{pct(po == null ? null : 1 - po)}</div><div className="s">odd justa {po != null && po < 1 ? (1 / (1 - po)).toFixed(2) : "—"}</div></div>
            {ev && <div className="kpi"><div className="l">Valor esp.</div><div className={`v ${ev[1] > 0 ? "over" : "under"}`}>{ev[1] > 0 ? "+" : ""}{(100 * ev[1]).toFixed(1)}%</div><div className="s">no {ev[0]}</div></div>}
            <div className="kpi"><div className="l">DvP</div><div className={`v ${(d.dvp_rank ?? 15) >= 21 ? "over" : (d.dvp_rank ?? 15) <= 10 ? "under" : ""}`}>{d.dvp_rank ?? "—"}º</div><div className="s">30 = cede mais</div></div>
          </div>
          <BetForm d={d} mercado={mercado} data={data} line={line} oo={oo} ou={ou} po={po} />
          {d.checklist && (
            <div className="panel"><b>Checklist BetânIAG</b>
              <table className="ck" style={{ marginTop: 6 }}><tbody>
                {d.checklist.map((c) => (
                  <tr key={c.item}><td>{c.ok ? <span className="over">✓</span> : c.ok === false ? <span className="under">✗</span> : <span className="muted">•</span>}</td>
                    <td>{c.item}</td><td className="v">{c.valor}</td><td className="n">{c.nota}</td></tr>))}
              </tbody></table>
            </div>
          )}
          <div className="panel">
            <b>Desfalques</b> <span className="muted small">{d.jogo.injury_report ? `injury report ${d.jogo.injury_report.slice(11)} ET` : "fora no último jogo"}</span>
            <div className="small" style={{ marginTop: 6 }}>{d.jogo.fora}: {d.jogo.desfalques?.fora.join(", ") || "—"}<br />{d.jogo.casa}: {d.jogo.desfalques?.casa.join(", ") || "—"}</div>
            {d.com_sem?.map((c) => <div key={c.companheiro} className="small" style={{ marginTop: 6 }}>Com <b>{c.companheiro}</b>: {c.com ?? "—"} em {c.jogos_com} j · sem: {c.sem ?? "—"} em {c.jogos_sem} j</div>)}
            {d.jogo.margem_esperada != null && <div className="muted small" style={{ marginTop: 6 }}>
              Margem esperada: {d.jogo.margem_esperada >= 0 ? d.jogo.casa : d.jogo.fora} por {Math.abs(d.jogo.margem_esperada).toFixed(1)} · blowout {Math.round(100 * (d.jogo.risco_blowout ?? 0))}%</div>}
          </div>
          {d.proj_detalhe && (
            <div className="panel small"><b>De onde vem a projeção</b>
              <div style={{ marginTop: 6, lineHeight: 1.7 }}>
                Base {d.proj_detalhe.base} = taxa por minuto × {d.proj_detalhe.minutos} min<br />
                Defesa (DvP {d.dvp_rank ?? "—"}º): ×{d.proj_detalhe.f_dvp} · Ritmo: ×{d.proj_detalhe.f_ritmo}<br />
                Ajuste calibrado ({Math.round(100 * d.proj_detalhe.ausencia)}% do time fora): ×{d.proj_detalhe.f_ajuste}
                {d.proj_detalhe.erro_tipico && <><br /><span className="muted">Erro típico ±{d.proj_detalhe.erro_tipico}</span></>}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function BetForm({ d, mercado, data, line, oo, ou, po }: { d: Detalhe; mercado: string; data: string; line: number;
  oo: number; ou: number; po: number | null }) {
  const [lado, setLado] = useState<"over" | "under">(po != null && po < 0.5 ? "under" : "over");
  const [un, setUn] = useState(1);
  const [odd, setOdd] = useState(0);
  const [tags, setTags] = useState<string[]>([]);
  const [obs, setObs] = useState("");
  const [casa, setCasa] = useState(() => { try { return localStorage.getItem("casa") ?? ""; } catch { return ""; } });
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta });
  const qc = useQueryClient();
  const oddLado = odd || (lado === "over" ? oo : ou);
  const body = (confirmar = false) => ({ data, player_id: d.player_id, mercado, lado, linha: line, odd: oddLado, unidades: un,
    casa: casa || undefined, obs: obs || undefined, etiquetas: tags, confirmar });
  const m = useMutation({
    mutationFn: async () => {
      try { return await api2.apostar(body()); } catch (e) {
        if (e instanceof LimiteError && confirm(`${e.avisos.join("\n")}\n\nRegistrar mesmo assim?`)) return api2.apostar(body(true));
        throw e;
      }
    },
    onSuccess: () => { try { localStorage.setItem("casa", casa); } catch { /* sem storage */ } setTags([]); setObs("");
      qc.invalidateQueries({ queryKey: ["apostas"] }); },
  });
  const chance = po == null ? null : lado === "over" ? po : 1 - po;
  const toggle = (t: string) => setTags(tags.includes(t) ? tags.filter((x) => x !== t) : [...tags, t]);
  return (
    <div className="panel"><b>Registrar aposta</b> <span className="muted small">{lado} {line} · chance {chance == null ? "—" : `${Math.round(100 * chance)}%`}</span>
      <div className="row" style={{ marginTop: 8, alignItems: "flex-end" }}>
        <div className="seg">{(["over", "under"] as const).map((l) => <button key={l} className={l === lado ? "on" : ""} onClick={() => { setLado(l); setOdd(0); }}>{l === "over" ? "Over" : "Under"}</button>)}</div>
        <div className="seg">{[0.5, 1, 2].map((u) => <button key={u} className={u === un ? "on" : ""} onClick={() => setUn(u)}>{u}u</button>)}</div>
      </div>
      <div className="row" style={{ marginTop: 8, alignItems: "flex-end" }}>
        <label className="field">Odd<input className="input" type="number" step={0.01} value={oddLado || ""} onChange={(e) => setOdd(Number(e.target.value))} /></label>
        <label className="field">Casa<input className="input" value={casa} placeholder="opcional" onChange={(e) => setCasa(e.target.value)} /></label>
      </div>
      <div className="small muted" style={{ marginTop: 8 }}>Por quê? (diário: mostra quais motivos dão lucro)</div>
      <div className="tabs" style={{ marginTop: 4 }}>{(meta.data?.etiquetas ?? []).map((t) =>
        <button key={t} className={`tab ${tags.includes(t) ? "on" : ""}`} onClick={() => toggle(t)}>{t}</button>)}</div>
      <div className="row" style={{ marginTop: 8, alignItems: "flex-end" }}>
        <input className="input" style={{ flex: 1, minWidth: 140 }} placeholder="Nota (opcional)" value={obs} onChange={(e) => setObs(e.target.value)} />
        <button className="btn primary" disabled={m.isPending || !(oddLado > 1)} onClick={() => m.mutate()}>{m.isSuccess ? "Registrada ✓" : "Registrar"}</button>
      </div>
      {m.error && !(m.error instanceof LimiteError) && <div className="err small">{String((m.error as Error).message)}</div>}
      {m.data?.avisos?.length ? <div className="small" style={{ color: "#fcd9b6", marginTop: 6 }}>⚠ {m.data.avisos.join(" ")}</div> : null}
    </div>
  );
}

const col = createColumnHelper<JogoLog>();

function LogTable({ rows, d, mercado }: { rows: JogoLog[]; d: Detalhe; mercado: string }) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const stats = LOG_COLS.some(([k]) => k === mercado) ? LOG_COLS : [...LOG_COLS, [mercado, MARKETS[mercado]] as [string, string]];
  const columns = useMemo(() => [
    col.accessor("data", { header: "Data", cell: (c) => ddmm(c.getValue()) }),
    col.accessor("adv", { header: "Adv.", cell: (c) => `${c.row.original.em_casa ? "vs" : "@"} ${c.getValue()}` }),
    col.accessor((r) => r.margem ?? 0, { id: "res", header: "Res.",
      cell: (c) => c.row.original.resultado ? `${c.row.original.resultado} ${c.getValue() > 0 ? "+" : ""}${c.getValue()}` : "" }),
    ...stats.map(([k, label]) => col.accessor((r) => r[k] as number, {
      id: k, header: label,
      cell: (c) => Math.round(c.getValue() as number * 10) / 10,
    })),
  ], [mercado]); // eslint-disable-line
  const table = useReactTable({ data: rows, columns, state: { sorting }, onSortingChange: setSorting,
                                getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel() });
  return (
    <div className="tw">
      <table className="t">
        <thead>{table.getHeaderGroups().map((hg) => (
          <tr key={hg.id}>{hg.headers.map((h) => (
            <th key={h.id} onClick={h.column.getToggleSortingHandler()}
              style={h.id === mercado ? { color: "var(--text)" } : undefined}>
              {flexRender(h.column.columnDef.header, h.getContext())}{{ asc: " ▲", desc: " ▼" }[h.column.getIsSorted() as string] ?? ""}
            </th>))}</tr>))}
        </thead>
        <tbody>{table.getRowModel().rows.map((r) => (
          <tr key={r.id}>{r.getVisibleCells().map((c) => {
            const band = (r.original as unknown as { faixas?: Record<string, string | null> }).faixas?.[c.column.id];
            return <td key={c.id} className={band ? `b-${band}` : ""}
              style={c.column.id === mercado ? { boxShadow: "inset 2px 0 #e6edf3" } : undefined}>
              {flexRender(c.column.columnDef.cell, c.getContext())}</td>;
          })}</tr>))}
        </tbody>
      </table>
      {!rows.length && <div className="muted" style={{ padding: 12 }}>Sem jogos nesse recorte.</div>}
      <span hidden>{d.player_id}</span>
    </div>
  );
}
