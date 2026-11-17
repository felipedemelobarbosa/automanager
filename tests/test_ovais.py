"""Corrida em oval: pelotão no superspeedway, amarelas (nunca VSC), relargadas, oval curto de contato."""
import os
import random
import statistics as S
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state  # noqa: E402
from automanager.event.inscritos import montar_inscritos  # noqa: E402
from automanager.event.sessoes import Evento, SessaoCorrida  # noqa: E402

TIPOS = {"super": dict(retas=80, curvas_alta=20, curvas_baixa=0, tempo_base_treino=48.0, voltas_corrida=100),
         "curto": dict(retas=40, curvas_alta=5, curvas_baixa=55, tempo_base_treino=20.0, voltas_corrida=200),
         "mista": None}


def corridas(tipo, n=4):
    st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
    c = st["categorias"]["formula_alfa"]
    base = next(e for e in c["calendario"] if e["tipo_pista"] == "oval")
    t = TIPOS[tipo]
    if t:
        pista = dict(base, **t, tempo_base_corrida=t["tempo_base_treino"] * 1.025, prob_chuva=0)
    else:
        pista = dict(next(e for e in c["calendario"] if e["tipo_pista"] == "mista"), prob_chuva=0)
    out = []
    for k in range(n):
        ev = Evento(c["categoria"], pista, montar_inscritos(st, "formula_alfa", None, pista), random.Random(k))
        pelotao = 0
        while ev.proxima_sessao():
            ev.preparar_ia()
            ev.sessao.iniciar()
            if isinstance(ev.sessao, SessaoCorrida):
                s = ev.sessao
                while not s.terminada:
                    s.avancar_volta()
                    if s.volta_lider == s.total_voltas // 2:
                        viv = sorted(s.correndo(), key=lambda x: x.tempo_total)
                        pelotao = sum(1 for a, b in zip(viv, viv[1:]) if b.tempo_total - a.tempo_total < 1.0)
            else:
                ev.sessao.simular_ate_o_fim()
        fim = [r["carro"] for r in ev.resultado_corrida if r["carro"].status == "fim"]
        out.append({"ev": ev, "log": ev.sessao.log, "margem": fim[1].tempo_total - fim[0].tempo_total,
                    "pelotao": pelotao})
    return out


class TestOval(unittest.TestCase):
    def test_perfil(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
        c = st["categorias"]["formula_alfa"]
        base = next(e for e in c["calendario"] if e["tipo_pista"] == "oval")
        perfis = {}
        for k, t in TIPOS.items():
            if t:
                pista = dict(base, **t)
                ev = Evento(c["categoria"], pista, montar_inscritos(st, "formula_alfa", None, pista), random.Random(1))
                perfis[k] = ev.perfil_oval()
        self.assertEqual(perfis["super"]["pelotao"], 1.0)
        self.assertEqual(perfis["curto"]["pelotao"], 0.0)
        self.assertGreater(perfis["curto"]["curto"], 0.9)

    def test_superspeedway_em_pelotao(self):
        sup, mista = corridas("super"), corridas("mista")
        self.assertGreater(S.mean(r["pelotao"] for r in sup), S.mean(r["pelotao"] for r in mista))
        self.assertGreater(S.mean(r["pelotao"] for r in sup), 6)
        self.assertLess(S.mean(r["margem"] for r in sup), 3)
        trocas = S.mean(sum("ultrapassa" in m for m in r["log"]) for r in sup)
        self.assertGreater(trocas, 3 * S.mean(sum("ultrapassa" in m for m in r["log"]) for r in mista))

    def test_amarelas_sem_vsc(self):
        for r in corridas("curto"):
            self.assertFalse(any("VIRTUAL" in m for m in r["log"]))
        amarelas = S.mean(sum("BANDEIRA AMARELA" in m for m in r["log"]) for r in corridas("curto"))
        self.assertGreater(amarelas, 3)


if __name__ == "__main__":
    unittest.main()
