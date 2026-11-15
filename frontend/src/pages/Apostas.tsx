// Apostas: registro, conferência automática e desempenho (acerto real x chance).
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api2, Bet, Resumo } from "../api";
import { ddmm } from "../components";

const MK: Record<string, string> = { pts: "Pontos", reb: "Rebotes", ast: "Assist.", pra: "PRA", pr: "PR", pa: "PA", ra: "RA",
  fg3m: "3FM", fg3a: "3FA", fg2m: "2FM", fg2a: "2FA", ftm: "FTM", fta: "FTA", stl: "Roubos", blk: "Tocos", turnover: "Turnovers" };
const ICON: Record<string, string> = { ganha: "✅", perdida: "❌", devolvida: "↩️", anulada: "⛔", pendente: "⏳" };
const STATUS = ["pendente", "ganha", "perdida", "devolvida", "anulada"];

export default function Apostas() {
  const [status, setStatus] = useState<string | undefined>();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["apostas", status], queryFn: () => api2.apostas(status) });
  const conferir = useMutation({ mutationFn: api2.conferir, onSuccess: () => qc.invalidateQueries({ queryKey: ["apostas"] }) });
  const apagar = useMutation({ mutationFn: api2.apagarAposta, onSuccess: () => qc.invalidateQueries({ queryKey: ["apostas"] }) });

  if (q.isLoading) return <div className="loading">Carregando…</div>;
  if (q.error) return <div className="err">{String((q.error as Error).message)}</div>;
  const { apostas, desempenho: d, config } = q.data!;
  const g = d.geral;
  const cls = g.lucro_unidades > 0 ? "over" : g.lucro_unidades < 0 ? "under" : "";

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1>Apostas</h1>
        <button className="btn" disabled={conferir.isPending} onClick={() => conferir.mutate()}>
          {conferir.isPending ? "Conferindo…" : conferir.data ? `Conferidas: ${Object.values(conferir.data.conferidas).reduce((a, b) => a + b, 0)}` : "Conferir resultados"}</button>
      </div>
      {!g.apostas ? (
        <p className="muted">Nenhuma aposta registrada. Registre pela página do jogador (“Registrar aposta”).</p>
      ) : (
        <>
          <div className="kpis" style={{ marginTop: 12 }}>
            <div className="kpi"><div className="l">Apostas</div><div className="v">{g.apostas}</div><div className="s">{g.pendentes} pendentes</div></div>
            <div className="kpi"><div className="l">Acerto</div><div className="v">{g.acerto_pct == null ? "—" : `${Math.round(g.acerto_pct)}%`}</div>
              <div className="s">{g.chance_media_pct == null ? "" : `chance média ${Math.round(g.chance_media_pct)}%`}</div></div>
            <div className="kpi"><div className="l">Lucro</div><div className={`v ${cls}`}>{g.lucro_unidades > 0 ? "+" : ""}{g.lucro_unidades.toFixed(2)} u</div>
              <div className="s">{config.valor_unidade ? `${config.moeda} ${(g.lucro_unidades * config.valor_unidade).toFixed(2)}` : ""}</div></div>
            <div className="kpi"><div className="l">ROI</div><div className={`v ${cls}`}>{g.roi_pct == null ? "—" : `${g.roi_pct > 0 ? "+" : ""}${g.roi_pct.toFixed(1)}%`}</div>
              <div className="s">{g.unidades_apostadas} u apostadas</div></div>
          </div>
          <p className="muted small">Acerto real × chance média calculada: se o acerto fica abaixo da chance por muitas apostas, o método está otimista. ROI só ganha significado depois de dezenas de apostas.</p>
          {d.curva.length >= 2 && (
            <div className="chart"><ResponsiveContainer width="100%" height={200}>
              <AreaChart data={d.curva.map((c) => ({ ...c, x: ddmm(c.data) }))} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="#1d2632" />
                <XAxis dataKey="x" tick={{ fill: "#8b98a9", fontSize: 11 }} /><YAxis tick={{ fill: "#8b98a9", fontSize: 11 }} />
                <Tooltip contentStyle={{ background: "#121821", border: "1px solid #263040" }} formatter={(v) => [`${v} u`, "lucro acumulado"]} />
                <Area dataKey="lucro_acumulado" stroke="#22c55e" fill="#22c55e" fillOpacity={0.12} />
              </AreaChart></ResponsiveContainer></div>
          )}
        </>
      )}

      <h2>Registro</h2>
      <div className="tabs" style={{ marginBottom: 8 }}>
        <button className={`tab ${!status ? "on" : ""}`} onClick={() => setStatus(undefined)}>Todas</button>
        {STATUS.map((s) => <button key={s} className={`tab ${s === status ? "on" : ""}`} onClick={() => setStatus(s)}>{ICON[s]} {s}</button>)}
      </div>
      <div className="tw"><table className="t">
        <thead><tr><th>Jogador</th><th>Aposta</th><th>Odd</th><th>Unid.</th><th>Chance</th><th>Real</th><th>Lucro</th><th>Data</th><th>Casa</th><th></th></tr></thead>
        <tbody>{apostas.map((b: Bet) => (
          <tr key={b.id}>
            <td>{ICON[b.status]} <b>{b.jogador}</b></td>
            <td>{b.side === "over" ? "Over" : "Under"} {b.line} {MK[b.market] ?? b.market}</td>
            <td>{b.odd.toFixed(2)}</td><td>{b.units}</td>
            <td>{b.prob == null ? "—" : `${Math.round(100 * b.prob)}%`}</td>
            <td>{b.actual ?? "—"}</td>
            <td className={b.profit_units == null ? "" : b.profit_units > 0 ? "over" : b.profit_units < 0 ? "under" : ""}>
              {b.profit_units == null ? "—" : `${b.profit_units > 0 ? "+" : ""}${b.profit_units.toFixed(2)}`}</td>
            <td>{ddmm(b.date)}</td><td>{b.bookmaker ?? ""}</td>
            <td><button className="star" title="Apagar" onClick={() => confirm(`Apagar a aposta em ${b.jogador}?`) && apagar.mutate(b.id)}>🗑</button></td>
          </tr>))}
        </tbody></table>
        {!apostas.length && <div className="muted" style={{ padding: 12 }}>Nada aqui.</div>}
      </div>

      {g.conferidas > 0 && (
        <>
          <h2>Desempenho por grupo</h2>
          <div className="grid2">
            {([["mercado", "Por mercado"], ["unidades", "Por unidades"], ["faixa_chance", "Por faixa de chance calculada"], ["lado", "Over × under"]] as const).map(([k, title]) => (
              <div key={k}><div className="small muted" style={{ marginBottom: 4 }}>{title}</div><Group rows={d[k]} label={k === "mercado" ? (x) => MK[x] ?? x : (x) => x} /></div>))}
          </div>
        </>
      )}
    </>
  );
}

function Group({ rows, label }: { rows: Record<string, Resumo>; label: (k: string) => string }) {
  return (
    <div className="tw"><table className="t">
      <thead><tr><th>Grupo</th><th>Apostas</th><th>Acerto</th><th>Chance méd.</th><th>Lucro</th><th>ROI</th></tr></thead>
      <tbody>{Object.entries(rows).map(([k, v]) => (
        <tr key={k}><td>{label(k)}</td><td>{v.conferidas}</td><td>{v.acerto_pct == null ? "—" : `${v.acerto_pct}%`}</td>
          <td>{v.chance_media_pct == null ? "—" : `${v.chance_media_pct}%`}</td>
          <td className={v.lucro_unidades > 0 ? "over" : v.lucro_unidades < 0 ? "under" : ""}>{v.lucro_unidades}</td>
          <td>{v.roi_pct == null ? "—" : `${v.roi_pct}%`}</td></tr>))}
      </tbody></table></div>
  );
}
