"""Multijogador por arquivos: liga, senhas, ordens assinadas, planos de evento e políticas de ausência."""
import copy
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, multiplayer as mp, acoes, campeonato  # noqa: E402
from automanager.event import planos  # noqa: E402

CID = "formula_alfa"


def nova_liga(politica="ia"):
    st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
    mp.criar_liga(st, "Liga Teste", [
        {"nome": "Ana", "categoria": CID, "equipe": "tucano", "senha": "a1"},
        {"nome": "Bruno", "categoria": CID, "equipe": "vortex", "senha": "b2"}], politica)
    return st


def ordens(st_com, jid, senha, faz=None):
    """Simula o jogador: abre a versão distribuída, entra, age e devolve o arquivo de ordens (dict)."""
    dist = copy.deepcopy(mp.versao_jogadores(st_com))
    st_j = mp.entrar(dist, jid, senha)
    if faz:
        faz(st_j)
    return mp.ordens_da_sessao(st_j)


def ate_semana_de_corrida(st):
    while not any(e["especie"] == "corrida" and e["semana"] == st["semana"] and e.get("ativo")
                  for e in st["categorias"][CID]["calendario"]):
        mp.rodar_semana(st, random.Random(st["semana"]))


class TestLiga(unittest.TestCase):
    def test_versao_dos_jogadores_sem_segredos(self):
        st = nova_liga()
        d = mp.versao_jogadores(st)
        self.assertTrue(all("chave" not in j for j in d["multiplayer"]["jogadores"].values()))
        self.assertNotIn("recebidas", d["multiplayer"])
        self.assertIn("chave", st["multiplayer"]["jogadores"]["ana"])

    def test_senha_errada(self):
        st = nova_liga()
        with self.assertRaises(mp.ErroLiga):
            mp.entrar(mp.versao_jogadores(st), "ana", "errada")

    def test_ordens_alteradas_sao_recusadas(self):
        st = nova_liga()
        o = ordens(st, "ana", "a1", lambda s: acoes.executar(s, "emprestimo", valor=1000000, prazo=None))
        o["acoes"][0]["valor"] = 50000000
        with self.assertRaises(mp.ErroLiga):
            mp.importar_ordens(st, o)
        # outro jogador não consegue assinar pela Ana
        falsa = ordens(st, "bruno", "b2")
        falsa["jogador"] = "ana"
        with self.assertRaises(mp.ErroLiga):
            mp.importar_ordens(st, falsa)

    def test_semana_errada(self):
        st = nova_liga()
        o = ordens(st, "ana", "a1")
        mp.rodar_semana(st, random.Random(1))
        with self.assertRaises(mp.ErroLiga):
            mp.importar_ordens(st, o)

    def test_acoes_reaplicadas_pelo_comissario(self):
        st = nova_liga()
        caixa = st["categorias"][CID]["equipes"]["tucano"]["financas"]["caixa"]
        o = ordens(st, "ana", "a1", lambda s: acoes.executar(s, "emprestimo", valor=2000000, prazo=None))
        self.assertEqual(len(o["acoes"]), 1)
        mp.importar_ordens(st, o)
        mp.importar_ordens(st, ordens(st, "bruno", "b2"))
        r = mp.rodar_semana(st, random.Random(2))
        self.assertEqual(r["erros"], [])
        eq = st["categorias"][CID]["equipes"]["tucano"]
        self.assertEqual(len(eq.get("emprestimos", [])), 1)
        self.assertGreater(eq["financas"]["caixa"], caixa)

    def test_plano_de_corrida_aplicado(self):
        st = nova_liga()
        ate_semana_de_corrida(st)
        ev = next(e for e in st["categorias"][CID]["calendario"] if e["semana"] == st["semana"]
                  and e["especie"] == "corrida")
        pneus = st["categorias"][CID]["categoria"]["pneus"]["compostos"]
        comp = [k for k, v in pneus.items() if v["tipo"] == "seco"]         # corrida seca: plano com pneus secos
        ev["prob_chuva"] = 0.0                       # na chuva as paradas forçadas pelo clima mudariam o plano
        pn = st["categorias"][CID]["categoria"]["pneus"]
        pn["desgaste_critico"] = pn["desgaste_quebra"] = 999   # nem furo por desgaste (stint longo, agressivo)
        voltas = ev["voltas_corrida"]

        def faz(s):
            sess = mp.sessao(s)
            for p in state.pilotos_da_equipe(s, CID, "tucano"):
                if p["contrato"]["situacao"] != "principal":
                    continue
                pl = planos.plano_padrao()
                pl["corrida"]["paradas"] = [[comp[0], voltas // 3], [comp[-1], voltas - voltas // 3]]
                pl["corrida"]["ordens"]["agressividade"] = 2
                sess["planos"].setdefault(ev["id"], {})[p["id"]] = pl
        mp.importar_ordens(st, ordens(st, "ana", "a1", faz))
        mp.importar_ordens(st, ordens(st, "bruno", "b2"))
        mp.rodar_semana(st, random.Random(3))
        reg = next(r for r in st["temporadas"]["2026"][CID]["corridas"] if r["evento"] == ev["id"])
        meus = [l for l in reg["resultado"] if l["equipe"] == "tucano" and l["status"] == "Fim"]
        for l in meus:
            self.assertEqual(l["paradas"], 1)

    def test_politica_bloquear(self):
        st = nova_liga("bloquear")
        mp.importar_ordens(st, ordens(st, "ana", "a1"))
        with self.assertRaises(mp.ErroLiga):
            mp.rodar_semana(st, random.Random(4))
        mp.pular(st, "bruno")
        r = mp.rodar_semana(st, random.Random(4))
        self.assertEqual(r["ia"], ["bruno"])

    def test_politica_repetir(self):
        st = nova_liga("repetir")
        o = ordens(st, "ana", "a1", lambda s: acoes.executar(s, "emprestimo", valor=1000000, prazo=None))
        mp.importar_ordens(st, o)
        mp.rodar_semana(st, random.Random(5))
        r = mp.rodar_semana(st, random.Random(6))      # ninguém mandou: Ana repete (sem o empréstimo)
        self.assertEqual(r["repetidas"], ["ana"])
        self.assertIn("bruno", r["ia"])
        self.assertEqual(len(st["categorias"][CID]["equipes"]["tucano"].get("emprestimos", [])), 1)

    def test_salvar_e_carregar(self):
        st = nova_liga()
        pasta = tempfile.mkdtemp()
        caminho = mp.salvar_liga(st, os.path.join(pasta, "liga.json"))
        st2 = mp.carregar_liga(caminho)
        self.assertEqual(st2["multiplayer"]["id"], st["multiplayer"]["id"])
        jog = mp.exportar_para_jogadores(st, os.path.join(pasta, "jog.json"))
        st3 = mp.carregar_liga(jog)
        self.assertEqual(st3["multiplayer"]["papel"], "jogador")
        o = os.path.join(pasta, "o.json")
        s = mp.entrar(st3, "ana", "a1")
        mp.salvar_ordens(s, o)
        self.assertEqual(mp.importar_ordens(st2, mp.ler_ordens(o)), "ana")

    def test_temporada_inteira(self):
        st = nova_liga()
        ano = st["ano"]
        while st["ano"] == ano:
            mp.rodar_semana(st, random.Random(st["semana"]))
        self.assertTrue(campeonato.campeoes(st))


if __name__ == "__main__":
    unittest.main()
