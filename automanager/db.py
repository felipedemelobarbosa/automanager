"""Leitura, descoberta e validação dos arquivos de database (JSON).

Organização:  database/<ano>/<categoria>_<ano>.json
Cada arquivo contém: categoria (definições gerais), pilotos, chassis, motores,
equipes, patrocinadores e calendário.
"""
import json
import os
import re

from .util import PASTA_DATABASE
from . import contratos

ATRIBUTOS_PILOTO = ["consistencia", "ritmo_corrida", "concentracao", "chuva", "aceleracao", "acerto_carro",
                    "trabalho_equipe", "classificacao", "fisico", "conducao", "largada"]
ATRIBUTOS_CHASSIS = ["aerodinamica", "grip", "cambio", "freio", "eletrica", "dirigibilidade", "confiabilidade",
                     "classificacao", "chuva", "pneus"]
ATRIBUTOS_MOTOR = ["potencia"]

NOMES_ATRIBUTOS = {
    "consistencia": "Consistência", "ritmo_corrida": "Ritmo de corrida", "concentracao": "Concentração",
    "chuva": "Chuva", "aceleracao": "Aceleração", "acerto_carro": "Acerto do carro",
    "trabalho_equipe": "Trabalho em equipe", "classificacao": "Classificação", "fisico": "Físico",
    "conducao": "Condução", "largada": "Largada", "aerodinamica": "Aerodinâmica", "grip": "Grip",
    "cambio": "Câmbio", "freio": "Freio", "eletrica": "Sistema elétrico", "dirigibilidade": "Dirigibilidade",
    "confiabilidade": "Confiabilidade", "pneus": "Pneus", "potencia": "Potência",
}

PADRAO_ARQUIVO = re.compile(r"^(?P<cat>.+)_(?P<ano>\d{4})\.json$")


class ErroDatabase(Exception):
    pass


# ---------------------------------------------------------------- descoberta
def anos_disponiveis(pasta=PASTA_DATABASE):
    if not os.path.isdir(pasta):
        return []
    return sorted(d for d in os.listdir(pasta) if d.isdigit() and os.path.isdir(os.path.join(pasta, d)))


def arquivos_do_ano(ano, pasta=PASTA_DATABASE):
    """Todos os arquivos nomedacategoria_ano.json da pasta do ano (busca automática)."""
    p = os.path.join(pasta, str(ano))
    if not os.path.isdir(p):
        return []
    out = []
    for f in sorted(os.listdir(p)):
        m = PADRAO_ARQUIVO.match(f)
        if m and m.group("ano") == str(ano) and m.group("cat") != "novos_pilotos":   # não é uma categoria
            out.append(os.path.join(p, f))
    return out


def todos_os_arquivos(pasta=PASTA_DATABASE):
    out = []
    for ano in anos_disponiveis(pasta):
        out.extend(arquivos_do_ano(ano, pasta))
    return out


def resumo_arquivo(caminho):
    """Lê só o cabeçalho para listas de seleção."""
    d = carregar_arquivo(caminho, validar=False)
    c = d["categoria"]
    return {"caminho": caminho, "id": c["id"], "nome": c["nome"], "ano": c["ano"],
            "equipes": sum(1 for e in d.get("equipes", []) if e.get("ativa"))}


# ---------------------------------------------------------------- leitura
def carregar_arquivo(caminho, validar=True):
    try:
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise ErroDatabase(f"Não foi possível ler {os.path.basename(caminho)}: {e}") from e
    if validar:
        erros = validar_dados(dados)
        if erros:
            raise ErroDatabase(f"{os.path.basename(caminho)}:\n- " + "\n- ".join(erros[:25]))
    return dados


