// Área Props integrada (sugestão do Coni): Props, Linhas, Matchups, DvP e
// Potenciais como abas, com o mesmo dia, mercado, jogos, busca e favoritos.
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ColumnDef, createColumnHelper } from "@tanstack/react-table";
import { api, Filtro, FiltroParams, filtros, Jogador, Jogo, LinhaIn, Potencial } from "../api";
import { usePrefs, Esqueleto } from "../App";
import { baixarCsv, Bars, DataTable, heat, num, Photo, SealBadge, Star, useFavs, useMobile } from "../components";

export const MARKETS: Record<string, string> = {
  pts: "Pontos", reb: "Rebotes", ast: "Assist.", pra: "PRA", pr: "PR", pa: "PA", ra: "RA", fg3m: "3FM",
  fg3a: "3FA", fg2m: "2FM", fg2a: "2FA", ftm: "FTM", fta: "FTA", stl: "Roubos", blk: "Tocos", turnover: "Turnovers",
  dd: "Duplo-duplo", td: "Triplo-duplo",
};
const ABAS: Record<string, string> = { props: "Props", linhas: "Linhas", matchups: "Matchups", dvp: "DvP", potenciais: "Potenciais" };
const WIN: Record<string, number | null> = { L5: 5, L10: 10, L20: 20, Temp: null };

