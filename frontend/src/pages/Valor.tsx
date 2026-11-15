// Valor (edge): props em que a nossa chance passa da chance que a odd paga.
// A conta fica em metrics/valor.py; aqui só a tela.
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api3, ValorComOdd, ValorSemOdd } from "../api";
import { usePrefs, Esqueleto } from "../App";
import { num, pct, Recolhe, useCelular } from "../components";

const MK: Record<string, string> = { pts: "Pontos", reb: "Rebotes", ast: "Assist.", pra: "PRA", fg3m: "3FM" };
const pp = (x: number) => `${x >= 0 ? "+" : ""}${(100 * x).toFixed(1)} p.p.`;
const sinal = (x: number) => `${x >= 0 ? "+" : ""}${Math.round(100 * x)}%`;
const prop = (r: { lado: string; linha: number | null; mercado: string }) =>
  `${r.lado === "over" ? "Over" : "Under"} ${num(r.linha)} ${MK[r.mercado] ?? r.mercado}`;

export default function Valor() {
  const { data } = usePrefs();
  const nav = useNavigate();
  const q = useQuery({ queryKey: ["valor", data], queryFn: () => api3.valor(data) });
  const abrir = (id: number, mercado: string) => nav(`/jogador/${id}?mercado=${mercado}`);
  if (q.isLoading) return <Esqueleto />;
  if (q.error) return <div className="err">{String((q.error as Error).message)}</div>;
  const v = q.data!;
  const min = Math.round(100 * v.edge_minimo);
  return (
    <>
      <h1>Valor</h1>
      <p className="muted small" style={{ marginTop: 4 }}>
        Props em que a nossa chance passa da chance que a odd paga. <b>Valor não quer dizer que vai bater</b>: uma prop
        de 60% perde 4 em cada 10. Quer dizer que o preço está bom para a chance, e só compensa repetida muitas vezes.
      </p>

      <Recolhe titulo="Como funciona o edge">
        <ul className="small" style={{ margin: "4px 0", paddingLeft: 18, lineHeight: 1.6 }}>
          <li><b>Chance implícita</b> da odd = 1 ÷ odd. Odd 2,00 → 50%; odd 1,80 → 55,6%.</li>
          <li><b>Edge</b> = nossa chance − chance implícita. Nós 60% numa odd 2,00 → <b>+10 p.p.</b></li>
          <li><b>Valor esperado (EV)</b> = chance × odd − 1: o que a aposta tende a devolver por unidade. 60% × 2,00 − 1 = +20%.</li>
          <li><b>Odd justa</b> = 1 ÷ nossa chance: o empate. Acima dela há valor; abaixo, a casa leva.</li>
          <li><b>Mercado sem margem</b>: com as odds de over e under, a chance que a casa precifica tirando a margem dela.</li>
          <li>Entra quem tem edge de pelo menos {min} p.p. (Administração → Apostas). Confira na página Conferência se as nossas chances acertam.</li>
        </ul>
      </Recolhe>

      <h2>Com odd da casa</h2>
      {!v.com_odd.length ? (
        <p className="muted">
          {v.avaliadas ? `Nenhuma das ${v.avaliadas} odds digitadas tem edge de ${min} p.p. ou mais.`
            : "Nenhuma odd digitada para esta data."} As odds entram pela página do jogador (linha da casa) ou por
          <code> nbastats linha</code>; ainda não há busca automática nas casas.
        </p>
      ) : <TabelaComOdd linhas={v.com_odd} abrir={abrir} />}

      <h2>Sem odd: quanto a casa precisa pagar</h2>
      <p className="muted small" style={{ marginTop: 0 }}>
        As maiores chances do dia (uma por jogador). Se a casa pagar a <b>odd mínima</b> ou mais, a prop tem pelo menos {min} p.p.
        de edge. Linhas da casa primeiro; “ref.” = linha de referência (L10 arredondado), que só vale se a casa
        oferecer a mesma linha.
      </p>
      {!v.sem_odd.length ? <p className="muted">Sem jogos ou projeções para esta data.</p>
        : <TabelaSemOdd linhas={v.sem_odd} abrir={abrir} />}
    </>
  );
}

