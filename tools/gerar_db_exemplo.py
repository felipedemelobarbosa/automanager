"""Gera as databases de exemplo (fictícias) do AutoManager.  Uso: python tools/gerar_db_exemplo.py database/2026"""
import json, random, sys, os

OUT = sys.argv[1]
rng = random.Random(2026)

NOMES = {
    "Brasil": (["Rafael", "Thiago", "Lucas", "Bruno", "Diego", "Caio", "Pedro", "Gustavo"],
               ["Almeida", "Ferraz", "Moraes", "Teixeira", "Barros", "Cardoso", "Pires", "Rezende"]),
    "Reino Unido": (["Oliver", "James", "Harry", "Callum", "Alfie", "George"],
                    ["Whitmore", "Ashby", "Pennington", "Hale", "Crowther", "Dalton"]),
    "Itália": (["Matteo", "Lorenzo", "Davide", "Simone", "Andrea"],
               ["Ferrante", "Bellucci", "Moretti", "Galli", "Rinaldi"]),
    "Alemanha": (["Lukas", "Jonas", "Felix", "Maximilian", "Tobias"],
                 ["Brandt", "Kessler", "Hoffmann", "Vogt", "Lindner"]),
    "França": (["Antoine", "Hugo", "Julien", "Théo", "Mathis"],
               ["Delacroix", "Marchand", "Fontaine", "Girard", "Lemoine"]),
    "Japão": (["Haruto", "Ren", "Daiki", "Sota"], ["Kisaragi", "Moriyama", "Tachibana", "Oshiro"]),
    "Espanha": (["Pablo", "Álvaro", "Javier", "Marcos"], ["Ortega", "Navarro", "Salcedo", "Iglesias"]),
    "Argentina": (["Facundo", "Nicolás", "Tomás"], ["Ibarra", "Quiroga", "Sosa"]),
    "Estados Unidos": (["Tyler", "Connor", "Austin", "Wyatt"], ["Brooks", "Harlan", "McCoy", "Sutton"]),
    "Canadá": (["Liam", "Noah", "Ethan"], ["Tremblay", "Gagnon", "Bouchard"]),
    "Finlândia": (["Aleksi", "Eetu", "Joonas"], ["Lahtinen", "Virtanen", "Koskela"]),
    "Austrália": (["Jack", "Cooper", "Riley"], ["Pemberton", "Gallagher", "Fraser"]),
    "Holanda": (["Daan", "Sem", "Bram"], ["de Vries", "Mulder", "Bakker"]),
    "México": (["Emiliano", "Santiago"], ["Villaseñor", "Arriaga"]),
}
usados = set()


def nome_piloto(nac):
    while True:
        p, s = NOMES[nac]
        n = f"{rng.choice(p)} {rng.choice(s)}"
        if n not in usados:
            usados.add(n)
            return n


ATR_P = ["consistencia", "ritmo_corrida", "concentracao", "chuva", "aceleracao", "acerto_carro",
         "trabalho_equipe", "classificacao", "fisico", "conducao", "largada"]
ATR_C = ["aerodinamica", "grip", "cambio", "freio", "eletrica", "dirigibilidade", "confiabilidade",
         "classificacao", "chuva", "pneus"]


def attrs(keys, media, desvio=8):
    return {k: max(5, min(99, int(rng.gauss(media, desvio)))) for k in keys}


def piloto(pid, nac, media, idade, contrato):
    ano_pico = 2026 + max(0, rng.randint(27, 31) - idade)
    p = {"id": pid, "nome": nome_piloto(nac), "nacionalidade": nac, "idade": idade,
         "atributos": attrs(ATR_P, media), "contrato": contrato, "ano_pico": ano_pico,
         "potencial": min(97, int(media + max(0, ano_pico - 2026) * rng.uniform(1.0, 3.0)))}
    if idade >= 33:
        p["ano_aposentadoria"] = 2026 + rng.randint(1, 5)
    return p


def r100(x, step=1000):
    return int(round(x / step) * step)


# ------------------------------------------------------------------ comum
PONDERACAO = {
    "peso_caracteristicas": {"retas": 1.0, "curvas_alta": 1.0, "curvas_baixa": 1.0, "desgaste": 0.35,
                             "dificuldade": 0.35, "chuva": 1.6, "sessao": 0.7},
    "piloto": {
        "retas": {"aceleracao": 0.5, "conducao": 0.3, "concentracao": 0.2},
        "curvas_alta": {"conducao": 0.5, "concentracao": 0.3, "fisico": 0.2},
        "curvas_baixa": {"conducao": 0.45, "aceleracao": 0.3, "concentracao": 0.25},
        "desgaste": {"consistencia": 0.6, "conducao": 0.4},
        "dificuldade": {"concentracao": 0.5, "consistencia": 0.3, "conducao": 0.2},
        "chuva": {"chuva": 1.0},
        "sessao_treino": {"acerto_carro": 0.5, "ritmo_corrida": 0.5},
        "sessao_classificacao": {"classificacao": 1.0},
        "sessao_corrida": {"ritmo_corrida": 0.5, "consistencia": 0.3, "fisico": 0.2}
    },
    "chassis": {
        "retas": {"aerodinamica": 0.35, "cambio": 0.4, "eletrica": 0.25},
        "curvas_alta": {"aerodinamica": 0.6, "grip": 0.2, "dirigibilidade": 0.2},
        "curvas_baixa": {"grip": 0.4, "freio": 0.35, "dirigibilidade": 0.25},
        "desgaste": {"pneus": 1.0},
        "dificuldade": {"dirigibilidade": 0.6, "freio": 0.4},
        "chuva": {"chuva": 0.6, "grip": 0.4},
        "sessao_treino": {"dirigibilidade": 1.0},
        "sessao_classificacao": {"classificacao": 1.0},
        "sessao_corrida": {"pneus": 0.6, "confiabilidade": 0.4}
    },
    "motor": {
        "retas": {"potencia": 1.0}, "curvas_alta": {"potencia": 1.0}, "curvas_baixa": {"potencia": 1.0}
    },
    "importancia_motor_por_caracteristica": {"retas": 0.65, "curvas_alta": 0.3, "curvas_baixa": 0.15}
}

