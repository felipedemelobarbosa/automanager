"""Desenvolvimento do chassis e do motor (só se a categoria permitir).

- Carro desta temporada: cada ponto custa dinheiro e vale na hora.
- Carro da próxima temporada: OU "manutencao" (o carro atual, como estiver no fim da temporada, com perda
  de `perda_manutencao` em cada atributo, sem investimento) OU projeto "novo" (parte do zero e recebe
  investimento ponto a ponto).
- Custo de +1 ponto: fixo até `limite_custo_fixo`; acima disso, progressivamente mais caro.
- Equipes do PC investem a verba semanal planejada pela economia (economia.planejar_temporada).
"""
import re

from . import state, regulamento
from .db import ATRIBUTOS_CHASSIS
from .state import noticia

PARTES = ("chassis", "motor")
MAXIMO = 100


def config(st, cid):
    return st["categorias"][cid]["categoria"].get("desenvolvimento")


def pode(st, cid, eq, parte):
    """A equipe pode desenvolver esta parte? (regras da categoria + parte própria)."""
    c = st["categorias"][cid]
    cfg = config(st, cid)
    if not cfg or not cfg.get(parte):
        return False
    info = eq.get(parte) or {}
    if info.get("origem") != "proprio" or not info.get("id"):
        return False
    if parte == "chassis":
        return bool(c["categoria"]["regras"].get("desenvolvimento_chassis_por_equipe"))
    return state.pode_desenvolver_motor(st, cid, eq["id"])


def cliente(st, cid, eq, parte):
    """Equipe que compra o chassis numa categoria em que poderia desenvolver o próprio (fontes com 'proprio')."""
    if parte != "chassis":
        return False
    c = st["categorias"][cid]
    cfg = config(st, cid)
    if not cfg or not cfg.get("chassis") or not c["categoria"]["regras"].get("desenvolvimento_chassis_por_equipe"):
        return False
    if "proprio" not in state.fontes_chassis(c["categoria"]):
        return False
    return (eq.get("chassis") or {}).get("origem") != "proprio"


def cliente_pode_voltar(st, cid, eq, parte):
    """Cliente cujo contrato termina nesta temporada (e sem contrato para a próxima) pode fazer o próprio chassis."""
    from . import contratos
    if not cliente(st, cid, eq, parte) or eq.get(f"{parte}_futuro"):
        return False
    ct = (eq.get(parte) or {}).get("contrato")
    return not ct or contratos.termina_nesta_temporada(ct, contratos.corridas_restantes(st, cid))


def pode_projeto(st, cid, eq, parte):
    """A equipe tem carro da próxima temporada para projetar? (quem já comprou a peça para a próxima, não)."""
    if eq.get(f"{parte}_futuro"):
        return False
    return pode(st, cid, eq, parte) or cliente_pode_voltar(st, cid, eq, parte)


def atributos_da_parte(parte):
    return list(ATRIBUTOS_CHASSIS) if parte == "chassis" else ["potencia"]


def valores_atuais(st, cid, eq, parte):
    ent = _entidade(st, cid, eq, parte)
    if not ent:
        return {}
    if parte == "chassis":
        return dict(ent["atributos"])
    return {"potencia": ent.get("potencia", 0)}


def _entidade(st, cid, eq, parte):
    return state.chassis_da_equipe(st, cid, eq) if parte == "chassis" else state.motor_da_equipe(st, cid, eq)


# ---------------------------------------------------------------- custo
def custo_ponto(cfg_parte, valor):
    """Custo para ir de `valor` para `valor + 1`."""
    alvo = valor + 1
    base = cfg_parte["custo_por_ponto"]
    limite = cfg_parte.get("limite_custo_fixo", 50)
    if alvo <= limite:
        return base
    escala = cfg_parte.get("escala_progressiva", 15) or 15
    return base * (1 + ((alvo - limite) / escala) ** 2)


