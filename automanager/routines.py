"""Rotinas do motor do jogo, executadas a cada semana ("Continuar").

Ordem da semana:
  1. eventos da semana: corridas (a do usuário já vem jogada na tela do evento; as demais são
     simuladas em segundo plano), finanças da corrida, contratos por corridas, notícias
  2. desenvolvimento das equipes do PC
  3. mercado: chassis/motores, pilotos (inclui propostas do usuário) e patrocinadores
  4. avança a semana; depois da última, vira a temporada
"""
import random

from . import saude, campeonato, carreira, contratos, desenvolvimento, economia, mercado, state, regulamento, \
    fornecedores, tempo_base
from .state import financas_zeradas, lancar, noticia, pilotos_da_equipe

SEMANAS_POR_TEMPORADA = 52

# compatibilidade com o código anterior
corridas_na_temporada = mercado.corridas_na_temporada


# ====================================================================== avanço
def avancar_semana(st, rng=random):
    """Avança uma semana. Retorna a lista de notícias geradas nesta semana."""
    inicio = len(st["noticias"])
    for cid in st["categorias"]:
        _processar_eventos_da_semana(st, cid, rng)
    economia.rotina(st)
    for cid in regulamento.semanal(st, rng):          # regras da próxima temporada anunciadas
        desenvolvimento.reavaliar_ia(st, cid)
    desenvolvimento.rotina_ia(st, st["semana"])
    mercado.rotina_partes(st, rng)
    mercado.rotina_pilotos(st, rng)
    mercado.rotina_patrocinadores(st, rng)
    st["semana"] += 1
    if st["semana"] > SEMANAS_POR_TEMPORADA:
        nova_temporada(st, rng)
    mercado.garantir_minimo(st, rng)                  # corrida na nova semana: o PC completa o mínimo de pilotos
    _avisar_minimo(st)
    return st["noticias"][inicio:]


def _avisar_minimo(st):
    """Equipe de pessoa abaixo do mínimo de pilotos para a corrida desta semana: aviso (o Continuar fica bloqueado)."""
    for cid, eid, falta, ev in mercado.equipes_curtas(st, humanas_apenas=True):
        minimo = mercado.minimo_pilotos(st, cid)
        noticia(st, f"ATENÇÃO: {state.quem(st, cid, eid, True)} precisa de {minimo} pilotos titulares para o "
                    f"{ev['nome']} e tem {minimo - falta}. Contrate em Mercado > Pilotos – sem isso a semana não "
                    f"avança.", cid, "usuario", equipe=eid)


def corrida_do_usuario_na_semana(st):
    """Pista da corrida da categoria do usuário nesta semana (ainda não disputada) ou None."""
    cid = st["usuario"]["categoria"]
    for ev in st["categorias"][cid]["calendario"]:
        if ev.get("ativo") and ev["especie"] == "corrida" and ev["semana"] == st["semana"] \
                and not campeonato.ja_disputado(st, cid, ev["id"]):
            return ev
    return None


def teste_do_usuario_na_semana(st):
    """Pista do teste coletivo da categoria do usuário nesta semana (ainda não disputado) ou None."""
    cid = st["usuario"]["categoria"]
    if not st["categorias"][cid]["categoria"]["regras"].get("testes_coletivos"):
        return None
    feitos = {t["evento"] for t in campeonato.testes_da_temporada(st, cid)}
    for ev in st["categorias"][cid]["calendario"]:
        if ev.get("ativo") and ev["especie"] == "treino" and ev["semana"] == st["semana"] and ev["id"] not in feitos:
            return ev
    return None


