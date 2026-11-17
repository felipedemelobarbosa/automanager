"""Mudanças de regulamento ao longo das temporadas (categoria.regulamento, ver docs/DATABASE.md).

No meio da temporada (semana_anuncio) a categoria sorteia as regras da temporada seguinte e anuncia:
- grande mudança: os chassis perdem mais (perda extra na manutenção) e a importância do carro sobe;
  nas temporadas sem grande mudança, a importância do carro volta aos poucos ao valor da database;
- limite de desenvolvimento de uma parte (chassis ou motor) por algumas temporadas: congelado (0 ponto) ou com
  um máximo de pontos ganhos por atributo em cada temporada;
- ajuste pequeno na importância do carro (± ajuste_importancia).
Tudo é aplicado na virada da temporada. Desligado por padrão (temporadas importadas); a database de exemplo liga.
Referência real (F1): grandes mudanças em 1989, 1994-95, 1998, 2009, 2014, 2017, 2022 e 2026 (~1 a cada 4 anos);
motor congelado em 2007-2014 e 2022-2025.
"""
from .state import noticia
from .util import clamp

PADRAO = {"ativo": False, "semana_anuncio": 30,
          "prob_grande_mudanca": 0.2, "perda_grande_mudanca": [0.15, 0.30], "aumento_importancia_carro": [0.05, 0.10],
          "convergencia_por_temporada": 0.02,
          "prob_limite_desenvolvimento": 0.15, "limite_duracao": [2, 4], "prob_congelamento": 0.5,
          "limite_pontos_por_temporada": [2, 5],
          "prob_ajuste_importancia": 0.15, "ajuste_importancia": 0.03,
          "importancia_carro_min": 0.3, "importancia_carro_max": 0.8}

NOME_PARTE = {"chassis": "chassis", "motor": "motor"}


def cfg(categoria):
    return dict(PADRAO, **(categoria.get("regulamento") or {}))


def estado(c):
    r = c.setdefault("regulamento", {})
    r.setdefault("importancia_base", c["categoria"]["regras"].get("importancia_carro", 0.5))
    r.setdefault("limites", [])
    r.setdefault("historico", [])
    return r


def limite(st, cid, parte, ano=None):
    """Pontos por atributo permitidos na temporada `ano` (0 = congelado) ou None (sem limite)."""
    ano = st["ano"] if ano is None else ano
    r = st["categorias"][cid].get("regulamento") or {}
    anunciados = [m for m in (r.get("anuncio") or {}).get("mudancas", []) if m["tipo"] == "limite"]
    for lim in r.get("limites", []) + anunciados:
        if lim["parte"] == parte and lim["de"] <= ano <= lim["ate"]:
            return lim["pontos"]
    return None


def carro_mantido(st, cid, parte, ano_novo=None):
    """O limite vale na temporada atual e na próxima: o carro passa de uma para a outra sem perda e não há
    projeto novo (como no motor congelado da F1)."""
    ano_novo = st["ano"] + 1 if ano_novo is None else ano_novo
    return limite(st, cid, parte, ano_novo - 1) is not None and limite(st, cid, parte, ano_novo) is not None


def perda_extra(st, cid, parte, ano_novo=None):
    """Perda extra do chassis na passagem para `ano_novo` (grande mudança anunciada para esse ano)."""
    if parte != "chassis":
        return 0.0
    ano_novo = st["ano"] + 1 if ano_novo is None else ano_novo
    an = (st["categorias"][cid].get("regulamento") or {}).get("anuncio") or {}
    if an.get("ano") != ano_novo:
        return 0.0
    return sum(m.get("perda", 0.0) for m in an.get("mudancas", []) if m["tipo"] == "grande")


def grande_mudanca(st, cid, ano_novo):
    an = (st["categorias"][cid].get("regulamento") or {}).get("anuncio") or {}
    return an.get("ano") == ano_novo and any(m["tipo"] == "grande" for m in an.get("mudancas", []))


def partes_desenvolvidas(st, cid):
    """Partes que alguma equipe da categoria desenvolve (só elas podem ter limite)."""
    c = st["categorias"][cid]
    dev = c["categoria"].get("desenvolvimento") or {}
    regras = c["categoria"]["regras"]
    out = []
    if dev.get("chassis") and regras.get("desenvolvimento_chassis_por_equipe"):
        out.append("chassis")
    if dev.get("motor") and (regras.get("desenvolvimento_motor_por_equipe") or
                             any((m.get("fabricante") or {}).get("tipo") == "fabricante" for m in c["motores"].values())):
        out.append("motor")
    return out


def _texto_limite(parte, pontos, de, ate):
    if pontos == 0:
        return f"desenvolvimento do {NOME_PARTE[parte]} congelado de {de} a {ate}"
    return f"desenvolvimento do {NOME_PARTE[parte]} limitado a {pontos} pontos por atributo por temporada de {de} a {ate}"


