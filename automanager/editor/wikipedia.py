"""Importa uma categoria/temporada da Wikipedia em inglês – qualquer série, qualquer época.

Procura na página da temporada, por sinônimos de cabeçalho:
  inscritos     equipe (Constructor > Team > Entrant), chassis (Chassis/Car), motor (Engine/Power unit/
                Powertrain), piloto (Driver/Driver name/Drivers), rodadas (Rounds)
  calendário    rodada (Round/Rd.) + circuito (Circuit/Track/Venue) + data
  classificação de pilotos e de equipes (para estimar atributos) e sistema de pontuação
Sem coluna de chassis e/ou motor, a categoria é tratada como monomarca (fornecedor único, sem
desenvolvimento). O que a Wikipedia não tem recebe estimativas/valores padrão para ajuste no editor.
"""
import copy
import datetime
import json
import random
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import time

from .tabelas_html import extrair_tabelas
from ..db import ATRIBUTOS_PILOTO, ATRIBUTOS_CHASSIS

API = "https://en.wikipedia.org/w/api.php"
AGENTE = "AutoManager/0.1 (editor de database do jogo; importacao de temporadas)"

from ..paises import PAISES  # noqa: E402  (inglês -> português)
MESES = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}
SINONIMOS = {
    "equipe": [("constructor",), ("team",), ("entrant",)],
    "entrant": [("entrant",), ("team",)],
    "chassis": [("chassis",), ("car",)],
    "motor": [("power unit",), ("powertrain",), ("engine",)],
    "piloto": [("driver name",), ("driver",)],
    "rodadas": [("round",)],
}
NAO_EQUIPE = ("no.", "round", "driver", "engine", "chassis", "tyre", "car", "power", "pos")


class ErroImportacao(Exception):
    pass


# ---------------------------------------------------------------- acesso à Wikipedia
def _get(params, timeout=25, tentativas=4):
    """Chamada à API. Se a Wikipedia pedir para esperar (429), espera e tenta de novo algumas vezes."""
    q = urllib.parse.urlencode(dict(params, format="json", formatversion="2"))
    corpo = ""
    for n in range(tentativas):
        req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": AGENTE})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                corpo = r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 429 and n < tentativas - 1:
                _esperar(e.headers.get("Retry-After"), n)
                continue
            if e.code == 429:
                raise ErroImportacao("A Wikipedia pediu para esperar (muitas requisições). Tente de novo em alguns "
                                     "minutos.") from e
            raise ErroImportacao(f"Falha ao acessar a Wikipedia: {e}") from e
        except OSError as e:
            raise ErroImportacao(f"Falha ao acessar a Wikipedia (verifique a internet): {e}") from e
        if "too many requests" in corpo.lower()[:200]:
            if n < tentativas - 1:
                _esperar(None, n)
                continue
            raise ErroImportacao("A Wikipedia pediu para esperar (muitas requisições). Tente de novo em alguns "
                                 "minutos.")
        break
    try:
        return json.loads(corpo)
    except ValueError as e:
        raise ErroImportacao("Resposta inesperada da Wikipedia.") from e


def _esperar(retry_after, n):
    try:
        t = float(retry_after)
    except (TypeError, ValueError):
        t = 2.0 * 2 ** n
    time.sleep(max(1.0, min(t, 20.0)))


def titulo_sugerido(ano, serie="Formula One"):
    return f"{ano} {serie} World Championship" if serie == "Formula One" else f"{ano} {serie}"


def buscar_titulos(texto, limite=8):
    """Busca páginas pelo texto (ex.: '2023 IndyCar'). Retorna lista de títulos."""
    d = _get({"action": "query", "list": "search", "srsearch": texto, "srlimit": limite})
    return [r["title"] for r in d.get("query", {}).get("search", [])]


def baixar_html(titulo_ou_url, timeout=25):
    titulo = titulo_ou_url.strip()
    if "wikipedia.org/wiki/" in titulo:
        titulo = urllib.parse.unquote(titulo.split("/wiki/", 1)[1]).split("#")[0]
    d = _get({"action": "parse", "page": titulo.replace(" ", "_"), "prop": "text", "redirects": "1"}, timeout)
    if "error" in d:
        raise ErroImportacao(f"Página não encontrada: {d['error'].get('info', titulo)}")
    return d["parse"]["text"]


# ---------------------------------------------------------------- utilidades
def _norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _slug(s):
    return re.sub(r"\s+", "_", _norm(s))[:30] or "x"


def _limpa(s):
    s = re.sub(r"\[[^\]]*\]", "", s or "")
    return re.sub(r"\s*[†‡*^§#]+\s*$", "", s.strip()).strip()


def _pais(nome_en):
    return PAISES.get(nome_en, nome_en) if nome_en else ""