def noticias_do_teste(st, cid, reg):
    from .util import tempo_volta
    c = st["categorias"][cid]
    if not reg or not reg["geral"]:
        return
    top = ", ".join(f"{l['pos']}º {l['nome']} ({l['equipe_nome']}) {tempo_volta(l['melhor'])}" for l in reg["geral"][:3])
    noticia(st, f"{c['categoria']['nome']}: {reg['nome']} em {reg['local']} – mais rápidos: {top}.", cid, "resultado")
    for hcid, heid in sorted(state.humanas(st)):
        if hcid != cid:
            continue
        meus = [l for l in reg["geral"] if l["equipe"] == heid]
        if meus:
            lista = "; ".join(f"{l['nome']} {l['pos']}º ({tempo_volta(l['melhor'])}, {l.get('voltas_total', 0)} voltas)"
                              for l in meus)
            noticia(st, f"{state.quem(st, cid, heid)} no teste: {lista}. Veja em Histórico > Temporada atual.", cid,
                    "usuario", equipe=heid)


def _processar_eventos_da_semana(st, cid, rng):
    c = st["categorias"][cid]
    regras = c["categoria"]["regras"]
    for ev in c["calendario"]:
        if not ev.get("ativo") or ev["semana"] != st["semana"]:
            continue
        if ev["especie"] == "treino":
            if regras.get("testes_coletivos"):
                feito = next((t for t in campeonato.testes_da_temporada(st, cid) if t["evento"] == ev["id"]), None)
                if feito is None:
                    noticias_do_teste(st, cid, campeonato.simular_teste_coletivo(st, cid, ev, rng))
                elif not feito.get("noticiado"):
                    noticias_do_teste(st, cid, feito)
                feito = next((t for t in campeonato.testes_da_temporada(st, cid) if t["evento"] == ev["id"]), None)
                if feito:
                    feito["noticiado"] = True
            continue
        if not campeonato.ja_disputado(st, cid, ev["id"]):
            mercado.garantir_minimo(st, rng, cid, ev)
            campeonato.simular_em_segundo_plano(st, cid, ev, rng)
        reg = next((r for r in contratos.resultados_da_temporada(st, cid) if r["evento"] == ev["id"]), None)
        for eq in c["equipes"].values():
            if eq.get("ativa"):
                _financas_corrida(st, cid, eq)
        economia.pagar_premios(st, cid, reg)
        mercado.fim_de_corrida_pilotos(st, cid, ev["id"])
        saude.fim_de_corrida(st, cid, ev["id"])
        mercado.fim_de_corrida_partes(st, cid)
        if reg and reg.get("cancelada"):
            noticia(st, f"{c['categoria']['nome']}: o {ev['nome']} é cancelado (nenhuma volta completa) e não vale "
                        f"pontos.", cid, "resultado")
        elif reg and reg["resultado"]:
            v = reg["resultado"][0]
            pod = ", ".join(f"{l['pos']}º {l['nome']}" for l in reg["resultado"][1:3])
            noticia(st, f"{c['categoria']['nome']}: {v['nome']} ({v['equipe_nome']}) vence o {ev['nome']}. "
                        f"Pódio: {pod}.", cid, "resultado")


def _lancar(eq, tipo, chave, valor):
    lancar(eq, tipo, chave, valor)


def _financas_corrida(st, cid, eq):
    c = st["categorias"][cid]
    regras = c["categoria"]["regras"]
    n = corridas_na_temporada(c)
    for p in pilotos_da_equipe(st, cid, eq["id"]):
        _lancar(eq, "despesas", "salarios", p["contrato"].get("valor_por_corrida", 0))
    for parte in ("chassis", "motor"):
        info = eq.get(parte) or {}
        if info.get("origem") not in (None, "proprio") and info.get("contrato"):
            valor = info["contrato"].get("valor_por_corrida", 0)
            _lancar(eq, "despesas", parte, valor)
            dono = state.dono_da_parte(st, cid, eq, parte)
            if dono:                                       # a equipe que faz a peça recebe do cliente
                _lancar(dono, "receitas", "fornecimento", valor)
    if regras.get("patrocinios"):
        for pat in c["patrocinadores"].values():
            ct = pat.get("contrato")
            if not pat.get("ativo") or not ct or ct.get("equipe") != eq["id"]:
                continue
            valor = ct["valor"] if ct.get("pagamento") == "por_corrida" else ct["valor"] / n
            _lancar(eq, "receitas", "patrocinio", valor)
            if ct.get("unidade") == "corridas":
                ct["duracao"] -= 1
                if ct["duracao"] <= 0:
                    pat["contrato"] = None
                    noticia(st, f"Termina o contrato de patrocínio da {pat['nome']} com a {eq['nome']}.",
                            cid, "patrocinio")
    economia.pagar_parcelas(st, cid, eq)
    tv = regras.get("renda_tv") or {}
    if economia.tv_ativa(st, c["categoria"]):            # pela classificação final da temporada anterior
        _lancar(eq, "receitas", "tv", tv.get("valor_medio_por_equipe", 0) / n * economia.fator_tv(st, cid, eq["id"]))


