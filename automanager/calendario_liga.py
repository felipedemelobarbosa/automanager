"""Calendário da próxima temporada definido pelo comissário (multijogador).

O comissário edita uma cópia do calendário da categoria com o mesmo formulário do editor (pode ligar/desligar
eventos, mudar semanas, voltas, percentuais, e criar pistas novas). Ao salvar, o calendário fica em
st["multiplayer"]["calendario_proximo"][cid] = {"ano": ano + 1, "eventos": [...]} e uma notícia o publica (os
jogadores o veem no próximo arquivo da liga). Na virada da temporada ele substitui o calendário da categoria, sem os
sorteios de entrada/saída; categoria sem calendário definido segue o sorteio normal.

Tempos base: os eventos guardam os tempos já evoluídos da temporada atual. Pista nova, ou com tempo alterado pelo
comissário, recebe os tempos digitados em tempos_por_ano[próximo ano] (valem exatamente nesse ano e evoluem depois).
"""
import copy

from .state import noticia

CAMPOS_OBRIGATORIOS = ("id", "nome", "semana", "especie", "tipo_pista", "tempo_base_treino", "tempo_base_corrida",
                       "voltas_corrida", "retas", "curvas_alta", "curvas_baixa", "desgaste_pneus", "dificuldade",
                       "duracao_pitstop", "prob_chuva")


def _liga(st):
    return st.get("multiplayer") or {}


def proximo(st, cid):
    """{"ano", "eventos"} definido para a próxima temporada da categoria, ou None."""
    d = (_liga(st).get("calendario_proximo") or {}).get(cid)
    return d if d and d.get("ano") == st["ano"] + 1 else None


def validar(eventos):
    """Lista de erros do calendário (vazia = ok)."""
    erros, ids, semanas = [], set(), {}
    for ev in eventos:
        nome = ev.get("nome") or ev.get("id") or "?"
        for k in CAMPOS_OBRIGATORIOS:
            if ev.get(k) in (None, ""):
                erros.append(f"{nome}: falta '{k}'.")
        if ev.get("id") in ids:
            erros.append(f"{nome}: ID '{ev.get('id')}' repetido.")
        ids.add(ev.get("id"))
        if ev.get("especie") not in ("corrida", "treino"):
            erros.append(f"{nome}: espécie deve ser corrida ou teste coletivo.")
        if ev.get("tipo_pista") not in ("mista", "oval", "rua"):
            erros.append(f"{nome}: tipo de pista inválido.")
        s = ev.get("semana")
        if not isinstance(s, int) or not 1 <= s <= 52:
            erros.append(f"{nome}: a semana deve ser de 1 a 52.")
        elif ev.get("ativo"):
            if s in semanas:
                erros.append(f"{nome} e {semanas[s]} estão na mesma semana ({s}).")
            semanas[s] = nome
        for k in ("tempo_base_treino", "tempo_base_corrida"):
            if isinstance(ev.get(k), (int, float)) and ev[k] <= 0:
                erros.append(f"{nome}: '{k}' deve ser maior que zero.")
    if not any(ev.get("ativo") and ev.get("especie") == "corrida" for ev in eventos):
        erros.append("O calendário precisa de pelo menos uma corrida ativa.")
    return erros


def definir(st, cid, eventos):
    """Grava o calendário da próxima temporada. Retorna None ou a mensagem de erro."""
    if not st.get("multiplayer"):
        return "Só no multijogador."
    erros = validar(eventos)
    if erros:
        return "\n".join(erros)
    ano = st["ano"] + 1
    st["multiplayer"].setdefault("calendario_proximo", {})[cid] = {"ano": ano, "eventos": copy.deepcopy(eventos)}
    c = st["categorias"][cid]
    ativos = sorted((e for e in eventos if e.get("ativo")), key=lambda e: e["semana"])
    lista = "; ".join(f"S{e['semana']} {e['nome']}" + ("" if e["especie"] == "corrida" else " (teste)") for e in ativos)
    noticia(st, f"Calendário {ano} da {c['categoria']['nome']} definido pelo comissário: {lista}.", cid, "calendario")
    return None


def limpar(st, cid):
    """Desfaz: a próxima temporada volta ao sorteio normal."""
    (_liga(st).get("calendario_proximo") or {}).pop(cid, None)


def aplicar(st):
    """Virada (st["ano"] já é o ano novo, antes da evolução dos tempos base): troca o calendário das categorias
    com calendário definido. Retorna o conjunto dessas categorias (sem sorteio de entrada/saída neste ano)."""
    feitos = set()
    pend = _liga(st).get("calendario_proximo") or {}
    for cid, d in list(pend.items()):
        if d.get("ano") != st["ano"] or cid not in st["categorias"]:
            if d.get("ano", 0) < st["ano"]:
                pend.pop(cid)                          # antigo, de uma virada que já passou
            continue
        c = st["categorias"][cid]
        atual = {e["id"]: e for e in c["calendario"]}
        novo = []
        for ev in copy.deepcopy(d["eventos"]):
            antes = atual.get(ev["id"])
            tempos = [ev["tempo_base_treino"], ev["tempo_base_corrida"]]
            if antes is None or tempos != [antes.get("tempo_base_treino"), antes.get("tempo_base_corrida")]:
                ev.setdefault("tempos_por_ano", {})[str(st["ano"])] = tempos   # vale como digitado neste ano
            novo.append(ev)
        c["calendario"] = novo
        pend.pop(cid)
        feitos.add(cid)
        noticia(st, f"{c['categoria']['nome']}: começa a temporada {st['ano']} com o calendário definido pelo "
                    f"comissário.", cid, "calendario")
    return feitos