def custo_ate(cfg_parte, de, ate):
    return sum(custo_ponto(cfg_parte, v) for v in range(int(de), int(ate)))


def custo_alvos(st, cid, parte, atuais, alvos):
    cfg = config(st, cid)[parte]
    return sum(custo_ate(cfg, atuais[k], alvos[k]) for k in alvos if alvos[k] > atuais.get(k, 0))


def _pagar(eq, valor):
    eq["financas"]["caixa"] -= valor
    eq["financas"]["ano"]["despesas"]["desenvolvimento"] = \
        eq["financas"]["ano"]["despesas"].get("desenvolvimento", 0.0) + valor


# ---------------------------------------------------------------- regulamento
def _ganhos(eq, ano):
    g = eq.get("ganho_dev")
    if not g or g.get("ano") != ano:
        g = eq["ganho_dev"] = {"ano": ano}
    return g


def tetos_atual(st, cid, eq, parte):
    """Valor máximo de cada atributo nesta temporada pelo regulamento (limite de pontos ganhos) ou None."""
    lim = regulamento.limite(st, cid, parte)
    if lim is None:
        return None
    g = eq.get("ganho_dev") or {}
    ganhos = g.get(parte, {}) if g.get("ano") == st["ano"] else {}   # só lê: não mexe na equipe
    atuais = valores_atuais(st, cid, eq, parte)
    return {k: min(MAXIMO, v + max(0, lim - ganhos.get(k, 0))) for k, v in atuais.items()}


def projeto_permitido(st, cid, parte, ano_novo=None):
    """Com o limite valendo nesta temporada e na próxima, o carro passa sem perda e não há projeto novo."""
    return not regulamento.carro_mantido(st, cid, parte, ano_novo)


def perda_manutencao(st, cid, parte, ano_novo=None):
    """Perda do carro atual na passagem para a próxima temporada (com o regulamento anunciado)."""
    if regulamento.carro_mantido(st, cid, parte, ano_novo):
        return 0.0
    return min(1.0, config(st, cid).get("perda_manutencao", 0.3) + regulamento.perda_extra(st, cid, parte, ano_novo))


# ---------------------------------------------------------------- carro desta temporada
def investir_atual(st, cid, eq, parte, alvos):
    """alvos: {atributo: novo valor}. Retorna o custo. Levanta ValueError se não houver caixa."""
    if not pode(st, cid, eq, parte):
        raise ValueError("Esta equipe não pode desenvolver esta parte.")
    atuais = valores_atuais(st, cid, eq, parte)
    alvos = {k: min(MAXIMO, int(v)) for k, v in alvos.items() if int(v) > atuais.get(k, 0)}
    tetos = tetos_atual(st, cid, eq, parte)
    if tetos is not None and alvos:
        lim = regulamento.limite(st, cid, parte)
        if lim == 0:
            raise ValueError(f"Regulamento: o desenvolvimento do {parte} está congelado nesta temporada.")
        if any(v > tetos[k] for k, v in alvos.items()):
            from .db import NOMES_ATRIBUTOS
            raise ValueError(f"Regulamento: no máximo {lim} pontos por atributo nesta temporada (ainda é possível: "
                             + ", ".join(f"{NOMES_ATRIBUTOS.get(k, k)} +{tetos[k] - atuais[k]}" for k in alvos) + ").")
    custo = custo_alvos(st, cid, parte, atuais, alvos)
    if custo > eq["financas"]["caixa"]:
        raise ValueError("Caixa insuficiente.")
    ent = _entidade(st, cid, eq, parte)
    ganhos = _ganhos(eq, st["ano"]).setdefault(parte, {})
    for k, v in alvos.items():
        ganhos[k] = ganhos.get(k, 0) + v - atuais[k]
        if parte == "chassis":
            ent["atributos"][k] = v
        else:
            ent["potencia"] = v
    _pagar(eq, custo)
    return custo