# ====================================================================== nova temporada
def nova_temporada(st, rng=random):
    ano_ant = st["ano"]
    campeonato.fechar_temporada(st, ano_ant)
    for cid, c in st["categorias"].items():
        final = st["temporadas"].get(str(ano_ant), {}).get(cid, {}).get("final")
        if final and final["pilotos"]:
            noticia(st, f"{c['categoria']['nome']} {ano_ant}: {final['pilotos'][0]['nome']} é o campeão "
                        f"({final['pilotos'][0]['pontos']} pts); {final['equipes'][0]['nome']} vence entre as equipes.",
                    cid, "resultado")
    st["ano"] += 1
    st["semana"] = 1
    for c in st["categorias"].values():               # motores novos e cota zerada a cada temporada
        for eq in c["equipes"].values():
            eq.pop("motores", None)
    for cid, c in st["categorias"].items():
        c.setdefault("historico_financas", {})
        for eq in c["equipes"].values():
            c["historico_financas"].setdefault(eq["id"], {})[str(ano_ant)] = eq["financas"]["ano"]
            eq["financas"]["ano"] = financas_zeradas()
        c["categoria"]["ano"] = st["ano"]
        _inflacao(st, cid, rng)
    desenvolvimento.aplicar_projetos(st, st["ano"])
    desenvolvimento.evoluir_fabricantes(st, rng)
    fornecedores.evoluir(st, rng)
    for cid in st["categorias"]:
        tempo_base.virada(st, cid)                     # antes do regulamento: usa a grande mudança anunciada
        regulamento.virada(st, cid)
    desenvolvimento.ajustar_calibracao(st)
    _virada_contratos_pilotos(st)
    for cid in st["categorias"]:
        mercado.virada_partes(st, cid)
        _virada_patrocinadores(st, cid, rng)
        _virada_equipes(st, cid, rng)
        _virada_calendario(st, cid, rng)
    for p in st["pilotos"].values():
        p["idade"] = p.get("idade", 20) + 1
    mercado.aplicar_idade_maxima(st)
    carreira.virada(st, rng)
    saude.substitutos_sem_titular(st)              # depois dos fins de contrato e das aposentadorias
    mercado.atualizar_precos_chassis(st)
    noticia(st, f"Começa a temporada {st['ano']}.", None, "temporada")


