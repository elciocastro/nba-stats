// Ao Vivo: jogos em andamento e quem está a caminho de bater a linha (ou a média).
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { aoVivo, LiveGame, LivePlayer } from "../api";
import { Photo, Star, useFavs } from "../components";
import { Esqueleto } from "../App";

const MK: Record<string, string> = { pts: "Pontos", reb: "Rebotes", ast: "Assist.", fg3m: "3 pts", pra: "PRA" };
const ST: Record<string, { cls: string; txt: string }> = {
  bateu: { cls: "ok", txt: "bateu" }, "a caminho": { cls: "ok", txt: "a caminho" },
  "precisa acelerar": { cls: "hot", txt: "precisa acelerar" }, longe: { cls: "", txt: "longe" },
};

const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

export default function AoVivo() {
  const [mercado, setMercado] = useState("pts");
  const [alvo, setAlvo] = useState("linha");
  const [soFav, setSoFav] = useState(false);
  const fav = useFavs();
  const q = useQuery({ queryKey: ["aovivo", mercado, alvo], queryFn: () => aoVivo(mercado, alvo),
                       refetchInterval: 30_000, refetchIntervalInBackground: false });
  const live = q.data?.jogos.filter((g) => g.status === 2) ?? [];
  const keep = (p: LivePlayer) => !soFav || fav.has("jogador", p.player_id);

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1>Ao Vivo {live.length > 0 && <span className="pulse">●</span>}</h1>
        <span className="muted small">{q.isFetching ? "atualizando…" : q.data ? `atualiza a cada 30 s · dados de há ${q.data.atualizado_ha ?? 0} s` : ""}</span>
      </div>
      <div className="sticky-tools">
        <div className="row">
          <div className="tabs">{Object.entries(MK).map(([k, v]) => <button key={k} className={`tab ${k === mercado ? "on" : ""}`} onClick={() => setMercado(k)}>{v}</button>)}</div>
          <div className="seg"><button className={alvo === "linha" ? "on" : ""} onClick={() => setAlvo("linha")}>contra a linha</button>
            <button className={alvo === "media" ? "on" : ""} onClick={() => setAlvo("media")}>contra a média</button></div>
          <label className="toggle"><input type="checkbox" checked={soFav} onChange={(e) => setSoFav(e.target.checked)} />Só favoritos ★</label>
        </div>
      </div>
      {q.isLoading && <Esqueleto />}
      {q.error && <div className="err">{String((q.error as Error).message)}</div>}
      {q.data && !q.data.jogos.length && <div className="muted">Nenhum jogo hoje.</div>}

      {q.data && q.data.destaques.length > 0 && (
        <>
          <h2>A caminho de bater {alvo === "linha" ? "a linha" : "a média"}</h2>
          <p className="muted small" style={{ marginTop: 0 }}>Projeção do final = parcial + ritmo × minutos que ainda deve jogar (tempo restante × fatia de minutos dele; menos em blowout ou com 5 faltas).</p>
          <div className="games">{q.data.destaques.filter(keep).map((p) => <LiveCard key={`${p.player_id}`} p={p} />)}</div>
        </>
      )}

      {q.data && q.data.jogos.length > 0 && <h2>Jogos</h2>}
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {q.data?.jogos.map((g) => <GameBlock key={g.game_id} g={g} keep={keep} alvo={alvo} />)}
      </div>
    </>
  );
}

function Progress({ p }: { p: LivePlayer }) {
  const top = Math.max(p.alvo ?? 0, p.final, p.atual, 1) * 1.1;
  const pct = (x: number) => `${Math.min(100, (100 * x) / top)}%`;
  const done = p.alvo != null && p.atual > p.alvo;
  return (
    <div className="prog" title={`parcial ${p.atual} · projeção ${p.final}${p.alvo != null ? ` · alvo ${p.alvo}` : ""}`}>
      <div className="proj" style={{ width: pct(p.final) }} />
      <div className={`cur ${done ? "done" : ""}`} style={{ width: pct(p.atual) }} />
      {p.alvo != null && <div className="tgt" style={{ left: pct(p.alvo) }} />}
    </div>
  );
}