def validar_dados(d):
    """Retorna lista de erros (vazia se o arquivo for válido)."""
    erros = []
    for chave in ("categoria", "pilotos", "chassis", "motores", "equipes", "patrocinadores", "calendario"):
        if chave not in d:
            erros.append(f"falta a seção '{chave}'")
    if erros:
        return erros
    cat = d["categoria"]
    regras = cat.get("regras", {})
    for chave in ("pilotos_de_teste", "desenvolvimento_chassis_por_equipe", "desenvolvimento_motor_por_equipe",
                  "testes_coletivos", "orcamento_medio", "inflacao_media_anual", "patrocinios", "renda_tv",
                  "importancia_carro", "importancia_piloto"):
        if chave not in regras:
            erros.append(f"categoria.regras: falta '{chave}'")
    if "importancia_carro" in regras and "importancia_piloto" in regras:
        if abs(regras["importancia_carro"] + regras["importancia_piloto"] - 1.0) > 1e-6:
            erros.append("importancia_carro + importancia_piloto deve somar 1.0 (100%)")
    if not isinstance(cat.get("tier", 1), int) or cat.get("tier", 1) < 1:
        erros.append("categoria: 'tier' deve ser inteiro >= 1 (1 = topo)")
    for chave in ("pontuacao", "regras_pitstop", "pneus", "clima", "formato_evento", "ponderacao", "simulacao"):
        if chave not in cat:
            erros.append(f"categoria: falta '{chave}'")

    ids_eq = {e["id"] for e in d["equipes"]}
    ids_ch = {c["id"] for c in d["chassis"]}
    ids_mo = {m["id"] for m in d["motores"]}
    ids_corridas = {e.get("id") for e in d["calendario"] if e.get("especie") == "corrida"}

    def faixa(nome, attrs, chaves):
        for k in chaves:
            v = attrs.get(k)
            if not isinstance(v, (int, float)) or not 0 <= v <= 100:
                erros.append(f"{nome}: atributo '{k}' ausente ou fora de 0-100")

    for p in d["pilotos"]:
        faixa(f"piloto {p.get('id')}", p.get("atributos", {}), ATRIBUTOS_PILOTO)
        if p.get("ano_aposentadoria") is not None and p.get("idade_aposentadoria") is not None:
            erros.append(f"piloto {p.get('id')}: use 'ano_aposentadoria' OU 'idade_aposentadoria', não os dois")
        for k in ("ano_pico", "ano_aposentadoria", "idade_aposentadoria"):
            if p.get(k) is not None and not isinstance(p[k], int):
                erros.append(f"piloto {p.get('id')}: '{k}' deve ser um ano (inteiro)")
        if p.get("potencial") is not None and not 0 <= p["potencial"] <= 100:
            erros.append(f"piloto {p.get('id')}: 'potencial' fora de 0-100")
        c = p.get("contrato")
        if c:
            if c.get("equipe") not in ids_eq:
                erros.append(f"piloto {p['id']}: equipe '{c.get('equipe')}' não existe")
            if c.get("situacao") not in ("principal", "teste"):
                erros.append(f"piloto {p['id']}: situação deve ser 'principal' ou 'teste'")
            if c.get("situacao") == "teste" and not regras.get("pilotos_de_teste"):
                erros.append(f"piloto {p['id']}: categoria não tem pilotos de teste")
            contratos.validar(c, f"piloto {p['id']}", erros)
            lista = c.get("corridas_definidas")
            if lista:
                if "corridas" not in c:
                    erros.append(f"piloto {p['id']}: corridas definidas só valem para contrato por corridas")
                for evid in lista:
                    if evid not in ids_corridas:
                        erros.append(f"piloto {p['id']}: corrida definida '{evid}' não existe no calendário")
    erros.extend(validar_contratos_futuros(d))
    for c in d["chassis"]:
        faixa(f"chassis {c.get('id')}", c.get("atributos", {}), ATRIBUTOS_CHASSIS)
        if c.get("equipe") and c["equipe"] not in ids_eq:
            erros.append(f"chassis {c['id']}: equipe '{c['equipe']}' não existe")
    for m in d["motores"]:
        faixa(f"motor {m.get('id')}", m, ATRIBUTOS_MOTOR)
        fab = m.get("fabricante", {})
        if fab.get("tipo") not in ("equipe", "fabricante"):
            erros.append(f"motor {m['id']}: fabricante.tipo deve ser 'equipe' ou 'fabricante'")
        if fab.get("tipo") == "equipe" and fab.get("equipe") not in ids_eq:
            erros.append(f"motor {m['id']}: equipe fabricante '{fab.get('equipe')}' não existe")
        exc = m.get("exclusividade") or {}
        if exc.get("exclusivo"):
            alvo = exc.get("equipe")
            if alvo not in ids_eq and alvo not in {e.get("nome") for e in d["equipes"]}:
                erros.append(f"motor {m['id']}: equipe da exclusividade '{alvo}' não existe")
    fontes = regras.get("fontes_de_motor_permitidas", ["proprio", "equipe", "fabricante"])
    for e in d["equipes"]:
        faixa(f"equipe {e.get('id')}", e, ["recursos"])
        for k in ("cor", "cor_secundaria"):
            if e.get(k) and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(e[k])):
                erros.append(f"equipe {e.get('id')}: '{k}' deve estar no formato #RRGGBB")
        ch = e.get("chassis")
        if ch and ch.get("id") and ch["id"] not in ids_ch:
            erros.append(f"equipe {e['id']}: chassis '{ch['id']}' não existe")
        for parte in ("chassis", "motor"):
            if (e.get(parte) or {}).get("contrato"):
                contratos.validar(e[parte]["contrato"], f"equipe {e['id']} ({parte})", erros)
        mo = e.get("motor")
        if mo and mo.get("id"):
            if mo["id"] not in ids_mo:
                erros.append(f"equipe {e['id']}: motor '{mo['id']}' não existe")
            if mo.get("origem") not in fontes:
                erros.append(f"equipe {e['id']}: origem do motor '{mo.get('origem')}' não permitida na categoria")
    for ev in d["calendario"]:
        for k in ("semana", "especie", "tipo_pista", "tempo_base_treino", "tempo_base_corrida", "retas",
                  "curvas_alta", "curvas_baixa", "desgaste_pneus", "dificuldade", "duracao_pitstop", "prob_chuva"):
            if k not in ev:
                erros.append(f"calendário {ev.get('id')}: falta '{k}'")
        if ev.get("especie") not in ("corrida", "treino"):
            erros.append(f"calendário {ev.get('id')}: espécie deve ser 'corrida' ou 'treino'")
        if ev.get("tipo_pista") not in ("mista", "oval", "rua"):
            erros.append(f"calendário {ev.get('id')}: tipo_pista deve ser 'mista', 'oval' ou 'rua'")
        anos = {}
        for k in ("anos_entrada", "anos_saida"):
            v = ev.get(k) or []
            if not isinstance(v, list) or any(not isinstance(a, int) or isinstance(a, bool) for a in v):
                erros.append(f"calendário {ev.get('id')}: '{k}' deve ser uma lista de anos")
                v = []
            anos[k] = set(v)
            if isinstance(cat.get("ano"), int) and any(a <= cat["ano"] for a in v):
                erros.append(f"calendário {ev.get('id')}: '{k}' deve ter anos depois de {cat['ano']} "
                             f"(no ano do arquivo vale 'ativo')")
        tpa = ev.get("tempos_por_ano")
        if tpa is not None:
            ok = isinstance(tpa, dict) and all(
                str(a).isdigit() and isinstance(t, list) and len(t) == 2
                and all(isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0 for x in t)
                for a, t in tpa.items())
            if not ok:
                erros.append(f"calendário {ev.get('id')}: 'tempos_por_ano' deve ser {{ano: [treino, corrida]}}")
            elif isinstance(cat.get("ano"), int) and any(int(a) <= cat["ano"] for a in tpa):
                erros.append(f"calendário {ev.get('id')}: 'tempos_por_ano' deve ter anos depois de {cat['ano']} "
                             f"(no ano do arquivo valem os tempos base)")
        if anos["anos_entrada"] & anos["anos_saida"]:
            erros.append(f"calendário {ev.get('id')}: o mesmo ano não pode estar em anos_entrada e anos_saida")
    erros.extend(validar_escalacao(d))
    for p in d["patrocinadores"]:
        c = p.get("contrato")
        if c and c.get("equipe") not in ids_eq:
            erros.append(f"patrocinador {p['id']}: equipe '{c.get('equipe')}' não existe")
    return erros


