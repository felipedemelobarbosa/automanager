"""Tempo base das pistas por ano: informado no editor (tempos_por_ano) ou pela evolução automática."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, routines, tempo_base, regulamento  # noqa: E402

CID = "formula_alfa"


class TestTempoBase(unittest.TestCase):
    def setUp(self):
        self.st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
        self.c = self.st["categorias"][CID]
        self.ev = next(e for e in self.c["calendario"] if e["especie"] == "corrida")
        self.t0 = (self.ev["tempo_base_treino"], self.ev["tempo_base_corrida"])
        self.c["categoria"]["regulamento"]["prob_grande_mudanca"] = 0.0

    def virar(self, grande=False):
        r = regulamento.estado(self.c)
        if grande:
            r["anuncio"] = {"ano": self.st["ano"] + 1, "mudancas": [{"tipo": "grande", "perda": 0.0,
                                                                     "importancia_carro": 0.6}]}
        self.st["ano"] += 1
        tempo_base.virada(self.st, CID)
        regulamento.virada(self.st, CID)
        return self.ev["tempo_base_treino"], self.ev["tempo_base_corrida"]

    def test_evolucao_automatica(self):
        t1 = self.virar()
        self.assertAlmostEqual(t1[0], round(self.t0[0] * 0.988, 3))
        t2 = self.virar(grande=True)                      # grande mudança: +3%
        self.assertAlmostEqual(t2[1], round(self.t0[1] * 0.988 * 1.03, 3))

    def test_sem_regulamento(self):
        self.c["categoria"]["regulamento"]["ativo"] = False
        self.assertAlmostEqual(self.virar()[0], round(self.t0[0] * 0.998, 3))

    def test_desligada(self):
        self.c["categoria"]["evolucao_tempo_base"] = {"ativa": False}
        self.assertEqual(self.virar(), self.t0)

    def test_anos_informados_e_evolucao_a_partir_deles(self):
        self.ev["tempos_por_ano"] = {"2028": [80.0, 82.0]}
        self.virar()                                       # 2027: evolução a partir do arquivo
        self.assertEqual(self.virar(), (80.0, 82.0))       # 2028: informado
        self.assertEqual(self.virar(), (round(80.0 * 0.988, 3), round(82.0 * 0.988, 3)))   # 2029: a partir de 2028

    def test_temporadas_completas(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=2)
        st["usuario"] = {"categoria": None, "equipe": None}
        ev = next(e for e in st["categorias"][CID]["calendario"] if e["especie"] == "corrida")
        t0 = ev["tempo_base_corrida"]
        rng = random.Random(1)
        while st["ano"] < 2028:
            routines.avancar_semana(st, rng)
        fator = st["categorias"][CID]["evolucao_tempo"]["fator"]
        self.assertEqual(set(fator), {"2026", "2027", "2028"})
        self.assertAlmostEqual(ev["tempo_base_corrida"], round(t0 * fator["2028"], 3))

    def test_validacao(self):
        d = db.carregar_arquivo(db.arquivos_do_ano(2026)[0], validar=False)
        ev = next(e for e in d["calendario"] if e["especie"] == "corrida")
        ev["tempos_por_ano"] = {"2028": [88.4, 90.1]}
        self.assertEqual(db.validar_dados(d), [])
        ev["tempos_por_ano"] = {"2026": [88.4, 90.1]}
        self.assertTrue(any("depois de 2026" in e for e in db.validar_dados(d)))
        ev["tempos_por_ano"] = {"2028": [88.4]}
        self.assertTrue(any("tempos_por_ano" in e for e in db.validar_dados(d)))


if __name__ == "__main__":
    unittest.main()
