"""Mudanças de regulamento, peças de fornecedor que mudam a cada ano e negociação de chassis/motor."""
import os
import random
import statistics as S
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, regulamento, fornecedores, mercado, acoes, routines, desenvolvimento as dev  # noqa: E402
from automanager import multiplayer as mp  # noqa: E402
import copy  # noqa: E402

ALFA, BETA = "formula_alfa", "formula_beta"


def jogo(usuario=(ALFA, "tucano")):
    st = state.novo_jogo(db.arquivos_do_ano(2026), semente=4)
    if usuario:
        state.escolher_equipe(st, *usuario)
    else:
        st["usuario"] = {"categoria": None, "equipe": None}
    return st


def forcar(st, cid, **probs):
    reg = st["categorias"][cid]["categoria"].setdefault("regulamento", {})
    reg.update({"ativo": True, "prob_grande_mudanca": 0, "prob_limite_desenvolvimento": 0,
                "prob_ajuste_importancia": 0}, **probs)
    regulamento.estado(st["categorias"][cid])


def anunciar(st, cid, rng=None):
    st["semana"] = int(regulamento.cfg(st["categorias"][cid]["categoria"])["semana_anuncio"])
    return regulamento.semanal(st, rng or random.Random(1))


def virar(st, cid, rng=None):
    st["ano"] += 1
    st["semana"] = 1
    dev.aplicar_projetos(st, st["ano"])
    fornecedores.evoluir(st, rng or random.Random(2))
    regulamento.virada(st, cid)


