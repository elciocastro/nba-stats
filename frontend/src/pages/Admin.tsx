// Administração: usuários (criar, desativar, validade, senha provisória,
// encerrar sessões), registro de acessos e saúde da carga/backup.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api, api3, Meta, UsuarioAdm } from "../api";

const quando = (iso: string | null) => (iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—");

export default function Admin({ meta }: { meta: Meta }) {
  const [sp, setSp] = useSearchParams();
  const aba = sp.get("aba") ?? "usuarios";
  if (meta.modo !== "usuarios") return <PrimeiroAdmin meta={meta} />;
  if (meta.usuario?.papel !== "admin") return <><h1>Administração</h1><p className="muted">Só para administradores.</p></>;
  const tabs: Record<string, string> = { usuarios: "Usuários", acessos: "Acessos", sistema: "Sistema" };
  return (
    <>
      <h1>Administração</h1>
      <nav className="areatabs">{Object.entries(tabs).map(([k, v]) =>
        <a key={k} className={k === aba ? "on" : ""} href="#" onClick={(e) => { e.preventDefault(); setSp({ aba: k }); }}>{v}</a>)}</nav>
      <div style={{ marginTop: 14 }}>
        {aba === "usuarios" && <Usuarios eu={meta.usuario?.id} />}
        {aba === "acessos" && <Acessos />}
        {aba === "sistema" && <Sistema />}
      </div>
    </>
  );
}

function PrimeiroAdmin({ meta }: { meta: Meta }) {
  const qc = useQueryClient();
  const [f, setF] = useState({ login: "", nome: "", senha: "", repete: "", senha_atual: "" });
  const m = useMutation({
    mutationFn: () => {
      if (f.senha !== f.repete) throw new Error("As senhas não conferem.");
      return api.primeiroAdmin({ login: f.login, nome: f.nome || undefined, senha: f.senha, senha_atual: f.senha_atual || undefined });
    },
    onSuccess: () => qc.invalidateQueries(),
  });
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  return (
    <>
      <h1>Administração</h1>
      <div className="panel" style={{ maxWidth: 520 }}>
        <b>Criar o primeiro administrador</b>
        <p className="muted small">Hoje o site usa {meta.modo === "senha" ? "uma senha única para todos" : "acesso aberto (sem senha)"}.
          Com o primeiro administrador, cada pessoa passa a entrar com o próprio login, e você controla quem acessa,
          até quando, e vê o registro de entradas. {meta.modo === "senha" && "A senha única deixa de valer."}</p>
        <div style={{ display: "grid", gap: 8 }}>
          <input className="input" placeholder="Login (ex.: elcio)" value={f.login} onChange={set("login")} autoComplete="username" />
          <input className="input" placeholder="Nome (opcional)" value={f.nome} onChange={set("nome")} />
          <input className="input" type="password" placeholder="Senha (mín. 8)" value={f.senha} onChange={set("senha")} autoComplete="new-password" />
          <input className="input" type="password" placeholder="Repita a senha" value={f.repete} onChange={set("repete")} autoComplete="new-password" />
          {meta.modo === "senha" && <input className="input" type="password" placeholder="Senha atual do site" value={f.senha_atual} onChange={set("senha_atual")} />}
          <button className="btn primary" disabled={m.isPending || !f.login || !f.senha} onClick={() => m.mutate()}>Criar e entrar</button>
          {m.error && <div className="err">{(m.error as Error).message}</div>}
        </div>
      </div>
    </>
  );
}

function Senha({ titulo, senha, onClose }: { titulo: string; senha: string; onClose: () => void }) {
  const [ok, setOk] = useState(false);
  return (
    <div className="panel" style={{ borderColor: "var(--over)", marginBottom: 14 }}>
      <b>{titulo}</b>
      <p className="small muted" style={{ margin: "6px 0" }}>Senha provisória (aparece só agora). Passe para a pessoa por um canal privado;
        ela vai criar a própria senha no primeiro acesso.</p>
      <div className="row"><code style={{ fontSize: "1.1rem", padding: "4px 10px", background: "var(--panel2)", borderRadius: 6 }}>{senha}</code>
        <button className="btn" onClick={() => navigator.clipboard?.writeText(senha).then(() => setOk(true))}>{ok ? "Copiada ✓" : "Copiar"}</button>
        <button className="btn" onClick={onClose}>Fechar</button></div>
    </div>
  );
}

function Usuarios({ eu }: { eu?: number }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["admin-usuarios"], queryFn: api3.usuarios });
  const [novo, setNovo] = useState({ login: "", nome: "", papel: "usuario", expira_em: "" });
  const [prov, setProv] = useState<{ titulo: string; senha: string } | null>(null);
  const [err, setErr] = useState("");
  const done = () => { setErr(""); qc.invalidateQueries({ queryKey: ["admin-usuarios"] }); };
  const fail = (e: Error) => setErr(e.message);
  const criar = useMutation({ mutationFn: () => api3.criarUsuario({ ...novo, expira_em: novo.expira_em || null }),
    onSuccess: (r) => { setProv({ titulo: `Usuário ${novo.login} criado`, senha: r.senha_provisoria });
                        setNovo({ login: "", nome: "", papel: "usuario", expira_em: "" }); done(); }, onError: fail });
  const mudar = useMutation({ mutationFn: (v: { id: number; b: Parameters<typeof api3.mudarUsuario>[1] }) => api3.mudarUsuario(v.id, v.b),
    onSuccess: done, onError: fail });
  const reset = useMutation({ mutationFn: (u: UsuarioAdm) => api3.resetarSenha(u.id).then((r) => ({ u, r })),
    onSuccess: ({ u, r }) => { setProv({ titulo: `Nova senha de ${u.login}`, senha: r.senha_provisoria }); done(); }, onError: fail });
  const derrubar = useMutation({ mutationFn: api3.derrubar, onSuccess: done, onError: fail });
  const apagar = useMutation({ mutationFn: api3.apagarUsuario, onSuccess: done, onError: fail });

  return (
    <>
      {prov && <Senha {...prov} onClose={() => setProv(null)} />}
      <div className="panel" style={{ marginBottom: 14 }}>
        <b>Novo usuário</b>
        <div className="row" style={{ marginTop: 8, alignItems: "flex-end" }}>
          <label className="field">Login<input className="input" value={novo.login} onChange={(e) => setNovo({ ...novo, login: e.target.value })} /></label>
          <label className="field">Nome<input className="input" value={novo.nome} onChange={(e) => setNovo({ ...novo, nome: e.target.value })} /></label>
          <label className="field">Papel<select className="input" value={novo.papel} onChange={(e) => setNovo({ ...novo, papel: e.target.value })}>
            <option value="usuario">usuário</option><option value="admin">admin</option></select></label>
          <label className="field">Acesso até (opcional)<input className="input" type="date" style={{ width: 150 }} value={novo.expira_em}
            onChange={(e) => setNovo({ ...novo, expira_em: e.target.value })} /></label>
          <button className="btn primary" disabled={!novo.login || criar.isPending} onClick={() => criar.mutate()}>Criar</button>
        </div>
      </div>
      {err && <div className="err" style={{ marginBottom: 10 }}>{err}</div>}
      <div className="tw"><table className="t">
        <thead><tr><th>Usuário</th><th>Papel</th><th>Situação</th><th>Acesso até</th><th>Último acesso</th><th>Sessões</th><th>Ações</th></tr></thead>
        <tbody>{q.data?.usuarios.map((u) => (
          <tr key={u.id}>
            <td><b>{u.nome}</b> <span className="muted small">{u.login}{u.id === eu ? " (você)" : ""}</span></td>
            <td><select className="input" value={u.papel} onChange={(e) => mudar.mutate({ id: u.id, b: { papel: e.target.value } })}>
              <option value="usuario">usuário</option><option value="admin">admin</option></select></td>
            <td><span className={`chip ${u.ativo ? "ok" : "bad"}`}>{u.ativo ? "ativo" : "desativado"}</span>
              {u.trocar_senha && <span className="chip hot" style={{ marginLeft: 4 }} title="Ainda não criou a própria senha">provisória</span>}</td>
            <td><input className="input" type="date" style={{ width: 150 }} value={u.expira_em ?? ""}
              onChange={(e) => mudar.mutate({ id: u.id, b: { expira_em: e.target.value || null, mudar_validade: true } })} /></td>
            <td className="small">{quando(u.ultimo_acesso)}</td>
            <td>{u.sessoes}</td>
            <td style={{ whiteSpace: "nowrap" }}>
              <button className="btn" onClick={() => mudar.mutate({ id: u.id, b: { ativo: !u.ativo } })}>{u.ativo ? "Desativar" : "Ativar"}</button>{" "}
              <button className="btn" title="Gera uma senha provisória e encerra as sessões" onClick={() => confirm(`Gerar nova senha para ${u.login}?`) && reset.mutate(u)}>Nova senha</button>{" "}
              <button className="btn" disabled={!u.sessoes} title="Desconecta todos os aparelhos" onClick={() => derrubar.mutate(u.id)}>Desconectar</button>{" "}
              {u.id !== eu && <button className="star" title="Apagar" onClick={() => confirm(`Apagar ${u.login}? Não dá para desfazer.`) && apagar.mutate(u.id)}>🗑</button>}
            </td>
          </tr>))}
        </tbody></table></div>
      <p className="muted small">Desativar ou mudar a senha derruba as sessões abertas na hora. Com “Acesso até”, o login para de funcionar depois da data.
        Sempre fica pelo menos um admin ativo.</p>
    </>
  );
}

