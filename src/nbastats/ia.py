"""Relatório BetânIAG com IA (opcional, desligado por padrão).

O modelo de linguagem só **escreve** a análise: todos os números vêm do site
(projeção, chance, odds, janelas, DvP, lesões) e vão como dados JSON. A
instrução proíbe inventar números.

Para ligar: ``pip install -e ".[ia]"``, ``ANTHROPIC_API_KEY`` no ``.env`` e
``ia.habilitado: true`` em ``config/betaniag.yaml``.
"""

from __future__ import annotations

import json
import os
from typing import Any

SYSTEM = """Você é o analista do Protocolo BetânIAG para props da NBA. Escreva em português do Brasil.

Regras:
- Use SOMENTE os números do JSON recebido. Não invente estatísticas, odds, notícias nem lesões.
  Se faltar um dado, diga que falta.
- A chance do modelo é calibrada; taxas de acerto (L5, L10, H2H) são contexto. H2H com menos de
  3 jogos é só curiosidade.
- Odd justa = 1 / chance. Há valor quando a odd da casa supera a odd justa.
- Se a validação estiver como "pré-análise", diga isso no início.
- Formato: título; um parágrafo de leitura; uma tabela Markdown com as colunas
  Jogador | Mercado | Lado | Linha | Chance | Odd justa | Odd casa | EV | Nível; e uma lista curta
  de riscos (minutos, lesões, blowout, poucos jogos).
- Não prometa resultado e não incentive apostar além do planejado."""


class IADesligada(RuntimeError):
    """IA desligada na configuração ou sem chave/biblioteca."""


def status(cfg: dict[str, Any]) -> tuple[bool, str]:
    """(pode usar, motivo) a partir de config/betaniag.yaml e do ambiente."""
    ia = cfg.get("ia") or {}
    if not ia.get("habilitado"):
        return False, "IA desligada em config/betaniag.yaml (ia.habilitado: false)."
    if not os.getenv("ANTHROPIC_API_KEY"):
        return False, "Falta ANTHROPIC_API_KEY no .env."
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False, 'Biblioteca ausente: pip install -e ".[ia]".'
    return True, f"IA ligada ({ia.get('modelo', 'claude-opus-5-5')})."


def player_payload(p: dict[str, Any], stat: str, seal: dict[str, Any] | None,
                   valid: dict[str, Any] | None) -> dict[str, Any]:
    """O que vai para o modelo sobre um jogador: só números já calculados."""
    jan = {k: {kk: v.get(kk) for kk in ("jogos", "over", "pct", "media")}
           for k, v in (p.get("janelas") or {}).items()}
    return {
        "jogador": p["jogador"], "time": p["time"], "adversario": p["adversario"], "mercado": stat,
        "linha": p.get("linha"), "linha_de_referencia": p.get("linha_ref"),
        "odd_over": p.get("odd_over"), "odd_under": p.get("odd_under"),
        "projecao": p.get("proj"), "erro_tipico": (p.get("proj_detalhe") or {}).get("erro_tipico"),
        "chance_over": p.get("p_over"), "chance_under": p.get("p_under"),
        "minutos_l5": p.get("min_l5"), "minutos_l10": p.get("min_l10"),
        "minutos_esperados": (p.get("proj_detalhe") or {}).get("minutos"),
        "dvp_rank_adversario": p.get("dvp_rank"), "lesao": p.get("lesao"),
        "com_sem_desfalques": p.get("com_sem"), "janelas": jan,
        "selo": None if seal is None else {k: seal.get(k) for k in (
            "lado", "chance", "odd", "ev", "chance_mercado", "vantagem", "nivel", "unidade")},
        "validacao": valid,
    }


def report(cfg: dict[str, Any], data: dict[str, Any], question: str | None = None) -> str:
    """Gera o texto da análise. Levanta IADesligada se não puder usar a IA."""
    ok, why = status(cfg)
    if not ok:
        raise IADesligada(why)
    import anthropic

    ia = cfg.get("ia") or {}
    ask = question or "Escreva a análise formal do protocolo para estes dados."
    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=ia.get("modelo", "claude-opus-5-5"),
        max_tokens=int(ia.get("max_tokens", 8000)),
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": ia.get("esforco", "medium")},
        system=SYSTEM,
        messages=[{"role": "user", "content": (
            f"Dados do site (JSON):\n{json.dumps(data, ensure_ascii=False, default=str)}\n\n"
            f"Pedido: {ask}")}],
    )
    if response.stop_reason == "refusal":
        raise IADesligada("O modelo recusou o pedido.")
    text = "".join(b.text for b in response.content if b.type == "text")
    if response.stop_reason == "max_tokens":
        text += "\n\n_(texto cortado pelo limite de tamanho; aumente ia.max_tokens)_"
    return text
