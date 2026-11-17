"""Tempo base das pistas ao longo das temporadas.

Cada evento do calendário pode ter `tempos_por_ano` ({"2028": [treino, corrida]}): nesses anos valem os tempos
informados. Nos outros, o tempo segue a evolução automática a partir do último ano informado (ou dos tempos do
arquivo), com os parâmetros de categoria.evolucao_tempo_base (todos opcionais):

- `ganho_por_temporada` (0,012): sem grande mudança de regulamento, o tempo base cai 1,2% por temporada
  (desenvolvimento dos carros, pneus, combustível etc.; na F1, 1 a 2% por ano nos períodos de regras estáveis);
- `grande_mudanca` (0,03): no ano de uma grande mudança de regulamento, o tempo base sobe 3% (na F1, as
  mudanças feitas para frear os carros custaram de 2 a 4%: 2005, 2006, 2014, 2022). O jogo já deixa os carros
  mais lentos nesse ano pela perda extra do chassis (~0,5% a mais), por isso a fórmula usa 3%;
- `ganho_sem_regulamento` (0,002): categoria com o regulamento desligado: 0,2% por temporada, a média de longo
  prazo da F1 (Monza: pole de 1:20.1 em 2004 e 1:19.3 em 2024), que já desconta as mudanças de regras;
- `ativa` (true): false mantém os tempos do arquivo (e os informados por ano).

Os atributos de chassis, motor e pilotos também entram no tempo de volta (nota 50 = tempo base); como o nível
médio deles fica perto do da database ao longo dos anos (calibração automática), eles não dão tendência própria:
numa simulação de 10 temporadas, mexeram no tempo médio só ±0,5%. A tendência de longo prazo vem daqui.
"""
from . import regulamento

PADRAO = {"ativa": True, "ganho_por_temporada": 0.012, "grande_mudanca": 0.03, "ganho_sem_regulamento": 0.002}


def cfg(categoria):
    return dict(PADRAO, **(categoria.get("evolucao_tempo_base") or {}))


def _estado(st, c, ano_inicio):
    """Fator acumulado por ano (1,0 no ano de referência) e os tempos do arquivo de cada evento."""
    e = c.get("evolucao_tempo")
    if e is None:
        e = c["evolucao_tempo"] = {"ano0": ano_inicio, "fator": {str(ano_inicio): 1.0}}
    for ev in c["calendario"]:
        ev.setdefault("tempo_base_arquivo", [ev.get("tempo_base_treino"), ev.get("tempo_base_corrida")])
    return e


def iniciar(st):
    for c in st["categorias"].values():
        _estado(st, c, st["ano"])


def tempos_do_ano(ev, ano, e):
    """(treino, corrida) do evento no ano: o informado, ou o último informado/do arquivo com a evolução."""
    tabela = {int(a): v for a, v in (ev.get("tempos_por_ano") or {}).items()}
    if ano in tabela:
        return tuple(tabela[ano])
    anteriores = [a for a in tabela if a < ano and str(a) in e["fator"]]
    if anteriores:
        ref = max(anteriores)
        t = tabela[ref]
    else:
        ref = e["ano0"]
        t = ev["tempo_base_arquivo"]
    k = e["fator"].get(str(ano), 1.0) / e["fator"].get(str(ref), 1.0)
    return round(t[0] * k, 3), round(t[1] * k, 3)


def virada(st, cid):
    """Nova temporada (st["ano"] já é o ano novo; antes de regulamento.virada, que apaga o anúncio)."""
    c = st["categorias"][cid]
    cat = c["categoria"]
    e = _estado(st, c, st["ano"] - 1)              # saves antigos: o ano anterior vira a referência
    b = cfg(cat)
    if not b["ativa"]:
        f = 1.0
    elif regulamento.cfg(cat)["ativo"]:
        f = 1 + b["grande_mudanca"] if regulamento.grande_mudanca(st, cid, st["ano"]) else 1 - b["ganho_por_temporada"]
    else:
        f = 1 - b["ganho_sem_regulamento"]
    e["fator"][str(st["ano"])] = round(e["fator"].get(str(st["ano"] - 1), 1.0) * f, 6)
    for ev in c["calendario"]:
        ev["tempo_base_treino"], ev["tempo_base_corrida"] = tempos_do_ano(ev, st["ano"], e)
