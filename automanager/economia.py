"""Economia das equipes: orçamento planejado do PC, empréstimos com juros e falência.

Configuração em categoria["financas"] (valores padrão entre parênteses):
  reserva_minima          fração do orçamento médio que o PC tenta manter em caixa (0.15)
  uso_do_excedente        fração do caixa acima da reserva que o PC investe por temporada (0.5)
  juros_anual             juros dos empréstimos (0.08)
  limite_emprestimo       teto da dívida = fator × orçamento médio × (0.5 + recursos/100) (0.5)
  prazo_temporadas        prazo padrão dos empréstimos, em temporadas (3)
  semanas_para_falencia   semanas seguidas com caixa negativo e sem crédito até a falência (8)
"""
from . import campeonato
from .state import noticia, lancar, pilotos_da_equipe, eh_humana, quem
from .util import dinheiro

PADRAO = {"reserva_minima": 0.15, "uso_do_excedente": 0.5, "juros_anual": 0.08, "limite_emprestimo": 0.5,
          "prazo_temporadas": 3, "semanas_para_falencia": 8}


def cfg(st, cid):
    return dict(PADRAO, **(st["categorias"][cid]["categoria"].get("financas") or {}))


def corridas(st, cid):
    c = st["categorias"][cid]
    return max(1, sum(1 for e in c["calendario"] if e.get("ativo") and e["especie"] == "corrida"))


# ---------------------------------------------------------------- previsão
def receita_prevista(st, cid, eq):
    """Receita esperada na temporada: TV (pela posição) + venda de chassis/motor a clientes + patrocínios."""
    c = st["categorias"][cid]
    regras = c["categoria"]["regras"]
    n = corridas(st, cid)
    total = 0.0
    tv = regras.get("renda_tv") or {}
    if tv.get("ativa"):
        fatores = tv.get("fator_por_posicao_campeonato") or []
        pos = campeonato.posicao_equipe(st, cid, eq["id"])
        fator = fatores[min(pos, len(fatores)) - 1] if (pos and fatores) else 1.0
        total += tv.get("valor_medio_por_equipe", 0) * fator
    from .state import dono_da_parte
    for outra in c["equipes"].values():                   # venda de chassis/motor a clientes
        if outra.get("ativa") and outra["id"] != eq["id"]:
            for parte in ("chassis", "motor"):
                d = dono_da_parte(st, cid, outra, parte)
                if d and d["id"] == eq["id"]:
                    total += ((outra.get(parte) or {}).get("contrato") or {}).get("valor_por_corrida", 0) * n
    for pat in c["patrocinadores"].values():
        ct = pat.get("contrato")
        if pat.get("ativo") and ct and ct.get("equipe") == eq["id"]:
            if ct.get("pagamento") == "por_corrida":
                total += ct["valor"] * (min(n, ct["duracao"]) if ct.get("unidade") == "corridas" else n)
            else:
                total += ct["valor"]
    return total


def despesas_fixas_previstas(st, cid, eq):
    n = corridas(st, cid)
    total = sum(p["contrato"].get("valor_por_corrida", 0) for p in pilotos_da_equipe(st, cid, eq["id"])) * n
    for parte in ("chassis", "motor"):
        info = eq.get(parte) or {}
        if info.get("origem") not in (None, "proprio") and info.get("contrato"):
            total += info["contrato"].get("valor_por_corrida", 0) * n
    total += sum(e["parcela"] for e in eq.get("emprestimos", [])) * n
    return total


def planejar_temporada(st, cid, eq):
    """Verba semanal de desenvolvimento do PC até o fim da temporada (recalculada a cada 13 semanas):
    (receita - despesas fixas) do que ainda falta da temporada + ajuste pelo caixa acima/abaixo da reserva."""
    from . import contratos
    c = cfg(st, cid)
    orc = st["categorias"][cid]["categoria"]["regras"]["orcamento_medio"]
    frac = contratos.corridas_restantes(st, cid) / corridas(st, cid)
    sobra = (receita_prevista(st, cid, eq) - despesas_fixas_previstas(st, cid, eq)) * frac
    excesso = eq["financas"]["caixa"] - orc * c["reserva_minima"]
    ajuste = excesso * (c["uso_do_excedente"] if excesso > 0 else 1.0)
    semanas = max(1, 53 - st["semana"])
    eq["verba_semanal_dev"] = max(0.0, sobra + ajuste) / semanas


# ---------------------------------------------------------------- empréstimos
def divida(eq):
    return sum(e["saldo"] for e in eq.get("emprestimos", []))


def limite_credito(st, cid, eq):
    c = cfg(st, cid)
    orc = st["categorias"][cid]["categoria"]["regras"]["orcamento_medio"]
    return max(0.0, orc * c["limite_emprestimo"] * (0.5 + eq.get("recursos", 50) / 100) - divida(eq))


def simular_emprestimo(st, cid, valor, prazo_temporadas=None):
    c = cfg(st, cid)
    prazo = int(prazo_temporadas or c["prazo_temporadas"])
    n = max(1, prazo * corridas(st, cid))
    taxa = (1 + c["juros_anual"]) ** (1 / corridas(st, cid)) - 1      # juros por corrida
    parcela = valor * taxa / (1 - (1 + taxa) ** -n) if taxa > 0 else valor / n
    return {"valor": valor, "saldo": valor, "juros_anual": c["juros_anual"], "taxa_corrida": taxa,
            "parcelas_restantes": n, "parcela": parcela, "ano": st["ano"], "semana": st["semana"]}