function LiveCard({ p }: { p: LivePlayer }) {
  const nav = useNavigate();
  const st = p.status ? ST[p.status] : null;
  return (
    <div className="game" style={{ cursor: "pointer" }} onClick={() => nav(`/jogador/${p.player_id}`)}>
      <div className="row" style={{ gap: 10, flexWrap: "nowrap" }}>
        <Photo id={p.player_id} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700 }}>{p.jogador} <span className="muted small">{p.time}{p.jogo ? ` · ${p.jogo}` : ""}</span></div>
          <div className="small">{p.atual} agora · alvo {p.alvo}{p.linha_ref ? " ref" : ""} · <b>final ~{p.final}</b></div>
        </div>
        {st && <span className={`chip ${st.cls}`}>{p.chance != null ? `${Math.round(100 * p.chance)}%` : st.txt}</span>}
      </div>
      <Progress p={p} />
      <div className="muted small">{p.minutos} min jogados · ~{p.restante} min restantes{p.em_quadra ? " · em quadra" : ""}
        {p.alertas.includes("faltas") && <span className="tag"> {p.faltas} faltas</span>}{p.alertas.includes("blowout") && <span className="tag"> blowout</span>}</div>
    </div>
  );
}

function GameBlock({ g, keep, alvo }: { g: LiveGame; keep: (p: LivePlayer) => boolean; alvo: string }) {
  const [open, setOpen] = useState(g.status === 2);
  const fav = useFavs();
  const nav = useNavigate();
  const players = g.jogadores.filter(keep);
  const live = g.status === 2;
  return (
    <div className="panel">
      <div className="row" style={{ justifyContent: "space-between", cursor: "pointer" }} onClick={() => setOpen(!open)}>
        <div className="row" style={{ gap: 14 }}>
          <span style={{ fontSize: "1.2rem", fontWeight: 800 }}>{g.fora} {g.placar_fora} <span className="muted">@</span> {g.casa} {g.placar_casa}</span>
          <span className={`chip ${live ? "hot" : ""}`}>{live ? `${g.periodo > 4 ? `OT${g.periodo - 4}` : `${g.periodo}º`} · ${clock(g.relogio_seg)}` : g.status_texto}</span>
          {live && Math.abs(g.placar_casa - g.placar_fora) >= 20 && <span className="chip bad">blowout</span>}
        </div>
        <span className="muted">{open ? "▾" : "▸"} {players.length} jogadores</span>
      </div>
      {open && g.status >= 2 && (
        <div style={{ overflowX: "auto", marginTop: 10 }}><table className="t live">
          <thead><tr><th>Jogador</th><th>Min</th><th>Agora</th><th>{alvo === "linha" ? "Linha" : "Média"}</th><th>Final ~</th><th className="pc" style={{ width: "28%" }}></th><th>Chance</th></tr></thead>
          <tbody>{players.map((p) => {
            const st = p.status ? ST[p.status] : null;
            return (
              <tr key={p.player_id} onClick={() => nav(`/jogador/${p.player_id}`)} style={{ cursor: "pointer" }}>
                <td><div className="pname"><Star on={fav.has("jogador", p.player_id)} onClick={() => fav.toggle("jogador", p.player_id, p.jogador)} />
                  <span><b>{p.jogador}</b> <span className="muted small">{p.time}{p.em_quadra && live ? " ●" : ""}</span>
                  {p.faltas >= 5 && <span className="tag"> {p.faltas}F</span>}</span></div></td>
                <td>{p.minutos}</td><td><b>{p.atual}</b></td><td>{p.alvo ?? "—"}{p.linha_ref && alvo === "linha" ? " ref" : ""}</td>
                <td>{p.final}</td><td className="pc"><Progress p={p} /></td>
                <td>{st ? <span className={`chip ${st.cls}`}>{p.status === "bateu" ? "✓ bateu" : `${Math.round(100 * (p.chance ?? 0))}%`}</span> : "—"}</td>
              </tr>);
          })}</tbody>
        </table></div>
      )}
      {open && g.status === 1 && <div className="muted small" style={{ marginTop: 8 }}>{g.status_texto} — começa mais tarde.</div>}
    </div>
  );
}
