"""Corridas não se repetem: resultados e acontecimentos variam de corrida para corrida e de temporada para
temporada, pelo fluxo real do jogo (gerador aleatório global, como a interface)."""
import copy
import itertools
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, routines, campeonato  # noqa: E402


class TestVariedade(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corridas = []
        orig = campeonato.registrar_corrida

        def captura(st, cid, pista, ev):
            reg = orig(st, cid, pista, ev)
            cls.corridas.append({"cid": cid, "reg": reg, "log": set(ev.sessao.log)})
            return reg
        campeonato.registrar_corrida = captura
        try:
            st = state.novo_jogo(db.arquivos_do_ano(2026))
            st["usuario"] = {"categoria": None, "equipe": None}
            random.seed(None)
            while st["ano"] < 2028:
                routines.avancar_semana(st)
        finally:
            campeonato.registrar_corrida = orig

    def _pares(self):
        return [(a, b) for a, b in itertools.combinations(self.corridas, 2) if a["cid"] == b["cid"]]

    def test_resultados_diferentes(self):
        self.assertGreater(len(self.corridas), 40)
        for a, b in self._pares():
            oa = [l["piloto"] for l in a["reg"]["resultado"]]
            ob = [l["piloto"] for l in b["reg"]["resultado"]]
            self.assertNotEqual(oa[:10], ob[:10], (a["reg"]["nome"], b["reg"]["nome"]))

    def test_acontecimentos_nao_se_repetem(self):
        for a, b in self._pares():
            ua = {m for m in a["log"] if "ultrapassa" in m or "ABANDONO" in m or "pit stop" in m}
            ub = {m for m in b["log"] if "ultrapassa" in m or "ABANDONO" in m or "pit stop" in m}
            self.assertLess(len(ua & ub) / max(1, len(ua | ub)), 0.25)

    def test_mesma_corrida_rodada_duas_vezes_muda(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026))
        pista = next(e for e in st["categorias"]["formula_alfa"]["calendario"] if e["especie"] == "corrida")
        r1 = campeonato.simular_em_segundo_plano(copy.deepcopy(st), "formula_alfa", pista, random.Random(1))
        r2 = campeonato.simular_em_segundo_plano(copy.deepcopy(st), "formula_alfa", pista, random.Random(2))
        r1b = campeonato.simular_em_segundo_plano(copy.deepcopy(st), "formula_alfa", pista, random.Random(1))
        self.assertNotEqual([l["piloto"] for l in r1["resultado"]], [l["piloto"] for l in r2["resultado"]])
        self.assertEqual(r1["resultado"], r1b["resultado"])      # mesma semente = mesma corrida (reprodutível)


if __name__ == "__main__":
    unittest.main()


class TestJogosNovos(unittest.TestCase):
    CAMPOS = ("potencial", "ano_pico", "ano_aposentadoria")

    def _carreiras(self, st):
        return {pid: tuple(p.get(k) for k in self.CAMPOS) for pid, p in st["pilotos"].items()}

    def test_cada_jogo_novo_tem_carreiras_proprias(self):
        a = state.novo_jogo(db.arquivos_do_ano(2026))
        b = state.novo_jogo(db.arquivos_do_ano(2026))
        self.assertNotEqual(a["semente"], b["semente"])
        ca, cb = self._carreiras(a), self._carreiras(b)
        self.assertGreater(sum(ca[p] != cb[p] for p in ca), len(ca) // 3)

    def test_mesma_semente_mesmo_jogo(self):
        a = state.novo_jogo(db.arquivos_do_ano(2026), semente=42)
        b = state.novo_jogo(db.arquivos_do_ano(2026), semente=42)
        self.assertEqual(self._carreiras(a), self._carreiras(b))


class TestCalendario(unittest.TestCase):
    def test_reserva_nao_repete_pista_do_calendario(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026))
        cal = st["categorias"]["formula_alfa"]["calendario"]
        ativa = next(e for e in cal if e["especie"] == "corrida" and e.get("ativo"))
        reserva = dict(ativa, id="evX", ativo=False, semana=51, prob_ativar=1.0, prob_inativar=0.0)
        cal.append(reserva)
        for e in cal:
            e["prob_inativar"] = 0.0
        routines._virada_calendario(st, "formula_alfa", random.Random(1))
        self.assertFalse(reserva["ativo"])
        ativa["ativo"] = False                            # a original saiu: aí a reserva pode entrar
        routines._virada_calendario(st, "formula_alfa", random.Random(1))
        self.assertTrue(reserva["ativo"])

    def test_database_de_exemplo_sem_pista_repetida(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026))
        for c in st["categorias"].values():
            corridas = [(e["nome"], e["local"]) for e in c["calendario"] if e["especie"] == "corrida"]
            self.assertEqual(len(corridas), len(set(corridas)))
