import { createContext, useContext, useState } from "react";
import { QueryClient, QueryClientProvider, useMutation, useQuery } from "@tanstack/react-query";
import { BrowserRouter, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { api, api2, Meta, Modo, SenhaError } from "./api";
import Inicio from "./pages/Inicio";
import JogadorPage from "./pages/Jogador";
import Props from "./pages/Props";
import AoVivo from "./pages/AoVivo";
import Apostas from "./pages/Apostas";
import Comparar from "./pages/Comparar";
import Noticias from "./pages/Noticias";
import Ranking from "./pages/Ranking";
import Jogos from "./pages/Jogos";
import Admin from "./pages/Admin";
import Calibracao from "./pages/Calibracao";
import { BotaoTema, Logo, Site, useMarca } from "./marca";

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

function Login({ modo, onOk, site }: { modo: Modo; onOk: () => void; site?: Site | null }) {
  const [login, setLogin] = useState("");
  const [s, setS] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <form className="login" onSubmit={async (e) => {
      e.preventDefault();
      setBusy(true);
      try { await api.login(login, s); onOk(); } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
    }}>
      <h1 className="brand" style={{ gap: 8 }}><Logo size={34} /> {site?.nome ?? "NBA Stats"}</h1>
      {site?.subtitulo && <p className="muted small" style={{ margin: "-4px 0 4px" }}>{site.subtitulo}</p>}
      {modo === "usuarios" && <input className="input" placeholder="Login" value={login} autoFocus autoComplete="username"
        autoCapitalize="none" onChange={(e) => setLogin(e.target.value)} />}
      <input className="input" type="password" placeholder="Senha" value={s} autoFocus={modo !== "usuarios"}
        autoComplete="current-password" onChange={(e) => setS(e.target.value)} />
      <button className="btn primary" disabled={busy}>Entrar</button>
      {err && <div className="err">{err}</div>}
    </form>
  );
}

function TrocarSenha({ obrigatoria, onOk }: { obrigatoria?: boolean; onOk: () => void }) {
  const [f, setF] = useState({ atual: "", nova: "", repete: "" });
  const [err, setErr] = useState("");
  const [ok, setOk] = useState(false);
  return (
    <form className="login" onSubmit={async (e) => {
      e.preventDefault();
      if (f.nova !== f.repete) return setErr("As senhas novas não conferem.");
      try { await api.trocarSenha(f.atual, f.nova); setOk(true); setErr(""); onOk(); } catch (x) { setErr((x as Error).message); }
    }}>
      <h1>{obrigatoria ? "Crie sua senha" : "Trocar senha"}</h1>
      {obrigatoria && <p className="muted small" style={{ margin: 0 }}>Você entrou com uma senha provisória. Escolha a sua (mínimo 8 caracteres).</p>}
      <input className="input" type="password" placeholder={obrigatoria ? "Senha provisória" : "Senha atual"} value={f.atual}
        autoComplete="current-password" onChange={(e) => setF({ ...f, atual: e.target.value })} />
      <input className="input" type="password" placeholder="Nova senha" value={f.nova} autoComplete="new-password" onChange={(e) => setF({ ...f, nova: e.target.value })} />
      <input className="input" type="password" placeholder="Repita a nova senha" value={f.repete} autoComplete="new-password" onChange={(e) => setF({ ...f, repete: e.target.value })} />
      <button className="btn primary">Salvar</button>
      {ok && !obrigatoria && <div className="over">Senha trocada ✓</div>}
      {err && <div className="err">{err}</div>}
      {obrigatoria && <button type="button" className="btn" onClick={async () => { await api.sair(); qc.clear(); onOk(); }}>Sair</button>}
    </form>
  );
}

const sair = async () => { await api.sair(); qc.clear(); window.location.assign("/"); };

