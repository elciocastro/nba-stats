// Cliente da API (FastAPI em /api). Sessão: Authorization Bearer; senha única (sem usuários): X-Senha.

export type Janela = { jogos: number; over: number; pct: number | null; media: number | null };
export type Selo = { nivel: string; cor: string; texto: string; unidade: number | null };

export type Jogo = {
  id: number; casa: string; fora: string; status: string | null; casa_id: number; fora_id: number;
  placar_casa: number | null; placar_fora: number | null;
  margem_esperada: number | null; risco_blowout: number | null;
  ritmo: { casa: number | null; fora: number | null; liga: number | null } | null;
  desfalques: { casa: string[]; fora: string[] } | null;
  injury_report: string | null; validacao: { status: string; motivo: string } | null;
};

export type Jogador = {
  player_id: number; jogador: string; time: string; adversario: string; game_id: number;
  grupo: string | null; posicao_est: string | null; lesao: string | null; lesao_motivo: string | null;
  linha: number | null; linha_ref: boolean; odd_over: number | null; odd_under: number | null;
  proj: number | null; diff: number | null; p_over: number | null; p_under: number | null;
  ev: number | null; lado: "over" | "under" | null; chance: number | null;
  l5: number | null; l10: number | null; temporada: number | null;
  min_l5: number | null; min_l10: number | null; usg_l5: number | null; usg_l10: number | null;
  dvp_rank: number | null; dvp_rec_rank: number | null; selo: Selo | null;
  janelas: Record<string, Janela>; valores: { data: string; valor: number; casa: boolean }[];
  time_id: number; jogos: number; proj_vs_l10: number | null; encaixe_zonas: number | null;
  com_sem: { companheiro: string; com: number | null; jogos_com: number; sem: number | null; jogos_sem: number }[] | null;
  fora_ultimo_jogo: boolean; real: number | null;
};

export type Favoritos = Record<"jogador" | "time" | "jogo", { entity_id: number; label: string | null }[]>;
export type LinhaIn = { data: string; player_id: number; mercado: string; linha: number | null;
                        odd_over: number | null; odd_under: number | null };
export type DvpResp = { grupos: string[]; dias_recente: number;
                        linhas: ({ time: string; joga_hoje: boolean } & Record<string, number | string | boolean>)[] };
export type Potencial = { player_id: number; jogador: string; time: string; posicao: string | null; jogos: number;
                          anos_de_liga: number | null; nota: number; joga_hoje: boolean } & Record<string, number | string | null | boolean>;

export type JogoLog = {
  data: string; season: number; game_id: number; opp_id: number; adv: string; em_casa: boolean;
  resultado: "V" | "D" | null; margem: number | null; descanso: number | null;
  minutes: number; usadas: number; [stat: string]: number | string | boolean | null;
};

export type Detalhe = Jogador & {
  jogo: Jogo; temporada_atual: number; rotulos: { atual: string; anterior: string };
  proj_detalhe: { valor: number; base: number; minutos: number; f_dvp: number; f_ritmo: number;
                  f_ajuste: number; ausencia: number; erro_tipico: number | null } | null;
  com_sem: { companheiro: string; com: number | null; jogos_com: number; sem: number | null; jogos_sem: number }[] | null;
  medias: Record<string, number>; log: JogoLog[]; adversario_id: number;
  checklist: { item: string; valor: string; ok: boolean | null; nota: string }[] | null;
};

export type Oportunidade = {
  player_id: number; jogador: string; time: string; adversario: string; mercado: string;
  linha: number; linha_ref: boolean; proj: number | null; lado: string; chance: number;
  odd: number | null; ev: number | null; selo: Selo | null; valores: number[]; lesao: string | null;
};

export type Inicio = {
  data: string;
  jogos: {
    game_id: number; casa: string; fora: string; status: string | null; placar: string | null;
    favorito: string | null; margem: number | null; blowout: number | null; ritmo_vs_liga: number | null;
    desfalques: { casa: string[]; fora: string[] }; props_boas: number;
    melhor: { jogador: string; player_id: number; mercado: string; lado: string; linha: number; chance: number } | null;
    validacao: { status: string } | null;
  }[];
  oportunidades: { com_odd: Oportunidade[]; sem_odd: Oportunidade[] };
  em_alta: { player_id: number; jogador: string; time: string; adversario: string; l5: number;
             temporada: number; alta_pct: number; min_l5: number; min_l10: number;
             uso_l5: number | null; proj: number | null; lesao: string | null; valores: number[] }[];
};

