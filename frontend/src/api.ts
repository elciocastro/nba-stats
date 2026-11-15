// Cliente da API (FastAPI em /api). A senha vai no cabeçalho X-Senha.

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

export type Meta = { mercados: Record<string, string>; hoje: string; atualizado: string | null; betaniag: boolean };

export class SenhaError extends Error {}

const senha = () => localStorage.getItem("senha") ?? "";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", "X-Senha": senha(), ...(init?.headers ?? {}) },
  });
  if (r.status === 401) throw new SenhaError("senha");
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
  login: async (s: string) => {
    const r = await fetch("/api/login", { method: "POST", headers: { "Content-Type": "application/json" },
                                          body: JSON.stringify({ senha: s }) });
    if (!r.ok) throw new SenhaError("Senha incorreta");
    localStorage.setItem("senha", s);
  },
};

export const headshot = (id: number) => `https://cdn.nba.com/headshots/nba/latest/260x190/${id}.png`;
