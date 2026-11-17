"""Idiomas: dicionários consistentes e tradução de textos exatos, montados (modelos) e por linha."""
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import i18n  # noqa: E402


class TestIdiomas(unittest.TestCase):
    def tearDown(self):
        i18n.definir("pt")

    def test_dicionarios(self):
        for lang in ("en", "es"):
            with open(os.path.join(i18n.PASTA, f"{lang}.json"), encoding="utf-8") as f:
                d = json.load(f)
            self.assertGreater(len(d), 1000)
            for k, v in d.items():
                a = sorted(set(re.findall(r"(?<!\{)\{(\d+)\}", k)))
                b = sorted(set(re.findall(r"(?<!\{)\{(\d+)\}", v)))
                self.assertEqual(a, b, f"{lang}: {k!r} -> {v!r}")

    def test_portugues_nao_muda(self):
        i18n.definir("pt")
        self.assertEqual(i18n.t("Continuar  >>"), "Continuar  >>")

    def test_ingles(self):
        i18n.definir("en")
        self.assertEqual(i18n.t("Continuar  >>"), "Continue  >>")
        self.assertEqual(i18n.t("SEMANA 3 / 52"), "WEEK 3 / 52")
        self.assertEqual(i18n.t("Tomás Ibarra (Vortex Racing) vence o Grande Prêmio X. Pódio: 2º A, 3º B."),
                         "Tomás Ibarra (Vortex Racing) vence o Grande Prêmio X. Pódio: 2º A, 3º B.")
        self.assertEqual(i18n.t("Fórmula Alfa: Tomás Ibarra (Vortex Racing) vence o GP X. Pódio: 2º A, 3º B."),
                         "Fórmula Alfa: Tomás Ibarra (Vortex Racing) wins the GP X. Podium: P2 A, P3 B.")
        self.assertEqual(i18n.t("Idade:"), "Age:")
        self.assertEqual(i18n.t("Serra Azul, Brasil"), "Serra Azul, Brazil")
        self.assertEqual(i18n.t("Scuderia Ventura"), "Scuderia Ventura")       # nomes não são traduzidos
        self.assertEqual(i18n.t("Sua equipe fez proposta a Ana (USD 1 por corrida, 2 temporadas). Resposta na "
                                "próxima semana."),
                         "Your team made an offer to Ana (USD 1 per race, 2 seasons). Answer next week.")

    def test_espanhol_varias_linhas(self):
        i18n.definir("es")
        self.assertEqual(i18n.t("Ordens aplicadas: Ana\nConduzidos pela IA: Bruno"),
                         "Órdenes aplicadas: Ana\nManejados por la IA: Bruno")
        self.assertEqual(i18n.t("Holanda"), "Países Bajos")


if __name__ == "__main__":
    unittest.main()
