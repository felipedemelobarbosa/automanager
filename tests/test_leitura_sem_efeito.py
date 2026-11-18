"""Consultas usadas pelas telas não podem mudar a equipe (no multijogador, a equipe do jogador e a do comissário
têm de ficar iguais para as ordens conferirem)."""
import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, desenvolvimento as dev, multiplayer as mp, regulamento  # noqa: E402

CID = "formula_alfa"


def foto(eq):
    return json.dumps(eq, sort_keys=True, default=str)


class TestLeituraSemEfeito(unittest.TestCase):
    def setUp(self):
        self.st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
        mp.criar_liga(self.st, "Liga", [{"nome": "Ana", "categoria": CID, "equipe": "tucano", "senha": "a"}])

    def consultas_da_tela(self, st):
        """O que a tela de desenvolvimento lê (carro desta temporada e da próxima)."""
        eq = st["categorias"][CID]["equipes"]["tucano"]
        for parte in dev.PARTES:
            dev.pode(st, CID, eq, parte)
            dev.pode_projeto(st, CID, eq, parte)
            dev.projeto(eq, parte)
            dev.valores_atuais(st, CID, eq, parte)
            if dev.pode_projeto(st, CID, eq, parte):
                dev.valores_projeto(st, CID, eq, parte)
                dev.base_projeto(st, CID, eq, parte)
                dev.perda_manutencao(st, CID, parte)
                dev.projeto_permitido(st, CID, parte)
            if dev.pode(st, CID, eq, parte):
                dev.tetos_atual(st, CID, eq, parte)
            dev.cliente(st, CID, eq, parte)
            dev.cliente_pode_voltar(st, CID, eq, parte)
        return eq

    def test_tela_de_desenvolvimento_nao_muda_a_equipe(self):
        eq = self.st["categorias"][CID]["equipes"]["tucano"]
        eq.pop("projeto", None)                       # 1ª temporada de uma equipe de jogador: ainda sem projeto
        eq.pop("ganho_dev", None)
        self.st["categorias"][CID]["regulamento"] = {"limites": [{"parte": "chassis", "pontos": 3,
                                                                  "de": self.st["ano"], "ate": self.st["ano"]}],
                                                     "historico": []}
        antes = foto(eq)
        self.consultas_da_tela(self.st)
        self.assertEqual(foto(eq), antes)

    def test_ordens_conferem_depois_de_abrir_a_tela(self):
        self.st["categorias"][CID]["equipes"]["tucano"].pop("projeto", None)
        sj = mp.entrar(copy.deepcopy(mp.versao_jogadores(self.st)), "ana", "a")
        self.consultas_da_tela(sj)                    # o jogador só olha a tela, sem investir
        self.assertEqual(mp.importar_ordens(self.st, mp.ordens_da_sessao(sj)), "ana")

    def test_escolher_o_modo_grava_o_projeto(self):
        eq = self.st["categorias"][CID]["equipes"]["tucano"]
        eq.pop("projeto", None)
        dev.mudar_modo(eq, "chassis", "novo")
        self.assertEqual(eq["projeto"]["chassis"]["modo"], "novo")


if __name__ == "__main__":
    unittest.main()
