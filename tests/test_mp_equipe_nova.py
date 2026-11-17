"""Multijogador: vaga de equipe nova – o jogador cria a equipe ao abrir a liga e faz o desenvolvimento inicial /
contrata as peças, tudo pelas ordens."""
import copy
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, multiplayer as mp, acoes, mercado  # noqa: E402
from automanager.db import ATRIBUTOS_CHASSIS  # noqa: E402
from automanager.event.inscritos import montar_inscritos  # noqa: E402


def liga(politica="ia"):
    st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
    mp.criar_liga(st, "Liga Nova", [
        {"nome": "Ana", "categoria": "formula_alfa", "senha": "a", "nova_equipe": True},
        {"nome": "Bia", "categoria": "formula_beta", "senha": "b", "nova_equipe": True},
        {"nome": "Caio", "categoria": "formula_alfa", "senha": "c", "equipe": "vortex"}], politica)
    return st


def jogador(st, jid, senha):
    return mp.entrar(copy.deepcopy(mp.versao_jogadores(st)), jid, senha)


def criar(sj, jid, nome):
    return acoes.executar(sj, "criar_equipe", jogador=jid, nome=nome, nacionalidade="Brasil", cor="#00aa00",
                          cor_secundaria="#ffffff")


def equipe(st, jid):
    j = st["multiplayer"]["jogadores"][jid]
    return j["categoria"], st["categorias"][j["categoria"]]["equipes"].get(j["equipe"])


class TestVagaEquipeNova(unittest.TestCase):
    def test_comissario_so_reserva_a_vaga(self):
        st = liga()
        n = len(st["categorias"]["formula_alfa"]["equipes"])
        self.assertIsNone(st["multiplayer"]["jogadores"]["ana"]["equipe"])
        self.assertEqual(len(st["categorias"]["formula_alfa"]["equipes"]), n)       # nada criado pelo comissário
        self.assertIn("o jogador cria", dict((x[0], x[2]) for x in mp.situacao(st))["ana"])

    def test_jogador_cria_e_comissario_reproduz(self):
        st = liga()
        sj = jogador(st, "ana", "a")
        self.assertEqual(acoes.executar(sj, "emprestimo", valor=1000000, prazo=None), "Crie a equipe primeiro.")
        self.assertIsNone(criar(sj, "ana", "Arara GP"))
        self.assertEqual(criar(sj, "ana", "Outra"), "A equipe já foi criada.")
        cid, eqj = equipe(sj, "ana")
        self.assertTrue(eqj["dev_inicial_pendente"])
        cfg = state.config_dev_inicial(sj, cid, "chassis")
        attrs = {k: cfg["atributo_base"] + 10 for k in ATRIBUTOS_CHASSIS}
        self.assertIsNone(acoes.executar(sj, "dev_inicial", chassis=attrs, potencia=None))
        caixa_jogador = eqj["financas"]["caixa"]
        mp.importar_ordens(st, mp.ordens_da_sessao(sj))               # reprodução confere (mesmo orçamento sorteado)
        mp.importar_ordens(st, mp.ordens_da_sessao(jogador(st, "caio", "c")))
        r = mp.rodar_semana(st, random.Random(1))
        self.assertEqual(r["erros"], [])
        cid, eq = equipe(st, "ana")
        self.assertEqual(eq["nome"], "Arara GP")
        self.assertEqual(eq["id"], eqj["id"])
        self.assertEqual(state.chassis_da_equipe(st, cid, eq)["atributos"], attrs)
        self.assertLessEqual(abs(eq["financas"]["caixa"] - caixa_jogador), abs(caixa_jogador))  # mesma base

    def test_orcamento_igual_nos_dois_lados(self):
        st = liga()
        a, b = jogador(st, "ana", "a"), jogador(st, "ana", "a")
        criar(a, "ana", "Arara GP")
        criar(b, "ana", "Arara GP")
        self.assertEqual(equipe(a, "ana")[1]["financas"]["caixa"], equipe(b, "ana")[1]["financas"]["caixa"])

    def test_sem_ordens_a_vaga_espera(self):
        st = liga("ia")
        r = mp.rodar_semana(st, random.Random(2))
        self.assertEqual(r["erros"], [])
        self.assertIsNone(st["multiplayer"]["jogadores"]["ana"]["equipe"])

    def test_ia_faz_dev_inicial_depois_de_criada(self):
        st = liga("ia")
        sj = jogador(st, "ana", "a")
        criar(sj, "ana", "Arara GP")                                  # cria, mas não faz o desenvolvimento
        mp.importar_ordens(st, mp.ordens_da_sessao(sj))
        mp.rodar_semana(st, random.Random(3))
        mp.rodar_semana(st, random.Random(4))                         # semana seguinte sem ordens: a IA faz
        cid, eq = equipe(st, "ana")
        self.assertFalse(eq.get("dev_inicial_pendente"))
        self.assertIsNotNone(state.chassis_da_equipe(st, cid, eq))

    def test_beta_compra_pecas_e_corre(self):
        st = liga()
        sj = jogador(st, "bia", "b")
        self.assertIsNone(criar(sj, "bia", "Jacaré Racing"))
        cid, eqj = equipe(sj, "bia")
        self.assertFalse(eqj.get("dev_inicial_pendente"))             # Beta: sem desenvolvimento
        for parte in ("chassis", "motor"):
            opc = [e for e, ok, _ in mercado.opcoes(sj, cid, eqj, parte) if ok]
            self.assertIsNone(acoes.executar(sj, "contratar_parte", parte=parte, id=opc[0]["id"], duracao=1,
                                             unidade="temporadas", inicio="agora"))
        for p in [p for p in sj["pilotos"].values() if mercado.livre_agora(p) and not p.get("lesao")][:2]:
            self.assertIsNone(acoes.executar(sj, "proposta_piloto", piloto=p["id"], situacao="principal",
                                             valor=mercado.salario_pedido(p, sj["categorias"][cid]["categoria"]) * 2,
                                             duracao=1, unidade="temporadas", inicio="agora"))
        mp.importar_ordens(st, mp.ordens_da_sessao(sj))
        mp.rodar_semana(st, random.Random(5))
        mp.rodar_semana(st, random.Random(6))
        _, eq = equipe(st, "bia")
        pista = next(e for e in st["categorias"][cid]["calendario"] if e["especie"] == "corrida")
        self.assertTrue([i for i in montar_inscritos(st, cid, None, pista) if i["equipe"]["id"] == eq["id"]])

    def test_ordens_vazias_sem_equipe(self):
        st = liga()
        mp.importar_ordens(st, mp.ordens_da_sessao(jogador(st, "ana", "a")))   # abriu e não criou: válido


if __name__ == "__main__":
    unittest.main()


class TestArquivos(unittest.TestCase):
    def test_novos_pilotos_nao_e_categoria(self):
        nomes = [os.path.basename(p) for p in db.todos_os_arquivos()]
        self.assertTrue(nomes)
        self.assertFalse(any(n.startswith("novos_pilotos") for n in nomes))
