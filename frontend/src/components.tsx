import { useState } from "react";
import { headshot, Selo } from "./api";

// Taxa de over -> cor (verde forte a vermelho forte). Só visual.
export function heat(pct: number | null | undefined): { background: string; color: string } {
  if (pct === null || pct === undefined) return { background: "transparent", color: "#5b6676" };
  if (pct >= 70) return { background: "var(--h-strong)", color: "#fff" };
  if (pct >= 58) return { background: "var(--h-good)", color: "#dcfce7" };
  if (pct >= 43) return { background: "var(--h-mid)", color: "#cbd5e1" };
  if (pct >= 31) return { background: "var(--h-bad)", color: "#fee2e2" };
  return { background: "var(--h-worst)", color: "#fff" };
}

export const pct = (x: number | null | undefined) => (x === null || x === undefined ? "—" : `${Math.round(100 * x)}%`);
export const num = (x: number | null | undefined, d = 1) => (x === null || x === undefined ? "—" : x.toFixed(d));
export const ddmm = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;

export function Photo({ id, big }: { id: number; big?: boolean }) {
  const [ok, setOk] = useState(true);
  return ok ? <img className={big ? "ph big" : "ph"} src={headshot(id)} loading="lazy" alt="" onError={() => setOk(false)} />
    : <div className={big ? "ph big" : "ph"} />;
}

export function SealBadge({ s, children }: { s: Selo | null | undefined; children?: React.ReactNode }) {
  if (!s) return <>{children}</>;
  return <span className="sl" style={{ background: s.cor, color: s.texto }} title={`BetânIAG: ${s.nivel}`}>
    {children ?? s.nivel}{s.unidade != null ? ` · ${s.unidade}u` : ""}</span>;
}

// Barras dos últimos jogos (mais antigo à esquerda), verdes acima da linha.
export function Bars({ values, line, w = 150, h = 36 }: { values: number[]; line: number | null; w?: number; h?: number }) {
  if (!values.length) return <svg width={w} height={h} />;
  const top = Math.max(...values, (line ?? 0) * 1.4, 1);
  const gap = 2, bw = Math.max((w - gap * (values.length - 1)) / values.length, 2);
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ flexShrink: 0 }}>
      {values.map((v, i) => {
        const bh = Math.max((h * v) / top, 2);
        const fill = line == null ? "#8b98a9" : v > line ? "var(--over)" : "var(--under)";
        return <rect key={i} x={i * (bw + gap)} y={h - bh} width={bw} height={bh} rx={1.5} fill={fill}><title>{v}</title></rect>;
      })}
      {line != null && <line x1={0} x2={w} y1={h - (h * line) / top} y2={h - (h * line) / top}
        stroke="#e6edf3" strokeDasharray="3,2" opacity={0.7} />}
    </svg>
  );
}