# ---------------------------------------------------------------- carro da próxima temporada
def projeto(eq, parte):
    p = eq.setdefault("projeto", {})
    return p.setdefault(parte, {"modo": "manutencao", "investido": {}})


def base_projeto(st, cid, eq, parte, modo=None, ano_novo=None):
    modo = modo or projeto(eq, parte)["modo"]
    atuais = valores_atuais(st, cid, eq, parte)
    if (eq.get(parte) or {}).get("origem") != "proprio":
        return {k: 0 for k in atributos_da_parte(parte)}          # cliente: chassis próprio só do zero
    if modo == "novo" and projeto_permitido(st, cid, parte, ano_novo):
        return {k: 0 for k in atributos_da_parte(parte)}
    perda = perda_manutencao(st, cid, parte, ano_novo)
    return {k: int(atuais.get(k, 0) * (1 - perda)) for k in atributos_da_parte(parte)}


def valores_projeto(st, cid, eq, parte, ano_novo=None):
    base = base_projeto(st, cid, eq, parte, ano_novo=ano_novo)
    if (eq.get(parte) or {}).get("origem") != "proprio" and projeto(eq, parte)["modo"] == "novo":
        inv = projeto(eq, parte)["investido"]
        return {k: min(MAXIMO, base[k] + inv.get(k, 0)) for k in base}
    if projeto(eq, parte)["modo"] != "novo" or not projeto_permitido(st, cid, parte, ano_novo):
        return base                                   # manutenção: carro atual com a perda, sem investimento
    inv = projeto(eq, parte)["investido"]
    return {k: min(MAXIMO, base[k] + inv.get(k, 0)) for k in base}


def mudar_modo(eq, parte, modo):
    """Troca entre 'novo' e 'manutencao'. O que já foi investido no projeto é perdido."""
    p = projeto(eq, parte)
    if p["modo"] != modo:
        p["modo"] = modo
        p["investido"] = {}


def investir_projeto(st, cid, eq, parte, alvos):
    if eq.get(f"{parte}_futuro"):
        raise ValueError(f"A equipe já comprou o {parte} da próxima temporada no Mercado.")
    if not pode_projeto(st, cid, eq, parte):
        raise ValueError("Esta equipe não pode desenvolver esta parte.")
    if not projeto_permitido(st, cid, parte):
        raise ValueError(f"Regulamento: o {parte} atual passa para a próxima temporada sem perda e não há projeto novo.")
    if projeto(eq, parte)["modo"] != "novo":
        raise ValueError("Na manutenção não há investimento no carro da próxima temporada: escolha o projeto novo.")
    atuais = valores_projeto(st, cid, eq, parte)
    alvos = {k: min(MAXIMO, int(v)) for k, v in alvos.items() if int(v) > atuais.get(k, 0)}
    custo = custo_alvos(st, cid, parte, atuais, alvos)
    if custo > eq["financas"]["caixa"]:
        raise ValueError("Caixa insuficiente.")
    inv = projeto(eq, parte)["investido"]
    for k, v in alvos.items():
        inv[k] = inv.get(k, 0) + (v - atuais[k])
    _pagar(eq, custo)
    return custo


