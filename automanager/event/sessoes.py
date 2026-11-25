"""Evento e sessões: treinos livres, classificação (vários modelos) e corrida.

Todas as sessões expõem a mesma interface para a tela:
  iniciar(), avancar(segundos) / avancar_volta(), simular_ate_o_fim(),
  terminada, linhas_classificacao(), log (lista de mensagens), descricao_progresso()

Modelos de classificação (`formato_evento.classificacao`, um dict ou uma lista de etapas):
  "tempo"                    sessão(ões) cronometrada(s) por tempo ou voltas; com ou sem eliminação
  "grupos"                   pilotos divididos em grupos; grid intercalado entre os grupos
  "volta_unica"              cada piloto sai sozinho; vale a melhor volta ou a média de N voltas
  "corrida_classificatoria"  bateria curta; a ordem de chegada forma o grid
  "campeonato"               grid pela classificação do campeonato (ou invertida)
A corrida aceita `grid_invertido_top`: inverte os N primeiros do grid.
"""
import heapq
import math
import itertools
import random

from .clima import Clima, NOMES as NOMES_CLIMA, PNEU_IDEAL
from .modelo import (Carro, ModeloVolta, acerto_ia, acerto_ideal, avaliar_acerto, texto_feedback, nota_acerto,
                     tipo_pneu, vida_pneu,
                     fator_desgaste, multiplicador_pneu, registrar_volta_pneu, trocar_pneu)
from ..util import clamp, tempo_volta, relogio

MAX_PARADAS_PLANO = 3


# ============================================================================ evento
class Evento:
    voltas_pista = 0.0          # voltas dadas na pista por todos (emborrachamento); padrão p/ eventos salvos
    notas = ()                  # avisos do fim de semana (motor novo, punições) mostrados na 1ª sessão
    vitimas = ()                # padrão p/ eventos salvos antes das batidas graves

    def __init__(self, categoria, pista, inscritos, rng=None, ordem_campeonato=None):
        """inscritos: lista de dicts {piloto, equipe, chassis, motor, usuario}.
        ordem_campeonato: ids dos pilotos na ordem do campeonato (para grids/ordens de saída)."""
        self.cat = categoria
        self.pista = pista
        self.rng = rng or random.Random()
        self.clima = Clima(categoria["clima"], pista.get("prob_chuva", 0.2), self.rng)
        self.modelo = ModeloVolta(categoria, pista, self.rng)
        self.carros = [Carro(i["piloto"], i["equipe"], i.get("chassis"), i.get("motor"), i.get("usuario", False))
                       for i in inscritos]
        self.ordem_campeonato = list(ordem_campeonato or [])
        self.programacao = montar_programacao(categoria)
        self.indice = -1
        self.sessao = None
        self.grid = None             # lista de carros na ordem do grid
        self.pole = None
        self.resultado_corrida = None
        self.historico_sessoes = []  # resumo de cada sessão cronometrada encerrada
        self.voltas_pista = 0.0
        self.notas = []
        self.vitimas = []            # batidas graves: [{"piloto", "tipo": "lesao"|"morte", "evento"}]
        self._preparar_carros()

    # ---------------------------------------------------------------- fim de semana
    def _preparar_carros(self):
        """Forma do fim de semana, lastro de sucesso e motor (vida útil / cota por temporada)."""
        sim, regras = self.cat["simulacao"], self.cat["regras"]
        pos = {pid: i for i, pid in enumerate(self.ordem_campeonato)}
        lastros = regras.get("lastro_por_posicao") or []
        vida = sim.get("vida_motor_voltas", 700) or 0
        cota = regras.get("motores_por_temporada")
        for c in self.carros:
            p = c.piloto
            # forma: muda devagar de um evento para o outro; pilotos consistentes e concentrados variam menos
            sigma = sim.get("forma_sigma", 0.0015) * (1.3 - 0.3 * (c.atr("consistencia") + c.atr("concentracao")) / 200)
            f = 0.6 * p.get("forma", 0.0) + self.rng.gauss(0, sigma)
            f = clamp(f, -3 * sigma, 3 * sigma)
            p["forma"] = round(f, 6)
            c.forma = f
            i = pos.get(c.id)
            c.lastro = float(lastros[i]) if i is not None and i < len(lastros) else 0.0
            if vida:
                reg = c.equipe.setdefault("motores", {}).setdefault(c.id, {"uso": 0.0, "usados": 1})
                if reg["uso"] >= 0.9 * vida:
                    reg["uso"] = 0.0
                    reg["usados"] += 1
                    if cota and reg["usados"] > cota:
                        c.penalidade_grid = int(regras.get("penalidade_motor_grid", 10))
                        self.notas.append(f"{c.nome} usa o motor nº {reg['usados']} (cota de {cota}): larga "
                                          f"{c.penalidade_grid} posições atrás.")
                    else:
                        self.notas.append(f"{c.nome} estreia um motor novo (nº {reg['usados']}).")
                c.uso_motor = reg["uso"]

    def gravar_uso_motor(self):
        """Ao fim do evento: a quilometragem do motor de cada carro volta para a equipe."""
        for c in self.carros:
            reg = c.equipe.get("motores", {}).get(c.id)
            if reg is not None:
                reg["uso"] = round(c.uso_motor, 1)

    def evolucao(self):
        """0 (pista verde) .. 1 (emborrachada), pelas voltas dadas por todos no fim de semana."""
        import math
        ref = max(1, len(self.carros)) * self.cat["simulacao"].get("voltas_emborrachamento", 15)
        return 1 - math.exp(-self.voltas_pista / ref)

    def lavar_pista(self, fator):
        """Chuva leva embora parte da borracha."""
        self.voltas_pista *= fator

    def contar_volta(self, c):
        self.voltas_pista += 1

    OVAL_PADRAO = {"vacuo": 0.012, "alcance_vacuo_s": 1.5, "retas_pelotao": [0.5, 0.75], "piso_ultrapassagem_pelotao": 0.4,
                   "custo_disputa_pelotao": 0.3, "multiplicador_batida_pelotao": 6.0, "carros_max_pelotao": 12,
                   "prob_amarela_acidente": 0.9, "prob_amarela_quebra": 0.35, "amarelas_detritos_por_corrida": 6.0,
                   "colisao_oval_curto": 2.5, "efeito_largada": 0.3, "voltas_amarela": [4, 7],
                   "compressao_pelotao": 0.6, "tentativas_relargada": 3, "piso_relargada": 0.6,
                   "alcance_relargada_s": 0.8, "respeitar_tempo_maximo": False,
                   "amarelas_oval_curto": 2.0, "ultrapassagem_oval_curto": 0.7}

    def perfil_oval(self):
        """None fora de oval. Num oval: {'pelotao': 0..1, 'curto': 0..1, **parâmetros}. Pelotão (pack racing)
        cresce com as retas (superspeedway); 'curto' com as curvas lentas (short track: 50% de curvas de baixa =
        oval curto pleno); o intermediário fica entre os dois. Parâmetros em simulacao.oval."""
        if not self.oval():
            return None
        cfg = dict(self.OVAL_PADRAO, **(self.cat["simulacao"].get("oval") or {}))
        perfil = self.modelo.perfil
        lo, hi = cfg["retas_pelotao"]
        cfg["pelotao"] = clamp((perfil["retas"] - lo) / max(0.01, hi - lo), 0.0, 1.0)
        # só as curvas lentas: um intermediário com menos de 50% de retas (curvas de alta) não vira oval curto
        cfg["curto"] = clamp(perfil["curvas_baixa"] / 0.5, 0.0, 1.0)
        return cfg

    def oval(self):
        """Oval não admite chuva (risco de acidente alto demais): com chuva, bandeira vermelha até secar."""
        return self.pista.get("tipo_pista") == "oval"

    def regras_batida(self):
        from .. import saude
        return saude.cfg(self.cat)

    def registrar_batida(self, envolvidos, msg):
        """Sorteia lesões e mortes dos envolvidos numa batida grave. Vítimas ficam fora do resto do evento."""
        from .. import saude
        for c, tipo in saude.sortear_vitimas(self.cat, envolvidos, self.rng):
            if not tipo:
                continue
            c.fora_do_evento = tipo
            self.vitimas.append({"piloto": c.id, "tipo": tipo, "evento": self.pista.get("nome", ""),
                                 "evento_id": self.pista.get("id")})
            msg(f"{c.nome} é levado ao centro médico e não volta mais no fim de semana." if tipo == "lesao"
                else f"{c.nome} não resiste aos ferimentos.")

    def regras_bandeira_vermelha(self):
        """regras.bandeira_vermelha: relogio_durante_suspensao ('parado' = a sessão não perde tempo de pista;
        'corre' = o tempo de espera conta), limite_espera_sessao_min e limite_espera_corrida_min (passou do
        limite sem secar: a sessão/corrida é encerrada; vazio ou 0 = sem limite)."""
        rb = self.cat["regras"].get("bandeira_vermelha") or {}
        return {"corre": rb.get("relogio_durante_suspensao", "parado") == "corre",
                "sessao": rb.get("limite_espera_sessao_min", 60),
                "corrida": rb.get("limite_espera_corrida_min", 120)}

    def esperar_secar(self, limite_min=None):
        """Sessão suspensa: o clima avança de 10 em 10 minutos até a pista secar ou até o limite de espera.
        Retorna (minutos de espera, secou?)."""
        cl = self.clima
        sem_limite = not limite_min
        teto = 24 * 60 if sem_limite else float(limite_min)
        minutos = 0
        while cl.estado != "seco" and minutos < teto:
            minutos += 10
            if cl.estabilidade >= 1 or cl.rng.random() >= cl.estabilidade:
                cl.estado = cl._passo()
        if sem_limite:
            cl.estado = "seco"                 # sem limite e prob_chuva = 1: não secaria nunca, encerra a espera
        for c in self.carros:
            c._cache.clear()
        return minutos, cl.estado == "seco"
        c.voltas_evento += 1
        c.uso_motor += 1

    @property
    def nomes_sessoes(self):
        return [cfg.get("nome", tipo.capitalize()) for tipo, cfg in self.programacao]

    def progresso_evento(self, progresso_sessao):
        """0..1 ao longo do fim de semana (usado na evolução da pista)."""
        n = max(1, len(self.programacao) - 1)
        return clamp((self.indice + progresso_sessao) / n, 0, 1)

    def ordem_por_campeonato(self, invertida=False):
        pos = {pid: i for i, pid in enumerate(self.ordem_campeonato)}
        resto = sorted((c for c in self.carros if c.id not in pos),
                       key=lambda c: -self.modelo.ratings(c, "classificacao", self.clima)[2])
        ordem = sorted((c for c in self.carros if c.id in pos), key=lambda c: pos[c.id]) + resto
        return list(reversed(ordem)) if invertida else ordem

    def proxima_sessao(self):
        if self.indice + 1 >= len(self.programacao):
            return None
        self.indice += 1
        tipo, cfg = self.programacao[self.indice]
        if self.indice > 0:
            self.clima.nova_sessao()
            if self.clima.estado != "seco":
                self.lavar_pista(0.6)
        for c in self.carros:
            c.resetar_sessao()
        if tipo == "corrida":
            if self.grid is None:
                self.grid = sorted(self.carros, key=lambda c: -self.modelo.ratings(c, "classificacao", self.clima)[2])
            self.sessao = SessaoCorrida(self, cfg)
        elif tipo == "corrida_classificatoria":
            self.sessao = SessaoCorrida(self, cfg, classificatoria=True)
        elif tipo == "grid_campeonato":
            self.sessao = SessaoGrid(self, cfg)
        else:
            self.sessao = SessaoCronometrada(self, tipo, cfg)
        if self.oval() and self.clima.estado != "seco" and not isinstance(self.sessao, SessaoGrid):
            rb = self.regras_bandeira_vermelha()
            minutos, secou = self.esperar_secar(rb["corrida" if tipo.startswith("corrida") else "sessao"])
            self.sessao.espera_inicial = minutos * 60.0
            if secou:
                self.sessao.log.append(f"BANDEIRA VERMELHA: chuva no oval. Início adiado em {minutos} min, até a "
                                       f"pista secar.")
            else:
                self.sessao.cancelada_chuva = True
                self.sessao.log.append(f"BANDEIRA VERMELHA: chuva no oval. A chuva não parou em {minutos} min: "
                                       f"sessão cancelada.")
        return self.sessao

    def preparar_ia(self):
        """Acerto, pneu, combustível e estratégia das equipes do PC antes da sessão."""
        s = self.sessao
        for c in self.carros:
            if not c.usuario:
                c.acerto = acerto_ia(c, self.modelo.ideal(c, self.clima.estado), self.rng)
                c.ordens = {"agressividade": 0, "uso_motor": 0, "uso_carro": 0}
            if isinstance(s, SessaoCorrida):
                if not c.usuario:
                    c.plano_corrida = planejar(self, c, s.total_voltas, s.paradas_minimas)
                    c.pneu_inicial = c.plano_corrida[0][0]
                    c.combustivel_inicial = combustivel_inicial(self, c, s.total_voltas)
                elif c.estrategia_auto or not c.plano_corrida:
                    c.plano_corrida = planejar(self, c, s.total_voltas, s.paradas_minimas, primeiro=c.pneu_inicial)
            elif not c.usuario:
                c.pneu_inicial = composto_para_clima(self, c, s.tipo)

    def compostos_disponiveis(self):
        return self.cat["pneus"].get("compostos_disponiveis", list(self.cat["pneus"]["compostos"]))


