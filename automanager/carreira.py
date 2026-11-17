"""Carreira dos pilotos: curva de habilidades, aposentadoria e novos pilotos.

Campos do piloto no JSON (todos opcionais; o jogo define o que faltar):
  ano_pico            ano em que as habilidades chegam ao máximo (padrão: idade sorteada entre 27 e 31)
  potencial           média dos atributos no pico, 0-100 (padrão: estimado pela idade)
  ano_aposentadoria   ano em que o piloto se aposenta (deixa de correr)
  idade_aposentadoria alternativa ao ano: idade com que se aposenta (padrão: idade sorteada entre 34 e 40)
Os atributos do JSON são os valores iniciais. Até o pico sobem em curva; depois caem aos poucos,
com físico e reflexos caindo mais rápido e experiência (acerto, consistência...) se mantendo.

Novos pilotos (no início de cada temporada), nesta ordem:
  1. arquivo database/<ano>/novos_pilotos_<ano>.json (formato dos pilotos + "categoria" opcional)
  2. subida das categorias de tier inferior (pelo próprio mercado)
  3. pilotos fictícios no tier mais baixo carregado, com nomes de database/nomes.json na proporção
     de nacionalidades de cada categoria; quantidade = aposentados + margem
"""
import json
import os
import random

from .db import ATRIBUTOS_PILOTO
from .state import noticia
from .util import PASTA_DATABASE, clamp

# quanto cada atributo cai por ano depois do pico (multiplicador da queda base)
QUEDA = {"fisico": 1.8, "aceleracao": 1.5, "largada": 1.3, "classificacao": 1.3, "concentracao": 1.1,
         "chuva": 0.8, "conducao": 1.0, "ritmo_corrida": 0.6, "consistencia": 0.3, "acerto_carro": 0.2,
         "trabalho_equipe": 0.2}
MARGEM_FICTICIOS = 2


# ---------------------------------------------------------------- preparação
def preparar_piloto(p, ano, rng=random):
    """Completa os campos de carreira que faltarem. Guarda os atributos iniciais para a curva."""
    idade = p.get("idade", 22)
    if not p.get("ano_pico"):
        p["ano_pico"] = ano + max(0, rng.randint(27, 31) - idade)
    if not p.get("ano_aposentadoria"):
        alvo = p.get("idade_aposentadoria") or rng.randint(34, 40)
        p["ano_aposentadoria"] = ano + max(1, alvo - idade)
    media = sum(p["atributos"].values()) / max(1, len(p["atributos"]))
    if not p.get("potencial"):
        anos_ate_pico = max(0, p["ano_pico"] - ano)
        p["potencial"] = int(clamp(media + anos_ate_pico * rng.uniform(1.0, 3.0), media, 97))
    p.setdefault("ano_inicio_carreira", ano)
    p.setdefault("atributos_iniciais", dict(p["atributos"]))
    p.setdefault("temporadas_sem_contrato", 0)


def preparar_todos(st, rng=random):
    for p in st["pilotos"].values():
        preparar_piloto(p, st["ano"], rng)


# ---------------------------------------------------------------- curva
def _curva(progresso):
    """0..1 -> 0..1, crescimento rápido no começo e mais lento perto do pico."""
    progresso = clamp(progresso, 0, 1)
    return 1 - (1 - progresso) ** 2


def evoluir(p, ano, rng=random):
    """Atualiza os atributos do piloto para o ano informado."""
    ini = p.get("atributos_iniciais") or p["atributos"]
    media_ini = sum(ini.values()) / max(1, len(ini))
    ganho_total = max(0.0, p.get("potencial", media_ini) - media_ini)
    if ano <= p["ano_pico"]:
        duracao = max(1, p["ano_pico"] - p.get("ano_inicio_carreira", ano))
        f = _curva((ano - p.get("ano_inicio_carreira", ano)) / duracao)
        for k in ATRIBUTOS_PILOTO:
            alvo = ini.get(k, 50) + ganho_total * f + rng.uniform(-1, 1)
            p["atributos"][k] = int(clamp(round(max(p["atributos"].get(k, 0), alvo)), 1, 99))
    else:
        anos_pos = ano - p["ano_pico"]
        idade = p.get("idade", 30)
        base = 0.8 + 0.25 * anos_pos + (1.0 if idade >= 35 else 0.0)
        for k in ATRIBUTOS_PILOTO:
            queda = base * QUEDA.get(k, 1.0) * rng.uniform(0.6, 1.4)
            p["atributos"][k] = int(clamp(round(p["atributos"].get(k, 50) - queda), 1, 99))