export type Usuario = { id: number; login: string; nome: string; papel: "admin" | "usuario"; trocar_senha: boolean; expira_em: string | null };
export type Modo = "usuarios" | "senha" | "aberto";
export type Meta = { mercados: Record<string, string>; hoje: string; atualizado: string | null; betaniag: boolean;
  modo: Modo; usuario: Usuario | null; alerta: string | null };

export class SenhaError extends Error {
  constructor(public modo: Modo = "senha") { super("login"); }
}

const store = {
  get: (k: string) => { try { return localStorage.getItem(k) ?? ""; } catch { return ""; } },
  set: (k: string, v: string) => { try { if (v) localStorage.setItem(k, v); else localStorage.removeItem(k); } catch { /* sem storage */ } },
};
const authHeaders = (): Record<string, string> => {
  const h: Record<string, string> = {};
  if (store.get("token")) h.Authorization = `Bearer ${store.get("token")}`;
  if (store.get("senha")) h["X-Senha"] = store.get("senha");
  return h;
};

export async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...authHeaders(), ...(init?.headers ?? {}) },
  });
  if (r.status === 401) {
    const b = await r.json().catch(() => ({}));
    if (b.detail === "login") throw new SenhaError(b.modo ?? "senha");
    throw new Error(b.detail ?? "Não autorizado");
  }
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? r.statusText);
  return r.json();
}

const qs = (o: Record<string, string | number | boolean | undefined | null>) =>
  new URLSearchParams(Object.entries(o).filter(([, v]) => v !== undefined && v !== null)
    .map(([k, v]) => [k, String(v)])).toString();

export const api = {
  meta: () => call<Meta>("/api/meta"),
  inicio: (data: string, betaniag: boolean) => call<Inicio>(`/api/inicio?${qs({ data, betaniag })}`),
  props: (data: string, mercado: string, betaniag: boolean) =>
    call<{ jogos: Jogo[]; jogadores: Jogador[]; temporada: string; anterior: string }>(
      `/api/props?${qs({ data, mercado, betaniag })}`),
  jogador: (id: number, data: string, mercado: string, betaniag: boolean) =>
    call<Detalhe>(`/api/jogador/${id}?${qs({ data, mercado, betaniag })}`),
  chance: (mercado: string, proj: number, linha: number) =>
    call<{ p_over: number | null }>(`/api/chance?${qs({ mercado, proj, linha })}`),
  salvarLinha: (b: { data: string; player_id: number; mercado: string; linha: number | null;
                     odd_over: number | null; odd_under: number | null }) =>
    call<{ ok: boolean }>("/api/linhas", { method: "PUT", body: JSON.stringify(b) }),
  salvarLinhas: (b: LinhaIn[]) => call<{ salvas: number }>("/api/linhas/lote", { method: "PUT", body: JSON.stringify(b) }),
  dvp: (data: string, mercado: string, recente: boolean) => call<DvpResp>(`/api/dvp?${qs({ data, mercado, recente })}`),
  potenciais: (data: string) => call<{ jogadores: Potencial[]; regras: Record<string, unknown> }>(`/api/potenciais?${qs({ data })}`),
  favoritos: () => call<Favoritos>("/api/favoritos"),
  favoritar: (tipo: string, id: number, nome?: string) =>
    call<Favoritos>("/api/favoritos", { method: "POST", body: JSON.stringify({ tipo, id, nome }) }),
  desfavoritar: (tipo: string, id: number) => call<Favoritos>(`/api/favoritos/${tipo}/${id}`, { method: "DELETE" }),
  saude: () => call<{ ok: boolean; modo: Modo }>("/api/saude"),
  login: async (login: string, senha: string) => {
    const r = await fetch("/api/login", { method: "POST", headers: { "Content-Type": "application/json" },
                                          body: JSON.stringify({ login, senha }) });
    const b = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(b.detail ?? "Senha incorreta");
    if (b.token) { store.set("token", b.token); store.set("senha", ""); } else store.set("senha", senha);
  },
  primeiroAdmin: async (body: { login: string; nome?: string; senha: string; senha_atual?: string }) => {
    const b = await call<{ token: string }>("/api/primeiro-admin", { method: "POST", body: JSON.stringify(body) });
    store.set("token", b.token); store.set("senha", "");
  },
  sair: async () => { await call("/api/sair", { method: "POST" }).catch(() => null); store.set("token", ""); store.set("senha", ""); },
  trocarSenha: (atual: string, nova: string) => call<{ ok: boolean }>("/api/eu/senha", { method: "POST", body: JSON.stringify({ atual, nova }) }),
};