export default function Props() {
  const [sp, setSp] = useSearchParams();
  const aba = sp.get("aba") ?? "props";
  const mercado = sp.get("mercado") ?? "pts";
  const set = (k: string, v: string | null) => { const n = new URLSearchParams(sp); v == null ? n.delete(k) : n.set(k, v); setSp(n, { replace: true }); };
  const { data, betaniag } = usePrefs();
  const [jogos, setJogos] = useState<number[]>([]);
  const [busca, setBusca] = useState("");
  const [soFav, setSoFav] = useState(false);
  const [chanceMin, setChanceMin] = useState(0);
  const [lado, setLado] = useState("");
  const [soCasa, setSoCasa] = useState(false);
  const [semDuvida, setSemDuvida] = useState(false);
  const fav = useFavs();
  const atual: FiltroParams = { aba, mercado, chance_min: chanceMin, lado, so_casa: soCasa, so_fav: soFav, sem_duvida: semDuvida };
  const aplicar = (f: FiltroParams) => {
    const n = new URLSearchParams(sp);
    if (f.aba) n.set("aba", f.aba);
    if (f.mercado) n.set("mercado", f.mercado);
    setSp(n, { replace: true });
    setChanceMin(f.chance_min ?? 0); setLado(f.lado ?? ""); setSoCasa(!!f.so_casa); setSoFav(!!f.so_fav); setSemDuvida(!!f.sem_duvida);
  };
  const usesPlayers = ["props", "linhas", "matchups"].includes(aba);
  const q = useQuery({ queryKey: ["props", data, mercado, betaniag], enabled: usesPlayers,
                       queryFn: () => api.props(data, mercado, betaniag) });

  const players = useMemo(() => (q.data?.jogadores ?? []).filter((p) =>
    (!jogos.length || jogos.includes(p.game_id)) &&
    (!busca || p.jogador.toLowerCase().includes(busca.toLowerCase())) &&
    (!soFav || fav.playerFav(p)) &&
    (!chanceMin || (p.chance ?? 0) * 100 >= chanceMin) &&
    (!lado || p.lado === lado) &&
    (!soCasa || (p.linha != null && !p.linha_ref)) &&
    (!semDuvida || !p.lesao)), [q.data, jogos, busca, soFav, fav, chanceMin, lado, soCasa, semDuvida]);

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}><h1>Props</h1>
        <span className="row"><span className="muted small">{q.data ? `${players.length} jogadores · ${q.data.jogos.length} jogos` : ""}</span>
          {usesPlayers && q.data && <button className="btn" onClick={() => baixarCsv(`props-${mercado}-${data}`,
            players.map((p) => ({ ...p, chance_pct: p.chance == null ? null : Math.round(100 * p.chance), linha_tipo: p.linha_ref ? "ref" : "casa" })),
            [["jogador", "Jogador"], ["time", "Time"], ["adversario", "Adversário"], ["linha", "Linha"], ["linha_tipo", "Tipo de linha"],
             ["odd_over", "Odd over"], ["odd_under", "Odd under"], ["proj", "Projeção"], ["diff", "Proj − linha"], ["lado", "Lado"],
             ["chance_pct", "Chance %"], ["ev", "Valor esperado"], ["l5", "L5"], ["l10", "L10"], ["temporada", "Temporada"],
             ["min_l10", "Min L10"], ["dvp_rank", "DvP rank"], ["lesao", "Lesão"]])}>⤓ CSV</button>}</span></div>
      <nav className="areatabs">{Object.entries(ABAS).map(([k, v]) => (
        <a key={k} className={k === aba ? "on" : ""} onClick={() => set("aba", k)} href={`?aba=${k}&mercado=${mercado}`}
           onClickCapture={(e) => e.preventDefault()}>{v}</a>))}</nav>

      {aba !== "potenciais" && (
        <div className="sticky-tools">
          <div className="tabs">{Object.entries(MARKETS).map(([k, v]) => (
            <button key={k} className={`tab ${k === mercado ? "on" : ""}`} onClick={() => set("mercado", k)}>{v}</button>))}</div>
          {usesPlayers && q.data && (
            <>
              <div className="tabs">{q.data.jogos.map((g) => <GameChip key={g.id} g={g} on={jogos.includes(g.id)}
                onClick={() => setJogos(jogos.includes(g.id) ? jogos.filter((x) => x !== g.id) : [...jogos, g.id])} />)}</div>
              <div className="row">
                <input className="input" placeholder="Buscar jogador" value={busca} onChange={(e) => setBusca(e.target.value)} style={{ width: 180 }} />
                <label className="toggle"><input type="checkbox" checked={soFav} onChange={(e) => setSoFav(e.target.checked)} />Só favoritos ★</label>
                <select className="input" value={chanceMin} onChange={(e) => setChanceMin(Number(e.target.value))} title="Chance mínima do lado mais provável">
                  {[0, 55, 60, 65, 70].map((c) => <option key={c} value={c}>{c ? `Chance ≥ ${c}%` : "Qualquer chance"}</option>)}</select>
                <select className="input" value={lado} onChange={(e) => setLado(e.target.value)}>
                  <option value="">Over e under</option><option value="over">Só over</option><option value="under">Só under</option></select>
                <label className="toggle"><input type="checkbox" checked={soCasa} onChange={(e) => setSoCasa(e.target.checked)} />Só linha da casa</label>
                <label className="toggle" title="Esconde quem está no injury report (Questionable, Probable...)">
                  <input type="checkbox" checked={semDuvida} onChange={(e) => setSemDuvida(e.target.checked)} />Sem dúvida de lesão</label>
              </div>
              <FiltrosSalvos atual={atual} aplicar={aplicar} />
            </>
          )}
        </div>
      )}

      {usesPlayers && q.isLoading && <Esqueleto />}
      {usesPlayers && q.error && <div className="err">{String((q.error as Error).message)}</div>}
      {usesPlayers && q.data && !q.data.jogos.length && <div className="muted">Nenhum jogo nesta data.</div>}
      {aba === "props" && q.data && <PropsTab players={players} mercado={mercado} temp={q.data.temporada} ant={q.data.anterior} />}
      {aba === "linhas" && q.data && <LinhasTab players={players} mercado={mercado} />}
      {aba === "matchups" && q.data && <MatchupsTab players={players} mercado={mercado} jogos={q.data.jogos} />}
      {aba === "dvp" && <DvpTab mercado={mercado} />}
      {aba === "potenciais" && <PotenciaisTab busca={busca} setBusca={setBusca} />}
    </>
  );
}

function FiltrosSalvos({ atual, aplicar }: { atual: FiltroParams; aplicar: (f: FiltroParams) => void }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["filtros"], queryFn: filtros.listar, staleTime: 300_000 });
  const set = (d: { filtros: Filtro[] }) => qc.setQueryData(["filtros"], d);
  const salvar = useMutation({ mutationFn: (nome: string) => filtros.salvar(nome, atual), onSuccess: set,
                               onError: (e) => alert((e as Error).message) });
  const apagar = useMutation({ mutationFn: filtros.apagar, onSuccess: set });
  return (
    <div className="tabs">
      <span className="muted small" style={{ alignSelf: "center" }}>Meus filtros:</span>
      {q.data?.filtros.map((f) => (
        <span key={f.id} className="gchip">
          <button className="tab" onClick={() => aplicar(f.params)} title={JSON.stringify(f.params)}>{f.nome}</button>
          <button className="star" title="Apagar filtro" onClick={() => confirm(`Apagar o filtro "${f.nome}"?`) && apagar.mutate(f.id)}>×</button>
        </span>))}
      <button className="tab" onClick={() => { const n = prompt("Nome do filtro (ex.: PRA chance ≥ 60%)"); if (n) salvar.mutate(n); }}>+ Salvar atual</button>
    </div>
  );
}

