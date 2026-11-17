"""Resultados de corridas, campeonatos e histórico.

st["temporadas"][ano][cid] = {
   "corridas": [{evento, nome, local, semana, pole, volta_rapida, resultado: [linha...]}],
   "final": {"pilotos": [...], "equipes": [...]}        # gravado na virada da temporada
}
linha = {pos, piloto, nome, nacionalidade, equipe, equipe_nome, pontos, status, voltas, tempo, grid, paradas}
Os nomes ficam gravados porque pilotos/equipes podem mudar ou sumir com o tempo.
"""
import random

from .event.inscritos import montar_inscritos
from .event.sessoes import Evento
from .event import planos as planos_evento


def _temporada(st, cid, ano=None):
    t = st.setdefault("temporadas", {}).setdefault(str(ano or st["ano"]), {})
    return t.setdefault(cid, {"corridas": [], "final": None})


def ja_disputado(st, cid, evento_id):
    return any(r["evento"] == evento_id for r in _temporada(st, cid)["corridas"])


def registrar_corrida(st, cid, pista, ev):
    """Grava o resultado de um Evento já terminado."""
    ev.gravar_uso_motor()
    linhas = []
    for r in ev.resultado_corrida or []:
        c = r["carro"]
        linhas.append({"pos": r["pos"], "piloto": c.id, "nome": c.nome, "nacionalidade": c.piloto["nacionalidade"],
                       "equipe": c.equipe["id"], "equipe_nome": c.equipe["nome"], "pontos": r["pontos"],
                       "status": "Fim" if c.status == "fim" else (c.motivo or "Abandono"), "voltas": c.voltas,
                       "tempo": round(c.tempo_total, 3), "grid": getattr(c, "grid", None), "paradas": c.paradas})
    vr = ev.sessao.volta_mais_rapida if ev.sessao and ev.sessao.tipo == "corrida" else None
    reg = {"evento": pista["id"], "nome": pista["nome"], "local": pista["local"], "semana": pista["semana"],
           "pole": ev.pole.nome if ev.pole else None,
           "volta_rapida": {"nome": vr[1].nome, "tempo": round(vr[0], 3)} if vr else None,
           "resultado": linhas}
    if getattr(ev.sessao, "cancelada", False):
        reg["cancelada"] = True                    # oval com chuva que não parou: não conta no campeonato
    if getattr(ev.sessao, "interrompida", False):
        reg["interrompida"] = True
    _aplicar_vitimas(st, cid, ev)
    _temporada(st, cid)["corridas"].append(reg)
    return reg


def _planos(st, cid, pista):
    """Planos de evento dos jogadores do multijogador para esta pista ({piloto_id: plano})."""
    if not st.get("multiplayer"):
        return {}
    from . import multiplayer
    return multiplayer.planos_do_evento(st, cid, pista["id"])


def simular_em_segundo_plano(st, cid, pista, rng=random):
    """Simula o evento inteiro sem interação (equipes do PC e, se for o caso, a do usuário com acerto da IA)."""
    c = st["categorias"][cid]
    inscritos = montar_inscritos(st, cid, None, pista)
    if len(inscritos) < 2:
        return None
    ev = Evento(c["categoria"], pista, inscritos, random.Random(rng.random()), ordem_campeonato=ordem(st, cid))
    planos = _planos(st, cid, pista)
    while ev.proxima_sessao():
        planos_evento.aplicar(ev, planos)
        ev.sessao.iniciar()
        ev.sessao.simular_ate_o_fim()
    return registrar_corrida(st, cid, pista, ev)


def ordem(st, cid):
    """Ids dos pilotos na ordem do campeonato atual (antes da 1ª corrida: final do ano anterior)."""
    pil, _ = classificacao(st, cid)
    if not pil:
        ant = st.get("temporadas", {}).get(str(st["ano"] - 1), {}).get(cid, {}).get("final")
        pil = ant["pilotos"] if ant else []
    return [p["id"] for p in pil]


