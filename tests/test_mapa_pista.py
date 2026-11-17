"""Retas e curvas a partir do mapa da pista (sem rede: pista desenhada com medidas conhecidas)."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from PIL import Image, ImageDraw
    from automanager.editor import mapa_pista as mp
except ImportError:                                   # pragma: no cover
    mp = None


def estadio(reta_px=300, raio_px=100, espessura=12, rotulos=True):
    """Pista oval: duas retas e duas curvas de raio conhecido, com textos e uma linha fina (como nos mapas)."""
    w, h = reta_px + 2 * raio_px + 200, 2 * raio_px + 200
    im = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(im)
    x0, y0 = 100 + raio_px, 100
    pts = []
    for i in range(200):
        pts.append((x0 + reta_px * i / 200, y0))
    for i in range(200):
        a = -math.pi / 2 + math.pi * i / 200
        pts.append((x0 + reta_px + raio_px * math.cos(a), y0 + raio_px + raio_px * math.sin(a)))
    for i in range(200):
        pts.append((x0 + reta_px - reta_px * i / 200, y0 + 2 * raio_px))
    for i in range(200):
        a = math.pi / 2 + math.pi * i / 200
        pts.append((x0 + raio_px * math.cos(a), y0 + raio_px + raio_px * math.sin(a)))
    d.line(pts + [pts[0]], fill=(0, 0, 0), width=espessura, joint="curve")
    if rotulos:
        d.text((x0 + 50, y0 + 60), "Curva 1  N  500 m", fill=(0, 0, 0))
        d.line([(20, 20), (150, 20)], fill=(0, 0, 0), width=2)                 # escala do mapa
        d.line([(x0, y0 + 2 * raio_px), (x0 + 100, y0 + 2 * raio_px + 60)], fill=(120, 120, 120), width=6)
    comprimento_px = 2 * reta_px + 2 * math.pi * raio_px
    return im, comprimento_px


@unittest.skipIf(mp is None, "Pillow não instalado")
class TestMapaPista(unittest.TestCase):
    def test_estadio_reconhecido_e_medido(self):
        im, comp_px = estadio()
        laco = mp.tracar(mp.abrir_imagem(im))
        # 1 px = 1 m: retas 600 m, curvas de raio 100 m (curva de alta pelo padrão: 80 a 400 m)
        r = mp.analisar(laco, comp_px / 1000.0, mp.config(None))
        p = r["percentuais"]["raio"]
        esperado_retas = 100 * 600 / comp_px
        self.assertAlmostEqual(p["retas"], esperado_retas, delta=8)
        self.assertAlmostEqual(p["curvas_alta"], 100 - esperado_retas, delta=8)
        self.assertLessEqual(p["curvas_baixa"], 5)
        self.assertEqual(sum(p.values()), 100)
        self.assertEqual(sum(r["percentuais"]["velocidade"].values()), 100)

    def test_curvas_fechadas_viram_baixa(self):
        im, comp_px = estadio(raio_px=100)
        laco = mp.tracar(mp.abrir_imagem(im))
        # mesma pista, mas com escala 1 px = 0,5 m: curvas de 50 m de raio -> curvas de baixa
        p = mp.analisar(laco, comp_px * 0.5 / 1000.0, mp.config(None))["percentuais"]["raio"]
        self.assertGreater(p["curvas_baixa"], 35)
        self.assertLessEqual(p["curvas_alta"], 10)

    def test_marcacao_manual(self):
        # quadrado de cantos arredondados marcado à mão: a spline fecha o laço
        pts = [(0, 0), (500, 0), (1000, 0), (1000, 500), (1000, 1000), (500, 1000), (0, 1000), (0, 500)]
        laco = mp.spline_fechada(pts)
        p = mp.analisar(laco, 4.0, mp.config(None))["percentuais"]["raio"]
        self.assertEqual(sum(p.values()), 100)
        self.assertGreater(p["retas"], 30)

    def test_config_da_categoria(self):
        cfg = mp.config({"mapa_pista": {"criterio": "velocidade", "raio_reta": 300}})
        self.assertEqual(cfg["criterio"], "velocidade")
        self.assertEqual(cfg["raio_reta"], 300)
        self.assertEqual(cfg["raio_baixa"], 80)


if __name__ == "__main__":
    unittest.main()
