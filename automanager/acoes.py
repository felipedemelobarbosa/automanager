"""Ações de gestão de uma equipe humana (a do 'usuário' em st["usuario"]).

Toda decisão tomada nas telas passa por executar(). No modo jogador do multijogador, as ações que deram
certo são gravadas na sessão e vão para o arquivo de ordens; o comissário as reaplica no jogo verdadeiro
com aplicar(), no contexto da equipe do jogador (como()).

Ações (campos):
  proposta_piloto   piloto, situacao, valor, duracao, unidade, inicio ("agora"|"proxima")
  rescindir_piloto  piloto
  contratar_parte   parte ("chassis"|"motor"), id, duracao, unidade, inicio, rescindir (bool)
  proposta_parte    parte, id, valor, duracao, unidade, inicio, rescindir – com negociação de chassis/motor ligada
  rescindir_parte   parte
  patrocinio        patrocinador, aceitar (bool)
  emprestimo        valor, prazo (temporadas ou None)
  quitar_emprestimo indice
  dev_modo          parte, modo ("novo"|"manutencao")
  dev_investir      parte, proxima (bool), incrementos {atributo: pontos a somar}
  dev_inicial       chassis ({atributo: valor} ou None), potencia (int ou None), comprar_chassis (bool: chassis
                    comprado no Mercado, se a categoria deixar) – só equipe recém-criada
  criar_equipe      jogador, nome, nacionalidade, cor, cor_secundaria – multijogador: o jogador cria a própria
                    equipe (o comissário só reservou a vaga); orçamento sorteado com semente fixa da liga + jogador
"""
import random
from contextlib import contextmanager

from . import mercado, economia, desenvolvimento as dev, state


@contextmanager
def como(st, cid, eid):
    """Executa no contexto da equipe (cid, eid) como se fosse a do usuário."""
    antes = st.get("usuario")
    st["usuario"] = {"categoria": cid, "equipe": eid}
    try:
        yield
    finally:
        st["usuario"] = antes


def _ctx(st):
    u = st["usuario"]
    return u["categoria"], st["categorias"][u["categoria"]]["equipes"][u["equipe"]]


def _criar_equipe(st, d):
    u = st["usuario"]
    cid = u.get("categoria")
    if u.get("equipe"):
        return "A equipe já foi criada."
    mp = st.get("multiplayer") or {}
    j = (mp.get("jogadores") or {}).get(d.get("jogador"))
    if not j or j.get("categoria") != cid or j.get("equipe"):
        return "Ação inválida."
    nome, nac = str(d.get("nome", "")).strip(), str(d.get("nacionalidade", "")).strip()
    if not nome or not nac:
        return "Informe o nome e a nacionalidade."
    if nome.lower() in {e["nome"].lower() for e in st["categorias"][cid]["equipes"].values()}:
        return f"Já existe uma equipe chamada {nome}."
    rng = random.Random(f"{mp.get('id')}|{d['jogador']}")      # mesmo orçamento no jogador e no comissário
    eq = state.nova_equipe(st, cid, nome, nac, rng, d.get("cor"), d.get("cor_secundaria"), base="jog_" + d["jogador"])
    u["equipe"] = eq["id"]
    j["equipe"] = eq["id"]
    return None


