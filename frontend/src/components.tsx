import { useState } from "react";
import { headshot, Selo } from "./api";

// Taxa de over -> cor (verde forte a vermelho forte). Só visual.
export function heat(pct: number | null | undefined): { background: string; color: string } {
  if (pct === null || pct === undefined) return { background: "transparent", color: "var(--h-none-t)" };
  if (pct >= 70) return { background: "var(--h-strong)", color: "var(--h-strong-t)" };
  if (pct >= 58) return { background: "var(--h-good)", color: "var(--h-good-t)" };
  if (pct >= 43) return { background: "var(--h-mid)", color: "var(--h-mid-t)" };
  if (pct >= 31) return { background: "var(--h-bad)", color: "var(--h-bad-t)" };
  return { background: "var(--h-worst)", color: "var(--h-worst-t)" };
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
        const fill = line == null ? "var(--muted)" : v > line ? "var(--over)" : "var(--under)";
        return <rect key={i} x={i * (bw + gap)} y={h - bh} width={bw} height={bh} rx={1.5} fill={fill}><title>{v}</title></rect>;
      })}
      {line != null && <line x1={0} x2={w} y1={h - (h * line) / top} y2={h - (h * line) / top}
        stroke="var(--text)" strokeDasharray="3,2" opacity={0.7} />}
    </svg>
  );
}

// ---------- tabela ordenável ----------
import { ColumnDef, flexRender, getCoreRowModel, getSortedRowModel, SortingState, useReactTable } from "@tanstack/react-table";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { api, Favoritos } from "./api";

export function DataTable<T>({ data, columns, onRow, cellClass, initialSort, maxHeight = 680 }: {
  data: T[]; columns: ColumnDef<T, any>[]; onRow?: (r: T) => void;
  cellClass?: (r: T, col: string) => string | React.CSSProperties | undefined;
  initialSort?: SortingState; maxHeight?: number;
}) {
  const [sorting, setSorting] = useState<SortingState>(initialSort ?? []);
  const table = useReactTable({ data, columns, state: { sorting }, onSortingChange: setSorting,
                                getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel() });
  return (
    <div className="tw" style={{ maxHeight }}>
      <table className="t">
        <thead>{table.getHeaderGroups().map((hg) => (
          <tr key={hg.id}>{hg.headers.map((h) => (
            <th key={h.id} onClick={h.column.getToggleSortingHandler()} title={String(h.column.columnDef.meta ?? "")}>
              {flexRender(h.column.columnDef.header, h.getContext())}
              {{ asc: " ▲", desc: " ▼" }[h.column.getIsSorted() as string] ?? ""}
            </th>))}</tr>))}
        </thead>
        <tbody>{table.getRowModel().rows.map((r) => (
          <tr key={r.id} onClick={onRow ? () => onRow(r.original) : undefined} style={onRow ? { cursor: "pointer" } : undefined}>
            {r.getVisibleCells().map((c) => {
              const x = cellClass?.(r.original, c.column.id);
              return <td key={c.id} className={typeof x === "string" ? x : undefined} style={typeof x === "object" ? x : undefined}>
                {flexRender(c.column.columnDef.cell, c.getContext())}</td>;
            })}</tr>))}
        </tbody>
      </table>
      {!data.length && <div className="muted" style={{ padding: 14 }}>Nada com esses filtros.</div>}
    </div>
  );
}

// ---------- favoritos ----------
export function useFavs() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["favoritos"], queryFn: api.favoritos, staleTime: 300_000 });
  const set = (d: Favoritos) => qc.setQueryData(["favoritos"], d);
  const add = useMutation({ mutationFn: (v: { tipo: string; id: number; nome?: string }) => api.favoritar(v.tipo, v.id, v.nome), onSuccess: set });
  const del = useMutation({ mutationFn: (v: { tipo: string; id: number }) => api.desfavoritar(v.tipo, v.id), onSuccess: set });
  const favs = q.data ?? { jogador: [], time: [], jogo: [] };
  const has = (tipo: keyof Favoritos, id: number) => favs[tipo].some((f) => f.entity_id === id);
  const toggle = (tipo: keyof Favoritos, id: number, nome?: string) =>
    has(tipo, id) ? del.mutate({ tipo, id }) : add.mutate({ tipo, id, nome });
  // jogador favorito, do time favorito ou no jogo favorito
  const playerFav = (p: { player_id: number; time_id?: number; game_id?: number }) =>
    has("jogador", p.player_id) || (p.time_id != null && has("time", p.time_id)) || (p.game_id != null && has("jogo", p.game_id));
  return { favs, has, toggle, playerFav };
}

export function Star({ on, onClick, title }: { on: boolean; onClick: () => void; title?: string }) {
  return <button className={`star ${on ? "on" : ""}`} title={title ?? (on ? "Tirar dos favoritos" : "Favoritar")}
    onClick={(e) => { e.stopPropagation(); onClick(); }}>{on ? "★" : "☆"}</button>;
}

export function useMobile(px = 760) {
  const [m, setM] = useState(() => window.matchMedia(`(max-width: ${px}px)`).matches);
  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${px}px)`);
    const f = () => setM(mq.matches);
    mq.addEventListener("change", f);
    return () => mq.removeEventListener("change", f);
  }, [px]);
  return m;
}

/** Baixa uma tabela como CSV (Excel abre direto: BOM UTF-8 e separador vírgula). */
export function baixarCsv(nome: string, linhas: Record<string, unknown>[], colunas: [string, string][]) {
  const esc = (v: unknown) => { const t = v == null ? "" : Array.isArray(v) ? v.join(" | ") : String(v);
    return /[",;\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t; };
  const body = [colunas.map(([, r]) => esc(r)).join(","), ...linhas.map((l) => colunas.map(([k]) => esc(l[k])).join(","))].join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob(["\ufeff" + body], { type: "text/csv;charset=utf-8" }));
  a.download = nome.endsWith(".csv") ? nome : `${nome}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}
