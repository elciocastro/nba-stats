// Calibração pública: quando o site disse X% para um lado, quanto acertou.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CalResumo, calibracao } from "../api";
import { MARKETS } from "./Props";

const PRINCIPAIS = ["pts", "reb", "ast", "pra", "fg3m", "pr", "pa", "ra", "stl", "blk", "turnover"];

export default function Calibracao() {
  const q = useQuery({ queryKey: ["calibracao"], queryFn: calibracao });
  const [mk, setMk] = useState("pts");
  if (q.isLoading) return <div className="loading">Carregando…</div>;
  if (q.error) return <div className="err">{String((q.error as Error).message)}</div>;
  const c = q.data!;
  const bt = c.backtest[0];
  return (
    <>
      <h1>Calibração</h1>
      <p className="muted" style={{ maxWidth: 820, marginTop: 0 }}>
        Quando o site diz que um lado tem 60% de chance, ele deveria acertar perto de 60% das vezes, nem mais, nem menos.
        Aqui está a conta honesta, por faixa de chance. Barras parecidas = número confiável; acerto abaixo da chance = site otimista.
      </p>

      <h2>Jogos já disputados (backtest)</h2>
      {!bt ? <p className="muted">Ainda não calculado. Rode <code>nbastats calibracao 2026 --desde 2026-11-01</code>.</p> : (
        <>
          <p className="muted small" style={{ marginTop: 0 }}>Temporada {bt.temporada}/{String(bt.temporada + 1).slice(2)}
            {bt.desde ? ` desde ${bt.desde.slice(8, 10)}/${bt.desde.slice(5, 7)}` : ""}, fora da amostra usada para calibrar.
            Linha = L10 arredondado (a linha da casa costuma ser mais difícil). Atualizado em {new Date(bt.atualizado_em).toLocaleDateString("pt-BR")}.</p>
          <div className="tabs" style={{ marginBottom: 10 }}>{PRINCIPAIS.filter((k) => bt.mercados[k]?.n).map((k) =>
            <button key={k} className={`tab ${k === mk ? "on" : ""}`} onClick={() => setMk(k)}>{MARKETS[k]}</button>)}</div>
          <div className="grid2">
            <Grafico r={bt.mercados[mk]} />
            <Mercados m={bt.mercados} onPick={setMk} />
          </div>
        </>
      )}

      <h2>Previsões mostradas antes dos jogos</h2>
      <p className="muted small" style={{ marginTop: 0 }}>A chance que o site mostrou antes de cada jogo (foto guardada até o início), conferida depois.
        Pontos, rebotes, assistências, PRA e 3 pontos. A amostra cresce a cada dia.</p>
      {c.previsoes.geral.n < 30 ? <p className="muted">Ainda {c.previsoes.geral.n} previsões conferidas; os números ficam confiáveis com algumas centenas.</p> : (
        <div className="grid2">
          <Grafico r={c.previsoes.geral} />
          <div>
            <Mercados m={c.previsoes.mercados} />
            {c.previsoes.so_linha_da_casa.n > 0 && <p className="muted small">Só com linha da casa: {c.previsoes.so_linha_da_casa.n} previsões,
              chance média {c.previsoes.so_linha_da_casa.chance_media_pct}% × acerto {c.previsoes.so_linha_da_casa.acerto_pct}%.</p>}
          </div>
        </div>
      )}

      <h2>Suas apostas</h2>
      {c.apostas.n < 10 ? <p className="muted">{c.apostas.n} apostas conferidas até agora. O selo e a unidade sugerida (BetânIAG) só devem ser ligados com dezenas por faixa.</p> : (
        <div className="grid2"><Grafico r={c.apostas} /><Faixas r={c.apostas} /></div>
      )}
    </>
  );
}

function Grafico({ r }: { r?: CalResumo }) {
  if (!r?.n) return <div className="muted">Sem dados.</div>;
  return (
    <div className="chart">
      <div className="small muted" style={{ padding: "0 8px" }}>{r.n} palpites · acerto {r.acerto_pct}% com chance média {r.chance_media_pct}% · Brier {r.brier}</div>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={r.faixas} margin={{ top: 10, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="#1d2632" />
          <XAxis dataKey="faixa" tick={{ fill: "#8b98a9", fontSize: 11 }} />
          <YAxis domain={[40, 100]} tick={{ fill: "#8b98a9", fontSize: 11 }} unit="%" />
          <Tooltip contentStyle={{ background: "#121821", border: "1px solid #263040" }}
            formatter={(v, n, p) => [`${v}%${n === "Acerto real" ? ` (${p.payload.n} palpites)` : ""}`, n]} />
          <Legend />
          <Bar dataKey="chance_media_pct" name="Chance prometida" fill="#64748b" radius={[2, 2, 0, 0]} />
          <Bar dataKey="acerto_pct" name="Acerto real" fill="#22c55e" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function Faixas({ r }: { r: CalResumo }) {
  return (
    <div className="tw"><table className="t">
      <thead><tr><th>Faixa</th><th>Palpites</th><th>Chance</th><th>Acerto</th><th>Diferença</th></tr></thead>
      <tbody>{r.faixas.map((f) => {
        const d = Math.round((f.acerto_pct - f.chance_media_pct) * 10) / 10;
        return <tr key={f.faixa}><td>{f.faixa}</td><td>{f.n}</td><td>{f.chance_media_pct}%</td><td>{f.acerto_pct}%</td>
          <td className={Math.abs(d) < 3 ? "" : d > 0 ? "over" : "under"}>{d > 0 ? "+" : ""}{d} p.p.</td></tr>;
      })}</tbody></table></div>
  );
}

function Mercados({ m, onPick }: { m: Record<string, CalResumo>; onPick?: (k: string) => void }) {
  const rows = Object.entries(m).filter(([, r]) => r.n).sort(([a], [b]) => (PRINCIPAIS.indexOf(a) + 99 * +!PRINCIPAIS.includes(a)) - (PRINCIPAIS.indexOf(b) + 99 * +!PRINCIPAIS.includes(b)));
  return (
    <div className="tw" style={{ maxHeight: 340 }}><table className="t">
      <thead><tr><th>Mercado</th><th>Palpites</th><th>Chance média</th><th>Acerto</th><th>Brier</th></tr></thead>
      <tbody>{rows.map(([k, r]) => {
        const d = (r.acerto_pct ?? 0) - (r.chance_media_pct ?? 0);
        return <tr key={k} style={onPick ? { cursor: "pointer" } : undefined} onClick={() => onPick?.(k)}>
          <td>{MARKETS[k] ?? k}</td><td>{r.n}</td><td>{r.chance_media_pct}%</td>
          <td className={Math.abs(d) < 3 ? "" : d > 0 ? "over" : "under"}>{r.acerto_pct}%</td><td>{r.brier}</td></tr>;
      })}</tbody></table></div>
  );
}
