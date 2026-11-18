"""Renda de TV (ano de início, classificação final da temporada anterior) e prêmios por corrida."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, economia, routines  # noqa: E402

CID = "formula_alfa"


class TestPremiosTV(unittest.TestCase):
    def setUp(self):
        self.st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
        self.c = self.st["categorias"][CID]
        self.regras = self.c["categoria"]["regras"]
        self.ids = [e for e, x in self.c["equipes"].items() if x.get("ativa")]

    def test_tv_ano_inicio(self):
        self.assertTrue(economia.tv_ativa(self.st, self.c["categoria"]))
        self.regras["renda_tv"]["ano_inicio"] = 2027
        self.assertFalse(economia.tv_ativa(self.st, self.c["categoria"]))
        eq = self.c["equipes"][self.ids[0]]
        routines._financas_corrida(self.st, CID, eq)
        self.assertEqual(eq["financas"]["ano"]["receitas"].get("tv", 0), 0)
        self.st["ano"] = 2027
        self.assertTrue(economia.tv_ativa(self.st, self.c["categoria"]))

    def test_tv_pela_classificacao_final_do_ano_anterior(self):
        fatores = self.regras["renda_tv"]["fator_por_posicao_campeonato"]
        self.assertEqual(economia.fator_tv(self.st, CID, self.ids[0]), 1.0)      # 1º ano: todas iguais
        ordem = list(reversed(self.ids))
        self.st.setdefault("temporadas", {})["2026"] = {CID: {"final": {"equipes": [{"id": e} for e in ordem[:-1]]}}}
        self.st["ano"] = 2027
        self.assertEqual(economia.fator_tv(self.st, CID, ordem[0]), fatores[0])
        self.assertEqual(economia.fator_tv(self.st, CID, ordem[1]), fatores[1])
        self.assertEqual(economia.fator_tv(self.st, CID, ordem[-1]), fatores[-1])  # fora da classificação: último
        eq = self.c["equipes"][ordem[0]]
        routines._financas_corrida(self.st, CID, eq)
        n = routines.corridas_na_temporada(self.c)
        self.assertAlmostEqual(eq["financas"]["ano"]["receitas"]["tv"],
                               self.regras["renda_tv"]["valor_medio_por_equipe"] / n * fatores[0])

    def test_premios_por_corrida(self):
        p = self.regras["premios_corrida"]
        a, b, c = self.ids[:3]
        reg = {"resultado": [{"pos": 1, "equipe": a, "pontos": 25}, {"pos": 2, "equipe": b, "pontos": 18},
                             {"pos": 3, "equipe": a, "pontos": 15}, {"pos": 11, "equipe": c, "pontos": 0}]}
        economia.pagar_premios(self.st, CID, reg)
        rec = lambda e: self.c["equipes"][e]["financas"]["ano"]["receitas"].get("premios", 0)
        self.assertEqual(rec(a), p["vitoria"] + 2 * p["podio"] + 40 * p["por_ponto"])
        self.assertEqual(rec(b), p["podio"] + 18 * p["por_ponto"])
        self.assertEqual(rec(c), 0)
        economia.pagar_premios(self.st, CID, dict(reg, cancelada=True))           # corrida cancelada: nada
        self.assertEqual(rec(b), p["podio"] + 18 * p["por_ponto"])
        self.regras["premios_corrida"]["ativa"] = False
        economia.pagar_premios(self.st, CID, reg)
        self.assertEqual(rec(b), p["podio"] + 18 * p["por_ponto"])

    def test_temporada_paga_premios_e_entra_na_previsao(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=2)
        st["usuario"] = {"categoria": None, "equipe": None}
        c = st["categorias"][CID]
        eq = next(e for e in c["equipes"].values() if e.get("ativa"))
        sem_premio = dict(c["categoria"]["regras"]["premios_corrida"], ativa=False)
        com = economia.receita_prevista(st, CID, eq)
        c["categoria"]["regras"]["premios_corrida"], guardado = sem_premio, c["categoria"]["regras"]["premios_corrida"]
        self.assertLess(economia.receita_prevista(st, CID, eq), com)
        c["categoria"]["regras"]["premios_corrida"] = guardado
        rng = random.Random(1)
        while not any(r.get("resultado") for r in st.get("temporadas", {}).get("2026", {}).get(CID, {}).get("corridas", [])):
            routines.avancar_semana(st, rng)
        total = sum(e["financas"]["ano"]["receitas"].get("premios", 0) for e in c["equipes"].values())
        # a previsão conta todos os pontos possíveis; o da volta mais rápida pode não ser dado (fora do top 10)
        por_ponto = c["categoria"]["regras"]["premios_corrida"]["por_ponto"]
        self.assertAlmostEqual(total, economia.premio_total_por_corrida(c["categoria"]), delta=2 * por_ponto)


if __name__ == "__main__":
    unittest.main()
