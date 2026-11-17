"""Clima: prob_chuva da pista = fração do tempo/sessões com chuva; mudanças um passo por vez."""
import collections
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager.event.clima import Clima  # noqa: E402

CFG = {"proporcao_chuva_forte": 0.35, "estabilidade_por_10min": 0.94, "efeitos": {}}


class TestClima(unittest.TestCase):
    def test_equilibrio_dentro_da_sessao(self):
        for p in (0.0, 0.1, 0.3, 0.6):
            c = Clima(CFG, p, random.Random(7))
            cont = collections.Counter()
            for _ in range(60000):
                c.avancar(600)
                cont[c.estado] += 1
            molhado = (cont["chuva_leve"] + cont["chuva_pesada"]) / 60000
            self.assertAlmostEqual(molhado, p, delta=0.03)

    def test_proporcao_de_chuva_forte(self):
        c = Clima(dict(CFG, estabilidade_por_10min=0.0), 0.4, random.Random(5))   # sem estabilidade: mistura rápido
        cont = collections.Counter()
        for _ in range(100000):
            c.avancar(600)
            cont[c.estado] += 1
        self.assertAlmostEqual(cont["chuva_pesada"] / (cont["chuva_leve"] + cont["chuva_pesada"]), 0.35, delta=0.02)

    def test_inicio_de_sessao(self):
        for p in (0.1, 0.3):
            molhadas = 0
            for k in range(4000):
                c = Clima(CFG, p, random.Random(k))
                for _ in range(4):                    # fim de semana: sessão, troca de sessão, 1 h de pista...
                    c.nova_sessao()
                    c.avancar(3600)
                molhadas += c.estado != "seco"
            self.assertAlmostEqual(molhadas / 4000, p, delta=0.03)

    def test_um_passo_por_vez(self):
        c = Clima(dict(CFG, estabilidade_por_10min=0.0), 0.5, random.Random(3))
        for _ in range(5000):
            antes = c.estado
            c.avancar(600)
            self.assertFalse({antes, c.estado} == {"seco", "chuva_pesada"})

    def test_estabilidade_total_nao_muda(self):
        c = Clima(dict(CFG, estabilidade_por_10min=1.0), 0.5, random.Random(3))
        e = c.estado
        self.assertFalse(c.avancar(6 * 3600))
        self.assertEqual(c.estado, e)


if __name__ == "__main__":
    unittest.main()