def aplicar_projetos(st, ano_novo):
    """Virada de temporada: o projeto vira o carro atual."""
    yy_ant, yy = f"{(ano_novo - 1) % 100:02d}", f"{ano_novo % 100:02d}"
    for cid, c in st["categorias"].items():
        if not config(st, cid):
            continue
        for eq in c["equipes"].values():
            if not eq.get("ativa"):
                continue
            for parte in PARTES:
                if eq.get(f"{parte}_futuro"):
                    (eq.get("projeto") or {}).pop(parte, None)      # comprou no Mercado: vale o contrato
                    continue
                if cliente(st, cid, eq, parte):
                    if projeto(eq, parte)["modo"] == "novo":
                        _virar_proprio(st, cid, eq, parte, valores_projeto(st, cid, eq, parte, ano_novo), yy)
                    continue
                if not pode(st, cid, eq, parte):
                    continue
                novos = valores_projeto(st, cid, eq, parte, ano_novo)
                modo = projeto(eq, parte)["modo"] if projeto_permitido(st, cid, parte, ano_novo) else "manutencao"
                ent = _entidade(st, cid, eq, parte)
                if parte == "chassis":
                    ent["atributos"].update(novos)
                else:
                    ent["potencia"] = novos["potencia"]
                ent["nome"] = re.sub(rf"{yy_ant}$", yy, ent["nome"])
                eq["projeto"][parte] = {"modo": "manutencao", "investido": {}}
                if parte == "chassis":
                    txt = (f"{eq['nome']} apresenta o {ent['nome']}, projeto totalmente novo." if modo == "novo"
                           else f"{eq['nome']} vai de {ent['nome']}, evolução do carro anterior.")
                    noticia(st, txt, cid, "desenvolvimento")


def _virar_proprio(st, cid, eq, parte, valores, yy):
    """Cliente que fez projeto novo: passa a correr com o próprio chassis (o contrato de compra terminou)."""
    c = st["categorias"][cid]
    chid = f"ch_{eq['id']}"
    ent = c["chassis"].get(chid)
    if not ent or ent.get("equipe") != eq["id"]:
        ent = c["chassis"][chid] = {"id": chid, "nacionalidade": eq.get("nacionalidade", ""), "equipe": eq["id"],
                                    "atributos": {}, "contrato": None}
    ent["nome"] = f"{eq['nome'].split()[0]} C{yy}"
    ent["atributos"] = {k: int(valores.get(k, 0)) for k in ATRIBUTOS_CHASSIS}
    eq["chassis"] = {"id": chid, "origem": "proprio"}
    eq["projeto"][parte] = {"modo": "manutencao", "investido": {}}
    noticia(st, f"{eq['nome']} volta a ter chassis próprio: {ent['nome']}, projeto totalmente novo.", cid,
            "desenvolvimento")


def construir_do_zero(st, cid, eq, parte, verba):
    """Equipe nova sem carro: cria a peça do zero e investe a verba (ponto a ponto no atributo mais fraco)."""
    c = st["categorias"][cid]
    ano2 = f"{st['ano'] % 100:02d}"
    if parte == "chassis":
        chid = (eq.get("chassis") or {}).get("id") or f"ch_{eq['id']}"
        c["chassis"][chid] = {"id": chid, "nome": f"{eq['nome'].split()[0]} C{ano2}",
                              "nacionalidade": eq.get("nacionalidade", ""), "equipe": eq["id"],
                              "atributos": {k: 0 for k in ATRIBUTOS_CHASSIS}, "contrato": None}
        eq["chassis"] = {"id": chid, "origem": "proprio"}
    else:
        mid = (eq.get("motor") or {}).get("id") or f"mot_{eq['id']}"
        c["motores"][mid] = {"id": mid, "nome": f"{eq['nome'].split()[0]} M{ano2}",
                             "nacionalidade": eq.get("nacionalidade", ""), "potencia": 0,
                             "fabricante": {"tipo": "equipe", "equipe": eq["id"]},
                             "exclusividade": {"exclusivo": False, "equipe": None}, "contrato": None}
        eq["motor"] = {"id": mid, "origem": "proprio"}
    return _gastar_guloso(st, cid, eq, parte, verba, False)