PNEUS = {
    "compostos": {
        "super_macio": {"nome": "Super macio", "tipo": "seco", "ritmo": 0.9915, "degradacao": 0.0019, "vida": 11,
                        "cliff": 0.006, "aquecimento_voltas": 0, "sensibilidade_termica": 1.4},
        "macio": {"nome": "Macio", "tipo": "seco", "ritmo": 0.994, "degradacao": 0.0012, "vida": 17,
                  "cliff": 0.005, "aquecimento_voltas": 1, "sensibilidade_termica": 1.2},
        "medio": {"nome": "Médio", "tipo": "seco", "ritmo": 0.9968, "degradacao": 0.0007, "vida": 26,
                  "cliff": 0.0045, "aquecimento_voltas": 1, "sensibilidade_termica": 1.0},
        "duro": {"nome": "Duro", "tipo": "seco", "ritmo": 1.0, "degradacao": 0.00045, "vida": 36,
                 "cliff": 0.004, "aquecimento_voltas": 2, "sensibilidade_termica": 0.8},
        "muito_duro": {"nome": "Muito duro", "tipo": "seco", "ritmo": 1.003, "degradacao": 0.0003, "vida": 48,
                       "cliff": 0.0035, "aquecimento_voltas": 3, "sensibilidade_termica": 0.6},
        "chuva_leve": {"nome": "Chuva leve", "tipo": "chuva_leve", "ritmo": 1.0, "degradacao": 0.0005, "vida": 30,
                       "cliff": 0.004, "aquecimento_voltas": 1, "sensibilidade_termica": 1.0},
        "chuva_pesada": {"nome": "Chuva pesada", "tipo": "chuva_pesada", "ritmo": 1.0, "degradacao": 0.0004,
                         "vida": 35, "cliff": 0.004, "aquecimento_voltas": 1, "sensibilidade_termica": 1.0}
    },
    "_comentario_compostos": "ritmo = multiplicador do tempo com pneu ideal; degradacao = fração do tempo perdida por "
                             "volta de uso; vida = voltas (pista e carro de referência) até o cliff; cliff = perda "
                             "extra por (voltas além da vida)^1.5; aquecimento_voltas = voltas até o pneu entrar na "
                             "temperatura; sensibilidade_termica = quanto agressividade/uso do carro aumentam a "
                             "degradação. Pista (desgaste_pneus), carro (atributo pneus) e piloto (consistência) "
                             "multiplicam a degradação e dividem a vida.",
    "adequacao_clima": {
        "seco": {"seco": 1.0, "chuva_leve": 1.05, "chuva_pesada": 1.09},
        "chuva_leve": {"seco": 1.09, "chuva_leve": 1.0, "chuva_pesada": 1.025},
        "chuva_pesada": {"seco": 1.28, "chuva_leve": 1.04, "chuva_pesada": 1.0}
    },
    "_comentario_adequacao": "linha = clima atual, coluna = tipo de pneu. Multiplicador do tempo de volta.",
    "penalidade_aquecimento": 0.008,
    "desgaste_critico": 100,
    "desgaste_quebra": 140,
    "_comentario_desgaste": "desgaste = % da vida usada. Acima de desgaste_critico o pneu pode furar; a partir de "
                            "desgaste_quebra o furo tende a causar abandono."
}

CLIMA = {
    "efeitos": {
        "seco": {"tempo": 1.0, "peso_chassis": 1.0, "peso_motor": 1.0, "peso_piloto": 1.0,
                 "acidentes": 1.0, "aleatoriedade": 1.0, "ultrapassagem": 1.0},
        "chuva_leve": {"tempo": 1.07, "peso_chassis": 1.15, "peso_motor": 0.75, "peso_piloto": 1.25,
                       "acidentes": 2.0, "aleatoriedade": 1.5, "ultrapassagem": 0.85},
        "chuva_pesada": {"tempo": 1.15, "peso_chassis": 1.25, "peso_motor": 0.55, "peso_piloto": 1.5,
                         "acidentes": 3.5, "aleatoriedade": 2.0, "ultrapassagem": 0.7}
    },
    "proporcao_chuva_forte": 0.35,
    "estabilidade_por_10min": 0.94,
    "_comentario": "estabilidade = probabilidade de o clima não tentar mudar a cada 10 minutos simulados (muda um "
                   "passo por vez: seco ↔ chuva leve ↔ chuva forte). prob_chuva de cada pista = fração das sessões com "
                   "chuva, a longo prazo."
}


