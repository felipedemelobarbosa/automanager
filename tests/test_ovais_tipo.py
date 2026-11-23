"""Tipo de oval pelas retas/curvas: superspeedway (pelotão), intermediário e curto – percentuais medidos no mapa
real de cada pista (critério pela velocidade, o padrão em ovais)."""
import copy
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state  # noqa: E402
from automanager.editor import mapa_pista  # noqa: E402
from automanager.event.inscritos import montar_inscritos  # noqa: E402
from automanager.event.sessoes import Evento  # noqa: E402

CID = "formula_alfa"
PISTAS = {"daytona": (93, 7, 0), "charlotte": (50, 49, 1), "charlotte_pelo_raio": (44, 56, 0),
          "martinsville": (48, 15, 37), "bristol": (43, 20, 37)}


class TestTipoDeOval(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
        cls.c = cls.st["categorias"][CID]
        cls.base = next(e for e in cls.c["calendario"] if e.get("tipo_pista") == "oval")

    def perfil(self, nome):
        r, a, b = PISTAS[nome]
        pista = dict(copy.deepcopy(self.base), retas=r, curvas_alta=a, curvas_baixa=b)
        ev = Evento(self.c["categoria"], pista, montar_inscritos(self.st, CID, None, pista), random.Random(1))
        return ev.perfil_oval()

    def test_tipos(self):
        self.assertEqual(self.perfil("daytona")["pelotao"], 1.0)                      # superspeedway
        self.assertEqual(self.perfil("daytona")["curto"], 0.0)
        for nome in ("charlotte", "charlotte_pelo_raio"):                             # intermediário
            self.assertEqual(self.perfil(nome)["pelotao"], 0.0, nome)
            self.assertLess(self.perfil(nome)["curto"], 0.05, nome)                   # menos de 50% de retas não é curto
        for nome in ("martinsville", "bristol"):                                      # curto
            self.assertGreater(self.perfil(nome)["curto"], 0.7, nome)
            self.assertEqual(self.perfil(nome)["pelotao"], 0.0, nome)

    def test_parametros_do_oval_curto(self):
        p = self.perfil("martinsville")
        self.assertEqual((p["amarelas_oval_curto"], p["ultrapassagem_oval_curto"]), (2.0, 0.7))

    def test_mapa_usa_velocidade_em_ovais(self):
        cfg = mapa_pista.config(None)
        self.assertEqual((cfg["criterio"], cfg["criterio_oval"]), ("raio", "velocidade"))


if __name__ == "__main__":
    unittest.main()
