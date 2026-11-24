"""Multijogador por arquivos (um comissário e vários jogadores).

Fluxo de cada semana (1 semana = 1 turno):
  1. O comissário exporta o arquivo da liga para os jogadores (sem as senhas e sem as ordens dos outros).
  2. Cada jogador abre o arquivo no modo jogador, entra com a senha, toma as decisões da sua equipe
     (propostas a pilotos, contratos de chassis/motor, patrocínios, empréstimos, desenvolvimento) e define o
     plano dos eventos da semana. Salva um arquivo de ordens assinado com a senha.
  3. O comissário importa os arquivos de ordens e roda a semana: as ações de cada jogador são reaplicadas
     (em ordem sorteada entre os jogadores), os planos de evento valem para os carros dele nas simulações e a
     semana avança como no jogo de um jogador.

Política para quem não mandou o arquivo (escolhida na criação da liga, pode ser trocada):
  "ia"       a IA conduz a equipe nesta semana;
  "repetir"  repete o desenvolvimento e o plano de evento das últimas ordens (sem novas ações de mercado);
  "bloquear" a semana só roda com todos os arquivos (ou se o comissário pular o jogador: IA nesta semana).

st["multiplayer"] = {
  "id", "nome", "politica", "papel": "comissario"|"jogador", "criada_em",
  "jogadores": {jid: {"nome", "categoria", "equipe", "sal", "verificador", "chave"*, "eliminado"?}},
  "recebidas"*: {jid: ordens}, "ultimas"*: {jid: ordens}, "ultimo_plano"*: {jid: planos},
  "pular": [jid], "ia_nesta_semana": [jid], "planos_semana"*: {jid: planos}, "historico": [...],
  "sessao" (só no modo jogador, em memória): {"jogador", "acoes", "planos", "_chave"}}
  (* só no arquivo do comissário)
"""
import copy
import hashlib
import hmac
import json
import os
import random
import re
import secrets
import time
import unicodedata

from . import state, routines, acoes
from .event import planos as planos_evento
from .util import PASTA_DADOS

PASTA_LIGAS = os.path.join(PASTA_DADOS, "ligas")
POLITICAS = ("ia", "repetir", "bloquear")
FORMATO_ORDENS = "automanager-ordens"
SECRETOS = ("recebidas", "ultimas", "ultimo_plano", "planos_semana", "envios", "auto", "pasta_compartilhada")
ACOES_REPETIVEIS = ("dev_modo", "dev_investir")


class ErroLiga(Exception):
    pass


# ---------------------------------------------------------------- senhas e assinatura
def _derivar(senha, sal):
    return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(sal), 100_000).hex()


def _verificador(chave):
    return hashlib.sha256(("verificador:" + chave).encode()).hexdigest()


def _canonico(d):
    return json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _assinar(chave, dados):
    return hmac.new(bytes.fromhex(chave), _canonico(dados).encode("utf-8"), hashlib.sha256).hexdigest()


def _slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_") or "jogador"


# ---------------------------------------------------------------- liga
def criar_liga(st, nome, jogadores, politica="ia"):
    """jogadores: [{"nome", "categoria", "equipe" ou "nova_equipe": {"nome", "nacionalidade", "cor",
    "cor_secundaria"}, "senha"}]. Transforma o estado novo em liga (tudo ou nada)."""
    antes = {"categorias": copy.deepcopy(st["categorias"]), "noticias": list(st.get("noticias", []))}
    try:
        return _criar_liga(st, nome, jogadores, politica)
    except ErroLiga:
        st.update(antes)                         # desfaz equipes novas já criadas
        raise