def montar_programacao(cat):
    fmt = cat["formato_evento"]
    prog = [("treino", tl) for tl in fmt.get("treinos_livres", [])]
    cl = fmt.get("classificacao")
    etapas = cl if isinstance(cl, list) else ([cl] if cl else [])
    for e in etapas:
        modelo = e.get("modelo", "tempo")
        if modelo == "corrida_classificatoria":
            prog.append(("corrida_classificatoria", e))
        elif modelo == "campeonato":
            prog.append(("grid_campeonato", e))
        else:
            prog.append(("classificacao", e))
    if fmt.get("corrida"):
        prog.append(("corrida", fmt["corrida"]))
    return prog


# ============================================================================ estratégia
def compostos_do_tipo(ev, tipo):
    comp = ev.cat["pneus"]["compostos"]
    return [k for k in ev.compostos_disponiveis() if comp[k]["tipo"] == tipo]


def composto_para_clima(ev, carro, sessao):
    tipo = PNEU_IDEAL[ev.clima.estado]
    lista = compostos_do_tipo(ev, tipo) or ev.compostos_disponiveis()
    if tipo != "seco" or sessao == "classificacao":
        return lista[0]                         # chuva: o único; classificação: o mais macio
    return ev.rng.choice(lista[: max(1, len(lista) - 1)])


def _custos_acumulados(ev, carro, composto, voltas, clima):
    """custo[L] = soma dos multiplicadores de tempo de um stint de L voltas com pneu novo."""
    f = fator_desgaste(carro, ev.cat, ev.pista, clima, composto)
    acum, total = [0.0], 0.0
    for a in range(voltas):
        total += multiplicador_pneu(ev.cat, composto, clima, a * f, a)
        acum.append(total)
    return acum


def fator_ultrapassagem_pista(pista, perfil, sim):
    """Facilidade de ultrapassar na pista: cresce com o quadrado da proporção de retas (pista rápida = fácil,
    pista lenta e travada = difícil); pista de rua ainda multiplica por fator_ultrapassagem_rua."""
    ref = sim.get("ultrapassagem_retas_referencia", 0.4) or 0.4
    f = (perfil["retas"] / ref) ** sim.get("ultrapassagem_expoente_retas", 2.0)
    if pista.get("tipo_pista") == "rua":
        f *= sim.get("fator_ultrapassagem_rua", 0.6)
    return clamp(f, 0.03, 3.0)


def regra_dois_compostos(cat):
    return bool(cat["regras_pitstop"].get("dois_compostos_secos"))


def cumpre_dois_compostos(cat, compostos):
    """Corrida seca com a regra ligada: pelo menos 2 compostos secos diferentes. Quem usou pneu de chuva
    (intermediário/chuva) fica dispensado."""
    tipos = [tipo_pneu(cat, k) for k in compostos]
    if any(t != "seco" for t in tipos):
        return True
    return len(set(compostos)) >= 2


def planejar(ev, carro, voltas, paradas_minimas=0, primeiro=None, usados=None):
    """Melhor estratégia pela degradação: compara planos de 0 a 3 paradas e as combinações de
    compostos; o tamanho de cada stint é proporcional à vida do composto. Retorna [[composto, voltas]]."""
    voltas = max(1, int(voltas))
    clima = ev.clima.estado
    tipo = PNEU_IDEAL[clima]
    lista = compostos_do_tipo(ev, tipo) or ev.compostos_disponiveis()
    if primeiro and primeiro not in lista:
        lista = [primeiro] + lista
    if not ev.cat["regras_pitstop"].get("troca_de_pneus", True):
        return [[primeiro or lista[0], voltas]]
    base = ev.pista.get("tempo_base_corrida", 90)
    perda_pit = ev.pista.get("duracao_pitstop", 22) + 1.0
    custos = {k: _custos_acumulados(ev, carro, k, voltas, clima) for k in lista}
    vidas = {k: max(1.0, vida_pneu(carro, ev.cat, ev.pista, clima, k)) for k in lista}
    candidatos = []
    for paradas in range(max(0, paradas_minimas), MAX_PARADAS_PLANO + 1):
        if paradas + 1 > voltas:
            break
        for combo in itertools.product(lista, repeat=paradas + 1):
            if primeiro and combo[0] != primeiro:
                continue
            soma = sum(vidas[k] for k in combo)
            tam = [max(1, round(voltas * vidas[k] / soma)) for k in combo]
            tam[-1] = voltas - sum(tam[:-1])
            if tam[-1] < 1:
                continue
            custo = sum(custos[k][n] for k, n in zip(combo, tam)) * base + paradas * perda_pit
            candidatos.append((custo, [[k, n] for k, n in zip(combo, tam)]))
    if tipo == "seco" and regra_dois_compostos(ev.cat):
        validos = [x for x in candidatos
                   if cumpre_dois_compostos(ev.cat, set(usados or ()) | {k for k, _ in x[1]})]
        candidatos = validos or candidatos         # só um composto seco disponível: a regra não tem como valer
    if not candidatos:
        return [[primeiro or lista[0], voltas]]
    candidatos.sort(key=lambda x: x[0])
    if carro.usuario:
        return candidatos[0][1]                      # estratégia automática do jogador: a melhor calculada
    return _escolha_da_equipe(ev, carro, candidatos, voltas)


def _escolha_da_equipe(ev, carro, candidatos, voltas):
    """As equipes do PC não seguem todas a estratégia ótima: cada uma escolhe entre as boas opções com um
    sorteio que favorece as mais rápidas (quanto mais recursos, mais perto da ótima) e ainda ajusta um pouco
    o tamanho dos stints."""
    sim = ev.cat["simulacao"]
    recursos = (carro.equipe or {}).get("recursos", 60)
    temp = sim.get("variacao_estrategia_s", 6.0) * (1.5 - recursos / 100)
    melhor = candidatos[0][0]
    if temp > 0:
        perto = [(c, p) for c, p in candidatos[:8] if c - melhor <= 2.5 * temp]   # só opções realmente boas
        pesos = [math.exp(-(c - melhor) / temp) for c, _ in perto]
        plano = ev.rng.choices([p for _, p in perto], weights=pesos)[0]
    else:
        plano = candidatos[0][1]
    plano = [list(st) for st in plano]
    var = sim.get("variacao_stint", 0.1)
    if len(plano) > 1 and var > 0:
        for i in range(len(plano) - 1):
            folga = max(1, round(plano[i][1] * var))
            d = ev.rng.randint(-folga, folga)
            d = max(1 - plano[i][1], min(d, plano[i + 1][1] - 1))
            plano[i][1] += d
            plano[i + 1][1] -= d
    return plano


def combustivel_inicial(ev, carro, voltas):
    if not ev.cat["regras_pitstop"].get("reabastecimento"):
        return voltas + 1
    if carro.plano_corrida:
        return min(voltas + 1, carro.plano_corrida[0][1] + 1)
    return voltas + 1


# ============================================================================ grid pelo campeonato
class SessaoGrid:
    """Etapa sem pista: o grid sai da classificação do campeonato (ou invertida)."""
    tipo = "classificacao"

    def __init__(self, evento, cfg):
        self.ev = evento
        self.cfg = cfg
        self.nome = cfg.get("nome", "Grid pelo campeonato")
        self.iniciada = False
        self.terminada = False
        self.log = []
        self.relogio = 0.0
        self.ordem_final = None

    def iniciar(self):
        self.iniciada = True
        self.ordem_final = self.ev.ordem_por_campeonato(invertida=self.cfg.get("invertido", False))
        for i, c in enumerate(self.ordem_final, 1):
            c.posicao = i
            c.status = "fim"
        self.ev.grid = list(self.ordem_final)
        self.ev.pole = self.ordem_final[0]
        self.log.append(f"Grid definido pela classificação do campeonato"
                        f"{' (invertida)' if self.cfg.get('invertido') else ''}. Pole: {self.ordem_final[0].nome}.")
        self.terminada = True

    def avancar(self, segundos):
        pass

    def simular_ate_o_fim(self):
        if not self.iniciada:
            self.iniciar()

    def descricao_progresso(self):
        return "Grid definido" if self.terminada else "Aguardando"

    def linhas_classificacao(self):
        return [{"pos": i, "carro": c, "melhor": "-", "ultima": "-", "gap": "", "voltas": 0, "pneu": "-",
                 "desgaste": "", "status": "Grid"} for i, c in enumerate(self.ordem_final or [], 1)]



