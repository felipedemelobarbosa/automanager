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
    erros.extend(validar_escalacao(d))
    for p in d["patrocinadores"]:
        c = p.get("contrato")
        if c and c.get("equipe") not in ids_eq:
            erros.append(f"patrocinador {p['id']}: equipe '{c.get('equipe')}' não existe")
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
