"""Ajustes feitos pela tela de Administração, por cima dos YAML de config/.

Os arquivos de ``config/`` continuam sendo o padrão (no Git). O que o admin
muda vai para ``data/ajustes/<arquivo>.yaml`` (fora do Git, por ambiente) e é
mesclado por cima na leitura. "Restaurar padrão" apaga só o ajuste.

Só os campos listados em ``CAMPOS`` podem ser mudados pela tela, cada um com
tipo e limites, para a tela nunca gravar algo que quebre a análise.
Parâmetros calibrados (mercados, margem, blowout) ficam de fora: quem os
muda é ``nbastats calibrar``.
"""

from __future__ import annotations

import copy
import os
import re
from pathlib import Path
from typing import Any

import yaml

ARQUIVOS = {"site": "Site", "apostas": "Apostas", "alertas": "Alertas", "betaniag": "BetânIAG",
            "projecao": "Projeção e Ao Vivo", "matchup": "Matchups", "potencial": "Potenciais"}

# (arquivo, caminho, tipo, rótulo, ajuda, extras)
_C = [
    ("site", "nome", "texto", "Nome do site", "Aparece no topo, no login e na aba do navegador.", {"max": 30}),
    ("site", "subtitulo", "texto", "Subtítulo", "Frase curta no login.", {"max": 60}),
    ("site", "cor_destaque", "cor", "Cor de destaque", "Botões, abas ativas e valores positivos.", {}),
    ("site", "tema_padrao", "opcao", "Tema padrão", "Cada pessoa pode trocar no menu; isto vale para quem nunca escolheu.",
     {"opcoes": ["escuro", "claro", "sistema"]}),
    ("apostas", "valor_unidade", "numero", "Valor de 1 unidade", "Só para mostrar o lucro em dinheiro.",
     {"min": 0, "max": 100000}),
    ("apostas", "moeda", "texto", "Moeda", "Ex.: R$.", {"max": 5}),
    ("apostas", "unidades", "lista_numeros", "Unidades oferecidas", "Botões do registro de aposta.", {"min": 0.1, "max": 10}),
    ("apostas", "anular_se_nao_jogou", "sim_nao", "Anular se não jogou", "Como a maioria das casas: devolve a aposta.", {}),
    ("apostas", "etiquetas", "lista_textos", "Motivos (diário)", "Etiquetas oferecidas ao registrar.", {"max": 30}),
    ("apostas", "jogo_responsavel.limite_unidades_dia", "numero", "Limite de unidades por dia",
     "Ao passar, o site pede confirmação. 0 = sem limite.", {"min": 0, "max": 1000}),
    ("apostas", "jogo_responsavel.limite_unidades_semana", "numero", "Limite de unidades em 7 dias", "0 = sem limite.",
     {"min": 0, "max": 5000}),
    ("apostas", "jogo_responsavel.aviso_sequencia_perdas", "inteiro", "Aviso após derrotas seguidas", "0 = sem aviso.",
     {"min": 0, "max": 50}),
    ("apostas", "valor.edge_minimo", "numero", "Edge mínimo (página Valor)",
     "Nossa chance menos a chance da odd. 0,03 = 3 pontos percentuais.", {"min": 0, "max": 0.5}),
    ("alertas", "habilitado", "sim_nao", "Alertas no Telegram",
     "Precisa de NBASTATS_TELEGRAM_TOKEN e NBASTATS_TELEGRAM_CHAT no .env.", {}),
    ("alertas", "so_favoritos", "sim_nao", "Só favoritos", "Desligado: alerta de qualquer jogador.", {}),
    ("alertas", "ev_minimo", "numero", "Valor esperado mínimo", "Linha da casa com valor a partir disto (0,05 = +5%).",
     {"min": 0, "max": 1}),
    ("alertas", "status_alerta", "lista_opcoes", "Status que geram alerta", "",
     {"opcoes": ["Out", "Doubtful", "Questionable", "Probable"]}),
    ("alertas", "ao_vivo", "sim_nao", "Alertas durante os jogos", "Favorito a caminho de bater a linha e quem bateu.", {}),
    ("alertas", "ao_vivo_chance_min", "numero", "Ao vivo: chance mínima", "0,7 = 70%.", {"min": 0.5, "max": 0.99}),
    ("alertas", "resumo_top", "inteiro", "Oportunidades no resumo", "Quantas entram no resumo das 17h.", {"min": 1, "max": 20}),
    ("betaniag", "habilitado", "sim_nao", "BetânIAG ligado por padrão", "Cada pessoa ainda pode ligar/desligar no topo.", {}),
    ("betaniag", "unidades.habilitado", "sim_nao", "Mostrar unidade sugerida",
     "Só ligar depois de validar as faixas com a Calibração e as apostas (5i).", {}),
    ("betaniag", "validacao.minutos_antes_do_jogo", "inteiro", "Validação: relatório até X min antes", "",
     {"min": 0, "max": 600}),
    ("betaniag", "alertas.h2h_min_jogos", "inteiro", "H2H: mínimo de jogos", "Abaixo disso o H2H é só curiosidade.",
     {"min": 1, "max": 20}),
    ("betaniag", "destaques.min_media.pts", "numero", "Destaques: média mínima de pontos", "", {"min": 0, "max": 60}),
    ("betaniag", "destaques.min_media.reb", "numero", "Destaques: média mínima de rebotes", "", {"min": 0, "max": 30}),
    ("betaniag", "destaques.min_media.ast", "numero", "Destaques: média mínima de assistências", "", {"min": 0, "max": 30}),
    ("betaniag", "destaques.min_media.pra", "numero", "Destaques: média mínima de PRA", "", {"min": 0, "max": 80}),
    ("betaniag", "destaques.min_media.fg3m", "numero", "Destaques: média mínima de bolas de 3", "", {"min": 0, "max": 10}),
    ("projecao", "lavada.margem", "inteiro", "Lavada: diferença final", "Jogo decidido por isto ou mais conta como lavada.",
     {"min": 5, "max": 60}),
    ("projecao", "ao_vivo.peso_ao_vivo", "numero", "Ao Vivo: peso do ritmo do jogo",
     "0 = só a projeção pré-jogo; 1 = só o que está acontecendo.", {"min": 0, "max": 1}),
    ("projecao", "ao_vivo.blowout_margem", "inteiro", "Ao Vivo: margem de lavada no 4º quarto", "", {"min": 5, "max": 60}),
    ("projecao", "ao_vivo.faltas_limite", "inteiro", "Ao Vivo: faltas que reduzem minutos", "", {"min": 3, "max": 6}),
    ("matchup", "filtros.min_jogos", "inteiro", "Análise: mínimo de jogos na temporada", "", {"min": 1, "max": 40}),
    ("matchup", "filtros.min_minutos_l10", "numero", "Análise: mínimo de minutos (L10)", "", {"min": 0, "max": 40}),
    ("matchup", "lesoes.desfalque_min_minutos", "numero", "Desfalque: mínimo de minutos (L10)", "", {"min": 0, "max": 40}),
    ("potencial", "ultimos_jogos", "inteiro", "Potenciais: janela recente (jogos)", "", {"min": 3, "max": 30}),
    ("potencial", "filtros.min_jogos", "inteiro", "Potenciais: mínimo de jogos", "", {"min": 1, "max": 82}),
    ("potencial", "filtros.min_minutos", "numero", "Potenciais: mínimo de minutos", "", {"min": 0, "max": 48}),
    ("potencial", "filtros.max_anos_de_liga", "inteiro_ou_vazio", "Potenciais: máximo de anos de liga", "Vazio = sem limite.",
     {"min": 0, "max": 25}),
]
CAMPOS = {(a, c): {"arquivo": a, "caminho": c, "tipo": t, "rotulo": r, "ajuda": h, **x} for a, c, t, r, h, x in _C}
_COR = re.compile(r"^#[0-9a-fA-F]{6}$")