def _criar_liga(st, nome, jogadores, politica):
    if politica not in POLITICAS:
        raise ErroLiga("Política inválida.")
    if not nome.strip():
        raise ErroLiga("Informe o nome da liga.")
    if not jogadores:
        raise ErroLiga("Inclua pelo menos um jogador.")
    vistos, js = set(), {}
    for j in jogadores:
        if not j.get("nome", "").strip() or not j.get("senha"):
            raise ErroLiga("Cada jogador precisa de nome e senha.")
        if j.get("nova_equipe"):
            # vaga para equipe nova: quem cria (nome, país, cores) e faz o desenvolvimento inicial é o jogador,
            # ao abrir a liga – vai nas ordens dele (acoes 'criar_equipe' e 'dev_inicial')
            if j.get("categoria") not in st["categorias"]:
                raise ErroLiga(f"Categoria inválida para {j['nome']}.")
            j = dict(j, equipe=None)
        else:
            eq = st["categorias"].get(j["categoria"], {}).get("equipes", {}).get(j.get("equipe"))
            if not eq or not eq.get("ativa"):
                raise ErroLiga(f"Equipe inválida para {j['nome']}.")
            if (j["categoria"], j["equipe"]) in vistos:
                raise ErroLiga(f"A {eq['nome']} foi escolhida por mais de um jogador.")
            vistos.add((j["categoria"], j["equipe"]))
        jid, n = _slug(j["nome"]), 1
        while jid in js:
            n += 1
            jid = f"{_slug(j['nome'])}{n}"
        sal = secrets.token_hex(16)
        chave = _derivar(j["senha"], sal)
        js[jid] = {"nome": j["nome"].strip(), "categoria": j["categoria"], "equipe": j["equipe"], "sal": sal,
                   "chave": chave, "verificador": _verificador(chave)}
    st["multiplayer"] = {"id": secrets.token_hex(8), "nome": nome.strip(), "politica": politica,
                         "papel": "comissario", "criada_em": time.strftime("%Y-%m-%d %H:%M"), "jogadores": js,
                         "recebidas": {}, "ultimas": {}, "ultimo_plano": {}, "pular": [], "historico": []}
    st["usuario"] = {"categoria": None, "equipe": None}
    for j in js.values():
        if not j["equipe"]:
            state.noticia(st, f"{j['nome']} entra na liga {nome.strip()} com uma equipe nova na "
                              f"{st['categorias'][j['categoria']]['categoria']['nome']}.", j["categoria"], "usuario")
            continue
        eq = st["categorias"][j["categoria"]]["equipes"][j["equipe"]]
        state.noticia(st, f"{j['nome']} assume o comando da {eq['nome']} na liga {nome.strip()}.", j["categoria"],
                      "usuario", equipe=j["equipe"])
    return st["multiplayer"]


def jogadores_ativos(st):
    return {jid: j for jid, j in st["multiplayer"]["jogadores"].items() if not j.get("eliminado")}


def nome_arquivo(st, sufixo):
    mp = st["multiplayer"]
    return f"{_slug(mp['nome'])}_{st['ano']}_s{st['semana']:02d}_{sufixo}.json"


def salvar_liga(st, caminho):
    """Arquivo completo do comissário (com senhas derivadas e ordens recebidas)."""
    os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, caminho)
    return caminho


def carregar_liga(caminho):
    st = state.carregar(caminho)
    if not st.get("multiplayer"):
        raise ErroLiga("Este arquivo não é de uma liga multijogador.")
    soma = st["multiplayer"].pop("checksum_liga", None)
    if soma is not None:
        st.pop("nome_save", None)
        if _hash(st) != soma:
            raise ErroLiga("Checksum do arquivo da liga não confere: o arquivo foi alterado ou corrompido.")
        st["nome_save"] = os.path.splitext(os.path.basename(caminho))[0]
    return st


def versao_jogadores(st):
    """Cópia para distribuir: sem as chaves dos jogadores e sem as ordens recebidas."""
    d = copy.deepcopy(st)
    mp = d["multiplayer"]
    for k in SECRETOS:
        mp.pop(k, None)
    mp.pop("sessao", None)
    for j in mp["jogadores"].values():
        j.pop("chave", None)
    mp["papel"] = "jogador"
    return d


def exportar_para_jogadores(st, caminho):
    d = versao_jogadores(st)
    d["multiplayer"]["checksum_liga"] = _hash({k: v for k, v in d.items() if k != "nome_save"})
    return salvar_liga(d, caminho)


