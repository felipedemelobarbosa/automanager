"""Contratos que começam em qualquer temporada futura (pilotos, chassis e motores)."""
import copy
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, mercado, routines, acoes, multiplayer as mp, contratos  # noqa: E402

ALFA, BETA = "formula_alfa", "formula_beta"


def jogo(cid=ALFA, eid="tucano"):
    st = state.novo_jogo(db.arquivos_do_ano(2026), semente=4)
    state.escolher_equipe(st, cid, eid)
    return st


def virar(st):
    """Só a parte de contratos da virada de temporada."""
    st["ano"] += 1
    routines._virada_contratos_pilotos(st)
    for cid in st["categorias"]:
        mercado.virada_partes(st, cid)


def livre(st, p):
    p["contrato"] = None
    p["contrato_futuro"] = None
    p.pop("ano_aposentadoria", None)
    p["idade"] = 22
    return p


class TestPilotos(unittest.TestCase):
    def setUp(self):
        self.st = jogo()
        self.c = self.st["categorias"][ALFA]
        self.eq = self.c["equipes"]["tucano"]
        for p in state.pilotos_da_equipe(self.st, ALFA, "tucano"):      # vagas da Tucano abrem em 2028
            p["contrato"]["temporadas"] = 2
            p.pop("ano_aposentadoria", None)
        self.p = livre(self.st, next(p for p in self.st["pilotos"].values() if p.get("contrato")
                                     and p["contrato"].get("equipe") == "vortex"))

    def propor(self, inicio, dur=2, unidade="temporadas", pid=None):
        return acoes.aplicar(self.st, "proposta_piloto", {"piloto": pid or self.p["id"], "situacao": "principal",
                                                          "valor": 200000, "duracao": dur, "unidade": unidade,
                                                          "inicio": inicio})

    def oferta(self, ano, p=None, eid="tucano", compra=False):
        return {"categoria": ALFA, "equipe": eid, "situacao": "principal", "quando": "proxima",
                "ano_inicio": ano, "valor_por_corrida": 200000, "pedido": 150000, "duracao": 2,
                "unidade": "temporadas", "perspectiva": 0.5, "usuario": False, "compra_contrato": compra}

    def test_vagas_por_ano(self):
        self.assertEqual(mercado.vagas_no_ano(self.st, ALFA, self.eq, 2027)["principal"], 0)
        self.assertEqual(mercado.vagas_no_ano(self.st, ALFA, self.eq, 2028)["principal"], 2)
        self.assertEqual(self.propor(2027), "A equipe não tem vaga para essa função na próxima temporada.")
        self.assertIsNone(self.propor(2028))
        prop = self.st["propostas_usuario"][f"{ALFA}|tucano|{self.p['id']}"]
        self.assertEqual((prop["quando"], prop["ano_inicio"]), ("proxima", 2028))

    def test_assina_e_comeca_no_ano_certo(self):
        mercado._assinar(self.st, self.p, self.oferta(2029), random.Random(1))
        ct = self.p["contrato_futuro"]
        self.assertEqual((ct["equipe"], ct["inicio_ano"]), ("tucano", 2029))
        self.assertEqual(mercado.vagas_no_ano(self.st, ALFA, self.eq, 2029)["principal"], 1)
        self.assertEqual(mercado.vagas_no_ano(self.st, ALFA, self.eq, 2028)["principal"], 2)
        virar(self.st)                                   # 2027
        virar(self.st)                                   # 2028: ainda não
        self.assertIsNone(self.p["contrato"])
        self.assertIsNotNone(self.p["contrato_futuro"])
        virar(self.st)                                   # 2029: começa
        self.assertEqual(self.p["contrato"]["equipe"], "tucano")
        self.assertIsNone(self.p["contrato_futuro"])

    def test_um_so_contrato_futuro_e_contrato_ate_la(self):
        mercado._assinar(self.st, self.p, self.oferta(2029, eid="vortex"), random.Random(1))
        self.assertEqual(self.propor(2030), "O piloto já assinou com uma equipe para 2029.")
        # livre agora: pode correr até 2028, não além
        self.eq_agora_vaga()
        self.assertIn("terminar antes", self.propor("agora", dur=4))
        self.assertIsNone(self.propor("agora", dur=3))
        o = dict(self.oferta(2026), quando="atual", duracao=9)
        mercado._assinar(self.st, self.p, o, random.Random(1))
        self.assertEqual(mercado.fim_do_contrato(self.st, self.p["contrato"]), 2028)

    def eq_agora_vaga(self):
        p = state.pilotos_da_equipe(self.st, ALFA, "tucano")[0]
        p["contrato"] = None

    def test_compra_com_sobreposicao_nao_deixa_piloto_livre(self):
        alvo = next(p for p in self.st["pilotos"].values() if p.get("contrato")
                    and p["contrato"].get("equipe") == "ventura")
        alvo["contrato"]["temporadas"] = 4                # vai até 2029
        alvo["contrato"].pop("inicio_ano", None)
        alvo.pop("ano_aposentadoria", None)
        alvo["idade"] = 25
        ventura = self.c["equipes"]["ventura"]
        esperado = mercado.multa(self.st, alvo["contrato"], ALFA, a_partir_de=2028)
        n = mercado.corridas_na_temporada(self.c)
        self.assertAlmostEqual(esperado, mercado.fator_multa(self.st, ALFA) * alvo["contrato"]["valor_por_corrida"]
                               * 2 * n)
        caixa_v = ventura["financas"]["caixa"]
        mercado._assinar(self.st, alvo, self.oferta(2028, compra=True), random.Random(1))
        self.assertAlmostEqual(ventura["financas"]["caixa"] - caixa_v, esperado)
        self.assertEqual(mercado.fim_do_contrato(self.st, alvo["contrato"]), 2027)
        for ano, equipe in ((2027, "ventura"), (2028, "tucano"), (2029, "tucano")):
            virar(self.st)
            self.assertEqual(alvo["contrato"]["equipe"], equipe, ano)     # nunca sem equipe

    def test_aposentadoria_e_idade_no_ano_de_inicio(self):
        self.p["ano_aposentadoria"] = 2029
        self.assertEqual(self.propor(2029), "O piloto vai se aposentar antes de 2029.")
        self.p.pop("ano_aposentadoria")
        self.c["categoria"]["regras"]["idade_pilotos"] = {"idade_maxima": 26}
        self.assertIn("mais de 26 anos", self.propor(2031))                # terá 27
        self.assertIsNone(self.propor(2028))                                # terá 24

    def test_ia_planeja_vagas_sem_estourar_os_carros(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=6)
        st["usuario"] = {"categoria": None, "equipe": None}
        rng = random.Random(6)
        antecipados = set()
        while st["ano"] < 2028:
            routines.avancar_semana(st, rng)
            for cid, c in st["categorias"].items():
                alvo = c["categoria"]["regras"]["pilotos_principais_por_equipe"]
                for eq in c["equipes"].values():
                    if not eq.get("ativa"):
                        continue
                    for ano in range(st["ano"] + 1, st["ano"] + 6):
                        ocup = alvo - mercado.vagas_no_ano(st, cid, eq, ano)["principal"]
                        self.assertLessEqual(ocup, alvo)
            for p in st["pilotos"].values():
                f = p.get("contrato_futuro")
                if f and int(f.get("inicio_ano") or 0) >= st["ano"] + 2:
                    antecipados.add(p["id"])
                    self.assertLess(mercado.fim_do_contrato(st, p["contrato"]) if p.get("contrato") else 0,
                                    f["inicio_ano"])
        self.assertTrue(antecipados)                     # a IA também assina para temporadas mais à frente