def simulacao(amplitude, salario_min, salario_max):
    return {
        "amplitude_desempenho": amplitude,
        "_comentario_amplitude": "diferença máxima de tempo de volta entre nota 0 e nota 100 (fração).",
        "aleatoriedade_volta": 0.004,
        "evolucao_pista": 0.012,
        "aprendizado_por_volta": 0.03,
        "penalidade_maxima_acerto": 0.018,
        "reducao_maxima_acerto_piloto": 0.6,
        "efeito_combustivel_por_volta": 0.00055,
        "taxa_erro_volta": 0.03,
        "taxa_acidente_base": 0.0012,
        "taxa_quebra_base": 0.0010,
        "ultrapassagem_base": 0.30,
        "fator_ultrapassagem_rua": 0.6,
        "ultrapassagem_retas_referencia": 0.4,
        "ultrapassagem_expoente_retas": 2.0,
        "ultrapassagem_sensibilidade_ritmo": 1.2,
        "ultrapassagem_expoente_ritmo": 2.0,
        "variacao_estrategia_s": 6.0,
        "variacao_stint": 0.1,
        "oval": {"alcance_relargada_s": 0.8, "alcance_vacuo_s": 1.5, "amarelas_detritos_por_corrida": 6.0, "carros_max_pelotao": 12, "colisao_oval_curto": 2.5, "compressao_pelotao": 0.6, "custo_disputa_pelotao": 0.3, "efeito_largada": 0.3, "multiplicador_batida_pelotao": 6.0, "piso_relargada": 0.6, "piso_ultrapassagem_pelotao": 0.4, "prob_amarela_acidente": 0.9, "prob_amarela_quebra": 0.35, "respeitar_tempo_maximo": False, "retas_pelotao": [0.5, 0.75], "tentativas_relargada": 3, "vacuo": 0.012, "voltas_amarela": [4, 7], "_comentario": "Corrida em oval (tipo_pista 'oval'). O tipo sai das retas/curvas da pista: 'pelotão' cresce com as retas entre retas_pelotao [mín, máx] (superspeedway, pack racing) e 'curto' com poucas retas ou curvas lentas (short track); o intermediário fica entre os dois. vacuo: ganho no vácuo (fração do tempo) até alcance_vacuo_s; compressao_pelotao: aproxima o ritmo dos carros no pelotão; piso_ultrapassagem_pelotao e custo_disputa_pelotao: passa-se fácil e sem perder muito tempo no pelotão; multiplicador_batida_pelotao e carros_max_pelotao: o 'Big One'; prob_amarela_acidente/quebra e amarelas_detritos_por_corrida (por corrida, independe do nº de voltas): bandeira amarela (safety car, nunca VSC); voltas_amarela [mín, máx]; colisao_oval_curto: contato no oval curto; efeito_largada: largada lançada; tentativas_relargada e piso_relargada: relargada em fila dupla (alcance_relargada_s: lado a lado, disputa quem está até essa distância). respeitar_tempo_maximo: False = no oval a corrida cumpre a distância (sem limite de tempo, como na IndyCar/NASCAR)."},
        "risco_colisao_disputa": 0.008,
        "distancia_minima_s": 0.25,
        "intervalo_grid_s": 0.25,
        "ordens": {"agressividade_tempo": 0.0018, "agressividade_risco": 0.4, "agressividade_desgaste": 0.12,
                   "uso_motor_tempo": 0.0015, "uso_motor_quebra": 0.45, "uso_motor_combustivel": 0.04,
                   "uso_carro_tempo": 0.0012, "uso_carro_quebra": 0.3, "uso_carro_desgaste": 0.1},
        "_comentario_pitstop": "não cumprir a parada obrigatória não gera penalidade de tempo: a consequência é "
                               "o desgaste extremo do pneu / falta de combustível (provável abandono).",
        "mercado_pilotos": {"salario_minimo_por_corrida": salario_min,
                            "salario_maximo_por_corrida": salario_max,
                            "fracao_orcamento_pilotos": 0.2,
                            "peso_salario_na_escolha": 0.55,
                            "peso_perspectiva_na_escolha": 0.45,
                            "semana_inicio_propostas": 20}
    }


MOBILIDADE = {"de_tier_inferior": 1.0, "de_tier_superior": 0.3, "mesmo_tier": 0.6,
              "_comentario": "multiplicadores da chance de um piloto vir de outra categoria para esta: de um tier "
                             "inferior (subindo), de um tier superior (descendo) ou do mesmo tier. Tier 1 = topo.",
              "retorno": {"prob_anual": 0.04, "anos_maximos_fora": 6, "idade_maxima": 40, "_comentario": "Aposentado pode voltar à categoria de onde saiu: chance por temporada (cai quanto mais tempo fora; zero depois de anos_maximos_fora ou acima de idade_maxima). Base real: na F1, ~1 piloto por temporada volta depois de 1+ temporada parado, entre ~25 ex-pilotos dos últimos 6 anos (≈4% ao ano por ex-piloto)."}}

CARREIRA = {"calibracao_automatica": True, "_comentario": "Mantém o nível dos pilotos perto da database: estreantes com nível e potencial da database do início do jogo e correção suave por temporada do potencial (pelo tier mais alto)."}

MERCADO_PATROCINIO = {"prob_busca_semanal": 0.10, "peso_desempenho": 0.4, "validade_oferta_semanas": 4,
                      "_comentario": "patrocinador livre procura equipe: índice carro x pilotos com aleatoriedade; "
                                     "depois da 1ª corrida o desempenho (posição no campeonato) entra com peso_desempenho."}


EMPRESAS_PRE = ["Aurora", "Vértice", "Nimbus", "Atlântico", "Boreal", "Cobalto", "Delta", "Equinócio", "Falcão",
                "Granito", "Horizonte", "Jade", "Kronos", "Lumen", "Meridiano", "Netuno", "Órion", "Quasar", "Rubi",
                "Safira", "Titã", "Vega", "Zênite", "Brisa", "Cometa", "Dínamo", "Fênix", "Hélio", "Lótus", "Monarca"]
EMPRESAS_SUF = [("Energia", "Energia"), ("Bank", "Bancos"), ("Telecom", "Telecomunicações"), ("Seguros", "Seguros"),
                ("Logística", "Logística"), ("Bebidas", "Bebidas"), ("Tech", "Tecnologia"), ("Air", "Aviação"),
                ("Watches", "Relógios"), ("Alimentos", "Alimentos"), ("Motors", "Automotivo"),
                ("Lubrificantes", "Petróleo"), ("Eletrônicos", "Eletrônicos"), ("Investimentos", "Finanças")]


