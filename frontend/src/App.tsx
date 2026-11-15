import { createContext, useContext, useState } from "react";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import { api, SenhaError } from "./api";
import Inicio from "./pages/Inicio";
import JogadorPage from "./pages/Jogador";

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
        <span className="brand">🏀 NBA Stats</span>
        <nav className="nav">
          <NavLink to="/" end>Início</NavLink>
          <a href="http://localhost:8501" target="_blank" rel="noreferrer" title="Site antigo (Streamlit)">Props ↗</a>
        </nav>
        <span className="sp" />
        <label className="toggle"><input type="checkbox" checked={betaniag} onChange={(e) => setBetaniag(e.target.checked)} />BetânIAG</label>
        <input className="input" type="date" value={data} onChange={(e) => e.target.value && setData(e.target.value)} />
      </header>
      <main className="main">
        <Routes>
          <Route path="/" element={<Inicio />} />
          <Route path="/jogador/:id" element={<JogadorPage />} />
        </Routes>
      </main>
      <nav className="bottom">
        <NavLink to="/" end><b>⌂</b>Início</NavLink>
      </nav>
    </Ctx.Provider>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter><Shell /></BrowserRouter>
    </QueryClientProvider>
  );
}
