"""Multas, empréstimos, falência, novas equipes, patrocínio para todos e carreira dos pilotos."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, routines, mercado, economia, carreira  # noqa: E402


def novo(cid="formula_alfa", eid="tucano"):
    st = state.novo_jogo(db.arquivos_do_ano(2026))
    state.escolher_equipe(st, cid, eid)
    return st


class TestMultas(unittest.TestCase):
    def test_formula_da_multa(self):
        st = novo()
        n = mercado.corridas_na_temporada(st["categorias"]["formula_alfa"])
        ct = {"categoria": "formula_alfa", "equipe": "tucano", "valor_por_corrida": 100000, "temporadas": 2}
        self.assertAlmostEqual(mercado.multa(st, ct, "formula_alfa"), 0.5 * 100000 * (n + n))
        ct2 = {"categoria": "formula_alfa", "equipe": "tucano", "valor_por_corrida": 100000, "corridas": 3}
        self.assertAlmostEqual(mercado.multa(st, ct2, "formula_alfa"), 0.5 * 100000 * 3)

    def test_rescindir_piloto(self):
        st = novo()
        eq = state.equipe_usuario(st)
        p = state.pilotos_da_equipe(st, "formula_alfa", "tucano")[0]
        esperado = mercado.multa(st, p["contrato"], "formula_alfa")
        caixa = eq["financas"]["caixa"]
        mercado.rescindir_piloto(st, p["id"])
        self.assertIsNone(p["contrato"])
        self.assertAlmostEqual(eq["financas"]["caixa"], caixa - esperado)

    def test_compra_de_contrato_pelo_usuario(self):
        st = novo()
        st["semana"] = 25
        alvo = state.pilotos_da_equipe(st, "formula_alfa", "vortex")[0]
        meu = next(p for p in state.pilotos_da_equipe(st, "formula_alfa", "tucano")
                   if p["contrato"]["situacao"] == "principal")
        mercado.rescindir_piloto(st, meu["id"])                    # abre a vaga
        self.assertIsNone(mercado.fazer_proposta(st, alvo["id"], "principal", 2000000, 2, "temporadas", "agora"))
        self.assertTrue(next(p for p in st["propostas_usuario"].values() if p["piloto"] == alvo["id"])["compra_contrato"])
        vortex = st["categorias"]["formula_alfa"]["equipes"]["vortex"]
        antes = vortex["financas"]["caixa"]
        routines.avancar_semana(st, random.Random(1))
        routines.avancar_semana(st, random.Random(1))
        if alvo["contrato"] and alvo["contrato"]["equipe"] == "tucano":
            self.assertGreater(vortex["financas"]["ano"]["receitas"]["multas"], 0)
        else:
            self.assertTrue(any(alvo["nome"] in n["texto"] and "recusou" in n["texto"] for n in st["noticias"]))
        self.assertIsNotNone(antes)

    def test_troca_de_motor_no_meio_do_ano(self):
        st = novo()
        eq = state.equipe_usuario(st)
        self.assertIsNotNone(mercado.contratar_parte(st, "formula_alfa", eq, "motor", "mot_rhone", 1, "temporadas",
                                                     "agora"))
        caixa = eq["financas"]["caixa"]
        valor = mercado.multa_parte(st, "formula_alfa", eq, "motor")
        self.assertIsNone(mercado.contratar_parte(st, "formula_alfa", eq, "motor", "mot_rhone", 1, "temporadas",
                                                  "agora", rescindir=True))
        self.assertEqual(eq["motor"]["id"], "mot_rhone")
        self.assertAlmostEqual(eq["financas"]["caixa"], caixa - valor)


class TestEconomia(unittest.TestCase):
    def test_emprestimo_e_parcelas(self):
        st = novo()
        eq = state.equipe_usuario(st)
        caixa = eq["financas"]["caixa"]
        self.assertIsNone(economia.tomar_emprestimo(st, "formula_alfa", eq, 10_000_000, 2))
        self.assertAlmostEqual(eq["financas"]["caixa"], caixa + 10_000_000)
        emp = eq["emprestimos"][0]
        n = emp["parcelas_restantes"]
        for _ in range(n):
            economia.pagar_parcelas(st, "formula_alfa", eq)
        self.assertEqual(eq.get("emprestimos"), [])
        pago = eq["financas"]["ano"]["despesas"]["emprestimos"]
        self.assertGreater(pago, 10_000_000)                       # pagou juros
        self.assertLess(pago, 10_000_000 * 1.2)
        self.assertIsNotNone(economia.tomar_emprestimo(st, "formula_alfa", eq, 10 ** 12))

    def test_falencia_do_pc(self):
        st = novo()
        eq = st["categorias"]["formula_alfa"]["equipes"]["atlas"]
        eq["financas"]["caixa"] = -10 ** 9
        for _ in range(12):
            economia.rotina(st)
        self.assertFalse(eq["ativa"])
        self.assertTrue(all((p.get("contrato") or {}).get("equipe") != "atlas" for p in st["pilotos"].values()))

    def test_falencia_do_usuario_encerra_o_jogo(self):
        st = novo()
        eq = state.equipe_usuario(st)
        eq["financas"]["caixa"] = -10 ** 9
        economia.tomar_emprestimo(st, "formula_alfa", eq, economia.limite_credito(st, "formula_alfa", eq))
        eq["financas"]["caixa"] = -10 ** 9
        for _ in range(10):
            economia.rotina(st)
        self.assertEqual(st.get("fim_de_jogo", {}).get("motivo"), "falencia")

    def test_equipe_surge_no_ano_definido(self):
        st = novo()
        rng = random.Random(1)
        while st["ano"] < 2028:
            routines.avancar_semana(st, rng)
        self.assertTrue(st["categorias"]["formula_alfa"]["equipes"]["danubio"]["ativa"])

    def test_toda_equipe_recebe_patrocinio(self):
        st = novo()
        c = st["categorias"]["formula_alfa"]
        for p in c["patrocinadores"].values():
            p["contrato"] = None
            p["ativo"] = False                                    # nenhum patrocinador disponível
        rng = random.Random(2)
        for _ in range(30):
            mercado.rotina_patrocinadores(st, rng)
        com = {p["contrato"]["equipe"] for p in c["patrocinadores"].values() if p.get("contrato")}
        sem = [e["id"] for e in c["equipes"].values() if e["ativa"] and e["id"] not in com and e["id"] != "tucano"]
        self.assertEqual(sem, [])


class TestCarreira(unittest.TestCase):
    def test_curva_ate_o_pico_e_queda(self):
        p = {"id": "x", "nome": "X", "idade": 18, "atributos": {k: 50 for k in db.ATRIBUTOS_PILOTO},
             "ano_pico": 2030, "potencial": 80}
        carreira.preparar_piloto(p, 2026, random.Random(1))
        medias = []
        for ano in range(2027, 2036):
            p["idade"] += 1
            carreira.evoluir(p, ano, random.Random(ano))
            medias.append(sum(p["atributos"].values()) / 11)
        pico = medias[2030 - 2027]
        self.assertGreater(pico, 75)
        self.assertLess(medias[-1], pico)
        self.assertTrue(all(b >= a for a, b in zip(medias[:3], medias[1:4])))
        self.assertGreater(p["atributos"]["acerto_carro"] - 50, p["atributos"]["fisico"] - 50)

    def test_aposentadoria_e_novos_pilotos(self):
        st = novo()
        veterano = next(p for p in st["pilotos"].values() if p.get("contrato"))
        veterano["ano_aposentadoria"] = 2027
        rng = random.Random(3)
        while st["ano"] < 2027:
            routines.avancar_semana(st, rng)
        self.assertNotIn(veterano["id"], st["pilotos"])
        self.assertIn(veterano["id"], st["aposentados"])
        self.assertTrue(any(k.startswith("novos2027/") for k in st["pilotos"]))     # arquivo de novos pilotos
        ficticios = [p for p in st["pilotos"].values() if p.get("ficticio")]
        self.assertTrue(ficticios)
        self.assertTrue(all(p["categoria_origem"] == "formula_beta" for p in ficticios))  # tier mais baixo
        self.assertTrue(all(17 <= p["idade"] <= 21 for p in ficticios))


if __name__ == "__main__":
    unittest.main()
