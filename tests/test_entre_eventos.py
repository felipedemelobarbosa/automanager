"""Variáveis que passam de um evento para o outro e constantes que não podem mudar dentro da temporada.

Uma temporada inteira (todas as equipes com a IA) é rodada semana a semana; depois de cada semana conferimos:
forma dos pilotos, uso e cota de motores, lastro pelo campeonato, contratos por corrida, pontos, caixa x
lançamentos e as constantes da categoria. Testes menores conferem o que zera a cada evento."""
import copy
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, routines, campeonato, contratos  # noqa: E402
from automanager.event.inscritos import montar_inscritos  # noqa: E402
from automanager.event.sessoes import Evento  # noqa: E402

CONSTANTES = ("regras", "pneus", "clima", "formato_evento", "ponderacao", "simulacao", "pontuacao",
              "regras_pitstop", "tier", "mobilidade")


def jogo_ia():
    st = state.novo_jogo(db.arquivos_do_ano(2026))
    st["usuario"] = {"categoria": None, "equipe": None}
    return st


def soma_lancamentos(eq):
    a = eq["financas"]["ano"]
    return sum(a["receitas"].values()) - sum(a["despesas"].values())


def corridas(st, cid):
    return campeonato._temporada(st, cid)["corridas"]


class TestTemporadaEntreEventos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.st = st = jogo_ia()
        rng = random.Random(11)
        cls.falhas = []
        ano = st["ano"]
        constantes = {cid: copy.deepcopy({k: c["categoria"].get(k) for k in CONSTANTES})
                      for cid, c in st["categorias"].items()}
        caixa0 = {(cid, e["id"]): e["financas"]["caixa"] - soma_lancamentos(e)
                  for cid, c in st["categorias"].items() for e in c["equipes"].values()}
        uso_ant = {}
        cls.formas = {}
        cls.semanas_treino = cls.semanas_corrida = 0
        while st["ano"] == ano:
            antes_ct = {pid: copy.deepcopy(p.get("contrato")) for pid, p in st["pilotos"].items()}
            n_corr = {cid: len(corridas(st, cid)) for cid in st["categorias"]}
            semana = st["semana"]
            routines.avancar_semana(st, rng)
            if st["ano"] != ano:
                break
            for cid, c in st["categorias"].items():
                novas = corridas(st, cid)[n_corr[cid]:]
                houve_corrida = bool(novas)
                houve_treino = any(e["semana"] == semana and e["especie"] == "treino" and e.get("ativo")
                                   for e in c["calendario"])
                cls.semanas_corrida += houve_corrida
                cls.semanas_treino += houve_treino and not houve_corrida
                # constantes da categoria
                atual = {k: c["categoria"].get(k) for k in CONSTANTES}
                if atual != constantes[cid]:
                    cls.falhas.append(f"{cid} s{semana}: constantes da categoria mudaram")
                # contratos por corrida: só diminuem quando há corrida, e de 1 em 1
                for pid, ct0 in antes_ct.items():
                    if not ct0 or ct0.get("categoria") != cid or not contratos.por_corridas(ct0):
                        continue
                    ct1 = (st["pilotos"].get(pid) or {}).get("contrato")
                    if not ct1 or ct1.get("equipe") != ct0["equipe"]:
                        continue
                    d = ct0["corridas"] - ct1["corridas"]
                    if not houve_corrida and d != 0:
                        cls.falhas.append(f"{pid}: contrato por corrida mudou sem corrida (s{semana})")
                    if d not in (0, 1):
                        cls.falhas.append(f"{pid}: contrato por corrida diminuiu {d} numa semana")
                # motores: o uso só cresce dentro da temporada, exceto quando entra motor novo (usados + 1)
                for eq in c["equipes"].values():
                    for pid, reg in (eq.get("motores") or {}).items():
                        k = (cid, eq["id"], pid)
                        if k in uso_ant:
                            u0, n0 = uso_ant[k]
                            if reg["usados"] < n0 or (reg["usados"] == n0 and reg["uso"] < u0):
                                cls.falhas.append(f"{k}: uso do motor voltou atrás sem motor novo")
                        uso_ant[k] = (reg["uso"], reg["usados"])
                # caixa = saldo inicial + lançamentos do ano
                for eq in c["equipes"].values():
                    k = (cid, eq["id"])
                    if k in caixa0 and eq.get("ativa"):
                        dif = eq["financas"]["caixa"] - soma_lancamentos(eq) - caixa0[k]
                        if abs(dif) > 1e-3 * max(1.0, abs(caixa0[k])):
                            cls.falhas.append(f"{k} s{semana}: caixa difere dos lançamentos em {dif:.2f}")
                if houve_corrida:
                    for p in st["pilotos"].values():
                        cls.formas.setdefault(p["id"], []).append(p.get("forma", 0.0))
        cls.ano = ano
        cls.motores_na_virada = [eq.get("motores") for c in st["categorias"].values() for eq in c["equipes"].values()]
        routines.avancar_semana(st, rng) if st["ano"] == ano else None

    def test_sem_falhas_semana_a_semana(self):
        self.assertEqual(self.falhas, [], "\n".join(self.falhas[:20]))
        self.assertGreater(self.semanas_corrida, 10)
        self.assertGreater(self.semanas_treino, 0)

    def test_pontos_somam(self):
        st = self.st
        for cid in st["categorias"]:
            t = st["temporadas"][str(self.ano)][cid]
            pil, eqs = campeonato._somar(t["corridas"])
            total = sum(l["pontos"] for r in t["corridas"] for l in r["resultado"])
            self.assertAlmostEqual(sum(p["pontos"] for p in pil), total)
            self.assertAlmostEqual(sum(e["pontos"] for e in eqs), total)
            for r in t["corridas"]:
                pts = sorted((l["pontos"] for l in r["resultado"]), reverse=True)
                self.assertEqual([l["pontos"] for l in sorted(r["resultado"], key=lambda l: l["pos"])][:len(pts)],
                                 [l["pontos"] for l in sorted(r["resultado"], key=lambda l: l["pos"])])
                self.assertEqual(sorted(l["pos"] for l in r["resultado"]), list(range(1, len(r["resultado"]) + 1)))
            final = t.get("final")
            self.assertTrue(final and final["pilotos"])
            self.assertEqual(final["pilotos"][0]["id"], pil[0]["id"])

    def test_forma_encadeada_e_limitada(self):
        mudou = 0
        for pid, f in self.formas.items():
            self.assertTrue(all(abs(x) < 0.02 for x in f), pid)
            mudou += len(set(f)) > 1
        self.assertGreater(mudou, 10)

    def test_motores_zerados_na_virada(self):
        self.assertGreater(self.st["ano"], self.ano)
        for c in self.st["categorias"].values():
            for eq in c["equipes"].values():
                self.assertFalse(eq.get("motores"), eq["id"])