function Cartao({ r, abrir, children }: { r: ValorComOdd | ValorSemOdd; abrir: (id: number, m: string) => void;
  children: React.ReactNode }) {
  return (
    <button className="valor-card" onClick={() => abrir(r.player_id, r.mercado)}>
      <div><b>{r.jogador}</b> <span className="muted small">{r.time} × {r.adversario}</span>
        {r.lesao && <span className="chip hot" style={{ marginLeft: 6 }}>{r.lesao}</span>}</div>
      <div>{prop(r)}{r.linha_ref && <span className="muted small"> ref.</span>}</div>
      <div className="valor-nums">{children}</div>
    </button>
  );
}

function TabelaComOdd({ linhas, abrir }: { linhas: ValorComOdd[]; abrir: (id: number, m: string) => void }) {
  const cel = useCelular();
  if (cel) return <div className="valor-lista">{linhas.map((r) => (
    <Cartao key={`${r.player_id}-${r.mercado}-${r.lado}`} r={r} abrir={abrir}>
      <span>odd <b>{num(r.odd, 2)}</b> ({pct(r.implicita)})</span><span>nossa <b>{pct(r.chance)}</b></span>
      <span className="over">edge <b>{pp(r.edge)}</b></span><span className="over">EV {sinal(r.ev)}</span>
    </Cartao>))}</div>;
  return (
    <div className="tw"><table className="t">
      <thead><tr><th>Jogador</th><th>Prop</th><th>Odd</th><th>Implícita</th><th>Nossa</th><th>Edge</th><th>EV</th>
        <th>Odd justa</th><th>Mercado s/ margem</th></tr></thead>
      <tbody>{linhas.map((r) => (
        <tr key={`${r.player_id}-${r.mercado}-${r.lado}`} style={{ cursor: "pointer" }} onClick={() => abrir(r.player_id, r.mercado)}>
          <td style={{ textAlign: "left" }}><b>{r.jogador}</b> <span className="muted small">{r.time} × {r.adversario}</span>
            {r.lesao && <span className="chip hot" style={{ marginLeft: 6 }}>{r.lesao}</span>}</td>
          <td style={{ textAlign: "left" }}>{prop(r)}</td>
          <td>{num(r.odd, 2)}</td><td>{pct(r.implicita)}</td><td><b>{pct(r.chance)}</b></td>
          <td className="over"><b>{pp(r.edge)}</b></td><td className="over">{sinal(r.ev)}</td>
          <td>{num(r.odd_justa, 2)}</td><td>{pct(r.chance_mercado)}</td>
        </tr>))}</tbody>
    </table></div>
  );
}

function TabelaSemOdd({ linhas, abrir }: { linhas: ValorSemOdd[]; abrir: (id: number, m: string) => void }) {
  const cel = useCelular();
  if (cel) return <div className="valor-lista">{linhas.map((r) => (
    <Cartao key={`${r.player_id}-${r.mercado}`} r={r} abrir={abrir}>
      <span>proj. {num(r.proj)}</span><span>nossa <b>{pct(r.chance)}</b></span>
      <span>justa {num(r.odd_justa, 2)}</span><span className="over">mínima <b>{num(r.odd_minima, 2)}</b></span>
    </Cartao>))}</div>;
  return (
    <div className="tw" style={{ maxHeight: 560 }}><table className="t">
      <thead><tr><th>Jogador</th><th>Prop</th><th>Proj.</th><th>Nossa</th><th>Odd justa</th><th>Odd mínima</th></tr></thead>
      <tbody>{linhas.map((r) => (
        <tr key={`${r.player_id}-${r.mercado}`} style={{ cursor: "pointer" }} onClick={() => abrir(r.player_id, r.mercado)}>
          <td style={{ textAlign: "left" }}><b>{r.jogador}</b> <span className="muted small">{r.time} × {r.adversario}</span>
            {r.lesao && <span className="chip hot" style={{ marginLeft: 6 }}>{r.lesao}</span>}</td>
          <td style={{ textAlign: "left" }}>{prop(r)}{r.linha_ref && <span className="muted small"> ref.</span>}</td>
          <td>{num(r.proj)}</td><td><b>{pct(r.chance)}</b></td><td>{num(r.odd_justa, 2)}</td>
          <td className="over"><b>{num(r.odd_minima, 2)}</b></td>
        </tr>))}</tbody>
    </table></div>
  );
}