# ---------------------------------------------------------------- anúncio (meio da temporada)
def semanal(st, rng):
    """Na semana do anúncio, sorteia as regras da próxima temporada. Retorna as categorias com anúncio."""
    anunciadas = []
    for cid, c in st["categorias"].items():
        b = cfg(c["categoria"])
        if not b["ativo"] or st["semana"] != int(b["semana_anuncio"]):
            continue
        r = estado(c)
        prox = st["ano"] + 1
        if (r.get("anuncio") or {}).get("ano") == prox:
            continue
        mudancas = []
        carro = c["categoria"]["regras"].get("importancia_carro", 0.5)
        if rng.random() < b["prob_grande_mudanca"] and not carro_mantido(st, cid, "chassis", prox):
            novo = round(clamp(carro + rng.uniform(*b["aumento_importancia_carro"]),
                               b["importancia_carro_min"], b["importancia_carro_max"]), 2)
            if "chassis" in partes_desenvolvidas(st, cid):
                perda = round(rng.uniform(*b["perda_grande_mudanca"]), 2)
                texto = (f"grande mudança nas regras técnicas: os chassis perdem mais {perda * 100:.0f}% na passagem "
                         f"para {prox} (a manutenção do carro rende menos) e o carro passa a pesar mais "
                         f"(importância do carro {carro:.2f} → {novo:.2f})")
            else:
                perda = 0.0                       # chassis de fornecedor: todos lançam modelo novo
                texto = (f"grande mudança nas regras técnicas: os fornecedores lançam chassis novos para {prox} e o "
                         f"carro passa a pesar mais (importância do carro {carro:.2f} → {novo:.2f})")
            mudancas.append({"tipo": "grande", "perda": perda, "importancia_carro": novo})
        elif rng.random() < b["prob_ajuste_importancia"]:
            d = b["ajuste_importancia"] * rng.choice([-1, 1])
            novo = round(clamp(carro + d, b["importancia_carro_min"], b["importancia_carro_max"]), 2)
            texto = None
            if novo != round(carro, 2):
                mudancas.append({"tipo": "importancia", "importancia_carro": novo})
                texto = f"ajuste nas regras: importância do carro {carro:.2f} → {novo:.2f}"
        else:
            texto = None
        textos = [texto] if texto else []
        livres = [p for p in partes_desenvolvidas(st, cid) if limite(st, cid, p, prox) is None]
        if livres and rng.random() < b["prob_limite_desenvolvimento"]:
            parte = rng.choice(livres)
            dur = rng.randint(*[int(x) for x in b["limite_duracao"]])
            pontos = 0 if rng.random() < b["prob_congelamento"] else \
                rng.randint(*[int(x) for x in b["limite_pontos_por_temporada"]])
            lim = {"parte": parte, "pontos": pontos, "de": prox, "ate": prox + dur - 1}
            mudancas.append(dict(lim, tipo="limite"))
            textos.append(_texto_limite(parte, pontos, lim["de"], lim["ate"]))
        r["anuncio"] = {"ano": prox, "mudancas": mudancas}
        for txt in textos:
            frase = f"REGULAMENTO {prox}: {txt}."
            r["historico"].append({"ano": prox, "anunciado_em": st["ano"], "texto": frase})
            noticia(st, frase, cid, "regulamento")
        if mudancas:
            anunciadas.append(cid)
    return anunciadas


# ---------------------------------------------------------------- virada de temporada
def virada(st, cid):
    """Aplica o que foi anunciado para a temporada que começa (st["ano"] já é o ano novo)."""
    c = st["categorias"][cid]
    b = cfg(c["categoria"])
    if not b["ativo"] and not c.get("regulamento"):
        return
    r = estado(c)
    regras = c["categoria"]["regras"]
    an = r.get("anuncio") or {}
    mudancas = an.get("mudancas", []) if an.get("ano") == st["ano"] else []
    carro = regras.get("importancia_carro", 0.5)
    grande = any(m["tipo"] == "grande" for m in mudancas)
    for m in mudancas:
        if "importancia_carro" in m:
            carro = m["importancia_carro"]
        if m["tipo"] == "limite":
            r["limites"].append({k: m[k] for k in ("parte", "pontos", "de", "ate")})
    if not grande and b["ativo"]:
        base = r["importancia_base"]
        passo = min(abs(carro - base), b["convergencia_por_temporada"])
        carro += passo if carro < base else -passo
    regras["importancia_carro"] = round(carro, 3)
    regras["importancia_piloto"] = round(1 - carro, 3)
    for lim in r["limites"]:
        if lim["ate"] == st["ano"] - 1:
            noticia(st, f"REGULAMENTO {st['ano']}: termina o limite de desenvolvimento do {NOME_PARTE[lim['parte']]}.",
                    cid, "regulamento")
    r["limites"] = [lim for lim in r["limites"] if lim["ate"] >= st["ano"]]
    if an.get("ano") == st["ano"]:
        r.pop("anuncio", None)


def descricao_atual(st, cid):
    """Linhas para as telas: regras em vigor e anunciadas."""
    c = st["categorias"][cid]
    r = c.get("regulamento") or {}
    regras = c["categoria"]["regras"]
    out = [f"Importância do carro {regras.get('importancia_carro', 0):.2f} / piloto {regras.get('importancia_piloto', 0):.2f}."]
    for lim in r.get("limites", []):
        out.append(_texto_limite(lim["parte"], lim["pontos"], lim["de"], lim["ate"]).capitalize() + ".")
    an = r.get("anuncio")
    if an:
        out += [h["texto"] for h in r.get("historico", []) if h["ano"] == an["ano"]]
    return out