# ---------------------------------------------------------------- IA
def _gastar_guloso(st, cid, eq, parte, verba, alvo_projeto):
    """Investe ponto a ponto no atributo mais fraco enquanto houver verba."""
    cfg = config(st, cid)[parte]
    if alvo_projeto and not projeto_permitido(st, cid, parte):
        return 0.0
    valores = valores_projeto(st, cid, eq, parte) if alvo_projeto else valores_atuais(st, cid, eq, parte)
    if not valores:
        return 0.0
    tetos = None if alvo_projeto else tetos_atual(st, cid, eq, parte)
    teto = {k: (tetos[k] if tetos else MAXIMO) for k in valores}
    novos = dict(valores)
    gasto = 0.0
    while True:
        abertos = [a for a in novos if novos[a] < teto[a]]
        if not abertos:
            break
        k = min(abertos, key=lambda a: novos[a])
        c = custo_ponto(cfg, novos[k])
        if gasto + c > verba:
            break
        gasto += c
        novos[k] += 1
    if gasto <= 0:
        return 0.0
    alvos = {k: v for k, v in novos.items() if v > valores[k]}
    try:
        return investir_projeto(st, cid, eq, parte, alvos) if alvo_projeto else investir_atual(st, cid, eq, parte, alvos)
    except ValueError:
        return 0.0


def _estimar(cfg, base, verba):
    """Média dos atributos após gastar `verba` ponto a ponto no atributo mais fraco."""
    v = dict(base)
    gasto = 0.0
    while v:
        k = min(v, key=lambda a: v[a])
        c = custo_ponto(cfg, v[k])
        if v[k] >= MAXIMO or gasto + c > verba:
            break
        gasto += c
        v[k] += 1
    return sum(v.values()) / max(1, len(v))


def _escolher_modo_ia(st, cid, eq, parte, verba_anual):
    """Compara: (a) manutenção – toda a verba no carro atual, que vira o do ano seguinte com a perda;
    (b) projeto novo – a maior parte da verba no carro feito do zero. Fica com o melhor resultado."""
    if not projeto_permitido(st, cid, parte):
        mudar_modo(eq, parte, "manutencao")
        return
    cfg = config(st, cid)[parte]
    perda = perda_manutencao(st, cid, parte)
    atuais = valores_atuais(st, cid, eq, parte)
    if regulamento.limite(st, cid, parte) is not None:
        manut = sum(atuais.values()) / max(1, len(atuais)) * (1 - perda)   # pouco a ganhar no carro atual
    else:
        manut = _estimar(cfg, atuais, verba_anual) * (1 - perda)
    novo = _estimar(cfg, {k: 0 for k in atributos_da_parte(parte)}, verba_anual * FRACAO_PROJETO_NOVO)
    mudar_modo(eq, parte, "novo" if novo > manut else "manutencao")


FRACAO_PROJETO_NOVO = 0.8


def nivel_estimado_proxima(st, cid, eq, parte, verba_anual):
    """Nível médio esperado do carro próprio da próxima temporada com a verba anual (manutenção ou projeto novo,
    o melhor); para um cliente, só o projeto novo do zero."""
    cfg = config(st, cid)[parte]
    novo = _estimar(cfg, {k: 0 for k in atributos_da_parte(parte)}, verba_anual * FRACAO_PROJETO_NOVO) \
        if projeto_permitido(st, cid, parte) else 0.0
    if not pode(st, cid, eq, parte):
        return novo
    atuais = valores_atuais(st, cid, eq, parte)
    manut = _estimar(cfg, atuais, verba_anual) * (1 - perda_manutencao(st, cid, parte))
    return max(manut, novo)


def reavaliar_ia(st, cid):
    """Regulamento anunciado: equipes do PC revêem a escolha entre manutenção e projeto novo (só trocam de
    manutenção para projeto novo, ou saem do projeto se ele deixou de ser permitido)."""
    humanas = state.humanas(st)
    c = st["categorias"][cid]
    for eq in c["equipes"].values():
        if not eq.get("ativa") or (cid, eq["id"]) in humanas:
            continue
        pesos = _pesos_ia(st, cid, eq)
        for parte in pesos:
            if eq.get(f"{parte}_futuro"):
                continue
            if not projeto_permitido(st, cid, parte):
                mudar_modo(eq, parte, "manutencao")
            elif projeto(eq, parte)["modo"] == "manutencao":
                restante = eq.get("verba_semanal_dev", 0.0) * max(1, 52 - st["semana"]) * pesos[parte]
                _escolher_modo_ia(st, cid, eq, parte, restante)