def _fim_contrato_arquivo(ct, ano, n_corridas):
    """Última temporada coberta por um contrato do arquivo (atual: começa no ano do arquivo; futuro: no inicio_ano)."""
    ini = ct.get("inicio_ano") or ano
    anos = -(-ct["corridas"] // n_corridas) if "corridas" in ct else ct.get("temporadas", 1)
    return ini + max(1, anos) - 1


def validar_contratos_futuros(d):
    """Pilotos já contratados para uma temporada futura ('contrato_futuro' com 'inicio_ano')."""
    erros = []
    cat = d["categoria"]
    regras = cat.get("regras", {})
    ano = cat.get("ano") if isinstance(cat.get("ano"), int) else None
    ids_eq = {e["id"] for e in d["equipes"]}
    n = max(1, sum(1 for e in d["calendario"] if e.get("especie") == "corrida" and e.get("ativo", True)))
    alvo = {"principal": regras.get("pilotos_principais_por_equipe", 2),
            "teste": regras.get("pilotos_de_teste_por_equipe", 0) if regras.get("pilotos_de_teste") else 0}
    anos_checar = set()
    for p in d["pilotos"]:
        f = p.get("contrato_futuro")
        if not f:
            continue
        nome = f"piloto {p.get('id')}"
        if f.get("equipe") not in ids_eq:
            erros.append(f"{nome}: equipe '{f.get('equipe')}' do contrato futuro não existe")
        if f.get("situacao") not in ("principal", "teste"):
            erros.append(f"{nome}: situação do contrato futuro deve ser 'principal' ou 'teste'")
        elif f["situacao"] == "teste" and not regras.get("pilotos_de_teste"):
            erros.append(f"{nome}: categoria não tem pilotos de teste")
        contratos.validar(f, f"{nome} (contrato futuro)", erros)
        if f.get("corridas_definidas"):
            erros.append(f"{nome}: corridas definidas só valem para o contrato atual")
        ini = f.get("inicio_ano")
        if not isinstance(ini, int) or (ano is not None and ini <= ano):
            erros.append(f"{nome}: o contrato futuro precisa de 'inicio_ano' depois de {ano}")
            continue
        if ano is None or not isinstance(f.get("corridas", f.get("temporadas")), int):
            continue
        anos_checar.add(ini)
        c = p.get("contrato")
        if c and isinstance(c.get("corridas", c.get("temporadas")), int) and _fim_contrato_arquivo(c, ano, n) >= ini:
            erros.append(f"{nome}: o contrato atual vai até {_fim_contrato_arquivo(c, ano, n)}; o contrato futuro "
                         f"tem de começar depois")
        apos = p.get("ano_aposentadoria")
        if apos is None and p.get("idade_aposentadoria") is not None and isinstance(p.get("idade"), int):
            apos = ano + max(1, p["idade_aposentadoria"] - p["idade"])
        if isinstance(apos, int) and apos <= ini:
            erros.append(f"{nome}: vai se aposentar em {apos}, antes do contrato futuro ({ini})")
    erros.extend(_validar_partes_futuras(d, ano, n))
    if ano is None:
        return erros
    for y in sorted(anos_checar):          # vagas: ninguém pode ter mais pilotos que o limite em nenhum ano
        ocup = {}
        for p in d["pilotos"]:
            for ct in (p.get("contrato"), p.get("contrato_futuro")):
                if not ct or not isinstance(ct.get("corridas", ct.get("temporadas")), int):
                    continue
                if not isinstance(ct.get("inicio_ano", ano), int):
                    continue
                if (ct.get("inicio_ano") or ano) <= y <= _fim_contrato_arquivo(ct, ano, n):
                    k = (ct.get("equipe"), ct.get("situacao"))
                    ocup[k] = ocup.get(k, 0) + 1
        for (eid, sit), q in sorted(ocup.items(), key=str):
            if sit in alvo and q > alvo[sit]:
                erros.append(f"equipe {eid}: {q} pilotos ({sit}) com contrato em {y} (máximo {alvo[sit]})")
    return erros


def _validar_partes_futuras(d, ano, n):
    """Equipe que já contratou chassis/motor para uma temporada futura ('chassis_futuro' / 'motor_futuro')."""
    erros = []
    ids = {"chassis": {c["id"] for c in d["chassis"]}, "motor": {m["id"] for m in d["motores"]}}
    origens = {"chassis": ("terceiros", "equipe"), "motor": ("equipe", "fabricante")}
    fontes_motor = d["categoria"].get("regras", {}).get("fontes_de_motor_permitidas", ["proprio", "equipe", "fabricante"])
    for e in d["equipes"]:
        for parte in ("chassis", "motor"):
            f = e.get(f"{parte}_futuro")
            if not f:
                continue
            nome = f"equipe {e.get('id')} ({parte} futuro)"
            if f.get("id") not in ids[parte]:
                erros.append(f"{nome}: '{f.get('id')}' não existe")
            if f.get("origem") not in origens[parte]:
                erros.append(f"{nome}: origem deve ser {' ou '.join(origens[parte])} (a peça futura é comprada)")
            elif parte == "motor" and f["origem"] not in fontes_motor:
                erros.append(f"{nome}: origem '{f['origem']}' não permitida na categoria")
            ct = f.get("contrato")
            if not isinstance(ct, dict):
                erros.append(f"{nome}: falta o contrato")
                continue
            contratos.validar(ct, nome, erros)
            ini = ct.get("inicio_ano")
            if not isinstance(ini, int) or (ano is not None and ini <= ano):
                erros.append(f"{nome}: o contrato precisa de 'inicio_ano' depois de {ano}")
                continue
            atual = e.get(parte) or {}
            ca = atual.get("contrato")
            if ano is not None and atual.get("origem") not in (None, "proprio") and isinstance(ca, dict) \
                    and isinstance(ca.get("corridas", ca.get("temporadas")), int):
                fim = _fim_contrato_arquivo(ca, ano, n)
                if fim >= ini:
                    erros.append(f"{nome}: o contrato atual vai até {fim}; o futuro tem de começar depois")
    return erros


def validar_escalacao(d):
    """Revezamento: em cada corrida, nenhuma equipe pode ter mais pilotos principais escalados que carros."""
    limite = d["categoria"].get("regras", {}).get("pilotos_principais_por_equipe") or 99
    erros = []
    por_equipe = {}
    for p in d["pilotos"]:
        c = p.get("contrato") or {}
        if c.get("situacao") == "principal" and c.get("equipe"):
            por_equipe.setdefault(c["equipe"], []).append(c.get("corridas_definidas"))
    for eid, listas in por_equipe.items():
        if not any(listas):
            continue                    # sem corridas definidas: comportamento normal
        for ev in d["calendario"]:
            if ev.get("especie") != "corrida":
                continue
            n = sum(1 for lst in listas if not lst or ev.get("id") in lst)
            if n > limite:
                erros.append(f"equipe {eid}: {n} pilotos escalados em '{ev.get('nome', ev.get('id'))}' "
                             f"(máximo {limite} por equipe)")
    return erros


def indexar(lista):
    return {x["id"]: x for x in lista}