function Shell() {
  const [data, setData] = useState(today());
  const [betaniag, setB] = useState(() => { try { return localStorage.getItem("betaniag") === "1"; } catch { return false; } });
  const setBetaniag = (b: boolean) => { try { localStorage.setItem("betaniag", b ? "1" : "0"); } catch { /* sem storage */ } setB(b); };
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta });
  const saude = useQuery({ queryKey: ["saude"], queryFn: api.saude, staleTime: 600_000 });
  const marca = useMarca(meta.data?.site ?? saude.data?.site);
  const [, force] = useState(0);
  const reload = () => { qc.clear(); force((x) => x + 1); };
  if (meta.error instanceof SenhaError) return <Login modo={meta.error.modo} onOk={reload} site={saude.data?.site} />;
  if (meta.data?.usuario?.trocar_senha) return <TrocarSenha obrigatoria onOk={reload} />;
  const m = meta.data;

  return (
    <Ctx.Provider value={{ data, setData, betaniag, setBetaniag }}>
      <header className="top">
        <NavLink to="/" className="brand"><Logo /><span className="lbl">{m?.site?.nome ?? "NBA Stats"}</span></NavLink>
        <nav className="nav">
          <NavLink to="/" end>Início</NavLink>
          <NavLink to="/props">Props</NavLink>
          <NavLink to="/aovivo">Ao Vivo</NavLink>
          <NavLink to="/apostas">Apostas</NavLink>
          <NavLink to="/comparar">Comparar</NavLink>
          <NavLink to="/noticias">Notícias</NavLink>
          <NavLink to="/ranking">Ranking</NavLink>
          <NavLink to="/jogos">Jogos</NavLink>
          <NavLink to="/calibracao">Calibração</NavLink>
        </nav>
        <span className="sp" />
        <Atualizar />
        <label className="toggle"><input type="checkbox" checked={betaniag} onChange={(e) => setBetaniag(e.target.checked)} />BetânIAG</label>
        <input className="input" type="date" value={data} onChange={(e) => e.target.value && setData(e.target.value)} />
        <BotaoTema {...marca} />
        {m && <Conta meta={m} />}
      </header>
      {m?.alerta && <div className="alerta">⚠ {m.alerta}</div>}
      <main className="main">
        <Routes>
          <Route path="/" element={<Inicio />} />
          <Route path="/jogador/:id" element={<JogadorPage />} />
          <Route path="/props" element={<Props />} />
          <Route path="/aovivo" element={<AoVivo />} />
          <Route path="/apostas" element={<Apostas />} />
          <Route path="/comparar" element={<Comparar />} />
          <Route path="/noticias" element={<Noticias />} />
          <Route path="/ranking" element={<Ranking />} />
          <Route path="/jogos" element={<Jogos />} />
          <Route path="/jogos/:id" element={<Jogos />} />
          <Route path="/calibracao" element={<Calibracao />} />
          <Route path="/admin" element={m ? <Admin meta={m} /> : null} />
          <Route path="/conta" element={<TrocarSenha onOk={() => null} />} />
          <Route path="/mais" element={<Mais meta={m} />} />
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

const podeAdmin = (m: Meta) => m.modo !== "usuarios" || m.usuario?.papel === "admin";

function Conta({ meta }: { meta: Meta }) {
  const u = meta.usuario;
  return (
    <details className="conta">
      <summary title={u ? `${u.nome} (${u.papel})` : "Conta"}>{u ? u.nome.slice(0, 1).toUpperCase() : "⚙"}</summary>
      <div className="menu" onClick={(e) => { (e.currentTarget.closest("details") as HTMLDetailsElement).open = false; }}>
        {u && <div className="muted small" style={{ padding: "4px 10px" }}>{u.nome} · {u.papel}</div>}
        {podeAdmin(meta) && <NavLink to="/admin">Administração</NavLink>}
        {u && <NavLink to="/conta">Trocar senha</NavLink>}
        {meta.modo !== "aberto" && <a href="#" onClick={(e) => { e.preventDefault(); sair(); }}>Sair</a>}
      </div>
    </details>
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
  const on = ["/mais", "/comparar", "/noticias", "/ranking", "/jogos", "/calibracao", "/admin", "/conta"].some((p) => pathname.startsWith(p));
  return <NavLink to="/mais" className={on ? "active" : ""}><b>⋯</b>Mais</NavLink>;
}

function Mais({ meta }: { meta?: Meta }) {
  const items = [["/comparar", "⇄", "Comparar", "Jogador × jogador, time × time e tendências"],
                 ["/noticias", "✚", "Notícias", "Mudanças no injury report e quem pode voltar"],
                 ["/ranking", "≡", "Ranking", "Médias, últimos jogos, por 36 min e arremesso"],
                 ["/jogos", "▦", "Jogos", "Box score completo de cada jogo"],
                 ["/calibracao", "◎", "Calibração", "Quando o site disse X%, quanto acertou"]];
  if (meta && podeAdmin(meta)) items.push(["/admin", "⚙", "Administração", "Usuários, acessos, carga e backup"]);
  if (meta?.usuario) items.push(["/conta", "🔑", "Trocar senha", meta.usuario.nome]);
  return (
    <>
      <h1>Mais</h1>
      <div className="games">{items.map(([to, i, t, s]) => (
        <NavLink key={to} to={to} className="game" style={{ color: "inherit" }}>
          <b style={{ fontSize: "1.1rem" }}>{i} {t}</b><div className="d">{s}</div></NavLink>))}
        {meta && meta.modo !== "aberto" && <a href="#" className="game" style={{ color: "inherit" }} onClick={(e) => { e.preventDefault(); sair(); }}>
          <b style={{ fontSize: "1.1rem" }}>⎋ Sair</b><div className="d">Encerrar a sessão neste aparelho</div></a>}
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