# ---------------------------------------------------------------- modo jogador
def entrar(st_liga, jid, senha):
    """Abre a liga como jogador: devolve uma cópia do estado com a equipe dele como 'usuário' e a sessão
    que grava as ações. Levanta ErroLiga se a senha não confere."""
    mp = st_liga.get("multiplayer") or {}
    j = mp.get("jogadores", {}).get(jid)
    if not j:
        raise ErroLiga("Jogador não encontrado.")
    if j.get("eliminado"):
        raise ErroLiga("Este jogador está fora da liga.")
    chave = _derivar(senha, j["sal"])
    if not hmac.compare_digest(_verificador(chave), j["verificador"]):
        raise ErroLiga("Senha incorreta.")
    st = versao_jogadores(st_liga)
    st["usuario"] = {"categoria": j["categoria"], "equipe": j["equipe"]}
    st["multiplayer"]["sessao"] = {"jogador": jid, "acoes": [], "planos": {}, "_chave": chave}
    return st


def entrar_com_chave(st_liga, jid, chave):
    """Reabre a liga (nova semana da pasta compartilhada) com a chave já derivada da senha na sessão atual."""
    j = (st_liga.get("multiplayer") or {}).get("jogadores", {}).get(jid)
    if not j or j.get("eliminado") or not hmac.compare_digest(_verificador(chave), j["verificador"]):
        raise ErroLiga("Não foi possível reabrir a liga com este jogador.")
    st = versao_jogadores(st_liga)
    st["usuario"] = {"categoria": j["categoria"], "equipe": j["equipe"]}
    st["multiplayer"]["sessao"] = {"jogador": jid, "acoes": [], "planos": {}, "_chave": chave}
    return st


def sessao(st):
    return (st.get("multiplayer") or {}).get("sessao")


# ---------------------------------------------------------------- integridade
CAMPOS_ORDENS = ("formato", "versao", "liga", "jogador", "equipe", "ano", "semana", "acoes", "planos", "resultado_esperado",
                 "checksum", "assinatura")


def _hash(d):
    return hashlib.sha256(_canonico(d).encode("utf-8")).hexdigest()


def impressao_equipe(st, cid, eid):
    """Resumo (SHA-256) de tudo o que as ordens de uma equipe podem mudar: caixa e finanças, contratos de
    chassis/motor, projetos e valores do carro, empréstimos, pilotos com contrato (atual e futuro), propostas
    pendentes (a pilotos e a fornecedores), patrocinadores e ofertas de patrocínio da equipe. Notícias ficam de fora."""
    c = st["categorias"][cid]
    if not eid:
        return _hash({"sem_equipe": cid})        # vaga de equipe nova ainda não criada pelo jogador
    eq = c["equipes"][eid]

    def da_equipe(ct):
        return bool(ct) and ct.get("categoria", cid) == cid and ct.get("equipe") == eid
    dados = {
        "equipe": eq,
        "pilotos": {pid: [p.get("contrato"), p.get("contrato_futuro")] for pid, p in st["pilotos"].items()
                    if da_equipe(p.get("contrato")) or da_equipe(p.get("contrato_futuro"))},
        "propostas": {k: v for k, v in st.get("propostas_usuario", {}).items()
                      if v.get("equipe") == eid and v.get("categoria") == cid},
        "propostas_partes": {k: v for k, v in st.get("propostas_partes", {}).items()
                             if v.get("equipe") == eid and v.get("categoria") == cid},
        "patrocinadores": {k: v.get("contrato") for k, v in c["patrocinadores"].items()
                           if (v.get("contrato") or {}).get("equipe") == eid},
        "ofertas": [o for o in st.get("ofertas_patrocinio", []) if o.get("equipe") == eid and o.get("categoria") == cid],
        "chassis": {k: v for k, v in c["chassis"].items() if v.get("equipe") == eid},
        "motores": {k: v for k, v in c["motores"].items() if (v.get("fabricante") or {}).get("equipe") == eid},
    }
    return _hash(dados)


