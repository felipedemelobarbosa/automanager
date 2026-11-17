"""Contratos por temporadas ou por corridas (pilotos, chassis, motores, patrocínios).

Formato: {"temporadas": n}  ou  {"corridas": n}  (mais os demais campos de cada tipo).
Pilotos com contrato por corridas podem ter "corridas_definidas": [ids do calendário] – corre só nelas
(revezamento: a equipe pode ter mais pilotos principais que carros, desde que cada corrida respeite o limite).
Patrocínios usam {"duracao": n, "unidade": "temporadas"|"corridas"} (formato original).
"""


def corridas_restantes(st, cid):
    """Corridas ainda não disputadas na temporada atual da categoria."""
    c = st["categorias"][cid]
    feitas = {r["evento"] for r in resultados_da_temporada(st, cid)}
    return sum(1 for e in c["calendario"]
               if e.get("ativo") and e["especie"] == "corrida" and e["semana"] >= st["semana"] and e["id"] not in feitas)


def resultados_da_temporada(st, cid, ano=None):
    ano = str(ano or st["ano"])
    return st.get("temporadas", {}).get(ano, {}).get(cid, {}).get("corridas", [])


def por_corridas(ct):
    return ct is not None and "corridas" in ct


def termina_nesta_temporada(ct, restantes):
    if not ct:
        return True
    if por_corridas(ct):
        return ct["corridas"] <= restantes
    return ct.get("temporadas", 1) <= 1


def descricao(ct):
    if not ct:
        return "-"
    if por_corridas(ct):
        return f"{ct['corridas']} corr."
    return f"{ct.get('temporadas', 1)} temp."


def escalado(ct, evento_id):
    """Contrato por corridas com 'corridas_definidas': o piloto só corre nas corridas da lista."""
    lista = (ct or {}).get("corridas_definidas")
    return not lista or evento_id is None or evento_id in lista


def novo(duracao, unidade, **extra):
    d = dict(extra)
    d["corridas" if unidade == "corridas" else "temporadas"] = max(1, int(duracao))
    return d


def validar(ct, nome, erros):
    if ct is None:
        return
    n = ct.get("corridas", ct.get("temporadas"))
    if not isinstance(n, int) or n < 1:
        erros.append(f"{nome}: contrato precisa de 'temporadas' ou 'corridas' (inteiro >= 1)")