def rotina_ia(st, semana_da_temporada):
    humanas = state.humanas(st)
    for cid, c in st["categorias"].items():
        cfg = config(st, cid)
        if not cfg:
            continue
        for eq in c["equipes"].values():
            if not eq.get("ativa") or (cid, eq["id"]) in humanas:
                continue
            partes = [p for p in PARTES if pode(st, cid, eq, p) or
                      (cliente(st, cid, eq, p) and projeto(eq, p)["modo"] == "novo" and pode_projeto(st, cid, eq, p))]
            if not partes:
                continue
            verba = min(eq.get("verba_semanal_dev", 0.0), max(0.0, eq["financas"]["caixa"]))
            pesos = {"chassis": 0.7, "motor": 0.3} if len(partes) == 2 else {partes[0]: 1.0}
            # a verba que não deu para gastar na semana (ponto caro) fica guardada até o fim da temporada
            saldo = eq.setdefault("saldo_dev", {})
            if semana_da_temporada == 1:
                saldo.clear()
            for parte in partes:
                proprio = pode(st, cid, eq, parte)
                if proprio and (semana_da_temporada == 1 or "projeto" not in eq or parte not in eq["projeto"]):
                    _escolher_modo_ia(st, cid, eq, parte, verba * 52 * pesos[parte])
                if not proprio:
                    alvos = (("projeto", 1.0, True),)          # cliente construindo o próprio chassis
                elif not pode_projeto(st, cid, eq, parte):
                    alvos = (("atual", 1.0, False),)           # comprou a peça da próxima temporada
                elif projeto(eq, parte)["modo"] == "novo":
                    alvos = (("atual", 1 - FRACAO_PROJETO_NOVO, False), ("projeto", FRACAO_PROJETO_NOVO, True))
                else:
                    alvos = (("atual", 1.0, False),)
                for nome, frac, prox in alvos:
                    chave = f"{parte}_{nome}"
                    disp = saldo.get(chave, 0.0) + verba * pesos[parte] * frac
                    disp = min(disp, max(0.0, eq["financas"]["caixa"]))
                    saldo[chave] = max(0.0, disp - _gastar_guloso(st, cid, eq, parte, disp, prox))


# ---------------------------------------------------------------- calibração automática dos custos
def _nivel(ent, parte):
    if parte == "chassis":
        v = list((ent.get("atributos") or {}).values())
        return sum(v) / len(v) if v else 0.0
    return float(ent.get("potencia", 0))


def _pesos_ia(st, cid, eq):
    partes = [p for p in PARTES if pode(st, cid, eq, p)]
    return {"chassis": 0.7, "motor": 0.3} if len(partes) == 2 else {p: 1.0 for p in partes}


