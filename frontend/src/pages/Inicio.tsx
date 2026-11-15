import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api, Oportunidade } from "../api";
import { usePrefs } from "../App";
import { Bars, num, Photo, SealBadge, useFavs } from "../components";

const MK: Record<string, string> = { pts: "Pontos", reb: "Rebotes", ast: "Assist.", pra: "PRA", fg3m: "3FM" };

export default function Inicio() {
  const { data, betaniag } = usePrefs();
  const nav = useNavigate();
  const q = useQuery({ queryKey: ["inicio", data, betaniag], queryFn: () => api.inicio(data, betaniag) });
  const open = (id: number, mercado: string) => nav(`/jogador/${id}?mercado=${mercado}`);
  const fav = useFavs();
  const pra = useQuery({ queryKey: ["props", data, "pra", betaniag], queryFn: () => api.props(data, "pra", betaniag) });
  const favPlayers = (pra.data?.jogadores ?? []).filter((p) => fav.playerFav(p));

  if (q.isLoading) return <div className="loading">Montando os destaques… (a primeira conta do dia leva alguns segundos)</div>;
  if (q.error) return <div className="err">{String(q.error)}</div>;
  const d = q.data!;
  if (!d.jogos.length) return <div className="muted">Nenhum jogo nesta data.</div>;

  const opps = [...d.oportunidades.com_odd, ...d.oportunidades.sem_odd];
  return (
    <>
      <h1>Destaques do dia</h1>
      <div className="kpis" style={{ marginTop: 12 }}>
        <div className="kpi"><div className="l">Jogos</div><div className="v">{d.jogos.length}</div></div>
        <div className="kpi"><div className="l">Props boas</div><div className="v">{betaniag ? d.jogos.reduce((a, j) => a + j.props_boas, 0) : "—"}</div>
          <div className="s">{betaniag ? "selo Forte/Boa" : "ligue o BetânIAG"}</div></div>
        <div className="kpi"><div className="l">Com odd da casa</div><div className="v">{d.oportunidades.com_odd.length}</div></div>
        <div className="kpi"><div className="l">Em alta</div><div className="v">{d.em_alta.length}</div></div>
      </div>

      {favPlayers.length > 0 && (
        <>
          <h2>★ Favoritos que jogam hoje (PRA)</h2>
          <div className="games">{favPlayers.map((p) => (
            <div className="prow" key={p.player_id} onClick={() => open(p.player_id, "pra")} style={{ border: "1px solid var(--line)" }}>
              <Photo id={p.player_id} />
              <div className="who"><div className="nm">{p.jogador}<small>{p.time} x {p.adversario}</small></div>
                <div className="ln">linha {p.linha}{p.linha_ref ? " ref" : ""} · L10 {num(p.l10)}</div></div>
              <div className="ed"><div className="l">PROJ</div><div className={`v ${(p.diff ?? 0) > 0 ? "over" : "under"}`}>{num(p.proj)}</div>
                <div className="small"><SealBadge s={p.selo}>{p.lado === "over" ? "▲" : "▼"} {Math.round(100 * (p.chance ?? 0))}%</SealBadge></div></div>
            </div>))}
          </div>
        </>
      )}

      <h2>Jogos do dia</h2>
      <div className="games">
        {d.jogos.map((g) => (
          <div className="game" key={g.game_id}>
            <div className="t">{g.fora} @ {g.casa}<small>{g.placar ?? g.status}</small></div>
            <div className="row" style={{ gap: 6, marginTop: 8 }}>
              {g.favorito && <span className="chip">{g.favorito} por {num(g.margem)}</span>}
              {g.blowout != null && <span className={`chip ${g.blowout >= 0.4 ? "bad" : ""}`}>blowout {Math.round(100 * g.blowout)}%</span>}
              {g.ritmo_vs_liga != null && <span className={`chip ${g.ritmo_vs_liga >= 1.5 ? "hot" : ""}`}>ritmo {g.ritmo_vs_liga > 0 ? "+" : ""}{g.ritmo_vs_liga}</span>}
              {g.props_boas > 0 && <span className="chip ok">{g.props_boas} props boas</span>}
              {g.validacao?.status === "validada" && <span className="chip ok">validada</span>}
            </div>
            <div className="d">{g.fora}: {g.desfalques.fora.join(", ") || "—"}<br />{g.casa}: {g.desfalques.casa.join(", ") || "—"}</div>
            {g.melhor && (
              <div className="b" onClick={() => open(g.melhor!.player_id, g.melhor!.mercado)}>
                Maior chance: <b>{g.melhor.jogador}</b> {g.melhor.lado} {g.melhor.linha} {MK[g.melhor.mercado]} · {Math.round(100 * g.melhor.chance)}%
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="grid2">
        <section>
          <h2>Melhores oportunidades</h2>
          <p className="muted small">Com odd da casa, pelo valor esperado; sem odd, pela chance do modelo (linha "ref" = L10, favorece o under).</p>
          <div className="plist">{opps.map((o) => <OppRow key={`${o.player_id}${o.mercado}`} o={o} onClick={() => open(o.player_id, o.mercado)} />)}</div>
        </section>
        <section>
          <h2>Em alta: vale acompanhar</h2>
          <p className="muted small">Jogam hoje e vêm acima da temporada no PRA dos últimos 5 jogos (barras: últimos 10 contra a média).</p>
          <div className="plist">
            {d.em_alta.map((r) => (
              <div className="prow" key={r.player_id} onClick={() => open(r.player_id, "pra")}>
                <Photo id={r.player_id} />
                <div className="who">
                  <div className="nm">{r.jogador}<small>{r.time} x {r.adversario}</small> {r.lesao && <span className="tag">{r.lesao}</span>}</div>
                  <div className="ln">PRA L5 {r.l5} · temp. {r.temporada} · min {Math.round(r.min_l5)} (L10 {Math.round(r.min_l10)})</div>
                </div>
                <div className="ed"><div className="l">ALTA</div><div className="v over">+{r.alta_pct}%</div><div className="small muted">proj {num(r.proj)}</div></div>
                <Bars values={r.valores} line={r.temporada} />
              </div>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}

function OppRow({ o, onClick }: { o: Oportunidade; onClick: () => void }) {
  const cls = o.lado === "over" ? "over" : "under";
  return (
    <div className="prow" onClick={onClick}>
      <Photo id={o.player_id} />
      <div className="who">
        <div className="nm">{o.jogador}<small>{o.time} x {o.adversario}</small> {o.lesao && <span className="tag">{o.lesao}</span>}</div>
        <div className="ln">{o.lado === "over" ? "Over" : "Under"} {o.linha}{o.linha_ref ? " ref" : ""} {MK[o.mercado]}
          {o.odd ? ` @ ${o.odd.toFixed(2)}` : ""}{o.ev != null ? ` · EV ${o.ev > 0 ? "+" : ""}${Math.round(100 * o.ev)}%` : ""}</div>
      </div>
      <div className="ed"><div className="l">PROJ</div><div className={`v ${cls}`}>{num(o.proj)}</div>
        <div className="small"><SealBadge s={o.selo}>{o.lado === "over" ? "▲" : "▼"} {Math.round(100 * o.chance)}%</SealBadge></div></div>
      <Bars values={o.valores} line={o.linha} />
    </div>
  );
}