def _inflacao(st, cid, rng):
    c = st["categorias"][cid]
    cat = c["categoria"]
    media = cat["regras"].get("inflacao_media_anual", 0.0)
    taxa = max(-0.02, media * rng.uniform(0.5, 1.5)) if media else 0.0
    if not taxa:
        return
    f = 1 + taxa
    regras = cat["regras"]
    regras["orcamento_medio"] = round(regras["orcamento_medio"] * f, -3)
    if regras.get("renda_tv"):
        regras["renda_tv"]["valor_medio_por_equipe"] = round(regras["renda_tv"]["valor_medio_por_equipe"] * f, -2)
    if regras.get("premios_corrida"):
        for k in ("vitoria", "podio", "por_ponto"):
            if regras["premios_corrida"].get(k):
                regras["premios_corrida"][k] = round(regras["premios_corrida"][k] * f, -2)
    mp = cat["simulacao"]["mercado_pilotos"]
    for k in ("salario_minimo_por_corrida", "salario_maximo_por_corrida"):
        mp[k] = round(mp[k] * f, -2)
    for bloco in (cat.get("desenvolvimento_inicial") or {}, cat.get("desenvolvimento") or {}):
        for parte in bloco.values():
            if isinstance(parte, dict) and "custo_por_ponto" in parte:
                parte["custo_por_ponto"] = round(parte["custo_por_ponto"] * f, -2)
    for ent in list(c["chassis"].values()) + list(c["motores"].values()):
        if ent.get("contrato"):
            ent["contrato"]["valor_por_corrida"] = round(ent["contrato"]["valor_por_corrida"] * f, -2)
    for eq in c["equipes"].values():
        for parte in ("chassis", "motor", "chassis_futuro", "motor_futuro"):
            info = eq.get(parte) or {}
            if info.get("contrato"):
                info["contrato"]["valor_por_corrida"] = round(info["contrato"]["valor_por_corrida"] * f, -2)
    for pat in c["patrocinadores"].values():
        if pat.get("contrato"):
            pat["contrato"]["valor"] = round(pat["contrato"]["valor"] * f, -2)
        if pat.get("valor_base"):
            pat["valor_base"] = round(pat["valor_base"] * f, -3)
    for p in st["pilotos"].values():
        for k in ("contrato", "contrato_futuro"):
            ct = p.get(k)
            if ct and ct.get("categoria") == cid:
                ct["valor_por_corrida"] = round(ct["valor_por_corrida"] * f, -2)
    noticia(st, f"{cat['nome']}: inflação de {taxa * 100:.1f}% atualiza custos e receitas.", cid, "economia")


def _virada_contratos_pilotos(st):
    for p in st["pilotos"].values():
        c = p.get("contrato")
        if c:
            c.pop("corridas_definidas", None)      # a lista vale só para a temporada em que foi definida
        if c and not contratos.por_corridas(c):
            c["temporadas"] = c.get("temporadas", 1) - 1
            if c["temporadas"] <= 0:
                p["categoria_atual"] = c.get("categoria")
                p["contrato"] = None
        f = p.get("contrato_futuro")
        if f and not p.get("contrato") and int(f.get("inicio_ano") or st["ano"]) <= st["ano"]:
            p["contrato"], p["contrato_futuro"] = f, None        # o contrato futuro começa no seu ano
            p["categoria_atual"] = p["contrato"].get("categoria")


def _virada_patrocinadores(st, cid, rng):
    c = st["categorias"][cid]
    for pat in c["patrocinadores"].values():
        ct = pat.get("contrato")
        eq = c["equipes"].get(ct["equipe"]) if ct else None
        if pat.get("ativo"):
            if ct and ct.get("unidade") == "temporadas":
                ct["duracao"] -= 1
                if ct["duracao"] <= 0:
                    pat["contrato"] = None
                    noticia(st, f"Termina o patrocínio da {pat['nome']} à {eq['nome'] if eq else '?'}.",
                            cid, "patrocinio")
            if rng.random() < pat.get("prob_fechamento", 0):
                pat["ativo"], pat["contrato"] = False, None
                noticia(st, f"A empresa {pat['nome']} ({pat['ramo']}) encerra suas atividades no esporte.",
                        cid, "patrocinio")
        elif rng.random() < pat.get("prob_surgimento", 0):
            pat["ativo"] = True
            noticia(st, f"A empresa {pat['nome']} ({pat['ramo']}, {pat['pais']}) passa a buscar equipes "
                        f"para patrocinar.", cid, "patrocinio")


def _virada_equipes(st, cid, rng):
    c = st["categorias"][cid]
    for eq in c["equipes"].values():
        if mercado.eh_usuario(st, cid, eq["id"]) or state.eh_da_pessoa(st, cid, eq["id"]):
            continue
        if eq.get("ativa"):
            if rng.random() < eq.get("prob_fechamento", 0):
                eq["ativa"] = False
                for p in st["pilotos"].values():
                    for k in ("contrato", "contrato_futuro"):
                        ct = p.get(k)
                        if ct and ct.get("categoria") == cid and ct.get("equipe") == eq["id"]:
                            p[k] = None
                            p["categoria_atual"] = cid
                for pat in c["patrocinadores"].values():
                    if pat.get("contrato") and pat["contrato"].get("equipe") == eq["id"]:
                        pat["contrato"] = None
                noticia(st, f"FECHAMENTO: a {eq['nome']} encerra as atividades na {c['categoria']['nome']}. "
                            f"Seus pilotos estão livres no mercado.", cid, "equipe")
        elif _surge(st, c, eq, rng):
            _ativar_equipe(st, cid, eq, rng)