def _cabecalhos(t):
    """Nome de cada coluna juntando as linhas de cabeçalho (ignora linhas de seção que ocupam a tabela toda)."""
    n = max(len(l) for l in t["grade"]) if t["grade"] else 0
    linhas = [l for l in t["grade"][:max(1, t["cabecalho_linhas"])] if len(set(l)) > 1 or len(l) == 1]
    nomes = []
    for c in range(n):
        partes = []
        for l in linhas or t["grade"][:1]:
            if c < len(l) and l[c] not in partes:
                partes.append(l[c])
        nomes.append(" ".join(partes).lower())
    return nomes


def _col(cab, *chaves, excluir=()):
    for i, h in enumerate(cab):
        if all(k in h for k in chaves) and not any(x in h for x in excluir):
            return i
    return None


def _col_sin(cab, tipo, excluir=()):
    for chaves in SINONIMOS[tipo]:
        i = _col(cab, *chaves, excluir=excluir)
        if i is not None:
            return i
    return None


def _linhas(t, com_links=False):
    """Linhas de dados (sem cabeçalho nem linhas de seção que repetem o mesmo texto).
    com_links=True: (texto, países, links) – links de cada célula: [(texto do link, título do artigo)]."""
    out = []
    c = t["cabecalho_linhas"]
    links = t.get("links") or [[] for _ in t["grade"]]
    for l, pp, ll in zip(t["grade"][c:], t["paises"][c:], links[c:]):
        if len(l) > 2 and len(set(l)) == 1:
            continue
        out.append((l, pp, ll) if com_links else (l, pp))
    return out


def _artigo(ll, i, texto=None):
    """Título do artigo linkado na célula i (o do texto informado, se houver; senão o primeiro)."""
    if i is None or i >= len(ll) or not ll[i]:
        return None
    if texto:
        alvo = _norm(texto)
        for txt, tit in ll[i]:
            n = _norm(txt)
            if n and (n == alvo or alvo.startswith(n) or n.startswith(alvo)):
                return tit
        return None
    return ll[i][0][1]


def _contar_rodadas(txt, total):
    txt = (txt or "").strip().lower()
    if not txt or txt.startswith("all"):
        return total
    n = 0
    for parte in re.split(r"[,;]", txt):
        nums = [int(x) for x in re.findall(r"\d+", parte)]
        if len(nums) >= 2:
            n += abs(nums[1] - nums[0]) + 1
        elif nums:
            n += 1
    return n or total


def _lista_rodadas(txt, total):
    """Rodadas disputadas como conjunto de números ('1–10, 13' -> {1..10, 13}); None = todas ou não informado."""
    txt = (txt or "").strip().lower()
    if not txt or txt.startswith("all"):
        return None
    out = set()
    for parte in re.split(r"[,;]", txt):
        nums = [int(x) for x in re.findall(r"\d+", parte)]
        if len(nums) >= 2:
            a, b = sorted(nums[:2])
            out.update(range(a, b + 1))
        elif nums:
            out.add(nums[0])
    out = {r for r in out if 1 <= r <= total}
    return out if out and len(out) < total else None


def _semana(data_txt, ano):
    t = (data_txt or "").lower()
    mes = next((v for k, v in MESES.items() if k in t or k[:3] in re.findall(r"[a-z]+", t)), None)
    dias = re.findall(r"\b(\d{1,2})\b", t)
    if not dias or not mes:
        return None
    try:
        return datetime.date(int(ano), mes, int(dias[-1])).isocalendar()[1]
    except ValueError:
        return None


def _separar_construtor(txt):
    partes = re.split(r"\s*[-–]\s*", txt, maxsplit=1)
    return (partes[0], partes[1]) if len(partes) == 2 else (txt, None)


# ---------------------------------------------------------------- localizar tabelas
def _tabelas_validas(tabelas):
    for t in tabelas:
        if "wikitable" in t["classe"] and len(t["grade"]) >= 3:
            yield t, _cabecalhos(t)


def _achar_inscritos(tabelas):
    melhor = None
    for t, cab in _tabelas_validas(tabelas):
        if _col_sin(cab, "piloto", excluir=("pos",)) is None:
            continue
        if _col_sin(cab, "equipe", excluir=NAO_EQUIPE[:3]) is None:
            continue
        if _col(cab, "pos") is not None and _col(cab, "pos") == 0:
            continue                                  # é uma classificação
        if any(k in h for h in cab for k in ("winning", "winner", "pole", "fastest")):
            continue                                  # é o resumo de resultados
        if "practice" in t["secao"].lower() or "test" in t["secao"].lower():
            continue
        pontos = len(_linhas(t)) + (5 if _col_sin(cab, "chassis") is not None else 0)
        if melhor is None or pontos > melhor[0]:
            melhor = (pontos, t, cab)
    return (melhor[1], melhor[2]) if melhor else (None, None)