function GameChip({ g, on, onClick }: { g: Jogo; on: boolean; onClick: () => void }) {
  const fav = useFavs();
  const when = g.placar_casa != null ? `${g.placar_fora}-${g.placar_casa}` : (g.status ?? "").replace(" ET", "");
  return (
    <span className="gchip">
      <button className={`tab ${on ? "on" : ""}`} onClick={onClick}>
        {g.fora} @ {g.casa} {when}{g.risco_blowout != null ? ` · ${Math.round(100 * g.risco_blowout)}% blowout` : ""}
      </button>
      <Star on={fav.has("jogo", g.id)} onClick={() => fav.toggle("jogo", g.id, `${g.fora} @ ${g.casa}`)} />
    </span>
  );
}

function PlayerName({ p }: { p: Jogador }) {
  const fav = useFavs();
  return (
    <div className="pname">
      <Star on={fav.has("jogador", p.player_id)} onClick={() => fav.toggle("jogador", p.player_id, p.jogador)} />
      <Photo id={p.player_id} />
      <div style={{ lineHeight: 1.2, textAlign: "left" }}>
        <div style={{ fontWeight: 650 }}>{p.jogador}{p.lesao && <> <span className="tag">{p.lesao}</span></>}
          {p.fora_ultimo_jogo && !p.lesao && <span title="Não jogou a última partida: confirmar"> ⚠</span>}</div>
        <div className="muted small">{p.time} x {p.adversario}</div>
      </div>
    </div>
  );
}

const ch = createColumnHelper<Jogador>();
const sideTxt = (p: Jogador) => p.chance == null ? "—" : `${p.lado === "over" ? "▲" : "▼"} ${Math.round(100 * p.chance)}%`;