def programacao_teste(categoria):
    """Dias do teste coletivo: categoria["formato_teste_coletivo"] = {"dias", "minutos_por_dia"} (padrão 2 × 240)."""
    fmt = categoria.get("formato_teste_coletivo") or {}
    dias, minutos = int(fmt.get("dias", 2)), int(fmt.get("minutos_por_dia", 240))
    return [("treino", {"nome": f"Dia {i + 1}", "limite": "tempo", "valor": minutos}) for i in range(dias)]


def criar_evento_teste(st, cid, pista, inscritos, rng=random):
    c = st["categorias"][cid]
    ev = Evento(c["categoria"], pista, inscritos, random.Random(rng.random()))
    ev.programacao = programacao_teste(c["categoria"])
    ev.modo = "teste"
    return ev


def registrar_teste(st, cid, pista, ev):
    """Grava o teste a partir dos dias já encerrados (ev.historico_sessoes)."""
    ev.gravar_uso_motor()
    reg = {"evento": pista["id"], "nome": pista["nome"], "local": pista["local"], "semana": pista["semana"],
           "dias": [], "geral": []}
    melhor = {}
    for d in ev.historico_sessoes:
        reg["dias"].append({"nome": d["nome"], "clima": d["clima"], "resultado": d["linhas"]})
        for l in d["linhas"]:
            m = melhor.setdefault(l["piloto"], dict(l, melhor=None, voltas_total=0))
            m["voltas_total"] += l.get("voltas", 0)
            if l.get("melhor") and (m["melhor"] is None or l["melhor"] < m["melhor"]):
                m["melhor"] = l["melhor"]
    reg["geral"] = sorted((m for m in melhor.values() if m["melhor"]), key=lambda l: l["melhor"])
    for i, l in enumerate(reg["geral"], 1):
        l["pos"] = i
    _temporada(st, cid).setdefault("testes", []).append(reg)
    _aplicar_vitimas(st, cid, ev)
    return reg


def _aplicar_vitimas(st, cid, ev):
    """Lesões e mortes das batidas graves do evento passam para o jogo (uma vez só)."""
    if getattr(ev, "vitimas", None) and not getattr(ev, "_vitimas_aplicadas", False):
        from . import saude
        saude.aplicar(st, cid, ev.vitimas, random.Random(ev.rng.random()))
        ev._vitimas_aplicadas = True


def simular_teste_coletivo(st, cid, pista, rng=random):
    """Teste coletivo simulado em segundo plano (todos os dias)."""
    inscritos = montar_inscritos(st, cid, None, pista)
    if len(inscritos) < 2:
        return None
    ev = criar_evento_teste(st, cid, pista, inscritos, rng)
    planos = _planos(st, cid, pista)
    while ev.proxima_sessao():
        planos_evento.aplicar(ev, planos)
        ev.sessao.iniciar()
        ev.sessao.simular_ate_o_fim()
    return registrar_teste(st, cid, pista, ev)


def testes_da_temporada(st, cid, ano=None):
    return st.get("temporadas", {}).get(str(ano or st["ano"]), {}).get(cid, {}).get("testes", [])


# ---------------------------------------------------------------- classificação
def classificacao(st, cid, ano=None):
    """(pilotos, equipes) ordenados por pontos, vitórias e melhores resultados."""
    corridas = _temporada(st, cid, ano)["corridas"] if str(ano or st["ano"]) in st.get("temporadas", {}) else []
    return _somar(corridas)