def _achar_calendario(tabelas):
    candidatas = []
    for t, cab in _tabelas_validas(tabelas):
        tem_rodada = any(h.startswith(("round", "rd")) for h in cab)
        tem_local = any(k in h for h in cab for k in ("circuit", "track", "venue"))
        if not (tem_rodada and tem_local) or any("pole" in h for h in cab):
            continue
        sec = t["secao"].lower()
        prioridade = 0 if ("calendar" in sec or "schedule" in sec) else 1
        candidatas.append((prioridade, t, cab))
    if not candidatas:   # sem calendário próprio: usa o resumo de resultados
        for t, cab in _tabelas_validas(tabelas):
            if any(h.startswith(("round", "rd")) for h in cab) and any("pole" in h for h in cab):
                candidatas.append((2, t, cab))
    candidatas.sort(key=lambda x: x[0])
    return (candidatas[0][1], candidatas[0][2]) if candidatas else (None, None)


def _achar_classificacao(tabelas, de_pilotos):
    melhor = None
    for t, cab in _tabelas_validas(tabelas):
        if not cab or not cab[0].startswith("pos"):
            continue
        sec = t["secao"].lower()
        if de_pilotos:
            if _col(cab, "driver") is None:
                continue
            nota = 0 if ("driver" in sec and not any(x in sec for x in ("independent", "trophy", "rookie", "award",
                                                                          "jack"))) else 1
        else:
            if _col_sin(cab, "equipe", excluir=("driver",)) is None and _col(cab, "manufacturer") is None:
                continue
            if any(x in sec for x in ("independent", "trophy", "award", "engine", "manufacturer")):
                nota = 2
            elif any(x in sec for x in ("constructor", "team", "entrant")):
                nota = 0
            else:
                nota = 1
        if melhor is None or nota < melhor[0]:
            melhor = (nota, t, cab)
    return (melhor[1], melhor[2]) if melhor else (None, None)


def _classificacao(t, cab, coluna_tipo):
    """[(nome, pontos)] na ordem da tabela."""
    out, vistos = [], set()
    i_nome = _col(cab, "driver") if coluna_tipo == "piloto" else \
        (_col_sin(cab, "equipe", excluir=("driver",)) if _col_sin(cab, "equipe", excluir=("driver",)) is not None
         else _col(cab, "manufacturer"))
    i_pts = next((i for i in range(len(cab) - 1, -1, -1) if "point" in cab[i] or "pts" in cab[i]), len(cab) - 1)
    for l, _ in _linhas(t):
        if i_nome is None or i_nome >= len(l) or not re.match(r"^\s*(\d+|=?\d+|nc|ex|dsq|—|-)", l[0].lower() or ""):
            continue
        nome = _limpa(l[i_nome].split("\n")[0])
        if not nome or nome.lower().startswith(("pos", "key", "source")) or nome in vistos:
            continue
        pts = re.findall(r"[\d.]+", l[i_pts]) if i_pts < len(l) else []
        vistos.add(nome)
        out.append((nome, float(pts[0]) if pts else 0.0))
    return out


def _pontuacao(tabelas):
    """Sistema de pontuação: {"posicoes": [...], "pole": n, "volta_mais_rapida": n} ou None.
    Com várias tabelas/linhas (ex.: sprint e corrida principal), fica com a da corrida principal
    (a de mais posições pontuadas, evitando 'sprint')."""
    candidatas = []
    for t in tabelas:
        if "wikitable" not in t["classe"] or len(t["grade"]) < 2:
            continue
        cab = [c.lower() for c in t["grade"][0]]
        if not any("1st" in c for c in cab):
            continue
        sprint_na_secao = "sprint" in t["secao"].lower()
        for l in t["grade"][1:]:
            rot = l[0].lower()
            if not rot.startswith(("race", "points", "feature", "pts", "position", "main", "sprint")):
                continue
            pos, pole, vr = [], 0, 0
            for h, c in zip(cab[1:], l[1:]):
                v = c.strip()
                if not re.match(r"^\d+$", v):
                    continue
                if re.match(r"^\d+(st|nd|rd|th)", h):
                    pos.append(int(v))
                elif "pole" in h:
                    pole = int(v)
                elif h in ("fl", "fastest lap") or "fastest" in h:
                    vr = int(v)
            if len(pos) >= 3 and pos[0] > pos[1]:
                prioridade = 1 if ("sprint" in rot or sprint_na_secao) else 0
                candidatas.append((prioridade, -len(pos), -pos[0],
                                   {"posicoes": pos, "pole": pole, "volta_mais_rapida": vr}))
    if not candidatas:
        return None
    return min(candidatas, key=lambda x: x[:3])[3]


