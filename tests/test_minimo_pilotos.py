"""Mínimo e máximo de pilotos titulares por equipe: várias propostas abertas, nunca acima dos carros, nunca abaixo
do mínimo numa corrida (PC contrata na hora; jogador e comissário não avançam a semana)."""
import copy
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, mercado, routines, acoes, campeonato, multiplayer as mp  # noqa: E402

ALFA = "formula_alfa"


def jogo(eid="tucano", minimo=None, semente=4):
    st = state.novo_jogo(db.arquivos_do_ano(2026), semente=semente)
    if eid:
        state.escolher_equipe(st, ALFA, eid)
    else:
        st["usuario"] = {"categoria": None, "equipe": None}
    for c in st["categorias"].values():
        if minimo:
            c["categoria"]["regras"]["pilotos_minimos_por_equipe"] = minimo
    return st


def titulares(st, eid, cid=ALFA):
    return [p for p in state.pilotos_da_equipe(st, cid, eid) if p["contrato"]["situacao"] == "principal"]


def livres(st, n):
    return [p for p in st["pilotos"].values() if not p.get("contrato") and not p.get("contrato_futuro")
            and not p.get("lesao") and p.get("idade", 30) < 30][:n]


def ir_para_corrida(st, cid=ALFA):
    """Coloca o jogo na semana da próxima corrida da categoria (sem simular nada)."""
    ev = min((e for e in st["categorias"][cid]["calendario"] if e.get("ativo") and e["especie"] == "corrida"),
             key=lambda e: e["semana"])
    st["semana"] = ev["semana"]
    return ev


class TestMaximo(unittest.TestCase):
    def test_varias_propostas_uma_vaga(self):
        st = jogo()
        titulares(st, "tucano")[0]["contrato"] = None            # uma vaga agora
        alvo = livres(st, 3)
        for p in alvo:
            self.assertIsNone(acoes.aplicar(st, "proposta_piloto", {"piloto": p["id"], "situacao": "principal",
                                                                     "valor": 900000, "duracao": 1,
                                                                     "unidade": "temporadas", "inicio": "agora"}))
        st["semana"] += 1
        mercado.rotina_pilotos(st, random.Random(1))
        self.assertEqual(len(titulares(st, "tucano")), 2)          # nunca acima dos carros
        self.assertTrue(any("já preencheu a vaga" in n["texto"] for n in st["noticias"]))

    def test_pc_manda_mais_propostas_que_vagas(self):
        st = jogo()
        titulares(st, "vortex")[0]["contrato"] = None
        capt = {}
        orig = mercado._pilotos_decidem
        mercado._pilotos_decidem = lambda s, ofertas, rng: capt.update(ofertas)
        try:
            mercado.rotina_pilotos(st, random.Random(2))
        finally:
            mercado._pilotos_decidem = orig
        da_vortex = [pid for pid, l in capt.items() if any(o["equipe"] == "vortex" and o["quando"] == "atual"
                                                           for o in l)]
        self.assertEqual(len(da_vortex), mercado.OFERTAS_POR_VAGA)

    def test_cada_temporada_do_contrato_precisa_de_vaga(self):
        st = jogo()
        eq = st["categorias"][ALFA]["equipes"]["tucano"]
        for p in titulares(st, "tucano"):
            p["contrato"]["temporadas"] = 1                          # vagas abrem em 2027
            p.pop("ano_aposentadoria", None)
        a, b, c = livres(st, 3)
        for p in (a, b):                                             # 2028: os dois carros já ocupados
            mercado._assinar(st, p, {"categoria": ALFA, "equipe": "tucano", "situacao": "principal",
                                     "quando": "proxima", "ano_inicio": 2028, "valor_por_corrida": 1e5,
                                     "pedido": 1e5, "duracao": 2, "unidade": "temporadas", "perspectiva": .5,
                                     "usuario": False, "compra_contrato": False}, random.Random(1))
        self.assertEqual(mercado.vagas_no_ano(st, ALFA, eq, 2027)["principal"], 2)
        erro = acoes.aplicar(st, "proposta_piloto", {"piloto": c["id"], "situacao": "principal", "valor": 1e5,
                                                     "duracao": 3, "unidade": "temporadas", "inicio": "proxima"})
        self.assertEqual(erro, "A equipe não tem vaga para essa função em 2028: o contrato tem de terminar antes.")
        mercado._assinar(st, c, {"categoria": ALFA, "equipe": "tucano", "situacao": "principal", "quando": "proxima",
                                 "ano_inicio": 2027, "valor_por_corrida": 1e5, "pedido": 1e5, "duracao": 3,
                                 "unidade": "temporadas", "perspectiva": .5, "usuario": False,
                                 "compra_contrato": False}, random.Random(1))
        self.assertEqual(mercado.fim_do_contrato(st, c["contrato_futuro"]), 2027)      # só até onde há vaga


