import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { NavLink, useNavigate } from "react-router-dom";
import { api, api2, Atuacao, Classif, Liga, Manchete, Oportunidade, Resultado, teamLogo } from "../api";
import { usePrefs } from "../App";
import { Bars, num, Photo, SealBadge, useFavs } from "../components";
import { BolaQuicando } from "../marca";

const MK: Record<string, string> = { pts: "Pontos", reb: "Rebotes", ast: "Assist.", pra: "PRA", fg3m: "3FM" };

export default function Inicio() {
  const { data } = usePrefs();
  const liga = useQuery({ queryKey: ["liga", data], queryFn: () => api2.liga(data), refetchInterval: 10 * 60_000 });
  const L = liga.data;
  return (
    <>
      <div className="secao"><h1>Início</h1><span className="muted small">{dataLonga(data)}</span></div>
      {liga.error && <div className="err" style={{ marginTop: 10 }}>{String((liga.error as Error).message)}</div>}
      {L && L.resultados.length > 0 && <Rodada l={L} />}
      <div className="home">
        <div>
          <Hoje />
          {L && L.destaques.length > 0 && <Destaques d={L.destaques} rodada={L.rodada!} />}
        </div>
        <aside className="side">
          {liga.isLoading && <Carregando texto="Buscando a liga…" />}
          {L && <Noticias n={L.noticias} />}
          {L && <Classificacao c={L.classificacao} />}
          {L && <Lideres l={L.lideres} />}
          {L && <Transacoes t={L.transacoes} />}
        </aside>
      </div>
    </>
  );
}

function Carregando({ texto }: { texto: string }) {
  return <div className="carregando"><BolaQuicando size={30} />{texto}</div>;
}

const DIAS = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
const dataCurta = (d: string) => `${DIAS[new Date(`${d}T12:00`).getDay()]} ${d.slice(8, 10)}/${d.slice(5, 7)}`;
const dataLonga = (d: string) => new Date(`${d}T12:00`).toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
function haQuanto(iso: string | null) {
  if (!iso) return "";
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 60_000);
  if (min < 60) return `há ${Math.max(min, 1)} min`;
  if (min < 48 * 60) return `há ${Math.round(min / 60)} h`;
  return `há ${Math.round(min / 1440)} dias`;
}

function TeamLogo({ id }: { id: number }) {
  const [ok, setOk] = useState(true);
  return ok ? <img className="tl" src={teamLogo(id)} alt="" loading="lazy" onError={() => setOk(false)} /> : <span className="tl" />;
}

function Rodada({ l }: { l: Liga }) {
  const nav = useNavigate();
  const lado = (r: Resultado, casa: boolean) => {
    const sigla = casa ? r.casa : r.fora, pl = casa ? r.placar_casa : r.placar_fora;
    return <div className={`ln ${r.vencedor === sigla ? "w" : ""}`}><TeamLogo id={casa ? r.casa_id : r.fora_id} />{sigla}<span className="pl">{pl}</span></div>;
  };
  const top = (c: Resultado["cestinha_casa"]) => c ? `${c.jogador.split(" ").slice(-1)[0]} ${c.pts}p ${c.reb}r ${c.ast}a` : "—";
  return (
    <>
      <div className="secao"><h2>Última rodada · {dataCurta(l.rodada!)}</h2><NavLink to="/jogos">box scores ›</NavLink></div>
      <div className="rodada">{l.resultados.map((r) => (
        <div key={r.game_id} className="res" onClick={() => nav(`/jogos/${r.game_id}`)} title="Abrir o box score">
          {lado(r, false)}{lado(r, true)}
          <span className="top">{top(r.cestinha_fora)} · {top(r.cestinha_casa)}</span>
        </div>))}
      </div>
    </>
  );
}

