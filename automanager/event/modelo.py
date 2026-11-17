"""Modelo do tempo de volta, desgaste, incidentes e acerto.

tempo = tempo_base(sessão)
        x clima x rating aerodinâmico/chassis x rating de motor (com desgaste do motor) x rating do piloto
        x acerto (por componente) x pneu (composto, clima, desgaste) x combustível x ordens
        x evolução da pista x aprendizado x fadiga x forma do fim de semana x chuva (cúbico) x dano x lastro
        x dispersão (só piora: depende da consistência) (x erro ocasional)

A dispersão é unilateral: a volta ideal do piloto é o piso e a falta de consistência só acrescenta tempo,
como no modelo de referência cf.dc·(1,5 − 0,316·√cons)·Rnd() (consistência em 0-20 = atributo/5).

Os ratings de chassis, motor e piloto são calculados para a sessão, a pista e o
clima atuais (ponderação da matriz do JSON da categoria), portanto não são estáticos.
"""
import math

from .. import ratings
from ..util import clamp
from .clima import PNEU_IDEAL

PARAMETROS_ACERTO = ("aerodinamica", "cambio", "suspensao", "freios")
NOMES_ACERTO = {"aerodinamica": "Aerodinâmica (asa)", "cambio": "Relação de câmbio",
                "suspensao": "Suspensão", "freios": "Freios"}
DICAS_ACERTO = {"aerodinamica": ("menos asa", "mais asa"), "cambio": ("relação mais curta", "relação mais longa"),
                "suspensao": ("suspensão mais macia", "suspensão mais dura"),
                "freios": ("freios menos agressivos", "freios mais agressivos")}
ORDENS = ("agressividade", "uso_motor", "uso_carro")
NOMES_ORDENS = {"agressividade": "Agressividade", "uso_motor": "Uso do motor", "uso_carro": "Uso do carro"}


class Carro:
    """Um piloto + carro inscrito no evento. Persistente entre as sessões do evento."""
    # padrões para eventos salvos antes destes campos existirem
    logo_chassis = logo_motor = nacionalidade_chassis = nacionalidade_motor = None
    plano_fixo = None                    # stints definidos pelo jogador (multijogador)
    feedback = None                      # último comentário do piloto sobre o acerto (painel da tela do evento)
    forma = 0.0                          # forma do fim de semana (fração de tempo; + = mais lento)
    dano = 0.0                           # dano persistente (fração de tempo por volta) até o reparo no box
    lastro = 0.0                         # kg de lastro de sucesso
    uso_motor = 0.0                      # voltas do motor em uso (no início do evento + as do evento)
    voltas_evento = 0                    # voltas dadas no evento (todas as sessões)
    penalidade_grid = 0                  # posições perdidas no grid (motor além da cota)
    ritmo = None                         # tempo de volta esperado nesta volta (sem dispersão nem erro)

    def __init__(self, piloto, equipe, chassis, motor, usuario=False):
        self.piloto = piloto
        self.equipe = equipe
        self.chassis = chassis["atributos"] if chassis else {}
        self.nome_chassis = chassis["nome"] if chassis else "-"
        self.potencia = motor["potencia"] if motor else 0
        self.nome_motor = motor["nome"] if motor else "-"
        self.logo_chassis = (chassis or {}).get("logotipo")
        self.logo_motor = (motor or {}).get("logotipo")
        self.nacionalidade_chassis = (chassis or {}).get("nacionalidade")
        self.nacionalidade_motor = (motor or {}).get("nacionalidade")
        self.usuario = usuario
        self.conhecimento = 0.0          # aprendizado do piloto ao longo do evento (0..1)
        self.acerto = {k: 50 for k in PARAMETROS_ACERTO}
        self.ordens = {k: 0 for k in ORDENS}
        self.pneu_inicial = None
        self.combustivel_inicial = None
        self.estrategia_auto = True
        self.chamado_box = None          # composto pedido pelo usuário
        self._cache = {}
        self.resetar_sessao()

    @property
    def nome(self):
        return self.piloto["nome"]

    @property
    def id(self):
        return self.piloto["id"]

    def atr(self, k):
        return self.piloto["atributos"].get(k, 50)

    def resetar_sessao(self):
        self.pneu = None
        self.desgaste = 0.0               # % da vida útil do pneu usada (100% = início do cliff)
        self.uso_pneu = 0.0               # voltas "efetivas" do jogo de pneus
        self.idade_pneu = 0               # voltas reais do jogo de pneus
        self.plano_corrida = []           # estratégia: [[composto, voltas], ...]
        self.combustivel = 0.0
        self.voltas = 0
        self.tempo_total = 0.0
        self.melhor = None
        self.ultima = None
        self.melhor_fase = None
        self.status = "garagem"          # garagem | pista | box | abandono | eliminado | fim
        self.motivo = ""
        self.paradas = 0
        self.compostos_usados = set()
        self.ultimo_pit_volta = False
        self.posicao = None
        self.plano = []                  # voltas restantes do run (treino/classificação)
        self.chamado_box = None
        self.dano = 0.0