class TestMinimo(unittest.TestCase):
    def test_pc_completa_antes_da_corrida(self):
        st = jogo(eid=None, minimo=2)
        ev = ir_para_corrida(st)
        titulares(st, "vortex")[0]["contrato"] = None
        les = titulares(st, "ventura")[0]
        les["lesao"] = {"corridas": 3, "ano": 2026, "evento": "x"}       # lesionado não conta
        mercado.garantir_minimo(st, random.Random(1))
        for eid in ("vortex", "ventura"):
            self.assertEqual(mercado.aptos_para_corrida(st, ALFA, eid, ev["id"]), 2, eid)
        self.assertLessEqual(len([p for p in titulares(st, "ventura") if not p.get("lesao")]), 2)

    def test_sem_piloto_livre_o_jogo_cria_um(self):
        st = jogo(eid=None, minimo=2)
        ev = ir_para_corrida(st)
        titulares(st, "vortex")[0]["contrato"] = None
        for p in st["pilotos"].values():
            if not p.get("contrato"):
                p["lesao"] = {"corridas": 9, "ano": 2026, "evento": "x"}    # ninguém livre e apto
        mercado.garantir_minimo(st, random.Random(1))
        self.assertEqual(mercado.aptos_para_corrida(st, ALFA, "vortex", ev["id"]), 2)
        self.assertTrue(any(p.get("ficticio") for p in titulares(st, "vortex")))

    def test_temporada_inteira_sem_equipe_abaixo_do_minimo(self):
        st = jogo(eid=None, minimo=2, semente=7)
        rng = random.Random(7)
        no_inicio = {cid: {e for e, eq in c["equipes"].items() if eq.get("ativa")} for cid, c in st["categorias"].items()}
        while st["ano"] == 2026:
            routines.avancar_semana(st, rng)
        for cid in st["categorias"]:
            for r in st["temporadas"]["2026"][cid]["corridas"]:
                if r.get("cancelada"):
                    continue
                por_eq = {}
                for x in r["resultado"]:
                    por_eq[x["equipe"]] = por_eq.get(x["equipe"], 0) + 1
                for e in no_inicio[cid] | set(por_eq):          # inclui equipes que surgiram no meio do ano
                    self.assertGreaterEqual(por_eq.get(e, 0), 2, (cid, r["evento"], e))

    def test_jogador_responde_na_hora(self):
        st = jogo(minimo=2)
        ir_para_corrida(st)
        titulares(st, "tucano")[0]["contrato"] = None
        self.assertEqual(mercado.faltam_pilotos(st, ALFA, "tucano")[0], 1)
        self.assertEqual(mercado.equipes_curtas(st, humanas_apenas=True)[0][:3], (ALFA, "tucano", 1))
        mercado.garantir_minimo(st, random.Random(1))                   # o PC não contrata pelo jogador
        self.assertEqual(mercado.faltam_pilotos(st, ALFA, "tucano")[0], 1)
        for p in livres(st, 2):                                         # duas propostas para uma vaga
            acoes.aplicar(st, "proposta_piloto", {"piloto": p["id"], "situacao": "principal", "valor": 900000,
                                                   "duracao": 1, "unidade": "temporadas", "inicio": "agora"})
        mercado.responder_agora(st, ALFA, "tucano", random.Random(1))   # sem esperar a semana seguinte
        self.assertEqual(mercado.faltam_pilotos(st, ALFA, "tucano")[0], 0)
        self.assertEqual(len(titulares(st, "tucano")), 2)

    def test_multijogador_bloqueia_a_semana(self):
        st = jogo(eid=None, minimo=2)
        mp.criar_liga(st, "Liga", [{"nome": "Ana", "categoria": ALFA, "equipe": "tucano", "senha": "a"}])
        st["multiplayer"]["politica"] = "ia"
        ir_para_corrida(st)
        titulares(st, "tucano")[0]["contrato"] = None
        sj = mp.entrar(copy.deepcopy(mp.versao_jogadores(st)), "ana", "a")
        self.assertEqual(mp.importar_ordens(st, mp.ordens_da_sessao(sj)), "ana")
        with self.assertRaises(mp.ErroLiga) as e:
            mp.rodar_semana(st, random.Random(1))
        self.assertIn("Tucano", str(e.exception))
        p = livres(st, 1)[0]
        sj = mp.entrar(copy.deepcopy(mp.versao_jogadores(st)), "ana", "a")
        self.assertIsNone(acoes.executar(sj, "proposta_piloto", piloto=p["id"], situacao="principal", valor=900000,
                                         duracao=1, unidade="temporadas", inicio="agora"))
        self.assertEqual(mp.importar_ordens(st, mp.ordens_da_sessao(sj)), "ana")
        mp.rodar_semana(st, random.Random(1))
        r = st["temporadas"]["2026"][ALFA]["corridas"][-1]
        self.assertEqual(sum(1 for x in r["resultado"] if x["equipe"] == "tucano"), 2)