function Destaques({ d, rodada }: { d: Atuacao[]; rodada: string }) {
  const nav = useNavigate();
  return (
    <>
      <h2>Destaques da rodada · {dataCurta(rodada)}</h2>
      <div className="atu">{d.map((a) => (
        <div key={a.player_id} className="card" onClick={() => nav(`/jogador/${a.player_id}`)}>
          <Photo id={a.player_id} />
          <div style={{ minWidth: 0 }}>
            <div className="nm" style={{ fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{a.jogador}</div>
            <div className="muted small">{a.time} {a.venceu ? "venceu" : "perdeu"} x {a.adversario} · {a.min} min</div>
            <div className="nums"><b>{a.pts}</b> pts · <b>{a.reb}</b> reb · <b>{a.ast}</b> ast{a.fg3m ? ` · ${a.fg3m} bola${a.fg3m > 1 ? "s" : ""} de 3` : ""}</div>
            {a.marcas.length > 0 && <div className="row" style={{ gap: 4, marginTop: 4 }}>{a.marcas.map((m) =>
              <span key={m} className={`chip ${m === "triplo-duplo" || m.startsWith("recorde") ? "hot" : "ok"}`}>{m}</span>)}</div>}
          </div>
          <div className="gs" title="Game Score (Hollinger): ~10 é uma atuação média; 30+ é excepcional"><div className="v">{a.game_score}</div><div className="l">GMSC</div></div>
        </div>))}
      </div>
    </>
  );
}

function Noticias({ n }: { n: Manchete[] }) {
  if (!n.length) return <><h2>Notícias</h2><p className="muted small">Sem manchetes ainda. Use “Atualizar dados”.</p></>;
  const [primeira, ...resto] = n;
  const item = (x: Manchete, destaque = false) => (
    <a key={x.id} className={`nw ${destaque ? "destaque" : ""}`} href={x.url} target="_blank" rel="noopener noreferrer">
      {x.imagem ? <img src={x.imagem} alt="" loading="lazy" /> : <span className="ni" />}
      <div className="tx"><div className="tt">{x.titulo}</div>
        {destaque && x.resumo && <div className="rs">{x.resumo}</div>}
        <div className="mt">{x.tipo} · {haQuanto(x.publicado)}</div></div>
    </a>);
  return (
    <>
      <div className="secao"><h2>Notícias</h2><span className="muted small">ESPN, em inglês</span></div>
      <div className="news">{item(primeira, true)}{resto.slice(0, 7).map((x) => item(x))}</div>
    </>
  );
}

function Classificacao({ c }: { c: Liga["classificacao"] }) {
  const [conf, setConf] = useState<"East" | "West">("East");
  const rows: Classif[] = c[conf];
  return (
    <>
      <div className="secao"><h2>Classificação</h2>
        <div className="seg">{(["East", "West"] as const).map((k) =>
          <button key={k} className={k === conf ? "on" : ""} onClick={() => setConf(k)}>{k === "East" ? "Leste" : "Oeste"}</button>)}</div></div>
      <div className="tw" style={{ maxHeight: "none" }}><table className="t cls">
        <thead><tr><th>Time</th><th>V</th><th>D</th><th>%</th><th>Atrás</th><th>Últ. 10</th><th>Seq.</th></tr></thead>
        <tbody>{rows.map((r) => (
          <tr key={r.team_id} className={r.pos === 6 || r.pos === 10 ? "corte" : ""}>
            <td className={r.zona ? `zona-${r.zona}` : ""}><span className="row" style={{ gap: 6, flexWrap: "nowrap" }}>
              <span className="pos">{r.pos}</span><TeamLogo id={r.team_id} /><b>{r.time}</b></span></td>
            <td>{r.v}</td><td>{r.d}</td><td>{r.pct == null ? "—" : r.pct.toFixed(3).replace(/^0/, "")}</td>
            <td>{r.atras}</td><td>{r.ult10}</td>
            <td className={r.sequencia.startsWith("V") ? "over" : r.sequencia.startsWith("D") ? "under" : ""}>{r.sequencia}</td>
          </tr>))}</tbody></table></div>
      <p className="muted small" style={{ margin: "4px 0 0" }}>Verde: playoff direto (1–6) · âmbar: play-in (7–10)</p>
    </>
  );
}

function Lideres({ l }: { l: Liga["lideres"] }) {
  const nav = useNavigate();
  const keys = Object.keys(l.categorias);
  const [k, setK] = useState(keys[0] ?? "pts");
  const cat = l.categorias[k];
  if (!cat) return null;
  return (
    <>
      <div className="secao"><h2>Líderes da temporada</h2><NavLink to="/ranking">ranking ›</NavLink></div>
      <div className="tabs" style={{ marginBottom: 4 }}>{keys.map((x) =>
        <button key={x} className={`tab ${x === k ? "on" : ""}`} onClick={() => setK(x)}>{l.categorias[x].nome}</button>)}</div>
      <div className="lid">{cat.jogadores.map((p, i) => (
        <div key={p.player_id} className="r" onClick={() => nav(`/jogador/${p.player_id}`)}>
          <span className="muted small" style={{ width: 14 }}>{i + 1}</span><Photo id={p.player_id} />
          <div><b>{p.jogador}</b> <span className="muted small">{p.time}</span></div>
          <span className="v">{p.media.toFixed(1)}</span>
        </div>))}
      </div>
      <p className="muted small" style={{ margin: "4px 0 0" }}>Média por jogo; mínimo de {l.min_jogos} jogos (70% dos jogos do time).</p>
    </>
  );
}

function Transacoes({ t }: { t: Liga["transacoes"] }) {
  const nav = useNavigate();
  const [todas, setTodas] = useState(false);
  if (!t.length) return null;
  const COR: Record<string, string> = { Troca: "hot", Contratação: "ok", Dispensa: "bad" };
  return (
    <>
      <h2>Transações</h2>
      <div>{t.slice(0, todas ? t.length : 6).map((x) => (
        <div key={x.id} className="tx-item">
          <div className="mt"><span className={`chip ${COR[x.tipo] ?? ""}`}>{x.tipo}</span>{dataCurta(x.data)}</div>
          {x.linhas.map((l, i) => {
            const p = x.jogadores.find((j) => l.includes(j.jogador));
            return <div key={i} style={p ? { cursor: "pointer" } : undefined} onClick={() => p && nav(`/jogador/${p.player_id}`)}>{l}</div>;
          })}
        </div>))}
      </div>
      {t.length > 6 && <button className="btn" style={{ marginTop: 6 }} onClick={() => setTodas(!todas)}>{todas ? "Menos" : `Ver todas (${t.length})`}</button>}
    </>
  );
}

/** O dia dos props: pesado (projeções), carrega à parte sem travar a página. */
function Hoje() {
  const { data, betaniag } = usePrefs();
  const nav = useNavigate();
  const q = useQuery({ queryKey: ["inicio", data, betaniag], queryFn: () => api.inicio(data, betaniag) });
  const open = (id: number, mercado: string) => nav(`/jogador/${id}?mercado=${mercado}`);
  const fav = useFavs();
  const pra = useQuery({ queryKey: ["props", data, "pra", betaniag], queryFn: () => api.props(data, "pra", betaniag) });
  const favPlayers = (pra.data?.jogadores ?? []).filter((p) => fav.playerFav(p));

  if (q.isLoading) return <><h2>Hoje</h2><Carregando texto="Montando as projeções do dia… (a primeira conta leva alguns segundos)" /></>;
  if (q.error) return <div className="err">{String(q.error)}</div>;
  const d = q.data!;
  if (!d.jogos.length) return <><h2>Hoje</h2><p className="muted">Nenhum jogo nesta data.</p></>;

  const opps = [...d.oportunidades.com_odd, ...d.oportunidades.sem_odd];
  return (
    <>
      <h2>Hoje · {d.jogos.length} jogos</h2>
      <div className="kpis">
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
