"""Contrato por corridas com corridas definidas (revezamento) e aposentadoria por idade."""
import json
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, routines, carreira, campeonato, contratos  # noqa: E402
from automanager.event.inscritos import montar_inscritos  # noqa: E402


def dados_alfa():
    caminho = next(c for c in db.arquivos_do_ano(2026) if "formula_alfa" in c)
    return db.carregar_arquivo(caminho)


def jogo(d):
    pasta = tempfile.mkdtemp()
    caminho = os.path.join(pasta, "formula_alfa_2026.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(d, f)
    st = state.novo_jogo([caminho])
    state.escolher_equipe(st, "formula_alfa", "vortex")
    return st


def preparar_revezamento(d):
    corridas = [e["id"] for e in d["calendario"] if e["especie"] == "corrida"]
    tuc = [p for p in d["pilotos"] if (p.get("contrato") or {}).get("equipe") == "tucano"]
    princ = [p for p in tuc if p["contrato"]["situacao"] == "principal"]
    teste = next(p for p in tuc if p["contrato"]["situacao"] == "teste")
    a, b = princ[0], teste
    a["contrato"].update({"corridas": 2, "corridas_definidas": corridas[:2]})
    a["contrato"].pop("temporadas", None)
    b["contrato"].update({"situacao": "principal", "corridas": len(corridas) - 2,
                          "corridas_definidas": corridas[2:]})
    b["contrato"].pop("temporadas", None)
    return corridas, a, b, princ[1]


class TestRevezamento(unittest.TestCase):
    def test_validacao(self):
        d = dados_alfa()
        corridas, a, b, _ = preparar_revezamento(d)
        self.assertEqual(db.validar_dados(d), [])
        b["contrato"]["corridas_definidas"] = corridas[:3]
        self.assertTrue(any("escalados" in e for e in db.validar_dados(d)))
        b["contrato"]["corridas_definidas"] = ["nao_existe"]
        self.assertTrue(any("não existe no calendário" in e for e in db.validar_dados(d)))

    def test_inscritos_e_fim_do_contrato(self):
        d = dados_alfa()
        corridas, a, b, fixo = preparar_revezamento(d)
        st = jogo(d)
        cal = {e["id"]: e for e in st["categorias"]["formula_alfa"]["calendario"]}

        def da_tucano(ev):
            return {i["piloto"]["id_db"] for i in montar_inscritos(st, "formula_alfa", None, cal[ev])
                    if i["equipe"]["id"] == "tucano"}
        self.assertEqual(da_tucano(corridas[0]), {a["id"], fixo["id"]})
        self.assertEqual(da_tucano(corridas[3]), {b["id"], fixo["id"]})
        rng = random.Random(1)
        for _ in range(60):
            if st["ano"] != 2026:
                break
            ev = routines.corrida_do_usuario_na_semana(st)
            if ev:
                campeonato.simular_em_segundo_plano(st, "formula_alfa", ev, rng)
            routines.avancar_semana(st, rng)
            pa = st["pilotos"][state.id_global_piloto("formula_alfa", a["id"])]
            feitas = {r["evento"] for r in contratos.resultados_da_temporada(st, "formula_alfa", 2026)}
            if set(corridas[:2]) <= feitas and st["ano"] == 2026:
                self.assertTrue(pa.get("contrato") is None or pa["contrato"].get("equipe") != "tucano")
        res = st["temporadas"]["2026"]["formula_alfa"]["corridas"]
        for r in res:
            nomes = {x["nome"] for x in r["resultado"]}
            self.assertEqual(a["nome"] in nomes, r["evento"] in corridas[:2], r["evento"])


class TestAposentadoriaPorIdade(unittest.TestCase):
    def test_idade(self):
        p = {"idade": 30, "atributos": {"x": 50}, "idade_aposentadoria": 33}
        carreira.preparar_piloto(p, 2026, random.Random(0))
        self.assertEqual(p["ano_aposentadoria"], 2029)

    def test_validacao(self):
        d = dados_alfa()
        p = d["pilotos"][0]
        p["idade_aposentadoria"] = 38
        self.assertTrue(any("OU" in e for e in db.validar_dados(d)))
        p.pop("ano_aposentadoria")
        self.assertEqual(db.validar_dados(d), [])


if __name__ == "__main__":
    unittest.main()


class TestImportadorRevezamento(unittest.TestCase):
    def test_f1_2023_alphatauri(self):
        import gzip
        from automanager.editor import wikipedia
        pasta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados")
        with gzip.open(os.path.join(pasta, "wikipedia_2023_formula_one.html.gz"), "rt", encoding="utf-8") as f:
            html = f.read()
        d, _ = wikipedia.importar(html, 2026, "formula_1", "Fórmula 1", dados_alfa())
        ct = {p["nome"]: p.get("contrato") or {} for p in d["pilotos"]}
        self.assertEqual(ct["Nyck de Vries"]["corridas_definidas"], [f"ev{i:02d}" for i in range(1, 11)])
        self.assertEqual(ct["Liam Lawson"]["corridas_definidas"], [f"ev{i:02d}" for i in range(13, 18)])
        self.assertEqual(ct["Daniel Ricciardo"]["corridas_definidas"],
                         ["ev11", "ev12"] + [f"ev{i:02d}" for i in range(18, 23)])
        self.assertNotIn("corridas_definidas", ct["Yuki Tsunoda"])
        self.assertEqual(db.validar_dados(d), [])
        # jogando a temporada: cada um corre só nas suas etapas
        pasta_tmp = tempfile.mkdtemp()
        caminho = os.path.join(pasta_tmp, "formula_1_2026.json")
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(d, f)
        st = state.novo_jogo([caminho])
        state.escolher_equipe(st, "formula_1", "alpine")
        rng = random.Random(3)
        for _ in range(52):
            if st["ano"] != 2026:
                break
            ev = routines.corrida_do_usuario_na_semana(st)
            if ev:
                campeonato.simular_em_segundo_plano(st, "formula_1", ev, rng)
            routines.avancar_semana(st, rng)
        corridas = st["temporadas"]["2026"]["formula_1"]["corridas"]
        self.assertGreater(len(corridas), 15)
        for r in corridas:
            # pela AlphaTauri (livre depois do contrato, o piloto pode ser contratado por outra equipe)
            nomes = {x["nome"] for x in r["resultado"] if x["equipe"] == "alphatauri"}
            self.assertEqual("Nyck de Vries" in nomes, r["evento"] in ct["Nyck de Vries"]["corridas_definidas"])
            self.assertEqual("Liam Lawson" in nomes, r["evento"] in ct["Liam Lawson"]["corridas_definidas"])