class TestEvento(unittest.TestCase):
    def _evento(self, st, cid="formula_alfa", ordem=None, semente=1):
        c = st["categorias"][cid]
        pista = next(e for e in c["calendario"] if e["especie"] == "corrida" and e.get("ativo"))
        return Evento(c["categoria"], pista, montar_inscritos(st, cid, None, pista), random.Random(semente),
                      ordem_campeonato=ordem), pista

    def test_tudo_zera_a_cada_evento(self):
        st = jogo_ia()
        ev, _ = self._evento(st)
        while ev.proxima_sessao():
            ev.sessao.iniciar()
            ev.sessao.simular_ate_o_fim()
        self.assertGreater(ev.voltas_pista, 0)
        ev2, _ = self._evento(st, semente=2)
        self.assertEqual(ev2.voltas_pista, 0.0)
        self.assertEqual(ev2.evolucao(), 0.0)
        for c in ev2.carros:
            self.assertEqual(c.dano, 0.0)
            self.assertEqual(c.voltas_evento, 0)

    def test_lastro_pela_ordem_do_campeonato(self):
        st = jogo_ia()
        regras = st["categorias"]["formula_alfa"]["categoria"]["regras"]
        regras["lastro_por_posicao"] = [30, 20, 10]
        ev0, _ = self._evento(st)
        ids = [c.id for c in ev0.carros][::-1]
        ev, _ = self._evento(st, ordem=ids)
        lastro = {c.id: c.lastro for c in ev.carros}
        self.assertEqual([lastro.get(i) for i in ids[:3]], [30.0, 20.0, 10.0])
        self.assertTrue(all(lastro[i] == 0 for i in ids[3:] if i in lastro))

    def test_cota_de_motores_e_punicao(self):
        st = jogo_ia()
        cat = st["categorias"]["formula_alfa"]["categoria"]
        cat["regras"]["motores_por_temporada"] = 1
        cat["simulacao"]["vida_motor_voltas"] = 50
        ev, _ = self._evento(st)
        ev.gravar_uso_motor()
        eq = ev.carros[0].equipe
        pid = ev.carros[0].id
        eq["motores"][pid]["uso"] = 49.0          # perto do fim da vida: o próximo evento troca o motor
        ev2, _ = self._evento(st, semente=3)
        c = next(c for c in ev2.carros if c.id == pid)
        self.assertEqual(eq["motores"][pid]["usados"], 2)
        self.assertEqual(c.uso_motor, 0.0)
        self.assertEqual(c.penalidade_grid, 10)
        self.assertTrue(any(c.nome in n for n in ev2.notas))
        outro = next(x for x in ev2.carros if x.id != pid and x.equipe is not eq)
        self.assertEqual(outro.penalidade_grid, 0)


if __name__ == "__main__":
    unittest.main()