# ---------------------------------------------------------------------------- acerto
def acerto_ideal(pista, clima_estado):
    perfil = ratings.perfil_pista(pista)
    r, ca, cb = perfil["retas"], perfil["curvas_alta"], perfil["curvas_baixa"]
    dif = pista.get("dificuldade", 50) / 100
    rua = 1.0 if pista.get("tipo_pista") == "rua" else 0.0
    ideal = {
        "aerodinamica": 15 + 80 * (0.9 * ca + cb),
        "cambio": 20 + 70 * (r + 0.4 * ca),
        "suspensao": 30 + 50 * ca + 20 * (1 - dif) - 25 * rua,
        "freios": 20 + 70 * cb,
    }
    if clima_estado != "seco":
        chuva = 1.0 if clima_estado == "chuva_pesada" else 0.6
        ideal["aerodinamica"] += 18 * chuva
        ideal["suspensao"] -= 18 * chuva
        ideal["freios"] -= 10 * chuva
    return {k: clamp(v, 0, 100) for k, v in ideal.items()}


def pesos_acerto(pista):
    """Quanto cada parâmetro do acerto pesa nesta pista (média 1): asa nas curvas de alta, câmbio nas retas,
    suspensão e freios nas curvas de baixa (freios também nas freadas do fim das retas)."""
    p = ratings.perfil_pista(pista)
    r, ca, cb = p["retas"], p["curvas_alta"], p["curvas_baixa"]
    w = {"aerodinamica": 0.25 + ca + 0.4 * cb, "cambio": 0.25 + r + 0.3 * ca,
         "suspensao": 0.25 + cb + 0.4 * ca, "freios": 0.25 + cb + 0.4 * r}
    tot = sum(w.values())
    return {k: 4 * v / tot for k, v in w.items()}


def distancia_acerto(acerto, ideal, pesos=None):
    pesos = pesos or {k: 1.0 for k in PARAMETROS_ACERTO}
    return math.sqrt(sum(pesos[k] * (acerto[k] - ideal[k]) ** 2 for k in PARAMETROS_ACERTO)
                     / len(PARAMETROS_ACERTO)) / 100


def multiplicador_acerto(carro, ideal, sim, pesos=None):
    """Distância ao acerto ideal (cada parâmetro pesando conforme a pista) piora o tempo; o atributo 'acerto do
    carro' reduz essa piora. Limitado por `penalidade_maxima_acerto` para não gerar voltas irreais."""
    d = distancia_acerto(carro.acerto, ideal, pesos)
    reducao = sim.get("reducao_maxima_acerto_piloto", 0.6) * carro.atr("acerto_carro") / 100
    efetiva = d * (1 - reducao) * (1 - 0.3 * carro.conhecimento)
    return 1 + sim.get("penalidade_maxima_acerto", 0.018) * min(1.0, efetiva / 0.45) ** 1.5


def acerto_ia(carro, pista, clima_estado, rng):
    """Equipes do PC acertam o carro com erro que diminui com recursos, piloto e aprendizado."""
    ideal = acerto_ideal(pista, clima_estado)
    sigma = 28 * (1 - 0.5 * carro.equipe.get("recursos", 50) / 100) * (1 - 0.5 * carro.atr("acerto_carro") / 100)
    sigma *= (1 - 0.6 * carro.conhecimento)
    return {k: int(clamp(ideal[k] + rng.gauss(0, sigma), 0, 100)) for k in PARAMETROS_ACERTO}


def avaliar_acerto(carro, ideal, rng):
    """Leitura do piloto sobre cada parâmetro: quanto falta (+) ou sobra (−) para o ideal, com o erro de
    leitura dele – a precisão depende do atributo 'acerto do carro' e do conhecimento da pista."""
    ruido = 22 * (1 - carro.atr("acerto_carro") / 100) * (1 - 0.4 * carro.conhecimento)
    return {k: ideal[k] - carro.acerto[k] + rng.gauss(0, ruido) for k in PARAMETROS_ACERTO}