# ---------------------------------------------------------------- importação
def importar(html, ano, cid, nome, modelo, semente=None):
    """Monta um arquivo de database completo. `modelo`: dict de um arquivo existente (regras copiadas).
    Retorna (dados, avisos)."""
    rng = random.Random(semente if semente is not None else ano)
    avisos = []
    tabelas = extrair_tabelas(html)
    t_ent, cab_ent = _achar_inscritos(tabelas)
    if not t_ent:
        raise ErroImportacao("Não encontrei a tabela de equipes e pilotos (colunas de equipe e de piloto).")
    t_cal, cab_cal = _achar_calendario(tabelas)
    t_pil, cab_pil = _achar_classificacao(tabelas, True)
    t_con, cab_con = _achar_classificacao(tabelas, False)

    calendario = _importar_calendario(t_cal, cab_cal, ano, avisos)
    total_rodadas = len(calendario) or 20

    pil_cls = _classificacao(t_pil, cab_pil, "piloto") if t_pil else []
    con_cls = _classificacao(t_con, cab_con, "equipe") if t_con else []
    if not pil_cls:
        avisos.append("Classificação de pilotos não encontrada: atributos dos pilotos ficaram no valor médio.")
    if not con_cls:
        avisos.append("Classificação de equipes não encontrada: atributos dos carros ficaram no valor médio.")

    equipes, chassis, motores, pilotos, rodadas, info = _importar_inscritos(
        t_ent, cab_ent, pil_cls, con_cls, total_rodadas, rng, avisos)

    cat = copy.deepcopy(modelo["categoria"])
    cat.update({"id": cid, "nome": nome, "ano": int(ano)})
    regras = cat["regras"]
    regras["desenvolvimento_chassis_por_equipe"] = not info["chassis_monomarca"]
    proprios = [e["id"] for e in equipes.values() if (e.get("motor") or {}).get("origem") == "proprio"]
    regras["desenvolvimento_motor_por_equipe"] = bool(proprios)
    regras["equipes_com_desenvolvimento_de_motor"] = proprios
    regras["fontes_de_motor_permitidas"] = ["proprio", "equipe", "fabricante"] if proprios else ["equipe", "fabricante"]
    if not regras["desenvolvimento_chassis_por_equipe"] and not proprios:
        cat["desenvolvimento"] = None
        avisos.append("Categoria monomarca (chassis e motores de fornecedores): sem desenvolvimento por equipe.")
    pts = _pontuacao(tabelas)
    if pts:
        cat["pontuacao"].update(pts)
    else:
        avisos.append("Sistema de pontuação não encontrado em tabela: mantido o do arquivo modelo.")

    _contratos_pilotos(regras, cat, pilotos, rodadas, total_rodadas,
                       {e["_rodada"]: e["id"] for e in calendario})
    for e in calendario:
        e.pop("_rodada", None)
    for e in equipes.values():
        e.pop("_tmp", None)
    dados = {"versao_formato": 1, "categoria": cat, "pilotos": list(pilotos.values()), "chassis": list(chassis.values()),
             "motores": list(motores.values()), "equipes": list(equipes.values()), "patrocinadores": [],
             "calendario": calendario, "_importado_de": "Wikipedia (en)"}
    avisos.append("Idade dos pilotos, dados das pistas (tempo base, voltas, retas/curvas, desgaste, chuva) e "
                  "patrocinadores não vêm da Wikipedia: ajuste no editor.")
    return dados, avisos


