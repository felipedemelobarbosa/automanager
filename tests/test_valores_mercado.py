"""Mercado: pretensão do piloto mostrada como estimativa (não o valor real), total do contrato e identificação
da equipe nas ordens do multijogador."""
import copy
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, mercado, contratos, multiplayer as mp, acoes  # noqa: E402

CID = "formula_alfa"


class TestPretensao(unittest.TestCase):
    def test_estimativa_nao_e_o_valor_real(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=3)
        cat = st["categorias"][CID]["categoria"]
        iguais, desvios = 0, []
        for p in list(st["pilotos"].values())[:40]:
            real = mercado.salario_pedido(p, cat)
            est, lo, hi = mercado.pedido_estimado(st, p, cat, "tucano")
            self.assertLess(lo, hi)
            self.assertAlmostEqual(est / real, 1, delta=0.21)
            iguais += abs(est - round(real, -2)) < 1
            desvios.append(abs(est / real - 1))
            self.assertEqual((est, lo, hi), mercado.pedido_estimado(st, p, cat, "tucano"))   # estável
        self.assertLess(iguais, 5)
        self.assertGreater(sum(desvios) / len(desvios), 0.05)

    def test_cada_equipe_tem_sua_estimativa(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=3)
        cat = st["categorias"][CID]["categoria"]
        p = next(iter(st["pilotos"].values()))
        self.assertNotEqual(mercado.pedido_estimado(st, p, cat, "tucano"), mercado.pedido_estimado(st, p, cat, "vortex"))


class TestTotalContrato(unittest.TestCase):
    def test_corridas_cobertas(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=3)
        n = mercado.corridas_na_temporada(st["categorias"][CID])
        self.assertEqual(mercado.corridas_do_contrato(st, CID, 5, "corridas", "agora"), 5)
        self.assertEqual(mercado.corridas_do_contrato(st, CID, 2, "temporadas", "proxima"), 2 * n)
        self.assertEqual(mercado.corridas_do_contrato(st, CID, 2, "temporadas", "agora"),
                         contratos.corridas_restantes(st, CID) + n)


class TestOrdensComEquipe(unittest.TestCase):
    def test_nome_da_equipe_nas_ordens(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
        mp.criar_liga(st, "L", [{"nome": "Ana", "categoria": CID, "equipe": "tucano", "senha": "a"}])
        sj = mp.entrar(copy.deepcopy(mp.versao_jogadores(st)), "ana", "a")
        o = mp.ordens_da_sessao(sj)
        self.assertEqual(o["equipe"], {"id": "tucano", "nome": st["categorias"][CID]["equipes"]["tucano"]["nome"]})
        mp.importar_ordens(st, o)

    def test_equipe_trocada_e_recusada(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
        mp.criar_liga(st, "L", [{"nome": "Ana", "categoria": CID, "equipe": "tucano", "senha": "a"}])
        sj = mp.entrar(copy.deepcopy(mp.versao_jogadores(st)), "ana", "a")
        sj["usuario"]["equipe"] = "vortex"                       # arquivo montado para outra equipe
        with self.assertRaises(mp.ErroLiga):
            mp.importar_ordens(st, mp.ordens_da_sessao(sj))

    def test_equipe_nova_aparece_nas_ordens(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
        mp.criar_liga(st, "L", [{"nome": "Ana", "categoria": CID, "nova_equipe": True, "senha": "a"}])
        sj = mp.entrar(copy.deepcopy(mp.versao_jogadores(st)), "ana", "a")
        self.assertEqual(mp.ordens_da_sessao(sj)["equipe"], {"id": None, "nome": None})
        acoes.executar(sj, "criar_equipe", jogador="ana", nome="Arara GP", nacionalidade="Brasil")
        o = mp.ordens_da_sessao(sj)
        self.assertEqual(o["equipe"]["nome"], "Arara GP")
        mp.importar_ordens(st, o)


if __name__ == "__main__":
    unittest.main()
