"""Anti-trapaça do acerto: a fórmula pública não dá o acerto ideal real (desvio escondido por evento e preferência
de cada piloto); só o treino (comentários dos pilotos) leva até ele. No multijogador o desvio só existe no jogo do
comissário e a preferência não vai no arquivo dos jogadores."""
import copy
import os
import random
import statistics
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, multiplayer as mp  # noqa: E402
from automanager.event import modelo as m, planos, persistencia  # noqa: E402
from automanager.event.inscritos import montar_inscritos  # noqa: E402
from automanager.event.sessoes import Evento  # noqa: E402

ALFA = "formula_alfa"


def jogo():
    st = state.novo_jogo(db.arquivos_do_ano(2026), semente=7)
    state.escolher_equipe(st, ALFA, "tucano")
    return st


def evento(st, seed, idx=0):
    c = st["categorias"][ALFA]
    pista = [e for e in c["calendario"] if e["especie"] == "corrida"][idx]
    return Evento(c["categoria"], pista, montar_inscritos(st, ALFA, "tucano", pista), random.Random(seed))


class TestIdealEscondido(unittest.TestCase):
    def setUp(self):
        self.st = jogo()

    def test_formula_nao_e_o_ideal_e_muda_por_evento(self):
        ev1, ev2 = evento(self.st, 1), evento(self.st, 2)
        carro = ev1.carros[0]
        formula = m.acerto_ideal(ev1.pista, "seco")
        real1 = ev1.modelo.ideal(carro, "seco")
        real2 = ev2.modelo.ideal(ev2.carros[0], "seco")
        self.assertNotEqual(real1, formula)
        self.assertNotEqual(real1, real2)                                    # outro fim de semana, outro ideal
        self.assertNotEqual(ev1.modelo.desvio["seco"], ev1.modelo.desvio["chuva"])

    def test_acerto_da_formula_perde_tempo(self):
        perdas = []
        for seed in range(30):
            ev = evento(self.st, seed)
            for c in ev.carros:
                c.acerto = dict(m.acerto_ideal(ev.pista, "seco"))            # quem "leu o código"
                perdas.append(m.multiplicador_acerto(c, ev.modelo.ideal(c, "seco"), ev.modelo.sim,
                                                     ev.modelo.pesos_acerto) - 1)
        self.assertGreater(statistics.mean(perdas), 0.0005)                    # ~0,1%: como o acerto médio da IA

    def test_comentario_do_piloto_aponta_o_ideal_real(self):
        ev = evento(self.st, 3)
        c = ev.carros[0]
        c.acerto = dict(m.acerto_ideal(ev.pista, "seco"))
        real = ev.modelo.ideal(c, "seco")
        rng = random.Random(1)
        medias = {k: statistics.mean(m.avaliar_acerto(c, real, rng)[k] for _ in range(400)) for k in real}
        for k in real:
            self.assertAlmostEqual(medias[k], real[k] - c.acerto[k], delta=3)

    def test_evento_retomado_tem_o_mesmo_ideal(self):
        ev = evento(self.st, 4)
        ev.proxima_sessao()
        dados = persistencia.serializar(ev, ALFA)
        ev2, _ = persistencia.restaurar(dados, self.st)
        self.assertEqual(ev2.modelo.desvio, ev.modelo.desvio)


class TestPreferenciaDoPiloto(unittest.TestCase):
    def test_cada_piloto_tem_a_sua_e_o_arquivo_dos_jogadores_nao(self):
        st = jogo()
        a, b = [p for p in state.pilotos_da_equipe(st, ALFA, "tucano") if p["contrato"]["situacao"] == "principal"]
        self.assertTrue(a.get("pref_acerto") and b.get("pref_acerto"))
        ev = evento(st, 5)
        ca = next(c for c in ev.carros if c.piloto["id"] == a["id"])
        cb = next(c for c in ev.carros if c.piloto["id"] == b["id"])
        self.assertNotEqual(ev.modelo.ideal(ca, "seco"), ev.modelo.ideal(cb, "seco"))
        mp.criar_liga(st, "Liga", [{"nome": "Ana", "categoria": ALFA, "equipe": "tucano", "senha": "a"}])
        dist = mp.versao_jogadores(st)
        self.assertFalse(any("pref_acerto" in p for p in dist["pilotos"].values()))
        self.assertTrue(all("pref_acerto" in p for p in st["pilotos"].values()))   # o comissário guarda


class TestModoEngenheiro(unittest.TestCase):
    def test_planos_novos_e_antigos(self):
        self.assertEqual(planos.plano_padrao()["treino"]["acerto_modo"], "engenheiro")
        antigo = {"treino": {"acerto": {"aerodinamica": 70}}}
        self.assertEqual(planos.normalizar(antigo, ["macio"])["treino"]["acerto_modo"], "fixo")

    def test_engenheiro_mira_o_ideal_real(self):
        """Na corrida (depois dos treinos), o engenheiro fica perto do ideal real – como a IA – e quem copiou a
        fórmula pública não ganha quase nada sobre um acerto neutro."""
        from automanager.event.sessoes import SessaoCorrida
        st = jogo()
        pid = next(p["id"] for p in state.pilotos_da_equipe(st, ALFA, "tucano")
                   if p["contrato"]["situacao"] == "principal")
        dist = {"engenheiro": [], "formula": []}
        for seed in range(12):
            for modo in dist:
                ev = evento(st, seed)
                pl = planos.plano_padrao()
                if modo == "formula":
                    for g in pl.values():
                        g["acerto_modo"] = "fixo"
                        g["acerto"] = {k: int(round(v)) for k, v in m.acerto_ideal(ev.pista, "seco").items()}
                while ev.proxima_sessao():
                    planos.aplicar(ev, {pid: copy.deepcopy(pl)})
                    if isinstance(ev.sessao, SessaoCorrida) and not ev.sessao.classificatoria:
                        c = next(c for c in ev.carros if c.piloto["id"] == pid)
                        dist[modo].append(m.distancia_acerto(c.acerto, ev.modelo.ideal(c, ev.clima.estado)))
                        break
                    ev.sessao.iniciar()
                    ev.sessao.simular_ate_o_fim()
        self.assertLess(statistics.mean(dist["engenheiro"]), 0.7 * statistics.mean(dist["formula"]))

if __name__ == "__main__":
    unittest.main()
