// Identidade: logo (bola), tema claro/escuro e cor de destaque.
import { useEffect, useState } from "react";

export type Tema = "escuro" | "claro" | "sistema";
export type Site = { nome: string; subtitulo?: string | null; cor_destaque: string; tema_padrao: Tema };

export function Logo({ size = 26 }: { size?: number }) {
  return (
    <svg className="logo" width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <rect width="64" height="64" rx="14" fill="var(--brand)" />
      <g fill="none" stroke="var(--brand-ink)" strokeWidth="3.6" strokeLinecap="round">
        <circle cx="32" cy="32" r="21" />
        <path d="M32 11 V53 M11 32 H53" />
        <path d="M17.5 17 C25 24 25 40 17.5 47" />
        <path d="M46.5 17 C39 24 39 40 46.5 47" />
      </g>
    </svg>
  );
}

const lerTema = (): Tema | null => {
  try { const t = localStorage.getItem("tema"); return t === "escuro" || t === "claro" || t === "sistema" ? t : null; } catch { return null; }
};

/** Aplica o tema (escolha da pessoa > padrão do site) e a cor de destaque. */
export function useMarca(site?: Site | null) {
  const [tema, setTemaState] = useState<Tema | null>(lerTema);
  const efetivo: Tema = tema ?? site?.tema_padrao ?? "escuro";
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const apply = () => {
      const claro = efetivo === "claro" || (efetivo === "sistema" && mq.matches);
      document.documentElement.dataset.theme = claro ? "claro" : "escuro";
      document.querySelector('meta[name="theme-color"]')?.setAttribute("content", claro ? "#ffffff" : "#0b0f14");
    };
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, [efetivo]);
  useEffect(() => {
    if (!site) return;
    const root = document.documentElement.style;
    root.setProperty("--brand", site.cor_destaque);
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(site.cor_destaque.slice(i, i + 2), 16));
    root.setProperty("--brand-soft", `rgba(${r}, ${g}, ${b}, .12)`);
    // texto sobre a cor: escuro em cores claras, branco nas escuras
    root.setProperty("--brand-ink", 0.299 * r + 0.587 * g + 0.114 * b > 150 ? "#111827" : "#ffffff");
    document.title = site.nome;
  }, [site]);
  const setTema = (t: Tema) => { try { localStorage.setItem("tema", t); } catch { /* sem storage */ } setTemaState(t); };
  return { tema: efetivo, setTema };
}

export function BotaoTema({ tema, setTema }: { tema: Tema; setTema: (t: Tema) => void }) {
  const prox: Record<Tema, Tema> = { escuro: "claro", claro: "sistema", sistema: "escuro" };
  const icone: Record<Tema, string> = { escuro: "☾", claro: "☀", sistema: "◐" };
  return <button className="tema" title={`Tema: ${tema} (clique para ${prox[tema]})`} onClick={() => setTema(prox[tema])}>{icone[tema]}</button>;
}

/** Bola quicando (login e carregamentos). Parada para quem pede menos movimento. */
export function BolaQuicando({ size = 64 }: { size?: number }) {
  return (
    <div className="bola" style={{ width: size, height: size * 1.9 }} aria-hidden="true">
      <svg className="bola-svg" width={size} height={size} viewBox="0 0 64 64">
        <g className="bola-giro">
          <circle cx="32" cy="32" r="30" fill="var(--brand)" />
          <g fill="none" stroke="var(--brand-ink)" strokeWidth="3" strokeLinecap="round" opacity=".85">
            <path d="M32 2 V62 M2 32 H62" />
            <path d="M12 10 C22 20 22 44 12 54" />
            <path d="M52 10 C42 20 42 44 52 54" />
          </g>
        </g>
        <circle cx="23" cy="20" r="9" fill="#fff" opacity=".14" />
      </svg>
      <span className="bola-sombra" />
    </div>
  );
}
