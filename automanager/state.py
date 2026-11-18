"""Estado do jogo em memória + savegame.

O estado é composto só de dicts/listas (serializável direto em JSON), o que
mantém a estrutura maleável: campos novos nos arquivos da DB são preservados.

state = {
  "versao", "ano", "semana",
  "usuario": {"categoria": id, "equipe": id},
  "categorias": {cat_id: {"categoria", "equipes", "chassis", "motores",
                          "patrocinadores", "calendario"}},
  "pilotos": {id_global: piloto},     # pool único (pilotos livres de todas as categorias)
  "noticias": [...]
}
"""
import copy
import json
import os
import random
import time

from . import db
from .util import PASTA_SAVES

VERSAO_SAVE = 1


def id_global_piloto(cat_id, pid):
    return f"{cat_id}/{pid}"


def _caixa_inicial(equipe, regras):
    """Caixa de equipe existente quando a DB não informa 'caixa'."""
    if equipe.get("caixa") is not None:
        return float(equipe["caixa"])
    return regras["orcamento_medio"] * (0.6 + 0.6 * equipe.get("recursos", 50) / 100)


def financas_zeradas():
    return {"receitas": {"patrocinio": 0.0, "tv": 0.0, "premios": 0.0, "fornecimento": 0.0, "multas": 0.0},
            "despesas": {"salarios": 0.0, "chassis": 0.0, "motor": 0.0, "desenvolvimento": 0.0, "multas": 0.0}}


def dono_da_parte(st, cid, eq, parte):
    """Equipe que faz e vende o chassis/motor que `eq` compra (None se for de fornecedor ou próprio)."""
    info = eq.get(parte) or {}
    if info.get("origem") in (None, "proprio") or not info.get("id"):
        return None
    c = st["categorias"][cid]
    ent = (c["chassis"] if parte == "chassis" else c["motores"]).get(info["id"]) or {}
    dono = ent.get("equipe") if parte == "chassis" else ((ent.get("fabricante") or {}).get("equipe")
                                                         if (ent.get("fabricante") or {}).get("tipo") == "equipe" else None)
    d = c["equipes"].get(dono)
    return d if d and d["id"] != eq["id"] else None


def lancar(eq, tipo, chave, valor):
    """Lança receita ou despesa no ano e no caixa da equipe."""
    ano = eq["financas"]["ano"][tipo]
    ano[chave] = ano.get(chave, 0.0) + valor
    eq["financas"]["caixa"] += valor if tipo == "receitas" else -valor


def novo_jogo(caminhos, semente=None):
    """Carrega uma ou várias categorias (mesma temporada) num estado novo. `semente` sorteia o que a database
    não define (potencial, ano de pico e de aposentadoria dos pilotos...): sem ela, cada jogo novo recebe uma
    semente aleatória própria (guardada em st["semente"]), para que as carreiras não se repitam de um jogo
    para o outro."""
    if semente is None:
        semente = random.SystemRandom().randrange(2 ** 32)
    st = {"semente": semente, "versao": VERSAO_SAVE, "ano": None, "semana": 1, "usuario": {"categoria": None, "equipe": None},
          "arquivos": list(caminhos), "categorias": {}, "pilotos": {}, "noticias": [],
          "avisos_enviados": {}, "criado_em": time.strftime("%Y-%m-%d %H:%M")}
    for caminho in caminhos:
        d = db.carregar_arquivo(caminho)
        cat = d["categoria"]
        cid = cat["id"]
        if cid in st["categorias"]:
            raise db.ErroDatabase(f"Categoria '{cid}' carregada duas vezes.")
        if st["ano"] is None:
            st["ano"] = cat["ano"]
        elif st["ano"] != cat["ano"]:
            raise db.ErroDatabase("Todas as categorias devem ser da mesma temporada.")
        equipes = {}
        for e in d["equipes"]:
            e = copy.deepcopy(e)
            e["financas"] = {"caixa": _caixa_inicial(e, cat["regras"]), "ano": financas_zeradas()}
            equipes[e["id"]] = e
        st["categorias"][cid] = {
            "categoria": cat,
            "equipes": equipes,
            "chassis": db.indexar(copy.deepcopy(d["chassis"])),
            "motores": db.indexar(copy.deepcopy(d["motores"])),
            "patrocinadores": db.indexar(copy.deepcopy(d["patrocinadores"])),
            "calendario": copy.deepcopy(d["calendario"]),
            "arquivo": os.path.basename(caminho),
        }
        for p in d["pilotos"]:
            p = copy.deepcopy(p)
            gid = id_global_piloto(cid, p["id"])
            p["id_db"], p["id"] = p["id"], gid
            p["categoria_origem"] = cid
            if p.get("contrato"):
                p["contrato"]["categoria"] = cid
                if p["contrato"].get("corridas_definidas"):
                    p["contrato"]["corridas"] = len(p["contrato"]["corridas_definidas"])
            p["contrato_futuro"] = None
            st["pilotos"][gid] = p
    from . import carreira
    rng = random.Random(semente)
    carreira.preparar_todos(st, rng)
    carreira.carregar_novos_do_arquivo(st, st["ano"], rng)
    carreira.referencia_pilotos(st)
    from . import desenvolvimento
    desenvolvimento.calibrar_custos(st)
    desenvolvimento.calibrar_fabricantes(st)
    from . import fornecedores, regulamento, tempo_base
    fornecedores.iniciar(st)
    tempo_base.iniciar(st)
    from . import mercado
    mercado.atualizar_precos_chassis(st)
    for c in st["categorias"].values():
        if regulamento.cfg(c["categoria"])["ativo"]:
            regulamento.estado(c)
    return st


