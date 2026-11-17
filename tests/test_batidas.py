"""Batidas graves (vários carros), término antecipado com pontuação integral/parcial, lesões e mortes."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, saude, mercado, routines  # noqa: E402
from automanager.event.inscritos import montar_inscritos  # noqa: E402
from automanager.event.sessoes import Evento, SessaoCorrida  # noqa: E402

CID = "formula_alfa"


def jogo(batida=None, usuario="tucano"):
    st = state.novo_jogo(db.arquivos_do_ano(2026), semente=2)
    if usuario:
        state.escolher_equipe(st, CID, usuario)
    else:
        st["usuario"] = {"categoria": None, "equipe": None}
    cat = st["categorias"][CID]["categoria"]
    cat["clima"]["estabilidade_por_10min"] = 1.0
    cat["regras"]["batida_grave"] = dict(batida or {"prob_por_volta": 0.0})
    return st


def ate_a_corrida(st, semente=1):
    c = st["categorias"][CID]
    pista = dict(next(e for e in c["calendario"] if e["especie"] == "corrida" and e["tipo_pista"] == "mista"),
                 prob_chuva=0.0)
    ev = Evento(c["categoria"], pista, montar_inscritos(st, CID, None, pista), random.Random(semente))
    while ev.proxima_sessao():
        ev.preparar_ia()
        ev.sessao.iniciar()
        if isinstance(ev.sessao, SessaoCorrida):
            return ev
        ev.sessao.simular_ate_o_fim()


class TestPontuacaoInterrompida(unittest.TestCase):
    def _interromper(self, fracao, parciais="metade"):
        st = jogo()
        cat = st["categorias"][CID]["categoria"]
        cat["pontuacao"]["corrida_interrompida"] = {"distancia_minima": 0.5, "pontos_parciais": parciais}
        ev = ate_a_corrida(st)
        s = ev.sessao
        while s.volta_lider < int(s.total_voltas * fracao):
            s.avancar_volta()
        s.interrompida = True
        s._finalizar()
        return ev, cat["pontuacao"]

    def test_metade_abaixo_de_50(self):
        ev, pts = self._interromper(0.3)
        v = ev.resultado_corrida[0]
        extra = pts.get("pole", 0) if ev.pole is v["carro"] else 0
        vr = pts.get("volta_mais_rapida", 0) if ev.sessao.volta_mais_rapida[1] is v["carro"] else 0
        self.assertEqual(v["pontos"], (pts["posicoes"][0] + vr) / 2 + extra)

    def test_proporcional(self):
        ev, pts = self._interromper(0.3, "proporcional")
        frac = max(c.voltas for c in ev.carros if c.status == "fim") / ev.sessao.total_voltas
        segundo = ev.resultado_corrida[1]
        vr = pts.get("volta_mais_rapida", 0) if ev.sessao.volta_mais_rapida[1] is segundo["carro"] else 0
        extra = pts.get("pole", 0) if ev.pole is segundo["carro"] else 0
        self.assertAlmostEqual(segundo["pontos"], round((pts["posicoes"][1] + vr) * frac, 2) + extra, places=2)

    def test_integral_acima_de_50(self):
        ev, pts = self._interromper(0.6)
        v = ev.resultado_corrida[0]
        extra = pts.get("pole", 0) if ev.pole is v["carro"] else 0
        vr = pts.get("volta_mais_rapida", 0) if ev.sessao.volta_mais_rapida[1] is v["carro"] else 0
        self.assertEqual(v["pontos"], pts["posicoes"][0] + vr + extra)


class TestBatidaGrave(unittest.TestCase):
    def test_corrida_bandeira_vermelha_e_relargada(self):
        st = jogo({"prob_por_volta": 1.0, "prob_encerrar_sessao": 0.0, "prob_lesao": 0.0, "prob_morte": 0.0,
                   "fator_treinos": 0.0})
        ev = ate_a_corrida(st)
        s = ev.sessao
        s.avancar_volta()
        fora = [c for c in ev.carros if c.motivo == "Batida grave"]
        self.assertGreaterEqual(len(fora), 2)
        self.assertTrue(any("BATIDA GRAVE" in m for m in s.log))
        self.assertTrue(s.sc and s.sc["tipo"] == "SC")
        self.assertFalse(s.terminada)

    def test_corrida_encerrada(self):
        st = jogo({"prob_por_volta": 1.0, "prob_encerrar_sessao": 1.0, "prob_lesao": 0.0, "prob_morte": 0.0,
                   "fator_treinos": 0.0})
        ev = ate_a_corrida(st)
        for _ in range(3):
            ev.sessao.avancar_volta()
            if ev.sessao.terminada:
                break
        self.assertTrue(ev.sessao.terminada)
        self.assertTrue(ev.sessao.interrompida)

    def test_treino_encerrado(self):
        st = jogo({"prob_por_volta": 1.0, "fator_treinos": 50.0, "prob_encerrar_sessao": 1.0,
                   "prob_lesao": 0.0, "prob_morte": 0.0})
        c = st["categorias"][CID]
        pista = dict(next(e for e in c["calendario"] if e["especie"] == "corrida"), prob_chuva=0.0)
        ev = Evento(c["categoria"], pista, montar_inscritos(st, CID, None, pista), random.Random(3))
        ev.proxima_sessao()
        ev.preparar_ia()
        ev.sessao.iniciar()
        ev.sessao.simular_ate_o_fim()
        self.assertTrue(ev.sessao.terminada)
        self.assertTrue(getattr(ev.sessao, "encerrada_chuva", False))
        self.assertTrue(any("BATIDA GRAVE" in m for m in ev.sessao.log))

    def test_padroes_pequenos(self):
        b = saude.PADRAO
        self.assertLess(b["prob_morte"], 0.01)
        self.assertLess(b["prob_lesao"], 0.1)


class TestLesaoEMorte(unittest.TestCase):
    def _principal(self, st, eid):
        return next(p for p in state.pilotos_da_equipe(st, CID, eid) if p["contrato"]["situacao"] == "principal")

    def test_lesao_ia_promove_teste_e_volta(self):
        st = jogo()
        p = self._principal(st, "vortex")
        antes = dict(p["atributos"])
        saude.lesionar(st, CID, p, random.Random(1), "teste")
        self.assertTrue(p["lesao"]["corridas"] >= 1)
        self.assertTrue(all(p["atributos"][k] <= antes[k] for k in antes))
        self.assertLess(sum(p["atributos"].values()), sum(antes.values()))
        sub = [x for x in state.pilotos_da_equipe(st, CID, "vortex") if x["contrato"].get("substituto_de") == p["id"]]
        self.assertEqual(len(sub), 1)
        pista = next(e for e in st["categorias"][CID]["calendario"] if e["especie"] == "corrida")
        ids = {i["piloto"]["id"] for i in montar_inscritos(st, CID, None, pista)}
        self.assertNotIn(p["id"], ids)
        self.assertIn(sub[0]["id"], ids)
        for _ in range(p["lesao"]["corridas"]):
            saude.fim_de_corrida(st, CID)
        self.assertNotIn("lesao", p)
        self.assertEqual(sub[0]["contrato"]["situacao"], "teste")
        self.assertIn(p["id"], {i["piloto"]["id"] for i in montar_inscritos(st, CID, None, pista)})

    def test_equipe_do_jogador_nao_corre_ate_contratar(self):
        st = jogo()
        p = self._principal(st, "tucano")
        saude.lesionar(st, CID, p, random.Random(1))
        self.assertTrue(any("ATENÇÃO" in n["texto"] and "Contrate" in n["texto"] for n in st["noticias"]))
        pista = next(e for e in st["categorias"][CID]["calendario"] if e["especie"] == "corrida")
        tucano = [i for i in montar_inscritos(st, CID, None, pista) if i["equipe"]["id"] == "tucano"]
        self.assertEqual(len(tucano), 1)                            # só um carro
        self.assertEqual(mercado.vagas(st, CID, st["categorias"][CID]["equipes"]["tucano"])[0]["principal"], 1)
        # o jogador contrata: o contrato vale; quando o titular volta, o jogador decide quem dispensar
        livre = next(x for x in st["pilotos"].values() if mercado.livre_agora(x) and not x.get("lesao"))
        mercado._assinar(st, livre, {"categoria": CID, "equipe": "tucano", "situacao": "principal", "quando": "atual",
                                     "valor_por_corrida": 1000, "duracao": 2, "unidade": "temporadas"},
                         random.Random(1))
        self.assertIsNone(livre["contrato"].get("substituto_de"))
        for _ in range(p["lesao"]["corridas"]):
            saude.fim_de_corrida(st, CID)
        self.assertIsNotNone(livre["contrato"])                     # continua na equipe
        self.assertTrue(any("Decida quem dispensar" in n["texto"] for n in st["noticias"]))
        corre = {i["piloto"]["id"] for i in montar_inscritos(st, CID, None, pista) if i["equipe"]["id"] == "tucano"}
        self.assertEqual(len(corre), 2)
        self.assertIn(p["id"], corre)                                # contrato mais antigo corre
        self.assertNotIn(livre["id"], corre)
        mercado.rescindir_piloto(st, p["id"])                        # o jogador escolhe dispensar o titular
        corre = {i["piloto"]["id"] for i in montar_inscritos(st, CID, None, pista) if i["equipe"]["id"] == "tucano"}
        self.assertIn(livre["id"], corre)

    def test_morte(self):
        st = jogo()
        p = self._principal(st, "ventura")
        saude.falecer(st, CID, p, "teste")
        self.assertNotIn(p["id"], st["pilotos"])
        self.assertIn(p["id"], st["falecidos"])
        self.assertTrue(any(n["texto"].startswith("LUTO") for n in st["noticias"]))
        principais = [x for x in state.pilotos_da_equipe(st, CID, "ventura") if x["contrato"]["situacao"] == "principal"]
        self.assertEqual(len(principais), 2)                         # o piloto de testes assumiu de vez
        self.assertFalse(any(x["contrato"].get("substituto_de") for x in principais))

    def test_vitimas_do_evento_chegam_ao_jogo(self):
        st = jogo({"prob_por_volta": 1.0, "prob_encerrar_sessao": 0.0, "prob_lesao": 1.0, "prob_morte": 0.0,
                   "fator_treinos": 0.0})
        st["usuario"] = {"categoria": None, "equipe": None}
        ev = ate_a_corrida(st)
        ev.sessao.avancar_volta()
        self.assertTrue(ev.vitimas)
        while not ev.sessao.terminada:
            ev.sessao.avancar_volta()
        from automanager import campeonato
        campeonato.registrar_corrida(st, CID, ev.pista, ev)
        for v in ev.vitimas:
            self.assertTrue(st["pilotos"][v["piloto"]].get("lesao"))
        # a lesão não é descontada na própria corrida
        n = {v["piloto"]: st["pilotos"][v["piloto"]]["lesao"]["corridas"] for v in ev.vitimas}
        saude.fim_de_corrida(st, CID, ev.pista["id"])
        self.assertEqual(n, {v["piloto"]: st["pilotos"][v["piloto"]]["lesao"]["corridas"] for v in ev.vitimas})

    def test_multijogador_semana_da_ia_nao_contrata(self):
        from automanager import multiplayer as mp
        st = jogo(usuario=None)
        mp.criar_liga(st, "Liga", [{"nome": "Ana", "categoria": CID, "equipe": "tucano", "senha": "a"}], "ia")
        st["multiplayer"]["ia_nesta_semana"] = ["ana"]
        p = self._principal(st, "tucano")
        saude.lesionar(st, CID, p, random.Random(1))
        for _ in range(3):
            mercado.rotina_pilotos(st, random.Random(2))
            st["semana"] += 1
        principais = [x for x in state.pilotos_da_equipe(st, CID, "tucano") if x["contrato"]["situacao"] == "principal"]
        self.assertEqual(len(principais), 2)                         # o lesionado + o outro titular, ninguém novo


if __name__ == "__main__":
    unittest.main()