def texto_feedback(diffs):
    partes = []
    for k in PARAMETROS_ACERTO:
        diff = diffs[k]
        if abs(diff) < 7:
            continue
        intens = "bem " if abs(diff) > 22 else "um pouco " if abs(diff) < 13 else ""
        partes.append(f"{intens}{DICAS_ACERTO[k][1 if diff > 0 else 0]}")
    return ("pede " + ", ".join(partes)) if partes else "está satisfeito com o acerto"


def nota_acerto(diffs):
    """Nota do piloto para o acerto como um todo: 1 a 5 estrelas (pela leitura dele, não pelo valor real)."""
    media = sum(abs(d) for d in diffs.values()) / max(1, len(diffs))
    return max(1, min(5, round(5 * max(0.0, 1 - media / 30))))


def feedback_acerto(carro, ideal, rng):
    """Comentário do piloto sobre o acerto. Precisão depende do atributo 'acerto do carro'."""
    return texto_feedback(avaliar_acerto(carro, ideal, rng))


# ---------------------------------------------------------------------------- pneus
def tipo_pneu(categoria, composto):
    return categoria["pneus"]["compostos"][composto]["tipo"]


def fator_desgaste(carro, categoria, pista, clima_estado, composto=None, fator=1.0):
    """Multiplicador da degradação (e divisor da vida) do pneu nesta volta.

    Considera a pista (desgaste), o carro (atributo 'pneus' do chassis), o piloto (consistência), as
    ordens (agressividade e uso do carro, amplificadas pela sensibilidade térmica do composto) e o
    superaquecimento de pneu de chuva em pista seca."""
    comp = categoria["pneus"]["compostos"][composto or carro.pneu]
    so = categoria["simulacao"]["ordens"]
    f = (max(5, pista.get("desgaste_pneus", 50)) / 50) ** 1.2
    f *= 1.3 - 0.6 * carro.chassis.get("pneus", 50) / 100
    f *= 1.15 - 0.3 * carro.atr("consistencia") / 100
    termico = comp.get("sensibilidade_termica", 1.0)
    f *= max(0.5, 1 + termico * (so["agressividade_desgaste"] * carro.ordens["agressividade"]
                                 + so["uso_carro_desgaste"] * carro.ordens["uso_carro"]))
    if comp["tipo"] != "seco" and clima_estado == "seco":
        f *= 3.0
    f *= 1 + carro.lastro / 500                       # lastro gasta mais pneu
    return max(0.1, f * fator)


def desgaste_por_volta(carro, categoria, pista, clima_estado):
    """Uso efetivo do pneu nesta volta (1 = uma volta em condições de referência)."""
    return fator_desgaste(carro, categoria, pista, clima_estado)


def registrar_volta_pneu(carro, categoria, pista, clima_estado, fator=1.0):
    """fator < 1 = ritmo reduzido (safety car)."""
    comp = categoria["pneus"]["compostos"][carro.pneu]
    carro.uso_pneu += desgaste_por_volta(carro, categoria, pista, clima_estado) * fator
    carro.idade_pneu += 1
    carro.desgaste = 100 * carro.uso_pneu / max(1, comp.get("vida", 20))


def trocar_pneu(carro, composto):
    carro.pneu = composto
    carro.uso_pneu = 0.0
    carro.idade_pneu = 0
    carro.desgaste = 0.0


def vida_pneu(carro, categoria, pista, clima_estado, composto, limite=100):
    """Voltas até o pneu chegar a `limite`% da vida (100% = início do cliff)."""
    comp = categoria["pneus"]["compostos"][composto]
    return comp.get("vida", 20) / fator_desgaste(carro, categoria, pista, clima_estado, composto) * limite / 100


def multiplicador_pneu(categoria, composto, clima_estado, uso, idade):
    """Efeito do pneu no tempo de volta: ritmo do composto x adequação ao clima x aquecimento x
    degradação linear x cliff (queda brusca depois da vida útil)."""
    pn = categoria["pneus"]
    comp = pn["compostos"][composto]
    m = comp["ritmo"] * pn["adequacao_clima"][clima_estado][comp["tipo"]]
    n_aq = comp.get("aquecimento_voltas", 1)
    if idade < n_aq:
        m *= 1 + pn.get("penalidade_aquecimento", 0.008) * (n_aq - idade) / n_aq
    m *= 1 + comp.get("degradacao", 0.0006) * uso
    alem = uso - comp.get("vida", 20)
    if alem > 0:
        m *= 1 + comp.get("cliff", 0.004) * alem ** 1.5
    return m