// ---------- Props ----------
function PropsTab({ players, mercado, temp, ant }: { players: Jogador[]; mercado: string; temp: string; ant: string }) {
  const nav = useNavigate();
  const mobile = useMobile();
  const [win, setWin] = useState("L10");
  const open = (p: Jogador) => nav(`/jogador/${p.player_id}?mercado=${mercado}`);
  const vals = (p: Jogador) => { const v = p.valores.map((x) => x.valor); return WIN[win] ? v.slice(-WIN[win]!) : v; };
  const rateCols = [temp, "H2H", "L5", "L10", "L20", ant];
  const columns = useMemo<ColumnDef<Jogador, any>[]>(() => [
    ch.accessor("jogador", { header: "Jogador", cell: (c) => <PlayerName p={c.row.original} /> }),
    ch.accessor((p) => p.selo?.nivel ?? "", { id: "selo", header: "BetânIAG", cell: (c) => <SealBadge s={c.row.original.selo} /> }),
    ch.accessor("linha", { header: "Linha", cell: (c) => c.getValue() == null ? "—" : `${c.getValue()}${c.row.original.linha_ref ? " ref" : ""}` }),
    ch.accessor("odd_over", { header: "O", cell: (c) => c.getValue()?.toFixed(2) ?? "—", meta: "Odd over" }),
    ch.accessor("odd_under", { header: "U", cell: (c) => c.getValue()?.toFixed(2) ?? "—", meta: "Odd under" }),
    ...rateCols.map((k) => ch.accessor((p) => p.janelas?.[k]?.pct ?? -1, {
      id: `r_${k}`, header: k, meta: k === "H2H" ? "Over contra o adversário, todas as temporadas" : `Over na janela ${k}`,
      cell: (c) => c.getValue() < 0 ? "—" : `${c.getValue()}%`,
    })),
    ch.accessor("proj", { header: "Proj", cell: (c) => num(c.getValue()) }),
    ch.accessor("diff", { header: "Diff", cell: (c) => c.getValue() == null ? "—" : `${c.getValue() > 0 ? "+" : ""}${c.getValue().toFixed(1)}`, meta: "Projeção − linha" }),
    ch.accessor((p) => p.chance ?? 0, { id: "chance", header: "Chance", cell: (c) => sideTxt(c.row.original) }),
    ch.accessor((p) => p.ev ?? -9, { id: "ev", header: "EV", cell: (c) => c.getValue() <= -9 ? "—" : `${c.getValue() > 0 ? "+" : ""}${Math.round(100 * c.getValue())}%`, meta: "Valor esperado (com odd da casa)" }),
    ch.accessor("dvp_rank", { header: "DvP", cell: (c) => c.getValue() ? `${c.getValue()}º` : "—", meta: "Rank da defesa na posição (30 = cede mais)" }),
    ch.display({ id: "bars", header: `${win} vs linha`, cell: (c) => <Bars values={vals(c.row.original)} line={c.row.original.linha} w={140} h={30} /> }),
  ], [mercado, win, temp, ant]); // eslint-disable-line

  const cls = (p: Jogador, col: string) => {
    if (col.startsWith("r_")) { const v = p.janelas?.[col.slice(2)]?.pct; return { ...heat(v), fontWeight: 700 }; }
    if (col === "proj" || col === "diff") return p.diff == null ? undefined : { color: p.diff > 0 ? "var(--over)" : "var(--under)", fontWeight: 700 };
    if (col === "dvp" || col === "dvp_rank") return p.dvp_rank == null ? undefined : { color: p.dvp_rank >= 21 ? "var(--over)" : p.dvp_rank <= 10 ? "var(--under)" : undefined };
    if (col === "ev") return p.ev == null ? undefined : { color: p.ev > 0 ? "var(--over)" : "var(--under)" };
    return undefined;
  };

  return (
    <>
      <div className="row" style={{ marginBottom: 8 }}>
        <div className="seg">{Object.keys(WIN).map((w) => <button key={w} className={w === win ? "on" : ""} onClick={() => setWin(w)}>{w}</button>)}</div>
        <span className="muted small">% = vezes acima da linha na janela · clique no cabeçalho para ordenar e na linha para abrir o jogador</span>
      </div>
      {mobile ? (
        <div className="plist">{players.map((p) => (
          <div className="prow" key={p.player_id} onClick={() => open(p)}>
            <Photo id={p.player_id} />
            <div className="who">
              <div className="nm">{p.jogador}<small>{p.time}</small> {p.lesao && <span className="tag">{p.lesao}</span>}</div>
              <div className="ln">{p.linha ?? "—"}{p.linha_ref ? " ref" : ""} · x {p.adversario}{p.janelas?.H2H?.jogos ? ` · H2H ${p.janelas.H2H.over}/${p.janelas.H2H.jogos}` : ""}</div>
            </div>
            <div className="ed"><div className="l">PROJ</div><div className={`v ${(p.diff ?? 0) > 0 ? "over" : "under"}`}>{num(p.proj)}</div>
              <div className="small"><SealBadge s={p.selo}>{sideTxt(p)}</SealBadge></div></div>
            <Bars values={vals(p)} line={p.linha} w={84} h={32} />
          </div>))}
        </div>
      ) : (
        <DataTable data={players} columns={columns} onRow={open} cellClass={cls} initialSort={[{ id: "chance", desc: true }]} maxHeight={900} />
      )}
    </>
  );
}

// ---------- Linhas ----------
type Edit = { linha: string; odd_over: string; odd_under: string };

