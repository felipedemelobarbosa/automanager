"""Testes básicos (sem interface gráfica).  Uso:  python -m unittest discover tests"""
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, routines  # noqa: E402
from automanager.event.sessoes import Evento  # noqa: E402
from automanager.event.inscritos import montar_inscritos  # noqa: E402


class TestDatabase(unittest.TestCase):
    def test_arquivos_validos(self):
        arqs = db.arquivos_do_ano(2026)
        self.assertGreaterEqual(len(arqs), 2)
        for a in arqs:
            self.assertEqual(db.validar_dados(db.carregar_arquivo(a, validar=False)), [], a)

    def test_validacao_detecta_erro(self):
        d = db.carregar_arquivo(db.arquivos_do_ano(2026)[0])
        d["pilotos"][0]["atributos"]["consistencia"] = 150
        d["categoria"]["regras"]["importancia_carro"] = 0.9
        erros = db.validar_dados(d)
        self.assertTrue(any("consistencia" in e for e in erros))
        self.assertTrue(any("somar" in e for e in erros))


class TestJogo(unittest.TestCase):
    def setUp(self):
        self.st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)

    def test_multiplas_categorias_pool_de_pilotos(self):
        self.assertEqual(len(self.st["categorias"]), 2)
        origens = {p["categoria_origem"] for p in self.st["pilotos"].values()}
        self.assertEqual(origens, {"formula_alfa", "formula_beta"})

    def test_criar_equipe_orcamento(self):
        regras = self.st["categorias"]["formula_alfa"]["categoria"]["regras"]
        for i in range(20):
            st = state.novo_jogo(db.arquivos_do_ano(2026), semente=i)
            eq = state.criar_equipe(st, "formula_alfa", f"Teste {i}", "Brasil", random.Random(i))
            self.assertGreaterEqual(eq["financas"]["caixa"], regras["orcamento_medio"] * 0.7 - 1000)
            self.assertLessEqual(eq["financas"]["caixa"], regras["orcamento_medio"] * 1.2 + 1000)
        self.assertEqual(state.precisa_desenvolvimento_inicial(st, "formula_alfa", eq["id"]), (True, False))

    def test_duas_temporadas_e_save(self):
        state.escolher_equipe(self.st, "formula_alfa", "tucano")
        rng = random.Random(3)
        for _ in range(routines.SEMANAS_POR_TEMPORADA * 2 + 3):
            routines.avancar_semana(self.st, rng)
        self.assertEqual(self.st["ano"], 2028)
        # equipes do PC devem ter pilotos principais para a temporada atual
        for cid, c in self.st["categorias"].items():
            alvo = c["categoria"]["regras"]["pilotos_principais_por_equipe"]
            for eq in c["equipes"].values():
                if eq.get("ativa") and eq["id"] != "tucano":
                    principais = [p for p in state.pilotos_da_equipe(self.st, cid, eq["id"])
                                  if p["contrato"]["situacao"] == "principal" and not p.get("lesao")]
                    self.assertEqual(len(principais), alvo, f"{cid}/{eq['id']}")
        with tempfile.TemporaryDirectory() as d:
            caminho = state.salvar(self.st, "teste", d)
            st2 = state.carregar(caminho)
            self.assertEqual(st2["ano"], self.st["ano"])
            self.assertEqual(len(st2["pilotos"]), len(self.st["pilotos"]))


class TestEvento(unittest.TestCase):
    def _rodar(self, arquivo, idx, seed):
        st = state.novo_jogo([arquivo], semente=seed)
        cid = list(st["categorias"])[0]
        c = st["categorias"][cid]
        corridas = [e for e in c["calendario"] if e["especie"] == "corrida"]
        ev = Evento(c["categoria"], corridas[idx], montar_inscritos(st, cid, None), random.Random(seed))
        while ev.proxima_sessao():
            ev.sessao.iniciar()
            ev.sessao.simular_ate_o_fim()
        return ev

    def test_evento_completo_todas_as_pistas(self):
        for arq in db.arquivos_do_ano(2026):
            st = state.novo_jogo([arq], semente=1)
            n = sum(1 for e in list(st["categorias"].values())[0]["calendario"] if e["especie"] == "corrida")
            for i in range(n):
                ev = self._rodar(arq, i, i)
                res = ev.resultado_corrida
                self.assertEqual(len(res), len(ev.carros))
                self.assertEqual(len(ev.grid), len(ev.carros))
                fim = [r for r in res if r["carro"].status == "fim"]
                self.assertTrue(fim)
                tempos = [r["carro"].tempo_total for r in fim]
                self.assertEqual(tempos, sorted(tempos))
                if getattr(ev.sessao, "cancelada", False):        # oval com chuva que não parou: sem pontos
                    self.assertEqual(sum(r["pontos"] for r in res), 0)
                    continue
                if getattr(ev.sessao, "interrompida", False):     # término antecipado: pontuação pode ser parcial
                    continue
                self.assertEqual(res[0]["pontos"], ev.cat["pontuacao"]["posicoes"][0]
                                 + (ev.cat["pontuacao"].get("pole", 0) if ev.pole is res[0]["carro"] else 0)
                                 + (ev.cat["pontuacao"].get("volta_mais_rapida", 0)
                                    if ev.sessao.volta_mais_rapida and ev.sessao.volta_mais_rapida[1] is res[0]["carro"]
                                    else 0))

    def test_classificacao_com_fases_elimina(self):
        arq = [a for a in db.arquivos_do_ano(2026) if "alfa" in a][0]
        st = state.novo_jogo([arq], semente=1)
        c = st["categorias"]["formula_alfa"]
        ev = Evento(c["categoria"], c["calendario"][2], montar_inscritos(st, "formula_alfa", None), random.Random(1))
        for _ in range(3):
            s = ev.proxima_sessao()
            s.iniciar()
            s.simular_ate_o_fim()
        q = ev.proxima_sessao()
        q.iniciar()
        q.simular_ate_o_fim()
        elim = sum(f["eliminados"] for f in c["categoria"]["formato_evento"]["classificacao"]["fases"])
        self.assertEqual(len(q.eliminados), elim)
        self.assertEqual(ev.grid[0], q.ordem_final[0])

    def test_acerto_influencia_tempo(self):
        arq = [a for a in db.arquivos_do_ano(2026) if "alfa" in a][0]
        st = state.novo_jogo([arq], semente=1)
        c = st["categorias"]["formula_alfa"]
        from automanager.event.modelo import acerto_ideal
        pista = c["calendario"][2]
        tempos = {}
        for nome, acerto in (("ideal", acerto_ideal(pista, "seco")), ("ruim", {k: 0 for k in
                                                                              acerto_ideal(pista, "seco")})):
            ev = Evento(c["categoria"], dict(pista, prob_chuva=0), montar_inscritos(st, "formula_alfa", None),
                        random.Random(7))
            carro = ev.carros[0]
            carro.acerto = acerto
            carro.pneu = "medio"
            amostra = [ev.modelo.volta(carro, "treino", ev.clima)[0] for _ in range(300)]
            tempos[nome] = sum(amostra) / len(amostra)
        self.assertLess(tempos["ideal"], tempos["ruim"])
        self.assertLess(tempos["ruim"] / tempos["ideal"], 1.03)   # sem voltas irreais


if __name__ == "__main__":
    unittest.main()