def _surge(st, c, eq, rng):
    """Equipe inativa surge: no ano definido (na equipe ou na lista da categoria) ou por sorteio."""
    if eq.get("falida_em") == st["ano"] - 1:
        return False
    anos = [x.get("ano") for x in c["categoria"].get("novas_equipes", []) if x.get("equipe") == eq["id"]]
    if eq.get("ano_surgimento"):
        anos.append(eq["ano_surgimento"])
    definidos = [a for a in anos if a]
    if definidos:
        return st["ano"] in definidos
    na_lista = any(x.get("equipe") == eq["id"] for x in c["categoria"].get("novas_equipes", []))
    prob = eq.get("prob_surgimento", 0) or (0.15 if na_lista else 0)
    return rng.random() < prob


def _ativar_equipe(st, cid, eq, rng):
    c = st["categorias"][cid]
    regras = c["categoria"]["regras"]
    eq["ativa"] = True
    eq["semanas_negativo"] = 0
    eq.pop("verba_semanal_dev", None)
    eq["financas"]["caixa"] = regras["orcamento_medio"] * rng.uniform(0.7, 1.2)
    # sem carro próprio cadastrado: constrói do zero com parte do orçamento
    for parte, tabela in (("chassis", c["chassis"]), ("motor", c["motores"])):
        info = eq.get(parte) or {}
        if info.get("origem") == "proprio" and info.get("id") not in tabela:
            pode = regras.get("desenvolvimento_chassis_por_equipe") if parte == "chassis" else \
                (regras.get("desenvolvimento_motor_por_equipe") and
                 (not regras.get("equipes_com_desenvolvimento_de_motor") or
                  eq["id"] in regras["equipes_com_desenvolvimento_de_motor"]))
            if pode and c["categoria"].get("desenvolvimento"):
                desenvolvimento.construir_do_zero(st, cid, eq, parte, eq["financas"]["caixa"] *
                                                  (0.35 if parte == "chassis" else 0.15))
            else:
                eq[parte] = None
    noticia(st, f"NOVA EQUIPE: a {eq['nome']} ({eq['nacionalidade']}) é confirmada na "
                f"{c['categoria']['nome']} {st['ano']}.", cid, "equipe")


def _virada_calendario(st, cid, rng):
    """Entrada e saída de pistas do calendário. Anos fixados no evento (anos_entrada / anos_saida) valem no lugar
    do sorteio naquele ano; nos outros anos, prob_ativar / prob_inativar."""
    c = st["categorias"][cid]
    for ev in c["calendario"]:
        entra = st["ano"] in (ev.get("anos_entrada") or [])
        sai = st["ano"] in (ev.get("anos_saida") or [])
        if ev.get("ativo"):
            if sai or (not entra and rng.random() < ev.get("prob_inativar", 0)):
                ev["ativo"] = False
                noticia(st, f"{c['categoria']['nome']}: {ev['nome']} ({ev['local']}) sai do calendário {st['ano']}.",
                        cid, "calendario")
        elif entra or (not sai and rng.random() < ev.get("prob_ativar", 0)):
            if ev["especie"] == "corrida" and any(
                    o is not ev and o.get("ativo") and o["especie"] == "corrida"
                    and (o["nome"], o.get("local")) == (ev["nome"], ev.get("local")) for o in c["calendario"]):
                continue                      # a pista já está no calendário: não entra uma 2ª corrida nela
            ev["ativo"] = True
            noticia(st, f"{c['categoria']['nome']}: nova corrida! {ev['nome']} ({ev['local']}) entra no "
                        f"calendário {st['ano']}, na semana {ev['semana']}.", cid, "calendario")