def _planos_enxutos(st, planos):
    """Só o que o comissário precisa: eventos desta semana da categoria do jogador, pilotos inscritos da equipe,
    grupos de sessão do evento (teste coletivo = só 'treino'), valores já normalizados."""
    from .event.inscritos import montar_inscritos
    u = st["usuario"]
    c = st["categorias"][u["categoria"]]
    comp = _compostos(st, u["categoria"])
    troca = c["categoria"]["regras_pitstop"].get("troca_de_pneus", True)
    out = {}
    for ev in c["calendario"]:
        if ev["id"] not in planos or ev["semana"] != st["semana"] or not ev.get("ativo"):
            continue
        meus = {i["piloto"]["id"] for i in montar_inscritos(st, u["categoria"], u["equipe"], ev) if i["usuario"]}
        grupos = ("treino",) if ev["especie"] == "treino" else planos_evento.GRUPOS
        por_piloto = {}
        for pid, pl in planos[ev["id"]].items():
            if pid in meus:
                n = planos_evento.normalizar({g: pl[g] for g in grupos if g in (pl or {})}, comp, troca)
                if n:
                    por_piloto[pid] = n
        if por_piloto:
            out[ev["id"]] = por_piloto
    return out


def ordens_da_sessao(st):
    """Arquivo de ordens: só o necessário para reproduzir as decisões no jogo do comissário (ações de gestão e
    plano dos eventos da semana), o resumo do resultado que o jogador viu, checksum e assinatura."""
    s = sessao(st)
    mp = st["multiplayer"]
    u = st["usuario"]
    eq = st["categorias"][u["categoria"]]["equipes"].get(u.get("equipe")) or {}
    dados = {"formato": FORMATO_ORDENS, "versao": 3, "liga": mp["id"], "jogador": s["jogador"],
             "equipe": {"id": eq.get("id"), "nome": eq.get("nome")}, "ano": st["ano"],
             "semana": st["semana"], "acoes": [dict(a) for a in s.get("acoes", [])],
             "planos": _planos_enxutos(st, s.get("planos", {})),
             "resultado_esperado": impressao_equipe(st, u["categoria"], u["equipe"])}
    dados["checksum"] = _hash(dados)
    dados["assinatura"] = _assinar(s["_chave"], dados)
    return dados


def salvar_ordens(st, caminho):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(ordens_da_sessao(st), f, ensure_ascii=False, indent=1)
    return caminho


def ler_ordens(caminho):
    try:
        with open(caminho, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError) as e:
        raise ErroLiga(f"Não foi possível ler {os.path.basename(caminho)}: {e}") from e
    if not isinstance(d, dict) or d.get("formato") != FORMATO_ORDENS:
        raise ErroLiga(f"{os.path.basename(caminho)} não é um arquivo de ordens.")
    return d


def retomar_ordens(st, dados):
    """No modo jogador: reaplica um arquivo de ordens já salvo desta semana (para continuar editando).
    Retorna a lista de erros."""
    s = sessao(st)
    mp = st["multiplayer"]
    if dados.get("liga") != mp["id"] or dados.get("jogador") != s["jogador"]:
        raise ErroLiga("Estas ordens são de outra liga ou de outro jogador.")
    if (dados.get("ano"), dados.get("semana")) != (st["ano"], st["semana"]):
        raise ErroLiga("Estas ordens são de outra semana.")
    erros = []
    for a in dados.get("acoes", []):
        e = acoes.executar(st, a["acao"], **{k: v for k, v in a.items() if k != "acao"})
        if e:
            erros.append(e)
    s["planos"] = copy.deepcopy(dados.get("planos") or {})
    return erros


