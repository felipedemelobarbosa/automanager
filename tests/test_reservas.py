"""Piloto de testes (reserva): o jogador pode colocá-lo no carro; o PC usa a reserva numa vaga aberta se ela for boa."""
import copy
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, mercado, acoes, saude, multiplayer as mp  # noqa: E402

ALFA = "formula_alfa"


def jogo(eid="tucano", semente=4):
    st = state.novo_jogo(db.arquivos_do_ano(2026), semente=semente)
    if eid:
        state.escolher_equipe(st, ALFA, eid)
    else:
        st["usuario"] = {"categoria": None, "equipe": None}
    return st


def da_equipe(st, eid, sit):
    return [p for p in state.pilotos_da_equipe(st, ALFA, eid) if p["contrato"]["situacao"] == sit]


class TestJogador(unittest.TestCase):
    def setUp(self):
        self.st = jogo()
        self.eq = self.st["categorias"][ALFA]["equipes"]["tucano"]
        self.reserva = da_equipe(self.st, "tucano", "teste")[0]

    def promover(self, pid=None):
        return acoes.aplicar(self.st, "promover_piloto", {"piloto": pid or self.reserva["id"]})

    def test_no_lugar_do_lesionado_e_volta(self):
        titular = da_equipe(self.st, "tucano", "principal")[0]
        titular["lesao"] = {"corridas": 1, "ano": 2026, "evento": "x"}
        self.assertEqual(mercado.lesionado_sem_substituto(self.st, ALFA, "tucano")["id"], titular["id"])
        self.assertIsNone(self.promover())
        ct = self.reserva["contrato"]
        self.assertEqual((ct["situacao"], ct["situacao_original"], ct["substituto_de"]),
                         ("principal", "teste", titular["id"]))
        self.assertIsNone(mercado.lesionado_sem_substituto(self.st, ALFA, "tucano"))
        saude.fim_de_corrida(self.st, ALFA)                                     # ele se recupera
        self.assertEqual(self.reserva["contrato"]["situacao"], "teste")
        self.assertNotIn("substituto_de", self.reserva["contrato"])

    def test_vaga_aberta_em_definitivo(self):
        da_equipe(self.st, "tucano", "principal")[0]["contrato"] = None
        self.assertIsNone(self.promover())
        self.assertEqual(self.reserva["contrato"]["situacao"], "principal")
        self.assertNotIn("situacao_original", self.reserva["contrato"])
        self.assertEqual(mercado.vagas(self.st, ALFA, self.eq)[0], {"principal": 0, "teste": 1})

    def test_sem_vaga_e_titular_nao(self):
        self.assertIn("não tem vaga de titular", self.promover())
        titular = da_equipe(self.st, "tucano", "principal")[0]
        self.assertIn("piloto de testes", self.promover(titular["id"]))

    def test_multijogador_pelas_ordens(self):
        st = jogo(eid=None)
        mp.criar_liga(st, "Liga", [{"nome": "Ana", "categoria": ALFA, "equipe": "tucano", "senha": "a"}])
        for s in (st,):
            da_equipe(s, "tucano", "principal")[0]["contrato"] = None
        sj = mp.entrar(copy.deepcopy(mp.versao_jogadores(st)), "ana", "a")
        reserva = da_equipe(sj, "tucano", "teste")[0]
        self.assertIsNone(acoes.executar(sj, "promover_piloto", piloto=reserva["id"]))
        self.assertEqual(mp.importar_ordens(st, mp.ordens_da_sessao(sj)), "ana")
        mp.rodar_semana(st, random.Random(1))
        self.assertEqual(st["pilotos"][reserva["id"]]["contrato"]["situacao"], "principal")


class TestPC(unittest.TestCase):
    def test_promove_reserva_boa_e_vai_ao_mercado_com_reserva_fraca(self):
        for forte in (True, False):
            st = jogo(eid=None, semente=5)
            reserva = da_equipe(st, "vortex", "teste")[0]
            for k in reserva["atributos"]:
                reserva["atributos"][k] = 95 if forte else 20
            da_equipe(st, "vortex", "principal")[0]["contrato"] = None
            mercado.rotina_pilotos(st, random.Random(1))
            sit = reserva["contrato"]["situacao"]
            if forte:
                self.assertEqual(sit, "principal")
                self.assertTrue(any("promove o piloto de testes" in n["texto"] for n in st["noticias"]))
            else:
                self.assertEqual(sit, "teste")                                  # mercado, não a reserva fraca


if __name__ == "__main__":
    unittest.main()
