"""Mercado: pilotos (usuário e PC, com movimentação entre categorias por tier),
chassis/motores de terceiros (quando não há desenvolvimento) e patrocinadores.
"""
import random

from . import ratings, campeonato, contratos
from .state import noticia, pilotos_da_equipe, chassis_da_equipe, motor_da_equipe, lancar, eh_humana, quem
from .util import clamp, dinheiro


def corridas_na_temporada(c):
    return max(1, sum(1 for e in c["calendario"] if e.get("ativo") and e["especie"] == "corrida"))


def eh_usuario(st, cid, eid):
    """Equipe controlada por pessoa (um jogador ou jogadores do multijogador)."""
    return eh_humana(st, cid, eid)


# ====================================================================== pilotos – disponibilidade
def categoria_do_piloto(p):
    c = p.get("contrato")
    return (c or {}).get("categoria") or p.get("categoria_atual") or p.get("categoria_origem")


def livre_agora(p):
    return not p.get("contrato") and not p.get("contrato_futuro")


def ano_de_inicio(st, inicio):
    """'agora' = temporada atual, 'proxima' = a seguinte, ou um ano (qualquer temporada futura)."""
    if inicio in ("agora", "atual"):
        return st["ano"]
    if inicio in ("proxima", None, ""):
        return st["ano"] + 1
    return int(inicio)


def ano_da_oferta(st, o):
    return st["ano"] if o["quando"] == "atual" else int(o.get("ano_inicio") or st["ano"] + 1)