# ---------------------------------------------------------------- comissário
def importar_ordens(st, dados):
    """Confere liga, jogador, semana e assinatura e guarda as ordens. Retorna o id do jogador."""
    mp = st["multiplayer"]
    if mp.get("papel") != "comissario":
        raise ErroLiga("Só o arquivo do comissário importa ordens.")
    if dados.get("liga") != mp["id"]:
        raise ErroLiga("As ordens são de outra liga.")
    jid = dados.get("jogador")
    j = mp["jogadores"].get(jid)
    if not j:
        raise ErroLiga("Jogador desconhecido.")
    if j.get("eliminado"):
        raise ErroLiga(f"{j['nome']} está fora da liga.")
    if (dados.get("ano"), dados.get("semana")) != (st["ano"], st["semana"]):
        raise ErroLiga(f"As ordens de {j['nome']} são da semana {dados.get('semana')}/{dados.get('ano')}; a liga "
                       f"está na semana {st['semana']}/{st['ano']}.")
    sobra = set(dados) - set(CAMPOS_ORDENS)
    if dados.get("versao") != 3 or sobra or any(k not in dados for k in CAMPOS_ORDENS):
        raise ErroLiga(f"O arquivo de ordens de {j['nome']} não está no formato esperado.")
    corpo = {k: v for k, v in dados.items() if k not in ("checksum", "assinatura")}
    if not hmac.compare_digest(_hash(corpo), str(dados["checksum"])):
        raise ErroLiga(f"Checksum não confere nas ordens de {j['nome']}: o arquivo foi alterado ou corrompido.")
    esperado = _assinar(j["chave"], {k: v for k, v in dados.items() if k != "assinatura"})
    if not hmac.compare_digest(esperado, str(dados.get("assinatura", ""))):
        raise ErroLiga(f"Assinatura inválida nas ordens de {j['nome']} (arquivo alterado ou senha diferente).")
    # reproduz as ações numa cópia: o resultado tem de ser exatamente o que o jogador viu
    copia = copy.deepcopy({k: v for k, v in st.items() if k != "noticias"})
    copia["noticias"] = []
    erros = []
    with acoes.como(copia, j["categoria"], j["equipe"]):
        for a in dados["acoes"]:
            e = acoes.aplicar(copia, a.get("acao"), a)
            if e:
                erros.append(e)
    eid = copia["multiplayer"]["jogadores"][jid]["equipe"]          # pode ter sido criada nestas ordens
    if not erros and (dados.get("equipe") or {}).get("id") != eid:
        erros.append("a equipe do arquivo não é a do jogador")
    if erros or impressao_equipe(copia, j["categoria"], eid) != dados["resultado_esperado"]:
        raise ErroLiga(f"As ordens de {j['nome']} não reproduzem o mesmo resultado no jogo do comissário "
                       f"(o jogador usou um arquivo da liga diferente do desta semana?)"
                       + (f": {'; '.join(erros)}" if erros else "."))
    mp["recebidas"][jid] = dados
    if jid in mp.get("pular", []):
        mp["pular"].remove(jid)
    return jid


def situacao(st):
    """Linhas para a tela do comissário: [(jid, jogador, equipe, estado)]."""
    mp = st["multiplayer"]
    out = []
    for jid, j in mp["jogadores"].items():
        eq = st["categorias"][j["categoria"]]["equipes"].get(j["equipe"]) or {"nome": "(equipe nova – o jogador cria)"}
        if j.get("eliminado"):
            est = "fora da liga"
        elif jid in mp.get("recebidas", {}):
            est = "ordens recebidas"
        elif jid in mp.get("pular", []):
            est = "pulado (IA nesta semana)"
        else:
            est = "aguardando"
        out.append((jid, j["nome"], eq.get("nome", "?"), est))
    return out


def faltando(st):
    mp = st["multiplayer"]
    return [jid for jid in jogadores_ativos(st) if jid not in mp.get("recebidas", {})]


def pular(st, jid):
    mp = st["multiplayer"]
    if jid not in mp.setdefault("pular", []):
        mp["pular"].append(jid)


def pode_rodar(st):
    mp = st["multiplayer"]
    if mp["politica"] != "bloquear":
        return True, []
    pend = [jid for jid in faltando(st) if jid not in mp.get("pular", [])]
    return not pend, pend