# ---------------------------------------------------------------- aposentadoria
def disponivel_para(p, ano):
    """False se o piloto já terá se aposentado no ano informado."""
    return not p.get("ano_aposentadoria") or p["ano_aposentadoria"] > ano


def aposentar(st):
    """Aposenta quem chegou ao ano de aposentadoria (ou está há 2 temporadas sem contrato)."""
    saem = []
    for pid, p in list(st["pilotos"].items()):
        if p.get("contrato") is None and p.get("contrato_futuro") is None:
            p["temporadas_sem_contrato"] = p.get("temporadas_sem_contrato", 0) + 1
        else:
            p["temporadas_sem_contrato"] = 0
        sem = p["temporadas_sem_contrato"] >= 2 and p.get("idade", 0) >= 24
        if p.get("ano_aposentadoria", 9999) <= st["ano"] or sem:
            ct = p.get("contrato") or p.get("contrato_futuro") or {}
            cid = ct.get("categoria") or p.get("categoria_atual") or p.get("categoria_origem")
            p["aposentado_em"] = st["ano"]
            p["categoria_saida"] = cid
            st.setdefault("aposentados", {})[pid] = p
            del st["pilotos"][pid]
            saem.append((p, cid, ct))
            motivo = "sem equipe há duas temporadas" if sem and p.get("ano_aposentadoria", 9999) > st["ano"] \
                else f"aos {p.get('idade', '?')} anos"
            eq = ""
            if ct.get("equipe") and cid in st["categorias"]:
                eq = f" e deixa a {st['categorias'][cid]['equipes'].get(ct['equipe'], {}).get('nome', '?')}"
            from .state import eh_humana
            tipo = "usuario" if ct.get("equipe") and eh_humana(st, cid, ct["equipe"]) else "piloto"
            noticia(st, f"{p['nome']} anuncia a aposentadoria ({motivo}){eq}.", cid, tipo, equipe=ct.get("equipe"))
    return saem


# ---------------------------------------------------------------- novos pilotos
def _ler_nomes():
    caminho = os.path.join(PASTA_DATABASE, "nomes.json")
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f).get("nacionalidades", {})
    except (OSError, json.JSONDecodeError):
        return {}


def carregar_novos_do_arquivo(st, ano, rng=random):
    """database/<ano>/novos_pilotos_<ano>.json"""
    caminho = os.path.join(PASTA_DATABASE, str(ano), f"novos_pilotos_{ano}.json")
    if not os.path.exists(caminho):
        return []
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    lista = dados.get("pilotos", dados) if isinstance(dados, dict) else dados
    tiers = sorted(st["categorias"], key=lambda c: -st["categorias"][c]["categoria"].get("tier", 1))
    novos = []
    for p in lista:
        p = dict(p)
        cid = p.pop("categoria", None)
        if cid not in st["categorias"]:
            cid = tiers[0]
        gid = f"novos{ano}/{p['id']}"
        if gid in st["pilotos"] or gid in st.get("aposentados", {}):
            continue
        p.update({"id_db": p["id"], "id": gid, "categoria_origem": cid, "categoria_atual": cid,
                  "contrato": None, "contrato_futuro": None})
        preparar_piloto(p, ano, rng)
        st["pilotos"][gid] = p
        novos.append(p)
    if novos:
        noticia(st, f"Novos pilotos chegam ao mercado: {', '.join(p['nome'] for p in novos)}.", None, "piloto")
    return novos


def _proporcao_nacionalidades(st, cid):
    cont = {}
    for p in st["pilotos"].values():
        ct = p.get("contrato") or {}
        if (ct.get("categoria") or p.get("categoria_atual") or p.get("categoria_origem")) == cid:
            cont[p["nacionalidade"]] = cont.get(p["nacionalidade"], 0) + 1
    return cont


