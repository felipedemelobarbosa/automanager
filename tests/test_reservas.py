"""Piloto de testes (reserva): o jogador pode colocá-lo no carro; o PC usa a reserva numa vaga aberta se ela for boa."""
import copy
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, mercado, acoes, saude, routines, multiplayer as mp  # noqa: E402

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


class TestPromocaoSoNestaTemporada(unittest.TestCase):
    """Reserva assume uma vaga livre no meio da temporada (morte, saída) quando a próxima já tem titulares."""

    def preparar(self, eid="vortex", user=None, futuros=2):
        st = jogo(eid=user, semente=8)
        ano = st["ano"]
        tit = da_equipe(st, eid, "principal")
        reserva = da_equipe(st, eid, "teste")[0]
        reserva["idade"] = 22
        reserva["contrato"].update(temporadas=2, inicio_ano=ano)
        reserva["contrato"].pop("corridas", None)
        for p in tit:
            p["contrato"].update(temporadas=1)
            p["contrato"].pop("corridas", None)
            p["idade"] = 25
        livres = [p for p in st["pilotos"].values() if not p.get("contrato") and not p.get("contrato_futuro")
                  and not p.get("lesao")][:futuros]
        for p in livres:
            p["idade"] = 25
            p["contrato_futuro"] = {"categoria": ALFA, "equipe": eid, "situacao": "principal", "inicio_ano": ano + 1,
                                    "temporadas": 1, "valor_por_corrida": 1}
        return st, tit, reserva, livres

    def test_morte_reserva_fica_ate_o_fim_e_volta(self):
        st, tit, reserva, livres = self.preparar()
        eq = st["categorias"][ALFA]["equipes"]["vortex"]
        saude.falecer(st, ALFA, tit[0])
        ct = reserva["contrato"]
        self.assertEqual((ct["situacao"], ct["reserva_ate"]), ("principal", st["ano"]))
        self.assertEqual(mercado.vagas_no_ano(st, ALFA, eq, st["ano"] + 1)["principal"], 0)
        routines.nova_temporada(st, random.Random(1))
        self.assertEqual(reserva["contrato"]["situacao"], "teste")
        self.assertNotIn("reserva_ate", reserva["contrato"])
        self.assertEqual(sorted(p["id"] for p in da_equipe(st, "vortex", "principal")),
                         sorted(p["id"] for p in livres))

    def test_proxima_temporada_com_vaga_e_definitivo(self):
        st, tit, reserva, _ = self.preparar(futuros=1)
        saude.falecer(st, ALFA, tit[0])
        self.assertEqual(reserva["contrato"]["situacao"], "principal")
        self.assertNotIn("reserva_ate", reserva["contrato"])
        routines.nova_temporada(st, random.Random(1))
        self.assertEqual(reserva["contrato"]["situacao"], "principal")

    def test_jogador_promove_e_e_avisado(self):
        st, tit, reserva, _ = self.preparar(eid="tucano", user="tucano")
        tit[0]["contrato"] = None
        self.assertIsNone(acoes.aplicar(st, "promover_piloto", {"piloto": reserva["id"]}))
        self.assertEqual(reserva["contrato"]["reserva_ate"], st["ano"])
        self.assertTrue(any("até o fim da temporada" in n["texto"] for n in st["noticias"]))


class TestCadeiaDeSubstitutos(unittest.TestCase):
    """O substituto de um titular lesionado também se lesiona e outra reserva entra no lugar dele."""

    def setUp(self):
        self.st = jogo(eid=None, semente=7)
        self.titular = da_equipe(self.st, "vortex", "principal")[0]
        self.r1 = da_equipe(self.st, "vortex", "teste")[0]
        self.r2 = next(p for p in self.st["pilotos"].values() if not p.get("contrato") and not p.get("lesao"))
        self.r2["contrato"] = {"categoria": ALFA, "equipe": "vortex", "situacao": "teste", "valor_por_corrida": 1,
                               "temporadas": 1}
        for k in self.r1["atributos"]:                  # a reserva 1 é a melhor: entra primeiro
            self.r1["atributos"][k] = 90
        rng = random.Random(1)
        saude.lesionar(self.st, ALFA, self.titular, rng)
        saude.lesionar(self.st, ALFA, self.r1, rng)

    def corridas(self, titular, r1):
        self.titular["lesao"]["corridas"], self.r1["lesao"]["corridas"] = titular, r1

    def em_condicoes(self):
        return [p["id"] for p in da_equipe(self.st, "vortex", "principal") if not p.get("lesao")]

    def test_cadeia_montada(self):
        self.assertEqual(self.r1["contrato"]["substituto_de"], self.titular["id"])
        self.assertEqual(self.r2["contrato"]["substituto_de"], self.r1["id"])
        self.assertEqual(len(self.em_condicoes()), 2)

    def test_titular_volta_primeiro_os_dois_voltam_a_reserva(self):
        self.corridas(1, 5)
        saude.fim_de_corrida(self.st, ALFA)
        self.assertEqual((self.r1["contrato"]["situacao"], self.r2["contrato"]["situacao"]), ("teste", "teste"))
        self.assertNotIn("substituto_de", self.r2["contrato"])
        self.assertIn(self.titular["id"], self.em_condicoes())
        self.assertEqual(len(self.em_condicoes()), 2)

    def test_substituto_volta_primeiro_e_a_segunda_reserva_sai(self):
        self.corridas(5, 1)
        saude.fim_de_corrida(self.st, ALFA)
        self.assertEqual(self.r2["contrato"]["situacao"], "teste")
        self.assertEqual(self.r1["contrato"]["substituto_de"], self.titular["id"])
        self.assertEqual(len(self.em_condicoes()), 2)
        self.titular["lesao"]["corridas"] = 1
        saude.fim_de_corrida(self.st, ALFA)
        self.assertEqual(self.r1["contrato"]["situacao"], "teste")
        self.assertEqual(len(self.em_condicoes()), 2)

    def test_substituto_morre_e_a_segunda_reserva_herda_a_vaga(self):
        saude.falecer(self.st, ALFA, self.r1)
        self.assertEqual(self.r2["contrato"]["substituto_de"], self.titular["id"])
        self.assertEqual(len(self.em_condicoes()), 2)
        self.titular["lesao"]["corridas"] = 1
        saude.fim_de_corrida(self.st, ALFA)
        self.assertEqual(self.r2["contrato"]["situacao"], "teste")
        self.assertEqual(len(self.em_condicoes()), 2)

    def test_titular_deixa_a_equipe_na_virada(self):
        self.titular["contrato"] = None
        saude.substitutos_sem_titular(self.st)
        for r in (self.r1, self.r2):
            self.assertEqual(r["contrato"]["situacao"], "teste")
            self.assertNotIn("substituto_de", r["contrato"])


if __name__ == "__main__":
    unittest.main()