function LinhasTab({ players, mercado }: { players: Jogador[]; mercado: string }) {
  const { data } = usePrefs();
  const qc = useQueryClient();
  const [edits, setEdits] = useState<Record<number, Edit>>({});
  const save = useMutation({
    mutationFn: () => api.salvarLinhas(Object.entries(edits).map(([id, e]): LinhaIn => ({
      data, player_id: Number(id), mercado, linha: e.linha === "" ? null : Number(e.linha),
      odd_over: e.odd_over === "" ? null : Number(e.odd_over), odd_under: e.odd_under === "" ? null : Number(e.odd_under),
    }))),
    onSuccess: () => { setEdits({}); qc.invalidateQueries({ queryKey: ["props"] }); qc.invalidateQueries({ queryKey: ["inicio"] }); },
  });
  const cur = (p: Jogador): Edit => edits[p.player_id] ?? {
    linha: p.linha_ref || p.linha == null ? "" : String(p.linha),
    odd_over: p.odd_over == null ? "" : String(p.odd_over), odd_under: p.odd_under == null ? "" : String(p.odd_under),
  };
  const change = (p: Jogador, k: keyof Edit, v: string) => setEdits({ ...edits, [p.player_id]: { ...cur(p), [k]: v } });
  const n = Object.keys(edits).length;
  const columns = useMemo<ColumnDef<Jogador, any>[]>(() => [
    ch.accessor("jogador", { header: "Jogador", cell: (c) => <PlayerName p={c.row.original} /> }),
    ch.accessor("l10", { header: "L10", cell: (c) => num(c.getValue()) }),
    ch.accessor("proj", { header: "Proj", cell: (c) => num(c.getValue()) }),
    ...(["linha", "odd_over", "odd_under"] as (keyof Edit)[]).map((k) => ch.display({
      id: k, header: { linha: "Linha", odd_over: "Odd over", odd_under: "Odd under" }[k],
      cell: (c) => <input className={`cell ${edits[c.row.original.player_id] ? "dirty" : ""}`} type="number"
        step={k === "linha" ? 0.5 : 0.01} value={cur(c.row.original)[k]}
        placeholder={k === "linha" && c.row.original.linha_ref ? `${c.row.original.linha} ref` : ""}
        onChange={(e) => change(c.row.original, k, e.target.value)} />,
    })),
    ch.accessor((p) => p.chance ?? 0, { id: "chance", header: "Chance", cell: (c) => sideTxt(c.row.original) }),
  ], [edits, mercado]); // eslint-disable-line
  return (
    <>
      <div className="row" style={{ marginBottom: 8 }}>
        <button className="btn primary" disabled={!n || save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "Salvando…" : `Salvar ${n || ""} ${n === 1 ? "linha" : "linhas"}`}</button>
        {n > 0 && <button className="btn" onClick={() => setEdits({})}>Descartar</button>}
        <span className="muted small">Odds decimais. Linha vazia apaga e volta para a referência (L10). A chance e o valor esperado mudam em todas as abas.</span>
      </div>
      <DataTable data={players} columns={columns} maxHeight={900} />
    </>
  );
}