def gerar_ficticios(st, quantidade, rng=random):
    """Pilotos fictícios no(s) tier(s) mais baixo(s) carregado(s)."""
    if quantidade <= 0:
        return []
    nomes = _ler_nomes()
    if not nomes:
        return []
    pior_tier = max(c["categoria"].get("tier", 1) for c in st["categorias"].values())
    destinos = [cid for cid, c in st["categorias"].items() if c["categoria"].get("tier", 1) == pior_tier]
    existentes = {p["nome"] for p in st["pilotos"].values()} | {p["nome"] for p in st.get("aposentados", {}).values()}
    seq = st.setdefault("seq_ficticios", 0)
    gerados = []
    for i in range(quantidade):
        cid = destinos[i % len(destinos)]
        prop = {k: v for k, v in _proporcao_nacionalidades(st, cid).items() if k in nomes} or \
            {k: 1 for k in nomes}
        nac = rng.choices(list(prop), weights=list(prop.values()))[0]
        nome = None
        for _ in range(30):
            cand = f"{rng.choice(nomes[nac]['nomes'])} {rng.choice(nomes[nac]['sobrenomes'])}"
            if cand not in existentes:
                nome = cand
                break
        if not nome:
            continue
        existentes.add(nome)
        cal = st.get("calibracao_pilotos")
        if cal:
            # nível e potencial ancorados na database do início do jogo (não na média atual, que se realimenta)
            nivel = rng.gauss(cal["estreia"]["media"], cal["estreia"]["sd"])
            potencial = rng.gauss(cal["potencial"]["media"] + _ajuste(cal), cal["potencial"]["sd"])
        else:
            cat_pilotos = [p for p in st["pilotos"].values() if (p.get("contrato") or {}).get("categoria") == cid]
            media_cat = sum(_media(p) for p in cat_pilotos) / len(cat_pilotos) if cat_pilotos else 55
            nivel = media_cat - 15
            potencial = nivel + rng.uniform(5, 38)
        idade = rng.randint(17, 21)
        attrs = {k: int(clamp(rng.gauss(nivel, 6), 20, 90)) for k in ATRIBUTOS_PILOTO}
        nivel = sum(attrs.values()) / len(attrs)
        seq += 1
        gid = f"ficticio/{seq:05d}"
        p = {"id": gid, "id_db": gid, "nome": nome, "nacionalidade": nac, "idade": idade, "atributos": attrs,
             "contrato": None, "contrato_futuro": None, "categoria_origem": cid, "categoria_atual": cid,
             "ficticio": True,
             "potencial": int(clamp(potencial, nivel + 3, 96))}
        preparar_piloto(p, st["ano"], rng)
        st["pilotos"][gid] = p
        gerados.append(p)
    st["seq_ficticios"] = seq
    if gerados:
        nome_cat = ", ".join(st["categorias"][d]["categoria"]["nome"] for d in destinos)
        noticia(st, f"{len(gerados)} jovens pilotos estreiam no mercado da {nome_cat}: "
                    f"{', '.join(p['nome'] + ' (' + p['nacionalidade'] + ')' for p in gerados[:6])}"
                    f"{'...' if len(gerados) > 6 else ''}", destinos[0], "piloto")
    return gerados


# ---------------------------------------------------------------- virada de temporada
def virada(st, rng=random):
    """Chamada no início de cada temporada (depois da troca de contratos e da idade +1)."""
    saem = aposentar(st)
    for p in st["pilotos"].values():
        preparar_piloto(p, st["ano"], rng)
        evoluir(p, st["ano"], rng)
    if "calibracao_pilotos" not in st:
        referencia_pilotos(st)                     # saves antigos: a referência passa a ser o nível de agora
    ajustar_nivel(st)
    retornos(st, rng)
    novos = carregar_novos_do_arquivo(st, st["ano"], rng)
    faltam = len(saem) + MARGEM_FICTICIOS - len(novos)
    gerar_ficticios(st, faltam, rng)


# ---------------------------------------------------------------- nível da população de pilotos
def _media(p):
    return sum(p["atributos"].values()) / max(1, len(p["atributos"]))


def _calibra(st, cid):
    c = st["categorias"].get(cid)
    return bool(c) and (c["categoria"].get("carreira") or {}).get("calibracao_automatica", True) is not False


def _cat_do(p):
    ct = p.get("contrato") or {}
    return ct.get("categoria") or p.get("categoria_atual") or p.get("categoria_origem")


def referencia_pilotos(st):
    """No início do jogo, guarda o nível da database: média dos titulares de cada categoria (alvo de longo
    prazo), nível dos estreantes (pilotos de até 21 anos do tier mais baixo) e potencial (nível dos pilotos já
    estabelecidos, 25 anos ou mais: o que uma carreira atinge nesta database)."""
    import statistics as S
    todos = list(st["pilotos"].values())
    if not todos:
        return
    ref = {}
    for cid in st["categorias"]:
        tit = [_media(p) for p in todos if (p.get("contrato") or {}).get("categoria") == cid
               and p["contrato"].get("situacao") == "principal"]
        if tit:
            ref[cid] = round(S.mean(tit), 2)
    pior = max(c["categoria"].get("tier", 1) for c in st["categorias"].values())
    baixos = {cid for cid, c in st["categorias"].items() if c["categoria"].get("tier", 1) == pior}
    jovens = [_media(p) for p in todos if _cat_do(p) in baixos and p.get("idade", 25) <= 21] or \
        [_media(p) - 8 for p in todos if _cat_do(p) in baixos] or [50.0]
    feitos = [_media(p) for p in todos if p.get("idade", 25) >= 25] or [_media(p) for p in todos]
    st["calibracao_pilotos"] = {
        "ref": ref,
        "estreia": {"media": round(S.mean(jovens), 2), "sd": round(max(3.0, S.pstdev(jovens)), 2)},
        "potencial": {"media": round(S.mean(feitos), 2), "sd": round(max(4.0, S.pstdev(feitos)), 2)},
        "ajuste": 0.0}