def _somar(corridas):
    pil, eq = {}, {}
    for corr in corridas:
        if corr.get("cancelada"):
            continue
        for l in corr["resultado"]:
            p = pil.setdefault(l["piloto"], {"id": l["piloto"], "nome": l["nome"], "nacionalidade": l["nacionalidade"],
                                             "equipe": l["equipe_nome"], "pontos": 0, "vitorias": 0, "podios": 0,
                                             "corridas": 0, "posicoes": []})
            p["equipe"] = l["equipe_nome"]
            e = eq.setdefault(l["equipe"], {"id": l["equipe"], "nome": l["equipe_nome"], "pontos": 0, "vitorias": 0,
                                            "podios": 0, "posicoes": []})
            for d in (p, e):
                d["pontos"] += l["pontos"]
                if l["status"] == "Fim":
                    d["vitorias"] += l["pos"] == 1
                    d["podios"] += l["pos"] <= 3
                    d["posicoes"].append(l["pos"])
            p["corridas"] += 1

    def chave(d):
        return (-d["pontos"], -d["vitorias"], sorted(d["posicoes"]) + [999])

    return sorted(pil.values(), key=chave), sorted(eq.values(), key=chave)


def posicao_equipe(st, cid, eid):
    """Posição da equipe no campeonato atual (ou final da temporada anterior se ainda não houve corrida)."""
    _, equipes = classificacao(st, cid)
    if not equipes:
        ant = st.get("temporadas", {}).get(str(st["ano"] - 1), {}).get(cid, {}).get("final")
        if not ant:
            return None
        equipes = ant["equipes"]
    for i, e in enumerate(equipes, 1):
        if e["id"] == eid:
            return i
    return None


def fechar_temporada(st, ano):
    """Grava a classificação final de todas as categorias do ano."""
    for cid in st["categorias"]:
        t = _temporada(st, cid, ano)
        pil, eq = classificacao(st, cid, ano)
        t["final"] = {"pilotos": pil, "equipes": eq}


def campeoes(st, cid=None):
    out = []
    for ano, cats in sorted(st.get("temporadas", {}).items()):
        for c, t in cats.items():
            if cid and c != cid or not t.get("final") or not t["final"]["pilotos"]:
                continue
            nome_cat = st["categorias"][c]["categoria"]["nome"] if c in st["categorias"] else c
            out.append({"ano": ano, "categoria": nome_cat, "piloto": t["final"]["pilotos"][0]["nome"],
                        "nacionalidade": t["final"]["pilotos"][0].get("nacionalidade"),
                        "equipe": t["final"]["equipes"][0]["nome"] if t["final"]["equipes"] else "-"})
    return out


def total_geral(st, cid=None):
    """Pontuação somada de todas as temporadas (pilotos e equipes), com títulos."""
    pil, eq = {}, {}
    for ano, cats in st.get("temporadas", {}).items():
        for c, t in cats.items():
            if cid and c != cid:
                continue
            p_ano, e_ano = (t["final"]["pilotos"], t["final"]["equipes"]) if t.get("final") else _somar(t["corridas"])
            for i, p in enumerate(p_ano):
                d = pil.setdefault(p["id"], {"nome": p["nome"], "nacionalidade": p.get("nacionalidade", ""),
                                             "pontos": 0, "vitorias": 0, "podios": 0, "temporadas": set(), "titulos": 0})
                d["pontos"] += p["pontos"]
                d["vitorias"] += p["vitorias"]
                d["podios"] += p["podios"]
                d["temporadas"].add(ano)
                d["titulos"] += 1 if (i == 0 and t.get("final")) else 0
            for i, e in enumerate(e_ano):
                d = eq.setdefault((c, e["id"]), {"nome": e["nome"], "pontos": 0, "vitorias": 0, "podios": 0,
                                                 "temporadas": set(), "titulos": 0})
                d["pontos"] += e["pontos"]
                d["vitorias"] += e["vitorias"]
                d["podios"] += e["podios"]
                d["temporadas"].add(ano)
                d["titulos"] += 1 if (i == 0 and t.get("final")) else 0
    for d in list(pil.values()) + list(eq.values()):
        d["temporadas"] = len(d["temporadas"])
    ordem = lambda d: (-d["pontos"], -d["titulos"], -d["vitorias"])  # noqa: E731
    return sorted(pil.values(), key=ordem), sorted(eq.values(), key=ordem)