export const headshot = (id: number) => `https://cdn.nba.com/headshots/nba/latest/260x190/${id}.png`;

export type LivePlayer = {
  player_id: number; jogador: string; time: string; atual: number; minutos: number; restante: number;
  final: number; chance: number | null; falta: number | null; status: string | null; alertas: string[];
  alvo: number | null; linha_ref: boolean; media: number | null; proj_pre: number | null;
  em_quadra: boolean; faltas: number; jogo?: string; game_id?: number;
};
export type LiveGame = {
  game_id: number; status: number; status_texto: string; periodo: number; relogio_seg: number;
  casa: string; fora: string; placar_casa: number; placar_fora: number; minutos_restantes: number;
  jogadores: LivePlayer[];
};
export const aoVivo = (mercado: string, alvo: string) =>
  call<{ data: string | null; jogos: LiveGame[]; destaques: LivePlayer[]; atualizado_ha: number }>(`/api/aovivo?mercado=${mercado}&alvo=${alvo}`);

// ---------- apostas, comparar, notícias ----------
export type Bet = { id: number; date: string; jogador: string; player_id: number; market: string; side: string;
  line: number; odd: number; units: number; bookmaker: string | null; prob: number | null; proj: number | null;
  status: string; actual: number | null; profit_units: number | null; casa_time: string | null; fora_time: string | null };
export type Resumo = { apostas: number; pendentes: number; conferidas: number; ganhas: number; acerto_pct: number | null;
  chance_media_pct: number | null; unidades_apostadas: number; lucro_unidades: number; roi_pct: number | null };
export type Desempenho = { geral: Resumo; mercado: Record<string, Resumo>; unidades: Record<string, Resumo>;
  faixa_chance: Record<string, Resumo>; lado: Record<string, Resumo>; curva: { data: string; lucro_acumulado: number }[] };
export type TeamSide = { time: string; jogos: number; ritmo: number | null; saldo: number | null; pts_feitos: number | null;
  pts_cedidos: number | null; dvp: { grupo: string; stat: string; media: number | null; rank: number | null; media_rec: number | null; rank_rec: number | null }[] };
export type Trend = { player_id: number; jogador: string; time: string; l5: number; temporada: number; dif: number; pra_l5: number };
export type Noticias = { atual: string | null; anterior: string | null;
  mudancas: { tipo: string; player_id: number | null; jogador: string; time: string; antes: string | null; agora: string | null; motivo: string | null }[];
  relatorios: { published_at: string; nomes: number }[];
  retornos: { player_id: number; jogador: string; time: string; status: string; jogos_fora: number | null; minutos_antes: number;
              pts: number; reb: number; ast: number; pra: number; pra_por_min: number; motivo: string | null }[] };

const j = call;

export const api2 = {
  apostas: (status?: string) => j<{ apostas: Bet[]; desempenho: Desempenho; config: { valor_unidade: number | null; moeda: string; unidades: number[] } }>(
    `/api/apostas${status ? `?status=${status}` : ""}`),
  apostar: (b: { data: string; player_id: number; mercado: string; lado: string; linha: number; odd: number; unidades: number; casa?: string; obs?: string }) =>
    j<{ id: number; chance: number | null }>("/api/apostas", { method: "POST", body: JSON.stringify(b) }),
  apagarAposta: (id: number) => j(`/api/apostas/${id}`, { method: "DELETE" }),
  conferir: () => j<{ conferidas: Record<string, number> }>("/api/apostas/conferir", { method: "POST" }),
  times: () => j<{ id: number; sigla: string; nome: string }[]>("/api/times"),
  compararTimes: (a: number, b: number, data: string) => j<{ temporada: number; liga_ritmo: number; a: TeamSide; b: TeamSide }>(`/api/comparar/times?a=${a}&b=${b}&data=${data}`),
  tendencias: (data: string) => j<{ minutos: Trend[]; minutos_queda: Trend[]; uso: Trend[];
    defesas: { time: string; grupo: string; pra_temporada: number; pra_recente: number; dif: number; rank_recente: number }[] }>(`/api/tendencias?data=${data}`),
  noticias: (data: string) => j<Noticias>(`/api/noticias?data=${data}`),
  atualizar: (forcar = false) => j<{ pulado: boolean; minutos?: number; relatorio?: string | null }>(`/api/atualizar?forcar=${forcar}`, { method: "POST" }),
};