class TestRegulamento(unittest.TestCase):
    def test_exemplo_liga_e_importacao_desliga(self):
        st = jogo()
        self.assertTrue(regulamento.cfg(st["categorias"][ALFA]["categoria"])["ativo"])
        self.assertFalse(regulamento.PADRAO["ativo"])        # arquivo sem o bloco (importado): desligado

    def test_grande_mudanca(self):
        st = jogo()
        forcar(st, ALFA, prob_grande_mudanca=1.0, perda_grande_mudanca=[0.2, 0.2], aumento_importancia_carro=[0.1, 0.1])
        eq = st["categorias"][ALFA]["equipes"]["tucano"]
        antes = dev.valores_projeto(st, ALFA, eq, "chassis")
        self.assertEqual(anunciar(st, ALFA), [ALFA])
        self.assertAlmostEqual(dev.perda_manutencao(st, ALFA, "chassis"), 0.5)
        depois = dev.valores_projeto(st, ALFA, eq, "chassis")
        self.assertTrue(all(depois[k] < antes[k] for k in antes))       # a manutenção rende menos
        self.assertEqual(dev.perda_manutencao(st, ALFA, "motor"), 0.3)   # só o chassis
        atuais = dev.valores_atuais(st, ALFA, eq, "chassis")
        virar(st, ALFA)
        regras = st["categorias"][ALFA]["categoria"]["regras"]
        self.assertAlmostEqual(regras["importancia_carro"], 0.7)
        self.assertAlmostEqual(regras["importancia_carro"] + regras["importancia_piloto"], 1.0)
        novo = dev.valores_atuais(st, ALFA, eq, "chassis")
        self.assertEqual(novo, {k: int(v * 0.5) for k, v in atuais.items()})
        self.assertTrue(any("grande mudança" in h["texto"] for h in st["categorias"][ALFA]["regulamento"]["historico"]))

    def test_importancia_volta_ao_valor_da_database(self):
        st = jogo()
        forcar(st, ALFA)
        regras = st["categorias"][ALFA]["categoria"]["regras"]
        regras["importancia_carro"], regras["importancia_piloto"] = 0.7, 0.3
        for _ in range(3):
            virar(st, ALFA)
        self.assertAlmostEqual(regras["importancia_carro"], 0.64)
        for _ in range(10):
            virar(st, ALFA)
        self.assertAlmostEqual(regras["importancia_carro"], 0.6)          # não passa do valor da database

    def test_congelamento(self):
        st = jogo()
        forcar(st, ALFA, prob_limite_desenvolvimento=1.0, prob_congelamento=1.0, limite_duracao=[3, 3])
        st["categorias"][ALFA]["categoria"]["regulamento"]["prob_limite_desenvolvimento"] = 1.0
        rng = random.Random(1)
        while True:                                                       # sorteia até cair no chassis
            st2 = jogo()
            forcar(st2, ALFA, prob_limite_desenvolvimento=1.0, prob_congelamento=1.0, limite_duracao=[3, 3])
            anunciar(st2, ALFA, rng)
            an = st2["categorias"][ALFA]["regulamento"]["anuncio"]["mudancas"][0]
            if an["parte"] == "chassis":
                st = st2
                break
        ano = st["ano"]
        self.assertEqual(regulamento.limite(st, ALFA, "chassis", ano + 1), 0)
        self.assertTrue(dev.projeto_permitido(st, ALFA, "chassis"))      # 1ª temporada: projeto do carro congelado
        eq = st["categorias"][ALFA]["equipes"]["tucano"]
        virar(st, ALFA)
        alvo = {k: v + 1 for k, v in dev.valores_atuais(st, ALFA, eq, "chassis").items()}
        with self.assertRaises(ValueError):
            dev.investir_atual(st, ALFA, eq, "chassis", alvo)
        self.assertFalse(dev.projeto_permitido(st, ALFA, "chassis"))
        self.assertEqual(acoes.aplicar(st, "dev_modo", {"parte": "chassis", "modo": "novo"}),
                         "Regulamento: não há projeto novo enquanto vale o limite de desenvolvimento.")
        atuais = dev.valores_atuais(st, ALFA, eq, "chassis")
        self.assertEqual(dev.valores_projeto(st, ALFA, eq, "chassis"), atuais)   # passa sem perda
        virar(st, ALFA)
        self.assertEqual(dev.valores_atuais(st, ALFA, eq, "chassis"), atuais)
        virar(st, ALFA)                                                   # última temporada do limite
        self.assertTrue(dev.projeto_permitido(st, ALFA, "chassis"))
        virar(st, ALFA)
        self.assertIsNone(regulamento.limite(st, ALFA, "chassis"))
        self.assertEqual(st["categorias"][ALFA]["regulamento"]["limites"], [])

    def test_limite_de_pontos_na_ia(self):
        st = jogo()
        st["categorias"][ALFA]["regulamento"] = {"limites": [{"parte": "chassis", "pontos": 3, "de": st["ano"],
                                                              "ate": st["ano"] + 1}], "historico": []}
        eq = st["categorias"][ALFA]["equipes"]["vortex"]
        antes = dev.valores_atuais(st, ALFA, eq, "chassis")
        eq["financas"]["caixa"] = 1e12
        dev._gastar_guloso(st, ALFA, eq, "chassis", 1e11, False)
        dev._gastar_guloso(st, ALFA, eq, "chassis", 1e11, False)
        depois = dev.valores_atuais(st, ALFA, eq, "chassis")
        self.assertTrue(all(depois[k] - antes[k] <= 3 for k in antes))
        self.assertTrue(any(depois[k] - antes[k] == 3 for k in antes))

    def test_temporadas_com_regulamento_ligado(self):
        st = jogo(None)
        for c in st["categorias"].values():
            c["categoria"]["regulamento"].update(prob_grande_mudanca=0.5, prob_limite_desenvolvimento=0.5)
        rng = random.Random(3)
        ano0 = st["ano"]
        while st["ano"] < ano0 + 3:
            routines.avancar_semana(st, rng)
        hist = st["categorias"][ALFA]["regulamento"]["historico"]
        self.assertTrue(hist)
        for c in st["categorias"].values():
            r = c["categoria"]["regras"]
            self.assertAlmostEqual(r["importancia_carro"] + r["importancia_piloto"], 1.0)
            self.assertTrue(0.3 <= r["importancia_carro"] <= 0.8)