def calibrar_custos(st, rng=None):
    """Ajusta, no início do jogo, o custo por ponto de chassis e motor de cada categoria com desenvolvimento,
    para que a verba anual sustentável das equipes (receita prevista − despesas fixas) reconstrua, em média,
    o nível de chassis/motor da database. Sem isso o nível de longo prazo depende só dos números de custo
    e orçamento, e as peças se afastam da database depois da 1ª temporada. Grava o fator em
    desenvolvimento['calibracao'] (não altera o arquivo da database). Desligue com
    desenvolvimento['calibracao_automatica'] = false."""
    from . import economia
    for cid, c in st["categorias"].items():
        cfg = config(st, cid)
        if not cfg or cfg.get("calibracao") or cfg.get("calibracao_automatica", True) is False:
            continue
        cfg["calibracao"] = {}
        for parte in PARTES:
            if not cfg.get(parte):
                continue
            amostra = []                               # (verba anual da parte no projeto novo, nível atual)
            for eq in c["equipes"].values():
                if not eq.get("ativa") or not pode(st, cid, eq, parte):
                    continue
                ent = _entidade(st, cid, eq, parte)
                if not ent:
                    continue
                verba = max(0.0, economia.receita_prevista(st, cid, eq) - economia.despesas_fixas_previstas(st, cid, eq))
                amostra.append((verba * _pesos_ia(st, cid, eq)[parte], _nivel(ent, parte)))
            if not amostra or sum(v for v, _ in amostra) <= 0:
                continue
            alvo = sum(n for _, n in amostra) / len(amostra)
            base = {k: 0 for k in atributos_da_parte(parte)}
            original = dict(cfg[parte])

            perda = cfg.get("perda_manutencao", 0.3)

            def equilibrio(cfg_f, verba, inicio):
                """Nível de início de temporada a que a IA chega: o melhor entre projeto novo (80% da verba) e
                manutenção (toda a verba no carro atual, que perde `perda` na virada), no ponto fixo."""
                novo = _estimar(cfg_f, base, verba * FRACAO_PROJETO_NOVO)
                nivel = inicio
                for _ in range(6):
                    nivel = _estimar(cfg_f, {k: int(nivel) for k in base}, verba) * (1 - perda)
                return max(novo, nivel)

            def nivel_medio(fator):
                cfg_f = dict(original, custo_por_ponto=original["custo_por_ponto"] * fator)
                return sum(equilibrio(cfg_f, v, n) for v, n in amostra) / len(amostra)
            lo, hi = 1e-3, 1e3                         # nível médio cai quando o fator sobe
            for _ in range(26):
                meio = (lo * hi) ** 0.5
                if nivel_medio(meio) > alvo:
                    lo = meio
                else:
                    hi = meio
            fator = round((lo * hi) ** 0.5, 4)
            cfg[parte]["custo_por_ponto"] = original["custo_por_ponto"] * fator
            cfg["calibracao"][parte] = {"fator": fator, "custo_original": original["custo_por_ponto"],
                                        "nivel_alvo": round(alvo, 1), "equipes": len(amostra)}


def ajustar_calibracao(st):
    """Virada de temporada: a previsão de receita do início do jogo não conta os patrocínios que as equipes
    fecham depois, então o nível real pode se afastar do da database. Corrige aos poucos: se o nível médio da
    categoria ficou acima do alvo, o ponto fica mais caro; abaixo, mais barato (no máximo −15%/+20% por
    temporada)."""
    for cid, c in st["categorias"].items():
        cfg = config(st, cid)
        cal = (cfg or {}).get("calibracao")
        if not cal:
            continue
        for parte in PARTES:
            info = cal.get(parte)
            if not info:
                continue
            if regulamento.limite(st, cid, parte, st["ano"] - 1) is not None or \
                    regulamento.limite(st, cid, parte) is not None or regulamento.grande_mudanca(st, cid, st["ano"]):
                continue                  # nível mexido pelo regulamento (congelado, limitado ou carro novo): não corrige
            niveis = [_nivel(_entidade(st, cid, eq, parte), parte) for eq in c["equipes"].values()
                      if eq.get("ativa") and pode(st, cid, eq, parte) and _entidade(st, cid, eq, parte)]
            if not niveis or not info.get("nivel_alvo"):
                continue
            rel = (sum(niveis) / len(niveis)) / info["nivel_alvo"]
            ajuste = min(1.2, max(0.85, rel ** 3))
            info["fator"] = round(info["fator"] * ajuste, 4)
            cfg[parte]["custo_por_ponto"] = info["custo_original"] * info["fator"]


