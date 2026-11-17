"""Salvar e restaurar um evento em andamento (dentro do savegame JSON).

Tudo é convertido para JSON: carros viram {"__carro__": id}, conjuntos viram {"__set__": [...]},
o estado do gerador aleatório é guardado para que a simulação continue exatamente de onde parou.
"""
import random

from .clima import Clima
from .modelo import Carro, ModeloVolta
from .sessoes import Evento, SessaoCronometrada, SessaoCorrida, SessaoGrid, montar_programacao

_FORA_CARRO = ("piloto", "equipe", "_cache")
_FORA_SESSAO = ("ev",)


def _para_json(v):
    if isinstance(v, Carro):
        return {"__carro__": v.id}
    if isinstance(v, set):
        return {"__set__": [_para_json(x) for x in v]}
    if isinstance(v, dict):
        return {k: _para_json(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_para_json(x) for x in v]
    return v


def _de_json(v, carros):
    if isinstance(v, dict):
        if "__carro__" in v and len(v) == 1:
            return carros[v["__carro__"]]
        if "__set__" in v and len(v) == 1:
            return set(_de_json(x, carros) for x in v["__set__"])
        return {k: _de_json(x, carros) for k, x in v.items()}
    if isinstance(v, list):
        return [_de_json(x, carros) for x in v]
    return v


def serializar(ev, categoria_id):
    s = ev.sessao
    estado_rng = ev.rng.getstate()
    return {
        "categoria": categoria_id,
        "pista": ev.pista["id"],
        "rng": [estado_rng[0], list(estado_rng[1]), estado_rng[2]],
        "clima": {"estado": ev.clima.estado, "_acumulado": ev.clima._acumulado, "mudancas": ev.clima.mudancas},
        "indice": ev.indice,
        "ordem_campeonato": list(ev.ordem_campeonato),
        "programacao": [list(x) for x in ev.programacao],
        "historico_sessoes": ev.historico_sessoes,
        "modo": getattr(ev, "modo", "corrida"),
        "voltas_pista": ev.voltas_pista,
        "notas": list(ev.notas),
        "vitimas": list(ev.vitimas),
        "grid": _para_json(ev.grid),
        "pole": _para_json(ev.pole),
        "resultado_corrida": _para_json(ev.resultado_corrida),
        "carros": [dict({k: _para_json(v) for k, v in vars(c).items() if k not in _FORA_CARRO},
                        piloto_id=c.piloto["id"], equipe_id=c.equipe["id"]) for c in ev.carros],
        "sessao": None if s is None else {
            "classe": type(s).__name__,
            "dados": {k: _para_json(v) for k, v in vars(s).items() if k not in _FORA_SESSAO},
        },
    }


def restaurar(dados, st):
    """Recria o Evento a partir do save. `st` é o estado do jogo já carregado."""
    c = st["categorias"][dados["categoria"]]
    pista = next(e for e in c["calendario"] if e["id"] == dados["pista"])
    ev = Evento.__new__(Evento)
    ev.cat = c["categoria"]
    ev.pista = pista
    ev.rng = random.Random()
    ev.clima = Clima(ev.cat["clima"], pista.get("prob_chuva", 0.2), ev.rng)   # o construtor consome o rng...
    r = dados["rng"]
    ev.rng.setstate((r[0], tuple(r[1]), r[2]))                               # ...por isso o estado vem depois
    for k, v in dados["clima"].items():
        setattr(ev.clima, k, v)
    ev.modelo = ModeloVolta(ev.cat, pista, ev.rng)
    ev.voltas_pista = dados.get("voltas_pista", 0.0)
    ev.vitimas = list(dados.get("vitimas", []))
    ev.notas = list(dados.get("notas", []))
    carros = {}
    ev.carros = []
    for cd in dados["carros"]:
        car = Carro.__new__(Carro)
        cd = dict(cd)
        car.piloto = st["pilotos"][cd.pop("piloto_id")]
        car.equipe = c["equipes"][cd.pop("equipe_id")]
        car._cache = {}
        car.__dict__.update(cd)
        carros[car.id] = car
        ev.carros.append(car)
    for car, cd in zip(ev.carros, dados["carros"]):
        for k, v in cd.items():
            if k not in ("piloto_id", "equipe_id"):
                setattr(car, k, _de_json(v, carros))
    ev.programacao = [tuple(x) for x in dados["programacao"]] if dados.get("programacao") else \
        montar_programacao(ev.cat)
    ev.historico_sessoes = dados.get("historico_sessoes", [])
    ev.modo = dados.get("modo", "corrida")
    ev.ordem_campeonato = dados.get("ordem_campeonato", [])
    ev.indice = dados["indice"]
    ev.grid = _de_json(dados["grid"], carros)
    ev.pole = _de_json(dados["pole"], carros)
    ev.resultado_corrida = _de_json(dados["resultado_corrida"], carros)
    ev.sessao = None
    if dados["sessao"]:
        cls = {"SessaoCronometrada": SessaoCronometrada, "SessaoCorrida": SessaoCorrida, "SessaoGrid": SessaoGrid}[dados["sessao"]["classe"]]
        s = cls.__new__(cls)
        s.ev = ev
        for k, v in dados["sessao"]["dados"].items():
            setattr(s, k, _de_json(v, carros))
        if hasattr(s, "_heap"):
            s._heap = [tuple(x) for x in s._heap]
        ev.sessao = s
    return ev, pista