function Acessos() {
  const q = useQuery({ queryKey: ["admin-acessos"], queryFn: api3.acessos, refetchInterval: 60_000 });
  const MOT: Record<string, string> = { senha: "senha errada", inativo: "desativado", expirado: "acesso expirado", bloqueado: "bloqueado (tentativas)" };
  return (
    <>
      <p className="muted small" style={{ marginTop: 0 }}>Últimas 100 tentativas de login. Depois de 5 senhas erradas em 15 minutos, o login fica bloqueado por 15 minutos.</p>
      <div className="tw"><table className="t">
        <thead><tr><th>Quando</th><th>Login</th><th>Resultado</th><th>IP</th></tr></thead>
        <tbody>{q.data?.acessos.map((a, i) => (
          <tr key={i}><td>{quando(a.quando)}</td><td>{a.login ?? "—"}</td>
            <td><span className={`chip ${a.ok ? "ok" : "bad"}`}>{a.ok ? "entrou" : MOT[a.motivo ?? ""] ?? a.motivo}</span></td>
            <td className="muted small">{a.ip ?? ""}</td></tr>))}
        </tbody></table></div>
    </>
  );
}

function Sistema() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["admin-sistema"], queryFn: api3.sistema });
  const bk = useMutation({ mutationFn: api3.backup, onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-sistema"] }) });
  if (!q.data) return <div className="loading">Carregando…</div>;
  const { carga, backup, cargas, banco_mb, alertas } = q.data;
  return (
    <>
      <div className="kpis">
        <div className="kpi"><div className="l">Última carga boa</div><div className={`v ${carga.alerta ? "under" : "over"}`}>
          {carga.horas == null ? "—" : `${Math.round(carga.horas)} h`}</div><div className="s">{quando(carga.ultima_ok)}</div></div>
        <div className="kpi"><div className="l">Backups</div><div className={`v ${backup.alerta ? "under" : ""}`}>{backup.quantidade}</div>
          <div className="s">{backup.ultimo ? `último há ${Math.round(backup.horas ?? 0)} h · ${backup.tamanho_mb} MB` : "nenhum"}</div></div>
        <div className="kpi"><div className="l">Banco</div><div className="v">{banco_mb ?? "—"} MB</div><div className="s">data/nba.db</div></div>
        <div className="kpi"><div className="l">Alertas Telegram</div><div className={`v ${alertas.habilitado && alertas.telegram ? "over" : ""}`}>
          {alertas.habilitado && alertas.telegram ? "ligados" : "desligados"}</div>
          <div className="s">{alertas.telegram ? "bot configurado" : "sem token no .env"} · {alertas.habilitado ? "habilitado" : "config/alertas.yaml"}</div></div>
      </div>
      {(carga.alerta || backup.alerta) && <div className="err" style={{ margin: "10px 0" }}>{[carga.alerta, backup.alerta].filter(Boolean).join(" · ")}</div>}
      <div className="row" style={{ margin: "10px 0" }}>
        <button className="btn" disabled={bk.isPending} onClick={() => bk.mutate()}>{bk.isSuccess ? `Backup ${bk.data.arquivo} ✓` : "Fazer backup agora"}</button>
        <span className="muted small">O cron faz um por dia (06:30) e guarda os 14 mais novos em data/backup.</span>
      </div>
      <h2>Últimas cargas</h2>
      <div className="tw"><table className="t">
        <thead><tr><th>Tipo</th><th>Início</th><th>Situação</th><th>Jogos</th><th>Estatísticas</th><th>Erro</th></tr></thead>
        <tbody>{cargas.map((c, i) => (
          <tr key={i}><td>{c.kind}</td><td>{quando(c.started_at)}</td>
            <td><span className={`chip ${c.status === "ok" ? "ok" : c.status === "error" ? "bad" : "hot"}`}>{c.status}</span></td>
            <td>{c.games}</td><td>{c.stats}</td><td className="muted small" style={{ whiteSpace: "normal" }}>{c.error ?? ""}</td></tr>))}
        </tbody></table></div>
    </>
  );
}