def _importar_calendario(t_cal, cab, ano, avisos):
    calendario = []
    if not t_cal:
        avisos.append("Calendário não encontrado: adicione as corridas no editor.")
        return calendario
    i_rod = next(i for i, h in enumerate(cab) if h.startswith(("round", "rd")))
    i_circ = next((i for i, h in enumerate(cab) if any(k in h for k in ("circuit", "track", "venue"))), None)
    i_nome = next((i for i, h in enumerate(cab) if any(k in h for k in ("grand prix", "eprix", "race name", "event"))
                   and i != i_rod), None)
    if i_nome is None:
        i_nome = next((i for i, h in enumerate(cab) if h.startswith("race") and "date" not in h and i != i_rod), None)
    i_data = next((i for i, h in enumerate(cab) if "date" in h), None) or \
        next((i for i, h in enumerate(cab) if "feature" in h or "race 2" in h), None) or \
        next((i for i, h in enumerate(cab) if "sprint" in h), None)
    i_local = next((i for i, h in enumerate(cab) if "location" in h), None)
    i_pais = next((i for i, h in enumerate(cab) if "country" in h), None)
    vistos = set()
    for l, pp, ll in _linhas(t_cal, True):
        rod = re.findall(r"\d+", l[i_rod] if i_rod < len(l) else "")
        if not rod or rod[0] in vistos:
            continue
        vistos.add(rod[0])
        circ = _limpa(l[i_circ].split("\n")[0]) if i_circ is not None and i_circ < len(l) else ""
        nome = _limpa(l[i_nome].split("\n")[0]) if i_nome is not None and i_nome < len(l) else ""
        if not nome or nome.lower() == circ.lower():
            nome = f"Etapa {rod[0]} – {circ.split(',')[0]}"
        local = _limpa(l[i_local]) if i_local is not None and i_local < len(l) else \
            (circ.split(",", 1)[-1].strip() if "," in circ else circ)
        pais = ""
        for i in (i_pais, i_circ, i_local, i_nome):
            if i is not None and i < len(pp) and pp[i]:
                pais = _pais(pp[i].split("\n")[0])
                break
        if not pais and i_pais is not None and i_pais < len(l):
            pais = _pais(_limpa(l[i_pais]))
        if pais and pais not in local:
            local = f"{local}, {pais}" if local else pais
        n = _norm(f"{circ} {nome}")
        tipo = "oval" if re.search(r"speedway|oval|superspeedway|raceway park", n) and "road" not in n else \
            "rua" if re.search(r"street|marina|city|monaco|baku|singapore|las vegas|jeddah|eprix|e prix", n) else "mista"
        sem = _semana(l[i_data], ano) if i_data is not None and i_data < len(l) else None
        artigo = _artigo(ll, i_circ)
        calendario.append({
            "id": f"ev{len(calendario) + 1:02d}", "_rodada": int(rod[0]), "nome": nome, "ativo": True,
            "semana": sem or (8 + 2 * len(calendario)), "especie": "corrida", "local": local or circ,
            "tipo_pista": tipo, "tempo_base_treino": 90.0, "tempo_base_corrida": 92.25, "voltas_corrida": 60,
            "retas": 70 if tipo == "oval" else 40, "curvas_alta": 30, "curvas_baixa": 0 if tipo == "oval" else 30,
            "desgaste_pneus": 50, "dificuldade": 50, "duracao_pitstop": 22.0, "prob_chuva": 0.2,
            "prob_inativar": 0.02, "prob_ativar": 0.0})
        if artigo:
            calendario[-1]["wikipedia"] = artigo
    semanas = [e["semana"] for e in calendario]
    if len(set(semanas)) != len(semanas):
        avisos.append("Algumas corridas caíram na mesma semana: confira as datas no editor.")
    return calendario


