"""Plano de evento: o que o jogador do multijogador decide antes de um evento que não acompanha ao vivo.

Por piloto (id global), um bloco por grupo de sessão:
  {"treino":        {"acerto_modo": "engenheiro"|"fixo", "acerto": {aerodinamica, cambio, suspensao, freios: 0-100},
                     "pneu": composto|"auto",
                     "ordens": {agressividade, uso_motor, uso_carro: -2..2}},
   "classificacao": {... igual ao treino},
   "corrida":       {... + "combustivel": voltas|None (automático),
                     "paradas": "auto" | [[composto, voltas], ...] (stints em ordem; o 1º é o pneu de largada)}}
Treinos livres e dias de teste coletivo usam "treino"; classificação e corrida classificatória usam
"classificacao"; a corrida usa "corrida". Sem plano, o carro é conduzido pela IA.
"""
from .modelo import PARAMETROS_ACERTO, ORDENS

GRUPOS = ("treino", "classificacao", "corrida")
GRUPO_DA_SESSAO = {"treino": "treino", "classificacao": "classificacao", "corrida": "corrida",
                   "corrida_classificatoria": "classificacao"}
LIMITE_ORDEM = 2


def grupo_padrao(grupo):
    # engenheiro: a equipe acerta o carro a cada sessão pelo que aprende no treino (como as do PC) – o ideal real
    # do evento é escondido, então valores fixos são um chute; fixo: usa os valores de "acerto"
    g = {"acerto_modo": "engenheiro", "acerto": {k: 50 for k in PARAMETROS_ACERTO}, "pneu": "auto",
         "ordens": {k: 0 for k in ORDENS}}
    if grupo == "corrida":
        g.update({"combustivel": None, "paradas": "auto"})
    return g


def plano_padrao():
    return {g: grupo_padrao(g) for g in GRUPOS}


def normalizar(plano, compostos, troca_de_pneus=True):
    """Corrige valores fora da faixa e compostos que a categoria não disponibiliza. Sem troca de pneus na
    categoria, todos os stints usam o pneu de largada (as paradas servem só para combustível/reparo)."""
    out = {}
    for grupo in GRUPOS:
        g = (plano or {}).get(grupo)
        if not isinstance(g, dict):
            continue
        n = grupo_padrao(grupo)
        # planos antigos (sem o modo) tinham valores digitados: continuam fixos
        n["acerto_modo"] = g["acerto_modo"] if g.get("acerto_modo") in ("engenheiro", "fixo") else \
            ("fixo" if "acerto" in g else "engenheiro")
        for k in PARAMETROS_ACERTO:
            try:
                n["acerto"][k] = max(0, min(100, int((g.get("acerto") or {}).get(k, 50))))
            except (TypeError, ValueError):
                pass
        for k in ORDENS:
            try:
                n["ordens"][k] = max(-LIMITE_ORDEM, min(LIMITE_ORDEM, int((g.get("ordens") or {}).get(k, 0))))
            except (TypeError, ValueError):
                pass
        n["pneu"] = g.get("pneu") if g.get("pneu") in compostos else "auto"
        if grupo == "corrida":
            try:
                n["combustivel"] = max(1, int(g["combustivel"])) if g.get("combustivel") not in (None, "") else None
            except (TypeError, ValueError):
                n["combustivel"] = None
            par = g.get("paradas")
            if isinstance(par, list):
                stints = []
                for s in par:
                    try:
                        if s[0] in compostos and int(s[1]) >= 1:
                            stints.append([s[0], int(s[1])])
                    except (TypeError, ValueError, IndexError):
                        continue
                if stints and not troca_de_pneus:
                    stints = [[stints[0][0], n] for _c, n in stints]
                n["paradas"] = stints or "auto"
                if stints:
                    n["pneu"] = stints[0][0]
        out[grupo] = n
    return out


def aplicar(ev, planos):
    """Chamado logo depois de ev.proxima_sessao() e antes de sessao.iniciar(). planos = {piloto_id: plano}.
    Carros com plano para o grupo da sessão passam a ser 'do usuário' (a IA não mexe no acerto/estratégia)."""
    tipo = ev.programacao[ev.indice][0]
    grupo = GRUPO_DA_SESSAO.get(tipo)
    compostos = ev.compostos_disponiveis()
    for c in ev.carros:
        c.plano_fixo = None
        g = (planos or {}).get(c.id, {}).get(grupo) if grupo else None
        if not g:
            c.usuario = False
            continue
        c.usuario = True
        if g.get("acerto_modo") == "engenheiro":
            from .modelo import acerto_ia
            c.acerto = acerto_ia(c, ev.modelo.ideal(c, ev.clima.estado), ev.rng)
        else:
            c.acerto = dict(g["acerto"])
        c.ordens = dict(g["ordens"])
        pneu = g.get("pneu") if g.get("pneu") in compostos else None
        c.pneu_inicial = pneu
        if grupo == "corrida":
            par = g.get("paradas")
            if isinstance(par, list) and par:
                c.plano_fixo = [list(s) for s in par]
                c.plano_corrida = [list(s) for s in par]
                c.pneu_inicial = par[0][0]
                c.estrategia_auto = False
            else:
                c.estrategia_auto = True
            c.combustivel_inicial = g.get("combustivel")
        else:
            # pneu escolhido em todas as saídas; "auto" = equipe escolhe pelo clima
            c.estrategia_auto = pneu is None
