// Indicador que desliza até a aba ativa em toda barra de abas (.tabs, .seg,
// .areatabs). Desenhado pelo ::before da própria barra (CSS em styles.css),
// posicionado por variáveis: nada é inserido no DOM que o React controla.
const BARRAS = ".tabs, .seg, .areatabs";
const ATIVA = ":scope > .on, :scope > .active, :scope > [aria-current='page']";

function posicionar(barra: HTMLElement) {
  const ativa = barra.querySelector<HTMLElement>(ATIVA);
  if (!ativa) { barra.style.setProperty("--ind-o", "0"); return; }
  const v = (k: string, n: number) => barra.style.setProperty(k, `${n}px`);
  v("--ind-x", ativa.offsetLeft); v("--ind-y", ativa.offsetTop);
  v("--ind-w", ativa.offsetWidth); v("--ind-h", ativa.offsetHeight);
  barra.style.setProperty("--ind-o", "1");
  // primeira vez: aparece no lugar, sem viajar desde a esquerda
  if (!barra.dataset.ind) requestAnimationFrame(() => { barra.dataset.ind = "1"; });
}

let agendado = false;
function atualizar() {
  if (agendado) return;
  agendado = true;
  requestAnimationFrame(() => {
    agendado = false;
    document.querySelectorAll<HTMLElement>(BARRAS).forEach(posicionar);
  });
}

export function ligarIndicadores() {
  const mo = new MutationObserver(atualizar);
  mo.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["class", "aria-current"] });
  window.addEventListener("resize", atualizar);
  document.fonts?.ready.then(atualizar);
  atualizar();
}
