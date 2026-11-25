"""Lesões e falecimentos de pilotos em batidas graves.

Regras em categoria.regras.batida_grave (ver docs/DATABASE.md). O evento sorteia as vítimas na hora da batida
(Evento.vitimas); ao gravar o resultado, aplicar() leva isso ao jogo:
- lesão: o piloto fica fora de um número sorteado de corridas e perde alguns pontos de atributos;
- falecimento: o piloto sai do jogo (st["falecidos"]) e o contrato termina.
Substituição: equipes do PC promovem o piloto de testes (até o titular voltar) ou contratam pelo mercado;
equipes de jogadores (individual e multijogador) recebem um alerta e o carro não corre até contratarem alguém.
Quem é contratado como titular enquanto a equipe tem um titular lesionado é substituto: o contrato termina
quando o titular volta.
"""
from .state import noticia, eh_humana, pilotos_da_equipe
from .util import clamp

PADRAO = {"prob_por_volta": 0.0015, "fator_treinos": 0.5, "carros_min": 2, "carros_max": 5,
          "prob_encerrar_sessao": 0.2, "prob_lesao": 0.06, "prob_morte": 0.002,
          "lesao_corridas": [1, 6], "lesao_perda_atributos": [1, 6],
          "atributos_afetados": ["fisico", "concentracao", "conducao"]}


def cfg(categoria):
    return dict(PADRAO, **(categoria["regras"].get("batida_grave") or {}))


def lesionado(p):
    return bool((p or {}).get("lesao"))


def de_jogador(st, cid, eid):
    """Equipe de uma pessoa (no multijogador: de qualquer jogador, mesmo numa semana em que a IA conduz)."""
    mp = st.get("multiplayer")
    if mp:
        return any(j["categoria"] == cid and j["equipe"] == eid and not j.get("eliminado")
                   for j in mp["jogadores"].values())
    return eh_humana(st, cid, eid)


# ---------------------------------------------------------------- sorteio no evento
def sortear_vitimas(categoria, carros, rng):
    """[(carro, 'lesao'|'morte'|None)] para os carros de uma batida grave."""
    b = cfg(categoria)
    out = []
    for c in carros:
        r = rng.random()
        if r < b["prob_morte"]:
            out.append((c, "morte"))
        elif r < b["prob_morte"] + b["prob_lesao"]:
            out.append((c, "lesao"))
        else:
            out.append((c, None))
    return out


# ---------------------------------------------------------------- aplicação no jogo
def aplicar(st, cid, vitimas, rng):
    for v in vitimas or []:
        p = st["pilotos"].get(v["piloto"])
        if not p:
            continue
        if v["tipo"] == "morte":
            falecer(st, cid, p, v.get("evento", ""))
        else:
            lesionar(st, cid, p, rng, v.get("evento", ""), v.get("evento_id"))


def lesionar(st, cid, p, rng, onde="", evento_id=None):
    b = cfg(st["categorias"][cid]["categoria"])
    lo, hi = b["lesao_corridas"]
    corridas = rng.randint(int(lo), int(hi))
    plo, phi = b["lesao_perda_atributos"]
    perdas = {}
    for k in b["atributos_afetados"]:
        if k in p["atributos"]:
            n = rng.randint(int(plo), int(phi))
            perdas[k] = n
            p["atributos"][k] = int(clamp(p["atributos"][k] - n, 1, 99))
            if k in (p.get("atributos_iniciais") or {}):       # a curva de evolução não devolve o que se perdeu
                p["atributos_iniciais"][k] = int(clamp(p["atributos_iniciais"][k] - n, 1, 99))
    p["lesao"] = {"corridas": corridas, "ano": st["ano"], "perdas": perdas, "evento": evento_id}
    ct = p.get("contrato") or {}
    from .db import NOMES_ATRIBUTOS
    txt_perdas = ", ".join(f"{NOMES_ATRIBUTOS.get(k, k)} −{n}" for k, n in perdas.items())
    noticia(st, f"{p['nome']} se lesiona na batida grave{(' do ' + onde) if onde else ''} e fica fora de {corridas} "
                f"corrida(s) ({txt_perdas}).", cid, "usuario" if _da_pessoa(st, ct) else "piloto",
            equipe=ct.get("equipe"))
    if ct.get("situacao") == "principal" and ct.get("categoria") in st["categorias"]:
        substituir(st, ct["categoria"], ct["equipe"], p)


