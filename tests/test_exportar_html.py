"""Exportar para HTML: as páginas são geradas e mostram só o que o jogador vê no jogo."""
import copy
import os
import random
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, routines, campeonato, exportar_html, multiplayer as mp  # noqa: E402

ALFA = "formula_alfa"


def jogar(st, ate_semana, ate_ano=2026):
    rng = random.Random(3)
    st["ia_conduz_usuario"] = True
    while (st["ano"], st["semana"]) < (ate_ano, ate_semana):
        p = routines.corrida_do_usuario_na_semana(st)
        if p:
            campeonato.simular_em_segundo_plano(st, ALFA, p, rng)
        routines.avancar_semana(st, rng)
    st.pop("ia_conduz_usuario", None)


class TestExportarHTML(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.pasta)

    def ler(self, nome):
        with open(os.path.join(self.pasta, nome), encoding="utf-8") as f:
            return f.read()

    def test_um_jogador(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=3)
        state.escolher_equipe(st, ALFA, "tucano")
        jogar(st, 20, 2027)                                                          # 2026 inteira + parte de 2027
        indice = exportar_html.exportar(st, self.pasta)
        self.assertTrue(os.path.isfile(indice))
        arquivos = set(os.listdir(self.pasta))
        for cid in st["categorias"]:
            for p in ("classificacao", "calendario", "equipes", "pilotos"):
                self.assertIn(f"{cid}-{p}.html", arquivos)
            for r in st["temporadas"][str(st["ano"])][cid]["corridas"]:
                self.assertIn(f"{cid}-corrida-{r['evento']}.html", arquivos)
        self.assertTrue({"index.html", "financas.html", "noticias.html", "estilo.css", "ordenar.js"} <= arquivos)
        self.assertTrue(os.listdir(os.path.join(self.pasta, "img")))                 # bandeiras copiadas
        # links internos apontam para páginas que existem
        for nome in arquivos:
            if nome.endswith(".html"):
                for alvo in re.findall(r'href="([^"#]+)', self.ler(nome)):
                    self.assertIn(alvo, arquivos | {"estilo.css"}, (nome, alvo))
        # salário só dos pilotos da equipe do jogador; finanças só da equipe dele
        pil = self.ler(f"{ALFA}-pilotos.html")
        linhas_com_salario = [l for l in re.findall(r"<tr class=\"[^\"]*\">.*?</tr>", pil) if "USD" in l]
        self.assertTrue(linhas_com_salario)
        self.assertTrue(all('class="usuario"' in l for l in linhas_com_salario))
        fin = self.ler("financas.html")
        self.assertIn("Tucano Racing", fin)
        self.assertNotIn("Vortex Racing", fin)
        cls = self.ler(f"{ALFA}-classificacao.html")
        self.assertIn('class="usuario"', cls)                                       # equipe do jogador em destaque
        # temporada anterior: classificação final, corridas e o índice das temporadas
        self.assertIn("temporadas.html", arquivos)
        for cid in st["categorias"]:
            self.assertIn(f"{cid}-2026-classificacao.html", arquivos)
            for r in st["temporadas"]["2026"][cid]["corridas"]:
                self.assertIn(f"{cid}-2026-corrida-{r['evento']}.html", arquivos)
        campeao = st["temporadas"]["2026"][ALFA]["final"]["pilotos"][0]["nome"]
        self.assertIn(campeao, self.ler("temporadas.html"))
        self.assertIn(campeao, self.ler(f"{ALFA}-2026-classificacao.html"))
        fin = self.ler("financas.html")
        self.assertIn(">2026<", fin)                                                  # coluna da temporada anterior
        self.assertIn("2027 *", fin)

    def test_multijogador_visao_do_jogador(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=4)
        mp.criar_liga(st, "Liga", [{"nome": "Ana", "categoria": ALFA, "equipe": "tucano", "senha": "a"},
                                   {"nome": "Bia", "categoria": ALFA, "equipe": "vortex", "senha": "b"}])
        st["noticias"].append({"ano": 2026, "semana": 1, "categoria": ALFA, "tipo": "usuario", "equipe": "vortex",
                               "texto": "Segredo da Vortex"})
        sj = mp.entrar(copy.deepcopy(mp.versao_jogadores(st)), "ana", "a")
        exportar_html.exportar(sj, self.pasta)
        noticias = self.ler("noticias.html")                                          # como no jogo: todas,
        self.assertIn('<div class="noticia ">[2026 S01] Segredo da Vortex', noticias)    # destaque só nas dele
        fin = self.ler("financas.html")
        self.assertIn("Tucano Racing", fin)
        self.assertNotIn("Vortex Racing", fin)

    def test_comissario(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=4)
        mp.criar_liga(st, "Liga", [{"nome": "Ana", "categoria": ALFA, "equipe": "tucano", "senha": "a"},
                                   {"nome": "Bia", "categoria": ALFA, "equipe": "vortex", "senha": "b"}])
        exportar_html.exportar(st, self.pasta)
        fin = self.ler("financas.html")                                               # comissário: todas as equipes
        self.assertIn("Tucano Racing", fin)                                           # de jogadores
        self.assertIn("Vortex Racing", fin)
        self.assertNotIn("Scuderia Ventura", fin)


if __name__ == "__main__":
    unittest.main()