// ---------- Matchups ----------
function MatchupsTab({ players, mercado, jogos }: { players: Jogador[]; mercado: string; jogos: Jogo[] }) {
  const nav = useNavigate();
  const columns = useMemo<ColumnDef<Jogador, any>[]>(() => [
    ch.accessor("jogador", { header: "Jogador", cell: (c) => <PlayerName p={c.row.original} /> }),
    ch.accessor((p) => `${p.grupo ?? "?"} · ${p.posicao_est ?? "?"}`, { id: "pos", header: "Pos", meta: "Grupo do DvP · posição estimada" }),
    ch.accessor("min_l5", { header: "Min L5/L10", cell: (c) => `${Math.round(c.getValue() ?? 0)} / ${Math.round(c.row.original.min_l10 ?? 0)}` }),
    ch.accessor("usg_l5", { header: "Uso L5/L10", cell: (c) => `${num(c.getValue(), 0)} / ${num(c.row.original.usg_l10, 0)}`, meta: "Taxa de uso (%)" }),
    ch.accessor("temporada", { header: "Temp.", cell: (c) => num(c.getValue()) }),
    ch.accessor("l10", { header: "L10", cell: (c) => num(c.getValue()) }),
    ch.accessor("l5", { header: "L5", cell: (c) => num(c.getValue()) }),
    ch.accessor("proj", { header: "Proj", cell: (c) => num(c.getValue()) }),
    ch.accessor("proj_vs_l10", { header: "vs L10", cell: (c) => c.getValue() == null ? "—" : `${c.getValue() > 0 ? "+" : ""}${c.getValue().toFixed(1)}` }),
    ch.accessor("dvp_rank", { header: "DvP", cell: (c) => c.getValue() ? `${c.getValue()}º` : "—" }),
    ch.accessor("dvp_rec_rank", { header: "DvP 15d", cell: (c) => c.getValue() ? `${c.getValue()}º` : "—" }),
    ch.accessor("encaixe_zonas", { header: "Zonas", cell: (c) => c.getValue() == null ? "—" : `${c.getValue() > 0 ? "+" : ""}${c.getValue().toFixed(1)}`, meta: "Aproveitamento cedido acima da liga nas zonas dele (p.p.)" }),
    ch.accessor((p) => (p.com_sem ?? []).map((c) => `sem ${c.companheiro}: ${c.sem ?? "—"} (${c.jogos_sem} j)`).join("; "), { id: "comsem", header: "Com/sem desfalque", cell: (c) => <span className="small muted">{c.getValue()}</span> }),
    ...(players.some((p) => p.real != null) ? [ch.accessor("real", { header: "Real", cell: (c) => c.getValue() ?? "—" })] : []),
  ], [mercado, players]); // eslint-disable-line
  const cls = (p: Jogador, col: string) => {
    if (col === "proj_vs_l10" || col === "proj") return p.proj_vs_l10 == null ? undefined : { color: p.proj_vs_l10 > 0 ? "var(--over)" : "var(--under)", fontWeight: 700 };
    if (col === "dvp_rank" || col === "dvp_rec_rank") { const r = p[col]; return r == null ? undefined : { color: r >= 21 ? "var(--over)" : r <= 10 ? "var(--under)" : undefined }; }
    if (col === "encaixe_zonas") return p.encaixe_zonas == null ? undefined : { color: p.encaixe_zonas > 0 ? "var(--over)" : "var(--under)" };
    return undefined;
  };
  return (
    <>
      <div className="games" style={{ marginBottom: 12 }}>{jogos.map((g) => (
        <div className="game" key={g.id}>
          <div className="t">{g.fora} @ {g.casa}<small>{g.status}</small></div>
          <div className="row" style={{ gap: 6, marginTop: 6 }}>
            {g.margem_esperada != null && <span className="chip">{g.margem_esperada >= 0 ? g.casa : g.fora} por {Math.abs(g.margem_esperada).toFixed(1)}</span>}
            {g.risco_blowout != null && <span className={`chip ${g.risco_blowout >= .4 ? "bad" : ""}`}>blowout {Math.round(100 * g.risco_blowout)}%</span>}
            {g.ritmo?.casa && g.ritmo?.fora && <span className="chip">ritmo {g.ritmo.fora} / {g.ritmo.casa}</span>}
          </div>
          <div className="d">{g.fora}: {g.desfalques?.fora.join(", ") || "—"}<br />{g.casa}: {g.desfalques?.casa.join(", ") || "—"}</div>
        </div>))}
      </div>
      <DataTable data={players} columns={columns} onRow={(p) => nav(`/jogador/${p.player_id}?mercado=${mercado}`)} cellClass={cls}
        initialSort={[{ id: "proj_vs_l10", desc: true }]} maxHeight={900} />
      <p className="muted small">vs L10 = projeção acima/abaixo da média recente · DvP 30 = defesa que mais cede à posição · ⚠ = não jogou a última partida e não está no injury report.</p>
    </>
  );
}

