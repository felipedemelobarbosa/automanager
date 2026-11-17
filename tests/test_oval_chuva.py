"""Oval não admite chuva: bandeira vermelha e sessão suspensa até a pista secar."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state  # noqa: E402
from automanager.event.inscritos import montar_inscritos  # noqa: E402
from automanager.event.modelo import ModeloVolta  # noqa: E402
from automanager.event.sessoes import Evento, SessaoCorrida  # noqa: E402


def evento(tipo_pista, semente, prob_chuva=0.5, bandeira=None):
    st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
    c = st["categorias"]["formula_alfa"]
    cat = c["categoria"]
    cat["clima"]["estabilidade_por_10min"] = 0.6          # clima bem instável
    if bandeira is not None:
        cat["regras"]["bandeira_vermelha"] = bandeira
    cat["regras"]["batida_grave"] = {"prob_por_volta": 0.0}   # aqui só interessa a chuva
    pista = dict(next(e for e in c["calendario"] if e["tipo_pista"] == "oval"), prob_chuva=prob_chuva,
                 tipo_pista=tipo_pista)
    return Evento(cat, pista, montar_inscritos(st, "formula_alfa", None, pista), random.Random(semente))


def rodar(ev):
    climas, logs = [], []
    original = ModeloVolta.volta

    def volta(self, carro, sessao, clima, *a, **k):
        climas.append(clima.estado)
        return original(self, carro, sessao, clima, *a, **k)
    ModeloVolta.volta = volta
    try:
        while ev.proxima_sessao():
            ev.preparar_ia()
            ev.sessao.iniciar()
            ev.sessao.simular_ate_o_fim()
            logs += ev.sessao.log
    finally:
        ModeloVolta.volta = original
    return climas, logs


class TestOvalChuva(unittest.TestCase):
    def test_oval_nunca_roda_molhado(self):
        vermelhas = 0
        for semente in range(4):
            ev = evento("oval", semente)
            climas, logs = rodar(ev)
            self.assertTrue(climas)
            self.assertEqual(set(climas), {"seco"})
            vermelhas += sum("BANDEIRA VERMELHA" in m for m in logs)
            self.assertTrue(ev.resultado_corrida)
            fim = [r for r in ev.resultado_corrida if r["carro"].status == "fim"]
            self.assertTrue(fim)
            if not any("não parou" in m for m in logs):                              # sem limite estourado,
                self.assertEqual(fim[0]["carro"].voltas, ev.pista["voltas_corrida"])  # a corrida vai até o fim
        self.assertGreater(vermelhas, 0)

    def test_sem_limite_sempre_retoma(self):
        for semente in range(4):
            ev = evento("oval", semente, bandeira={"limite_espera_sessao_min": 0, "limite_espera_corrida_min": 0})
            climas, logs = rodar(ev)
            self.assertEqual(set(climas), {"seco"})
            self.assertFalse(any("não parou" in m for m in logs))
            fim = [r for r in ev.resultado_corrida if r["carro"].status == "fim"]
            self.assertEqual(fim[0]["carro"].voltas, ev.pista["voltas_corrida"])

    def test_chuva_que_nao_para_cancela(self):
        ev = evento("oval", 0, prob_chuva=1.0,
                    bandeira={"limite_espera_sessao_min": 60, "limite_espera_corrida_min": 120})
        climas, logs = rodar(ev)
        self.assertEqual(climas, [])                                   # nenhuma volta no fim de semana
        self.assertTrue(ev.sessao.cancelada)
        self.assertEqual(sum(r["pontos"] for r in ev.resultado_corrida), 0)
        self.assertTrue(any("Corrida cancelada" in m for m in logs))
        # o campeonato ignora a corrida cancelada
        from automanager import campeonato
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
        reg = campeonato.registrar_corrida(st, "formula_alfa", ev.pista, ev)
        self.assertTrue(reg["cancelada"])
        self.assertEqual(campeonato.classificacao(st, "formula_alfa"), ([], []))

    def test_relogio_corre_ou_para(self):
        achou = {}
        for corre in (False, True):
            regra = {"relogio_durante_suspensao": "corre" if corre else "parado",
                     "limite_espera_sessao_min": 0, "limite_espera_corrida_min": 0}
            for semente in range(12):
                ev = evento("oval", semente, bandeira=regra)
                while ev.proxima_sessao():
                    ev.preparar_ia()
                    ev.sessao.iniciar()
                    ev.sessao.simular_ate_o_fim()
                    if isinstance(ev.sessao, SessaoCorrida) and any("corrida suspensa" in m for m in ev.sessao.log):
                        achou[corre] = ev.sessao.tempo_suspenso
                if corre in achou:
                    break
        if len(achou) < 2:
            self.skipTest("sem bandeira vermelha na corrida com estas sementes")
        self.assertEqual(achou[False], 0.0)                 # parado: a espera não conta para o tempo máximo
        self.assertGreater(achou[True], 0.0)                # corre: a espera conta

    def test_pista_mista_continua_com_chuva(self):
        molhadas = 0
        for semente in range(4):
            climas, logs = rodar(evento("mista", semente))
            molhadas += sum(c != "seco" for c in climas)
            self.assertFalse(any("BANDEIRA VERMELHA" in m for m in logs))
        self.assertGreater(molhadas, 0)

    def test_relargada_atras_do_safety_car(self):
        for semente in range(12):
            ev = evento("oval", semente)
            _, logs = rodar(ev)
            if any("corrida suspensa" in m for m in logs):
                i = next(i for i, m in enumerate(logs) if "corrida suspensa" in m)
                self.assertIn("safety car", logs[i + 1])
                return
        self.skipTest("nenhuma bandeira vermelha na corrida com estas sementes")


if __name__ == "__main__":
    unittest.main()