class TestSubstitutoNaVirada(unittest.TestCase):
    """O titular lesionado deixa a equipe na virada: quem o substituía não fica como titular a mais."""
    def test_piloto_de_testes_volta_a_ser_de_testes(self):
        st = jogo(eid=None)
        st["semana"] = 52
        ferido, outro = titulares(st, "vortex")
        teste = next(p for p in state.pilotos_da_equipe(st, ALFA, "vortex") if p["contrato"]["situacao"] == "teste")
        for p in (ferido, teste):
            p["contrato"]["temporadas"] = 1 if p is ferido else 2
            p.pop("ano_aposentadoria", None)
        outro["contrato"]["temporadas"] = 3
        ferido["lesao"] = {"corridas": 5, "ano": 2026, "evento": "x"}
        teste["contrato"].update(situacao="principal", situacao_original="teste", substituto_de=ferido["id"])
        novo = livres(st, 1)[0]
        mercado._assinar(st, novo, {"categoria": ALFA, "equipe": "vortex", "situacao": "principal",
                                    "quando": "proxima", "ano_inicio": 2027, "valor_por_corrida": 1e5, "pedido": 1e5,
                                    "duracao": 2, "unidade": "temporadas", "perspectiva": .5, "usuario": False,
                                    "compra_contrato": False}, random.Random(1))
        routines.nova_temporada(st, random.Random(1))
        self.assertEqual(st["ano"], 2027)
        self.assertEqual(teste["contrato"]["situacao"], "teste")
        self.assertNotIn("substituto_de", teste["contrato"])
        self.assertEqual({p["id"] for p in titulares(st, "vortex")}, {outro["id"], novo["id"]})

    def test_titular_ainda_na_equipe_segue_substituido(self):
        st = jogo(eid=None)
        ferido = titulares(st, "vortex")[0]
        teste = next(p for p in state.pilotos_da_equipe(st, ALFA, "vortex") if p["contrato"]["situacao"] == "teste")
        teste["contrato"].update(situacao="principal", situacao_original="teste", substituto_de=ferido["id"])
        from automanager import saude
        saude.substitutos_sem_titular(st)
        self.assertEqual(teste["contrato"]["substituto_de"], ferido["id"])


class TestArquivo(unittest.TestCase):
    def test_validacao(self):
        d = db.carregar_arquivo(db.arquivos_do_ano(2026)[0], validar=False)
        regras = d["categoria"]["regras"]
        regras["pilotos_minimos_por_equipe"] = 2
        self.assertEqual(db.validar_minimo_pilotos(d), [])
        regras["pilotos_minimos_por_equipe"] = 3
        self.assertTrue(any("maior que os pilotos principais" in e for e in db.validar_minimo_pilotos(d)))
        regras["pilotos_minimos_por_equipe"] = 2
        p = next(p for p in d["pilotos"] if (p.get("contrato") or {}).get("equipe") == "tucano")
        p["contrato"] = None
        self.assertTrue(any(e.startswith("equipe tucano: 1 piloto(s)") for e in db.validar_minimo_pilotos(d)))


if __name__ == "__main__":
    unittest.main()
