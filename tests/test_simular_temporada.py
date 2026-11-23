"""Simular temporada: a IA conduz a equipe do jogador (desenvolvimento, contratos, pilotos, finanças), mas ela
continua sendo dele – não fecha por sorteio e a falência encerra o jogo."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, routines, campeonato, economia  # noqa: E402

ALFA = "formula_alfa"


def jogo():
    st = state.novo_jogo(db.arquivos_do_ano(2026), semente=4)
    state.escolher_equipe(st, ALFA, "tucano")
    return st


def simular(st, rng):
    """O que o botão Simular temporada faz (sem a tela)."""
    ano = st["ano"]
    st["ia_conduz_usuario"] = True
    try:
        while st["ano"] == ano:
            pista = routines.corrida_do_usuario_na_semana(st)
            if pista:
                campeonato.simular_em_segundo_plano(st, ALFA, pista, rng)
            routines.avancar_semana(st, rng)
    finally:
        st.pop("ia_conduz_usuario", None)


class TestSimularTemporada(unittest.TestCase):
    def test_ia_conduz_e_devolve_a_equipe(self):
        st = jogo()
        self.assertEqual(state.humanas(st), {(ALFA, "tucano")})
        simular(st, random.Random(4))
        self.assertEqual(st["ano"], 2027)
        self.assertEqual(state.humanas(st), {(ALFA, "tucano")})                 # de volta ao jogador
        c = st["categorias"][ALFA]
        eq = c["equipes"]["tucano"]
        self.assertTrue(eq.get("ativa"))
        self.assertTrue((eq.get("motor") or {}).get("id"))                       # contrato de motor renovado
        titulares = [p for p in state.pilotos_da_equipe(st, ALFA, "tucano") if p["contrato"]["situacao"] == "principal"]
        self.assertEqual(len(titulares), 2)
        self.assertGreater(c["historico_financas"]["tucano"]["2026"]["despesas"].get("desenvolvimento", 0), 0)
        corridas = st["temporadas"]["2026"][ALFA]["corridas"]
        self.assertTrue(all(sum(1 for x in r["resultado"] if x["equipe"] == "tucano") == 2 for r in corridas))

    def test_continua_sendo_do_jogador(self):
        st = jogo()
        st["ia_conduz_usuario"] = True
        self.assertEqual(state.humanas(st), set())
        self.assertTrue(state.eh_da_pessoa(st, ALFA, "tucano"))
        eq = st["categorias"][ALFA]["equipes"]["tucano"]
        eq["prob_fechamento"] = 1.0
        routines._virada_equipes(st, ALFA, random.Random(1))
        self.assertTrue(eq.get("ativa"))                                          # não fecha por sorteio
        economia.falir(st, ALFA, eq)
        self.assertEqual(st["fim_de_jogo"]["motivo"], "falencia")               # falência encerra o jogo


if __name__ == "__main__":
    unittest.main()