def planos_do_evento(st, cid, evento_id):
    """{piloto_id: plano} dos jogadores desta categoria para o evento (só pilotos da própria equipe)."""
    mp = st.get("multiplayer") or {}
    out = {}
    for jid, planos in (mp.get("planos_semana") or {}).items():
        j = mp["jogadores"].get(jid)
        if not j or j["categoria"] != cid or jid in (mp.get("ia_nesta_semana") or []):
            continue
        meus = {p["id"] for p in state.pilotos_da_equipe(st, cid, j["equipe"])}
        do_evento = planos.get(evento_id) or planos.get("*") or {}
        out.update({pid: pl for pid, pl in do_evento.items() if pid in meus})
    return out


def _compostos(st, cid):
    pn = st["categorias"][cid]["categoria"]["pneus"]
    return list(pn.get("compostos_disponiveis") or pn["compostos"])


def _dev_inicial_ia(st, j):
    """Jogador que não mandou ordens com a equipe ainda sem carro: a IA faz o desenvolvimento inicial (como nas
    equipes novas do PC: parte do orçamento no chassis e no motor próprios)."""
    from . import desenvolvimento
    cid = j["categoria"]
    if not j.get("equipe"):
        return                                   # o jogador ainda não criou a equipe
    eq = st["categorias"][cid]["equipes"][j["equipe"]]
    if not eq.get("dev_inicial_pendente"):
        return
    ch, mo = state.precisa_desenvolvimento_inicial(st, cid, eq["id"])
    if st["categorias"][cid]["categoria"].get("desenvolvimento"):
        for parte, ok, frac in (("chassis", ch, 0.35), ("motor", mo, 0.15)):
            if ok:
                desenvolvimento.construir_do_zero(st, cid, eq, parte, eq["financas"]["caixa"] * frac)
    else:
        from .db import ATRIBUTOS_CHASSIS
        base = state.config_dev_inicial(st, cid, "chassis")["atributo_base"]
        attrs = {k: base for k in ATRIBUTOS_CHASSIS} if ch else None
        pot = state.config_dev_inicial(st, cid, "motor")["atributo_base"] if mo else None
        state.aplicar_desenvolvimento_inicial(st, cid, eq["id"], attrs, pot, 0.0)
    eq.pop("dev_inicial_pendente", None)
    state.noticia(st, f"{eq['nome']}: sem ordens de {j['nome']}, a IA faz o desenvolvimento inicial do carro.", cid,
                  "usuario", equipe=eq["id"])


def _responder_curtas(st):
    """Equipes de jogadores abaixo do mínimo para a corrida desta semana: os pilotos respondem já às propostas."""
    from . import mercado
    for cid, eid, _f, _ev in mercado.equipes_curtas(st, humanas_apenas=True):
        mercado.responder_agora(st, cid, eid, random.Random(f"{st['ano']}|{st['semana']}|{cid}|{eid}"))


def _curtas_para_corrida(st, ordens, ia):
    """Simula numa cópia as ordens desta semana e as respostas imediatas dos pilotos: equipes de jogadores que
    continuariam abaixo do mínimo de titulares para a corrida desta semana ("Equipe (2 de 3)")."""
    from . import mercado
    if not any(mercado.minimo_pilotos(st, cid) and mercado.corridas_da_semana(st, cid) for cid in st["categorias"]):
        return []
    cp = copy.deepcopy(st)
    cp["multiplayer"]["ia_nesta_semana"] = list(ia)
    for jid in sorted(ordens):
        j = cp["multiplayer"]["jogadores"][jid]
        with acoes.como(cp, j["categoria"], j["equipe"]):
            for a in ordens[jid].get("acoes", []):
                acoes.aplicar(cp, a.get("acao"), a)
    _responder_curtas(cp)
    out = []
    for cid, eid, falta, ev in mercado.equipes_curtas(cp, humanas_apenas=True):
        minimo = mercado.minimo_pilotos(cp, cid)
        out.append(f"{cp['categorias'][cid]['equipes'][eid]['nome']} ({minimo - falta}/{minimo}, {ev['nome']})")
    return out


