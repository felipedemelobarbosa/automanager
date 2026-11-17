"""Imagens: nomes de arquivo, gravação, títulos de artigo no importador e busca (com rede simulada)."""
import gzip
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import imagens, db  # noqa: E402
from automanager.editor import wikipedia, imagens_wiki  # noqa: E402

DADOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados")


def png(cor=(200, 0, 0), tam=(600, 300), fmt="PNG"):
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", tam, cor).save(b, fmt)
    return b.getvalue()


@unittest.skipUnless(imagens.TEM_PILLOW, "Pillow não instalado")
class TestImagens(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.mkdtemp()
        self.p = mock.patch.object(imagens, "PASTA_IMAGENS", self.pasta)
        self.p.start()

    def tearDown(self):
        self.p.stop()

    def test_nome_arquivo(self):
        self.assertEqual(imagens.nome_arquivo("piloto", "Jean-Éric Vergne"), "pilotos/jean_eric_vergne.png")
        self.assertEqual(imagens.nome_arquivo("equipe", "McLaren"), "equipes/mclaren.png")
        self.assertEqual(imagens.campo("equipe"), "logotipo")

    def test_salvar_converte_e_reduz(self):
        rel = imagens.salvar_bytes(png(fmt="JPEG"), "pilotos/x.png")
        self.assertTrue(imagens.existe(rel))
        from PIL import Image
        with Image.open(imagens.caminho_absoluto(rel)) as im:
            self.assertEqual(im.format, "PNG")
            self.assertLessEqual(max(im.size), imagens.LADO_MAXIMO)

    def test_buscar_todas(self):
        d = {"pilotos": [{"nome": "A", "wikipedia": "Piloto A"}, {"nome": "Sem artigo"}],
             "equipes": [{"nome": "E", "wikipedia": "Equipe E"}],
             "calendario": [{"nome": "GP", "wikipedia": "Circuito C"}]}
        urls = {"Piloto A": "u1", "Circuito C": "u3"}
        with mock.patch.object(imagens_wiki, "urls_principais", lambda ts: {t: urls[t] for t in ts if t in urls}), \
                mock.patch.object(imagens_wiki, "url_alternativa", lambda t, tipo: "u2" if tipo == "equipe" else None), \
                mock.patch.object(imagens_wiki, "baixar", lambda u: png()):
            n, avisos = imagens_wiki.buscar_todas(d, pausa=0)
        self.assertEqual(n, 3)
        self.assertEqual(avisos, [])
        self.assertEqual(d["pilotos"][0]["imagem"], "pilotos/piloto_a.png")
        self.assertEqual(d["equipes"][0]["logotipo"], "equipes/equipe_e.png")
        self.assertEqual(d["calendario"][0]["imagem"], "pistas/circuito_c.png")
        self.assertNotIn("imagem", d["pilotos"][1])


@unittest.skipUnless(imagens.TEM_PILLOW, "Pillow não instalado")
class TestPastaLocalEBandeiras(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.mkdtemp()
        self.p = mock.patch.object(imagens, "PASTA_IMAGENS", self.pasta)
        self.p.start()

    def tearDown(self):
        self.p.stop()

    def test_importar_pasta(self):
        origem = tempfile.mkdtemp()
        os.makedirs(os.path.join(origem, "equipes"))
        os.makedirs(os.path.join(origem, "bandeiras"))
        arquivos = {"Tomas IBARRA.jpg": png(fmt="JPEG"), "equipes/vortex.png": png(), "Kraft KM-8.png": png(),
                    "Serra Azul.png": png(), "Brazil.png": png(), "bandeiras/Narnia.png": png(), "xyz.png": png()}
        for nome, b in arquivos.items():
            with open(os.path.join(origem, nome), "wb") as f:
                f.write(b)
        d = {"pilotos": [{"id": "p1", "nome": "Tomás Ibarra"}], "equipes": [{"id": "vortex", "nome": "Vortex Racing"}],
             "chassis": [], "motores": [{"id": "m1", "nome": "Kraft KM-8"}],
             "calendario": [{"id": "ev1", "nome": "GP", "local": "Serra Azul, Brasil"}]}
        feitos, sem_par = imagens.importar_pasta(d, origem)
        self.assertEqual(d["pilotos"][0]["imagem"], "pilotos/tomas_ibarra.png")
        self.assertEqual(d["equipes"][0]["logotipo"], "equipes/vortex_racing.png")
        self.assertEqual(d["motores"][0]["logotipo"], "motores/kraft_km_8.png")
        self.assertEqual(d["calendario"][0]["imagem"], "pistas/gp.png")
        self.assertEqual(imagens.bandeira("Brasil"), "bandeiras/brasil.png")
        self.assertEqual(imagens.bandeira("Brazil"), "bandeiras/brasil.png")
        self.assertTrue(imagens.existe("bandeiras/narnia.png"))
        self.assertEqual(sem_par, ["xyz.png"])
        self.assertEqual(len(feitos), 6)


class TestBandeirasDoJogo(unittest.TestCase):
    def test_paises_da_database_tem_bandeira(self):
        from automanager import paises
        import json
        faltam = set()
        for caminho in db.todos_os_arquivos():
            d = db.carregar_arquivo(caminho, validar=False)
            for k in ("pilotos", "equipes", "chassis", "motores", "patrocinadores"):
                for x in d.get(k, []):
                    pais = x.get("nacionalidade") or x.get("pais")
                    if pais and not imagens.bandeira(pais):
                        faltam.add(pais)
            for e in d.get("calendario", []):
                if not imagens.bandeira(paises.do_local(e.get("local"))):
                    faltam.add(e.get("local"))
        with open(os.path.join(os.path.dirname(db.arquivos_do_ano(2026)[0]), "..", "nomes.json"), encoding="utf-8") as f:
            for pais in json.load(f)["nacionalidades"]:
                if not imagens.bandeira(pais):
                    faltam.add(pais)
        self.assertEqual(faltam, set())

    def test_nomes_em_ingles_e_portugues(self):
        from automanager import paises
        self.assertEqual(paises.em_portugues("United Kingdom"), "Reino Unido")
        self.assertEqual(paises.em_portugues("reino unido"), "Reino Unido")
        self.assertEqual(paises.arquivo_wikimedia("Holanda"), "Flag of the Netherlands.svg")
        self.assertEqual(paises.do_local("Serra Azul, Brasil"), "Brasil")


class TestArtigosNoImportador(unittest.TestCase):
    def test_f1_2023(self):
        with gzip.open(os.path.join(DADOS, "wikipedia_2023_formula_one.html.gz"), "rt", encoding="utf-8") as f:
            html = f.read()
        modelo = db.carregar_arquivo(db.arquivos_do_ano(2026)[0], validar=False)
        d, _ = wikipedia.importar(html, 2023, "formula_1", "Fórmula 1", modelo)
        art = {p["nome"]: p.get("wikipedia") for p in d["pilotos"]}
        self.assertEqual(art.get("Max Verstappen"), "Max Verstappen")
        self.assertTrue(all(e.get("wikipedia") for e in d["equipes"]))
        self.assertIn("Circuit de Monaco", {e.get("wikipedia") for e in d["calendario"]})
        self.assertEqual(db.validar_dados(d), [])


if __name__ == "__main__":
    unittest.main()