// ---------- ranking, jogos, administração ----------
export type RankRow = { player_id: number; jogador: string; posicao: string | null; time: string; jogos: number;
  fg_pct: number | null; fg3_pct: number | null; ft_pct: number | null; ts_pct: number | null; fga: number; fg3a: number; fta: number;
  [k: string]: number | string | null };
export type JogoDia = { id: number; date: string; status: string | null; placar_casa: number | null; placar_fora: number | null;
  casa: string; fora: string; casa_id: number; fora_id: number; tem_box: boolean };
export type BoxRow = { player_id: number; jogador: string; posicao: string | null; min: number; pts: number; reb: number; ast: number;
  stl: number; blk: number; turnover: number; pf: number; fgm: number; fga: number; fg3m: number; fg3a: number; ftm: number; fta: number;
  oreb: number; dreb: number; plus_minus: number | null; pra: number };
export type BoxTime = { lado: string; time_id: number; time: string; nome: string; placar: number | null; jogadores: BoxRow[];
  nao_jogaram: string[]; totais: Record<string, number | null> };
export type UsuarioAdm = { id: number; login: string; nome: string; papel: string; ativo: boolean; expira_em: string | null;
  trocar_senha: boolean; criado_em: string; ultimo_acesso: string | null; sessoes: number };
export type Acesso = { quando: string; login: string | null; ok: boolean; ip: string | null; motivo: string | null };
export type Sistema = { carga: { ultima_ok: string | null; horas: number | null; alerta: string | null;
    falhas: { kind: string; started_at: string; error: string | null }[] };
  backup: { quantidade: number; ultimo: string | null; horas: number | null; tamanho_mb: number | null; alerta: string | null };
  cargas: { kind: string; started_at: string; finished_at: string | null; status: string; games: number; stats: number; error: string | null }[];
  banco_mb: number | null };

export const api3 = {
  ranking: (data: string, janela: number, min_jogos: number, por36: boolean, playoffs: boolean) =>
    call<{ temporada: number; janela: number; jogadores: RankRow[] }>(`/api/ranking?${qs({ data, janela, min_jogos, por36, playoffs })}`),
  jogos: (data: string) => call<{ data: string; pedida: string; jogos: JogoDia[] }>(`/api/jogos?${qs({ data })}`),
  jogo: (id: number) => call<{ id: number; data: string; status: string | null; playoffs: boolean; times: BoxTime[] }>(`/api/jogo/${id}`),
  usuarios: () => call<{ usuarios: UsuarioAdm[]; papeis: string[] }>("/api/admin/usuarios"),
  criarUsuario: (b: { login: string; nome?: string; papel: string; expira_em?: string | null }) =>
    call<{ id: number; senha_provisoria: string }>("/api/admin/usuarios", { method: "POST", body: JSON.stringify(b) }),
  mudarUsuario: (id: number, b: { nome?: string; papel?: string; ativo?: boolean; expira_em?: string | null; mudar_validade?: boolean }) =>
    call<{ ok: boolean }>(`/api/admin/usuarios/${id}`, { method: "PATCH", body: JSON.stringify(b) }),
  resetarSenha: (id: number) => call<{ senha_provisoria: string }>(`/api/admin/usuarios/${id}/senha`, { method: "POST" }),
  derrubar: (id: number) => call<{ encerradas: number }>(`/api/admin/usuarios/${id}/sair`, { method: "POST" }),
  apagarUsuario: (id: number) => call<{ ok: boolean }>(`/api/admin/usuarios/${id}`, { method: "DELETE" }),
  acessos: () => call<{ acessos: Acesso[] }>("/api/admin/acessos"),
  sistema: () => call<Sistema>("/api/admin/sistema"),
  backup: () => call<{ arquivo: string }>("/api/admin/backup", { method: "POST" }),
};
