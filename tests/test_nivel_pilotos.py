"""Nível da população de pilotos ancorado na database e retorno de aposentados."""
import os
import random
import statistics as S
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, routines, carreira  # noqa: E402


def titulares(st, cid):
    return [sum(p["atributos"].values()) / len(p["atributos"]) for p in st["pilotos"].values()
            if (p.get("contrato") or {}).get("categoria") == cid and p["contrato"]["situacao"] == "principal"]


class TestNivel(unittest.TestCase):
    def test_referencia_gravada(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
        cal = st["calibracao_pilotos"]
        self.assertAlmostEqual(cal["ref"]["formula_alfa"], S.mean(titulares(st, "formula_alfa")), places=1)
        self.assertLess(cal["estreia"]["media"], cal["potencial"]["media"])

    def test_estreantes_ancorados_na_database(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
        for p in st["pilotos"].values():                        # categoria "inflada": não muda o nível dos novatos
            p["atributos"] = {k: 95 for k in p["atributos"]}
        novos = carreira.gerar_ficticios(st, 60, random.Random(2))
        m = S.mean(sum(p["atributos"].values()) / len(p["atributos"]) for p in novos)
        self.assertAlmostEqual(m, st["calibracao_pilotos"]["estreia"]["media"], delta=3)

    def test_tier_mais_alto_estavel(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=5)
        st["usuario"] = {"categoria": None, "equipe": None}
        ref = st["calibracao_pilotos"]["ref"]["formula_alfa"]
        rng = random.Random(5)
        medias = []
        while st["ano"] < 2034:
            routines.avancar_semana(st, rng)
            if st["semana"] == 2:
                medias.append(S.mean(titulares(st, "formula_alfa")))
        self.assertLess(abs(S.mean(medias[-3:]) - ref), 5)


class TestRetorno(unittest.TestCase):
    def _aposentar(self, st, pid):
        p = st["pilotos"].pop(pid)
        p.update({"aposentado_em": st["ano"] - 2, "categoria_saida": "formula_alfa", "contrato": None, "idade": 33})
        st.setdefault("aposentados", {})[pid] = p
        return p

    def test_volta_com_chance_configuravel(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
        st["categorias"]["formula_alfa"]["categoria"].setdefault("mobilidade", {})["retorno"] = \
            {"prob_anual": 1.0, "anos_maximos_fora": 6, "idade_maxima": 40}
        pid = next(iter(st["pilotos"]))
        p = self._aposentar(st, pid)
        antes = dict(p["atributos"])
        carreira.retornos(st, random.Random(1))
        self.assertIn(pid, st["pilotos"])
        self.assertEqual(p["idade"], 35)
        self.assertEqual(p["categoria_atual"], "formula_alfa")
        self.assertGreater(p["ano_aposentadoria"], st["ano"])
        self.assertTrue(any("volta às pistas" in n["texto"] for n in st["noticias"]))
        self.assertIsNotNone(antes)

    def test_sem_chance_ou_velho_demais(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
        mob = st["categorias"]["formula_alfa"]["categoria"].setdefault("mobilidade", {})
        mob["retorno"] = {"prob_anual": 0.0}
        a, b = list(st["pilotos"])[:2]
        self._aposentar(st, a)
        carreira.retornos(st, random.Random(1))
        self.assertNotIn(a, st["pilotos"])
        mob["retorno"] = {"prob_anual": 1.0, "idade_maxima": 34}
        self._aposentar(st, b)
        carreira.retornos(st, random.Random(1))
        self.assertNotIn(b, st["pilotos"])                        # 33 + 2 anos fora = 35 > 34


if __name__ == "__main__":
    unittest.main()


class TestIdade(unittest.TestCase):
    def test_idade_maxima(self):
        from automanager import mercado
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
        state.escolher_equipe(st, "formula_beta", "prisma")
        cat = st["categorias"]["formula_beta"]["categoria"]
        cat["regras"]["idade_pilotos"] = {"idade_maxima": 25}
        velho = next(p for p in st["pilotos"].values() if not p.get("contrato") and p.get("idade", 0) > 26)
        erro = mercado.fazer_proposta(st, velho["id"], "principal", 50000, 1, "temporadas", "proxima")
        self.assertIn("mais de 25 anos", erro or "")
        # na virada, contrato de quem passou da idade termina
        pid = next(p["id"] for p in st["pilotos"].values()
                   if (p.get("contrato") or {}).get("categoria") == "formula_beta")
        st["pilotos"][pid]["idade"] = 26
        mercado.aplicar_idade_maxima(st)
        self.assertIsNone(st["pilotos"][pid]["contrato"])

    def test_preferencia_por_jovens(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=7)
        st["usuario"] = {"categoria": None, "equipe": None}
        st["categorias"]["formula_beta"]["categoria"]["regras"]["idade_pilotos"] = \
            {"preferida_ate": 22, "penalidade_por_ano": 4}
        rng = random.Random(7)
        while st["ano"] < 2031:
            routines.avancar_semana(st, rng)
        idades = [p["idade"] for p in st["pilotos"].values()
                  if (p.get("contrato") or {}).get("categoria") == "formula_beta" and p["contrato"]["situacao"] == "principal"]
        self.assertLess(S.mean(idades), 24)