class TestPartes(unittest.TestCase):
    def setUp(self):
        self.st = jogo(BETA, "prisma")
        self.c = self.st["categorias"][BETA]
        self.eq = self.c["equipes"]["prisma"]
        self.atual = self.eq["chassis"]["contrato"]
        self.atual["temporadas"] = 2                      # vai até 2027
        self.outro = next(ch for ch in self.c["chassis"].values() if ch["id"] != self.eq["chassis"]["id"])

    def contratar(self, inicio, rescindir=False):
        return acoes.aplicar(self.st, "contratar_parte", {"parte": "chassis", "id": self.outro["id"], "duracao": 2,
                                                          "unidade": "temporadas", "inicio": inicio,
                                                          "rescindir": rescindir})

    def test_futuro_sem_sobreposicao(self):
        self.assertIsNone(self.contratar(2029))
        self.assertEqual(self.contratar(2030), "A equipe já tem contrato de chassis para 2029.")
        virar(self.st)                                   # 2027: contrato atual
        virar(self.st)                                   # 2028: acabou, o novo ainda não começou
        self.assertFalse(mercado.tem_parte_ativa(self.eq, "chassis"))
        self.assertTrue(any("sem chassis para 2028" in n["texto"] for n in self.st["noticias"]))
        virar(self.st)                                   # 2029: começa
        self.assertEqual(self.eq["chassis"]["id"], self.outro["id"])

    def test_sobreposicao_paga_multa_e_encurta(self):
        self.assertIn("é preciso pagar a multa", self.contratar(2027))
        self.atual["temporadas"] = 3                      # vai até 2028
        esperado = mercado.multa_parte(self.st, BETA, self.eq, "chassis", 2027)
        caixa = self.eq["financas"]["caixa"]
        self.assertIsNone(self.contratar(2027, rescindir=True))
        self.assertAlmostEqual(caixa - self.eq["financas"]["caixa"], esperado)
        self.assertEqual(mercado.fim_do_contrato(self.st, self.atual, BETA), 2026)
        virar(self.st)                                   # 2027: o novo, sem buraco
        self.assertEqual(self.eq["chassis"]["id"], self.outro["id"])


class TestMultijogador(unittest.TestCase):
    def test_proposta_para_um_ano_vai_nas_ordens(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=4)
        mp.criar_liga(st, "Liga", [{"nome": "Ana", "categoria": ALFA, "equipe": "tucano", "senha": "a"}])
        for p in state.pilotos_da_equipe(st, ALFA, "tucano"):
            p["contrato"]["temporadas"] = 2
        p = livre(st, next(x for x in st["pilotos"].values() if x.get("contrato")
                           and x["contrato"].get("equipe") == "vortex"))
        sj = mp.entrar(copy.deepcopy(mp.versao_jogadores(st)), "ana", "a")
        self.assertIsNone(acoes.executar(sj, "proposta_piloto", piloto=p["id"], situacao="principal", valor=200000,
                                         duracao=2, unidade="temporadas", inicio=2030))
        self.assertEqual(mp.importar_ordens(st, mp.ordens_da_sessao(sj)), "ana")


if __name__ == "__main__":
    unittest.main()
