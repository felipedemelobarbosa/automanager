"""Feedback do piloto sobre o acerto: treinos e classificação; o acerto vale da 1ª sessão até a corrida."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, i18n  # noqa: E402
from automanager.event.inscritos import montar_inscritos  # noqa: E402
from automanager.event.sessoes import Evento, SessaoCorrida  # noqa: E402


def evento():
    st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
    state.escolher_equipe(st, "formula_alfa", "tucano")
    c = st["categorias"]["formula_alfa"]
    pista = dict(next(e for e in c["calendario"] if e["especie"] == "corrida"), prob_chuva=0)
    return Evento(c["categoria"], pista, montar_inscritos(st, "formula_alfa", "tucano", pista), random.Random(1))


class TestFeedback(unittest.TestCase):
    def tearDown(self):
        i18n.definir("pt")

    def test_feedback_no_treino_e_na_classificacao_acerto_mantido(self):
        ev = evento()
        meu = next(c for c in ev.carros if c.usuario)
        acerto = {"aerodinamica": 5, "cambio": 95, "suspensao": 5, "freios": 95}
        meu.acerto = dict(acerto)
        por_sessao = {}
        while ev.proxima_sessao():
            ev.preparar_ia()
            ev.sessao.iniciar()
            self.assertEqual(meu.acerto, acerto)                       # mantido da 1ª sessão até a corrida
            if isinstance(ev.sessao, SessaoCorrida):
                break
            ev.sessao.simular_ate_o_fim()
            por_sessao[ev.sessao.tipo] = [m for m in ev.sessao.log if "(sua equipe)" in m]
        self.assertTrue(por_sessao["treino"])
        self.assertTrue(por_sessao["classificacao"])

    def test_feedback_guardado_no_carro(self):
        ev = evento()
        meu = next(c for c in ev.carros if c.usuario)
        meu.acerto = {"aerodinamica": 5, "cambio": 50, "suspensao": 50, "freios": 50}
        ev.proxima_sessao()
        ev.preparar_ia()
        ev.sessao.iniciar()
        ev.sessao.simular_ate_o_fim()
        fb = meu.feedback
        self.assertEqual(fb["sessao"], ev.sessao.nome)
        self.assertEqual(fb["acerto"], meu.acerto)                       # o acerto que o piloto testou
        self.assertEqual(set(fb["diffs"]), {"aerodinamica", "cambio", "suspensao", "freios"})
        self.assertIn(fb["nota"], range(1, 6))
        self.assertGreater(fb["diffs"]["aerodinamica"], 0)               # asa no mínimo: pede mais asa
        self.assertTrue(any(fb["texto"] in m for m in ev.sessao.log))
        outro = next(c for c in ev.carros if not c.usuario)
        self.assertIsNone(outro.feedback)                               # só a equipe do jogador

    def test_frase_traduzida_por_inteiro(self):
        txt = "[0:12:30] Ana (sua equipe) pede um pouco mais asa, bem relação mais curta, freios menos agressivos."
        i18n.definir("en")
        self.assertEqual(i18n.t(txt), "[0:12:30] Ana (your team) asks for a little more wing, much shorter gearing, "
                                      "less aggressive brakes.")
        i18n.definir("es")
        self.assertIn("pide un poco más de alerón, relación mucho más corta", i18n.t(txt))


if __name__ == "__main__":
    unittest.main()