# ---------------------------------------------------------------- motores de fabricantes
def _receita_fornecimento(st, cid, m):
    from . import economia
    clientes = sum(1 for eq in st["categorias"][cid]["equipes"].values()
                   if eq.get("ativa") and (eq.get("motor") or {}).get("id") == m["id"])
    return ((m.get("contrato") or {}).get("valor_por_corrida") or 0) * economia.corridas(st, cid) * max(1, clientes)


def _verba_para_nivel(cfg_motor, nivel):
    """Verba anual (projeto novo) que constrói um motor de `nivel`."""
    lo, hi = 0.0, 1.0
    while _estimar(cfg_motor, {"potencia": 0}, hi * FRACAO_PROJETO_NOVO) < nivel and hi < 1e13:
        hi *= 2
    for _ in range(60):
        meio = (lo + hi) / 2
        if _estimar(cfg_motor, {"potencia": 0}, meio * FRACAO_PROJETO_NOVO) < nivel:
            lo = meio
        else:
            hi = meio
    return hi


def calibrar_fabricantes(st):
    """Verba base de cada fabricante de motor: a que mantém o nível do motor na database. Depois ela varia
    com a receita de fornecimento (mais clientes = mais verba, dentro de limites) e com um sorteio."""
    for cid, c in st["categorias"].items():
        cfg = config(st, cid)
        if not cfg or not cfg.get("motor") or cfg.get("calibracao_automatica", True) is False:
            continue
        fab = cfg.setdefault("calibracao", {}).setdefault("fabricantes", {})
        for m in c["motores"].values():
            if (m.get("fabricante") or {}).get("tipo") == "fabricante" and m["id"] not in fab:
                fab[m["id"]] = {"verba": round(_verba_para_nivel(cfg["motor"], m["potencia"])),
                                "receita": _receita_fornecimento(st, cid, m), "nivel_alvo": m["potencia"]}


def evoluir_fabricantes(st, rng):
    """Virada de temporada: motores de fabricantes (que não são de uma equipe) também evoluem. Verba = verba
    base calibrada × receita de fornecimento atual / inicial (limitada entre 0,8 e 1,25) × sorteio de ±15%;
    o fabricante fica com o melhor entre manter o motor (com a perda de manutenção) e um projeto novo.
    Só nas categorias com regras de desenvolvimento."""
    calibrar_fabricantes(st)                      # fabricantes novos (ou saves antigos)
    for cid, c in st["categorias"].items():
        cfg = config(st, cid)
        if not cfg or not cfg.get("motor"):
            continue
        mantido = regulamento.carro_mantido(st, cid, "motor", st["ano"])
        lim = regulamento.limite(st, cid, "motor") if mantido else None
        perda = 0.0 if mantido else cfg.get("perda_manutencao", 0.3)
        fab = (cfg.get("calibracao") or {}).get("fabricantes", {})
        for m in c["motores"].values():
            if (m.get("fabricante") or {}).get("tipo") != "fabricante":
                continue
            cal = fab.get(m["id"])
            if cal:
                rel = _receita_fornecimento(st, cid, m) / max(1.0, cal["receita"])
                verba = cal["verba"] * min(1.25, max(0.8, rel))
            else:
                verba = _receita_fornecimento(st, cid, m)
            verba *= rng.uniform(0.85, 1.15)
            manut = _estimar(cfg["motor"], {"potencia": m["potencia"]}, verba) * (1 - perda)
            novo = _estimar(cfg["motor"], {"potencia": 0}, verba * FRACAO_PROJETO_NOVO)
            antes = m["potencia"]
            m["potencia"] = int(max(manut, novo))
            if lim is not None:                        # regulamento: sem perda, ganho limitado
                m["potencia"] = antes + min(lim, max(0, m["potencia"] - antes))
            if m["potencia"] != antes:
                noticia(st, f"{m['nome']}: o fabricante apresenta a evolução do motor ({antes} → {m['potencia']}).",
                        cid, "desenvolvimento")