class TestFornecedores(unittest.TestCase):
    def test_chassis_e_motores_da_beta_mudam(self):
        st = jogo(None)
        c = st["categorias"][BETA]
        self.assertEqual(len(fornecedores.pecas(st, BETA, "chassis")), len(c["chassis"]))
        self.assertEqual(fornecedores.pecas(st, ALFA, "chassis"), [])     # a Alfa desenvolve o próprio
        antes = {k: dict(v["atributos"]) for k, v in c["chassis"].items()}
        preco = {k: v["contrato"]["valor_por_corrida"] for k, v in c["chassis"].items()}
        st["ano"] += 1
        fornecedores.evoluir(st, random.Random(5))
        mudou = [k for k in antes if c["chassis"][k]["atributos"] != antes[k]]
        self.assertTrue(mudou)
        for k in mudou:
            n0 = S.mean(antes[k].values())
            n1 = S.mean(c["chassis"][k]["atributos"].values())
            if round(n0) != round(n1):
                self.assertAlmostEqual(c["chassis"][k]["contrato"]["valor_por_corrida"], round(preco[k] * n1 / n0, -2))

    def test_nivel_da_database_se_mantem(self):
        st = jogo(None)
        c = st["categorias"][BETA]
        ref = fornecedores._referencia(st, BETA, "chassis")
        rng = random.Random(9)
        niveis = []
        for _ in range(30):
            st["ano"] += 1
            fornecedores.evoluir(st, rng)
            niveis.append(S.mean(S.mean(ch["atributos"].values()) for ch in c["chassis"].values()))
        self.assertLess(abs(S.mean(niveis[10:]) - ref), 2.5)

    def test_modelo_novo_troca_o_ano_no_nome(self):
        st = jogo(None)
        c = st["categorias"][BETA]
        c["categoria"]["regras"]["evolucao_fornecedores"] = {"prob_novo_modelo": 1.0}
        st["ano"] = 2028
        fornecedores.evoluir(st, random.Random(1))
        self.assertIn("Marlin M28", [ch["nome"] for ch in c["chassis"].values()])

    def test_desligado(self):
        st = jogo(None)
        c = st["categorias"][BETA]
        c["categoria"]["regras"]["evolucao_fornecedores"] = {"ativa": False}
        antes = {k: dict(v["atributos"]) for k, v in c["chassis"].items()}
        st["ano"] += 1
        fornecedores.evoluir(st, random.Random(5))
        self.assertEqual(antes, {k: v["atributos"] for k, v in c["chassis"].items()})


