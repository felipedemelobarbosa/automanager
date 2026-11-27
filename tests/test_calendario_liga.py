"""Multijogador: o comissário define o calendário da próxima temporada."""
import copy
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, routines, calendario_liga as cl, multiplayer as mp  # noqa: E402

ALFA = "formula_alfa"


def liga():
    st = state.novo_jogo(db.arquivos_do_ano(2026), semente=4)
    mp.criar_liga(st, "Liga", [{"nome": "Ana", "categoria": ALFA, "senha": "a", "equipe": "tucano"}])
    return st


def por_id(eventos):
    return {e["id"]: e for e in eventos}


class TestCalendarioDoComissario(unittest.TestCase):
    def setUp(self):
        self.st = liga()
        self.cal = copy.deepcopy(self.st["categorias"][ALFA]["calendario"])
        self.corridas = [e for e in self.cal if e["especie"] == "corrida" and e.get("ativo")]

    def test_validacao(self):
        cal = copy.deepcopy(self.cal)
        cal[3]["semana"] = cal[4]["semana"]
        self.assertIn("mesma semana", cl.definir(self.st, ALFA, cal))
        cal = copy.deepcopy(self.cal)
        for e in cal:
            if e["especie"] == "corrida":
                e["ativo"] = False
        self.assertIn("pelo menos uma corrida", cl.definir(self.st, ALFA, cal))
        cal = copy.deepcopy(self.cal)
        cal[1]["id"] = cal[0]["id"]
        self.assertIn("repetido", cl.definir(self.st, ALFA, cal))
        self.assertIsNone(cl.proximo(self.st, ALFA))

    def test_salvo_e_publicado_para_os_jogadores(self):
        self.assertIsNone(cl.definir(self.st, ALFA, self.cal))
        self.assertEqual(cl.proximo(self.st, ALFA)["ano"], self.st["ano"] + 1)
        self.assertTrue(any("definido pelo comissário" in n["texto"] for n in self.st["noticias"]))
        sj = mp.entrar(copy.deepcopy(mp.versao_jogadores(self.st)), "ana", "a")
        self.assertEqual(len(cl.proximo(sj, ALFA)["eventos"]), len(self.cal))

    def test_virada_usa_o_calendario_do_comissario(self):
        st = self.st
        ano = st["ano"] + 1
        cal = copy.deepcopy(self.cal)
        fora, mudada = self.corridas[0], self.corridas[1]
        por_id(cal)[fora["id"]]["ativo"] = False
        por_id(cal)[mudada["id"]]["semana"] = 51
        por_id(cal)[mudada["id"]]["prob_inativar"] = 1.0       # sem sorteio: continua no calendário
        nova = dict(copy.deepcopy(fora), id="ev_nova", nome="GP Novo", local="Recife, Brasil", semana=52, ativo=True,
                    tempo_base_treino=80.0, tempo_base_corrida=82.0)
        nova.pop("tempo_base_arquivo", None)
        cal.append(nova)
        self.assertIsNone(cl.definir(st, ALFA, cal))
        # referência: mesma liga sem calendário definido, para a evolução dos tempos
        ref = liga()
        routines.nova_temporada(ref, random.Random(1))
        routines.nova_temporada(st, random.Random(1))
        self.assertEqual(st["ano"], ano)
        novo = por_id(st["categorias"][ALFA]["calendario"])
        self.assertFalse(novo[fora["id"]]["ativo"])
        self.assertTrue(novo[mudada["id"]]["ativo"])
        self.assertEqual(novo[mudada["id"]]["semana"], 51)
        self.assertEqual((novo["ev_nova"]["tempo_base_treino"], novo["ev_nova"]["tempo_base_corrida"]), (80.0, 82.0))
        outra = self.corridas[2]["id"]                         # tempo não mexido: evolui como sem o comissário
        r = por_id(ref["categorias"][ALFA]["calendario"])[outra]
        self.assertEqual(novo[outra]["tempo_base_corrida"], r["tempo_base_corrida"])
        self.assertIsNone(cl.proximo(st, ALFA))                # usado: sai da fila
        self.assertTrue(any("calendário definido pelo comissário" in n["texto"] for n in st["noticias"]))
        routines.nova_temporada(st, random.Random(2))          # e a pista nova continua evoluindo depois
        self.assertLess(por_id(st["categorias"][ALFA]["calendario"])["ev_nova"]["tempo_base_corrida"], 82.0 + 3)

    def test_sem_calendario_definido_segue_o_sorteio(self):
        st = self.st
        reserva = next(e for e in st["categorias"][ALFA]["calendario"] if not e.get("ativo")
                       and not e.get("anos_entrada"))
        reserva["prob_ativar"] = 1.0
        self.assertIsNone(cl.definir(st, ALFA, copy.deepcopy(st["categorias"][ALFA]["calendario"])))
        cl.limpar(st, ALFA)                                    # o comissário desistiu
        routines.nova_temporada(st, random.Random(1))
        self.assertTrue(por_id(st["categorias"][ALFA]["calendario"])[reserva["id"]]["ativo"])


if __name__ == "__main__":
    unittest.main()
