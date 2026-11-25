"""Regras de pneus por categoria (troca_de_pneus, compostos_disponiveis, intermediário/chuva) e box manual
do jogador a qualquer momento (só no jogo individual; no multijogador vale o plano de stints)."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state  # noqa: E402
from automanager.event.inscritos import montar_inscritos  # noqa: E402
from automanager.event.modelo import tipo_pneu  # noqa: E402
from automanager.event.sessoes import Evento, SessaoCorrida  # noqa: E402
from automanager.event import planos as planos_evento  # noqa: E402


def ate_a_corrida(cid="formula_alfa", ajustar=None, eid=None, semente=5, clima="seco"):
    st = state.novo_jogo(db.arquivos_do_ano(2026))
    c = st["categorias"][cid]
    cat = c["categoria"]
    cat["clima"]["estabilidade_por_10min"] = 1.0          # clima não muda sozinho durante o teste
    if ajustar:
        ajustar(cat)
    pista = dict(next(e for e in c["calendario"] if e["especie"] == "corrida" and e.get("ativo")))
    pista["prob_chuva"] = 0.0
    ev = Evento(cat, pista, montar_inscritos(st, cid, eid, pista), random.Random(semente))
    while ev.proxima_sessao():
        if isinstance(ev.sessao, SessaoCorrida):
            break
        ev.preparar_ia()
        ev.sessao.iniciar()
        ev.sessao.simular_ate_o_fim()
    ev.clima.estado = clima
    for car in ev.carros:
        if car.usuario:
            car.pneu_inicial = next(k for k in ev.compostos_disponiveis() if tipo_pneu(cat, k) == "seco")
            car.combustivel_inicial = None
    ev.preparar_ia()
    ev.sessao.iniciar()
    return st, ev


def rodar(ev, voltas, cada_volta=None):
    trocas = []
    for _ in range(voltas):
        antes = {c.id: c.pneu for c in ev.carros}
        ev.sessao.avancar_volta()
        for c in ev.carros:
            if c.pneu != antes[c.id]:
                trocas.append((ev.sessao.volta_lider, c.id, antes[c.id], c.pneu))
        if cada_volta:
            cada_volta(ev)
        if ev.sessao.terminada:
            break
    return trocas


class TestRegrasDePneus(unittest.TestCase):
    def test_sem_troca_de_pneus_no_seco(self):
        def sem_troca(cat):
            cat["regras_pitstop"].update({"troca_de_pneus": False, "obrigatorio": False, "paradas_minimas": 0})
        _, ev = ate_a_corrida(ajustar=sem_troca)
        iniciais = {c.id: c.pneu for c in ev.carros}
        trocas = rodar(ev, 500)
        self.assertTrue(ev.sessao.terminada)
        self.assertEqual(trocas, [])
        self.assertEqual({c.id: c.pneu for c in ev.carros}, iniciais)

    def test_sem_troca_so_muda_quando_o_clima_obriga(self):
        def sem_troca(cat):
            cat["regras_pitstop"].update({"troca_de_pneus": False, "obrigatorio": False, "paradas_minimas": 0})
        _, ev = ate_a_corrida(ajustar=sem_troca)
        rodar(ev, 10)
        ev.clima.estado = "chuva_pesada"
        trocas = rodar(ev, 15)
        self.assertTrue(trocas)
        for _, _, de, para in trocas:
            self.assertEqual(tipo_pneu(ev.cat, para), "chuva_pesada")
        # chamar ao box para um pneu do tipo errado não troca
        c = next(c for c in ev.carros if c.status == "pista")
        p0, n0 = c.pneu, c.paradas
        c.chamado_box = "macio"
        rodar(ev, 1)
        self.assertEqual(c.pneu, p0)
        self.assertEqual(c.paradas, n0 + 1)

    def test_compostos_disponiveis_respeitados(self):
        def poucos(cat):
            cat["pneus"]["compostos_disponiveis"] = ["medio", "duro", "chuva_leve", "chuva_pesada"]
        _, ev = ate_a_corrida(ajustar=poucos)
        rodar(ev, 500)
        usados = set().union(*(c.compostos_usados for c in ev.carros)) | {c.pneu for c in ev.carros}
        self.assertLessEqual(usados, {"medio", "duro", "chuva_leve", "chuva_pesada"})
        self.assertGreater(sum(c.paradas for c in ev.carros), 0)
        # categoria Beta do banco de exemplo: macio, duro, chuva leve e chuva pesada
        _, ev = ate_a_corrida("formula_beta")
        rodar(ev, 500)
        usados = set().union(*(c.compostos_usados for c in ev.carros)) | {c.pneu for c in ev.carros}
        self.assertLessEqual(usados, set(ev.cat["pneus"]["compostos_disponiveis"]))

    def test_composto_fora_da_lista_e_recusado_no_box(self):
        def poucos(cat):
            cat["pneus"]["compostos_disponiveis"] = ["medio", "duro", "chuva_leve", "chuva_pesada"]
        _, ev = ate_a_corrida(ajustar=poucos)
        rodar(ev, 3)
        c = next(c for c in ev.carros if c.status == "pista")
        p0 = c.pneu
        c.chamado_box = "super_macio"
        rodar(ev, 1)
        self.assertEqual(c.pneu, p0)

    def test_plano_multijogador_sem_troca_usa_um_composto(self):
        n = planos_evento.normalizar({"corrida": {"paradas": [["macio", 20], ["duro", 30]]}},
                                     ["macio", "duro"], troca_de_pneus=False)
        self.assertEqual({s[0] for s in n["corrida"]["paradas"]}, {"macio"})
        n = planos_evento.normalizar({"corrida": {"paradas": [["super_macio", 20], ["duro", 30]]}},
                                     ["macio", "duro"])
        self.assertNotIn("super_macio", {s[0] for s in n["corrida"]["paradas"]})


class TestBoxManual(unittest.TestCase):
    """No jogo individual o jogador chama o carro ao box quando quiser, com qualquer composto disponível
    (macio, médio, duro, intermediário = chuva leve, chuva = chuva pesada), além das paradas planejadas."""

    def test_box_a_qualquer_momento(self):
        _, ev = ate_a_corrida(eid="tucano")
        ev.modelo.sim["taxa_quebra_base"] = ev.modelo.sim["taxa_acidente_base"] = 0.0   # o teste é do box: sem
        meu = next(c for c in ev.carros if c.usuario)                                   # quebra/batida que tire o carro
        meu.estrategia_auto = False
        sequencia = {2: "chuva_leve", 4: "chuva_pesada", 7: "macio", 8: "medio", 12: "duro"}
        visto = []

        def chamar(e):
            v = e.sessao.volta_lider
            if v in sequencia and meu.status == "pista":
                meu.chamado_box = sequencia[v]
            visto.append((v, meu.pneu, meu.paradas))
        rodar(ev, 14, chamar)
        pneus = [p for _, p, _ in visto]
        for comp in sequencia.values():
            self.assertIn(comp, pneus)
        self.assertEqual(meu.paradas, len(sequencia))
        self.assertEqual(dict((v, p) for v, p, _ in visto)[3], "chuva_leve")
        self.assertEqual(dict((v, p) for v, p, _ in visto)[13], "duro")

    def test_sem_chamar_nao_para(self):
        _, ev = ate_a_corrida(eid="tucano")
        meu = next(c for c in ev.carros if c.usuario)
        meu.estrategia_auto = False
        rodar(ev, 20)
        furos = sum(1 for m in ev.sessao.log if meu.nome in str(m) and "pneu furado" in str(m))
        self.assertEqual(meu.paradas, furos)          # só o furo obriga a parar sem o jogador chamar


if __name__ == "__main__":
    unittest.main()


class TestEstrategiaEUltrapassagem(unittest.TestCase):
    def test_equipes_variam_a_estrategia(self):
        _, ev = ate_a_corrida()
        planos = {tuple(map(tuple, c.plano_corrida)) for c in ev.carros if not c.usuario}
        self.assertGreater(len(planos), len(ev.carros) // 3)
        compostos = {s[0] for p in planos for s in p}
        self.assertGreater(len(compostos), 1)
        for p in planos:
            self.assertEqual(sum(n for _, n in p), ev.sessao.total_voltas)

    def test_jogador_recebe_a_melhor(self):
        from automanager.event.sessoes import planejar
        _, ev = ate_a_corrida(eid="tucano")
        meu = next(c for c in ev.carros if c.usuario)
        a = planejar(ev, meu, ev.sessao.total_voltas, 1)
        b = planejar(ev, meu, ev.sessao.total_voltas, 1)
        self.assertEqual(a, b)

    def test_ultrapassar_depende_das_retas(self):
        from automanager.event.sessoes import fator_ultrapassagem_pista
        sim = {}
        f = [fator_ultrapassagem_pista({"tipo_pista": "mista"}, {"retas": r}, sim) for r in (0.15, 0.3, 0.45, 0.6)]
        self.assertEqual(f, sorted(f))
        self.assertGreater(f[-1] / f[0], 10)
        self.assertLess(fator_ultrapassagem_pista({"tipo_pista": "rua"}, {"retas": 0.4}, sim),
                        fator_ultrapassagem_pista({"tipo_pista": "mista"}, {"retas": 0.4}, sim))


class TestDoisCompostos(unittest.TestCase):
    @staticmethod
    def _liga(cat, pen=0):
        cat["regras_pitstop"].update({"dois_compostos_secos": True, "penalidade_dois_compostos_s": pen})
        cat["pneus"]["desgaste_critico"] = 10000          # sem furos: o teste depende só da regra
        cat["regras"]["batida_grave"] = {"prob_por_volta": 0.0}

    def test_ia_cumpre(self):
        from automanager.event.sessoes import cumpre_dois_compostos
        _, ev = ate_a_corrida(ajustar=self._liga)
        for c in ev.carros:
            if not c.usuario:
                self.assertTrue(cumpre_dois_compostos(ev.cat, {k for k, _ in c.plano_corrida}), c.plano_corrida)
        rodar(ev, 500)
        self.assertTrue(ev.sessao.terminada)
        fim = [c for c in ev.carros if c.status == "fim"]
        self.assertTrue(fim)
        for c in fim:
            self.assertTrue(cumpre_dois_compostos(ev.cat, c.compostos_usados | {c.pneu}), c.nome)

    def test_quem_nao_cumpre_e_desclassificado(self):
        _, ev = ate_a_corrida(ajustar=self._liga, eid="tucano")
        meu = next(c for c in ev.carros if c.usuario)
        meu.estrategia_auto = False

        def chamar(e):
            if e.sessao.volta_lider == 20 and meu.status == "pista":
                meu.chamado_box = meu.pneu               # troca para o mesmo composto
        rodar(ev, 500, chamar)
        if meu.motivo not in (None, "", "Desclassificado"):
            self.skipTest("abandonou por outro motivo")
        self.assertEqual(meu.status, "abandono")
        self.assertEqual(meu.motivo, "Desclassificado")
        linha = next(r for r in ev.resultado_corrida if r["carro"] is meu)
        self.assertEqual(linha["pontos"], 0)

    def test_penalidade_em_segundos(self):
        def ajustar(cat):
            self._liga(cat, 30)
            cat["simulacao"].update({"taxa_acidente_base": 0.0, "taxa_quebra_base": 0.0})
        _, ev = ate_a_corrida(ajustar=ajustar, eid="tucano")
        meu = next(c for c in ev.carros if c.usuario)
        meu.estrategia_auto = False
        rodar(ev, 500)
        if meu.motivo:
            self.skipTest("abandonou")
        self.assertEqual(meu.status, "fim")
        self.assertTrue(any("30 s de penalidade" in m and meu.nome in m for m in ev.sessao.log))

    def test_desligada_por_padrao(self):
        _, ev = ate_a_corrida(eid="tucano")
        meu = next(c for c in ev.carros if c.usuario)
        meu.estrategia_auto = False
        rodar(ev, 500)
        self.assertNotEqual(meu.motivo, "Desclassificado")
