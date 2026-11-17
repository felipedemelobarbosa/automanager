"""Notas de desempenho (0-100) de piloto, chassis e motor para uma pista/sessão.

A ponderação vem da matriz `categoria.ponderacao` do JSON:
  para cada característica (retas, curvas_alta, curvas_baixa, desgaste, dificuldade,
  chuva, sessao_*) há pesos sobre os atributos do piloto / chassis / motor.
A importância de cada característica na pista vem dos dados do calendário.
"""

CARACTERISTICAS_BASE = ("retas", "curvas_alta", "curvas_baixa")


def perfil_pista(pista):
    """Frações de retas / curvas de alta / curvas de baixa (somam 1)."""
    tot = sum(max(0.0, float(pista.get(k, 0))) for k in CARACTERISTICAS_BASE) or 1.0
    return {k: max(0.0, float(pista.get(k, 0))) / tot for k in CARACTERISTICAS_BASE}


def _media_ponderada(atributos, pesos):
    soma_p = sum(pesos.values())
    if soma_p <= 0:
        return 50.0
    return sum(atributos.get(a, 50) * w for a, w in pesos.items()) / soma_p


def nota(atributos, matriz, pista, sessao, intensidade_chuva, peso_carac):
    """Nota 0-100 ponderada pelas características da pista.

    sessao: 'treino' | 'classificacao' | 'corrida'
    intensidade_chuva: 0 (seco) .. 1 (chuva forte)
    """
    perfil = perfil_pista(pista)
    termos = []  # (peso, valor)
    for c in CARACTERISTICAS_BASE:
        if c in matriz:
            termos.append((perfil[c] * peso_carac.get(c, 1.0), _media_ponderada(atributos, matriz[c])))
    if "desgaste" in matriz:
        termos.append((pista.get("desgaste_pneus", 50) / 100 * peso_carac.get("desgaste", 0.3),
                       _media_ponderada(atributos, matriz["desgaste"])))
    if "dificuldade" in matriz:
        termos.append((pista.get("dificuldade", 50) / 100 * peso_carac.get("dificuldade", 0.3),
                       _media_ponderada(atributos, matriz["dificuldade"])))
    if intensidade_chuva > 0 and "chuva" in matriz:
        termos.append((intensidade_chuva * peso_carac.get("chuva", 1.0), _media_ponderada(atributos, matriz["chuva"])))
    chave_sessao = f"sessao_{sessao}"
    if chave_sessao in matriz:
        termos.append((peso_carac.get("sessao", 0.5), _media_ponderada(atributos, matriz[chave_sessao])))
    tot = sum(p for p, _ in termos)
    if tot <= 0:
        return 50.0
    return sum(p * v for p, v in termos) / tot


def participacao_motor(pista, ponderacao):
    """Quanto do desempenho do carro vem do motor nesta pista (0..1)."""
    imp = ponderacao.get("importancia_motor_por_caracteristica",
                         {"retas": 0.65, "curvas_alta": 0.3, "curvas_baixa": 0.15})
    perfil = perfil_pista(pista)
    return sum(perfil[c] * imp.get(c, 0.0) for c in CARACTERISTICAS_BASE)


PISTA_GENERICA = {"retas": 40, "curvas_alta": 30, "curvas_baixa": 30, "desgaste_pneus": 50, "dificuldade": 50}


def nota_geral_piloto(piloto, categoria):
    """Nota geral (pista genérica, seco, corrida) – usada pela IA de contratação."""
    pond = categoria["ponderacao"]
    return nota(piloto["atributos"], pond["piloto"], PISTA_GENERICA, "corrida", 0.0, pond["peso_caracteristicas"])


def nota_geral_chassis(chassis, categoria):
    pond = categoria["ponderacao"]
    return nota(chassis["atributos"], pond["chassis"], PISTA_GENERICA, "corrida", 0.0, pond["peso_caracteristicas"])


def nota_geral_carro(chassis, motor, categoria):
    if not chassis and not motor:
        return 0.0
    es = participacao_motor(PISTA_GENERICA, categoria["ponderacao"])
    nc = nota_geral_chassis(chassis, categoria) if chassis else 0.0
    nm = motor.get("potencia", 0) if motor else 0.0
    return nc * (1 - es) + nm * es