def patrocinadores(equipes, orcamento, corridas, livres=5, inativos=3):
    """1 a 4 patrocinadores por equipe ativa (mais para quem tem mais recursos) + alguns livres e inativos."""
    usados, lista = set(), []

    def nome():
        while True:
            suf, ramo = rng.choice(EMPRESAS_SUF)
            n = f"{rng.choice(EMPRESAS_PRE)} {suf}"
            if n not in usados:
                usados.add(n)
                return n, ramo

    paises = [e["nacionalidade"] for e in equipes]
    ativas = [e for e in equipes if e["ativa"]]
    total = sum(1 + round(e["recursos"] / 35) for e in ativas) + livres + inativos
    k = 0
    for e in ativas + [None] * (livres + inativos):
        qtd = 1 + round(e["recursos"] / 35) if e else 1
        for _ in range(qtd):
            k += 1
            n, ramo = nome()
            pais = e["nacionalidade"] if (e and rng.random() < 0.5) else rng.choice(paises)
            base = r100(orcamento * rng.uniform(0.07, 0.20) * (0.6 + (e["recursos"] if e else 50) / 100), 1000)
            ativo = e is not None or k <= total - inativos
            contrato = None
            if e:
                if rng.random() < 0.7:
                    contrato = {"equipe": e["id"], "valor": base, "pagamento": "por_temporada",
                                "duracao": rng.choice([1, 2, 3]), "unidade": "temporadas"}
                else:
                    contrato = {"equipe": e["id"], "valor": r100(base / corridas, 1000), "pagamento": "por_corrida",
                                "duracao": rng.choice([corridas // 2, corridas, corridas + corridas // 2]),
                                "unidade": "corridas"}
            pref = rng.choice([{"tipo": "nacionalidade_equipe", "valor": pais},
                               {"tipo": "nacionalidade_piloto", "valor": pais},
                               {"tipo": "posicao_campeonato", "valor": rng.choice([3, 5, 8])}])
            lista.append({"id": f"pat{k:02d}", "nome": n, "ativo": ativo, "pais": pais, "ramo": ramo,
                          "valor_base": base, "preferencia": pref, "contrato": contrato,
                          "prob_fechamento": 0.03 if ativo else 0.0, "prob_surgimento": 0.0 if ativo else 0.3})
    return lista


CORES = {"vortex": ("#0b1f4b", "#d4af37"), "ventura": ("#c8102e", "#ffd100"), "hanazono": ("#ffffff", "#e4002b"),
         "lumiere": ("#0055a4", "#ffffff"), "kestrel": ("#ff8200", "#1a1a1a"), "nordwind": ("#7a7a7a", "#00a3e0"),
         "andes": ("#6cace4", "#ffffff"), "tucano": ("#009c3b", "#ffdf00"), "maple": ("#d52b1e", "#ffffff"),
         "atlas": ("#1a1a1a", "#c8102e"), "iberia": ("#aa151b", "#f1bf00"), "danubio": ("#4b0082", "#ff8200"),
         "prisma": ("#6a1b9a", "#00b2a9"), "halcon": ("#ffd100", "#c8102e"), "redline": ("#e10600", "#1a1a1a"),
         "orbita": ("#003b5c", "#ff8200"), "falke": ("#1a1a1a", "#ffd100"), "sakura": ("#ffb7c5", "#c8102e"),
         "liberty": ("#002868", "#bf0a30"), "pampas": ("#74acdf", "#f6b40e"), "fjord": ("#00a3e0", "#ffffff")}


BANDEIRA_VERMELHA = {
    "relogio_durante_suspensao": "parado", "limite_espera_sessao_min": 60, "limite_espera_corrida_min": 120,
    "_comentario": "Oval com chuva = bandeira vermelha. relogio_durante_suspensao: 'parado' (a espera não tira tempo "
                   "de pista nem conta para o tempo máximo da corrida) ou 'corre' (conta). Limites de espera em "
                   "minutos: passou sem secar, a sessão é encerrada (valem os tempos feitos) e a corrida termina "
                   "(se nem largou, é cancelada e ninguém pontua). 0 = sem limite."}


BATIDA_GRAVE = {
    "prob_por_volta": 0.0015,
    "fator_treinos": 0.5,
    "carros_min": 2,
    "carros_max": 5,
    "prob_encerrar_sessao": 0.2,
    "prob_lesao": 0.06,
    "prob_morte": 0.002,
    "lesao_corridas": [
        1,
        6
    ],
    "lesao_perda_atributos": [
        1,
        6
    ],
    "atributos_afetados": [
        "fisico",
        "concentracao",
        "conducao"
    ],
    "_comentario": "Batida grave = vários carros abandonam juntos. prob_por_volta: chance por volta do líder na corrida (×3 na 1ª volta, × acidentes do clima, × dificuldade da pista); treinos/classificação usam fator_treinos. prob_encerrar_sessao: chance de a bandeira vermelha encerrar a sessão. prob_lesao / prob_morte: por piloto envolvido. Lesão: fica fora de lesao_corridas [mín, máx] corridas e perde lesao_perda_atributos [mín, máx] pontos em cada atributo de atributos_afetados."
}

REGULAMENTO = {'ativo': True, 'semana_anuncio': 30, 'prob_grande_mudanca': 0.2, 'perda_grande_mudanca': [0.15, 0.3], 'aumento_importancia_carro': [0.05, 0.1], 'convergencia_por_temporada': 0.02, 'prob_limite_desenvolvimento': 0.15, 'limite_duracao': [2, 4], 'prob_congelamento': 0.5, 'limite_pontos_por_temporada': [2, 5], 'prob_ajuste_importancia': 0.15, 'ajuste_importancia': 0.03, 'importancia_carro_min': 0.3, 'importancia_carro_max': 0.8, '_comentario': 'Mudanças de regulamento, anunciadas na semana_anuncio para a temporada seguinte: grande mudança (chassis perdem mais na manutenção; importância do carro sobe e depois volta aos poucos ao valor da database), limite de desenvolvimento de uma parte (congelado ou pontos por temporada) e ajuste pequeno da importância do carro. Referência F1: grande mudança ~1 a cada 4 anos.'}

CORRIDA_INTERROMPIDA = {
    "distancia_minima": 0.5,
    "pontos_parciais": "metade",
    "_comentario": "Corrida encerrada antes do fim (chuva que não para, batida grave): a partir de distancia_minima (fração das voltas) vale a pontuação integral; abaixo, 'metade' dos pontos ou 'proporcional' à distância. Sem nenhuma volta completa, ninguém pontua."
}


def pista(i, nome, local, tipo, retas, ca, cb, desg, dif, pit, tb, voltas, chuva, semana, especie="corrida",
          ativo=True, p_in=0.02, p_at=0.0):
    return {"id": f"ev{i:02d}", "nome": nome, "ativo": ativo, "semana": semana, "especie": especie,
            "local": local, "tipo_pista": tipo, "tempo_base_treino": tb, "tempo_base_corrida": round(tb * 1.025, 2),
            "voltas_corrida": voltas, "retas": retas, "curvas_alta": ca, "curvas_baixa": cb,
            "desgaste_pneus": desg, "dificuldade": dif, "duracao_pitstop": pit, "prob_chuva": chuva,
            "prob_inativar": p_in, "prob_ativar": p_at}


PISTAS = [
    ("Grande Prêmio de Serra Azul", "Serra Azul, Brasil", "mista", 40, 30, 30, 60, 55, 22.0, 78.4, 64, 0.30),
    ("Grande Prêmio de Westmoor", "Westmoor, Reino Unido", "mista", 35, 45, 20, 55, 50, 21.0, 88.2, 52, 0.35),
    ("Gran Premio di Valtorre", "Valtorre, Itália", "mista", 60, 25, 15, 40, 40, 23.5, 82.1, 53, 0.12),
    ("Grand Prix de Port-Lumière", "Port-Lumière, Mônaco", "rua", 15, 10, 75, 30, 90, 20.0, 74.0, 78, 0.10),
    ("Großer Preis von Eichwald", "Eichwald, Alemanha", "mista", 45, 30, 25, 50, 45, 22.0, 90.5, 55, 0.25),
    ("Grande Prêmio de Laguna Seca do Sul", "Porto Sereno, Brasil", "mista", 30, 25, 45, 70, 60, 24.0, 71.0, 71, 0.25),
    ("Kisaragi Grand Prix", "Kisaragi, Japão", "mista", 30, 50, 20, 65, 70, 22.5, 91.3, 53, 0.30),
    ("Gran Premio de Costa Blanca", "Costa Blanca, Espanha", "mista", 35, 30, 35, 75, 45, 22.0, 80.8, 66, 0.08),
    ("Lakeshore 300", "Lakeshore, Estados Unidos", "oval", 80, 20, 0, 45, 35, 19.0, 38.5, 160, 0.15),
    ("Grand Prix de Marais", "Marais, Canadá", "rua", 45, 5, 50, 50, 65, 20.0, 76.2, 70, 0.20),
    ("Grand Prix of Pemberton Park", "Melbourne Sul, Austrália", "rua", 40, 25, 35, 45, 55, 21.0, 81.0, 58, 0.20),
    ("Gran Premio de Cerro Alto", "Cerro Alto, México", "mista", 50, 20, 30, 55, 45, 22.0, 79.0, 71, 0.10),
    ("Grand Prix van Duinwijk", "Duinwijk, Holanda", "mista", 30, 45, 25, 50, 55, 22.0, 73.5, 72, 0.35),
    ("Grande Prêmio de Atlântica", "Atlântica, Brasil", "mista", 45, 25, 30, 60, 50, 22.0, 72.4, 71, 0.40),
    # pistas só para as corridas de reserva (inativas): não repetem uma pista que já está no calendário
    ("Grand Prix de Montval", "Montval, Bélgica", "mista", 50, 35, 15, 55, 60, 23.0, 95.0, 44, 0.40),
    ("Gran Premio de Bahía Serena", "Bahía Serena, Chile", "rua", 35, 20, 45, 45, 70, 21.0, 79.5, 62, 0.15),
]


def calendario(qtd, semana_ini, passo, testes, extras_inativos):
    cal = []
    i = 1
    for (sem, nome, idx) in testes:
        p = PISTAS[idx]
        cal.append(pista(i, nome, p[1], p[2], p[3], p[4], p[5], p[6], p[7], p[8], p[9], 0, p[11], sem, "treino"))
        i += 1
    for k in range(qtd):
        p = PISTAS[k]
        cal.append(pista(i, p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], p[8], p[9], p[10], p[11],
                         semana_ini + k * passo))
        i += 1
    for idx in extras_inativos:
        p = PISTAS[idx]
        cal.append(pista(i, p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], p[8], p[9], p[10], p[11],
                         50, ativo=False, p_at=0.25))
        i += 1
    return cal