def aplicar(st, acao, d):
    """Aplica uma ação para a equipe do usuário. Retorna None ou a mensagem de erro."""
    if acao == "criar_equipe":
        return _criar_equipe(st, d)
    if not st["usuario"].get("equipe"):
        return "Crie a equipe primeiro."
    cid, eq = _ctx(st)
    try:
        if acao == "proposta_piloto":
            if d["piloto"] not in st["pilotos"]:
                return "Piloto não encontrado."
            return mercado.fazer_proposta(st, d["piloto"], d["situacao"], float(d["valor"]), int(d["duracao"]),
                                          d["unidade"], d["inicio"])
        if acao == "rescindir_piloto":
            p = st["pilotos"].get(d["piloto"])
            ct = (p or {}).get("contrato")
            if not ct or ct.get("categoria") != cid or ct.get("equipe") != eq["id"]:
                return "O piloto não tem contrato com a equipe."
            mercado.rescindir_piloto(st, d["piloto"])
            return None
        if acao == "proposta_parte":
            return mercado.fazer_proposta_parte(st, cid, eq, d["parte"], d["id"], float(d["valor"]), int(d["duracao"]),
                                                d["unidade"], d["inicio"], rescindir=bool(d.get("rescindir")))
        if acao == "contratar_parte":
            if mercado.negociacao(st["categorias"][cid]["categoria"]):
                return "Nesta categoria o preço é negociado: faça uma proposta ao fornecedor."
            return mercado.contratar_parte(st, cid, eq, d["parte"], d["id"], int(d["duracao"]), d["unidade"],
                                           d["inicio"], rescindir=bool(d.get("rescindir")))
        if acao == "rescindir_parte":
            mercado.rescindir_parte(st, cid, eq, d["parte"])
            return None
        if acao == "patrocinio":
            oferta = next((o for o in st.get("ofertas_patrocinio", []) if o["patrocinador"] == d["patrocinador"]
                           and o["categoria"] == cid and o.get("equipe", eq["id"]) == eq["id"]), None)
            if not oferta:
                return "A oferta de patrocínio não está mais disponível."
            mercado.responder_patrocinio(st, oferta, bool(d["aceitar"]))
            return None
        if acao == "emprestimo":
            return economia.tomar_emprestimo(st, cid, eq, float(d["valor"]), d.get("prazo"))
        if acao == "quitar_emprestimo":
            if not 0 <= int(d["indice"]) < len(eq.get("emprestimos", [])):
                return "Empréstimo não encontrado."
            return economia.quitar_emprestimo(st, cid, eq, int(d["indice"]))
        if acao == "dev_modo":
            if not dev.pode_projeto(st, cid, eq, d["parte"]):
                return "Esta equipe não pode desenvolver esta parte."
            if d["modo"] == "novo" and not dev.projeto_permitido(st, cid, d["parte"]):
                return "Regulamento: não há projeto novo enquanto vale o limite de desenvolvimento."
            dev.mudar_modo(eq, d["parte"], d["modo"])
            return None
        if acao == "dev_inicial":
            if not eq.get("dev_inicial_pendente"):
                return "O desenvolvimento inicial já foi feito."
            ch_ok, mo_ok = state.precisa_desenvolvimento_inicial(st, cid, eq["id"])
            chassis = d.get("chassis") or None
            pot = d.get("potencia")
            if ch_ok and not chassis and not (d.get("comprar_chassis") and
                                              state.compra_de_chassis(st["categorias"][cid]["categoria"])):
                return "Defina o chassis inicial."
            if (chassis and not ch_ok) or (pot is not None and not mo_ok):
                return "Esta categoria não permite essa parte própria."
            custo = state.custo_desenvolvimento_inicial(st, cid, chassis, pot)   # recalculado, não vem do arquivo
            if custo > eq["financas"]["caixa"]:
                return "Caixa insuficiente."
            state.aplicar_desenvolvimento_inicial(st, cid, eq["id"], chassis, None if pot is None else int(pot), custo)
            eq.pop("dev_inicial_pendente", None)
            return None
        if acao == "dev_investir":
            parte = d["parte"]
            atuais = (dev.valores_projeto if d.get("proxima") else dev.valores_atuais)(st, cid, eq, parte)
            alvos = {k: atuais.get(k, 0) + int(n) for k, n in d["incrementos"].items() if int(n) > 0}
            (dev.investir_projeto if d.get("proxima") else dev.investir_atual)(st, cid, eq, parte, alvos)
            return None
    except ValueError as e:
        return str(e)
    except (KeyError, TypeError, IndexError):
        return "Ação inválida."
    return f"Ação desconhecida: {acao}"


def executar(st, acao, **dados):
    """Chamado pelas telas. Aplica e, no modo jogador do multijogador, grava a ação para o arquivo de ordens."""
    erro = aplicar(st, acao, dados)
    sessao = (st.get("multiplayer") or {}).get("sessao")
    if erro is None and sessao is not None:
        sessao.setdefault("acoes", []).append(dict(dados, acao=acao))
    return erro
