"""Calibração automática dos custos de desenvolvimento e evolução dos motores de fabricantes."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, routines, desenvolvimento as dev  # noqa: E402

CID = "formula_alfa"


class TestCalibracao(unittest.TestCase):
    def test_fatores_gravados_e_nivel_alvo(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
        cfg = st["categorias"][CID]["categoria"]["desenvolvimento"]
        cal = cfg["calibracao"]
        for parte in ("chassis", "motor"):
            self.assertIn(parte, cal)
            self.assertAlmostEqual(cfg[parte]["custo_por_ponto"], cal[parte]["custo_original"] * cal[parte]["fator"])
        self.assertEqual(set(cal["fabricantes"]), {"mot_kraft", "mot_rhone"})
        # com a verba calibrada, um projeto novo de fabricante reconstrói o nível da database
        for mid, f in cal["fabricantes"].items():
            nivel = dev._estimar(cfg["motor"], {"potencia": 0}, f["verba"] * dev.FRACAO_PROJETO_NOVO)
            self.assertAlmostEqual(nivel, f["nivel_alvo"], delta=1)
        # categoria sem desenvolvimento não é calibrada
        self.assertIsNone(st["categorias"]["formula_beta"]["categoria"].get("desenvolvimento"))

    def test_pode_desligar(self):
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=1)
        cfg = st["categorias"][CID]["categoria"]["desenvolvimento"]
        cfg.pop("calibracao")
        cfg["calibracao_automatica"] = False
        dev.calibrar_custos(st)
        self.assertNotIn("calibracao", cfg)

    def test_nivel_se_mantem_e_fabricantes_evoluem(self):
        fab = ("mot_kraft", "mot_rhone")
        derivas = []
        for semente in (3, 5):                      # média de duas sementes: uma só oscila demais com o acaso
            st = state.novo_jogo(db.arquivos_do_ano(2026), semente=semente)   # o jogo inicial também (senão varia)
            st["usuario"] = {"categoria": None, "equipe": None}
            c = st["categorias"][CID]
            inicio = {m["id"]: m["potencia"] for m in c["motores"].values()}
            rng = random.Random(semente)
            historico = []
            while st["ano"] < 2030:
                routines.avancar_semana(st, rng)
                if st["semana"] == 1:
                    historico.append({m["id"]: m["potencia"] for m in c["motores"].values()})
            self.assertTrue(any(h[m] != inicio[m] for h in historico for m in fab))  # fabricantes não congelam
            obras = [m for m in inicio if m not in fab]
            media0 = sum(inicio[m] for m in obras) / len(obras)
            # média das últimas 3 temporadas (um ano isolado oscila com as finanças de cada equipe)
            media_final = sum(h[m] for h in historico[-3:] for m in obras) / (3 * len(obras))
            derivas.append(media_final - media0)
            self.assertTrue(all(0 < v <= 100 for h in historico for v in h.values()))
        self.assertLess(abs(sum(derivas) / len(derivas)), 8)                        # sem deriva forte


    def test_caixa_inicial_nao_faz_o_carro_saltar(self):
        """O caixa inicial acima da reserva é investido aos poucos (uso_do_excedente por temporada) e a calibração
        conta com ele: o nível médio de motor e chassis próprios não salta na 1ª temporada."""
        fab = ("mot_kraft", "mot_rhone")
        st = state.novo_jogo(db.arquivos_do_ano(2026), semente=2)
        st["usuario"] = {"categoria": None, "equipe": None}
        c = st["categorias"][CID]

        def niveis():
            motor = [m["potencia"] for k, m in c["motores"].items() if k not in fab]
            chassis = [dev._nivel(dev._entidade(st, CID, e, "chassis"), "chassis") for e in c["equipes"].values()
                       if e.get("ativa") and dev.pode(st, CID, e, "chassis")]
            return sum(motor) / len(motor), sum(chassis) / len(chassis)
        m0, c0 = niveis()
        rng = random.Random(3)
        while st["ano"] == 2026:
            routines.avancar_semana(st, rng)
        m1, c1 = niveis()
        self.assertLess(abs(m1 - m0), 5)          # antes: +10,7 (o caixa inicial ia quase todo na 1ª temporada)
        self.assertLess(abs(c1 - c0), 7)          # antes: +14,7
        caixa = [e["financas"]["caixa"] for e in c["equipes"].values() if e.get("ativa")]
        self.assertGreater(min(caixa), c["categoria"]["regras"]["orcamento_medio"] * 0.15)   # sobra excedente


if __name__ == "__main__":
    unittest.main()
