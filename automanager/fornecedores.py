"""Chassis e motores que ninguém desenvolve (fornecedores, categorias sem desenvolvimento) mudam a cada temporada.

regras.evolucao_fornecedores (ver docs/DATABASE.md):
- todo ano: atualização pequena, de -variacao_anual a +variacao_anual pontos em cada atributo;
- com chance prob_novo_modelo (~1 a cada 4 anos): modelo novo, de novo_modelo[0] a novo_modelo[1] pontos;
- reversão: a peça é puxada `reversao` da distância até o nível médio inicial das peças da categoria
  (o nível da database se mantém; a ordem entre os fornecedores muda);
- o preço por corrida acompanha a mudança do nível (contratos já assinados não mudam).
Uma grande mudança de regulamento obriga modelo novo de chassis. Limite de desenvolvimento em vigor: sem perda
e no máximo os pontos permitidos.
Peças que uma equipe desenvolve e motores de fabricante de categorias com desenvolvimento (que evoluem com
verba própria, desenvolvimento.evoluir_fabricantes) ficam de fora.
"""
import re

from . import regulamento, state
from .db import ATRIBUTOS_CHASSIS
from .state import noticia
from .util import clamp

PADRAO = {"ativa": True, "variacao_anual": 2, "prob_novo_modelo": 0.25, "novo_modelo": [-3, 8], "reversao": 0.2}


def cfg(categoria):
    return dict(PADRAO, **(categoria["regras"].get("evolucao_fornecedores") or {}))


def _nivel(ent, parte):
    if parte == "chassis":
        v = [ent["atributos"].get(k, 0) for k in ATRIBUTOS_CHASSIS]
        return sum(v) / len(v)
    return float(ent.get("potencia", 0))


def pecas(st, cid, parte):
    """Peças da categoria que evoluem por aqui."""
    c = st["categorias"][cid]
    dev = c["categoria"].get("desenvolvimento") or {}
    regras = c["categoria"]["regras"]
    out = []
    if parte == "chassis":
        for ch in c["chassis"].values():
            dono = ch.get("equipe")
            if dono and dev.get("chassis") and regras.get("desenvolvimento_chassis_por_equipe"):
                continue                                  # a equipe desenvolve
            if not ch.get("atributos"):
                continue
            out.append(ch)
    else:
        for m in c["motores"].values():
            fab = m.get("fabricante") or {}
            if fab.get("tipo") == "fabricante" and dev.get("motor"):
                continue                                  # evoluir_fabricantes (verba própria)
            if fab.get("tipo") == "equipe" and dev.get("motor") and state.pode_desenvolver_motor(st, cid, fab.get("equipe")):
                continue
            out.append(m)
    return out


def _referencia(st, cid, parte):
    c = st["categorias"][cid]
    ref = c.setdefault("evolucao_fornecedores", {}).setdefault("referencia", {})
    if parte not in ref:
        ps = pecas(st, cid, parte)
        ref[parte] = round(sum(_nivel(e, parte) for e in ps) / len(ps), 2) if ps else None
    return ref[parte]


def iniciar(st):
    """Guarda o nível de referência (o da database) no começo do jogo."""
    for cid in st["categorias"]:
        for parte in ("chassis", "motor"):
            _referencia(st, cid, parte)


def evoluir(st, rng):
    """Virada de temporada (st["ano"] já é o ano novo)."""
    yy = f"{st['ano'] % 100:02d}"
    for cid, c in st["categorias"].items():
        b = cfg(c["categoria"])
        if not b["ativa"]:
            continue
        for parte in ("chassis", "motor"):
            ref = _referencia(st, cid, parte)
            lim = regulamento.limite(st, cid, parte) if regulamento.carro_mantido(st, cid, parte, st["ano"]) else None
            forcar = parte == "chassis" and regulamento.grande_mudanca(st, cid, st["ano"])
            for ent in pecas(st, cid, parte):
                antes = _nivel(ent, parte)
                novo_modelo = forcar or rng.random() < b["prob_novo_modelo"]
                faixa = [int(x) for x in b["novo_modelo"]] if novo_modelo else \
                    [-int(b["variacao_anual"]), int(b["variacao_anual"])]
                # reversão ao nível da database; desconta também a média esperada dos modelos novos, para o
                # nível da categoria não subir sozinho com os anos (a ordem entre os fornecedores é que muda)
                deriva = b["prob_novo_modelo"] * sum(int(x) for x in b["novo_modelo"]) / 2
                puxa = b["reversao"] * ((ref if ref is not None else antes) - antes) - deriva
                attrs = ATRIBUTOS_CHASSIS if parte == "chassis" else ("potencia",)
                for k in attrs:
                    atual = ent["atributos"][k] if parte == "chassis" else ent["potencia"]
                    d = rng.randint(*faixa) + puxa
                    if lim is not None:
                        d = clamp(d, 0, lim)                  # limite em vigor: sem perda, ganho limitado
                    v = int(round(clamp(atual + d, 1, 99)))
                    if parte == "chassis":
                        ent["atributos"][k] = v
                    else:
                        ent["potencia"] = v
                depois = _nivel(ent, parte)
                if round(depois) == round(antes) and not novo_modelo:
                    continue
                if ent.get("contrato") and antes > 0:
                    ent["contrato"]["valor_por_corrida"] = round(ent["contrato"]["valor_por_corrida"] * depois / antes, -2)
                if novo_modelo:
                    ent["nome"] = re.sub(r"(?<=\D)\d{2}$", yy, ent["nome"])     # "Marlin M26" → "Marlin M28"
                    txt = f"{ent['nome']}: modelo novo para {st['ano']} (nível {antes:.0f} → {depois:.0f})."
                else:
                    txt = f"{ent['nome']}: atualização para {st['ano']} (nível {antes:.0f} → {depois:.0f})."
                noticia(st, txt, cid, "desenvolvimento")
