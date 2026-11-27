"""Multijogador: liga que começa do zero – nas categorias em que os jogadores criam equipes novas, as equipes da
database saem e todos os pilotos, patrocinadores e fornecimentos ficam livres."""
import copy
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, routines, multiplayer as mp, acoes  # noqa: E402

ALFA, BETA = "formula_alfa", "formula_beta"


def jogo():
    return state.novo_jogo(db.arquivos_do_ano(2026), semente=3)


def liga(st=None):
    st = st or jogo()
    mp.criar_liga(st, "Do Zero", [
        {"nome": "Ana", "categoria": ALFA, "senha": "a", "nova_equipe": True},
        {"nome": "Bia", "categoria": ALFA, "senha": "b", "nova_equipe": True}], todos_livres=True)
    return st


def contratados(st, cid):
    return [p for p in st["pilotos"].values()
            if any((p.get(k) or {}).get("categoria") == cid for k in ("contrato", "contrato_futuro"))]


class TestTodosLivres(unittest.TestCase):
    def test_equipes_da_database_saem_e_tudo_fica_livre(self):
        st = jogo()
        self.assertTrue(contratados(st, ALFA))
        beta_antes = len(contratados(st, BETA))
        liga(st)
        c = st["categorias"][ALFA]
        self.assertFalse([e for e in c["equipes"].values() if e.get("ativa")])
        self.assertTrue(all(e.get("fora_da_liga") for e in c["equipes"].values()))
        self.assertEqual(contratados(st, ALFA), [])                          # titulares, testes e futuros
        self.assertFalse([p for p in c["patrocinadores"].values() if p.get("contrato")])
        for e in c["equipes"].values():
            for parte in ("chassis", "motor"):
                self.assertIn((e.get(parte) or {}).get("origem"), (None, "proprio"))
                self.assertNotIn(f"{parte}_futuro", e)
        self.assertEqual(len(contratados(st, BETA)), beta_antes)               # outra categoria não muda
        self.assertEqual(st["multiplayer"]["todos_livres"], [ALFA])

    def test_jogador_com_equipe_da_database_na_categoria_e_recusado(self):
        st = jogo()
        antes = copy.deepcopy(st["pilotos"])
        with self.assertRaises(mp.ErroLiga):
            mp.criar_liga(st, "X", [{"nome": "Ana", "categoria": ALFA, "senha": "a", "nova_equipe": True},
                                    {"nome": "Caio", "categoria": ALFA, "senha": "c", "equipe": "vortex"}],
                          todos_livres=True)
        self.assertEqual(st["pilotos"], antes)
        self.assertNotIn("multiplayer", st)
        with self.assertRaises(mp.ErroLiga):                                 # ninguém cria equipe nova
            mp.criar_liga(st, "X", [{"nome": "Caio", "categoria": ALFA, "senha": "c", "equipe": "vortex"}],
                          todos_livres=True)

    def test_jogadores_contratam_e_ninguem_volta(self):
        st = liga()
        sj = mp.entrar(copy.deepcopy(mp.versao_jogadores(st)), "ana", "a")
        self.assertIsNone(acoes.executar(sj, "criar_equipe", jogador="ana", nome="Arara GP", nacionalidade="Brasil",
                                         cor="#00aa00", cor_secundaria="#ffffff"))
        ex_titular = next(p for p in sj["pilotos"].values() if p.get("categoria_atual") == ALFA
                          and not p.get("contrato") and p.get("categoria_origem") == ALFA)
        self.assertIsNone(acoes.executar(sj, "proposta_piloto", piloto=ex_titular["id"], situacao="principal",
                                         valor=200000, duracao=2, unidade="temporadas", inicio="agora"))
        self.assertEqual(mp.importar_ordens(st, mp.ordens_da_sessao(sj)), "ana")
        r = mp.rodar_semana(st, random.Random(1))
        self.assertEqual(r["erros"], [])
        ativas = [e for e in st["categorias"][ALFA]["equipes"].values() if e.get("ativa")]
        self.assertEqual([e["nome"] for e in ativas], ["Arara GP"])
        for _ in range(3):                                                   # nenhuma equipe da database ressurge
            routines.nova_temporada(st, random.Random(2))
            self.assertFalse([e for e in st["categorias"][ALFA]["equipes"].values()
                              if e.get("ativa") and e.get("fora_da_liga")])


if __name__ == "__main__":
    unittest.main()