class TestNegociacao(unittest.TestCase):
    def setUp(self):
        self.st = jogo((BETA, "prisma"))
        self.c = self.st["categorias"][BETA]
        self.c["categoria"]["regras"]["negociacao_partes"] = {"ativa": True}
        self.eq = self.c["equipes"]["prisma"]
        self.ch = next(iter(self.c["chassis"].values()))
        self.st["semana"] = 30

    def proposta(self, valor):
        return acoes.aplicar(self.st, "proposta_parte", {"parte": "chassis", "id": self.ch["id"], "valor": valor,
                                                        "duracao": 1, "unidade": "temporadas", "inicio": "proxima"})

    def test_preco_de_tabela_sem_negociacao(self):
        self.c["categoria"]["regras"]["negociacao_partes"] = {"ativa": False}
        self.assertEqual(mercado.preco_pedido_parte(self.st, BETA, "prisma", "chassis", self.ch),
                         self.ch["contrato"]["valor_por_corrida"])

    def test_pedido_escondido_fixo(self):
        p1 = mercado.preco_pedido_parte(self.st, BETA, "prisma", "chassis", self.ch)
        p2 = mercado.preco_pedido_parte(self.st, BETA, "prisma", "chassis", self.ch)
        tab = self.ch["contrato"]["valor_por_corrida"]
        self.assertEqual(p1, p2)
        self.assertTrue(0.85 * tab - 100 <= p1 <= 1.15 * tab + 100)
        precos = {mercado.preco_pedido_parte(self.st, BETA, e, "chassis", self.ch) for e in self.c["equipes"]}
        self.assertGreater(len(precos), 1)                                # cada equipe ouve um preço

    def test_contrato_direto_bloqueado(self):
        erro = acoes.aplicar(self.st, "contratar_parte", {"parte": "chassis", "id": self.ch["id"], "duracao": 1,
                                                          "unidade": "temporadas", "inicio": "proxima"})
        self.assertIn("negociado", erro)

    def _responder(self):
        self.st["semana"] += 1
        mercado._responder_propostas_partes(self.st)

    def test_oferta_baixa_recusada_e_alta_aceita(self):
        info = self.eq.get("chassis") or {}
        if info.get("contrato"):
            info["contrato"]["temporadas"] = 1                            # termina nesta temporada
        pedido = mercado.preco_pedido_parte(self.st, BETA, "prisma", "chassis", self.ch)
        self.assertIsNone(self.proposta(pedido * 0.8))
        self.assertIsNotNone(mercado.proposta_parte_pendente(self.st, BETA, "prisma", "chassis"))
        mercado._responder_propostas_partes(self.st)                       # mesma semana: ainda não responde
        self.assertIsNotNone(mercado.proposta_parte_pendente(self.st, BETA, "prisma", "chassis"))
        self._responder()
        self.assertIsNone(self.eq.get("chassis_futuro"))
        self.assertTrue(any("recusa a proposta" in n["texto"] for n in self.st["noticias"][-3:]))
        self.assertIsNone(self.proposta(pedido + 100))
        self._responder()
        fut = self.eq["chassis_futuro"]
        self.assertEqual(fut["id"], self.ch["id"])
        self.assertEqual(fut["contrato"]["valor_por_corrida"], round(pedido + 100, -2))

    def test_ia_fecha_contratos(self):
        st = jogo(None)
        st["categorias"][BETA]["categoria"]["regras"]["negociacao_partes"] = {"ativa": True}
        rng = random.Random(2)
        ano0 = st["ano"]
        while st["ano"] < ano0 + 2:
            routines.avancar_semana(st, rng)
            if st["semana"] == 10:
                for eq in st["categorias"][BETA]["equipes"].values():
                    if eq.get("ativa"):
                        self.assertTrue(mercado.tem_parte_ativa(eq, "chassis"), eq["nome"])
                        self.assertTrue(mercado.tem_parte_ativa(eq, "motor"), eq["nome"])



class TestNegociacaoMultijogador(unittest.TestCase):
    def test_oferta_vai_nas_ordens_e_e_respondida_no_comissario(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=8)
        st["categorias"][BETA]["categoria"]["regras"]["negociacao_partes"] = {"ativa": True}
        mp.criar_liga(st, "Liga", [{"nome": "Diego", "categoria": BETA, "equipe": "prisma", "senha": "d"},
                                   {"nome": "Eva", "categoria": BETA, "equipe": "halcon", "senha": "e"}])
        st["semana"] = 25
        for eid in ("prisma", "halcon"):
            st["categorias"][BETA]["equipes"][eid]["motor"]["contrato"]["temporadas"] = 1
        ofertas = {"diego": 0.5, "eva": 1.2}
        motor = next(iter(m for m in st["categorias"][BETA]["motores"].values()))
        for jid, f in ofertas.items():
            stj = mp.entrar(copy.deepcopy(mp.versao_jogadores(st)), jid, jid[0])
            self.assertIsNone(acoes.executar(stj, "proposta_parte", parte="motor", id=motor["id"],
                                             valor=motor["contrato"]["valor_por_corrida"] * f, duracao=1,
                                             unidade="temporadas", inicio="proxima"))
            dados = mp.ordens_da_sessao(stj)
            if jid == "eva":                                   # oferta alterada à mão: recusada
                ruim = copy.deepcopy(dados)
                ruim["acoes"][0]["valor"] /= 2
                with self.assertRaises(mp.ErroLiga):
                    mp.importar_ordens(st, ruim)
            mp.importar_ordens(st, dados)
        mp.rodar_semana(st, random.Random(1))
        pend = {k for k in st.get("propostas_partes", {}) if not st["propostas_partes"][k]["ia"]}
        self.assertEqual(pend, {f"{BETA}|prisma|motor", f"{BETA}|halcon|motor"})   # resposta só na semana seguinte
        mp.rodar_semana(st, random.Random(2))
        eqs = st["categorias"][BETA]["equipes"]
        self.assertIsNone(eqs["prisma"].get("motor_futuro"))
        self.assertEqual(eqs["halcon"]["motor_futuro"]["id"], motor["id"])
        self.assertTrue(any("recusa a proposta" in n["texto"] and n.get("equipe") == "prisma" for n in st["noticias"]))


