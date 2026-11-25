"""Modelo de volta e corrida: dispersão unilateral, forma, chuva, motor/cota, lastro, dano, safety car,
emborrachamento, tráfego na classificação, ar sujo e retardatários."""
import copy
import os
import random
import statistics as S
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import state, db  # noqa: E402
from automanager.event.sessoes import Evento, SessaoCorrida  # noqa: E402
from automanager.event.inscritos import montar_inscritos  # noqa: E402

CID = "formula_alfa"


def base():
    st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
    c = st["categorias"][CID]
    pista = dict(next(e for e in c["calendario"] if e["especie"] == "corrida" and e["tipo_pista"] == "mista"),
                 prob_chuva=0.0)
    return st, c, pista


def evento(st, c, pista, seed=1, cat=None):
    return Evento(cat or c["categoria"], pista, montar_inscritos(st, CID, None, pista), random.Random(seed))


class TestModelo(unittest.TestCase):
    def setUp(self):
        self.st, self.c, self.pista = base()

    def test_dispersao_unilateral(self):
        ev = evento(self.st, self.c, self.pista)
        ev.proxima_sessao()
        car = ev.carros[0]
        car.pneu = list(self.c["categoria"]["pneus"]["compostos"])[0]
        out = {}
        for cons in (30, 100):
            car.piloto = dict(car.piloto, atributos=dict(car.piloto["atributos"], consistencia=cons, concentracao=100))
            car._cache.clear()
            ev.modelo.rng = random.Random(3)
            out[cons] = min(ev.modelo.volta(car, "classificacao", ev.clima, 1.0)[0] for _ in range(2000))
        # o melhor tempo possível é o mesmo piso: o inconsistente nunca fica melhor que o consistente
        self.assertGreaterEqual(out[30], out[100] - 0.01)

    def test_forma_persiste_entre_eventos(self):
        evento(self.st, self.c, self.pista, 1)
        p = next(iter(self.st["pilotos"].values()))
        self.assertIn("forma", p)

    def test_motor_alem_da_cota_perde_grid(self):
        cat = copy.deepcopy(self.c["categoria"])
        cat["regras"]["motores_por_temporada"] = 1
        cat["simulacao"]["vida_motor_voltas"] = 100
        ins = montar_inscritos(self.st, CID, None, self.pista)
        alvo = ins[0]
        alvo["equipe"]["motores"] = {alvo["piloto"]["id"]: {"uso": 95.0, "usados": 1}}
        ev = Evento(cat, self.pista, ins, random.Random(2))
        car = next(c for c in ev.carros if c.id == alvo["piloto"]["id"])
        self.assertEqual(car.penalidade_grid, 10)
        self.assertEqual(car.uso_motor, 0.0)
        self.assertTrue(any("cota" in n for n in ev.notas))

    def test_lastro_deixa_mais_lento(self):
        ev = evento(self.st, self.c, self.pista)
        ev.proxima_sessao()
        car = ev.carros[0]
        car.pneu = list(self.c["categoria"]["pneus"]["compostos"])[0]
        t0 = ev.modelo.ritmo(car, "corrida", ev.clima, 1.0)
        car.lastro = 50
        self.assertGreater(ev.modelo.ritmo(car, "corrida", ev.clima, 1.0), t0)

    def test_chuva_cubica(self):
        ev = evento(self.st, self.c, self.pista)
        ev.proxima_sessao()
        car = ev.carros[0]
        car.pneu = list(self.c["categoria"]["pneus"]["compostos"])[0]

        class Cl:
            estado = "chuva_pesada"
            intensidade = 1.0
            efeitos = self.c["categoria"]["clima"]["efeitos"]["chuva_pesada"]
        tempos = []
        for q in (20, 50, 80):
            car.piloto = dict(car.piloto, atributos=dict(car.piloto["atributos"], chuva=q))
            car.chassis = dict(car.chassis, chuva=q)
            car._cache.clear()
            tempos.append(ev.modelo.ritmo(car, "corrida", Cl, 1.0))
        # perda cresce mais que linearmente quanto pior no molhado
        self.assertGreater(tempos[0] - tempos[1], tempos[1] - tempos[2])

    def test_emborrachamento_e_chuva(self):
        ev = evento(self.st, self.c, self.pista)
        self.assertEqual(ev.evolucao(), 0.0)
        ev.voltas_pista = 400
        e1 = ev.evolucao()
        self.assertGreater(e1, 0.6)
        ev.lavar_pista(0.5)
        self.assertLess(ev.evolucao(), e1)


class TestCorrida(unittest.TestCase):
    def setUp(self):
        self.st, self.c, self.pista = base()

    def _corrida(self, seed, cat=None):
        ev = evento(self.st, self.c, self.pista, seed, cat)
        while ev.proxima_sessao():
            ev.sessao.iniciar()
            if isinstance(ev.sessao, SessaoCorrida):
                return ev
            ev.sessao.simular_ate_o_fim()

    def test_safety_car_agrupa_e_barateia_parada(self):
        ev = self._corrida(4)
        s = ev.sessao
        for _ in range(20):
            s.avancar_volta()
        s.sc = {"tipo": "SC", "voltas": 3}
        antes = sorted(c.tempo_total for c in s.correndo())
        espalhamento0 = antes[-1] - antes[0]
        for _ in range(3):
            s.avancar_volta()
        depois = sorted(c.tempo_total for c in s.correndo())
        self.assertLess(depois[-1] - depois[0], espalhamento0)
        self.assertIsNone(s.sc)

    def test_dano_reparado_no_box(self):
        ev = self._corrida(5)
        s = ev.sessao
        car = s.grid[3]
        car.dano = 0.01
        for _ in range(3):
            s.avancar_volta()
            if car.dano == 0:
                break
        self.assertEqual(car.dano, 0.0)
        self.assertGreaterEqual(car.paradas, 1)

    def test_corridas_terminam_com_estatisticas_plausiveis(self):
        ult, dnf = [], []
        for seed in range(6):
            ev = self._corrida(seed)
            ev.sessao.simular_ate_o_fim()
            ult.append(sum(1 for m in ev.sessao.log if "ultrapassa" in m))
            dnf.append(sum(1 for r in ev.resultado_corrida if r["carro"].status != "fim"))
        self.assertTrue(10 <= S.mean(ult) <= 60, ult)
        self.assertLessEqual(S.mean(dnf), 6)


if __name__ == "__main__":
    unittest.main()
