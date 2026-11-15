// Notícias de lesão: mudanças entre os dois últimos injury reports e quem pode voltar.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api2 } from "../api";
import { usePrefs } from "../App";
import { Photo } from "../components";

const ICON: Record<string, string> = { entrou: "🆕", saiu: "✅", melhorou: "⬆️", piorou: "⬇️", lista: "•" };
// "Injury/Illness-RightKneeInjuryManagement" -> "Right Knee Injury Management"
const motivo = (m: string | null) => (m ?? "").replace(/^Injury\/Illness-/, "").replace(/([a-z])([A-Z])/g, "$1 $2").replace(/;/g, "; ").replace(/-/g, " · ");
const ST: Record<string, string> = { Out: "bad", Doubtful: "bad", Questionable: "hot", Probable: "ok", Available: "ok" };

export default function Noticias() {
  const { data } = usePrefs();
  const nav = useNavigate();
  const [mins, setMins] = useState(28);
  const q = useQuery({ queryKey: ["noticias", data], queryFn: () => api2.noticias(data), refetchInterval: 5 * 60_000 });
  if (q.isLoading) return <div className="loading">Carregando…</div>;
  if (q.error) return <div className="err">{String((q.error as Error).message)}</div>;
  const n = q.data!;
  return (
    <>
      <h1>Notícias de lesão</h1>
      {!n.atual ? <p className="muted">Nenhum injury report guardado para esta data. Use “Atualizar dados”.</p> : (
        <>
          <p className="muted small">Último relatório: {n.atual.slice(11)} ET{n.anterior ? ` · comparado com ${n.anterior.slice(11)} ET` : " (primeiro do dia)"} · {n.relatorios.length} relatórios na data</p>
          <h2>O que mudou</h2>
          {!n.mudancas.length ? <p className="muted">Nada mudou entre os dois últimos relatórios.</p> : (
            <div className="tw"><table className="t">
              <thead><tr><th>Jogador</th><th>Agora</th><th>Antes</th><th>Time</th><th>Motivo</th></tr></thead>
              <tbody>{n.mudancas.map((c, i) => (
                <tr key={i} style={c.player_id ? { cursor: "pointer" } : undefined} onClick={() => c.player_id && nav(`/jogador/${c.player_id}`)}>
                  <td>{ICON[c.tipo]} <b>{c.jogador}</b></td>
                  <td><span className={`chip ${ST[c.agora ?? ""] ?? ""}`}>{c.agora ?? "fora da lista"}</span></td>
                  <td>{c.antes ?? "—"}</td><td>{c.time}</td>
                  <td className="muted small" style={{ whiteSpace: "normal" }}>{motivo(c.motivo)}</td></tr>))}
              </tbody></table></div>)}
        </>
      )}
      <h2>Podem voltar hoje</h2>
      <p className="muted small" style={{ marginTop: 0 }}>Ficaram fora do último jogo do time e não estão Out/Doubtful no último relatório. Médias dos últimos 5 jogos que disputaram. Na volta, o técnico costuma limitar os minutos.</p>
      {!n.retornos.length ? <p className="muted">Ninguém relevante.</p> : (
        <>
          <div className="panel" style={{ maxWidth: 480, marginBottom: 10 }}>
            <div className="row" style={{ justifyContent: "space-between" }}><b>Com {mins} minutos</b><span className="muted small">PRA por minuto × minutos</span></div>
            <input type="range" min={10} max={40} value={mins} onChange={(e) => setMins(Number(e.target.value))} />
          </div>
          <div className="games">{n.retornos.map((r) => (
            <div className="game" key={r.player_id} style={{ cursor: "pointer" }} onClick={() => nav(`/jogador/${r.player_id}?mercado=pra`)}>
              <div className="row" style={{ flexWrap: "nowrap" }}><Photo id={r.player_id} />
                <div style={{ flex: 1 }}><b>{r.jogador}</b> <span className="muted small">{r.time}</span><br />
                  <span className={`chip ${ST[r.status] ?? ""}`}>{r.status}</span> <span className="muted small">{r.jogos_fora ?? "?"} jogo(s) fora</span></div>
                <div style={{ textAlign: "right" }}><div className="muted small">PRA com {mins} min</div><div style={{ fontSize: "1.3rem", fontWeight: 800 }}>{(r.pra_por_min * mins).toFixed(1)}</div></div>
              </div>
              <div className="d">Antes: {r.minutos_antes} min · {r.pts} pts · {r.reb} reb · {r.ast} ast · PRA {r.pra}</div>
            </div>))}
          </div>
        </>
      )}
    </>
  );
}