def pasta() -> Path:
    return Path(os.getenv("NBASTATS_AJUSTES", "data/ajustes"))


def _get(d: dict[str, Any], caminho: str) -> Any:
    for k in caminho.split("."):
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def _set(d: dict[str, Any], caminho: str, valor: Any) -> None:
    *ks, last = caminho.split(".")
    for k in ks:
        d = d.setdefault(k, {})
    d[last] = valor


def _del(d: dict[str, Any], caminho: str) -> None:
    ks = caminho.split(".")
    stack = [d]
    for k in ks[:-1]:
        if not isinstance(stack[-1].get(k), dict):
            return
        stack.append(stack[-1][k])
    stack[-1].pop(ks[-1], None)
    for i in range(len(ks) - 2, -1, -1):  # limpa dicionários que ficaram vazios
        if not stack[i + 1]:
            stack[i].pop(ks[i], None)


def _merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def lidos(arquivo: str) -> dict[str, Any]:
    p = pasta() / f"{arquivo}.yaml"
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.exists() else {}


def aplicar(arquivo: str, base: dict[str, Any]) -> dict[str, Any]:
    """``base`` (YAML de config/) com os ajustes da Administração por cima."""
    over = lidos(arquivo)
    return _merge(base, over) if over else base


def _gravar(arquivo: str, dados: dict[str, Any]) -> None:
    p = pasta() / f"{arquivo}.yaml"
    if not dados:
        p.unlink(missing_ok=True)
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text("# Ajustes feitos na Administração (por cima de config/). Apagar = voltar ao padrão.\n"
                   + yaml.safe_dump(dados, sort_keys=False, allow_unicode=True), encoding="utf-8")
    tmp.replace(p)