// ---------- DvP ----------
function DvpTab({ mercado }: { mercado: string }) {
  const { data } = usePrefs();
  const [recente, setRecente] = useState(false);
  const [soHoje, setSoHoje] = useState(false);
  const q = useQuery({ queryKey: ["dvp", data, mercado, recente], queryFn: () => api.dvp(data, mercado, recente) });
  type R = NonNullable<typeof q.data>["linhas"][number];
  const c2 = createColumnHelper<R>();
  const columns = useMemo<ColumnDef<R, any>[]>(() => [
    c2.accessor("time", { header: "Defesa", cell: (c) => <b>{c.getValue()}{c.row.original.joga_hoje ? " ●" : ""}</b> }),
    ...(q.data?.grupos ?? []).flatMap((g) => [
      c2.accessor((r) => r[g] as number, { id: g, header: `${g} cede`, cell: (c) => num(c.getValue()) }),
      c2.accessor((r) => r[`${g}_rank`] as number, { id: `${g}_rank`, header: `${g} rank`, cell: (c) => `${c.getValue()}º` }),
    ]),
  ], [q.data]); // eslint-disable-line
  const cls = (r: R, col: string) => {
    if (!col.endsWith("_rank")) return undefined;
    const v = r[col] as number;
    return v >= 26 ? { background: "var(--h-good)", color: "var(--h-good-t)", fontWeight: 700 } : v <= 5 ? { background: "var(--h-bad)", color: "var(--h-bad-t)", fontWeight: 700 } : undefined;
  };
  const rows = (q.data?.linhas ?? []).filter((r) => !soHoje || r.joga_hoje);
  return (
    <>
      <div className="row" style={{ marginBottom: 8 }}>
        <div className="seg"><button className={!recente ? "on" : ""} onClick={() => setRecente(false)}>Temporada</button>
          <button className={recente ? "on" : ""} onClick={() => setRecente(true)}>Últimos {q.data?.dias_recente ?? 15} dias</button></div>
        <label className="toggle"><input type="checkbox" checked={soHoje} onChange={(e) => setSoHoje(e.target.checked)} />Só quem joga hoje ●</label>
        <span className="muted small">Média cedida por jogo a cada posição em {MARKETS[mercado]}. Rank 30 = cede mais (verde = alvo bom).</span>
      </div>
      {q.isLoading ? <Esqueleto /> :
        <DataTable data={rows} columns={columns} cellClass={cls} initialSort={[{ id: `${q.data?.grupos[0]}_rank`, desc: true }]} maxHeight={900} />}
    </>
  );
}

// ---------- Potenciais ----------
function PotenciaisTab({ busca, setBusca }: { busca: string; setBusca: (s: string) => void }) {
  const { data } = usePrefs();
  const nav = useNavigate();
  const fav = useFavs();
  const [soHoje, setSoHoje] = useState(false);
  const q = useQuery({ queryKey: ["potenciais", data], queryFn: () => api.potenciais(data) });
  const c3 = createColumnHelper<Potencial>();
  const pair = (k: string, label: string) => c3.accessor((r) => r[`${k}_n`] as number, {
    id: k, header: label, cell: (c) => <>{num(c.getValue())} <span className="muted small">/ {num(c.row.original[k] as number)}</span></>,
  });
  const columns = useMemo<ColumnDef<Potencial, any>[]>(() => [
    c3.accessor("jogador", { header: "Jogador", cell: (c) => (
      <div className="pname"><Star on={fav.has("jogador", c.row.original.player_id)} onClick={() => fav.toggle("jogador", c.row.original.player_id, c.row.original.jogador)} />
        <Photo id={c.row.original.player_id} /><span><b>{c.getValue()}</b> <span className="muted small">{c.row.original.time}{c.row.original.joga_hoje ? " · joga hoje" : ""}</span></span></div>) }),
    c3.accessor("nota", { header: "Nota", cell: (c) => <b>{c.getValue().toFixed(2)}</b> }),
    c3.accessor("anos_de_liga", { header: "Anos", cell: (c) => c.getValue() ?? "—" }),
    c3.accessor("jogos", { header: "Jogos" }),
    pair("minutes", "Min"), pair("pts", "PTS"), pair("reb", "REB"), pair("ast", "AST"), pair("fg3m", "3PM"),
  ], [fav.favs]); // eslint-disable-line
  const rows = (q.data?.jogadores ?? []).filter((r) => (!soHoje || r.joga_hoje) && (!busca || r.jogador.toLowerCase().includes(busca.toLowerCase())));
  return (
    <>
      <div className="row" style={{ margin: "10px 0" }}>
        <input className="input" placeholder="Buscar jogador" value={busca} onChange={(e) => setBusca(e.target.value)} style={{ width: 180 }} />
        <label className="toggle"><input type="checkbox" checked={soHoje} onChange={(e) => setSoHoje(e.target.checked)} />Só quem joga hoje</label>
        <span className="muted small">Últimos 10 jogos / temporada. Regras em <code>config/potencial.yaml</code>. Clique para abrir (se joga hoje).</span>
      </div>
      {q.isLoading ? <Esqueleto /> :
        <DataTable data={rows} columns={columns} initialSort={[{ id: "nota", desc: true }]} maxHeight={900}
          onRow={(r) => r.joga_hoje && nav(`/jogador/${r.player_id}?mercado=pra`)} />}
      <p className="muted small"><Link to="/">← Início</Link></p>
    </>
  );
}