# =================================================================== FÓRMULA ALFA
def formula_alfa():
    equipes_def = [
        # id, nome, nac, recursos, chassis_media, motor
        ("vortex", "Vortex Racing", "Reino Unido", 92, 84, ("proprio", "mot_vortex")),
        ("ventura", "Scuderia Ventura", "Itália", 88, 81, ("proprio", "mot_ventura")),
        ("hanazono", "Hanazono Motorsport", "Japão", 80, 76, ("proprio", "mot_hanazono")),
        ("lumiere", "Équipe Lumière", "França", 70, 72, ("fabricante", "mot_rhone")),
        ("kestrel", "Kestrel Grand Prix", "Reino Unido", 65, 70, ("equipe", "mot_vortex")),
        ("nordwind", "Nordwind Racing", "Alemanha", 60, 66, ("fabricante", "mot_kraft")),
        ("andes", "Andes Racing", "Argentina", 50, 62, ("equipe", "mot_ventura")),
        ("tucano", "Tucano Racing", "Brasil", 45, 60, ("fabricante", "mot_kraft")),
        ("maple", "Maple Speed", "Canadá", 40, 57, ("equipe", "mot_hanazono")),
        ("atlas", "Atlas Grand Prix", "Estados Unidos", 35, 54, ("fabricante", "mot_rhone")),
        ("iberia", "Iberia Racing", "Espanha", 40, 55, ("fabricante", "mot_kraft")),
        ("danubio", "Danúbio GP", "Holanda", 30, 52, ("fabricante", "mot_rhone")),
    ]
    motores = [
        {"id": "mot_vortex", "nome": "Vortex V-26", "nacionalidade": "Reino Unido", "potencia": 88,
         "fabricante": {"tipo": "equipe", "equipe": "vortex"}, "exclusividade": {"exclusivo": False, "equipe": None},
         "contrato": {"valor_por_corrida": 520000, "temporadas": 2}},
        {"id": "mot_ventura", "nome": "Ventura Tipo 26", "nacionalidade": "Itália", "potencia": 86,
         "fabricante": {"tipo": "equipe", "equipe": "ventura"},
         "exclusividade": {"exclusivo": True, "equipe": "Andes Racing"},
         "contrato": {"valor_por_corrida": 480000, "temporadas": 2}},
        {"id": "mot_hanazono", "nome": "Hanazono RA-26", "nacionalidade": "Japão", "potencia": 82,
         "fabricante": {"tipo": "equipe", "equipe": "hanazono"}, "exclusividade": {"exclusivo": False, "equipe": None},
         "contrato": {"valor_por_corrida": 420000, "temporadas": 2}},
        {"id": "mot_kraft", "nome": "Kraft KM-8", "nacionalidade": "Alemanha", "potencia": 78,
         "fabricante": {"tipo": "fabricante"}, "exclusividade": {"exclusivo": False, "equipe": None},
         "contrato": {"valor_por_corrida": 350000, "temporadas": 1}},
        {"id": "mot_rhone", "nome": "Rhône R26", "nacionalidade": "França", "potencia": 74,
         "fabricante": {"tipo": "fabricante"}, "exclusividade": {"exclusivo": False, "equipe": None},
         "contrato": {"valor_por_corrida": 300000, "temporadas": 1}},
    ]
    equipes, chassis, pilotos = [], [], []
    nacs = list(NOMES.keys())
    pn = 1
    for (eid, nome, nac, rec, cm, (origem, mid)) in equipes_def:
        ativa = eid not in ("iberia", "danubio")
        chassis.append({"id": f"ch_{eid}", "nome": f"{nome.split()[0]} C26" if eid != "lumiere" else "Lumière L26",
                        "nacionalidade": nac, "equipe": eid, "atributos": attrs(ATR_C, cm, 6), "contrato": None})
        motor = {"id": mid, "origem": origem}
        if origem != "proprio":
            m = next(x for x in motores if x["id"] == mid)
            motor["contrato"] = {"valor_por_corrida": m["contrato"]["valor_por_corrida"],
                                 "temporadas": rng.choice([1, 2])}
        equipes.append({"id": eid, "nome": nome, "ativa": ativa, "nacionalidade": nac, "recursos": rec,
                        "cor": CORES[eid][0], "cor_secundaria": CORES[eid][1], "caixa": None,
                        "chassis": {"id": f"ch_{eid}", "origem": "proprio"}, "motor": motor,
                        "prob_fechamento": round(max(0.003, (100 - rec) / 4000), 3),
                        "prob_surgimento": 0.0 if ativa else 0.15})
        if eid == "danubio":
            equipes[-1]["ano_surgimento"] = 2028
        if not ativa:
            continue
        for k in range(2):
            media = int(rec * 0.3 + 52 + rng.randint(-6, 6))
            nac_p = nac if rng.random() < 0.35 else rng.choice(nacs)
            sal = r100(20000 + (media - 50) ** 2 * 260, 5000)
            pilotos.append(piloto(f"p{pn:03d}", nac_p, media, rng.randint(20, 36),
                                  {"equipe": eid, "valor_por_corrida": sal, "temporadas": rng.choice([1, 1, 2, 3]),
                                   "situacao": "principal"}))
            pn += 1
        pilotos.append(piloto(f"p{pn:03d}", rng.choice(nacs), rng.randint(50, 64), rng.randint(18, 24),
                              dict({"equipe": eid, "valor_por_corrida": 10000, "situacao": "teste"},
                                   **({"corridas": 7} if rec < 50 else {"temporadas": 1}))))
        pn += 1
    for k in range(9):
        pilotos.append(piloto(f"p{pn:03d}", rng.choice(nacs), rng.randint(52, 72), rng.randint(19, 34), None))
        pn += 1

    patro = patrocinadores(equipes, 60000000, 14)

    return {
        "versao_formato": 1,
        "categoria": {
            "id": "formula_alfa", "nome": "Fórmula Alfa", "ano": 2026, "moeda": "USD",
            "regras": {
                "pilotos_de_teste": True,
                "pilotos_principais_por_equipe": 2,
                "pilotos_de_teste_por_equipe": 1,
                "desenvolvimento_chassis_por_equipe": True,
                "desenvolvimento_motor_por_equipe": True,
                "equipes_com_desenvolvimento_de_motor": ["vortex", "ventura", "hanazono"],
                "_comentario_motor": "lista vazia = todas as equipes podem desenvolver motor próprio.",
                "fontes_de_motor_permitidas": ["proprio", "equipe", "fabricante"],
                "testes_coletivos": True,
                "orcamento_medio": 60000000,
                "inflacao_media_anual": 0.03,
                "patrocinios": True,
                "renda_tv": {"ativa": True, "valor_medio_por_equipe": 15000000,
                             "fator_por_posicao_campeonato": [1.4, 1.3, 1.2, 1.1, 1.05, 1.0, 0.95, 0.9, 0.8, 0.7]},
                "clientes_por_chassis": 2,
                "importancia_carro": 0.6,
                "importancia_piloto": 0.4,
                "idade_pilotos": {"idade_maxima": None, "preferida_ate": None, "penalidade_por_ano": 0, "_comentario": "idade_maxima: acima dela a categoria não contrata e o contrato termina na virada de temporada (vazio = sem limite). preferida_ate / penalidade_por_ano: na escolha das equipes do PC, cada ano acima da idade preferida tira esses pontos da nota do piloto (categorias de base preferem pilotos jovens)."},
                "bandeira_vermelha": BANDEIRA_VERMELHA,
                "batida_grave": BATIDA_GRAVE
            },
            "tier": 1,
            "novas_equipes": [{"equipe": "danubio", "ano": 2028}, {"equipe": "iberia", "ano": None}],
            "_comentario_novas_equipes": "equipes (inativas no arquivo) que podem surgir; com 'ano', surgem nesse ano; "
                                         "sem ano, por sorteio (prob_surgimento da equipe). A equipe também pode ter "
                                         "o campo 'ano_surgimento'.",
            "mobilidade": MOBILIDADE,
            "carreira": CARREIRA,
            "mercado_patrocinio": MERCADO_PATROCINIO,
            "financas": {"reserva_minima": 0.15, "uso_do_excedente": 0.5, "juros_anual": 0.08,
                         "limite_emprestimo": 0.5, "prazo_temporadas": 3, "semanas_para_falencia": 8,
                         "_comentario": "reserva_minima e limite_emprestimo são frações do orçamento médio; o limite "
                                        "é multiplicado por (0,5 + recursos/100) da equipe."},
            "contratos": {"fator_multa": 0.5,
                          "_comentario": "multa de rescisão = fator_multa × valor por corrida × corridas restantes"},
            "regulamento": REGULAMENTO,
            "desenvolvimento_inicial": {
                "chassis": {"custo_por_ponto": 120000, "atributo_base": 35, "atributo_maximo": 85},
                "motor": {"custo_por_ponto": 260000, "atributo_base": 40, "atributo_maximo": 85}
            },
            "desenvolvimento": {
                "perda_manutencao": 0.30,
                "chassis": {"custo_por_ponto": 20000, "limite_custo_fixo": 55, "escala_progressiva": 9},
                "motor": {"custo_por_ponto": 80000, "limite_custo_fixo": 55, "escala_progressiva": 9},
                        "_comentario": "custo de +1 ponto = custo_por_ponto até limite_custo_fixo; acima disso é multiplicado "
                               "por 1 + ((valor - limite) / escala_progressiva)^2. Próxima temporada: OU manutenção "
                               "(carro atual com perda_manutencao em cada atributo, sem investimento) OU projeto novo "
                               "(parte do zero)."
            },
            "pontuacao": {"posicoes": [25, 18, 15, 12, 10, 8, 6, 4, 2, 1], "volta_mais_rapida": 1, "pole": 0,
                          "corrida_interrompida": CORRIDA_INTERROMPIDA},
            "regras_pitstop": {"obrigatorio": True, "paradas_minimas": 1, "reabastecimento": False,
                               "troca_de_pneus": True,
                               "segundos_por_volta_de_combustivel": 0.0},
            "pneus": dict(PNEUS, compostos_disponiveis=["super_macio", "macio", "medio", "duro", "muito_duro",
                                                         "chuva_leve", "chuva_pesada"]),
            "clima": CLIMA,
            "formato_teste_coletivo": {"dias": 3, "minutos_por_dia": 240},
            "formato_evento": {
                "treinos_livres": [
                    {"nome": "Treino Livre 1", "limite": "tempo", "valor": 60},
                    {"nome": "Treino Livre 2", "limite": "tempo", "valor": 60},
                    {"nome": "Treino Livre 3", "limite": "voltas", "valor": 20}
                ],
                "classificacao": {"nome": "Classificação", "modelo": "tempo", "fases": [
                    {"nome": "Q1", "limite": "tempo", "valor": 18, "eliminados": 4},
                    {"nome": "Q2", "limite": "tempo", "valor": 15, "eliminados": 4},
                    {"nome": "Q3", "limite": "tempo", "valor": 12, "eliminados": 0}
                ]},
                "corrida": {"nome": "Corrida", "tempo_maximo_min": 120},
                "_comentario": "limite = 'tempo' (minutos) ou 'voltas'. O nº de voltas da corrida fica em cada pista. "
                               "classificacao pode ser um dict ou uma lista de etapas; modelos: tempo (fases com ou "
                               "sem eliminados), grupos, volta_unica, corrida_classificatoria, campeonato. "
                               "Veja docs/DATABASE.md."
            },
            "ponderacao": PONDERACAO,
            "simulacao": simulacao(0.075, 15000, 450000)
        },
        "pilotos": pilotos, "chassis": chassis, "motores": motores, "equipes": equipes,
        "patrocinadores": patro,
        "calendario": calendario(14, 10, 3, [(5, "Teste coletivo de pré-temporada I", 7),
                                             (7, "Teste coletivo de pré-temporada II", 2)], [14, 15])
    }