# ============================================================================ sessões cronometradas
class SessaoCronometrada:
    """Treino livre ou classificação cronometrada (modelos 'tempo', 'grupos' e 'volta_unica')."""

    def __init__(self, evento, tipo, cfg):
        self.ev = evento
        self.tipo = tipo                         # 'treino' | 'classificacao'
        self.cfg = cfg
        self.nome = cfg.get("nome", tipo)
        self.modelo = cfg.get("modelo", "tempo") if tipo == "classificacao" else "tempo"
        self.criterio = cfg.get("criterio", "melhor_volta")
        self.grupos = {}
        if self.modelo == "grupos":
            n = max(1, int(cfg.get("grupos", 2)))
            ordem = evento.ordem_por_campeonato() if evento.ordem_campeonato else \
                sorted(evento.carros, key=lambda c: evento.rng.random())
            self.grupos = {c.id: i % n for i, c in enumerate(ordem)}
            self.fases = [{"nome": f"Grupo {chr(65 + i)}", "limite": cfg.get("limite", "tempo"),
                           "valor": cfg.get("valor", 15), "eliminados": 0, "grupo": i} for i in range(n)]
        elif self.modelo == "volta_unica":
            self.fases = [{"nome": self.nome, "limite": "volta_unica", "valor": cfg.get("voltas_cronometradas", 1),
                           "eliminados": 0}]
        elif tipo == "classificacao" and cfg.get("fases"):
            self.fases = cfg["fases"]
        else:
            self.fases = [{"nome": self.nome, "limite": cfg.get("limite", "tempo"), "valor": cfg.get("valor", 30),
                           "eliminados": 0}]
        self.com_eliminacao = any(f.get("eliminados", 0) for f in self.fases)
        self.fase = 0
        self.relogio = 0.0
        self.iniciada = False
        self.terminada = False
        self.log = []
        self.eliminados = []                     # ordem final dos eliminados (do melhor ao pior, por fase)
        self._heap = []
        self._seq = 0
        self.ordem_final = None
        self.resultados_grupos = []

    # ---------------------------------------------------------------- controle
    @property
    def fase_atual(self):
        return self.fases[self.fase]

    def participantes(self):
        f = self.fase_atual
        if "grupo" in f:
            return [c for c in self.ev.carros if self.grupos.get(c.id) == f["grupo"]]
        return [c for c in self.ev.carros if c.status != "eliminado"]

    def _limite_tempo(self):
        f = self.fase_atual
        if f["limite"] == "tempo":
            # relógio correndo durante bandeira vermelha: o tempo de espera sai do tempo de pista
            return max(0.0, f["valor"] * 60.0 - getattr(self, "tempo_perdido", 0.0))
        if f["limite"] == "volta_unica":
            return 10 ** 9
        return f["valor"] * self.ev.pista["tempo_base_treino"] * 3.0   # teto de segurança

    def iniciar(self):
        self.iniciada = True
        self.ev.preparar_ia()
        self._msg(f"{self.nome} – início. Clima: {self.ev.clima.nome}.")
        for n in self.ev.notas:
            self._msg(n)
        self.ev.notas = []
        if getattr(self, "cancelada_chuva", False):
            self.encerrada_chuva = True             # nenhuma volta é agendada (seria calculada com pista molhada)
        self._iniciar_fase()
        if getattr(self, "cancelada_chuva", False):
            self._encerrar_por_chuva()
        elif self.ev.regras_bandeira_vermelha()["corre"]:
            self.tempo_perdido = getattr(self, "espera_inicial", 0.0)

    def _iniciar_fase(self):
        self.relogio = 0.0
        self.tempo_perdido = 0.0
        self._heap = []
        f = self.fase_atual
        if len(self.fases) > 1 and not getattr(self, "encerrada_chuva", False):
            self._msg(f"{f['nome']} – início ({self._descr_limite(f)}).")
        for c in self.ev.carros:
            c.tempos_fase = []
            c.recolher = False
            c.aguardando = False
        if getattr(self, "encerrada_chuva", False):
            for c in self.participantes():
                c.melhor_fase = self._chave(c)
                c.voltas_fase = 0
            return                                  # sessão encerrada pela chuva: ninguém mais vai à pista
        if f["limite"] == "volta_unica":
            ordem = self._ordem_saida()
            intervalo = self.cfg.get("intervalo_s", 90)
            for i, c in enumerate(ordem):
                c.status = "garagem"
                c.voltas_fase = 0
                c.melhor_fase = None
                self._agendar_run(c, i * intervalo, rapidas=f["valor"])
            self._msg("Ordem de saída: " + ", ".join(c.nome for c in ordem) + ".")
            return
        for c in self.ev.carros:
            if c.status not in ("eliminado", "fim") and c not in self.participantes():
                c.status = "aguardando"
        for c in self.participantes():
            c.melhor_fase = self._chave(c)      # sem eliminação, o tempo das partes anteriores continua valendo
            c.voltas_fase = 0
            c.status = "garagem"
            espera = self.ev.rng.uniform(0, 0.35 * self._limite_tempo()) if f["limite"] == "tempo" \
                else self.ev.rng.uniform(0, 300)
            self._agendar_run(c, espera)

    def _ordem_saida(self):
        o = self.cfg.get("ordem_saida", "campeonato_invertido")
        if o == "aleatoria":
            return sorted(self.ev.carros, key=lambda c: self.ev.rng.random())
        return self.ev.ordem_por_campeonato(invertida=(o == "campeonato_invertido"))

    @staticmethod
    def _descr_limite(f):
        if f["limite"] == "tempo":
            return f"{f['valor']} min"
        if f["limite"] == "volta_unica":
            return f"{f['valor']} volta(s) cronometrada(s) por piloto"
        return f"{f['valor']} voltas"

    def _msg(self, texto):
        self.log.append(f"[{relogio(self.relogio)}] {texto}")

    def _agendar_run(self, c, inicio, rapidas=None):
        """Planeja uma saída: volta de saída + voltas rápidas + volta de entrada."""
        if rapidas is None:
            if self.tipo == "classificacao":
                rapidas = self.ev.rng.choice([1, 2, 2])
            else:
                rapidas = self.ev.rng.randint(3, 8)
        c.combustivel = 3 if self.tipo == "classificacao" else self.ev.rng.uniform(5, 25)
        c.plano = ["saida"] + ["rapida"] * rapidas + ["entrada"]
        c.run_valida = True
        # pneu novo em cada saída; equipes do PC (ou estratégia automática) escolhem o tipo certo para o clima
        if c.usuario and not c.estrategia_auto and c.pneu_inicial:
            comp = c.pneu_inicial
        elif c.usuario and c.pneu_inicial and tipo_pneu(self.ev.cat, c.pneu_inicial) == PNEU_IDEAL[self.ev.clima.estado]:
            comp = c.pneu_inicial
        else:
            comp = composto_para_clima(self.ev, c, self.tipo)
        trocar_pneu(c, comp)
        self._agendar_volta(c, inicio)

    def _agendar_volta(self, c, inicio):
        tipo_volta = c.plano[0]
        t, info = self.ev.modelo.volta(c, self.tipo, self.ev.clima, evolucao=self.ev.evolucao(), tipo_volta=tipo_volta)
        if tipo_volta == "rapida":
            sim = self.ev.cat["simulacao"]
            na_pista = sum(1 for x in self.ev.carros if x.status == "pista")
            # tráfego: mais carros na pista = mais chance; bons classificadores acham espaço ('goodlaps')
            p_traf = sim.get("trafego_volta_rapida", 0.05) * na_pista / 10 \
                * (1.3 - 0.6 * (c.atr("classificacao") + c.atr("concentracao")) / 200)
            if self.ev.rng.random() < p_traf:
                perda = self.ev.rng.uniform(0.2, 1.0)
                t += perda
                info["trafego"] = perda
                info["abortada"] = self.ev.rng.random() < 0.25
            # limites da pista: volta apagada (mais provável com agressividade e pouca concentração)
            p_lim = sim.get("limites_pista", 0.012) * (1 + 0.5 * c.ordens["agressividade"]) \
                * (1.4 - c.atr("concentracao") / 100)
            info["apagada"] = self.ev.rng.random() < max(0.0, p_lim)
        c._volta_em_curso = (t, info, tipo_volta, inicio)
        c.status = "pista"
        self._seq += 1
        heapq.heappush(self._heap, (inicio + t, self._seq, c))

    def _pode_iniciar_volta(self, c, instante):
        if getattr(c, "fora_do_evento", None):
            return False
        f = self.fase_atual
        if f["limite"] == "tempo":
            return instante < f["valor"] * 60.0
        if f["limite"] == "volta_unica":
            return True
        return c.voltas_fase < f["valor"] and instante < self._limite_tempo()

    def _concluir_volta(self, c, fim):
        t, info, tipo_volta, inicio = c._volta_em_curso
        c.plano.pop(0)
        c.voltas += 1
        c.voltas_fase += 1
        self.ev.contar_volta(c)
        registrar_volta_pneu(c, self.ev.cat, self.ev.pista, self.ev.clima.estado)
        c.combustivel = max(0.0, c.combustivel - 1)
        c.conhecimento = min(1.0, c.conhecimento + self.ev.cat["simulacao"].get("aprendizado_por_volta", 0.03)
                             * (0.5 + c.atr("acerto_carro") / 200))
        if self._talvez_batida_grave(c):
            return
        inc = self.ev.modelo.incidente(c, self.ev.clima)
        if inc:
            tipo, grave = inc
            if grave:
                c.plano = []
                c.motivo = "acidente" if tipo == "acidente" else "quebra"
                c.run_valida = False
                self._msg(f"{c.nome} ({c.equipe['nome']}): {'ACIDENTE' if tipo == 'acidente' else 'QUEBRA'} – "
                          f"fora do restante da sessão.")
                c.status = "fim"
                return
            self._msg(f"{c.nome}: {'rodada' if tipo == 'acidente' else 'problema mecânico leve'}, volta perdida.")
            t *= 1.15
            if tipo_volta == "rapida":
                c.run_valida = False
            tipo_volta = "perdida"
        if tipo_volta == "rapida" and (info.get("abortada") or info.get("apagada")):
            if self.tipo == "classificacao":
                self._msg(f"{c.nome}: volta apagada (limites da pista)." if info.get("apagada")
                          else f"{c.nome} pega tráfego e aborta a volta.")
            c.ultima = t
            tipo_volta = "perdida"
        elif tipo_volta == "rapida" and info.get("trafego") and self.tipo == "classificacao":
            self._msg(f"{c.nome} pega tráfego (+{info['trafego']:.1f}s).")
        if tipo_volta == "rapida":
            c.ultima = t
            c.tempos_fase.append(t)
            if c.melhor is None or t < c.melhor:
                c.melhor = t
            c.melhor_fase = self._chave(c)
        if getattr(c, "recolher", False) and c.plano and c.plano[0] != "entrada":
            c.plano = ["entrada"]                     # chamado ao box: a próxima é a volta de entrada
        if c.plano and self._pode_iniciar_volta(c, fim):
            self._agendar_volta(c, fim)
            return
        # volta para a garagem
        c.status = "garagem"
        if c.usuario and self.tipo in ("treino", "classificacao"):     # o acerto vale da 1ª sessão até a corrida
            ideal = self.ev.modelo.ideal(c, self.ev.clima.estado)      # o ideal real (com o desvio escondido)
            diffs = avaliar_acerto(c, ideal, self.ev.rng)
            texto = texto_feedback(diffs)
            c.feedback = {"sessao": self.nome, "volta": c.voltas, "nota": nota_acerto(diffs), "texto": texto,
                          "diffs": {k: round(v, 1) for k, v in diffs.items()}, "acerto": dict(c.acerto)}
            self._msg(f"{c.nome} (sua equipe) {texto}.")
        if getattr(c, "recolher", False):
            c.recolher = False
            c.aguardando = True
            self._msg(f"{c.nome} está no box: ajuste o acerto e mande de volta à pista.")
            return
        if self.fase_atual["limite"] == "volta_unica":
            c.status = "fim"
            v = self._chave(c)
            self._msg(f"{c.nome}: {tempo_volta(v) if v else 'sem tempo válido'}.")
            return
        espera = self.ev.rng.uniform(150, 600) if self.tipo == "treino" else self.ev.rng.uniform(120, 360)
        if self._pode_iniciar_volta(c, fim + espera):
            self._agendar_run(c, fim + espera)
        else:
            c.status = "fim"

    # ---------------------------------------------------------------- box (usuário)
    def pode_chamar_box(self, c):
        return self.iniciada and not self.terminada and self.fase_atual["limite"] != "volta_unica" \
            and c.status == "pista" and not getattr(c, "recolher", False)

    def chamar_box(self, c):
        """O piloto completa a volta, faz a volta de entrada e espera no box."""
        if self.pode_chamar_box(c):
            c.recolher = True
            self._msg(f"Equipe chama {c.nome} ao box.")

    def liberar(self, c):
        """Volta à pista depois de ajustar o acerto (o acerto/pneu já estão no carro)."""
        if not getattr(c, "aguardando", False):
            return
        c.aguardando = False
        inicio = self.relogio + self.ev.rng.uniform(45, 90)
        if self._pode_iniciar_volta(c, inicio):
            self._agendar_run(c, inicio)
            self._msg(f"{c.nome} volta à pista com novo acerto.")
        else:
            c.status = "fim"

    def _esperando(self):
        return [c for c in self.ev.carros if getattr(c, "aguardando", False)]

    def _chave(self, c):
        """Tempo que vale para a classificação nesta fase."""
        if self.criterio == "media" and self.modelo == "volta_unica":
            n = self.fase_atual["valor"]
            if not getattr(c, "run_valida", True) or len(c.tempos_fase) < n:
                return None
            return sum(c.tempos_fase[:n]) / n
        if self.tipo == "classificacao" and self.modelo == "tempo" and self.com_eliminacao:
            return min(c.tempos_fase) if c.tempos_fase else None
        return c.melhor                          # sem eliminação: a melhor volta da sessão inteira

    def avancar(self, segundos):
        """Avança o relógio da sessão."""
        if self.terminada:
            return
        alvo = self.relogio + segundos
        while self._heap and self._heap[0][0] <= alvo:
            fim, _, c = heapq.heappop(self._heap)
            self._avancar_clima(fim - self.relogio)
            if self.terminada:
                return
            self.relogio = fim
            self._concluir_volta(c, fim)
            if self.terminada:
                return
        if not self._heap:
            esperando = self._esperando()
            limite = self._limite_tempo()
            if esperando and self.relogio < limite:
                # só carros parados no box: o relógio corre até o fim da sessão
                novo = min(alvo, limite)
                self._avancar_clima(novo - self.relogio)
                if self.terminada:
                    return
                self.relogio = novo
                if self.relogio < limite:
                    return
            for c in esperando:
                c.aguardando = False
                c.status = "fim"
            self._fim_fase()
            return
        self._avancar_clima(alvo - self.relogio)
        if self.terminada:
            return
        self.relogio = alvo

    def _avancar_clima(self, dt):
        if dt > 0 and self.ev.clima.avancar(dt):
            for m in self.ev.clima.mudancas[-1:]:
                self._msg(m)
            if self.ev.clima.estado != "seco":
                self.ev.lavar_pista(0.7)
                if self.ev.oval():
                    self._msg("BANDEIRA VERMELHA: chuva no oval, sessão suspensa.")
                    rb = self.ev.regras_bandeira_vermelha()
                    minutos, secou = self.ev.esperar_secar(rb["sessao"])
                    if rb["corre"]:
                        self.tempo_perdido = getattr(self, "tempo_perdido", 0.0) + minutos * 60.0
                    if not secou:
                        self._msg(f"A chuva não parou em {minutos} min: sessão encerrada. Valem os tempos já feitos.")
                        self._encerrar_por_chuva()
                    elif rb["corre"]:
                        self._msg(f"Sessão retomada após {minutos} min (tempo descontado da sessão): pista seca.")
                    else:
                        self._msg(f"Sessão retomada após {minutos} min: pista seca.")
            for c in self.ev.carros:
                c._cache.clear()

    def _encerrar_por_chuva(self):
        self._encerrar_antecipado()

    def _talvez_batida_grave(self, c):
        """Batida grave com vários carros na pista. True se `c` está entre os envolvidos."""
        ev = self.ev
        bg = ev.regras_batida()
        p = bg["prob_por_volta"] * bg["fator_treinos"] / max(1, len(ev.carros)) \
            * ev.clima.efeitos.get("acidentes", 1.0) * (0.5 + ev.pista.get("dificuldade", 50) / 100)
        if ev.rng.random() >= p:
            return False
        na_pista = [x for x in ev.carros if x.status == "pista" and x is not c]
        if not na_pista or bg["carros_min"] > len(na_pista) + 1:
            return False
        n = ev.rng.randint(max(2, int(bg["carros_min"])), min(int(bg["carros_max"]), len(na_pista) + 1))
        envolvidos = [c] + ev.rng.sample(na_pista, n - 1)
        self._heap = [x for x in self._heap if x[2] not in envolvidos]
        heapq.heapify(self._heap)
        for x in envolvidos:
            x.plano = []
            x.status = "fim"
            x.run_valida = False
            x.motivo = "batida grave"
        self._msg("BATIDA GRAVE: " + ", ".join(x.nome for x in envolvidos) + " – fora do restante da sessão.")
        ev.registrar_batida(envolvidos, self._msg)
        if ev.rng.random() < bg["prob_encerrar_sessao"]:
            self._msg("BANDEIRA VERMELHA: sessão encerrada após a batida grave. Valem os tempos já feitos.")
            self._encerrar_antecipado()
        else:
            self._msg("BANDEIRA VERMELHA: sessão interrompida para atendimento e limpeza da pista.")
            if ev.regras_bandeira_vermelha()["corre"]:
                self.tempo_perdido = getattr(self, "tempo_perdido", 0.0) + 15 * 60.0
        return True

    def _encerrar_antecipado(self):
        """Encerra a sessão: as fases que faltam não acontecem; vale a ordem pelos tempos já feitos (fase
        atual, depois o melhor tempo da sessão e, sem tempo, a ordem do campeonato)."""
        self.encerrada_chuva = True
        self._heap = []
        for c in self.ev.carros:
            c.aguardando = False
            if c.status not in ("eliminado",):
                c.status = "fim"
        while not self.terminada:
            self._fim_fase()

    def simular_ate_o_fim(self):
        while not self.terminada:
            for c in self._esperando():
                self.liberar(c)
            for c in self.ev.carros:
                c.recolher = False
            self.avancar(3600)

    def _fim_fase(self):
        f = self.fase_atual
        ordenados = self._ordem_fase()
        if "grupo" in f:
            self.resultados_grupos.append(ordenados)
            for c in ordenados:
                c.status = "fim"
            self._msg(f"{f['nome']} encerrado. Mais rápido: {ordenados[0].nome if ordenados else '-'}.")
        elif f.get("eliminados", 0) and self.fase < len(self.fases) - 1:
            n = f["eliminados"]
            fora = ordenados[-n:]
            for c in fora:
                c.status = "eliminado"
            self.eliminados = fora + self.eliminados
            self._msg(f"{f['nome']} encerrada. Eliminados: " + ", ".join(c.nome for c in fora) + ".")
        else:
            self._msg(f"{f['nome']} encerrada.")
        if self.fase < len(self.fases) - 1:
            self.fase += 1
            self._iniciar_fase()
            return
        self.terminada = True
        if self.resultados_grupos:
            self.ordem_final = self._intercalar(self.resultados_grupos)
        else:
            self.ordem_final = self._ordem_fase() + self.eliminados
        for i, c in enumerate(self.ordem_final, 1):
            c.posicao = i
        self.ev.historico_sessoes.append({
            "nome": self.nome, "tipo": self.tipo, "clima": self.ev.clima.nome,
            "linhas": [{"pos": i, "piloto": c.id, "nome": c.nome, "equipe": c.equipe["id"],
                        "equipe_nome": c.equipe["nome"], "melhor": round(c.melhor, 3) if c.melhor else None,
                        "voltas": c.voltas} for i, c in enumerate(self.ordem_final, 1)]})
        if self.tipo == "classificacao":
            self.ev.grid = list(self.ordem_final)
            self.ev.pole = self.ordem_final[0]
            self._msg(f"POLE POSITION: {self.ordem_final[0].nome} ({self.ordem_final[0].equipe['nome']}) – "
                      f"{tempo_volta(self.ordem_final[0].melhor_fase)}")
        else:
            m = self.ordem_final[0]
            if m.melhor:
                self._msg(f"Mais rápido: {m.nome} – {tempo_volta(m.melhor)}")

    @staticmethod
    def _intercalar(grupos):
        """Grid intercalado: o grupo com a volta mais rápida fica com as posições ímpares."""
        def melhor(g):
            return g[0].melhor_fase if g and g[0].melhor_fase else float("inf")
        grupos = sorted(grupos, key=melhor)
        ordem = []
        for i in range(max(len(g) for g in grupos)):
            for g in grupos:
                if i < len(g):
                    ordem.append(g[i])
        return ordem

    def _ordem_fase(self):
        ativos = self.participantes()
        if self.tipo == "classificacao":
            def chave(c):
                return c.melhor_fase
        else:
            def chave(c):
                return c.melhor
        pos = {pid: i for i, pid in enumerate(self.ev.ordem_campeonato)}
        return sorted(ativos, key=lambda c: (chave(c) is None, chave(c) or 0, c.melhor is None, c.melhor or 0,
                                             pos.get(c.id, 999)))

    # ---------------------------------------------------------------- tela
    def descricao_progresso(self):
        f = self.fase_atual
        if f["limite"] == "tempo":
            resto = max(0, f["valor"] * 60 - self.relogio)
            txt = f"Tempo restante: {relogio(resto)}"
        elif f["limite"] == "volta_unica":
            feitos = sum(1 for c in self.ev.carros if c.status == "fim")
            txt = f"Volta única – {feitos}/{len(self.ev.carros)} pilotos"
        else:
            txt = f"Voltas: máx. {f['valor']} por piloto – {relogio(self.relogio)}"
        if len(self.fases) > 1:
            txt = f"{f['nome']} | {txt}"
        return txt

    def linhas_classificacao(self):
        if self.terminada:
            ordem = self.ordem_final
        elif self.resultados_grupos:
            ordem = self._intercalar(self.resultados_grupos + [self._ordem_fase()])
            ordem += [c for c in self.ev.carros if c not in ordem]
        else:
            ordem = self._ordem_fase() + self.eliminados
            ordem += [c for c in self.ev.carros if c not in ordem]
        melhor = None
        linhas = []
        for i, c in enumerate(ordem, 1):
            t = c.melhor_fase if self.tipo == "classificacao" else c.melhor
            if melhor is None and t is not None:
                melhor = t
            gap = (t - melhor) if (t is not None and melhor is not None and i > 1) else None
            status = {"pista": "Na pista", "garagem": "Box", "fim": "Fim" if not c.motivo else c.motivo.capitalize(),
                      "eliminado": "Eliminado", "aguardando": "Aguardando"}.get(c.status, c.status)
            if self.grupos:
                status = f"Gr. {chr(65 + self.grupos.get(c.id, 0))} – {status}"
            linhas.append({"pos": i, "carro": c, "melhor": tempo_volta(t), "ultima": tempo_volta(c.ultima),
                           "gap": f"+{gap:.3f}" if gap is not None else "", "voltas": c.voltas,
                           "pneu": self.ev.cat["pneus"]["compostos"][c.pneu]["nome"] if c.pneu else "-",
                           "desgaste": f"{c.desgaste:.0f}%", "status": status})
        return linhas