def tomar_emprestimo(st, cid, eq, valor, prazo_temporadas=None):
    """Retorna None ou mensagem de erro."""
    if valor <= 0:
        return "Valor inválido."
    if valor > limite_credito(st, cid, eq) + 1:
        return f"Valor acima do crédito disponível ({dinheiro(limite_credito(st, cid, eq))})."
    emp = simular_emprestimo(st, cid, valor, prazo_temporadas)
    eq.setdefault("emprestimos", []).append(emp)
    lancar(eq, "receitas", "emprestimos", valor)
    noticia(st, f"{quem(st, cid, eq['id'])} toma empréstimo de {dinheiro(valor)} ({emp['parcelas_restantes']} parcelas de "
                f"{dinheiro(emp['parcela'])}, juros de {emp['juros_anual'] * 100:.1f}% ao ano).", cid,
            "usuario" if _usuario(st, cid, eq) else "economia", equipe=eq["id"])
    return None


def quitar_emprestimo(st, cid, eq, indice):
    emp = eq.get("emprestimos", [])[indice]
    if emp["saldo"] > eq["financas"]["caixa"]:
        return "Caixa insuficiente para quitar."
    lancar(eq, "despesas", "emprestimos", emp["saldo"])
    eq["emprestimos"].pop(indice)
    noticia(st, f"Empréstimo quitado ({dinheiro(emp['saldo'])}).", cid, "usuario" if _usuario(st, cid, eq) else "economia")
    return None


def pagar_parcelas(st, cid, eq):
    """Chamado a cada corrida."""
    for emp in list(eq.get("emprestimos", [])):
        juros = emp["saldo"] * emp["taxa_corrida"]
        lancar(eq, "despesas", "emprestimos", emp["parcela"])
        emp["saldo"] = max(0.0, emp["saldo"] + juros - emp["parcela"])
        emp["parcelas_restantes"] -= 1
        if emp["parcelas_restantes"] <= 0 or emp["saldo"] <= 1:
            eq["emprestimos"].remove(emp)


def _usuario(st, cid, eq):
    return eh_humana(st, cid, eq["id"])


# ---------------------------------------------------------------- rotina semanal
def rotina(st):
    """PC planeja verba, recorre a empréstimo quando o caixa fica negativo; falência de quem não consegue."""
    falidas = []
    for cid, c in st["categorias"].items():
        conf = cfg(st, cid)
        for eq in c["equipes"].values():
            if not eq.get("ativa"):
                continue
            usuario = _usuario(st, cid, eq)
            if not usuario and (st["semana"] % 13 == 1 or "verba_semanal_dev" not in eq):
                planejar_temporada(st, cid, eq)
            caixa = eq["financas"]["caixa"]
            if caixa < 0 and not usuario:
                credito = limite_credito(st, cid, eq)
                if credito > 0:
                    tomar_emprestimo(st, cid, eq, min(credito, -caixa + c["categoria"]["regras"]["orcamento_medio"] * 0.05))
                    caixa = eq["financas"]["caixa"]
            if caixa < 0 and limite_credito(st, cid, eq) <= 0:
                eq["semanas_negativo"] = eq.get("semanas_negativo", 0) + 1
                if eq["semanas_negativo"] == max(1, conf["semanas_para_falencia"] // 2) and usuario:
                    noticia(st, f"ALERTA: caixa negativo e sem crédito ({eq['nome']}). Se continuar assim a equipe vai "
                                f"à falência.", cid, "usuario", equipe=eq["id"])
                if eq["semanas_negativo"] >= conf["semanas_para_falencia"]:
                    falidas.append((cid, eq))
            else:
                eq["semanas_negativo"] = 0
    for cid, eq in falidas:
        falir(st, cid, eq)
    return falidas


def falir(st, cid, eq):
    """Falência: a equipe deixa a categoria; pilotos e patrocinadores ficam livres."""
    c = st["categorias"][cid]
    eq["ativa"] = False
    eq["falida_em"] = st["ano"]
    for p in st["pilotos"].values():
        for k in ("contrato", "contrato_futuro"):
            ct = p.get(k)
            if ct and ct.get("categoria") == cid and ct.get("equipe") == eq["id"]:
                p[k] = None
                p["categoria_atual"] = cid
    for pat in c["patrocinadores"].values():
        if pat.get("contrato") and pat["contrato"].get("equipe") == eq["id"]:
            pat["contrato"] = None
    eq["emprestimos"] = []
    if _usuario(st, cid, eq) and st.get("multiplayer"):
        for j in st["multiplayer"]["jogadores"].values():
            if j["categoria"] == cid and j["equipe"] == eq["id"]:
                j["eliminado"] = {"motivo": "falencia", "ano": st["ano"], "semana": st["semana"]}
        noticia(st, f"FALÊNCIA: a {eq['nome']} não conseguiu honrar as dívidas e encerra as atividades. O jogador "
                    f"está fora da liga.", cid, "usuario", equipe=eq["id"])
    elif _usuario(st, cid, eq):
        st["fim_de_jogo"] = {"motivo": "falencia", "ano": st["ano"], "semana": st["semana"]}
        noticia(st, "FALÊNCIA: sua equipe não conseguiu honrar as dívidas e encerra as atividades.", cid, "usuario")
    else:
        noticia(st, f"FALÊNCIA: a {eq['nome']} não consegue pagar as dívidas e deixa a {c['categoria']['nome']}.",
                cid, "equipe")
