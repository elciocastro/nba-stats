import { createContext, useContext, useState } from "react";
import { QueryClient, QueryClientProvider, useMutation, useQuery } from "@tanstack/react-query";
import { BrowserRouter, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { api, api2, SenhaError } from "./api";
import Inicio from "./pages/Inicio";
import JogadorPage from "./pages/Jogador";
import Props from "./pages/Props";
import AoVivo from "./pages/AoVivo";
import Apostas from "./pages/Apostas";
import Comparar from "./pages/Comparar";
import Noticias from "./pages/Noticias";

type Prefs = { data: string; setData: (d: string) => void; betaniag: boolean; setBetaniag: (b: boolean) => void };
const Ctx = createContext<Prefs>(null!);
export const usePrefs = () => useContext(Ctx);

const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const qc = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000, retry: (n, e) => !(e instanceof SenhaError) && n < 1 } },
});

function Login({ onOk }: { onOk: () => void }) {
  const [s, setS] = useState("");
  const [err, setErr] = useState("");
  return (
    <form className="login" onSubmit={async (e) => {
      e.preventDefault();
      try { await api.login(s); onOk(); } catch { setErr("Senha incorreta"); }
    }}>
      <h1>🏀 NBA Stats</h1>
      <input className="input" type="password" placeholder="Senha" value={s} autoFocus onChange={(e) => setS(e.target.value)} />
      <button className="btn primary">Entrar</button>
      {err && <div className="err">{err}</div>}
    </form>
  );
}

function Shell() {
  const [data, setData] = useState(today());
  const [betaniag, setB] = useState(localStorage.getItem("betaniag") === "1");
  const setBetaniag = (b: boolean) => { localStorage.setItem("betaniag", b ? "1" : "0"); setB(b); };
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta });
  const [, force] = useState(0);
  if (meta.error instanceof SenhaError) return <Login onOk={() => { qc.clear(); force((x) => x + 1); }} />;

  return (
    <Ctx.Provider value={{ data, setData, betaniag, setBetaniag }}>
      <header className="top">
        <span className="brand">🏀 <span className="lbl">NBA Stats</span></span>
        <nav className="nav">
          <NavLink to="/" end>Início</NavLink>
          <NavLink to="/props">Props</NavLink>
          <NavLink to="/aovivo">Ao Vivo</NavLink>
          <NavLink to="/apostas">Apostas</NavLink>
          <NavLink to="/comparar">Comparar</NavLink>
          <NavLink to="/noticias">Notícias</NavLink>
        </nav>
        <span className="sp" />
        <Atualizar />
        <label className="toggle"><input type="checkbox" checked={betaniag} onChange={(e) => setBetaniag(e.target.checked)} />BetânIAG</label>
        <input className="input" type="date" value={data} onChange={(e) => e.target.value && setData(e.target.value)} />
      </header>
      <main className="main">
        <Routes>
          <Route path="/" element={<Inicio />} />
          <Route path="/jogador/:id" element={<JogadorPage />} />
          <Route path="/props" element={<Props />} />
          <Route path="/aovivo" element={<AoVivo />} />
          <Route path="/apostas" element={<Apostas />} />
          <Route path="/comparar" element={<Comparar />} />
          <Route path="/noticias" element={<Noticias />} />
          <Route path="/mais" element={<Mais />} />
        </Routes>
      </main>
      <nav className="bottom">
        <NavLink to="/" end><b>⌂</b>Início</NavLink>
        <NavLink to="/props"><b>▤</b>Props</NavLink>
        <NavLink to="/aovivo"><b>●</b>Ao Vivo</NavLink>
        <NavLink to="/apostas"><b>$</b>Apostas</NavLink>
        <MaisLink />
      </nav>
    </Ctx.Provider>
  );
}

function Atualizar() {
  const m = useMutation({
    mutationFn: () => api2.atualizar(true),
    onSuccess: () => { qc.invalidateQueries(); setTimeout(() => m.reset(), 4000); },
  });
  const label = m.isPending ? "Atualizando…" : m.isSuccess ? "Atualizado ✓" : m.isError ? "Falhou" : "Atualizar dados";
  return <button className="btn upd" disabled={m.isPending} title={m.isError ? String((m.error as Error).message) : "Box scores, injury report e escalações"}
    onClick={() => m.mutate()}>{m.isPending ? "⟳" : "↻"} <span className="lbl">{label}</span></button>;
}

function MaisLink() {
  const { pathname } = useLocation();
  const on = ["/mais", "/comparar", "/noticias"].includes(pathname);
  return <NavLink to="/mais" className={on ? "active" : ""}><b>⋯</b>Mais</NavLink>;
}

function Mais() {
  const items = [["/comparar", "⇄", "Comparar", "Jogador × jogador, time × time e tendências"],
                 ["/noticias", "✚", "Notícias", "Mudanças no injury report e quem pode voltar"]];
  return (
    <>
      <h1>Mais</h1>
      <div className="games">{items.map(([to, i, t, s]) => (
        <NavLink key={to} to={to} className="game" style={{ color: "inherit" }}>
          <b style={{ fontSize: "1.1rem" }}>{i} {t}</b><div className="d">{s}</div></NavLink>))}
      </div>
    </>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter><Shell /></BrowserRouter>
    </QueryClientProvider>
  );
}