# ---------------------------------------------------------------------------- tempo de volta
class ModeloVolta:
    def __init__(self, categoria, pista, rng):
        self.cat = categoria
        self.pista = pista
        self.rng = rng
        self.sim = categoria["simulacao"]
        self.regras = categoria["regras"]
        self.pond = categoria["ponderacao"]
        perfil = ratings.perfil_pista(pista)
        self.perfil = perfil
        dif = pista.get("dificuldade", 50) / 100
        # proporção retas x curvas impacta a diferença possível entre os carros (spread); a dificuldade da
        # pista (e ser de rua) amplia sobretudo a diferença entre os pilotos – (0,85 + 0,03·diff) da referência
        base = self.sim["amplitude_desempenho"] * (0.75 + 0.5 * (perfil["curvas_alta"] + perfil["curvas_baixa"]))
        self.spread = base
        self.spread_piloto = base * (0.8 + 0.4 * dif) * (1.1 if pista.get("tipo_pista") == "rua" else 1.0)
        self.part_motor = ratings.participacao_motor(pista, self.pond)
        self.pesos_acerto = pesos_acerto(pista)

    def ratings(self, carro, sessao, clima):
        chave = (sessao, clima.estado)
        if chave not in carro._cache:
            pc = self.pond["peso_caracteristicas"]
            carro._cache[chave] = (
                ratings.nota(carro.chassis, self.pond["chassis"], self.pista, sessao, clima.intensidade, pc),
                carro.potencia,
                ratings.nota(carro.piloto["atributos"], self.pond["piloto"], self.pista, sessao, clima.intensidade, pc),
            )
        return carro._cache[chave]

    def tempo_base(self, sessao):
        return self.pista["tempo_base_corrida" if sessao == "corrida" else "tempo_base_treino"]

    def ritmo(self, carro, sessao, clima, evolucao=0.0, progresso_corrida=0.0):
        """Tempo de volta esperado (sem dispersão nem erro): a 'volta ideal' do piloto nesta situação."""
        ef = clima.efeitos
        nota_ch, pot, nota_p = self.ratings(carro, sessao, clima)
        o = carro.ordens
        so = self.sim["ordens"]
        cw = self.regras["importancia_carro"]
        dw = self.regras["importancia_piloto"]
        es = self.part_motor
        # motor gasto perde potência (até `perda_potencia_motor` pontos no fim da vida útil)
        vida = self.sim.get("vida_motor_voltas", 0) or 0
        perda_motor = self.sim.get("perda_potencia_motor", 3.0) * min(1.5, carro.uso_motor / vida) if vida else 0.0
        pot_ef = clamp(pot + 3 * o["uso_motor"] - perda_motor, 0, 100)

        m_aero = 1 + self.spread * cw * (1 - es) * ef["peso_chassis"] * (0.5 - nota_ch / 100)
        m_motor = 1 + self.spread * cw * es * ef["peso_motor"] * (0.5 - pot_ef / 100)
        m_piloto = 1 + self.spread_piloto * dw * ef["peso_piloto"] * (0.5 - nota_p / 100)

        ideal = acerto_ideal(self.pista, clima.estado)
        m_acerto = multiplicador_acerto(carro, ideal, self.sim, self.pesos_acerto)

        m_pneu = multiplicador_pneu(self.cat, carro.pneu, clima.estado, carro.uso_pneu, carro.idade_pneu)

        m_comb = 1 + self.sim.get("efeito_combustivel_por_volta", 0.0005) * max(0.0, carro.combustivel)
        m_ordens = 1 - so["agressividade_tempo"] * o["agressividade"] \
            - so["uso_motor_tempo"] * o["uso_motor"] * (0.5 + es) - so["uso_carro_tempo"] * o["uso_carro"]
        m_evo = 1 + self.sim.get("evolucao_pista", 0.012) * (1 - evolucao)
        m_aprend = 1 + 0.004 * (1 - carro.conhecimento)
        m_fadiga = 1 + 0.004 * (1 - carro.atr("fisico") / 100) * progresso_corrida
        m_forma = 1 + carro.forma
        # chuva: penalidade cúbica para a combinação piloto + carro ruim no molhado
        m_chuva = 1.0
        if clima.estado != "seco":
            w = 1.0 if clima.estado == "chuva_pesada" else 0.6
            q = 0.6 * carro.atr("chuva") / 100 + 0.4 * carro.chassis.get("chuva", 50) / 100
            m_chuva = 1 + self.sim.get("penalidade_chuva", 0.0035) * ((1 + w * (1 - q)) ** 3 - 1)
        m_dano = 1 + carro.dano
        m_lastro = 1 + self.regras.get("lastro_tempo_por_kg", 0.00007) * carro.lastro
        return self.tempo_base(sessao) * ef["tempo"] * m_aero * m_motor * m_piloto * m_acerto * m_pneu \
            * m_comb * m_ordens * m_evo * m_aprend * m_fadiga * m_forma * m_chuva * m_dano * m_lastro

    def dispersao(self, carro, clima):
        """Fração aleatória que só piora a volta: k·(1,5 − 0,316·√(consistência/5))·U(0,1), centrada para
        que um piloto de consistência média fique, em média, no tempo de referência."""
        k = self.sim.get("dispersao_consistencia", 0.006) * clima.efeitos["aleatoriedade"]
        escala = max(0.05, 1.5 - 0.316 * math.sqrt(max(0.0, carro.atr("consistencia")) / 5))
        return k * (escala * self.rng.random() - 0.2)

    def volta(self, carro, sessao, clima, evolucao=0.0, progresso_corrida=0.0, tipo_volta="rapida"):
        """Retorna (tempo, detalhes). evolucao: 0 (pista 'verde') .. 1 (pista emborrachada)."""
        o = carro.ordens
        ef = clima.efeitos
        base = self.ritmo(carro, sessao, clima, evolucao, progresso_corrida)
        carro.ritmo = base
        m_rand = 1 + self.dispersao(carro, clima)
        erro = False
        p_erro = self.sim.get("taxa_erro_volta", 0.03) * (1.5 - carro.atr("concentracao") / 100) \
            * math.sqrt(ef["acidentes"]) * (1 + 0.3 * o["agressividade"])
        if sessao == "classificacao":
            p_erro *= self.sim.get("fator_erro_classificacao", 0.5)
        m_erro = 1.0
        if self.rng.random() < max(0.0, p_erro):
            erro = True
            m_erro = 1 + self.rng.uniform(0.008, 0.035)
        t = base * m_rand * m_erro
        if tipo_volta == "saida":
            t *= 1.25
        elif tipo_volta == "entrada":
            t *= 1.18
        return t, {"erro": erro}

    # ------------------------------------------------------------------ incidentes
    def incidente(self, carro, clima):
        """None | ('acidente'|'quebra', grave: bool). Aleatório, mas tendendo aos atributos."""
        o = carro.ordens
        so = self.sim["ordens"]
        ef = clima.efeitos
        conf = carro.chassis.get("confiabilidade", 50)
        vida = self.sim.get("vida_motor_voltas", 0) or 0
        gasto = 1 + 2 * min(2.0, carro.uso_motor / vida) ** 2 if vida else 1.0      # motor velho quebra mais
        p_q = self.sim["taxa_quebra_base"] * (1.6 - conf / 100) ** 2 * gasto \
            * max(0.2, 1 + so["uso_motor_quebra"] * o["uso_motor"]) * max(0.2, 1 + so["uso_carro_quebra"] * o["uso_carro"])
        if self.rng.random() < p_q:
            return ("quebra", self.rng.random() < 0.75)
        tipo_ok = tipo_pneu(self.cat, carro.pneu) == PNEU_IDEAL[clima.estado]
        p_a = self.sim["taxa_acidente_base"] * (0.5 + self.pista.get("dificuldade", 50) / 100) \
            * (1.6 - carro.atr("concentracao") / 100) * (1.3 - 0.6 * carro.atr("conducao") / 100) \
            * ef["acidentes"] * max(0.2, 1 + so["agressividade_risco"] * o["agressividade"]) \
            * (1.0 if tipo_ok else 2.5) * (1 + max(0.0, carro.desgaste - 100) / 10)
        if self.rng.random() < p_a:
            return ("acidente", self.rng.random() < 0.45)
        return None

    def nota_largada(self, carro):
        return (0.65 * carro.atr("largada") + 0.35 * carro.atr("aceleracao")) / 100