# ---------------------------------------------------------------- consultas
def cat(st, cid=None):
    return st["categorias"][cid or st["usuario"]["categoria"]]


def equipe_usuario(st):
    u = st["usuario"]
    return st["categorias"][u["categoria"]]["equipes"][u["equipe"]]


def pilotos_da_equipe(st, cid, eid, futuro=False):
    out = []
    for p in st["pilotos"].values():
        c = p.get("contrato_futuro") if futuro else p.get("contrato")
        if c and c.get("categoria") == cid and c.get("equipe") == eid:
            out.append(p)
    ordem = {"principal": 0, "teste": 1}
    return sorted(out, key=lambda p: ordem.get(p["contrato_futuro" if futuro else "contrato"]["situacao"], 2))


def chassis_da_equipe(st, cid, equipe):
    ch = equipe.get("chassis") or {}
    return st["categorias"][cid]["chassis"].get(ch.get("id")) if ch.get("id") else None


def motor_da_equipe(st, cid, equipe):
    mo = equipe.get("motor") or {}
    return st["categorias"][cid]["motores"].get(mo.get("id")) if mo.get("id") else None


def proximo_evento(st, cid=None):
    c = cat(st, cid)
    futuros = [e for e in c["calendario"] if e.get("ativo") and e["semana"] >= st["semana"]]
    if not c["categoria"]["regras"].get("testes_coletivos"):
        futuros = [e for e in futuros if e["especie"] == "corrida"]
    return min(futuros, key=lambda e: e["semana"]) if futuros else None


def pode_desenvolver_motor(st, cid, eid):
    regras = st["categorias"][cid]["categoria"]["regras"]
    if not regras.get("desenvolvimento_motor_por_equipe"):
        return False
    if "proprio" not in regras.get("fontes_de_motor_permitidas", ["proprio"]):
        return False
    lista = regras.get("equipes_com_desenvolvimento_de_motor") or []
    return not lista or eid in lista


def noticia(st, texto, cid=None, tipo="geral", equipe=None):
    """tipo 'usuario' = notícia de uma equipe humana (em destaque); 'equipe' diz qual (multijogador)."""
    if tipo == "usuario" and equipe is None:
        equipe = (st.get("usuario") or {}).get("equipe")
    n = {"ano": st["ano"], "semana": st["semana"], "categoria": cid, "tipo": tipo, "texto": texto}
    if equipe:
        n["equipe"] = equipe
    st["noticias"].append(n)


# ---------------------------------------------------------------- equipes humanas (1 jogador ou multijogador)
def multijogador(st):
    return st.get("multiplayer")


def humanas(st):
    """{(categoria, equipe)} controladas por pessoas. No multijogador: as dos jogadores (menos as que a IA
    conduz nesta semana por falta de arquivo de ordens)."""
    mp = st.get("multiplayer")
    if mp:
        ia = set(mp.get("ia_nesta_semana") or [])
        return {(j["categoria"], j["equipe"]) for jid, j in mp["jogadores"].items()
                if not j.get("eliminado") and jid not in ia}
    u = st.get("usuario") or {}
    return {(u["categoria"], u["equipe"])} if u.get("equipe") else set()


def eh_humana(st, cid, eid):
    return (cid, eid) in humanas(st)


