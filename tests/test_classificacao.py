"""Modelos de classificação e degradação dos pneus."""
import copy
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state  # noqa: E402
from automanager.event.sessoes import Evento, planejar  # noqa: E402
from automanager.event.inscritos import montar_inscritos  # noqa: E402
from automanager.event.modelo import multiplicador_pneu  # noqa: E402

ALFA = [a for a in db.arquivos_do_ano(2026) if "alfa" in a][0]


def evento(classificacao, corrida_extra=None, seed=3, parar_apos=None):
    st = state.novo_jogo([ALFA])
    c = st["categorias"]["formula_alfa"]
    cat = copy.deepcopy(c["categoria"])
    cat["formato_evento"]["treinos_livres"] = []
    cat["formato_evento"]["classificacao"] = classificacao
    if corrida_extra:
        cat["formato_evento"]["corrida"].update(corrida_extra)
    inscritos = montar_inscritos(st, "formula_alfa", None)
    ordem = [i["piloto"]["id"] for i in inscritos]
    ev = Evento(cat, dict(c["calendario"][2], prob_chuva=0), inscritos, random.Random(seed), ordem_campeonato=ordem)
    sessoes = []
    while ev.proxima_sessao():
        ev.sessao.iniciar()
        ev.sessao.simular_ate_o_fim()
        sessoes.append(ev.sessao)
        if parar_apos and len(sessoes) >= parar_apos:
            break
    return ev, sessoes, ordem


class TestModelosClassificacao(unittest.TestCase):
    def test_tempo_sem_eliminacao_varias_fases(self):
        ev, s, _ = evento({"modelo": "tempo", "fases": [
            {"nome": "Parte 1", "limite": "tempo", "valor": 15, "eliminados": 0},
            {"nome": "Parte 2", "limite": "tempo", "valor": 15, "eliminados": 0}]}, parar_apos=1)
        q = s[0]
        self.assertEqual(q.eliminados, [])
        tempos = [c.melhor for c in q.ordem_final if c.melhor]
        self.assertEqual(tempos, sorted(tempos))     # vale a melhor volta da sessão inteira

    def test_eliminacao(self):
        ev, s, _ = evento({"modelo": "tempo", "fases": [
            {"nome": "Q1", "limite": "tempo", "valor": 15, "eliminados": 5},
            {"nome": "Q2", "limite": "voltas", "valor": 6, "eliminados": 0}]})
        self.assertEqual(len(s[0].eliminados), 5)
        self.assertEqual(ev.grid[-5:], s[0].eliminados)

    def test_grupos_intercalados(self):
        ev, s, _ = evento({"modelo": "grupos", "grupos": 2, "limite": "tempo", "valor": 12})
        q = s[0]
        self.assertEqual(len(q.resultados_grupos), 2)
        g = [q.grupos[c.id] for c in ev.grid]
        self.assertTrue(all(g[i] != g[i + 1] for i in range(len(g) - 1)))

    def test_volta_unica_media(self):
        ev, s, ordem = evento({"modelo": "volta_unica", "voltas_cronometradas": 4, "criterio": "media",
                               "ordem_saida": "campeonato_invertido"})
        q = s[0]
        validos = [c for c in q.ordem_final if c.melhor_fase]
        for c in validos:
            self.assertAlmostEqual(c.melhor_fase, sum(c.tempos_fase[:4]) / 4)
        self.assertEqual([c.melhor_fase for c in validos], sorted(c.melhor_fase for c in validos))
        self.assertIn(ordem[-1].split("/")[0], "formula_alfa")

    def test_corrida_classificatoria_define_grid(self):
        ev, s, _ = evento([{"modelo": "corrida_classificatoria", "voltas": 8, "grid": "campeonato_invertido"}])
        bateria = s[0]
        self.assertTrue(bateria.classificatoria)
        chegada = [r["carro"] for r in bateria.resultado]
        self.assertEqual(s[1].grid[0], chegada[0])
        self.assertTrue(ev.resultado_corrida)                         # a corrida principal pontua
        self.assertTrue(all(r["pontos"] == "" for r in bateria.resultado))

    def test_grid_pelo_campeonato_invertido_e_grid_invertido(self):
        ev, s, ordem = evento({"modelo": "campeonato", "invertido": True}, corrida_extra={"grid_invertido_top": 6})
        self.assertEqual(s[0].ordem_final[0].id, ordem[-1])
        self.assertEqual(s[1].grid[5].id, ordem[-1])                   # o 1º do grid foi para 6º

    def test_etapas_combinadas(self):
        ev, s, _ = evento([{"modelo": "tempo", "nome": "Classificação", "limite": "tempo", "valor": 20},
                           {"modelo": "corrida_classificatoria", "nome": "Bateria", "voltas": 6, "grid": "anterior"}])
        self.assertEqual([x.nome for x in s], ["Classificação", "Bateria", "Corrida"])


class TestPneus(unittest.TestCase):
    def test_curva_aquecimento_linear_cliff(self):
        cat = db.carregar_arquivo(ALFA)["categoria"]
        m = [multiplicador_pneu(cat, "macio", "seco", a, a) for a in range(30)]
        self.assertGreater(m[0], m[1])                                   # aquecimento
        self.assertLess(m[2], m[10])                                     # degradação
        passo_antes = m[15] - m[14]
        passo_depois = m[25] - m[24]
        self.assertGreater(passo_depois, passo_antes * 3)                # cliff
        duro = [multiplicador_pneu(cat, "duro", "seco", a, a) for a in range(30)]
        self.assertGreater(duro[5], m[5])                                # duro mais lento novo...
        self.assertLess(duro[28], m[28])                                 # ...mas dura mais

    def test_pista_abrasiva_pede_mais_paradas(self):
        st = state.novo_jogo([ALFA])
        c = st["categorias"]["formula_alfa"]
        ins = montar_inscritos(st, "formula_alfa", None)
        paradas = {}
        for desg in (20, 95):
            ev = Evento(c["categoria"], dict(c["calendario"][2], prob_chuva=0, desgaste_pneus=desg), ins,
                        random.Random(1))
            car = ev.carros[0]
            car.ordens = {"agressividade": 0, "uso_motor": 0, "uso_carro": 0}
            paradas[desg] = len(planejar(ev, car, 70, 0)) - 1
        self.assertGreater(paradas[95], paradas[20])


if __name__ == "__main__":
    unittest.main()