def validar(campo: dict[str, Any], valor: Any) -> Any:
    t, lo, hi = campo["tipo"], campo.get("min"), campo.get("max")

    def num(v: Any, inteiro: bool = False) -> float | int:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            try:
                v = float(str(v).replace(",", "."))
            except ValueError:
                raise ValueError(f"{campo['rotulo']}: precisa ser um número.")
        if inteiro:
            if float(v) != int(v):
                raise ValueError(f"{campo['rotulo']}: precisa ser inteiro.")
            v = int(v)
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            raise ValueError(f"{campo['rotulo']}: entre {lo} e {hi}.")
        return v

    if t == "sim_nao":
        if not isinstance(valor, bool):
            raise ValueError(f"{campo['rotulo']}: sim ou não.")
        return valor
    if t == "numero":
        return float(num(valor))
    if t == "inteiro":
        return num(valor, True)
    if t == "inteiro_ou_vazio":
        return None if valor in (None, "") else num(valor, True)
    if t == "texto":
        v = str(valor or "").strip()
        if not v or len(v) > (hi or 200):
            raise ValueError(f"{campo['rotulo']}: de 1 a {hi or 200} caracteres.")
        return v
    if t == "cor":
        if not isinstance(valor, str) or not _COR.match(valor):
            raise ValueError(f"{campo['rotulo']}: cor no formato #RRGGBB.")
        return valor.lower()
    if t == "opcao":
        if valor not in campo["opcoes"]:
            raise ValueError(f"{campo['rotulo']}: uma de {campo['opcoes']}.")
        return valor
    if t == "lista_opcoes":
        if not isinstance(valor, list) or any(v not in campo["opcoes"] for v in valor):
            raise ValueError(f"{campo['rotulo']}: só {campo['opcoes']}.")
        return list(dict.fromkeys(valor))
    if t == "lista_numeros":
        if not isinstance(valor, list) or not valor or len(valor) > 8:
            raise ValueError(f"{campo['rotulo']}: de 1 a 8 valores.")
        return sorted({float(num(v)) for v in valor})
    if t == "lista_textos":
        if not isinstance(valor, list) or len(valor) > 20:
            raise ValueError(f"{campo['rotulo']}: até 20 itens.")
        itens = [str(v).strip().replace(",", " ")[: hi or 30] for v in valor if str(v).strip()]
        return list(dict.fromkeys(itens))
    raise ValueError("tipo desconhecido")


def definir(arquivo: str, caminho: str, valor: Any) -> Any:
    campo = CAMPOS.get((arquivo, caminho))
    if campo is None:
        raise ValueError("Esse parâmetro não pode ser mudado pela tela.")
    v = validar(campo, valor)
    dados = lidos(arquivo)
    _set(dados, caminho, v)
    _gravar(arquivo, dados)
    return v


def restaurar(arquivo: str, caminho: str) -> None:
    if (arquivo, caminho) not in CAMPOS:
        raise ValueError("Esse parâmetro não pode ser mudado pela tela.")
    dados = lidos(arquivo)
    _del(dados, caminho)
    _gravar(arquivo, dados)


def painel(bases: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Seções para a tela: cada campo com o valor em uso, o padrão e se foi mudado."""
    out = []
    for arquivo, titulo in ARQUIVOS.items():
        over = lidos(arquivo)
        base = bases.get(arquivo, {})
        campos = []
        for (a, caminho), campo in CAMPOS.items():
            if a != arquivo:
                continue
            mudado = _has(over, caminho)
            padrao = _get(base, caminho)
            campos.append({**campo, "padrao": padrao, "valor": _get(over, caminho) if mudado else padrao,
                           "mudado": mudado})
        out.append({"arquivo": arquivo, "titulo": titulo, "campos": campos})
    return out


def _has(d: dict[str, Any], caminho: str) -> bool:
    """O caminho existe (mesmo com valor nulo, ex.: 'sem limite')."""
    *ks, last = caminho.split(".")
    for k in ks:
        if not isinstance(d, dict) or k not in d:
            return False
        d = d[k]
    return isinstance(d, dict) and last in d


SITE_PADRAO = {"nome": "NBA Stats", "subtitulo": "", "cor_destaque": "#22c55e", "tema_padrao": "escuro"}


def load_site(path: str | Path = Path("config/site.yaml")) -> dict[str, Any]:
    """Identidade do site (nome, subtítulo, cor, tema), com os ajustes por cima."""
    p = Path(path)
    data = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.exists() else {}
    return aplicar("site", {**SITE_PADRAO, **data})