def quem(st, cid, eid, minuscula=False):
    """'Sua equipe' (um jogador, equipe do usuário) ou 'A <nome>' – no multijogador sempre o nome."""
    if not st.get("multiplayer") and (st.get("usuario") or {}).get("equipe") == eid \
            and (st.get("usuario") or {}).get("categoria") == cid:
        return "sua equipe" if minuscula else "Sua equipe"
    nome = st["categorias"][cid]["equipes"].get(eid, {}).get("nome", "?")
    return f"a {nome}" if minuscula else f"A {nome}"


# ---------------------------------------------------------------- seleção / criação de equipe
def escolher_equipe(st, cid, eid):
    st["usuario"] = {"categoria": cid, "equipe": eid}
    eq = st["categorias"][cid]["equipes"][eid]
    noticia(st, f"Você assumiu o comando da {eq['nome']}.", cid, "usuario")


def criar_equipe(st, cid, nome, nacionalidade, rng=random, cor=None, cor_secundaria=None):
    """Cria a equipe do usuário com orçamento aleatório de 0,7 a 1,2 do orçamento médio."""
    eq = nova_equipe(st, cid, nome, nacionalidade, rng, cor, cor_secundaria)
    escolher_equipe(st, cid, eq["id"])
    return eq


def nova_equipe(st, cid, nome, nacionalidade, rng=random, cor=None, cor_secundaria=None, base="usuario"):
    """Equipe nova criada por uma pessoa (jogo individual ou jogador do multijogador), sem carro: se a categoria
    pede chassis/motor próprios, fica com 'dev_inicial_pendente' até o desenvolvimento inicial; senão, contrata
    as peças no Mercado."""
    c = st["categorias"][cid]
    regras = c["categoria"]["regras"]
    eid, n = base, 1
    while eid in c["equipes"]:
        n += 1
        eid = f"{base}{n}"
    orcamento = round(regras["orcamento_medio"] * rng.uniform(0.7, 1.2), -3)
    eq = {"id": eid, "nome": nome, "ativa": True, "nacionalidade": nacionalidade, "recursos": 50,
          "caixa": orcamento, "chassis": None, "motor": None, "prob_fechamento": 0.0, "prob_surgimento": 0.0,
          "criada_pelo_usuario": True,
          "financas": {"caixa": orcamento, "ano": financas_zeradas()}}
    if cor:
        eq["cor"] = cor
    if cor_secundaria:
        eq["cor_secundaria"] = cor_secundaria
    c["equipes"][eid] = eq
    ch, mo = precisa_desenvolvimento_inicial(st, cid, eid)
    if ch or mo:
        eq["dev_inicial_pendente"] = True
    noticia(st, f"Nova equipe {nome} ({nacionalidade}) se inscreve na {c['categoria']['nome']}.", cid, "equipe")
    return eq


def fontes_chassis(categoria):
    """De onde as equipes podem ter chassis: 'proprio' (desenvolvido pela equipe), 'fabricante' (fornecedor) e
    'equipe' (chassis de outra equipe). regras.fontes_de_chassis_permitidas; sem a lista: só próprio nas categorias
    com desenvolvimento de chassis, só de fornecedor nas outras."""
    r = categoria["regras"]
    f = list(r.get("fontes_de_chassis_permitidas") or (["proprio"] if r.get("desenvolvimento_chassis_por_equipe")
                                                        else ["fabricante"]))
    if not r.get("desenvolvimento_chassis_por_equipe"):
        f = [x for x in f if x != "proprio"] or ["fabricante"]
    return f


def compra_de_chassis(categoria):
    """A categoria deixa comprar chassis (de fornecedor ou de outra equipe)?"""
    return any(x in fontes_chassis(categoria) for x in ("fabricante", "equipe"))


def precisa_desenvolvimento_inicial(st, cid, eid):
    """(chassis?, motor?) – quais partes a equipe criada deve desenvolver na criação."""
    regras = st["categorias"][cid]["categoria"]["regras"]
    return bool(regras.get("desenvolvimento_chassis_por_equipe")), pode_desenvolver_motor(st, cid, eid)


DEV_INICIAL_PADRAO = {"chassis": {"custo_por_ponto": 100000, "atributo_base": 35, "atributo_maximo": 85},
                      "motor": {"custo_por_ponto": 200000, "atributo_base": 40, "atributo_maximo": 85}}