def _ajuste(cal):
    a = cal.get("ajuste", 0.0)
    return a if isinstance(a, (int, float)) else 0.0


def ajustar_nivel(st):
    """Correção suave por temporada: se a média dos titulares do tier mais alto se afastar da referência, o
    potencial dos estreantes e dos pilotos que ainda não chegaram ao auge é corrigido (no máx. 2 pontos por
    temporada). Só o tier mais alto conta: é nele que o potencial define o nível; nos tiers de baixo o nível vem
    do mercado (quem as equipes contratam entre os livres). Desligue com
    categoria.carreira.calibracao_automatica = false."""
    cal = st.get("calibracao_pilotos")
    if not cal:
        return
    topo = min(c["categoria"].get("tier", 1) for c in st["categorias"].values())
    desvios = {}
    for cid, alvo in cal["ref"].items():
        c = st["categorias"].get(cid)
        if not c or not _calibra(st, cid):
            continue
        tit = [_media(p) for p in st["pilotos"].values() if (p.get("contrato") or {}).get("categoria") == cid
               and p["contrato"].get("situacao") == "principal"]
        if tit:
            desvios[cid] = round(sum(tit) / len(tit) - alvo, 2)
    cal["ultimo_desvio"] = desvios
    base = [d for cid, d in desvios.items() if st["categorias"][cid]["categoria"].get("tier", 1) == topo]
    if not base:
        return
    corr = clamp(-0.5 * sum(base) / len(base), -2.0, 2.0)
    cal["ajuste"] = round(clamp(_ajuste(cal) + corr, -20, 20), 2)
    for p in st["pilotos"].values():
        if p.get("ano_pico", 0) > st["ano"] and p.get("potencial") and _calibra(st, _cat_do(p)):
            p["potencial"] = int(round(clamp(p["potencial"] + corr, _media(p), 97)))


# ---------------------------------------------------------------- retorno de quem parou
RETORNO_PADRAO = {"prob_anual": 0.04, "anos_maximos_fora": 6, "idade_maxima": 40}


def retornos(st, rng=random):
    """Aposentados podem voltar à categoria de onde saíram (chance pequena, em mobilidade.retorno da categoria).
    Base real: na F1, ~1 piloto por temporada volta depois de 1+ temporada fora, entre ~25 ex-pilotos que
    pararam nos últimos 6 anos – cerca de 4% ao ano por ex-piloto, menos quanto mais tempo fora."""
    for pid, p in list(st.get("aposentados", {}).items()):
        cid = p.get("categoria_saida")
        if cid not in st["categorias"]:
            continue
        cfg = dict(RETORNO_PADRAO, **((st["categorias"][cid]["categoria"].get("mobilidade") or {}).get("retorno") or {}))
        fora = st["ano"] - p.get("aposentado_em", st["ano"])
        idade = p.get("idade", 30) + fora
        if fora < 1 or fora > cfg["anos_maximos_fora"] or idade > cfg["idade_maxima"]:
            continue
        from .mercado import acima_da_idade
        if acima_da_idade(st["categorias"][cid]["categoria"], idade):
            continue
        chance = cfg["prob_anual"] * (1 - (fora - 1) / max(1, cfg["anos_maximos_fora"]))
        if rng.random() >= chance:
            continue
        del st["aposentados"][pid]
        p["idade"] = idade
        for ano in range(p["aposentado_em"] + 1, st["ano"] + 1):
            evoluir(p, ano, rng)                    # o tempo parado também pesa
        p.pop("aposentado_em", None)
        p.update({"contrato": None, "contrato_futuro": None, "categoria_atual": cid, "temporadas_sem_contrato": 0,
                  "ano_aposentadoria": st["ano"] + rng.randint(1, 4), "retornou_em": st["ano"]})
        st["pilotos"][pid] = p
        noticia(st, f"{p['nome']} anuncia a volta às pistas depois de {fora} temporada(s) parado e procura vaga na "
                    f"{st['categorias'][cid]['categoria']['nome']}.", cid, "piloto")