def falecer(st, cid, p, onde=""):
    ct = p.get("contrato") or {}
    p["falecido_em"] = st["ano"]
    p["contrato"] = None
    p["contrato_futuro"] = None
    p.pop("lesao", None)
    st.setdefault("falecidos", {})[p["id"]] = p
    del st["pilotos"][p["id"]]
    eq = st["categorias"].get(ct.get("categoria"), {}).get("equipes", {}).get(ct.get("equipe"), {})
    noticia(st, f"LUTO: {p['nome']} ({eq.get('nome', 'sem equipe')}) morre em consequência da batida grave"
                f"{(' do ' + onde) if onde else ''}.", cid, "usuario" if _da_pessoa(st, ct) else "piloto",
            equipe=ct.get("equipe"))
    titular = st["pilotos"].get(ct.get("substituto_de"))   # ele próprio substituía um titular lesionado?
    herdeiro = False
    for o in st["pilotos"].values():
        oc = o.get("contrato") or {}
        if oc.get("substituto_de") != p["id"]:
            continue
        if titular:                                       # quem o substituía passa a substituir o titular
            oc["substituto_de"] = titular["id"]
            herdeiro = True
        else:                                             # agora fica (sem titular a esperar)
            oc.pop("substituto_de", None)
            if oc.get("situacao_original"):
                oc["situacao"] = oc.pop("situacao_original")
    if ct.get("situacao") == "principal" and ct.get("categoria") in st["categorias"] and not herdeiro:
        substituir(st, ct["categoria"], ct["equipe"], titular or p)


def _da_pessoa(st, ct):
    return bool(ct.get("equipe")) and de_jogador(st, ct.get("categoria"), ct["equipe"])


def substituir(st, cid, eid, ausente):
    eq = st["categorias"][cid]["equipes"].get(eid)
    if not eq:
        return
    if de_jogador(st, cid, eid):
        tem_reserva = any(p["contrato"]["situacao"] == "teste" and not lesionado(p)
                          for p in pilotos_da_equipe(st, cid, eid))
        noticia(st, f"ATENÇÃO: {eq['nome']} está sem {ausente['nome']}. "
                    + ("Coloque o piloto de testes no carro (Pilotos da equipe > Promover a titular) ou contrate um "
                       "piloto (Mercado)" if tem_reserva else "Contrate um piloto (Mercado)")
                    + " – sem isso o carro não corre.", cid, "usuario", equipe=eid)
        return
    teste = [p for p in pilotos_da_equipe(st, cid, eid)
             if p["contrato"]["situacao"] == "teste" and not lesionado(p)]
    if not teste:
        return                                            # o mercado do PC contrata (vaga aberta)
    p = max(teste, key=lambda x: sum(x["atributos"].values()))
    ct = p["contrato"]
    if "lesao" in ausente:
        ct["situacao_original"] = "teste"
        ct["situacao"] = "principal"
        ct["substituto_de"] = ausente["id"]
    else:                                                 # falecimento: o piloto de testes vira titular (só até o
        from .mercado import promover_a_titular           # fim da temporada se a próxima já tem titulares)
        promover_a_titular(st, cid, eq, p)
    noticia(st, f"{eq['nome']}: o piloto de testes {p['nome']} assume o carro de {ausente['nome']}.", cid, "piloto",
            equipe=eid)


