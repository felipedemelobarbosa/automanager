"""Clima do evento: seco / chuva leve / chuva forte.

`prob_chuva` da pista = fração das sessões (e do tempo de pista) com chuva, a longo prazo. Cada sessão começa
mantendo o clima da anterior (50%) ou sorteando de novo por prob_chuva. Dentro da sessão, a cada 10 minutos
simulados há (1 − estabilidade) de chance de o clima tentar mudar, sempre um passo por vez
(seco ↔ chuva leve ↔ chuva forte); a mudança é aceita na proporção certa (Metropolis) para que o equilíbrio
continue sendo: seco 1 − p, chuva leve p·(1 − proporcao_chuva_forte), chuva forte p·proporcao_chuva_forte.
Assim a chuva não "gruda": a estabilidade só controla com que frequência o clima muda.
"""

ESTADOS = ("seco", "chuva_leve", "chuva_pesada")
NOMES = {"seco": "Seco", "chuva_leve": "Chuva leve", "chuva_pesada": "Chuva forte"}
INTENSIDADE = {"seco": 0.0, "chuva_leve": 0.5, "chuva_pesada": 1.0}
PNEU_IDEAL = {"seco": "seco", "chuva_leve": "chuva_leve", "chuva_pesada": "chuva_pesada"}


class Clima:
    def __init__(self, cfg_clima, prob_chuva, rng):
        self.cfg = cfg_clima
        self.prob_chuva = float(prob_chuva)
        self.prop_forte = cfg_clima.get("proporcao_chuva_forte", 0.35)
        self.estabilidade = cfg_clima.get("estabilidade_por_10min", 0.94)
        self.rng = rng
        self.estado = self._sortear()
        self._acumulado = 0.0
        self.mudancas = []  # mensagens para o log

    def _sortear(self):
        if self.rng.random() < self.prob_chuva:
            return "chuva_pesada" if self.rng.random() < self.prop_forte else "chuva_leve"
        return "seco"

    def nova_sessao(self):
        """Entre sessões o clima pode se manter ou ser sorteado de novo."""
        if self.rng.random() < 0.5:
            self.estado = self._sortear()
        self._acumulado = 0.0

    def _equilibrio(self):
        p = min(1.0, max(0.0, self.prob_chuva))
        return {"seco": 1 - p, "chuva_leve": p * (1 - self.prop_forte), "chuva_pesada": p * self.prop_forte}

    def _passo(self):
        """Um passo da cadeia: propõe um vizinho (chuva leve escolhe seco ou forte meio a meio; seco e forte só
        têm um vizinho, proposto com 1/2) e aceita com min(1, π(novo)/π(atual))."""
        pi = self._equilibrio()
        vizinhos = {"seco": ("chuva_leve",), "chuva_leve": ("seco", "chuva_pesada"), "chuva_pesada": ("chuva_leve",)}
        r = self.rng.random()
        opcoes = vizinhos[self.estado]
        if r >= 0.5 * len(opcoes):
            return self.estado                          # seco/forte: metade das vezes nem propõe
        novo = opcoes[int(r / 0.5)]
        atual = pi[self.estado]
        if atual <= 0 or self.rng.random() < min(1.0, pi[novo] / atual):
            return novo
        return self.estado

    def avancar(self, segundos):
        """Avança o tempo simulado. Retorna True se o clima mudou."""
        self._acumulado += segundos
        mudou = False
        while self._acumulado >= 600:
            self._acumulado -= 600
            if self.rng.random() < self.estabilidade:
                continue
            anterior = self.estado
            self.estado = self._passo()
            if self.estado != anterior:
                mudou = True
                self.mudancas.append(f"Clima: {NOMES[anterior]} -> {NOMES[self.estado]}")
        return mudou

    @property
    def efeitos(self):
        return self.cfg["efeitos"][self.estado]

    @property
    def intensidade(self):
        return INTENSIDADE[self.estado]

    @property
    def nome(self):
        return NOMES[self.estado]