if __name__ == "__main__":
    unittest.main()


class TestChassisCliente(unittest.TestCase):
    """1b: em categoria com desenvolvimento de chassis, a equipe escolhe entre desenvolver e comprar."""

    def setUp(self):
        self.st = jogo((ALFA, "tucano"))
        self.c = self.st["categorias"][ALFA]
        self.c["categoria"]["regras"]["fontes_de_chassis_permitidas"] = ["proprio", "equipe"]
        self.eq = self.c["equipes"]["tucano"]
        self.st["semana"] = 25

    def comprar(self, de="vortex", inicio="proxima"):
        return acoes.aplicar(self.st, "contratar_parte", {"parte": "chassis", "id": f"ch_{de}", "duracao": 1,
                                                          "unidade": "temporadas", "inicio": inicio})

    def test_padrao_sem_compra(self):
        self.c["categoria"]["regras"].pop("fontes_de_chassis_permitidas")
        self.assertEqual(mercado.opcoes(self.st, ALFA, self.eq, "chassis"), [])
        self.assertEqual(state.fontes_chassis(st_cat := self.st["categorias"][BETA]["categoria"]), ["fabricante"])
        self.assertFalse(state.compra_de_chassis(self.c["categoria"]))

    def test_opcoes_e_preco(self):
        ops = {e["id"]: ok for e, ok, _ in mercado.opcoes(self.st, ALFA, self.eq, "chassis")}
        self.assertIn("ch_vortex", ops)
        self.assertNotIn("ch_tucano", ops)                       # o próprio não
        ch = self.c["chassis"]["ch_vortex"]
        self.assertTrue(ch["contrato"]["automatico"])
        self.assertGreater(ch["contrato"]["valor_por_corrida"], 0)

    def test_comprar_para_a_proxima_e_virar(self):
        alvo = {k: v + 1 for k, v in dev.valores_projeto(self.st, ALFA, self.eq, "chassis").items()}
        acoes.aplicar(self.st, "dev_modo", {"parte": "chassis", "modo": "novo"})
        self.assertIsNone(self.comprar("vortex", "agora") and None)   # agora: tem chassis próprio
        self.assertEqual(self.comprar("vortex", "agora"), "A equipe tem chassis próprio.")
        self.assertIsNone(self.comprar())
        self.assertFalse(dev.pode_projeto(self.st, ALFA, self.eq, "chassis"))
        with self.assertRaises(ValueError):
            dev.investir_projeto(self.st, ALFA, self.eq, "chassis", alvo)
        virar(self.st, ALFA)
        mercado.virada_partes(self.st, ALFA)
        self.assertEqual(self.eq["chassis"]["id"], "ch_vortex")
        self.assertEqual(self.eq["chassis"]["origem"], "equipe")
        self.assertIs(state.chassis_da_equipe(self.st, ALFA, self.eq), self.c["chassis"]["ch_vortex"])
        self.assertTrue(dev.cliente(self.st, ALFA, self.eq, "chassis"))
        self.assertFalse(dev.pode(self.st, ALFA, self.eq, "chassis"))

    def test_cliente_volta_a_fazer_o_proprio(self):
        self.assertIsNone(self.comprar())
        virar(self.st, ALFA)
        mercado.virada_partes(self.st, ALFA)
        self.st["semana"] = 25
        self.assertTrue(dev.cliente_pode_voltar(self.st, ALFA, self.eq, "chassis"))   # contrato de 1 temporada
        self.assertIsNone(acoes.aplicar(self.st, "dev_modo", {"parte": "chassis", "modo": "novo"}))
        self.eq["financas"]["caixa"] = 1e10
        self.assertIsNone(acoes.aplicar(self.st, "dev_investir", {"parte": "chassis", "proxima": True,
                                                                  "incrementos": {k: 60 for k in
                                                                                  dev.atributos_da_parte("chassis")}}))
        virar(self.st, ALFA)
        mercado.virada_partes(self.st, ALFA)
        self.assertEqual(self.eq["chassis"]["origem"], "proprio")
        ch = state.chassis_da_equipe(self.st, ALFA, self.eq)
        self.assertEqual(ch["equipe"], "tucano")
        self.assertEqual(set(ch["atributos"].values()), {60})

    def test_vendedor_nao_troca_e_limite_de_clientes(self):
        self.assertIsNone(self.comprar())
        with acoes.como(self.st, ALFA, "vortex"):
            erro = acoes.aplicar(self.st, "contratar_parte", {"parte": "chassis", "id": "ch_ventura", "duracao": 1,
                                                              "unidade": "temporadas", "inicio": "proxima"})
        self.assertIn("clientes", erro)
        with acoes.como(self.st, ALFA, "maple"):
            self.assertIsNone(acoes.aplicar(self.st, "contratar_parte", {"parte": "chassis", "id": "ch_vortex",
                                                                        "duracao": 1, "unidade": "temporadas",
                                                                        "inicio": "proxima"}))
        terceira = self.c["equipes"]["atlas"]
        ok = {e["id"]: ok for e, ok, _ in mercado.opcoes(self.st, ALFA, terceira, "chassis")}
        self.assertFalse(ok["ch_vortex"])                        # padrão: 2 clientes por chassis
        # quem comprou para a próxima temporada não vende o chassis
        ok = {e["id"] for e, _, _ in mercado.opcoes(self.st, ALFA, terceira, "chassis")}
        self.assertNotIn("ch_tucano", ok)

    def test_desenvolvimento_inicial_comprando(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=4)
        st["categorias"][ALFA]["categoria"]["regras"]["fontes_de_chassis_permitidas"] = ["proprio", "equipe"]
        eq = state.nova_equipe(st, ALFA, "Nova GP", "Brasil", random.Random(1))
        st["usuario"] = {"categoria": ALFA, "equipe": eq["id"]}
        self.assertEqual(acoes.aplicar(st, "dev_inicial", {"chassis": None, "potencia": None}), "Defina o chassis inicial.")
        self.assertIsNone(acoes.aplicar(st, "dev_inicial", {"chassis": None, "potencia": None, "comprar_chassis": True}))
        self.assertIsNone(acoes.aplicar(st, "contratar_parte", {"parte": "chassis", "id": "ch_vortex", "duracao": 1,
                                                                "unidade": "temporadas", "inicio": "agora"}))
        self.assertEqual(eq["chassis"]["id"], "ch_vortex")

    def test_ia_escolhe_e_ninguem_fica_sem_chassis(self):
        st = jogo(None)
        st["categorias"][ALFA]["categoria"]["regras"]["fontes_de_chassis_permitidas"] = ["proprio", "equipe"]
        rng = random.Random(5)
        ano0 = st["ano"]
        clientes = 0
        while st["ano"] < ano0 + 3:
            routines.avancar_semana(st, rng)
            if st["semana"] == 5:
                for e in st["categorias"][ALFA]["equipes"].values():
                    if e.get("ativa"):
                        self.assertTrue(mercado.tem_parte_ativa(e, "chassis"), e["nome"])
                        if e["chassis"]["origem"] != "proprio":
                            clientes += 1
                            dono = st["categorias"][ALFA]["equipes"][st["categorias"][ALFA]["chassis"][e["chassis"]["id"]]["equipe"]]
                            self.assertEqual(dono["chassis"]["origem"], "proprio")   # o vendedor faz o chassis
                for ch in st["categorias"][ALFA]["chassis"].values():
                    self.assertLessEqual(len(mercado.clientes_do_chassis(st, ALFA, ch["id"])), 2)
        self.assertGreater(clientes, 0)