# =================================================================== FÓRMULA BETA
def formula_beta():
    chassis = [
        {"id": "ch_corsair", "nome": "Corsair C-26", "nacionalidade": "Reino Unido", "equipe": None,
         "atributos": attrs(ATR_C, 72, 5), "contrato": {"valor_por_corrida": 60000, "temporadas": 2}},
        {"id": "ch_marlin", "nome": "Marlin M26", "nacionalidade": "Itália", "equipe": None,
         "atributos": attrs(ATR_C, 68, 5), "contrato": {"valor_por_corrida": 50000, "temporadas": 2}},
        {"id": "ch_tempest", "nome": "Tempest T6", "nacionalidade": "França", "equipe": None,
         "atributos": attrs(ATR_C, 64, 5), "contrato": {"valor_por_corrida": 40000, "temporadas": 1}},
    ]
    motores = [
        {"id": "mot_volta", "nome": "Volta V8 Junior", "nacionalidade": "Itália", "potencia": 74,
         "fabricante": {"tipo": "fabricante"}, "exclusividade": {"exclusivo": False, "equipe": None},
         "contrato": {"valor_por_corrida": 45000, "temporadas": 1}},
        {"id": "mot_takumi", "nome": "Takumi TK-2", "nacionalidade": "Japão", "potencia": 70,
         "fabricante": {"tipo": "fabricante"}, "exclusividade": {"exclusivo": False, "equipe": None},
         "contrato": {"valor_por_corrida": 38000, "temporadas": 1}},
    ]
    eqdef = [("prisma", "Prisma Junior Team", "Brasil", 70, "ch_corsair", "mot_volta"),
             ("halcon", "Halcón Racing", "Espanha", 62, "ch_corsair", "mot_takumi"),
             ("redline", "Redline Motorsport", "Reino Unido", 66, "ch_marlin", "mot_volta"),
             ("orbita", "Órbita Competições", "Brasil", 50, "ch_marlin", "mot_takumi"),
             ("falke", "Falke Junior", "Alemanha", 58, "ch_tempest", "mot_volta"),
             ("sakura", "Sakura Speed", "Japão", 55, "ch_marlin", "mot_takumi"),
             ("liberty", "Liberty Racing", "Estados Unidos", 45, "ch_tempest", "mot_takumi"),
             ("pampas", "Pampas Motorsport", "Argentina", 40, "ch_tempest", "mot_volta"),
             ("fjord", "Fjord Racing", "Finlândia", 35, "ch_tempest", "mot_takumi")]
    equipes, pilotos = [], []
    nacs = list(NOMES.keys())
    pn = 1
    for (eid, nome, nac, rec, ch, mo) in eqdef:
        ativa = eid != "fjord"
        cht = next(c for c in chassis if c["id"] == ch)
        mot = next(m for m in motores if m["id"] == mo)
        equipes.append({"id": eid, "nome": nome, "ativa": ativa, "nacionalidade": nac, "recursos": rec,
                        "cor": CORES[eid][0], "cor_secundaria": CORES[eid][1], "caixa": None,
                        "chassis": {"id": ch, "origem": "terceiros",
                                    "contrato": {"valor_por_corrida": cht["contrato"]["valor_por_corrida"],
                                                 "temporadas": rng.choice([1, 2])}},
                        "motor": {"id": mo, "origem": "fabricante",
                                  "contrato": {"valor_por_corrida": mot["contrato"]["valor_por_corrida"],
                                               "temporadas": 1}},
                        "prob_fechamento": round((100 - rec) / 3000, 3), "prob_surgimento": 0.0 if ativa else 0.2})
        if not ativa:
            continue
        for k in range(2):
            media = rng.randint(48, 66)
            pilotos.append(piloto(f"p{pn:03d}", nac if rng.random() < 0.4 else rng.choice(nacs), media,
                                  rng.randint(17, 23),
                                  {"equipe": eid, "valor_por_corrida": r100(4000 + (media - 45) * 600, 500),
                                   "temporadas": rng.choice([1, 2]), "situacao": "principal"}))
            pn += 1
    for k in range(7):
        pilotos.append(piloto(f"p{pn:03d}", rng.choice(nacs), rng.randint(45, 62), rng.randint(17, 22), None))
        pn += 1
    patro = patrocinadores(equipes, 4000000, 10, livres=3, inativos=2)

    return {
        "versao_formato": 1,
        "categoria": {
            "id": "formula_beta", "nome": "Fórmula Beta", "ano": 2026, "moeda": "USD",
            "regras": {
                "pilotos_de_teste": False,
                "pilotos_principais_por_equipe": 2,
                "pilotos_de_teste_por_equipe": 0,
                "desenvolvimento_chassis_por_equipe": False,
                "desenvolvimento_motor_por_equipe": False,
                "equipes_com_desenvolvimento_de_motor": [],
                "fontes_de_motor_permitidas": ["fabricante"],
                "testes_coletivos": False,
                "orcamento_medio": 4000000,
                "inflacao_media_anual": 0.025,
                "patrocinios": True,
                "renda_tv": {"ativa": True, "valor_medio_por_equipe": 1000000,
                             "fator_por_posicao_campeonato": [1.3, 1.2, 1.1, 1.0, 1.0, 0.9, 0.8, 0.7]},
                "clientes_por_chassis": 2,
                "importancia_carro": 0.4,
                "importancia_piloto": 0.6,
                "idade_pilotos": {"idade_maxima": None, "preferida_ate": 22, "penalidade_por_ano": 4, "_comentario": "idade_maxima: acima dela a categoria não contrata e o contrato termina na virada de temporada (vazio = sem limite). preferida_ate / penalidade_por_ano: na escolha das equipes do PC, cada ano acima da idade preferida tira esses pontos da nota do piloto (categorias de base preferem pilotos jovens)."},
                "bandeira_vermelha": BANDEIRA_VERMELHA,
                "batida_grave": BATIDA_GRAVE
            },
            "tier": 2,
            "mobilidade": MOBILIDADE,
            "carreira": CARREIRA,
            "mercado_patrocinio": MERCADO_PATROCINIO,
            "financas": {"reserva_minima": 0.15, "uso_do_excedente": 0.5, "juros_anual": 0.08,
                         "limite_emprestimo": 0.5, "prazo_temporadas": 3, "semanas_para_falencia": 8,
                         "_comentario": "reserva_minima e limite_emprestimo são frações do orçamento médio; o limite "
                                        "é multiplicado por (0,5 + recursos/100) da equipe."},
            "contratos": {"fator_multa": 0.5,
                          "_comentario": "multa de rescisão = fator_multa × valor por corrida × corridas restantes"},
            "regulamento": REGULAMENTO,
            "desenvolvimento_inicial": None,
            "desenvolvimento": None,
            "pontuacao": {"posicoes": [20, 15, 12, 10, 8, 6, 4, 3, 2, 1], "volta_mais_rapida": 0, "pole": 2,
                          "corrida_interrompida": CORRIDA_INTERROMPIDA},
            "regras_pitstop": {"obrigatorio": False, "paradas_minimas": 0, "reabastecimento": True,
                               "troca_de_pneus": True,
                               "segundos_por_volta_de_combustivel": 0.4},
            "pneus": dict(PNEUS, compostos_disponiveis=["macio", "duro", "chuva_leve", "chuva_pesada"]),
            "clima": CLIMA,
            "formato_evento": {
                "treinos_livres": [{"nome": "Treino Livre", "limite": "voltas", "valor": 25}],
                "classificacao": {"nome": "Classificação", "modelo": "tempo", "fases": [
                    {"nome": "Sessão única", "limite": "tempo", "valor": 30, "eliminados": 0}]},
                "corrida": {"nome": "Corrida", "tempo_maximo_min": 60}
            },
            "ponderacao": PONDERACAO,
            "simulacao": simulacao(0.06, 3000, 25000)
        },
        "pilotos": pilotos, "chassis": chassis, "motores": motores, "equipes": equipes,
        "patrocinadores": patro,
        "calendario": [dict(e, voltas_corrida=max(20, e["voltas_corrida"] // 2) if e["voltas_corrida"] else 0)
                       for e in calendario(10, 12, 4, [], [11])]
    }


for nome, fn in (("formula_alfa_2026.json", formula_alfa), ("formula_beta_2026.json", formula_beta)):
    # nomes únicos entre as categorias (evita homônimos)
    with open(os.path.join(OUT, nome), "w", encoding="utf-8") as f:
        json.dump(fn(), f, ensure_ascii=False, indent=2)
    print("ok", nome)