def rodar_semana(st, rng=random):
    """Aplica as ordens e avança uma semana. Retorna {"noticias", "erros", "ia", "repetidas", "recebidas"}."""
    mp = st["multiplayer"]
    ok, pend = pode_rodar(st)
    if not ok:
        nomes = ", ".join(mp["jogadores"][j]["nome"] for j in pend)
        raise ErroLiga(f"Faltam as ordens de: {nomes}. (Política: bloquear – importe ou pule o jogador.)")
    ativos = jogadores_ativos(st)
    ordens, ia, repetidas = {}, [], []
    for jid in ativos:
        if jid in mp["recebidas"]:
            ordens[jid] = mp["recebidas"][jid]
        elif jid in mp.get("pular", []) or mp["politica"] == "ia":
            ia.append(jid)
        elif mp["politica"] == "repetir" and (mp["ultimas"].get(jid) or mp["ultimo_plano"].get(jid)):
            ult = mp["ultimas"].get(jid) or {}
            ordens[jid] = {"acoes": [a for a in ult.get("acoes", []) if a.get("acao") in ACOES_REPETIVEIS],
                           "planos": {"*": mp["ultimo_plano"].get(jid, {})}}
            repetidas.append(jid)
        else:
            ia.append(jid)
    curtas = _curtas_para_corrida(st, ordens, ia)
    if curtas:
        raise ErroLiga("Equipes abaixo do mínimo de pilotos titulares para a corrida desta semana: "
                       + "; ".join(curtas) + ". (Os jogadores precisam contratar – Mercado > Pilotos – e mandar as "
                       "ordens de novo; os pilotos respondem na hora.)")
    mp["ia_nesta_semana"] = ia
    for jid in ia:
        _dev_inicial_ia(st, mp["jogadores"][jid])
    erros = []
    ordem = sorted(ordens)
    rng.shuffle(ordem)                              # quem age primeiro no mercado é sorteado a cada semana
    planos_semana = {}
    for jid in ordem:
        j = mp["jogadores"][jid]
        d = ordens[jid]
        with acoes.como(st, j["categoria"], j["equipe"]):
            for a in d.get("acoes", []):
                e = acoes.aplicar(st, a.get("acao"), a)
                if e:
                    erros.append((jid, a.get("acao"), e))
                    state.noticia(st, f"Ordem não executada ({j['nome']}): {e}", j["categoria"], "usuario",
                                  equipe=j["equipe"])
        comp = _compostos(st, j["categoria"])
        troca = st["categorias"][j["categoria"]]["categoria"]["regras_pitstop"].get("troca_de_pneus", True)
        planos_semana[jid] = {ev: {pid: planos_evento.normalizar(pl, comp, troca) for pid, pl in por_piloto.items()}
                              for ev, por_piloto in (d.get("planos") or {}).items()}
        if jid in mp["recebidas"]:
            mp["ultimas"][jid] = d
            novos = {}
            for por_piloto in planos_semana[jid].values():
                novos.update(por_piloto)
            if novos:
                mp["ultimo_plano"][jid] = dict(mp["ultimo_plano"].get(jid, {}), **novos)
    mp["planos_semana"] = planos_semana
    _responder_curtas(st)
    semana, ano = st["semana"], st["ano"]
    try:
        noticias = routines.avancar_semana(st, rng)
    finally:
        mp["planos_semana"] = {}
        mp["ia_nesta_semana"] = []
    rec = sorted(mp["recebidas"])
    mp["recebidas"] = {}
    mp["pular"] = []
    mp.setdefault("historico", []).append({"ano": ano, "semana": semana, "recebidas": rec, "ia": ia,
                                           "repetidas": repetidas, "erros": len(erros)})
    return {"noticias": noticias, "erros": erros, "ia": ia, "repetidas": repetidas, "recebidas": rec}