def fim_de_corrida(st, cid, evento_id=None):
    """Uma corrida da categoria passou: desconta a lesão (não a do próprio evento em que se machucou); quem se
    recupera volta e o substituto sai."""
    for p in list(st["pilotos"].values()):
        les = p.get("lesao")
        if not les:
            continue
        ct = p.get("contrato") or {}
        cat_p = ct.get("categoria") or p.get("categoria_atual") or p.get("categoria_origem")
        if cat_p != cid or (evento_id is not None and les.get("evento") == evento_id and les.get("ano") == st["ano"]):
            continue
        les["corridas"] -= 1
        if les["corridas"] > 0:
            continue
        del p["lesao"]
        noticia(st, f"{p['nome']} se recupera da lesão e está liberado para correr.", cid,
                "usuario" if _da_pessoa(st, ct) else "piloto", equipe=ct.get("equipe"))
        if ct.get("situacao") == "principal" and _da_pessoa(st, ct):
            c = st["categorias"][ct["categoria"]]
            limite = c["categoria"]["regras"].get("pilotos_principais_por_equipe") or 99
            titulares = [x for x in pilotos_da_equipe(st, ct["categoria"], ct["equipe"])
                         if x["contrato"]["situacao"] == "principal" and not lesionado(x)]
            if len(titulares) > limite:
                noticia(st, f"ATENÇÃO: {c['equipes'][ct['equipe']]['nome']} tem {len(titulares)} pilotos titulares "
                            f"e só {limite} carros. Decida quem dispensar (Mercado > Pilotos); até lá correm os "
                            f"contratos mais antigos.", ct["categoria"], "usuario", equipe=ct["equipe"])
        _encerrar_substituicoes(st, cid, p["id"], p)


def _encerrar_substituicoes(st, cid, ausente_id, quem_volta):
    """Quem substituía `ausente_id` deixa o carro (o piloto de testes volta a ser de testes; o contratado como
    substituto sai). Em cadeia: quem substituía esse substituto (ele também se lesionou) sai junto."""
    for o in list(st["pilotos"].values()):
        oc = o.get("contrato") or {}
        if oc.get("substituto_de") != ausente_id:
            continue
        if oc.get("situacao_original"):
            oc["situacao"] = oc.pop("situacao_original")
            oc.pop("substituto_de")
        else:
            o["contrato"] = None
            o["categoria_atual"] = oc.get("categoria")
            eq = st["categorias"].get(oc.get("categoria"), {}).get("equipes", {}).get(oc.get("equipe"), {})
            noticia(st, f"{o['nome']} deixa a {eq.get('nome', '?')} com a volta de {quem_volta['nome']} (era "
                        f"substituto).", cid, "usuario" if _da_pessoa(st, oc) else "contrato", equipe=oc.get("equipe"))
        _encerrar_substituicoes(st, cid, o["id"], quem_volta)


def substitutos_sem_titular(st):
    """Virada de temporada: quem substituía um titular lesionado que deixou a equipe (contrato terminou, trocou de
    equipe ou se aposentou) deixa de ser substituto – o piloto de testes volta a ser de testes (senão a equipe
    ficaria com mais titulares que carros); o contratado no mercado segue com o próprio contrato."""
    mudou = True
    while mudou:                                           # em cadeia: o substituto de um substituto que saiu
        mudou = False
        for o in st["pilotos"].values():
            oc = o.get("contrato") or {}
            alvo_id = oc.get("substituto_de")
            if not alvo_id:
                continue
            ac = (st["pilotos"].get(alvo_id) or {}).get("contrato") or {}
            if ac.get("categoria") == oc.get("categoria") and ac.get("equipe") == oc.get("equipe") \
                    and ac.get("situacao") == "principal":
                continue                                   # o titular ainda é da equipe: segue substituindo
            oc.pop("substituto_de")
            mudou = True
            if oc.get("situacao_original"):
                oc["situacao"] = oc.pop("situacao_original")
                eq = st["categorias"].get(oc.get("categoria"), {}).get("equipes", {}).get(oc.get("equipe"), {})
                noticia(st, f"{o['nome']} volta a ser piloto de testes da {eq.get('nome', '?')}.", oc.get("categoria"),
                        "usuario" if _da_pessoa(st, oc) else "piloto", equipe=oc.get("equipe"))