def config_dev_inicial(st, cid, parte):
    di = st["categorias"][cid]["categoria"].get("desenvolvimento_inicial") or {}
    return dict(DEV_INICIAL_PADRAO[parte], **(di.get(parte) or {}))


def custo_desenvolvimento_inicial(st, cid, attrs_chassis=None, potencia=None):
    """Custo do chassis/motor iniciais. ValueError se algum valor estiver fora de [base, máximo]."""
    from .db import ATRIBUTOS_CHASSIS
    total = 0.0
    if attrs_chassis is not None:
        cfg = config_dev_inicial(st, cid, "chassis")
        if set(attrs_chassis) != set(ATRIBUTOS_CHASSIS):
            raise ValueError("Chassis inicial incompleto.")
        for k, v in attrs_chassis.items():
            if not cfg["atributo_base"] <= int(v) <= cfg["atributo_maximo"]:
                raise ValueError(f"Chassis inicial: {k} fora da faixa {cfg['atributo_base']}–{cfg['atributo_maximo']}.")
            total += (int(v) - cfg["atributo_base"]) * cfg["custo_por_ponto"]
    if potencia is not None:
        cfg = config_dev_inicial(st, cid, "motor")
        if not cfg["atributo_base"] <= int(potencia) <= cfg["atributo_maximo"]:
            raise ValueError(f"Motor inicial fora da faixa {cfg['atributo_base']}–{cfg['atributo_maximo']}.")
        total += (int(potencia) - cfg["atributo_base"]) * cfg["custo_por_ponto"]
    return total


def aplicar_desenvolvimento_inicial(st, cid, eid, attrs_chassis=None, potencia=None, custo=0.0):
    c = st["categorias"][cid]
    eq = c["equipes"][eid]
    ano2 = str(st["ano"])[-2:]
    if attrs_chassis is not None:
        chid = f"ch_{eid}"
        c["chassis"][chid] = {"id": chid, "nome": f"{eq['nome'].split()[0]} C{ano2}",
                              "nacionalidade": eq["nacionalidade"], "equipe": eid,
                              "atributos": {k: int(v) for k, v in attrs_chassis.items()}, "contrato": None}
        eq["chassis"] = {"id": chid, "origem": "proprio"}
    if potencia is not None:
        mid = f"mot_{eid}"
        c["motores"][mid] = {"id": mid, "nome": f"{eq['nome'].split()[0]} M{ano2}",
                             "nacionalidade": eq["nacionalidade"], "potencia": int(potencia),
                             "fabricante": {"tipo": "equipe", "equipe": eid}, "contrato": None}
        eq["motor"] = {"id": mid, "origem": "proprio"}
    eq["financas"]["caixa"] -= custo
    eq["financas"]["ano"]["despesas"]["desenvolvimento"] += custo


# ---------------------------------------------------------------- savegame
def listar_saves(pasta=PASTA_SAVES):
    if not os.path.isdir(pasta):
        return []
    out = []
    for f in sorted(os.listdir(pasta)):
        if not f.endswith(".json"):
            continue
        caminho = os.path.join(pasta, f)
        try:
            with open(caminho, encoding="utf-8") as fh:
                d = json.load(fh)
            u = d["usuario"]
            eq = d["categorias"][u["categoria"]]["equipes"][u["equipe"]]
            out.append({"caminho": caminho, "nome": f[:-5], "equipe": eq["nome"],
                        "categoria": d["categorias"][u["categoria"]]["categoria"]["nome"],
                        "ano": d["ano"], "semana": d["semana"],
                        "modificado": time.strftime("%d/%m/%Y %H:%M", time.localtime(os.path.getmtime(caminho)))})
        except (OSError, KeyError, json.JSONDecodeError, TypeError):
            out.append({"caminho": caminho, "nome": f[:-5], "equipe": "(arquivo inválido)", "categoria": "",
                        "ano": "", "semana": "", "modificado": ""})
    return out


def salvar(st, nome, pasta=PASTA_SAVES):
    os.makedirs(pasta, exist_ok=True)
    nome = "".join(ch for ch in nome if ch.isalnum() or ch in " _-").strip() or "save"
    caminho = os.path.join(pasta, nome + ".json")
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, caminho)
    st["nome_save"] = nome
    return caminho


def carregar(caminho):
    with open(caminho, encoding="utf-8") as f:
        st = json.load(f)
    if st.get("versao") != VERSAO_SAVE:
        raise db.ErroDatabase("Versão de savegame incompatível.")
    st["nome_save"] = os.path.splitext(os.path.basename(caminho))[0]
    return st
