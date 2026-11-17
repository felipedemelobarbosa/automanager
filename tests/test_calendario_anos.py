"""Anos fixados para uma pista entrar e sair do calendário (anos_entrada / anos_saida)."""
import copy
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, routines  # noqa: E402

CID = "formula_alfa"


class TestAnosDoCalendario(unittest.TestCase):
    def setUp(self):
        self.st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
        cal = self.st["categorias"][CID]["calendario"]
        ativos = {(e["nome"], e.get("local")) for e in cal if e.get("ativo") and e["especie"] == "corrida"}
        self.res = next(e for e in cal if not e.get("ativo") and e["especie"] == "corrida"
                        and (e["nome"], e.get("local")) not in ativos)
        self.fixo = next(e for e in cal if e.get("ativo") and e["especie"] == "corrida")
        for e in cal:                                   # sem sorteio: só os anos fixados mexem no calendário
            e["prob_ativar"] = e["prob_inativar"] = 0.0

    def virar(self):
        self.st["ano"] += 1
        routines._virada_calendario(self.st, CID, random.Random(0))
        return self.res.get("ativo"), self.fixo.get("ativo")

    def test_entra_e_sai_varias_vezes(self):
        self.res["anos_entrada"] = [2028, 2031]
        self.res["anos_saida"] = [2030]
        self.fixo["anos_saida"] = [2027]
        self.fixo["anos_entrada"] = [2029]
        seq = [self.virar() for _ in range(6)]           # 2027 … 2032
        self.assertEqual([r for r, _ in seq], [False, True, True, False, True, True])
        self.assertEqual([f for _, f in seq], [False, False, True, True, True, True])
        textos = [n["texto"] for n in self.st["noticias"]]
        self.assertTrue(any("nova corrida" in t and self.res["nome"] in t and "2028" in t for t in textos))
        self.assertTrue(any("sai do calendário 2030" in t and self.res["nome"] in t for t in textos))

    def test_ano_fixado_vence_o_sorteio(self):
        self.fixo["prob_inativar"] = 1.0                 # sairia todo ano, mas 2027 está fixado para entrar
        self.fixo["anos_entrada"] = [2027]
        self.virar()
        self.assertTrue(self.fixo["ativo"])
        self.res["prob_ativar"] = 1.0
        self.res["anos_saida"] = [2028]
        self.virar()
        self.assertFalse(self.res["ativo"])

    def test_sem_anos_mesmo_sorteio(self):
        """Sem anos fixados, a sequência aleatória é a mesma de antes (jogos salvos não mudam)."""
        st2 = copy.deepcopy(self.st)
        rng1, rng2 = random.Random(5), random.Random(5)
        for e in self.st["categorias"][CID]["calendario"] + st2["categorias"][CID]["calendario"]:
            e["prob_ativar"], e["prob_inativar"] = 0.3, 0.3
        routines._virada_calendario(self.st, CID, rng1)
        routines._virada_calendario(st2, CID, rng2)
        self.assertEqual(rng1.random(), rng2.random())

    def test_validacao(self):
        d = db.carregar_arquivo(db.arquivos_do_ano(2026)[0], validar=False)
        ev = next(e for e in d["calendario"] if not e.get("ativo"))
        ev["anos_entrada"], ev["anos_saida"] = [2028], [2030]
        self.assertEqual(db.validar_dados(d), [])
        ev["anos_saida"] = [2028]
        self.assertTrue(any("mesmo ano" in e for e in db.validar_dados(d)))
        ev["anos_saida"] = [2026]
        self.assertTrue(any("depois de 2026" in e for e in db.validar_dados(d)))
        ev["anos_saida"] = ["2030"]
        self.assertTrue(any("lista de anos" in e for e in db.validar_dados(d)))


if __name__ == "__main__":
    unittest.main()