def _importar_inscritos(t_ent, cab, pil_cls, con_cls, total_rodadas, rng, avisos):
    i_eq = _col_sin(cab, "equipe", excluir=NAO_EQUIPE[:3])
    i_ent = _col_sin(cab, "entrant")
    i_ch = _col_sin(cab, "chassis", excluir=("no.",))
    i_mot = _col_sin(cab, "motor")
    i_pil = _col_sin(cab, "piloto", excluir=("no.", "round", "pos"))
    i_rod = _col_sin(cab, "rodadas")
    i_num = next((i for i, h in enumerate(cab) if h.split()[-1:] in (["no."], ["no"], ["number"], ["#"])
                  or h.endswith(" no.") or h == "no."), None)
    usa_construtor = "constructor" in cab[i_eq]
    # épocas com muitos inscritos particulares: a equipe é o inscrito e o construtor é o fornecedor do chassis
    modo_inscrito = False
    if usa_construtor and i_ent is not None and i_ent != i_eq:
        linhas = _linhas(t_ent)
        n_ent = len({_norm(l[i_ent].split("\n")[0]) for l, _ in linhas if i_ent < len(l)})
        n_con = len({_norm(l[i_eq].split("\n")[0]) for l, _ in linhas if i_eq < len(l)})
        modo_inscrito = n_ent > 1.3 * n_con

    def nota_rank(lista, nome, alto=92, baixo=55):
        nn = _norm(nome)
        for i, (n, _) in enumerate(lista):
            if _norm(n) == nn or (nn and (_norm(n).startswith(nn) or nn.startswith(_norm(n)))):
                return alto - (alto - baixo) * i / max(1, len(lista) - 1)
        return None

    equipes, chassis, motores, pilotos, rodadas = {}, {}, {}, {}, {}
    nomes_chassis, nomes_motor = {}, {}
    for l, pp, ll in _linhas(t_ent, True):
        if i_eq >= len(l) or not l[i_eq].strip():
            continue
        bruto = _limpa(l[i_eq].split("\n")[0])
        if _norm(bruto) in ("constructor", "team", "entrant", "sources", "source", ""):
            continue
        construtor = None
        if usa_construtor:
            construtor, marca = _separar_construtor(bruto)
            nome_eq = construtor
        else:
            nome_eq, marca = bruto, None
        if modo_inscrito:
            nome_eq = _limpa(l[i_ent].split("\n")[0]) or nome_eq
        eid = _slug(nome_eq)
        if eid not in equipes:
            nac = ""
            for i in (i_ent, i_eq):
                if i is not None and i < len(pp) and pp[i]:
                    nac = _pais(pp[i].split("\n")[0])
                    break
            nota = nota_rank(con_cls, bruto)
            if nota is None:
                nota = nota_rank(con_cls, nome_eq)
            nota = 70 if nota is None else nota
            ch_txt = _limpa(l[i_ch].split("\n")[-1]) if i_ch is not None and i_ch < len(l) else ""
            mot_txt = _limpa(l[i_mot].split("\n")[-1]) if i_mot is not None and i_mot < len(l) else ""
            if not marca and mot_txt:
                marca = mot_txt.split()[0]
            equipes[eid] = {"id": eid, "nome": nome_eq, "ativa": True, "nacionalidade": nac,
                            "recursos": int(max(20, min(99, 35 + (nota - 55) * 60 / 37))), "caixa": None,
                            "chassis": None, "motor": None, "prob_fechamento": 0.01, "prob_surgimento": 0.0,
                            "_tmp": {"nota": nota, "chassis": ch_txt, "motor": mot_txt, "marca": marca,
                                     "construtor": construtor, "numeros": set(),
                                     # logotipos: artigo da marca (construtor / fabricante do motor) quando houver
                                     "art_ch": (_artigo(ll, i_eq) if usa_construtor else None)
                                     or _artigo(ll, i_ch, ch_txt) or _artigo(ll, i_ch),
                                     "art_mo": (_artigo(ll, i_eq, marca) if usa_construtor and marca else None)
                                     or _artigo(ll, i_mot, mot_txt) or _artigo(ll, i_mot)}}
            artigo = _artigo(ll, i_ent if modo_inscrito else i_eq)
            if artigo:
                equipes[eid]["wikipedia"] = artigo
            if ch_txt:
                nomes_chassis.setdefault(_norm(ch_txt.split("\n")[0]), set()).add(eid)
            if marca:
                nomes_motor.setdefault(_norm(marca), set()).add(eid)
        if i_pil is None or i_pil >= len(l):
            continue
        if i_num is not None and i_num < len(l):
            equipes[eid]["_tmp"]["numeros"].update(x for x in re.findall(r"\d+", l[i_num]))
        # remove marcas da Wikipedia como "R" (estreante) no fim do nome
        nomes = [re.sub(r"\s+(R|\(R\)|RY|\(RY\))$", "", _limpa(x)) for x in l[i_pil].split("\n") if _limpa(x)]
        paises = (pp[i_pil] or "").split("\n")
        rods = (l[i_rod] if i_rod is not None and i_rod < len(l) else "").split("\n")
        for k, nome_p in enumerate(nomes):
            if re.match(r"^\d+$", nome_p) or len(nome_p) < 3:
                continue
            pid = _slug(nome_p)
            nac = paises[k] if k < len(paises) else ""
            n_rod = _contar_rodadas(rods[k] if k < len(rods) else (rods[-1] if rods else ""), total_rodadas)
            if pid not in pilotos:
                nota = nota_rank(pil_cls, nome_p)
                nota = 52 if nota is None else nota
                pilotos[pid] = {"id": pid, "nome": nome_p, "nacionalidade": _pais(nac), "idade": 27,
                                "atributos": {a: int(max(5, min(99, rng.gauss(nota, 5)))) for a in ATRIBUTOS_PILOTO},
                                "contrato": None}
                artigo = _artigo(ll, i_pil, nome_p)
                if artigo:
                    pilotos[pid]["wikipedia"] = artigo
            lista_rod = _lista_rodadas(rods[k] if k < len(rods) else (rods[-1] if rods else ""), total_rodadas)
            rodadas.setdefault(eid, []).append((n_rod, pid, lista_rod))
    if not equipes:
        raise ErroImportacao("Nenhuma equipe encontrada na tabela de inscritos.")
    from .. import cores
    usadas = []
    for e in equipes.values():
        prim, sec = cores.sugerir(_norm(e["nome"]), usadas)
        e["cor"] = prim
        if sec:
            e["cor_secundaria"] = sec
        usadas.append(prim)
    if all(not e["nacionalidade"] for e in equipes.values()):
        avisos.append("A página não informa a nacionalidade das equipes: preencha no editor.")

    # chassis: monomarca se não houver coluna ou se quase todas as equipes usam o mesmo
    chassis_monomarca = i_ch is None or (len(nomes_chassis) <= max(1, len(equipes) // 4) and len(equipes) > 3)
    if chassis_monomarca:
        lista_ch = sorted(nomes_chassis, key=lambda k: -len(nomes_chassis[k])) or ["padrao"]
        for k in lista_ch:
            exemplo = next((e["_tmp"]["chassis"] for e in equipes.values() if _norm(e["_tmp"]["chassis"]) == k), "")
            chid = f"ch_{_slug(k)}"
            chassis[chid] = {"id": chid, "nome": exemplo or "Chassis padrão", "nacionalidade": "", "equipe": None,
                             "atributos": {a: 70 for a in ATRIBUTOS_CHASSIS},
                             "contrato": {"valor_por_corrida": 50000, "temporadas": 1}}
        for e in equipes.values():
            chid = f"ch_{_slug(_norm(e['_tmp']['chassis']))}" if e["_tmp"]["chassis"] else f"ch_{_slug(lista_ch[0])}"
            if chid not in chassis:
                chid = next(iter(chassis))
            e["chassis"] = {"id": chid, "origem": "terceiros",
                            "contrato": {"valor_por_corrida": chassis[chid]["contrato"]["valor_por_corrida"],
                                         "temporadas": 1}}
    elif modo_inscrito:
        for e in equipes.values():
            con = e["_tmp"]["construtor"] or e["nome"]
            chid = f"ch_{_slug(con)}"
            dono = next((x["id"] for x in equipes.values() if _norm(con) and _norm(con) in _norm(x["nome"])), None)
            if chid not in chassis:
                nota_con = max(x["_tmp"]["nota"] for x in equipes.values() if (x["_tmp"]["construtor"] or x["nome"]) == con)
                chassis[chid] = {"id": chid, "nome": e["_tmp"]["chassis"] or con, "nacionalidade": e["nacionalidade"],
                                 "equipe": dono, "atributos": {a: int(max(5, min(99, rng.gauss(nota_con, 4))))
                                                              for a in ATRIBUTOS_CHASSIS},
                                 "contrato": {"valor_por_corrida": 60000, "temporadas": 1}}
            if dono == e["id"]:
                e["chassis"] = {"id": chid, "origem": "proprio"}
            else:
                e["chassis"] = {"id": chid, "origem": "terceiros",
                                "contrato": {"valor_por_corrida": 60000, "temporadas": 1}}
        avisos.append("Época com inscritos particulares: as equipes são os inscritos; o chassis vem do construtor.")
    else:
        for e in equipes.values():
            chid = f"ch_{e['id']}"
            chassis[chid] = {"id": chid, "nome": e["_tmp"]["chassis"] or f"{e['nome']} {e['_tmp']['nota']:.0f}",
                             "nacionalidade": e["nacionalidade"], "equipe": e["id"],
                             "atributos": {a: int(max(5, min(99, rng.gauss(e["_tmp"]["nota"], 4))))
                                           for a in ATRIBUTOS_CHASSIS}, "contrato": None}
            e["chassis"] = {"id": chid, "origem": "proprio"}

    # motores por marca; marca igual ao nome de uma equipe = motor da própria equipe
    if i_mot is None and not any(e["_tmp"]["marca"] for e in equipes.values()):
        motores["mot_padrao"] = {"id": "mot_padrao", "nome": "Motor padrão", "nacionalidade": "", "potencia": 70,
                                 "fabricante": {"tipo": "fabricante"},
                                 "exclusividade": {"exclusivo": False, "equipe": None},
                                 "contrato": {"valor_por_corrida": 40000, "temporadas": 1}}
        for e in equipes.values():
            e["motor"] = {"id": "mot_padrao", "origem": "fabricante",
                          "contrato": {"valor_por_corrida": 40000, "temporadas": 1}}
        avisos.append("Sem coluna de motor: criado um motor padrão único.")
    else:
        por_nome = {_norm(e["nome"]): e["id"] for e in equipes.values()}
        for e in equipes.values():
            marca = e["_tmp"]["marca"] or "padrao"
            mid = f"mot_{_slug(marca)}"
            m = motores.setdefault(mid, {"id": mid, "nome": e["_tmp"]["motor"] or marca, "nacionalidade": "",
                                         "potencia": 0, "fabricante": {"tipo": "fabricante"},
                                         "exclusividade": {"exclusivo": False, "equipe": None},
                                         "contrato": {"valor_por_corrida": 300000, "temporadas": 1}})
            m["potencia"] = max(m["potencia"], int(max(40, min(99, e["_tmp"]["nota"] + rng.uniform(-3, 3)))))
            dono = por_nome.get(_norm(marca))
            if dono and not chassis_monomarca:
                m["fabricante"] = {"tipo": "equipe", "equipe": dono}
                m["nacionalidade"] = equipes[dono]["nacionalidade"]
                m["contrato"]["valor_por_corrida"] = 450000
            if m["fabricante"]["tipo"] == "equipe" and m["fabricante"]["equipe"] == e["id"]:
                e["motor"] = {"id": mid, "origem": "proprio"}
            else:
                e["motor"] = {"id": mid, "origem": m["fabricante"]["tipo"],
                              "contrato": {"valor_por_corrida": m["contrato"]["valor_por_corrida"], "temporadas": 1}}
        # corrige quem foi registrado antes de o motor virar "de equipe"
        for e in equipes.values():
            m = motores[e["motor"]["id"]]
            fab = m["fabricante"]
            if fab["tipo"] == "equipe":
                e["motor"] = {"id": m["id"], "origem": "proprio"} if fab["equipe"] == e["id"] else \
                    {"id": m["id"], "origem": "equipe",
                     "contrato": {"valor_por_corrida": m["contrato"]["valor_por_corrida"], "temporadas": 1}}
    # artigos da Wikipedia de chassis e motores (para buscar os logotipos)
    for e in equipes.values():
        for parte, tabela, chave in (("chassis", chassis, "art_ch"), ("motor", motores, "art_mo")):
            ent = tabela.get((e.get(parte) or {}).get("id"))
            if ent is not None and not ent.get("wikipedia") and e["_tmp"].get(chave):
                ent["wikipedia"] = e["_tmp"][chave]
    return equipes, chassis, motores, pilotos, rodadas, {"chassis_monomarca": chassis_monomarca}


def _contratos_pilotos(regras, cat, pilotos, rodadas, total_rodadas=None, rodada_para_id=None):
    """Quem correu a temporada toda é principal sem lista; quem correu só algumas etapas é principal com
    'corridas_definidas' (as etapas da coluna Rounds) – revezamento como na temporada real. Se numa etapa sobrar
    piloto (mais escalados que carros), sai quem não continua na etapa seguinte. Os demais: teste (se houver) ou livres.
    Um piloto que correu por duas equipes fica na equipe em que fez mais etapas."""
    n_princ = regras.get("pilotos_principais_por_equipe", 2)
    tem_teste = regras.get("pilotos_de_teste")
    n_teste = regras.get("pilotos_de_teste_por_equipe", 1) if tem_teste else 0
    mp = cat["simulacao"]["mercado_pilotos"]
    rodada_para_id = rodada_para_id or {}
    # carros por equipe = rodadas disputadas pela equipe ÷ rodadas da temporada (substitutos não somam carro)
    if total_rodadas:
        carros = [round(sum(x[0] for x in lista) / total_rodadas) for lista in rodadas.values()]
        if carros:
            n_princ = max(1, min(4, max(carros)))
            regras["pilotos_principais_por_equipe"] = n_princ
    # por piloto e equipe: total de etapas e conjunto (None = todas)
    por_eq = {}
    for eid, lista in rodadas.items():
        for n, pid, conj in lista:
            d = por_eq.setdefault(eid, {})
            if pid in d:
                n0, c0 = d[pid]
                d[pid] = (n0 + n, None if (c0 is None or conj is None) else c0 | conj)
            else:
                d[pid] = (n, conj)
    melhor_eq = {}
    for eid, d in por_eq.items():
        for pid, (n, _) in d.items():
            if pid not in melhor_eq or n > por_eq[melhor_eq[pid]][pid][0]:
                melhor_eq[pid] = eid

    def salario(p, sit):
        nota = sum(p["atributos"].values()) / len(p["atributos"])
        f = max(0.0, min(1.0, (nota - 40) / 55)) ** 2
        sal = mp["salario_minimo_por_corrida"] + (mp["salario_maximo_por_corrida"] - mp["salario_minimo_por_corrida"]) * f
        return round(sal, -3) if sit == "principal" else 10000

    for eid, d in por_eq.items():
        meus = sorted((pid for pid in d if melhor_eq[pid] == eid and pilotos[pid]["contrato"] is None),
                      key=lambda pid: -d[pid][0])
        usar_listas = bool(rodada_para_id) and any(d[pid][1] is not None for pid in meus)
        if not usar_listas:
            for i, pid in enumerate(meus):
                sit = "principal" if i < n_princ else "teste" if i < n_princ + n_teste else None
                if sit:
                    pilotos[pid]["contrato"] = {"equipe": eid, "valor_por_corrida": salario(pilotos[pid], sit),
                                                "temporadas": 1, "situacao": sit}
            continue
        fixos = [pid for pid in meus if d[pid][1] is None][:n_princ]
        parciais = {pid: {r for r in d[pid][1] if r in rodada_para_id} for pid in meus if d[pid][1] is not None}
        vaga = n_princ - len(fixos)
        for r in sorted(rodada_para_id):
            na_etapa = [pid for pid, conj in parciais.items() if r in conj]
            while len(na_etapa) > max(0, vaga):
                # sai primeiro quem não corre a etapa seguinte; depois, quem fez menos etapas
                sai = min(na_etapa, key=lambda pid: (r + 1 in parciais[pid], len(parciais[pid])))
                parciais[sai].discard(r)
                na_etapa.remove(sai)
        sobra = []
        for pid in meus:
            p = pilotos[pid]
            if pid in fixos:
                p["contrato"] = {"equipe": eid, "valor_por_corrida": salario(p, "principal"), "temporadas": 1,
                                 "situacao": "principal"}
            elif parciais.get(pid):
                ids = [rodada_para_id[r] for r in sorted(parciais[pid])]
                p["contrato"] = {"equipe": eid, "valor_por_corrida": salario(p, "principal"), "corridas": len(ids),
                                 "corridas_definidas": ids, "situacao": "principal"}
            else:
                sobra.append(pid)
        for pid in sobra[:n_teste]:
            pilotos[pid]["contrato"] = {"equipe": eid, "valor_por_corrida": salario(pilotos[pid], "teste"),
                                        "temporadas": 1, "situacao": "teste"}