# ============================================================================ corrida
class SessaoCorrida:
    """Corrida (ou corrida classificatória, cuja chegada forma o grid da corrida principal).

    Cada volta: ritmo de cada carro (com ar sujo de quem está a menos de 1 s do carro da frente), pit stops,
    incidentes (dano persistente até o reparo), disputas de posição (pela diferença de ritmo de fundo, com
    custo de tempo para quem ataca e quem defende), retardatários (bandeira azul) e safety car / VSC."""
    tipo = "corrida"
    sc = None                                    # {"tipo": "SC"|"VSC", "voltas": n} enquanto ativo

    def __init__(self, evento, cfg, classificatoria=False):
        self.ev = evento
        self.cfg = cfg
        self.classificatoria = classificatoria
        self.nome = cfg.get("nome", "Corrida classificatória" if classificatoria else "Corrida")
        self.total_voltas = int(cfg.get("voltas") or evento.pista["voltas_corrida"]) if classificatoria \
            else int(evento.pista["voltas_corrida"])
        self.tempo_maximo = (cfg.get("tempo_maximo_min") or 0) * 60 or None
        regras = evento.cat["regras_pitstop"]
        self.paradas_minimas = 0 if classificatoria else (
            regras.get("paradas_minimas", 0) if regras.get("obrigatorio") else 0)
        self.volta_lider = 0
        self.iniciada = False
        self.terminada = False
        self.log = []
        self.volta_mais_rapida = None            # (tempo, carro, volta)
        self.resultado = None
        self.relogio = 0.0

    def _msg(self, texto):
        self.log.append(f"[V{self.volta_lider:>3}] {texto}")

    def _grid_de_largada(self):
        ev = self.ev
        if self.classificatoria:
            origem = self.cfg.get("grid", "anterior")
            if origem == "anterior" and ev.grid:
                return list(ev.grid)
            if origem == "aleatorio":
                return sorted(ev.carros, key=lambda c: ev.rng.random())
            return ev.ordem_por_campeonato(invertida=(origem != "campeonato"))
        grid = list(ev.grid)
        n = int(self.cfg.get("grid_invertido_top", 0) or 0)
        if n > 1:
            grid = list(reversed(grid[:n])) + grid[n:]
            self._msg(f"Grid invertido entre os {n} primeiros.")
        return grid

    def iniciar(self):
        self.iniciada = True
        ev = self.ev
        self.grid = self._grid_de_largada()
        for n in ev.notas:
            self._msg(n)
        ev.notas = []
        if not self.classificatoria:
            # punição de grid (motor além da cota): de trás para a frente, cada um perde N posições
            for c in sorted([c for c in self.grid if c.penalidade_grid], key=lambda c: -self.grid.index(c)):
                i = self.grid.index(c)
                self.grid.insert(min(len(self.grid) - 1, i + c.penalidade_grid), self.grid.pop(i))
                self._msg(f"{c.nome} perde {c.penalidade_grid} posições no grid (motor além da cota).")
        ev.preparar_ia()
        sim = ev.cat["simulacao"]
        for i, c in enumerate(self.grid):
            c.status = "pista"
            if not c.plano_corrida:
                c.plano_corrida = planejar(ev, c, self.total_voltas, self.paradas_minimas, primeiro=c.pneu_inicial)
            trocar_pneu(c, c.pneu_inicial or c.plano_corrida[0][0])
            c.compostos_usados = {c.pneu}
            c.combustivel = c.combustivel_inicial if c.combustivel_inicial is not None \
                else combustivel_inicial(ev, c, self.total_voltas)
            c.combustivel = min(c.combustivel, self.total_voltas + 1)
            c.tempo_total = i * sim.get("intervalo_grid_s", 0.25)
            c.posicao = i + 1
            c.grid = i + 1
        for c in self.grid:
            if getattr(c, "fora_do_evento", None):            # vítima de batida grave em sessão anterior
                c.status = "abandono"
                c.motivo = "Não largou (lesão)" if c.fora_do_evento == "lesao" else "Não largou"
        self.tempo_suspenso = getattr(self, "espera_inicial", 0.0) if ev.regras_bandeira_vermelha()["corre"] else 0.0
        if getattr(self, "cancelada_chuva", False):
            self.cancelada = True
            self._msg("Corrida cancelada: a chuva não parou. Ninguém pontua.")
            self._finalizar()
            return
        self._msg(f"Largada! {self.total_voltas} voltas. Clima: {ev.clima.nome}. Pole: {self.grid[0].nome}.")

    def correndo(self):
        return [c for c in self.ev.carros if c.status in ("pista", "box")]

    # ---------------------------------------------------------------- pit stop
    def _replanejar(self, c, restantes, composto=None):
        if getattr(c, "plano_fixo", None):              # plano de paradas do jogador (multijogador)
            c.plano_corrida = [list(s) for s in c.plano_fixo]
            return composto or c.plano_fixo[0][0]
        """Chamado durante um pit stop: a parada em curso já conta para as obrigatórias."""
        faltam = max(0, self.paradas_minimas - (c.paradas + 1))
        c.plano_corrida = planejar(self.ev, c, restantes, faltam, primeiro=composto, usados=c.compostos_usados)
        return c.plano_corrida[0][0]

    def _decidir_pit(self, c, restantes):
        """Retorna (composto, motivo) se o carro para nesta volta. Estratégia guiada pela degradação."""
        ev = self.ev
        regras = ev.cat["regras_pitstop"]
        if c.chamado_box:
            comp = c.chamado_box
            c.chamado_box = None
            return comp, "pedido da equipe"
        manual = c.usuario and not c.estrategia_auto and not getattr(c, "plano_fixo", None)
        if c.dano >= ev.cat["simulacao"].get("dano_para_reparo", 0.006) and restantes > 3 and not manual:
            return ("replanejar" if not getattr(c, "plano_fixo", None) else c.pneu), "reparo de danos"
        if self.sc and not manual and not getattr(c, "plano_fixo", None) and len(c.plano_corrida) > 1 \
                and c.idade_pneu >= 0.55 * c.plano_corrida[0][1] and restantes > 5:
            return "replanejar", f"aproveita o {self.sc['tipo']}"
        if c.usuario and getattr(c, "plano_fixo", None):
            # plano de stints do jogador; se o clima pedir outro tipo de pneu, a equipe assume a estratégia
            if tipo_pneu(ev.cat, c.pneu) != PNEU_IDEAL[ev.clima.estado] and restantes > 2:
                c.plano_fixo = None
                c.estrategia_auto = True
                return "replanejar", "mudança de clima"
            if len(c.plano_fixo) > 1 and c.idade_pneu >= c.plano_fixo[0][1]:
                c.plano_fixo.pop(0)
                return c.plano_fixo[0][0], "parada planejada"
            if regras.get("reabastecimento") and c.combustivel < 1.2:
                return c.pneu, "sem combustível"
            return None, None
        if c.usuario and not c.estrategia_auto:
            if regras.get("reabastecimento") and c.combustivel < 1.2:
                return c.pneu, "sem combustível"
            return None, None
        if restantes <= 1:
            return None, None
        ideal_tipo = PNEU_IDEAL[ev.clima.estado]
        if tipo_pneu(ev.cat, c.pneu) != ideal_tipo and restantes > 2 \
                and ev.rng.random() < 0.55 + c.atr("concentracao") / 300:
            return "replanejar", f"troca para pneus de {NOMES_CLIMA[ideal_tipo].lower()}"
        if regras.get("reabastecimento") and c.combustivel < 1.5:
            return "replanejar", "reabastecimento"
        if not regras.get("troca_de_pneus", True):
            return None, None
        stint = c.plano_corrida[0][1] if c.plano_corrida else restantes
        # fim do stint planejado (com uma pequena tolerância de leitura da equipe) ou pneu além do cliff
        if len(c.plano_corrida) > 1 and c.idade_pneu >= stint + ev.rng.choice([-1, 0, 0, 1]):
            return "replanejar", "fim do stint"
        if c.desgaste >= 115 and restantes > 3:
            return "replanejar", "pneus no limite"
        if c.paradas < self.paradas_minimas and restantes <= 3:
            return "replanejar", "parada obrigatória"
        return None, None

    def _tempo_pit(self, c, restantes):
        ev = self.ev
        regras = ev.cat["regras_pitstop"]
        t = ev.pista.get("duracao_pitstop", 22) + ev.rng.uniform(0, 1.5)
        if self.sc:                               # todos andam devagar: a parada custa bem menos
            t *= ev.cat["simulacao"].get("pit_sob_sc", 0.55) if self.sc["tipo"] == "SC" \
                else ev.cat["simulacao"].get("pit_sob_vsc", 0.7)
        if c.dano > 0:
            t += ev.rng.uniform(4, 8)
            self._msg(f"{c.nome}: equipe repara os danos.")
            c.dano = 0.0
        if ev.rng.random() < 0.04:
            t += ev.rng.uniform(2, 8)
            self._msg(f"Problema no pit stop de {c.nome}!")
        if regras.get("reabastecimento"):
            alvo = min(restantes + 1, (c.plano_corrida[0][1] if c.plano_corrida else restantes) + 1)
            adicionar = max(0.0, alvo - c.combustivel)
            t += adicionar * regras.get("segundos_por_volta_de_combustivel", 0.4)
            c.combustivel += adicionar
        return t

    # ---------------------------------------------------------------- volta
    def avancar_volta(self):
        if self.terminada:
            return
        ev = self.ev
        sim = ev.cat["simulacao"]
        self.volta_lider += 1
        restantes = self.total_voltas - self.volta_lider + 1
        ordem = sorted(self.correndo(), key=lambda c: c.tempo_total)
        progresso = self.volta_lider / max(1, self.total_voltas)
        sc = self.sc
        oval = ev.perfil_oval()
        empurrados = set()
        if oval and oval["pelotao"] > 0:
            # quem tem um carro colado atrás ganha o empurrão do vácuo (no superspeedway, sozinho é mais lento)
            for a, b in zip(ordem, ordem[1:]):
                if 0 <= b.tempo_total - a.tempo_total < oval["alcance_vacuo_s"]:
                    empurrados.add(a)
        ritmo_medio = None
        if oval and oval["pelotao"] > 0:
            rs = [c.ritmo for c in ordem if c.ritmo]
            ritmo_medio = sum(rs) / len(rs) if rs else None
        self._graves = []
        novos = {}
        pitou = set()
        tempos = {}
        evol = ev.evolucao()
        anterior = None
        for c in ordem:
            comp, motivo = self._decidir_pit(c, restantes)
            t, info = ev.modelo.volta(c, "corrida", ev.clima, evolucao=evol, progresso_corrida=progresso)
            if ritmo_medio and c.ritmo:
                # superspeedway: o vácuo (e o limite de potência) aproxima a velocidade dos carros
                t -= oval["compressao_pelotao"] * oval["pelotao"] * (c.ritmo - ritmo_medio)
            if sc:
                # todos no ritmo do safety car / VSC (o VSC mantém as diferenças)
                t = c.ritmo * (sim.get("ritmo_sc", 1.4) if sc["tipo"] == "SC" else sim.get("ritmo_vsc", 1.35))
            elif self.volta_lider == 1:
                largada = ev.modelo.nota_largada(c)
                fl = oval["efeito_largada"] if oval else 1.0          # oval: largada lançada
                t += ((0.5 - largada) * 2.0 + ev.rng.uniform(0, 0.8)) * fl
            elif anterior is not None:
                gap = c.tempo_total - anterior.tempo_total
                pel = oval["pelotao"] if oval else 0.0
                if 0 <= gap < 1.0:
                    # ar sujo: perde pressão aerodinâmica atrás de outro carro, mais nas curvas de alta
                    # (no oval de pelotão o vácuo domina e o ar sujo quase não pesa)
                    t *= 1 + sim.get("ar_sujo", 0.01) * (0.3 + ev.modelo.perfil["curvas_alta"]) * (1 - gap) * (1 - pel)
                if oval and 0 <= gap < oval["alcance_vacuo_s"]:
                    # vácuo nas retas do oval: quem vem atrás anda mais rápido – é o que forma o pelotão
                    t *= 1 - oval["vacuo"] * ev.modelo.perfil["retas"] * (0.25 + pel) \
                        * (1 - gap / oval["alcance_vacuo_s"])
                    # no pelotão, carro mais lento acompanha quem vai à frente enquanto estiver no vácuo
                    if anterior in tempos and t > tempos[anterior]:
                        t -= pel * 0.6 * (t - tempos[anterior])
            if c in empurrados and not sc and self.volta_lider > 1:
                t *= 1 - 0.5 * oval["vacuo"] * ev.modelo.perfil["retas"] * oval["pelotao"]
            anterior = c
            if comp:
                if comp == "replanejar":
                    comp = self._replanejar(c, restantes)
                else:
                    self._replanejar(c, restantes, comp)
                t += self._tempo_pit(c, restantes)
                if self._pode_trocar(c, comp):
                    trocar_pneu(c, comp)
                    c.compostos_usados.add(comp)
                    self._msg(f"{c.nome} faz pit stop ({motivo}) – {ev.cat['pneus']['compostos'][comp]['nome']}.")
                else:
                    self._msg(f"{c.nome} faz pit stop ({motivo}) – sem troca de pneus.")
                c.paradas += 1
                pitou.add(c)
            registrar_volta_pneu(c, ev.cat, ev.pista, ev.clima.estado, fator=0.5 if sc else 1.0)
            uso = (1 + sim["ordens"].get("uso_motor_combustivel", 0.04) * c.ordens["uso_motor"]) * (0.6 if sc else 1.0)
            c.combustivel = max(0.0, c.combustivel - uso)
            ev.contar_volta(c)
            inc = None if sc else ev.modelo.incidente(c, ev.clima)
            if inc:
                tipo, grave = inc
                if grave:
                    c.status = "abandono"
                    c.motivo = "Acidente" if tipo == "acidente" else "Quebra"
                    self._msg(f"ABANDONO: {c.nome} ({c.equipe['nome']}) – {c.motivo.lower()}.")
                    self._graves.append(tipo)
                    continue
                perda = ev.rng.uniform(4, 15) if tipo == "acidente" else ev.rng.uniform(5, 20)
                t += perda
                danificado = ev.rng.random() < 0.6
                if danificado:
                    c.dano += ev.rng.uniform(0.002, 0.012) if tipo == "acidente" else ev.rng.uniform(0.001, 0.006)
                o_que = "rodada" if tipo == "acidente" else "problema mecânico"
                if danificado:
                    self._msg(f"{c.nome}: {o_que} (+{perda:.1f}s) – carro danificado.")
                else:
                    self._msg(f"{c.nome}: {o_que} (+{perda:.1f}s).")
            pn = ev.cat["pneus"]
            critico = pn.get("desgaste_critico", 100)
            if c.desgaste > critico and ev.rng.random() < (c.desgaste - critico + 5) / 150:
                if c.desgaste >= pn.get("desgaste_quebra", 140) and ev.rng.random() < 0.6:
                    c.status = "abandono"
                    c.motivo = "Pneu"
                    self._msg(f"ABANDONO: {c.nome} – pneu destruído pelo desgaste ({c.desgaste:.0f}%).")
                    self._graves.append("pneu")
                    continue
                t += ev.pista.get("duracao_pitstop", 22) + 20
                comp = self._replanejar(c, max(1, restantes - 1))
                trocar_pneu(c, comp)
                c.compostos_usados.add(comp)
                c.paradas += 1
                pitou.add(c)
                self._msg(f"{c.nome}: pneu furado! Volta lenta até o box.")
            if ev.cat["regras_pitstop"].get("reabastecimento") and c.combustivel <= 0 and c not in pitou:
                c.status = "abandono"
                c.motivo = "Sem combustível"
                self._msg(f"ABANDONO: {c.nome} – sem combustível.")
                continue
            tempos[c] = t
            novos[c] = c.tempo_total + t
        if sc:
            if sc["tipo"] == "SC":
                self._compactar(novos)
        else:
            self._resolver_disputas(ordem, novos, tempos, pitou)
            self._retardatarios(novos, tempos)
        for c, total in novos.items():
            c.ultima = tempos[c]
            c.tempo_total = total
            c.voltas += 1
            c.conhecimento = min(1.0, c.conhecimento + 0.005)
            if c not in pitou and self.volta_lider > 1 and not sc and (c.melhor is None or tempos[c] < c.melhor):
                c.melhor = tempos[c]
            if c not in pitou and self.volta_lider > 1 and not sc and (
                    self.volta_mais_rapida is None or tempos[c] < self.volta_mais_rapida[0]):
                self.volta_mais_rapida = (tempos[c], c, self.volta_lider)
        ordem_nova = sorted(self.correndo(), key=lambda c: c.tempo_total)
        for i, c in enumerate(ordem_nova, 1):
            c.posicao = i
        if ordem_nova:
            self.relogio = ordem_nova[0].tempo_total
        bandeira_vermelha = False
        if ev.clima.avancar(self.relogio - getattr(self, "_relogio_clima", 0.0)):
            self._msg(ev.clima.mudancas[-1])
            if ev.clima.estado != "seco":
                ev.lavar_pista(0.7)
                bandeira_vermelha = ev.oval()
            for c in ev.carros:
                c._cache.clear()
        self._relogio_clima = self.relogio
        # safety car: termina ou entra
        if sc:
            sc["voltas"] -= 1
            if sc["voltas"] <= 0:
                self.sc = None
                self._msg("Safety car recolhido: relargada!" if sc["tipo"] == "SC" else "Fim do VSC: pista liberada.")
                if sc["tipo"] == "SC" and ev.perfil_oval():
                    self._relargada = self.volta_lider + 1     # oval: relargada em fila dupla, embolada
        if bandeira_vermelha and not self.volta_lider >= self.total_voltas:
            # oval com chuva: corrida suspensa até secar ou até o limite de espera; o tempo parado conta (ou não)
            # para o tempo máximo conforme a categoria; relargada atrás do safety car, com o pelotão agrupado
            self._msg("BANDEIRA VERMELHA: chuva no oval, corrida suspensa.")
            rb = ev.regras_bandeira_vermelha()
            minutos, secou = ev.esperar_secar(rb["corrida"])
            if rb["corre"]:
                self.tempo_suspenso += minutos * 60.0
            if not secou:
                self._msg(f"A chuva não parou em {minutos} min: corrida encerrada na volta {self.volta_lider}.")
                self.interrompida = True
                self._finalizar()
                return
            self.sc = {"tipo": "SC", "voltas": 2}
            self._msg(f"Corrida retomada após {minutos} min, pista seca: relargada atrás do safety car.")
        if not sc and self.volta_lider < self.total_voltas and self._batida_grave():
            if ev.rng.random() < ev.regras_batida()["prob_encerrar_sessao"]:
                self._msg(f"BANDEIRA VERMELHA: a corrida não é retomada após a batida grave (volta {self.volta_lider}).")
                self.interrompida = True
                self._finalizar()
                return
            self._msg("BANDEIRA VERMELHA: corrida suspensa para atendimento e limpeza da pista. Relargada atrás do "
                      "safety car.")
            self.sc = {"tipo": "SC", "voltas": 3}
        if self._graves and restantes > 2:
            self._talvez_safety_car(self._graves)
        elif oval and not self.sc and restantes > 2:
            self._talvez_safety_car([])               # oval: amarela por detritos
        decorrido = self.relogio + getattr(self, "tempo_suspenso", 0.0)
        # oval: como na IndyCar/NASCAR, a corrida cumpre a distância (opção respeitar_tempo_maximo)
        tempo_max = self.tempo_maximo if (not oval or oval.get("respeitar_tempo_maximo")) else None
        if self.volta_lider >= self.total_voltas or not ordem_nova or \
                (tempo_max and decorrido >= tempo_max):
            if tempo_max and decorrido >= tempo_max and self.volta_lider < self.total_voltas:
                self._msg("Tempo máximo atingido: corrida encerrada.")
            self._finalizar()

    def _pode_trocar(self, c, comp):
        """A categoria permite trocar pneus na parada? Sem troca, só vale passar de pneu seco para o de chuva
        (ou o contrário) quando o clima exige – por segurança."""
        ev = self.ev
        if ev.cat["regras_pitstop"].get("troca_de_pneus", True):
            return comp in ev.compostos_disponiveis() or comp == c.pneu
        return tipo_pneu(ev.cat, comp) != tipo_pneu(ev.cat, c.pneu) and tipo_pneu(ev.cat, comp) == PNEU_IDEAL[ev.clima.estado]

    # ---------------------------------------------------------------- safety car
    def _talvez_safety_car(self, graves):
        ev = self.ev
        sim = ev.cat["simulacao"]
        rua = ev.pista.get("tipo_pista") == "rua"
        oval = ev.perfil_oval()
        if oval:
            # oval: toda batida chama bandeira amarela geral (safety car), nunca VSC; quebra com óleo/detritos também
            acidente = any(g in ("acidente", "colisao", "pneu") for g in graves)
            p = oval["prob_amarela_acidente"] if acidente else oval["prob_amarela_quebra"] if graves \
                else oval["amarelas_detritos_por_corrida"] * (0.8 * (1 + (oval["amarelas_oval_curto"] - 1) * oval["curto"])
                                                              + 0.4 * oval["pelotao"]) \
                / max(1, self.total_voltas)
            if ev.rng.random() >= p:
                return
            lo, hi = oval["voltas_amarela"]
            voltas = ev.rng.randint(int(lo), int(hi))
            if self.sc:
                self.sc.update(tipo="SC", voltas=max(self.sc["voltas"], voltas))
                return
            self.sc = {"tipo": "SC", "voltas": voltas}
            self._msg("BANDEIRA AMARELA: safety car na pista" + ("." if graves else " (detritos)."))
            return
        if any(g in ("acidente", "colisao", "pneu") for g in graves):
            p = sim.get("prob_sc_acidente", 0.45) * (1.35 if rua else 1.0)
            if ev.rng.random() >= p:
                return
            tipo = "SC" if ev.rng.random() < sim.get("fracao_sc", 0.65) else "VSC"
        elif ev.rng.random() < sim.get("prob_vsc_quebra", 0.3):
            tipo = "VSC"
        else:
            return
        voltas = ev.rng.randint(3, 5) if tipo == "SC" else ev.rng.randint(2, 3)
        if self.sc:
            self.sc["voltas"] = max(self.sc["voltas"], voltas)
            if tipo == "SC":
                self.sc["tipo"] = "SC"
            return
        self.sc = {"tipo": tipo, "voltas": voltas}
        self._msg("SAFETY CAR na pista: o pelotão se agrupa." if tipo == "SC"
                  else "VIRTUAL SAFETY CAR: todos reduzem o ritmo.")

    def _batida_grave(self):
        """Batida com vários carros (mais provável na largada, na chuva e em pista difícil). True se houve."""
        ev = self.ev
        bg = ev.regras_batida()
        p = bg["prob_por_volta"] * ev.clima.efeitos.get("acidentes", 1.0) \
            * (0.5 + ev.pista.get("dificuldade", 50) / 100) * (3.0 if self.volta_lider == 1 else 1.0)
        vivos = sorted(self.correndo(), key=lambda c: c.tempo_total)
        oval = ev.perfil_oval()
        cmax = int(bg["carros_max"])
        big_one = bool(oval and oval["pelotao"] > 0 and not getattr(self, "_big_one_feito", False))
        if big_one and len(vivos) > 1:
            # "Big One": no pelotão do superspeedway, carros colados multiplicam o risco e o tamanho da batida
            colados = sum(1 for a, b in zip(vivos, vivos[1:]) if b.tempo_total - a.tempo_total < 0.5) / (len(vivos) - 1)
            p *= 1 + (oval["multiplicador_batida_pelotao"] - 1) * oval["pelotao"] * colados
            cmax = int(round(cmax + (oval["carros_max_pelotao"] - cmax) * oval["pelotao"]))
        if ev.rng.random() >= p:
            return False
        if len(vivos) < max(2, int(bg["carros_min"])):
            return False
        teto = min(cmax, len(vivos))
        if big_one:
            # um "Big One" por corrida, com no máximo um terço dos carros que ainda correm: a corrida sempre
            # termina com carros na pista (depois dele, batidas graves voltam a ser as comuns)
            teto = min(teto, max(int(bg["carros_min"]), len(vivos) // 3))
            self._big_one_feito = True
        if teto < max(2, int(bg["carros_min"])):
            return False
        n = ev.rng.randint(max(2, int(bg["carros_min"])), teto)
        i = ev.rng.randrange(0, len(vivos) - n + 1)
        envolvidos = vivos[i:i + n]                     # carros próximos na pista
        for c in envolvidos:
            c.status = "abandono"
            c.motivo = "Batida grave"
        self._msg(f"BATIDA GRAVE na volta {self.volta_lider}: " + ", ".join(c.nome for c in envolvidos) + " abandonam.")
        ev.registrar_batida(envolvidos, self._msg)
        return True

    def _compactar(self, novos):
        """Atrás do safety car as diferenças encolhem (60% por volta, mínimo 0,6 s). Retardatários continuam
        uma volta atrás."""
        if not novos:
            return
        ordem = sorted(novos, key=novos.get)
        ref = ordem[0].ritmo or 90.0
        for a, b in zip(ordem, ordem[1:]):
            gap = novos[b] - novos[a]
            if gap < ref:
                novos[b] = novos[a] + max(0.6, gap * 0.4)

    # ---------------------------------------------------------------- disputas
    def _resolver_disputas(self, ordem, novos, tempos, pitou):
        """Disputa de posição: o carro que alcança o da frente tenta ultrapassar.
        Probabilidade cresce com a proporção de retas, a diferença de ritmo de fundo e a agressividade."""
        ev = self.ev
        sim = ev.cat["simulacao"]
        gap_min = sim.get("distancia_minima_s", 0.25)
        perfil = ev.modelo.perfil
        fator_pista = fator_ultrapassagem_pista(ev.pista, perfil, sim)
        resolvidos = []
        # na largada um carro pode ganhar (ou tentar ganhar) várias posições na mesma volta
        relargada = getattr(self, "_relargada", None) == self.volta_lider
        tentativas = 3 if self.volta_lider == 1 else \
            int((ev.perfil_oval() or {}).get("tentativas_relargada", 1)) if relargada else 1
        # relargada em fila dupla no oval: lado a lado, quem está até alcance_relargada_s do da frente disputa
        alcance = max(gap_min, (ev.perfil_oval() or {}).get("alcance_relargada_s", 0.0)) if relargada else gap_min
        for c in ordem:
            if c not in novos:
                continue
            if resolvidos and c not in pitou:
                passados = set()                  # quem c já passou nesta volta não é alvo de novo
                for _ in range(tentativas):
                    if c not in novos:
                        break
                    frente = [r for r in resolvidos if r not in pitou and r in novos and r not in passados
                              and novos[r] <= novos[c] + alcance]
                    if not frente:
                        break
                    alvo = max(frente, key=lambda r: novos[r])
                    if not novos[c] <= novos[alvo] + alcance + 1e-9:
                        break
                    antes = novos[c]
                    self._disputa(c, alvo, [r for r in resolvidos if r not in pitou and r in novos], novos, tempos,
                                  fator_pista, gap_min)
                    if c not in novos or novos[c] >= antes or novos[c] > novos[alvo]:
                        break                     # não passou: fica atrás e acabou a tentativa
                    passados.add(alvo)
            if c in novos:
                resolvidos.append(c)

    def _disputa(self, c, alvo, frente, novos, tempos, fator_pista, gap_min):
        ev = self.ev
        sim = ev.cat["simulacao"]
        # vantagem de ritmo de fundo (sem o acaso desta volta), em %: carro, piloto, pneus, combustível, dano
        rc, ra = c.ritmo or tempos[c], alvo.ritmo or tempos[alvo]
        ritmo = (ra - rc) / rc * 100
        if self.volta_lider == 1:
            # largada: conta também quem saiu melhor (reação, tração) nesta volta
            ritmo += (tempos[alvo] - tempos[c]) / tempos[c] * 100
        p = sim.get("ultrapassagem_base", 0.3) * fator_pista * ev.clima.efeitos.get("ultrapassagem", 1.0)
        # com o mesmo ritmo quase não se passa; quanto maior a vantagem, maior a chance
        # (não linear: diferença pequena quase nunca basta; diferença grande – pneu novo, carro bem melhor – sim)
        oval = ev.perfil_oval()
        pel = oval["pelotao"] if oval else 0.0
        # no pelotão do oval o vácuo dá o embalo: passa-se mesmo com o mesmo ritmo
        piso = 0.05 + (oval["piso_ultrapassagem_pelotao"] * pel if oval else 0.0)
        if oval and getattr(self, "_relargada", None) == self.volta_lider:
            piso = max(piso, oval["piso_relargada"])           # relargada em fila dupla: lado a lado
        p *= clamp(piso + sim.get("ultrapassagem_sensibilidade_ritmo", 1.2)
                   * max(0.0, ritmo) ** sim.get("ultrapassagem_expoente_ritmo", 2.0), 0.02, 3.0)
        p *= 1 + 0.25 * c.ordens["agressividade"] - 0.12 * alvo.ordens["agressividade"]
        p *= (0.7 + 0.6 * c.atr("conducao") / 100) / (0.7 + 0.6 * alvo.atr("concentracao") / 100)
        if self.volta_lider == 1:
            p *= 1.6
        elif getattr(self, "_relargada", None) == self.volta_lider:
            p *= 1.6
        if alvo.equipe is c.equipe:
            p *= 0.7 + 0.6 * alvo.atr("trabalho_equipe") / 100   # companheiro facilita
        if oval:
            p *= 1 - (1 - oval["ultrapassagem_oval_curto"]) * oval["curto"]   # oval curto: pista estreita, passa-se menos
        p = clamp(p, 0.01, 0.92)
        # a briga custa tempo aos dois (linha defensiva, freada tardia)
        custo = ev.rng.uniform(0.1, 0.3) * (1 + 0.15 * alvo.ordens["agressividade"]) \
            * (1 - (1 - oval["custo_disputa_pelotao"]) * pel if oval else 1.0)
        if ev.rng.random() < p:
            outros = sorted(novos[r] for r in frente if r is not alvo and novos[r] < novos[alvo])
            limite_frente = outros[-1] + gap_min if outros else None
            novo = min(novos[c] + 0.5 * custo, novos[alvo] - ev.rng.uniform(0.05, 0.4))
            if limite_frente is not None:
                novo = max(novo, limite_frente)
            novos[c] = novo
            novos[alvo] += custo
            if novo < novos[alvo]:
                self._msg(f"{c.nome} ultrapassa {alvo.nome}.")
            return
        novos[alvo] += custo * 0.6
        # tentativa frustrada: preso atrás
        risco = sim.get("risco_colisao_disputa", 0.008) * (1 + 0.6 * c.ordens["agressividade"]) * ev.clima.efeitos.get("acidentes", 1.0)
        if oval:
            risco *= 1 + (oval["colisao_oval_curto"] - 1) * oval["curto"]   # oval curto: corrida de contato
        if ev.rng.random() < max(0.0, risco):
            if ev.rng.random() < 0.35:
                c.status = "abandono"
                c.motivo = "Colisão"
                self._msg(f"COLISÃO! {c.nome} toca em {alvo.nome} e abandona.")
                self._graves.append("colisao")
                del novos[c]
                return
            novos[c] += ev.rng.uniform(3, 10)
            if ev.rng.random() < 0.5:
                c.dano += ev.rng.uniform(0.001, 0.008)
            if ev.rng.random() < 0.3:
                alvo.dano += ev.rng.uniform(0.001, 0.005)
            self._msg(f"{c.nome} toca em {alvo.nome} na disputa e perde tempo.")
            return
        novos[c] = max(novos[c], novos[alvo] + gap_min * ev.rng.uniform(0.8, 1.6))

    def _retardatarios(self, novos, tempos):
        """Bandeira azul: quem leva uma volta perde tempo abrindo caminho; quem dá a volta também perde um pouco."""
        if len(novos) < 2:
            return
        ev = self.ev
        lider = min(novos, key=novos.get)
        ref = tempos[lider]
        lid_antes = lider.tempo_total
        for c in list(novos):
            if c is lider:
                continue
            k0 = int((c.tempo_total - lid_antes) // ref)
            k1 = int((novos[c] - novos[lider]) // ref)
            if k1 <= k0:
                continue
            novos[c] += ev.rng.uniform(0.5, 1.0)
            for x in novos:
                if x is c:
                    continue
                kx = int((novos[x] - novos[lider]) // ref)
                if kx < k1 and abs((novos[c] - novos[x]) - (k1 - kx) * ref) < 1.5:
                    novos[x] += ev.rng.uniform(0.1, 0.3)

    def simular_ate_o_fim(self):
        while not self.terminada:
            self.avancar_volta()

    def avancar(self, segundos):
        self.avancar_volta()


    # ---------------------------------------------------------------- resultado
    def _finalizar(self):
        """Fim da corrida. Não cumprir a parada obrigatória não gera penalidade de tempo: a consequência
        vem do desgaste do pneu (furo/abandono) ou da falta de combustível."""
        self.terminada = True
        ev = self.ev
        for c in self.correndo():
            c.status = "fim"
        classificados = sorted([c for c in ev.carros if c.status == "fim"], key=lambda c: c.tempo_total)
        abandonos = sorted([c for c in ev.carros if c.status == "abandono"], key=lambda c: -c.voltas)
        ordem = classificados + abandonos
        lider = classificados[0] if classificados else None
        if self.classificatoria:
            ev.grid = list(ordem)
            ev.pole = ordem[0] if ordem else None
            self.resultado = [{"pos": i, "carro": c, "pontos": ""} for i, c in enumerate(ordem, 1)]
            for i, c in enumerate(ordem, 1):
                c.posicao = i
            if lider:
                self._msg(f"BANDEIRADA! {lider.nome} vence e larga na pole.")
            return
        if regra_dois_compostos(ev.cat):
            self._punir_dois_compostos()
            classificados = sorted([c for c in ev.carros if c.status == "fim"], key=lambda c: c.tempo_total)
            abandonos = sorted([c for c in ev.carros if c.status == "abandono"], key=lambda c: -c.voltas)
            ordem = classificados + abandonos
            lider = classificados[0] if classificados else None
        pts = ev.cat["pontuacao"]
        tabela = pts.get("posicoes", [])
        resultado = []
        cancelada = getattr(self, "cancelada", False)
        mult = 1.0
        if getattr(self, "interrompida", False) and not cancelada:
            # término antecipado (chuva que não para, batida grave): pontos integrais a partir de
            # distancia_minima; abaixo, metade ou proporcionais à distância; sem volta completa, ninguém pontua
            ci = pts.get("corrida_interrompida") or {}
            voltas = max((c.voltas for c in classificados), default=0)
            frac = voltas / max(1, self.total_voltas)
            if voltas == 0:
                cancelada = self.cancelada = True
                self._msg("Nenhuma volta completa: a corrida não vale pontos.")
            elif frac < ci.get("distancia_minima", 0.5):
                mult = 0.5 if ci.get("pontos_parciais", "metade") == "metade" else frac
                self._msg(f"Corrida interrompida com {frac:.0%} da distância: "
                          + ("metade dos pontos." if mult == 0.5 and ci.get("pontos_parciais", "metade") == "metade"
                             else f"pontos proporcionais ({mult:.0%})."))
            else:
                self._msg(f"Corrida interrompida com {frac:.0%} da distância: pontuação integral.")
        for i, c in enumerate(ordem, 1):
            pontos = tabela[i - 1] if (c.status == "fim" and i <= len(tabela)) else 0
            if self.volta_mais_rapida and self.volta_mais_rapida[1] is c and c.status == "fim" and i <= len(tabela):
                pontos += pts.get("volta_mais_rapida", 0)
            if mult != 1.0:
                pontos = round(pontos * mult, 2)
                pontos = int(pontos) if pontos == int(pontos) else pontos
            if ev.pole is c:
                pontos += pts.get("pole", 0)
            if cancelada:
                pontos = 0
            c.posicao = i
            resultado.append({"pos": i, "carro": c, "pontos": pontos})
        self.resultado = resultado
        ev.resultado_corrida = resultado
        if lider and not cancelada:
            self._msg(f"BANDEIRADA! Vitória de {lider.nome} ({lider.equipe['nome']}).")
        if self.volta_mais_rapida:
            t, c, v = self.volta_mais_rapida
            self._msg(f"Volta mais rápida: {c.nome} – {tempo_volta(t)} (volta {v}).")

    def _punir_dois_compostos(self):
        """Regra dos dois compostos secos: quem terminou sem cumprir é desclassificado (penalidade 0) ou recebe
        os segundos de penalidade definidos na categoria."""
        ev = self.ev
        pen = float(ev.cat["regras_pitstop"].get("penalidade_dois_compostos_s", 0) or 0)
        if len([k for k in ev.compostos_disponiveis() if tipo_pneu(ev.cat, k) == "seco"]) < 2:
            return
        for c in ev.carros:
            if c.status != "fim" or cumpre_dois_compostos(ev.cat, c.compostos_usados | {c.pneu}):
                continue
            if pen > 0:
                c.tempo_total += pen
                self._msg(f"{c.nome} não usou dois compostos secos: {pen:.0f} s de penalidade.")
            else:
                c.status = "abandono"
                c.motivo = "Desclassificado"
                self._msg(f"{c.nome} é desclassificado: não usou dois compostos secos.")

    # ---------------------------------------------------------------- tela
    def descricao_progresso(self):
        v = min(self.volta_lider, self.total_voltas)
        txt = f"Volta {v}/{self.total_voltas} – {relogio(self.relogio)}"
        if self.tempo_maximo:
            txt += f" (máx. {relogio(self.tempo_maximo)})"
        return txt

    def linhas_classificacao(self):
        ev = self.ev
        if self.resultado:
            ordem = [r["carro"] for r in self.resultado]
            pontos = {r["carro"]: r["pontos"] for r in self.resultado}
        else:
            ordem = sorted(self.correndo(), key=lambda c: c.tempo_total) + \
                sorted([c for c in ev.carros if c.status == "abandono"], key=lambda c: -c.voltas)
            pontos = {}
        lider = ordem[0] if ordem else None
        media = (lider.tempo_total / max(1, lider.voltas)) if lider and lider.voltas else None
        linhas = []
        anterior = None
        for i, c in enumerate(ordem, 1):
            if c.status == "abandono":
                gap = c.motivo or "Abandono"
                intv = ""
            elif c is lider:
                gap = "Líder" if not self.terminada else relogio(c.tempo_total)
                intv = ""
            else:
                d = c.tempo_total - lider.tempo_total
                voltas_atras = int(d // media) if media else 0
                gap = f"+{voltas_atras} volta(s)" if voltas_atras >= 1 else f"+{d:.3f}"
                intv = f"+{c.tempo_total - anterior.tempo_total:.3f}" if anterior and anterior.status != "abandono" else ""
            linhas.append({"pos": i, "carro": c, "melhor": tempo_volta(c.melhor), "ultima": tempo_volta(c.ultima),
                           "gap": gap, "intervalo": intv, "voltas": c.voltas,
                           "pneu": ev.cat["pneus"]["compostos"][c.pneu]["nome"] if c.pneu else "-",
                           "desgaste": f"{c.desgaste:.0f}%", "paradas": c.paradas,
                           "grid": getattr(c, "grid", ""),
                           "status": {"pista": "", "abandono": "Abandono", "fim": "Fim"}.get(c.status, ""),
                           "pontos": pontos.get(c, "")})
            anterior = c
        return linhas