def fim_do_contrato(st, ct, cid=None):
    """Última temporada coberta por um contrato (em vigor ou futuro, com 'inicio_ano')."""
    if not ct:
        return st["ano"] - 1
    cid = cid or ct.get("categoria")
    n = corridas_na_temporada(st["categorias"][cid])
    ini = ct.get("inicio_ano") or st["ano"]
    if ini > st["ano"]:                                    # contrato futuro: conta a partir do ano de início
        anos = -(-ct["corridas"] // n) if contratos.por_corridas(ct) else ct.get("temporadas", 1)
        return ini + max(1, anos) - 1
    if contratos.por_corridas(ct):
        rest = contratos.corridas_restantes(st, cid)
        return st["ano"] if ct["corridas"] <= rest else st["ano"] + -(-(ct["corridas"] - rest) // n)
    return st["ano"] + ct.get("temporadas", 1) - 1


def livre_em(st, p, ano):
    """Disponível para um contrato que começa em `ano` (futuro): sem contrato futuro, sem se aposentar antes e com
    o contrato atual terminando antes desse ano."""
    if p.get("contrato_futuro"):
        return False                                   # um só contrato futuro por piloto
    if p.get("ano_aposentadoria") and p["ano_aposentadoria"] <= ano:
        return False
    c = p.get("contrato")
    return not c or fim_do_contrato(st, c) < ano


def livre_proxima(st, p):
    """Disponível para a próxima temporada: sem contrato ou com contrato terminando nesta temporada."""
    return livre_em(st, p, st["ano"] + 1)


def temporadas_antes_do_futuro(st, p):
    """Piloto sem contrato agora mas já assinado para um ano futuro: quantas temporadas um contrato que começa
    agora pode durar sem chegar ao contrato futuro (None = sem limite)."""
    f = p.get("contrato_futuro")
    return None if not f else max(1, int(f.get("inicio_ano") or st["ano"] + 1) - st["ano"])


def _vagas_alvo(st, cid):
    regras = st["categorias"][cid]["categoria"]["regras"]
    return {"principal": regras.get("pilotos_principais_por_equipe", 2),
            "teste": regras.get("pilotos_de_teste_por_equipe", 0) if regras.get("pilotos_de_teste") else 0}


def vagas_no_ano(st, cid, eq, ano):
    """{situacao: vagas} da equipe numa temporada futura (contratos atuais que chegam até lá + contratos futuros
    que cobrem esse ano)."""
    alvo = _vagas_alvo(st, cid)
    ocup = {k: 0 for k in alvo}
    for p in st["pilotos"].values():
        c, f = p.get("contrato"), p.get("contrato_futuro")
        if c and c.get("categoria") == cid and c.get("equipe") == eq["id"] and fim_do_contrato(st, c) >= ano:
            ocup[c["situacao"]] = ocup.get(c["situacao"], 0) + 1
        if f and f.get("categoria") == cid and f.get("equipe") == eq["id"] \
                and int(f.get("inicio_ano") or st["ano"] + 1) <= ano <= fim_do_contrato(st, f):
            ocup[f["situacao"]] = ocup.get(f["situacao"], 0) + 1
    return {k: max(0, alvo[k] - ocup.get(k, 0)) for k in alvo}


def vagas(st, cid, eq):
    """({situacao: vagas agora}, {situacao: vagas na próxima temporada})."""
    alvo = _vagas_alvo(st, cid)
    atual = {k: 0 for k in alvo}
    for p in st["pilotos"].values():
        c = p.get("contrato")
        if c and c.get("categoria") == cid and c.get("equipe") == eq["id"]:
            if not (c["situacao"] == "principal" and p.get("lesao")):   # titular lesionado: vaga aberta agora
                atual[c["situacao"]] = atual.get(c["situacao"], 0) + 1
    return ({k: max(0, alvo[k] - atual.get(k, 0)) for k in alvo}, vagas_no_ano(st, cid, eq, st["ano"] + 1))


def travado(st, p):
    """Estabilidade: contrato que começou nesta temporada não pode ser comprado nem rescindido pelo PC
    até a temporada seguinte."""
    ct = p.get("contrato") or {}
    return ct.get("inicio_ano") is not None and ct["inicio_ano"] >= st["ano"]


def mobilidade(st, cid_destino, p):
    """Multiplicador da chance de o piloto mudar para a categoria de destino (tiers)."""
    origem = categoria_do_piloto(p)
    if not origem or origem == cid_destino or origem not in st["categorias"]:
        return 1.0
    dest = st["categorias"][cid_destino]["categoria"]
    t_dest = dest.get("tier", 1)
    t_orig = st["categorias"][origem]["categoria"].get("tier", 1)
    mob = dest.get("mobilidade") or {}
    if t_orig > t_dest:
        return mob.get("de_tier_inferior", 1.0)
    if t_orig < t_dest:
        return mob.get("de_tier_superior", 0.3)
    return mob.get("mesmo_tier", 0.6)


def regras_idade(categoria):
    """regras.idade_pilotos: idade_maxima (limite rígido: acima dele a categoria não contrata e o contrato termina
    na virada de temporada), preferida_ate e penalidade_por_ano (as equipes do PC desvalorizam, na escolha, cada
    ano acima da idade preferida – categorias de base preferem pilotos jovens). Vazio = sem restrição."""
    r = categoria["regras"].get("idade_pilotos") or {}
    return r.get("idade_maxima"), r.get("preferida_ate"), float(r.get("penalidade_por_ano") or 0)


def idade_no_inicio(st, p, quando):
    """Idade do piloto no início do contrato ('agora', 'proxima' ou o ano de início)."""
    return p.get("idade", 25) + ano_de_inicio(st, quando) - st["ano"]


def acima_da_idade(categoria, idade):
    mx = regras_idade(categoria)[0]
    return bool(mx) and idade > mx


def penalidade_idade(categoria, idade):
    _, pref, pen = regras_idade(categoria)
    return pen * max(0, idade - pref) if pref else 0.0


def pedido_estimado(st, p, categoria, eid=""):
    """O que a equipe acha que o piloto pede por corrida: (estimativa, mínimo, máximo). O valor real
    (salario_pedido) fica escondido – a estimativa erra até ±20% e a faixa tem ±10% em volta dela. O erro é fixo
    para o mesmo piloto, equipe e temporada (não muda a cada vez que a tela abre)."""
    real = salario_pedido(p, categoria)
    rng = random.Random(f"{st.get('semente', 0)}|{st.get('ano')}|{eid}|{p['id']}")
    est = real * rng.uniform(0.8, 1.2)
    return round(est, -2), round(est * 0.9, -2), round(est * 1.1, -2)


def corridas_do_contrato(st, cid, duracao, unidade, inicio):
    """Quantas corridas um contrato novo cobre (para mostrar o valor total antes de fechar)."""
    duracao = max(1, int(duracao))
    if unidade == "corridas":
        return duracao
    por_temp = corridas_na_temporada(st["categorias"][cid])
    if ano_de_inicio(st, inicio) == st["ano"]:
        return contratos.corridas_restantes(st, cid) + (duracao - 1) * por_temp
    return duracao * por_temp


def salario_pedido(p, categoria):
    m = categoria["simulacao"]["mercado_pilotos"]
    nota = ratings.nota_geral_piloto(p, categoria)
    f = clamp((nota - 40) / 55, 0, 1) ** 2
    return m["salario_minimo_por_corrida"] + (m["salario_maximo_por_corrida"] - m["salario_minimo_por_corrida"]) * f


def perspectiva_equipe(st, cid, eq):
    """0..1: possibilidades que a equipe oferece (carro + recursos)."""
    carro = ratings.nota_geral_carro(chassis_da_equipe(st, cid, eq), motor_da_equipe(st, cid, eq),
                                     st["categorias"][cid]["categoria"])
    return clamp((carro * 0.6 + eq.get("recursos", 50) * 0.4) / 100, 0, 1)


# ====================================================================== multas contratuais
def fator_multa(st, cid):
    return (st["categorias"][cid]["categoria"].get("contratos") or {}).get("fator_multa", 0.5)


def corridas_restantes_contrato(st, ct, cid, so_apos_esta_temporada=False, a_partir_de=None):
    """Corridas que ainda faltam no contrato (opcionalmente, só as posteriores a esta temporada, ou só as das
    temporadas a partir de `a_partir_de` – a parte que se sobrepõe a um contrato futuro)."""
    restam_temp = contratos.corridas_restantes(st, cid)
    n = corridas_na_temporada(st["categorias"][cid])
    if contratos.por_corridas(ct):
        total = ct["corridas"]
    else:
        total = restam_temp + (ct.get("temporadas", 1) - 1) * n
    if so_apos_esta_temporada and a_partir_de is None:
        a_partir_de = st["ano"] + 1
    if a_partir_de is None or a_partir_de <= st["ano"]:
        return total
    return max(0, total - restam_temp - (a_partir_de - st["ano"] - 1) * n)


def multa(st, ct, cid, so_apos_esta_temporada=False, a_partir_de=None):
    """multa = fator × valor por corrida × corridas restantes do contrato (ou só as que se sobrepõem)."""
    if not ct:
        return 0.0
    return fator_multa(st, cid) * ct.get("valor_por_corrida", 0) * \
        corridas_restantes_contrato(st, ct, cid, so_apos_esta_temporada, a_partir_de)


def encurtar_contrato(st, ct, cid, ultimo_ano):
    """O contrato passa a terminar no fim de `ultimo_ano` (o resto foi comprado por outra equipe)."""
    if contratos.por_corridas(ct):
        ct["corridas"] = max(1, contratos.corridas_restantes(st, cid)
                             + (ultimo_ano - st["ano"]) * corridas_na_temporada(st["categorias"][cid]))
    else:
        ct["temporadas"] = max(1, ultimo_ano - st["ano"] + 1)


def rescindir_piloto(st, pid, futuro=False):
    """A equipe encerra o contrato do piloto pagando a multa. Retorna o valor pago."""
    p = st["pilotos"][pid]
    chave = "contrato_futuro" if futuro else "contrato"
    ct = p.get(chave)
    if not ct:
        return 0.0
    cid = ct["categoria"]
    eq = st["categorias"][cid]["equipes"][ct["equipe"]]
    if futuro:
        valor = fator_multa(st, cid) * ct["valor_por_corrida"] * (
            ct["corridas"] if contratos.por_corridas(ct) else ct.get("temporadas", 1) * corridas_na_temporada(
                st["categorias"][cid]))
    else:
        valor = multa(st, ct, cid)
    lancar(eq, "despesas", "multas", valor)
    p[chave] = None
    p["categoria_atual"] = cid
    noticia(st, f"{quem(st, cid, eq['id'])} rescinde o contrato de {p['nome']} e paga multa de {dinheiro(valor)}.",
            cid, "usuario" if eh_usuario(st, cid, eq["id"]) else "contrato", equipe=eq["id"])
    return valor


def multa_parte(st, cid, eq, parte, a_partir_de=None):
    info = eq.get(parte) or {}
    if info.get("origem") in (None, "proprio"):
        return 0.0
    return multa(st, info.get("contrato"), cid, a_partir_de=a_partir_de)


def rescindir_parte(st, cid, eq, parte):
    """Encerra o contrato de chassis/motor pagando a multa ao fornecedor."""
    valor = multa_parte(st, cid, eq, parte)
    if not tem_parte_ativa(eq, parte) or (eq.get(parte) or {}).get("origem") == "proprio":
        return 0.0
    lancar(eq, "despesas", "multas", valor)
    tabela = st["categorias"][cid]["chassis" if parte == "chassis" else "motores"]
    nome_ent = tabela.get(eq[parte]["id"], {}).get("nome", eq[parte]["id"])
    fab = (tabela.get(eq[parte]["id"], {}).get("fabricante") or {})
    dono = fab.get("equipe") if fab.get("tipo") == "equipe" else tabela.get(eq[parte]["id"], {}).get("equipe")
    if dono in st["categorias"][cid]["equipes"]:
        lancar(st["categorias"][cid]["equipes"][dono], "receitas", "multas", valor)
    eq[parte] = None
    noticia(st, f"{quem(st, cid, eq['id'])} rescinde o contrato de {parte} ({nome_ent}) e paga multa de "
                f"{dinheiro(valor)}.", cid, "usuario" if eh_usuario(st, cid, eq["id"]) else "contrato", equipe=eq["id"])
    return valor


# ====================================================================== pilotos – proposta do usuário
def fazer_proposta(st, pid, situacao, valor, duracao, unidade, inicio):
    """Registra a proposta da equipe do usuário. O piloto responde na semana seguinte. `inicio`: 'agora',
    'proxima' ou o ano de início (qualquer temporada futura). Retorna None se aceita para análise, ou o erro."""
    cid, eid = st["usuario"]["categoria"], st["usuario"]["equipe"]
    c = st["categorias"][cid]
    eq = c["equipes"][eid]
    p = st["pilotos"][pid]
    regras = c["categoria"]["regras"]
    try:
        ano = ano_de_inicio(st, inicio)
    except (TypeError, ValueError):
        return "Ano de início inválido."
    if ano < st["ano"]:
        return "O contrato não pode começar numa temporada que já passou."
    if situacao == "teste" and not regras.get("pilotos_de_teste"):
        return "Esta categoria não tem pilotos de teste."
    if acima_da_idade(c["categoria"], idade_no_inicio(st, p, ano)):
        return f"A categoria não aceita pilotos com mais de {regras_idade(c['categoria'])[0]} anos."
    vag_atual, _ = vagas(st, cid, eq)
    ct = p.get("contrato")
    fut = p.get("contrato_futuro")
    da_casa = ct and ct.get("categoria") == cid and ct.get("equipe") == eid
    if ano == st["ano"]:
        if da_casa:
            return "O piloto já é da equipe."
        if fut and ct:
            return "O piloto já assinou com uma equipe para a próxima temporada." \
                if fut.get("inicio_ano") == st["ano"] + 1 else f"O piloto já assinou com uma equipe para {fut['inicio_ano']}."
        if ct and travado(st, p):
            return "O piloto começou contrato com outra equipe nesta temporada: só pode sair a partir da próxima."
        if vag_atual.get(situacao, 0) <= 0:
            return "A equipe não tem vaga livre agora para essa função."
        compra = bool(ct)
        limite = temporadas_antes_do_futuro(st, p)
        if limite is not None:                         # livre agora, mas já assinado para depois: até lá
            max_corr = contratos.corridas_restantes(st, cid) + (limite - 1) * corridas_na_temporada(c)
            if (unidade == "corridas" and duracao > max_corr) or (unidade != "corridas" and duracao > limite):
                return f"O piloto já assinou com outra equipe a partir de {fut['inicio_ano']}: o contrato tem de " \
                       f"terminar antes."
    else:
        if fut:
            return "O piloto já assinou com uma equipe para a próxima temporada." \
                if fut.get("inicio_ano") == st["ano"] + 1 else f"O piloto já assinou com uma equipe para {fut['inicio_ano']}."
        if p.get("ano_aposentadoria") and p["ano_aposentadoria"] <= ano:
            return "O piloto vai se aposentar ao fim desta temporada." if ano == st["ano"] + 1 \
                else f"O piloto vai se aposentar antes de {ano}."
        if vagas_no_ano(st, cid, eq, ano).get(situacao, 0) <= 0:
            return "A equipe não tem vaga para essa função na próxima temporada." if ano == st["ano"] + 1 \
                else f"A equipe não tem vaga para essa função em {ano}."
        if da_casa and fim_do_contrato(st, ct) >= ano:
            return f"O piloto já tem contrato com a equipe até {fim_do_contrato(st, ct)}."
        compra = bool(ct) and not da_casa and fim_do_contrato(st, ct) >= ano
        if compra and travado(st, p) and ct.get("inicio_ano", 0) > st["ano"]:
            return "O piloto acabou de assinar com outra equipe."
    if valor <= 0 or duracao < 1:
        return "Informe salário e duração válidos."
    for y in range(ano + 1, ultimo_ano_do_contrato(st, cid, ano, duracao, unidade) + 1):
        if vagas_no_ano(st, cid, eq, y).get(situacao, 0) <= 0:   # nunca mais pilotos que carros, em nenhum ano
            return f"A equipe não tem vaga para essa função em {y}: o contrato tem de terminar antes."
    st.setdefault("propostas_usuario", {})[f"{cid}|{eid}|{pid}"] = {
        "piloto": pid, "categoria": cid, "equipe": eid, "situacao": situacao, "valor_por_corrida": float(valor),
        "duracao": int(duracao), "unidade": unidade, "quando": "atual" if ano == st["ano"] else "proxima",
        "ano_inicio": ano, "semana": st["semana"], "ano": st["ano"], "compra_contrato": compra}
    if compra:
        m = multa(st, ct, ct["categoria"], a_partir_de=ano)
        noticia(st, f"Se aceitar, {quem(st, cid, eid, True)} pagará {dinheiro(m)} de multa à equipe atual de "
                    f"{p['nome']}.", cid, "usuario", equipe=eid)
    if ano > st["ano"] + 1:
        noticia(st, f"{quem(st, cid, eid)} fez proposta a {p['nome']} ({dinheiro(valor)} por corrida, {duracao} "
                    f"{unidade}, a partir de {ano}). Resposta na próxima semana.", cid, "usuario", equipe=eid)
    else:
        noticia(st, f"{quem(st, cid, eid)} fez proposta a {p['nome']} ({dinheiro(valor)} por corrida, {duracao} "
                    f"{unidade}). Resposta na próxima semana.", cid, "usuario", equipe=eid)
    return None


# ====================================================================== pilotos – rotina semanal
OFERTAS_POR_VAGA = 2          # o PC manda propostas a mais pilotos do que tem vagas (o primeiro que aceitar leva)


def teto_salario(st, cid, eq):
    """Salário por corrida que a equipe do PC pode pagar a um titular."""
    c = st["categorias"][cid]
    mp = c["categoria"]["simulacao"]["mercado_pilotos"]
    principais = c["categoria"]["regras"].get("pilotos_principais_por_equipe", 2) or 1
    # base = o maior entre o caixa e a receita prevista da temporada: com a verba de desenvolvimento
    # gasta, o caixa fica perto da reserva, mas a receita continua pagando os salários
    from .economia import receita_prevista
    base = max(0.0, eq["financas"]["caixa"], receita_prevista(st, cid, eq))
    return base * mp.get("fracao_orcamento_pilotos", 0.2) / corridas_na_temporada(c) / principais


def rotina_pilotos(st, rng=random):
    """Loop: equipes ativas têm pilotos com contrato? Se não, o PC faz propostas.
    As propostas do usuário entram na mesma disputa; o piloto escolhe a melhor."""
    ofertas = {}
    for cid, c in st["categorias"].items():
        categoria = c["categoria"]
        mp = categoria["simulacao"]["mercado_pilotos"]
        n = corridas_na_temporada(c)
        for eq in c["equipes"].values():
            if not eq.get("ativa"):
                continue
            vag_atual, vag_prox = vagas(st, cid, eq)
            if eh_usuario(st, cid, eq["id"]):
                _avisar_usuario(st, cid, eq, vag_atual, vag_prox, mp)
                continue
            pedidos = [("atual", s, st["ano"]) for s, q in vag_atual.items() for _ in range(q)]
            from .saude import de_jogador
            if de_jogador(st, cid, eq["id"]):
                # multijogador, semana conduzida pela IA: a equipe do jogador não contrata titular por conta própria
                pedidos = [x for x in pedidos if x[:2] != ("atual", "principal")]
            if st["semana"] >= mp.get("semana_inicio_propostas", 20):
                for s, q in vag_prox.items():
                    pedidos += [("proxima", s, st["ano"] + 1)] * max(0, q - vag_atual.get(s, 0))
                antecipado = _pedido_antecipado(st, cid, eq, rng)
                if antecipado:
                    pedidos.append(("proxima", "principal", antecipado))
            if not pedidos:
                _talvez_dispensar(st, cid, eq, categoria, rng)
                continue
            teto = teto_salario(st, cid, eq)
            reservados = set()                         # a mesma equipe não manda duas propostas ao mesmo piloto
            for quando, situacao, ano_ini in pedidos:
                teto_vaga = teto if situacao == "principal" else teto * 0.15
                melhor = None
                candidatos = []
                for p in st["pilotos"].values():
                    if p["id"] in reservados or p.get("lesao"):
                        continue
                    if not (not p.get("contrato") if quando == "atual" else livre_em(st, p, ano_ini)):
                        continue                       # agora: inclui quem está livre até um contrato futuro
                    idade = idade_no_inicio(st, p, ano_ini)
                    if acima_da_idade(categoria, idade):
                        continue
                    mob = mobilidade(st, cid, p)
                    if mob < 1 and rng.random() > mob:
                        continue                       # piloto de outra categoria fora do radar nesta semana
                    pedido = salario_pedido(p, categoria)
                    if situacao == "principal" and pedido > teto_vaga * 1.1:
                        continue
                    nota = ratings.nota_geral_piloto(p, categoria) - penalidade_idade(categoria, idade)
                    if situacao == "teste":
                        nota -= abs(p.get("idade", 25) - 21) * 1.5
                    candidatos.append((nota, p, pedido))
                    if melhor is None or nota > melhor[0]:
                        melhor = (nota, p, pedido)
                compra = False
                ordem = sorted(candidatos, key=lambda x: -x[0])
                alvos = ordem[:OFERTAS_POR_VAGA]
                if ano_ini > st["ano"] + 1 and candidatos:
                    # contrato antecipado: entre os 3 melhores disponíveis para aquela temporada
                    alvos = rng.sample(ordem[:3], min(OFERTAS_POR_VAGA, len(ordem[:3])))
                elif quando == "atual" or st["semana"] >= mp.get("semana_inicio_propostas", 20):
                    alvo = _alvo_de_compra(st, cid, eq, categoria, quando, situacao, teto_vaga, reservados,
                                           melhor[0] if melhor else 0, rng)
                    if alvo:
                        alvos, compra = [alvo], True
                # mais de uma proposta por vaga: quem aceitar primeiro fica com ela; as outras são recusadas por
                # falta de vaga (a equipe nunca passa do número de carros)
                piso = mp["salario_minimo_por_corrida"] * (1 if situacao == "principal" else 0.6)
                for _, p, pedido in alvos:
                    reservados.add(p["id"])
                    valor = min(pedido * rng.uniform(0.95, 1.2), max(teto_vaga, piso))
                    ofertas.setdefault(p["id"], []).append({
                        "categoria": cid, "equipe": eq["id"], "situacao": situacao, "quando": quando,
                        "ano_inicio": ano_ini, "valor_por_corrida": round(valor, -2), "pedido": pedido,
                        "duracao": None, "unidade": "temporadas",
                        "perspectiva": perspectiva_equipe(st, cid, eq), "usuario": False, "compra_contrato": compra})
    # propostas do usuário feitas na semana anterior
    for chave, prop in list(st.get("propostas_usuario", {}).items()):
        if prop["semana"] == st["semana"] and prop["ano"] == st["ano"]:
            continue                                   # responde só na semana seguinte
        pid = prop.get("piloto", chave)
        p = st["pilotos"].get(pid)
        del st["propostas_usuario"][chave]
        if not p:
            continue
        c = st["categorias"][prop["categoria"]]
        ofertas.setdefault(pid, []).append(dict(prop, pedido=salario_pedido(p, c["categoria"]), usuario=True,
                                                perspectiva=perspectiva_equipe(st, prop["categoria"],
                                                                               c["equipes"][prop["equipe"]])))
    _pilotos_decidem(st, ofertas, rng)


def _pedido_antecipado(st, cid, eq, rng):
    """Equipe do PC planeja uma vaga de titular que abre daqui a 2+ temporadas (contrato terminando ou piloto se
    aposentando): chance por semana de ~5% para 2 temporadas à frente, 2,5% para 3, 1,7% para 4... × recursos/70.
    No máximo um contrato antecipado por equipe de cada vez. Retorna o ano de início ou None."""
    for p in st["pilotos"].values():
        f = p.get("contrato_futuro")
        if f and f.get("categoria") == cid and f.get("equipe") == eq["id"] \
                and int(f.get("inicio_ano") or 0) >= st["ano"] + 2:
            return None
    anos = set()
    for p in pilotos_da_equipe(st, cid, eq["id"]):
        ct = p["contrato"]
        if ct.get("situacao") != "principal":
            continue
        fim = fim_do_contrato(st, ct)
        if p.get("ano_aposentadoria"):
            fim = min(fim, p["ano_aposentadoria"] - 1)
        if fim + 1 >= st["ano"] + 2:
            anos.add(fim + 1)
    for ano in sorted(anos):
        if vagas_no_ano(st, cid, eq, ano).get("principal", 0) <= 0:
            continue
        chance = 0.05 / (ano - st["ano"] - 1) * eq.get("recursos", 50) / 70
        if rng.random() < chance:
            return ano
    return None


def _talvez_dispensar(st, cid, eq, categoria, rng):
    """PC rescinde (pagando multa) com o pior piloto principal se houver um livre bem melhor."""
    if not 10 <= st["semana"] <= 45 or rng.random() > 0.03:
        return
    principais = [p for p in pilotos_da_equipe(st, cid, eq["id"]) if p["contrato"]["situacao"] == "principal"]
    livres = [p for p in st["pilotos"].values() if livre_agora(p)]
    if not principais or not livres:
        return
    principais = [p for p in principais if not travado(st, p)]
    if not principais:
        return
    pior = min(principais, key=lambda p: ratings.nota_geral_piloto(p, categoria))
    melhor_livre = max(ratings.nota_geral_piloto(p, categoria) for p in livres)
    if melhor_livre >= ratings.nota_geral_piloto(pior, categoria) + 8 and \
            multa(st, pior["contrato"], cid) <= max(0.0, eq["financas"]["caixa"]) * 0.05:
        rescindir_piloto(st, pior["id"])


def _alvo_de_compra(st, cid, eq, categoria, quando, situacao, teto, reservados, nota_livre, rng):
    """PC compra o contrato de um piloto de outra equipe só se ele for bem melhor que o melhor livre
    e a multa couber no caixa."""
    if situacao != "principal" or quando == "atual" or rng.random() > 0.1:
        return None                                  # PC não compra contratos no meio da temporada
    caixa = max(0.0, eq["financas"]["caixa"])
    melhor = None
    for p in st["pilotos"].values():
        ct = p.get("contrato")
        if not ct or p["id"] in reservados or p.get("contrato_futuro") or \
                (ct.get("categoria") == cid and ct.get("equipe") == eq["id"]):
            continue
        if quando == "proxima" and livre_proxima(st, p):
            continue
        if travado(st, p):
            continue
        if p.get("ano_aposentadoria") and p["ano_aposentadoria"] <= st["ano"] + 1:
            continue
        idade = idade_no_inicio(st, p, quando)
        if acima_da_idade(categoria, idade):
            continue
        nota = ratings.nota_geral_piloto(p, categoria) - penalidade_idade(categoria, idade)
        if nota < nota_livre + 8:
            continue
        pedido = salario_pedido(p, categoria)
        m = multa(st, ct, ct["categoria"], so_apos_esta_temporada=(quando != "atual"))
        if pedido > teto * 1.1 or m > caixa * 0.08:
            continue
        mob = mobilidade(st, cid, p)
        if mob < 1 and rng.random() > mob:
            continue
        if melhor is None or nota > melhor[0]:
            melhor = (nota, p, pedido)
    return melhor


def _disponivel(st, p, o):
    """O piloto ainda pode aceitar a oferta? (pode ter assinado com outra equipe)."""
    ano = ano_da_oferta(st, o)
    if p.get("contrato_futuro") and (ano > st["ano"] or p.get("contrato")):
        return False                                   # um só contrato futuro; agora, só se estiver livre até lá
    if o.get("compra_contrato"):
        return bool(p.get("contrato"))
    if ano == st["ano"]:
        return not p.get("contrato")
    return livre_em(st, p, ano)


def ultimo_ano_do_contrato(st, cid, ano, duracao, unidade):
    """Última temporada coberta por um contrato que começa em `ano`."""
    if unidade != "corridas":
        return ano + max(1, int(duracao)) - 1
    n = corridas_na_temporada(st["categorias"][cid])
    primeiro = contratos.corridas_restantes(st, cid) if ano == st["ano"] else n
    return ano if duracao <= primeiro else ano + -(-(duracao - primeiro) // n)


def tem_vaga(st, o):
    """A equipe da oferta ainda tem vaga para a função no ano de início? (outro piloto pode ter aceitado antes)"""
    eq = st["categorias"][o["categoria"]]["equipes"][o["equipe"]]
    ano = ano_da_oferta(st, o)
    livres = vagas(st, o["categoria"], eq)[0] if ano == st["ano"] else vagas_no_ano(st, o["categoria"], eq, ano)
    return livres.get(o["situacao"], 0) > 0


def _valida(st, p, o):
    """A oferta ainda é possível? (piloto disponível e equipe com vaga – nunca mais pilotos que carros)"""
    return _disponivel(st, p, o) and tem_vaga(st, o)


def _pilotos_decidem(st, ofertas, rng):
    for pid in sorted(ofertas, key=lambda _x: rng.random()):          # quem decide primeiro é sorteado
        lista = ofertas[pid]
        p = st["pilotos"][pid]
        avaliadas = []
        sem_vaga = None
        for o in lista:
            if not _disponivel(st, p, o):
                continue
            if not tem_vaga(st, o):
                if o.get("usuario"):
                    sem_vaga = o
                continue
            mp = st["categorias"][o["categoria"]]["categoria"]["simulacao"]["mercado_pilotos"]
            u = (mp.get("peso_salario_na_escolha", 0.55) * clamp(o["valor_por_corrida"] / max(1, o["pedido"]), 0, 1.5) / 1.5
                 + mp.get("peso_perspectiva_na_escolha", 0.45) * o["perspectiva"])
            if o["situacao"] == "teste":
                u *= 0.6
            u *= 0.6 + 0.4 * min(1.0, mobilidade(st, o["categoria"], p))
            u *= 1 - 0.05 * max(0, ano_da_oferta(st, o) - st["ano"] - 1)   # quanto mais longe, menos vale
            avaliadas.append((u + rng.uniform(-0.05, 0.05), o))
        if sem_vaga:
            noticia(st, f"Proposta a {p['nome']} cancelada: {quem(st, sem_vaga['categoria'], sem_vaga['equipe'], True)} "
                        f"já preencheu a vaga.", sem_vaga["categoria"], "usuario")
        prop_usuario = next((o for o in lista if o.get("usuario") and o is not sem_vaga), None)
        if not avaliadas:
            if prop_usuario:
                noticia(st, f"{p['nome']} não está mais disponível: proposta cancelada.", prop_usuario["categoria"],
                        "usuario")
            continue
        u, o = max(avaliadas, key=lambda x: x[0])
        urgente = o["quando"] == "atual" or st["semana"] >= 40
        espera = not urgente and u < 0.55 and rng.random() < 0.5
        if prop_usuario and (espera or o is not prop_usuario):
            motivo = "prefere aguardar outras propostas" if espera else "aceitou outra proposta"
            noticia(st, f"{p['nome']} recusou sua proposta ({motivo}).", prop_usuario["categoria"], "usuario")
        if espera:
            continue
        _assinar(st, p, o, rng)


def _assinar(st, p, o, rng):
    ano_ini = ano_da_oferta(st, o)
    if o.get("duracao"):
        duracao, unidade = o["duracao"], o.get("unidade", "temporadas")
    else:
        duracao, unidade = rng.choice([1, 1, 2] if p.get("idade", 25) >= 33 else [1, 2, 2, 3]), "temporadas"
        if o["quando"] == "atual":
            eq_o = st["categorias"][o["categoria"]]["equipes"][o["equipe"]]
            if vagas(st, o["categoria"], eq_o)[1].get(o["situacao"], 0) <= 0:
                duracao = 1                   # a próxima temporada já está fechada: substituto só até o fim desta
    # cada temporada do contrato precisa de vaga na equipe (outro piloto pode já ter assinado para um ano à frente)
    eq_o = st["categorias"][o["categoria"]]["equipes"][o["equipe"]]
    n_corr = corridas_na_temporada(st["categorias"][o["categoria"]])
    precisa = duracao if unidade != "corridas" else ultimo_ano_do_contrato(st, o["categoria"], ano_ini, duracao,
                                                                            unidade) - ano_ini + 1
    anos_vaga = 1
    while anos_vaga < precisa and vagas_no_ano(st, o["categoria"], eq_o, ano_ini + anos_vaga).get(o["situacao"], 0) > 0:
        anos_vaga += 1
    if anos_vaga < precisa:
        if unidade == "corridas":
            primeiro = contratos.corridas_restantes(st, o["categoria"]) if ano_ini == st["ano"] else n_corr
            duracao = min(duracao, primeiro + (anos_vaga - 1) * n_corr)
        else:
            duracao = anos_vaga
    limite = temporadas_antes_do_futuro(st, p) if ano_ini == st["ano"] else None
    if limite is not None:                    # livre agora, mas já assinado com outra equipe para depois
        if unidade == "corridas":
            duracao = min(duracao, contratos.corridas_restantes(st, o["categoria"])
                          + (limite - 1) * corridas_na_temporada(st["categorias"][o["categoria"]]))
        else:
            duracao = min(duracao, limite)
    contrato = contratos.novo(duracao, unidade, categoria=o["categoria"], equipe=o["equipe"],
                              valor_por_corrida=o["valor_por_corrida"], situacao=o["situacao"],
                              inicio_ano=ano_ini)
    from .saude import de_jogador
    if o["quando"] == "atual" and o["situacao"] == "principal" and not de_jogador(st, o["categoria"], o["equipe"]):
        # equipe do PC com titular lesionado: o contratado é substituto e sai quando ele voltar (na equipe de
        # jogador o contrato vale e o jogador decide depois quem dispensar)
        com_sub = {x["contrato"].get("substituto_de") for x in pilotos_da_equipe(st, o["categoria"], o["equipe"])}
        lesionados = [x for x in pilotos_da_equipe(st, o["categoria"], o["equipe"])
                      if x["contrato"]["situacao"] == "principal" and x.get("lesao") and x["id"] not in com_sub]
        if lesionados:
            contrato["substituto_de"] = lesionados[0]["id"]
    eq = st["categorias"][o["categoria"]]["equipes"][o["equipe"]]
    papel = "piloto principal" if o["situacao"] == "principal" else "piloto de testes"
    origem = categoria_do_piloto(p)
    troca = ""
    if origem and origem != o["categoria"] and origem in st["categorias"]:
        troca = f", vindo da {st['categorias'][origem]['categoria']['nome']}"
    prefixo = quem(st, o["categoria"], o["equipe"]) if o.get("usuario") else eq["nome"]
    antigo = p.get("contrato")
    if o.get("compra_contrato") and antigo:
        # paga a multa à equipe atual do piloto
        valor_multa = multa(st, antigo, antigo["categoria"], a_partir_de=ano_ini)
        eq_antiga = st["categorias"][antigo["categoria"]]["equipes"][antigo["equipe"]]
        lancar(eq, "despesas", "multas", valor_multa)
        lancar(eq_antiga, "receitas", "multas", valor_multa)
        if o["quando"] == "atual":
            p["contrato"] = None
        else:                                 # o contrato atual passa a terminar no ano anterior ao novo
            encurtar_contrato(st, antigo, antigo["categoria"], ano_ini - 1)
        envolve_usuario = o.get("usuario") or eh_usuario(st, antigo["categoria"], antigo["equipe"])
        noticia(st, f"{prefixo} paga {dinheiro(valor_multa)} de multa à {eq_antiga['nome']} pelo contrato de "
                    f"{p['nome']}.", o["categoria"], "usuario" if envolve_usuario else "contratacao",
                equipe=o["equipe"] if o.get("usuario") else antigo["equipe"])
    if o["quando"] == "atual":
        p["contrato"] = contrato
        p["categoria_atual"] = o["categoria"]
        noticia(st, f"{prefixo} contrata {p['nome']} ({p['nacionalidade']}{troca}) como {papel} "
                    f"– {contratos.descricao(contrato).rstrip('.')}.", o["categoria"], "usuario" if o.get("usuario") else "contratacao",
                equipe=o["equipe"])
    else:
        p["contrato_futuro"] = contrato
        noticia(st, f"{prefixo} acerta com {p['nome']} ({p['nacionalidade']}{troca}) como {papel} para "
                    f"{ano_ini} – {contratos.descricao(contrato).rstrip('.')}.", o["categoria"],
                "usuario" if o.get("usuario") else "contratacao", equipe=o["equipe"])


def _avisar_usuario(st, cid, eq, vag_atual, vag_prox, mp):
    falta_atual, falta_prox = sum(vag_atual.values()), sum(vag_prox.values())
    chave = f"{st['ano']}|{cid}|{eq['id']}" if st.get("multiplayer") else str(st["ano"])
    ultimo = st.setdefault("avisos_enviados", {}).get(chave, -99)
    if (falta_atual or (falta_prox and st["semana"] >= mp.get("semana_inicio_propostas", 20))) \
            and st["semana"] - ultimo >= 8:
        partes = []
        if falta_atual:
            partes.append(f"{falta_atual} vaga(s) para esta temporada")
        if falta_prox:
            partes.append(f"{falta_prox} vaga(s) para {st['ano'] + 1}")
        noticia(st, f"ATENÇÃO: {quem(st, cid, eq['id'], True)} tem {' e '.join(partes)} sem piloto contratado "
                    f"(Mercado > Pilotos).", cid, "usuario", equipe=eq["id"])
        st["avisos_enviados"][chave] = st["semana"]


def fim_de_corrida_pilotos(st, cid, evento_id=None):
    """Contratos por corridas: desconta uma corrida; ao zerar, o piloto fica livre.
    Com 'corridas_definidas', só desconta nas corridas da lista e termina depois da última delas."""
    cal = st["categorias"][cid]["calendario"]
    feitas = {r["evento"] for r in contratos.resultados_da_temporada(st, cid)} | {evento_id}
    for p in st["pilotos"].values():
        ct = p.get("contrato")
        if ct and ct.get("categoria") == cid and contratos.por_corridas(ct):
            lista = ct.get("corridas_definidas")
            if lista:
                if evento_id in lista:
                    ct["corridas"] -= 1
                pendentes = [e for e in cal if e["id"] in lista and e["id"] not in feitas and e.get("ativo")
                             and e["especie"] == "corrida" and e["semana"] >= st["semana"]]
                if not pendentes:
                    ct["corridas"] = 0
            else:
                ct["corridas"] -= 1
            if ct["corridas"] <= 0:
                eq = st["categorias"][cid]["equipes"].get(ct["equipe"], {})
                p["contrato"] = None
                p["categoria_atual"] = cid
                noticia(st, f"Termina o contrato de {p['nome']} com a {eq.get('nome', '?')}.", cid,
                        "usuario" if eh_usuario(st, cid, ct["equipe"]) else "contrato", equipe=ct["equipe"])


# ====================================================================== chassis e motores
def opcoes(st, cid, eq, parte):
    """Lista de (entidade, disponivel: bool, motivo) para contrato de chassis/motor."""
    c = st["categorias"][cid]
    regras = c["categoria"]["regras"]
    if parte == "chassis":
        from .state import fontes_chassis
        fontes = fontes_chassis(c["categoria"])
        out = []
        for ch in c["chassis"].values():
            dono = ch.get("equipe")
            if not dono:
                if "fabricante" in fontes and ch.get("contrato"):
                    out.append((ch, True, ""))
                continue
            if "equipe" not in fontes or dono == eq["id"]:
                continue
            de = c["equipes"].get(dono) or {}
            if not de.get("ativa") or (de.get("chassis") or {}).get("id") != ch["id"] \
                    or (de.get("chassis") or {}).get("origem") != "proprio" or de.get("chassis_futuro"):
                continue                          # só o chassis que a equipe dona usa e continua fazendo
            preco_chassis_de_equipe(st, cid, ch)
            limite = regras.get("clientes_por_chassis", 2)
            ja = clientes_do_chassis(st, cid, ch["id"]) - {eq["id"]}
            if limite and len(ja) >= int(limite):              # 0 = sem limite
                out.append((ch, False, f"a {de['nome']} já tem {len(ja)} cliente(s)"))
                continue
            exc = ch.get("exclusividade") or {}
            if exc.get("exclusivo") and exc.get("equipe") not in (eq["id"], eq["nome"]):
                out.append((ch, False, f"exclusivo da {exc.get('equipe')}"))
                continue
            out.append((ch, True, ""))
        return out
    if (eq.get("motor") or {}).get("origem") == "proprio":
        return []
    fontes = regras.get("fontes_de_motor_permitidas", ["equipe", "fabricante"])
    out = []
    for m in c["motores"].values():
        fab = m.get("fabricante") or {}
        if not m.get("contrato"):
            continue
        if fab.get("tipo") == "equipe":
            dono = c["equipes"].get(fab.get("equipe"))
            if "equipe" not in fontes or not dono or dono["id"] == eq["id"]:
                continue
            if not dono.get("ativa"):
                out.append((m, False, "equipe fabricante inativa"))
                continue
        elif "fabricante" not in fontes:
            continue
        exc = m.get("exclusividade") or {}
        if exc.get("exclusivo") and exc.get("equipe") not in (eq["id"], eq["nome"]):
            out.append((m, False, f"exclusivo da {exc.get('equipe')}"))
            continue
        out.append((m, True, ""))
    return out


def clientes_do_chassis(st, cid, chid):
    """Equipes (fora a dona) que usam este chassis agora ou têm contrato com ele para a próxima temporada."""
    c = st["categorias"][cid]
    dono = c["chassis"].get(chid, {}).get("equipe")
    return {e["id"] for e in c["equipes"].values() if e.get("ativa") and e["id"] != dono
            and chid in ((e.get("chassis") or {}).get("id"), (e.get("chassis_futuro") or {}).get("id"))}


def preco_chassis_de_equipe(st, cid, ch):
    """Chassis de equipe vendido a clientes: sem preço na database, vale 15% do orçamento médio por temporada
    (nível 75), proporcional ao nível; recalculado a cada temporada."""
    ct = ch.get("contrato")
    if ct and (not ct.get("automatico") or ct.get("ano") == st["ano"]):
        return ct["valor_por_corrida"]
    c = st["categorias"][cid]
    v = list((ch.get("atributos") or {}).values())
    nivel = sum(v) / len(v) if v else 50
    valor = round(0.15 * c["categoria"]["regras"]["orcamento_medio"] / corridas_na_temporada(c) * nivel / 75, -2)
    ch["contrato"] = {"valor_por_corrida": valor, "temporadas": 1, "automatico": True, "ano": st["ano"]}
    return valor


def atualizar_precos_chassis(st):
    """Preço dos chassis de equipe à venda (categorias com 'equipe' nas fontes). Feito em pontos fixos (início do
    jogo, toda semana, virada) para o jogo do jogador e o do comissário terem sempre os mesmos valores."""
    from .state import fontes_chassis
    for cid, c in st["categorias"].items():
        if "equipe" in fontes_chassis(c["categoria"]):
            for ch in c["chassis"].values():
                if ch.get("equipe"):
                    preco_chassis_de_equipe(st, cid, ch)


def nota_parte(ent, parte, categoria):
    return ratings.nota_geral_chassis(ent, categoria) if parte == "chassis" else ent.get("potencia", 0)


def tem_parte_ativa(eq, parte):
    info = eq.get(parte) or {}
    return bool(info.get("id"))


def negociacao(categoria):
    """regras.negociacao_partes: preço de chassis/motor negociado (pedido escondido). None = preço de tabela."""
    n = categoria["regras"].get("negociacao_partes")
    if isinstance(n, bool):
        n = {"ativa": n}
    n = dict({"ativa": False, "variacao": 0.15}, **(n or {}))
    return n if n["ativa"] else None


def preco_pedido_parte(st, cid, eid, parte, ent, ano=None):
    """O que o fornecedor realmente pede à equipe: preço de tabela ± variacao, fixo por fornecedor, equipe e
    temporada. Só existe com a negociação ligada (senão é o próprio preço de tabela)."""
    tabela = ent["contrato"]["valor_por_corrida"]
    neg = negociacao(st["categorias"][cid]["categoria"])
    if not neg:
        return tabela
    v = float(neg["variacao"])
    rng = random.Random(f"{st.get('semente', 0)}|{ano or st.get('ano')}|{eid}|{parte}|{ent['id']}")
    return round(tabela * rng.uniform(1 - v, 1 + v), -2)


def _validar_parte(st, cid, eq, parte, ent_id, inicio, rescindir):
    disp = {e["id"]: (ok, motivo) for e, ok, motivo in opcoes(st, cid, eq, parte)}
    if ent_id not in disp:
        return "Opção não disponível nesta categoria."
    if not disp[ent_id][0]:
        return f"Fornecimento recusado: {disp[ent_id][1]}."
    try:
        ano = ano_de_inicio(st, inicio)
    except (TypeError, ValueError):
        return "Ano de início inválido."
    if ano < st["ano"]:
        return "O contrato não pode começar numa temporada que já passou."
    if ano == st["ano"]:
        if tem_parte_ativa(eq, parte):
            if (eq.get(parte) or {}).get("origem") == "proprio":
                return f"A equipe tem {parte} próprio."
            if not rescindir:
                return f"A equipe já tem {parte} com contrato ativo: é preciso rescindir pagando a multa " \
                       f"({dinheiro(multa_parte(st, cid, eq, parte))})."
    else:
        fut = eq.get(f"{parte}_futuro")
        if fut:                                        # um só contrato futuro por peça
            return f"A equipe já tem contrato de {parte} para {_ano_futuro_parte(st, fut)}."
        atual = (eq.get(parte) or {}).get("contrato")
        if atual and (eq.get(parte) or {}).get("origem") != "proprio" and fim_do_contrato(st, atual, cid) >= ano:
            if not rescindir:
                return f"O contrato atual de {parte} vai até {fim_do_contrato(st, atual, cid)}: para começar em " \
                       f"{ano} é preciso pagar a multa ({dinheiro(multa_parte(st, cid, eq, parte, ano))})."
        if parte == "chassis" and (eq.get("chassis") or {}).get("origem") == "proprio" \
                and clientes_do_chassis(st, cid, eq["chassis"]["id"]):
            return "A equipe vende o próprio chassis a clientes: não pode trocá-lo por um comprado."
    return None


def _ano_futuro_parte(st, fut):
    return int((fut.get("contrato") or {}).get("inicio_ano") or st["ano"] + 1)


def contratar_parte(st, cid, eq, parte, ent_id, duracao, unidade, inicio, rescindir=False, valor=None):
    """Fecha contrato de chassis/motor. 'agora' com a peça já contratada exige rescindir (pagando a multa).
    `valor`: preço negociado por corrida (sem ele, o preço de tabela)."""
    erro = _validar_parte(st, cid, eq, parte, ent_id, inicio, rescindir)
    if erro:
        return erro
    tabela = st["categorias"][cid]["chassis" if parte == "chassis" else "motores"]
    ent = tabela[ent_id]
    origem = ("equipe" if ent.get("equipe") else "terceiros") if parte == "chassis" else ent["fabricante"]["tipo"]
    ano = ano_de_inicio(st, inicio)
    ct = contratos.novo(duracao, unidade, valor_por_corrida=valor if valor else ent["contrato"]["valor_por_corrida"])
    novo = {"id": ent_id, "origem": origem, "contrato": ct}
    if ano == st["ano"]:
        if tem_parte_ativa(eq, parte):
            rescindir_parte(st, cid, eq, parte)
        eq[parte] = novo
    else:
        ct["inicio_ano"] = ano
        atual = (eq.get(parte) or {}).get("contrato")
        if atual and (eq.get(parte) or {}).get("origem") != "proprio" and fim_do_contrato(st, atual, cid) >= ano:
            # o contrato atual se sobrepõe: paga a multa só pelas temporadas que se sobrepõem e encurta até ano − 1
            valor_multa = multa_parte(st, cid, eq, parte, ano)
            lancar(eq, "despesas", "multas", valor_multa)
            info = eq[parte]
            tab_atual = st["categorias"][cid]["chassis" if parte == "chassis" else "motores"].get(info["id"], {})
            fab = tab_atual.get("fabricante") or {}
            dono = fab.get("equipe") if fab.get("tipo") == "equipe" else tab_atual.get("equipe")
            if dono in st["categorias"][cid]["equipes"]:
                lancar(st["categorias"][cid]["equipes"][dono], "receitas", "multas", valor_multa)
            encurtar_contrato(st, atual, cid, ano - 1)
            noticia(st, f"{quem(st, cid, eq['id'])} paga {dinheiro(valor_multa)} de multa para encerrar o contrato de "
                        f"{parte} ({tab_atual.get('nome', info['id'])}) ao fim de {ano - 1}.", cid,
                    "usuario" if eh_usuario(st, cid, eq["id"]) else "contrato", equipe=eq["id"])
        eq[f"{parte}_futuro"] = novo
        if ano == st["ano"] + 1 and (eq.get(parte) or {}).get("origem") == "proprio" \
                and (eq.get("projeto") or {}).get(parte):
            eq["projeto"][parte] = {"modo": "manutencao", "investido": {}}   # comprou: o projeto próprio acaba
    quando = "imediato" if ano == st["ano"] else f"a partir de {ano}"
    nome = quem(st, cid, eq["id"]) if eh_usuario(st, cid, eq["id"]) else eq["nome"]
    noticia(st, f"{nome} fecha contrato de {parte} com {ent['nome']} ({contratos.descricao(ct)}, "
                f"{dinheiro(ct['valor_por_corrida'])} por corrida, {quando}).", cid,
            "usuario" if eh_usuario(st, cid, eq["id"]) else "contrato", equipe=eq["id"])
    return None


def fazer_proposta_parte(st, cid, eq, parte, ent_id, valor, duracao, unidade, inicio, rescindir=False, ia=False):
    """Negociação ligada: registra a oferta da equipe; o fornecedor responde na semana seguinte (aceita se a
    oferta cobre o preço que ele pede, que fica escondido). Retorna None ou a mensagem de erro."""
    c = st["categorias"][cid]
    if not negociacao(c["categoria"]):
        return "Nesta categoria o preço de chassis e motor é o de tabela (sem negociação)."
    erro = _validar_parte(st, cid, eq, parte, ent_id, inicio, True)
    if erro:
        return erro
    if valor <= 0 or duracao < 1:
        return "Informe valor e duração válidos."
    ent = c["chassis" if parte == "chassis" else "motores"][ent_id]
    st.setdefault("propostas_partes", {})[f"{cid}|{eq['id']}|{parte}"] = {
        "categoria": cid, "equipe": eq["id"], "parte": parte, "id": ent_id, "valor_por_corrida": round(float(valor), -2),
        "duracao": int(duracao), "unidade": unidade, "inicio": inicio, "rescindir": bool(rescindir),
        "semana": st["semana"], "ano": st["ano"], "ia": ia}
    if not ia:
        noticia(st, f"{quem(st, cid, eq['id'])} fez proposta pelo {parte} {ent['nome']} ({dinheiro(valor)} por corrida, "
                    f"{duracao} {unidade}). Resposta na próxima semana.", cid, "usuario", equipe=eq["id"])
    return None


def proposta_parte_pendente(st, cid, eid, parte):
    return (st.get("propostas_partes") or {}).get(f"{cid}|{eid}|{parte}")


def _responder_propostas_partes(st):
    """Fornecedores respondem às ofertas feitas em semanas anteriores."""
    for chave, pr in list((st.get("propostas_partes") or {}).items()):
        if pr["semana"] == st["semana"] and pr["ano"] == st["ano"]:
            continue
        del st["propostas_partes"][chave]
        c = st["categorias"].get(pr["categoria"])
        eq = (c or {}).get("equipes", {}).get(pr["equipe"])
        tabela = (c or {}).get("chassis" if pr["parte"] == "chassis" else "motores", {})
        ent = tabela.get(pr["id"])
        if not eq or not ent or not ent.get("contrato") or not eq.get("ativa"):
            continue
        cid, parte = pr["categoria"], pr["parte"]
        humano = not pr.get("ia")              # oferta de pessoa: a resposta vai para ela mesmo numa semana da IA
        ano_ini = ano_de_inicio(st, pr["inicio"])
        pedido = preco_pedido_parte(st, cid, eq["id"], parte, ent, ano_ini if ano_ini > st["ano"] + 1 else None)
        if pr["valor_por_corrida"] + 1e-6 < pedido:
            if humano:
                noticia(st, f"{ent['nome']} recusa a proposta da {eq['nome']} ({dinheiro(pr['valor_por_corrida'])} por "
                            f"corrida): o fornecedor quer mais.", cid, "usuario", equipe=eq["id"])
            continue
        erro = contratar_parte(st, cid, eq, parte, pr["id"], pr["duracao"], pr["unidade"], pr["inicio"],
                               rescindir=pr.get("rescindir"), valor=pr["valor_por_corrida"])
        if erro and humano:
            noticia(st, f"{ent['nome']} aceitaria a proposta da {eq['nome']}, mas o contrato não pôde ser fechado: "
                        f"{erro}", cid, "usuario", equipe=eq["id"])


def _contratar_ia(st, cid, eq, parte, ent, duracao, inicio, rng):
    """Equipe do PC: preço de tabela, ou (negociação ligada) oferta respondida na semana seguinte. Sem a peça
    para correr agora, paga o que o fornecedor pede na hora."""
    if not negociacao(st["categorias"][cid]["categoria"]):
        return contratar_parte(st, cid, eq, parte, ent["id"], duracao, "temporadas", inicio)
    if inicio == "agora" and not tem_parte_ativa(eq, parte):
        return contratar_parte(st, cid, eq, parte, ent["id"], duracao, "temporadas", inicio,
                               valor=preco_pedido_parte(st, cid, eq["id"], parte, ent))
    if proposta_parte_pendente(st, cid, eq["id"], parte):
        return None
    tent = eq.setdefault("tentativas_parte", {})
    tent[parte] = tent.get(parte, 0) + 1                  # recusada, a oferta seguinte sobe
    oferta = ent["contrato"]["valor_por_corrida"] * rng.uniform(0.9, 1.12) * (1 + 0.04 * (tent[parte] - 1))
    return fazer_proposta_parte(st, cid, eq, parte, ent["id"], oferta, duracao, "temporadas", inicio, ia=True)


def _escolha_ia(st, cid, eq, parte):
    c = st["categorias"][cid]
    n = corridas_na_temporada(c)
    disp = [e for e, ok, _ in opcoes(st, cid, eq, parte) if ok]
    if not disp:
        return None
    caixa = max(0.0, eq["financas"]["caixa"])
    precos = {e["id"]: e["contrato"]["valor_por_corrida"] * n for e in disp}
    pmax = max(precos.values()) or 1
    cabem = [e for e in disp if precos[e["id"]] <= caixa * 0.3] or [min(disp, key=lambda e: precos[e["id"]])]
    return max(cabem, key=lambda e: nota_parte(e, parte, c["categoria"]) * (1 - 0.4 * precos[e["id"]] / pmax))


def _decidir_chassis_ia(st, cid, eq, rng):
    """Categoria com desenvolvimento de chassis que também deixa comprar: a equipe do PC compara o carro próprio
    esperado para a próxima temporada (manutenção ou projeto novo, com a verba anual) com o melhor chassis à venda
    que cabe no caixa, e compra se ele for pelo menos 3 pontos melhor. Um cliente com o contrato terminando faz o
    mesmo: renova a compra ou passa a fazer o próprio chassis. Retorna True se tratou a equipe."""
    from . import desenvolvimento as dev
    from .state import compra_de_chassis
    c = st["categorias"][cid]
    proprio = dev.pode(st, cid, eq, "chassis")
    if not compra_de_chassis(c["categoria"]) or not (proprio or dev.cliente(st, cid, eq, "chassis")):
        return False
    if not tem_parte_ativa(eq, "chassis"):
        return False                                      # sem chassis para correr: compra agora (caminho normal)
    if eq.get("chassis_futuro") or proposta_parte_pendente(st, cid, eq["id"], "chassis"):
        return True
    if not proprio and (not dev.cliente_pode_voltar(st, cid, eq, "chassis") or
                        dev.projeto(eq, "chassis")["modo"] == "novo"):
        return True                                       # contrato continua, ou já está fazendo o próprio
    def esperado(e):
        """Nível do carro próprio da equipe na próxima temporada, com a verba anual dela."""
        peso = 0.7 if dev.pode(st, cid, e, "motor") else 1.0
        return dev.nivel_estimado_proxima(st, cid, e, "chassis", e.get("verba_semanal_dev", 0.0) * 52 * peso)

    if proprio and clientes_do_chassis(st, cid, eq["chassis"]["id"]):
        return True                                       # tem clientes: continua fazendo o próprio
    ent = _escolha_ia(st, cid, eq, "chassis")
    nivel_compra = -1.0
    if ent:
        dono = c["equipes"].get(ent.get("equipe"))
        nivel_compra = esperado(dono) if dono else dev._nivel(ent, "chassis")
    if ent and nivel_compra >= esperado(eq) + 3:
        _contratar_ia(st, cid, eq, "chassis", ent, rng.choice([1, 2]), "proxima", rng)
    elif not proprio:
        dev.mudar_modo(eq, "chassis", "novo")
        noticia(st, f"{eq['nome']} decide voltar a fazer o próprio chassis em {st['ano'] + 1}.", cid, "desenvolvimento")
    return True


def rotina_partes(st, rng=random):
    """Equipes do PC escolhem chassis/motor pelo melhor custo-benefício que cabe no caixa."""
    atualizar_precos_chassis(st)
    _responder_propostas_partes(st)
    for cid, c in st["categorias"].items():
        inicio = c["categoria"]["simulacao"]["mercado_pilotos"].get("semana_inicio_propostas", 20)
        restantes = contratos.corridas_restantes(st, cid)
        for eq in c["equipes"].values():
            if not eq.get("ativa") or eh_usuario(st, cid, eq["id"]):
                continue
            for parte in ("chassis", "motor"):
                if parte == "chassis" and not tem_parte_ativa(eq, parte) and \
                        not any(ok for _, ok, _m in opcoes(st, cid, eq, parte)):
                    from . import desenvolvimento as dev
                    if dev.cliente(st, cid, eq, parte):            # nada à venda: volta a fazer o próprio
                        dev.construir_do_zero(st, cid, eq, parte, max(0.0, eq["financas"]["caixa"]) * 0.35)
                        noticia(st, f"{eq['nome']} não encontra chassis à venda e constrói o próprio.", cid,
                                "desenvolvimento")
                    continue
                if not opcoes(st, cid, eq, parte):
                    continue
                if parte == "chassis" and st["semana"] >= inicio and _decidir_chassis_ia(st, cid, eq, rng):
                    continue
                if not tem_parte_ativa(eq, parte):
                    ent = _escolha_ia(st, cid, eq, parte)
                    if ent:
                        _contratar_ia(st, cid, eq, parte, ent, rng.choice([1, 2]), "agora", rng)
                    continue
                ct = eq[parte].get("contrato")
                if st["semana"] >= inicio and ct and not eq.get(f"{parte}_futuro") \
                        and contratos.termina_nesta_temporada(ct, restantes):
                    ent = _escolha_ia(st, cid, eq, parte)
                    if ent:
                        _contratar_ia(st, cid, eq, parte, ent, rng.choice([1, 2]), "proxima", rng)


def fim_de_corrida_partes(st, cid):
    c = st["categorias"][cid]
    for eq in c["equipes"].values():
        for parte in ("chassis", "motor"):
            info = eq.get(parte) or {}
            ct = info.get("contrato")
            if info.get("origem") in (None, "proprio") or not contratos.por_corridas(ct):
                continue
            ct["corridas"] -= 1
            if ct["corridas"] <= 0:
                eq[parte] = None
                noticia(st, f"Termina o contrato de {parte} da {eq['nome']}.", cid,
                        "usuario" if eh_usuario(st, cid, eq["id"]) else "contrato", equipe=eq["id"])


def virada_partes(st, cid):
    """Nova temporada: contratos por temporada descontam 1; vencidos dão lugar ao contrato futuro."""
    c = st["categorias"][cid]
    for eq in c["equipes"].values():
        eq.pop("tentativas_parte", None)
        for parte in ("chassis", "motor"):
            info = eq.get(parte) or {}
            ct = info.get("contrato")
            if ct and info.get("origem") not in (None, "proprio") and not contratos.por_corridas(ct):
                ct["temporadas"] = ct.get("temporadas", 1) - 1
                if ct["temporadas"] <= 0:
                    eq[parte] = None
            fut = eq.get(f"{parte}_futuro")
            if fut and _ano_futuro_parte(st, fut) <= st["ano"] and \
                    (not tem_parte_ativa(eq, parte) or info.get("origem") == "proprio"):
                eq[parte] = eq.pop(f"{parte}_futuro")     # inclui quem trocou o chassis próprio por um comprado
            if eq.get("ativa") and not tem_parte_ativa(eq, parte) and eh_usuario(st, cid, eq["id"]) \
                    and opcoes(st, cid, eq, parte):
                noticia(st, f"ATENÇÃO: {quem(st, cid, eq['id'], True)} está sem {parte} para {st['ano']} (Mercado > "
                            f"{'Chassis' if parte == 'chassis' else 'Motor'}).", cid, "usuario", equipe=eq["id"])


# ====================================================================== patrocinadores
def indice_equipe(st, cid, eq, rng):
    """Índice carro x pilotos (com aleatoriedade); depois da 1ª corrida inclui o desempenho."""
    c = st["categorias"][cid]
    cat = c["categoria"]
    carro = ratings.nota_geral_carro(chassis_da_equipe(st, cid, eq), motor_da_equipe(st, cid, eq), cat)
    pil = [p for p in pilotos_da_equipe(st, cid, eq["id"]) if p["contrato"]["situacao"] == "principal"]
    nota_p = sum(ratings.nota_geral_piloto(p, cat) for p in pil) / len(pil) if pil else 0
    idx = 0.5 * carro + 0.5 * nota_p
    if contratos.resultados_da_temporada(st, cid):
        pos = campeonato.posicao_equipe(st, cid, eq["id"])
        n = sum(1 for e in c["equipes"].values() if e.get("ativa"))
        if pos:
            desemp = 100 * (1 - (pos - 1) / max(1, n - 1))
            w = (cat.get("mercado_patrocinio") or {}).get("peso_desempenho", 0.4)
            idx = (1 - w) * idx + w * desemp
    return idx * rng.uniform(0.85, 1.15)


def _bonus_preferencia(st, cid, eq, pat):
    pref = pat.get("preferencia") or {}
    tipo, valor = pref.get("tipo"), pref.get("valor")
    if tipo == "nacionalidade_equipe":
        return 1.15 if eq.get("nacionalidade") == valor else 1.0
    if tipo == "nacionalidade_piloto":
        return 1.15 if any(p["nacionalidade"] == valor for p in pilotos_da_equipe(st, cid, eq["id"])) else 1.0
    if tipo == "posicao_campeonato" and contratos.resultados_da_temporada(st, cid):
        pos = campeonato.posicao_equipe(st, cid, eq["id"])
        return 1.15 if pos and pos <= valor else 0.85
    return 1.0


def rotina_patrocinadores(st, rng=random):
    ofertas = st.setdefault("ofertas_patrocinio", [])
    # ofertas vencidas
    for o in list(ofertas):
        c = st["categorias"][o["categoria"]]
        validade = (c["categoria"].get("mercado_patrocinio") or {}).get("validade_oferta_semanas", 4)
        if (st["ano"], st["semana"]) > (o["ano"], o["semana"] + validade) or o["ano"] != st["ano"]:
            ofertas.remove(o)
            c["patrocinadores"][o["patrocinador"]].pop("oferta_pendente", None)
    for cid, c in st["categorias"].items():
        cat = c["categoria"]
        if not cat["regras"].get("patrocinios"):
            continue
        cfg = cat.get("mercado_patrocinio") or {}
        n = corridas_na_temporada(c)
        equipes = [e for e in c["equipes"].values() if e.get("ativa")]
        if not equipes:
            continue
        _garantir_patrocinadores(st, cid, equipes, rng)
        com = {p["contrato"]["equipe"] for p in c["patrocinadores"].values() if p.get("contrato")}
        prob = cfg.get("prob_busca_semanal", 0.1) * (3 if any(e["id"] not in com for e in equipes) else 1)
        for pat in list(c["patrocinadores"].values()):
            if not pat.get("ativo") or pat.get("contrato") or pat.get("oferta_pendente"):
                continue
            if rng.random() > prob:
                continue
            # sorteio ponderado: equipes melhores são mais prováveis, mas não garantidas;
            # cada patrocinador que a equipe já tem reduz um pouco sua atratividade
            qtd = {e["id"]: 0 for e in equipes}
            for outro in c["patrocinadores"].values():
                if outro.get("contrato") and outro["contrato"].get("equipe") in qtd:
                    qtd[outro["contrato"]["equipe"]] += 1
            # toda equipe precisa de patrocínio: enquanto houver equipe sem nenhum, só elas entram no sorteio
            pendentes = {o["equipe"] for o in st.get("ofertas_patrocinio", []) if o.get("equipe")}
            sem = [e for e in equipes if qtd[e["id"]] == 0 and e["id"] not in pendentes]
            candidatas = sem or equipes
            notas = [(indice_equipe(st, cid, eq, rng) * _bonus_preferencia(st, cid, eq, pat), eq) for eq in candidatas]
            pesos = [max(1.0, i) ** 3 * 0.75 ** qtd[eq["id"]] for i, eq in notas]
            idx, eq = rng.choices(notas, weights=pesos)[0]
            base = pat.get("valor_base") or cat["regras"]["orcamento_medio"] * 0.05
            anual = round(base * (0.5 + clamp(idx, 0, 120) / 100), -3)
            if rng.random() < 0.6:
                proposta = {"valor": anual, "pagamento": "por_temporada", "duracao": rng.choice([1, 2, 3]),
                            "unidade": "temporadas"}
            else:
                proposta = {"valor": round(anual / n, -2), "pagamento": "por_corrida",
                            "duracao": rng.choice([max(1, n // 2), n, n + n // 2]), "unidade": "corridas"}
            if eh_usuario(st, cid, eq["id"]):
                pat["oferta_pendente"] = True
                ofertas.append(dict(proposta, patrocinador=pat["id"], categoria=cid, semana=st["semana"],
                                    ano=st["ano"], equipe=eq["id"]))
                destino = "à sua equipe" if not st.get("multiplayer") else f"à {eq['nome']}"
                noticia(st, f"A {pat['nome']} ({pat['ramo']}) oferece patrocínio {destino}: "
                            f"{dinheiro(proposta['valor'])} {proposta['pagamento'].replace('_', ' ')}, "
                            f"{proposta['duracao']} {proposta['unidade']} (Mercado > Patrocinadores).", cid, "usuario",
                        equipe=eq["id"])
            else:
                pat["contrato"] = dict(proposta, equipe=eq["id"])
                noticia(st, f"{eq['nome']} fecha patrocínio com a {pat['nome']} ({pat['ramo']}).", cid, "patrocinio")


def _garantir_patrocinadores(st, cid, equipes, rng):
    """Se há menos patrocinadores livres do que equipes sem patrocínio, cria empresas fictícias."""
    c = st["categorias"][cid]
    com = {p["contrato"]["equipe"] for p in c["patrocinadores"].values() if p.get("contrato")}
    com |= {o["equipe"] for o in st.get("ofertas_patrocinio", []) if o.get("equipe")}
    sem = [e for e in equipes if e["id"] not in com]
    livres = [p for p in c["patrocinadores"].values() if p.get("ativo") and not p.get("contrato")]
    faltam = len(sem) - len(livres)
    if faltam <= 0:
        return
    import json
    import os
    from .util import PASTA_DATABASE
    try:
        with open(os.path.join(PASTA_DATABASE, "nomes.json"), encoding="utf-8") as f:
            emp = json.load(f).get("empresas") or {}
    except (OSError, ValueError):
        emp = {}
    prefixos = emp.get("prefixos") or ["Nova"]
    sufixos = emp.get("sufixos") or ["Group"]
    paises = [e.get("nacionalidade") for e in equipes if e.get("nacionalidade")] or ["-"]
    orc = c["categoria"]["regras"]["orcamento_medio"]
    nomes = {p["nome"] for p in c["patrocinadores"].values()}
    for _ in range(faltam):
        for _t in range(20):
            suf = rng.choice(sufixos)
            nome = f"{rng.choice(prefixos)} {suf}"
            if nome not in nomes:
                break
        nomes.add(nome)
        n = st["seq_patrocinadores"] = st.get("seq_patrocinadores", 0) + 1
        pid = f"pat_ficticio_{n:04d}"
        c["patrocinadores"][pid] = {
            "id": pid, "nome": nome, "ativo": True, "pais": rng.choice(paises),
            "ramo": (emp.get("ramos") or {}).get(suf, "Diversos"),
            "valor_base": round(orc * rng.uniform(0.07, 0.18), -3),
            "preferencia": {"tipo": "posicao_campeonato", "valor": rng.choice([3, 5, 8, 12])},
            "contrato": None, "prob_fechamento": 0.03, "prob_surgimento": 0.0, "ficticio": True}
        noticia(st, f"A empresa {nome} entra no esporte e busca uma equipe para patrocinar.", cid, "patrocinio")


def responder_patrocinio(st, oferta, aceitar):
    c = st["categorias"][oferta["categoria"]]
    pat = c["patrocinadores"][oferta["patrocinador"]]
    st["ofertas_patrocinio"].remove(oferta)
    pat.pop("oferta_pendente", None)
    if aceitar:
        eid = oferta.get("equipe") or st["usuario"]["equipe"]
        pat["contrato"] = {"equipe": eid, "valor": oferta["valor"],
                           "pagamento": oferta["pagamento"], "duracao": oferta["duracao"], "unidade": oferta["unidade"]}
        noticia(st, f"{quem(st, oferta['categoria'], eid)} fecha patrocínio com a {pat['nome']}.", oferta["categoria"],
                "usuario", equipe=eid)


def aplicar_idade_maxima(st):
    """Virada de temporada (idades já atualizadas): contratos com pilotos acima da idade máxima da categoria
    terminam, sem multa."""
    for p in st["pilotos"].values():
        for chave in ("contrato", "contrato_futuro"):
            ct = p.get(chave)
            if not ct or ct.get("categoria") not in st["categorias"]:
                continue
            cat = st["categorias"][ct["categoria"]]["categoria"]
            if not acima_da_idade(cat, p.get("idade", 25)):
                continue
            eq = st["categorias"][ct["categoria"]]["equipes"].get(ct.get("equipe"), {})
            p[chave] = None
            p["categoria_atual"] = ct["categoria"]
            noticia(st, f"{p['nome']} passa da idade máxima da {cat['nome']} ({regras_idade(cat)[0]} anos) e deixa "
                        f"a {eq.get('nome', '?')}.", ct["categoria"],
                    "usuario" if eh_usuario(st, ct["categoria"], ct.get("equipe")) else "contrato",
                    equipe=ct.get("equipe"))


# ====================================================================== mínimo de pilotos por corrida
def minimo_pilotos(st, cid):
    """Pilotos principais mínimos por equipe em cada corrida (0 = sem mínimo)."""
    v = st["categorias"][cid]["categoria"]["regras"].get("pilotos_minimos_por_equipe")
    return int(v) if v else 0


def aptos_para_corrida(st, cid, eid, evento_id):
    """Titulares que podem correr o evento: com contrato, sem lesão e escalados (revezamento)."""
    return sum(1 for p in pilotos_da_equipe(st, cid, eid)
               if p["contrato"]["situacao"] == "principal" and not p.get("lesao")
               and contratos.escalado(p["contrato"], evento_id))


def corridas_da_semana(st, cid):
    return [ev for ev in st["categorias"][cid]["calendario"]
            if ev.get("ativo") and ev["especie"] == "corrida" and ev["semana"] == st["semana"]
            and not campeonato.ja_disputado(st, cid, ev["id"])]


def faltam_pilotos(st, cid, eid, ev=None):
    """Quantos titulares faltam para o mínimo na corrida `ev` (ou na corrida desta semana). (falta, evento)"""
    minimo = minimo_pilotos(st, cid)
    if not minimo:
        return 0, None
    pior = (0, None)
    for e in ([ev] if ev else corridas_da_semana(st, cid)):
        falta = minimo - aptos_para_corrida(st, cid, eid, e["id"])
        if falta > pior[0]:
            pior = (falta, e)
    return pior


def equipes_curtas(st, humanas_apenas=False):
    """[(cid, eid, falta, evento)] das equipes ativas abaixo do mínimo para a corrida desta semana."""
    out = []
    for cid, c in st["categorias"].items():
        if not minimo_pilotos(st, cid):
            continue
        for eid, eq in c["equipes"].items():
            if not eq.get("ativa") or (humanas_apenas and not eh_humana(st, cid, eid)):
                continue
            falta, ev = faltam_pilotos(st, cid, eid)
            if falta > 0:
                out.append((cid, eid, falta, ev))
    return out


def responder_agora(st, cid, eid, rng=random):
    """Corrida nesta semana e equipe abaixo do mínimo: os pilotos respondem já às propostas pendentes dela para
    esta temporada (sem esperar a semana seguinte)."""
    ofertas = {}
    c = st["categorias"][cid]
    for chave, prop in list(st.get("propostas_usuario", {}).items()):
        if prop["categoria"] != cid or prop["equipe"] != eid or ano_da_oferta(st, prop) != st["ano"]:
            continue
        del st["propostas_usuario"][chave]
        p = st["pilotos"].get(prop.get("piloto", chave))
        if p:
            ofertas.setdefault(p["id"], []).append(dict(prop, pedido=salario_pedido(p, c["categoria"]), usuario=True,
                                                        perspectiva=perspectiva_equipe(st, cid, c["equipes"][eid])))
    _pilotos_decidem(st, ofertas, rng)


def garantir_minimo(st, rng=random, cid=None, ev=None):
    """Equipes do PC abaixo do mínimo para a corrida desta semana contratam já: propostas a vários pilotos livres
    ao mesmo tempo (o primeiro que aceitar leva cada vaga, sem passar do número de carros), em rodadas até chegar
    ao mínimo; sem piloto livre, o jogo cria um piloto novo para a equipe."""
    for c_id in ([cid] if cid else list(st["categorias"])):
        c = st["categorias"][c_id]
        if not minimo_pilotos(st, c_id):
            continue
        for e in ([ev] if ev else corridas_da_semana(st, c_id)):
            for eq in c["equipes"].values():
                if eq.get("ativa") and not eh_humana(st, c_id, eq["id"]):
                    _completar_equipe(st, c_id, eq, e, rng)


def _completar_equipe(st, cid, eq, ev, rng):
    c = st["categorias"][cid]
    categoria = c["categoria"]
    mp = categoria["simulacao"]["mercado_pilotos"]
    piso = mp["salario_minimo_por_corrida"]
    teto = teto_salario(st, cid, eq)
    tentados = set()
    for _rodada in range(6):
        falta = minimo_pilotos(st, cid) - aptos_para_corrida(st, cid, eq["id"], ev["id"])
        if falta <= 0 or vagas(st, cid, eq)[0].get("principal", 0) <= 0:
            return
        cands = []
        for p in st["pilotos"].values():
            if p["id"] in tentados or p.get("contrato") or p.get("lesao"):
                continue
            if acima_da_idade(categoria, idade_no_inicio(st, p, st["ano"])):
                continue
            pedido = salario_pedido(p, categoria)
            cands.append((pedido > teto * 1.1, -ratings.nota_geral_piloto(p, categoria), pedido, p))
        if not cands:
            break
        cands.sort(key=lambda x: x[:3])                # primeiro os que cabem no orçamento, do melhor ao pior
        ofertas = {}
        for _caro, _n, pedido, p in cands[:OFERTAS_POR_VAGA * falta]:
            tentados.add(p["id"])
            ofertas[p["id"]] = [{"categoria": cid, "equipe": eq["id"], "situacao": "principal", "quando": "atual",
                                 "ano_inicio": st["ano"], "valor_por_corrida": round(max(pedido, piso), -2),
                                 "pedido": pedido, "duracao": 1, "unidade": "temporadas",
                                 "perspectiva": perspectiva_equipe(st, cid, eq), "usuario": False,
                                 "compra_contrato": False}]
        _pilotos_decidem(st, ofertas, rng)
    falta = minimo_pilotos(st, cid) - aptos_para_corrida(st, cid, eq["id"], ev["id"])
    vagas_livres = vagas(st, cid, eq)[0].get("principal", 0)
    if falta > 0 and vagas_livres > 0:
        from . import carreira
        for p in carreira.gerar_ficticios(st, min(falta, vagas_livres), rng, destino=cid):
            pedido = salario_pedido(p, categoria)
            _assinar(st, p, {"categoria": cid, "equipe": eq["id"], "situacao": "principal", "quando": "atual",
                             "ano_inicio": st["ano"], "valor_por_corrida": round(max(pedido, piso), -2),
                             "pedido": pedido, "duracao": 1, "unidade": "temporadas", "perspectiva": 0.5,
                             "usuario": False, "compra_contrato": False}, rng)
