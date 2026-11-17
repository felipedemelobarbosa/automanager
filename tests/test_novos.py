"""Testes de desenvolvimento, mercado, campeonato/histórico e importador da Wikipedia."""
import gzip
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import (db, state, routines, desenvolvimento as dev, mercado, campeonato,  # noqa: E402
                         contratos)
from automanager.editor import wikipedia  # noqa: E402

ALFA = [a for a in db.arquivos_do_ano(2026) if "alfa" in a][0]
BETA = [a for a in db.arquivos_do_ano(2026) if "beta" in a][0]


def novo(arqs=None, cid="formula_alfa", eid="vortex"):
    st = state.novo_jogo(arqs or db.arquivos_do_ano(2026))
    state.escolher_equipe(st, cid, eid)
    return st


class TestDesenvolvimento(unittest.TestCase):
    def test_custo_fixo_e_progressivo(self):
        cfg = {"custo_por_ponto": 1000, "limite_custo_fixo": 50, "escala_progressiva": 10}
        self.assertEqual(dev.custo_ponto(cfg, 10), 1000)
        self.assertEqual(dev.custo_ponto(cfg, 49), 1000)
        self.assertGreater(dev.custo_ponto(cfg, 60), dev.custo_ponto(cfg, 55))

    def test_so_quando_a_categoria_permite(self):
        st = novo()
        self.assertTrue(dev.pode(st, "formula_alfa", st["categorias"]["formula_alfa"]["equipes"]["vortex"], "chassis"))
        self.assertTrue(dev.pode(st, "formula_alfa", st["categorias"]["formula_alfa"]["equipes"]["vortex"], "motor"))
        # motor comprado: não desenvolve
        self.assertFalse(dev.pode(st, "formula_alfa", st["categorias"]["formula_alfa"]["equipes"]["kestrel"], "motor"))
        # categoria sem desenvolvimento
        self.assertFalse(dev.pode(st, "formula_beta", st["categorias"]["formula_beta"]["equipes"]["prisma"], "chassis"))

    def test_investir_atual_e_manutencao(self):
        st = novo()
        eq = st["categorias"]["formula_alfa"]["equipes"]["vortex"]
        antes = dev.valores_atuais(st, "formula_alfa", eq, "chassis")["grip"]
        caixa = eq["financas"]["caixa"]
        custo = dev.investir_atual(st, "formula_alfa", eq, "chassis", {"grip": antes + 2})
        self.assertEqual(dev.valores_atuais(st, "formula_alfa", eq, "chassis")["grip"], antes + 2)
        self.assertAlmostEqual(eq["financas"]["caixa"], caixa - custo)
        # manutenção: perda de 30% em cada item na virada
        atuais = dev.valores_atuais(st, "formula_alfa", eq, "chassis")
        dev.aplicar_projetos(st, 2027)
        depois = dev.valores_atuais(st, "formula_alfa", eq, "chassis")
        for k in atuais:
            self.assertEqual(depois[k], int(atuais[k] * 0.7))

    def test_projeto_novo_parte_do_zero(self):
        st = novo()
        eq = st["categorias"]["formula_alfa"]["equipes"]["vortex"]
        dev.mudar_modo(eq, "chassis", "novo")
        self.assertTrue(all(v == 0 for v in dev.valores_projeto(st, "formula_alfa", eq, "chassis").values()))
        dev.investir_projeto(st, "formula_alfa", eq, "chassis", {"aerodinamica": 30})
        dev.aplicar_projetos(st, 2027)
        v = dev.valores_atuais(st, "formula_alfa", eq, "chassis")
        self.assertEqual(v["aerodinamica"], 30)
        self.assertEqual(v["grip"], 0)


class TestMercado(unittest.TestCase):
    def test_proposta_usuario_resposta_na_semana_seguinte(self):
        st = novo(cid="formula_alfa", eid="tucano")
        st["semana"] = 25
        livre = next(p for p in st["pilotos"].values() if mercado.livre_agora(p))
        # 'agora' exige vaga livre na equipe
        self.assertIsNotNone(mercado.fazer_proposta(st, livre["id"], "principal", 500000, 1, "temporadas", "agora"))
        # libera uma vaga de principal
        p0 = next(p for p in state.pilotos_da_equipe(st, "formula_alfa", "tucano") if p["contrato"]["situacao"] == "principal")
        p0["contrato"] = None
        erro = mercado.fazer_proposta(st, livre["id"], "principal", 500000, 3, "corridas", "agora")
        self.assertIsNone(erro)
        routines.avancar_semana(st, random.Random(1))          # mesma semana: ainda sem resposta
        self.assertIn(livre["id"], [p["piloto"] for p in st["propostas_usuario"].values()])
        routines.avancar_semana(st, random.Random(1))
        self.assertNotIn(livre["id"], [p["piloto"] for p in st.get("propostas_usuario", {}).values()])
        respostas = [n["texto"] for n in st["noticias"] if livre["nome"] in n["texto"] and n["tipo"] == "usuario"]
        self.assertTrue(any(k in t for t in respostas for k in ("recusou", "contrata", "cancelada")))

    def test_mobilidade_por_tier(self):
        st = novo()
        piloto_beta = next(p for p in st["pilotos"].values() if p["categoria_origem"] == "formula_beta")
        piloto_alfa = next(p for p in st["pilotos"].values() if p["categoria_origem"] == "formula_alfa")
        self.assertEqual(mercado.mobilidade(st, "formula_alfa", piloto_beta), 1.0)   # sobe do tier 2 para o 1
        self.assertEqual(mercado.mobilidade(st, "formula_beta", piloto_alfa), 0.3)   # desce do tier 1 para o 2
        self.assertEqual(mercado.mobilidade(st, "formula_alfa", piloto_alfa), 1.0)

    def test_exclusividade_de_motor(self):
        st = novo()
        c = st["categorias"]["formula_alfa"]
        ops = {m["id"]: (ok, mot) for m, ok, mot in mercado.opcoes(st, "formula_alfa", c["equipes"]["tucano"], "motor")}
        self.assertFalse(ops["mot_ventura"][0])            # exclusivo da Andes Racing
        ops_andes = {m["id"]: ok for m, ok, _ in mercado.opcoes(st, "formula_alfa", c["equipes"]["andes"], "motor")}
        self.assertTrue(ops_andes["mot_ventura"])
        erro = mercado.contratar_parte(st, "formula_alfa", c["equipes"]["tucano"], "motor", "mot_ventura", 1,
                                       "temporadas", "proxima")
        self.assertIn("recusado", erro)

    def test_contrato_de_chassis_por_corridas(self):
        st = novo(cid="formula_beta", eid="prisma")
        eq = st["categorias"]["formula_beta"]["equipes"]["prisma"]
        eq["chassis"] = None
        self.assertIsNone(mercado.contratar_parte(st, "formula_beta", eq, "chassis", "ch_marlin", 2, "corridas", "agora"))
        self.assertEqual(eq["chassis"]["contrato"], {"valor_por_corrida": 50000, "corridas": 2})
        mercado.fim_de_corrida_partes(st, "formula_beta")
        mercado.fim_de_corrida_partes(st, "formula_beta")
        self.assertIsNone(eq["chassis"])

    def test_patrocinadores_procuram_equipes(self):
        st = novo()
        rng = random.Random(4)
        for c in st["categorias"].values():
            for p in c["patrocinadores"].values():
                p["contrato"] = None
                p["ativo"] = True
        for _ in range(30):
            mercado.rotina_patrocinadores(st, rng)
        c = st["categorias"]["formula_alfa"]
        com = [p for p in c["patrocinadores"].values() if p.get("contrato")]
        self.assertGreater(len(com), 3)
        self.assertGreater(len({p["contrato"]["equipe"] for p in com}), 1)   # não vão todos para a mesma equipe


class TestCampeonato(unittest.TestCase):
    def test_temporada_completa_e_historico(self):
        st = novo(cid="formula_alfa", eid="tucano")
        rng = random.Random(7)
        esperadas = {cid: sum(1 for e in c["calendario"] if e["especie"] == "corrida" and e.get("ativo"))
                     for cid, c in st["categorias"].items()}
        while st["ano"] == 2026:
            pista = routines.corrida_do_usuario_na_semana(st)
            if pista:
                campeonato.simular_em_segundo_plano(st, "formula_alfa", pista, rng)
            routines.avancar_semana(st, rng)
        for cid, c in st["categorias"].items():
            t = st["temporadas"]["2026"][cid]
            self.assertEqual(len(t["corridas"]), esperadas[cid])
            self.assertTrue(t["final"]["pilotos"])
            soma = sum(l["pontos"] for r in t["corridas"] for l in r["resultado"])
            self.assertEqual(soma, sum(p["pontos"] for p in t["final"]["pilotos"]))
        pil, eqs = campeonato.total_geral(st)
        self.assertEqual(sum(p["titulos"] for p in pil), 2)
        self.assertEqual(len(campeonato.campeoes(st)), 2)

    def test_sem_penalidade_por_nao_parar(self):
        from automanager.event.sessoes import Evento
        from automanager.event.inscritos import montar_inscritos
        st = novo()
        c = st["categorias"]["formula_alfa"]
        ev = Evento(c["categoria"], dict(c["calendario"][2], prob_chuva=0), montar_inscritos(st, "formula_alfa", "vortex"),
                    random.Random(2))
        while ev.proxima_sessao():
            for car in ev.carros:
                if car.usuario:
                    car.estrategia_auto = False
            ev.sessao.iniciar()
            ev.sessao.simular_ate_o_fim()
        log = "\n".join(ev.sessao.log)
        self.assertNotIn("parada obrigatória", log.lower().replace("pit stop (parada obrigatória)", ""))
        for car in ev.carros:
            if car.usuario:
                # estratégia manual sem chamada ao box: só o furo obriga a parar
                furos = sum(1 for m in ev.sessao.log if car.nome in m and "pneu furado" in m)
                self.assertEqual(car.paradas, furos)


class TestWikipedia(unittest.TestCase):
    def test_importa_f1_2005(self):
        html = gzip.open(os.path.join(os.path.dirname(__file__), "dados", "wikipedia_2005_formula_one.html.gz"),
                         "rt", encoding="utf-8").read()
        modelo = db.carregar_arquivo(ALFA)
        d, avisos = wikipedia.importar(html, 2005, "formula_1", "Fórmula 1", modelo)
        self.assertEqual(db.validar_dados(d), [])
        self.assertEqual(len(d["equipes"]), 10)
        self.assertEqual(len(d["calendario"]), 19)
        nomes = {p["nome"]: p for p in d["pilotos"]}
        self.assertEqual(nomes["Fernando Alonso"]["nacionalidade"], "Espanha")
        self.assertEqual(nomes["Fernando Alonso"]["contrato"]["equipe"], "renault")
        self.assertGreater(sum(nomes["Fernando Alonso"]["atributos"].values()),
                           sum(nomes["Patrick Friesacher"]["atributos"].values()))
        ferrari = next(m for m in d["motores"] if m["id"] == "mot_ferrari")
        self.assertEqual(ferrari["fabricante"], {"tipo": "equipe", "equipe": "ferrari"})
        self.assertEqual(d["categoria"]["pontuacao"]["posicoes"], [10, 8, 6, 5, 4, 3, 2, 1])
        # o arquivo importado é jogável
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            caminho = os.path.join(tmp, "formula_1_2005.json")
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(d, f)
            st = state.novo_jogo([caminho])
            state.escolher_equipe(st, "formula_1", "minardi")
            pista = next(e for e in st["categorias"]["formula_1"]["calendario"])
            reg = campeonato.simular_em_segundo_plano(st, "formula_1", pista, random.Random(1))
            self.assertTrue(reg["resultado"])


class TestContratos(unittest.TestCase):
    def test_termina_nesta_temporada(self):
        self.assertTrue(contratos.termina_nesta_temporada({"temporadas": 1}, 5))
        self.assertFalse(contratos.termina_nesta_temporada({"temporadas": 2}, 5))
        self.assertTrue(contratos.termina_nesta_temporada({"corridas": 3}, 5))
        self.assertFalse(contratos.termina_nesta_temporada({"corridas": 8}, 5))


if __name__ == "__main__":
    unittest.main()


class TestSalvarNoMeioDoEvento(unittest.TestCase):
    def _rodar(self, cortes=()):
        import json
        from automanager.event.sessoes import Evento
        from automanager.event.inscritos import montar_inscritos
        from automanager.event import persistencia
        st = novo(cid="formula_alfa", eid="tucano")
        c = st["categorias"]["formula_alfa"]
        ev = Evento(c["categoria"], c["calendario"][2], montar_inscritos(st, "formula_alfa", "tucano"), random.Random(9))
        passo = 0
        while True:
            if ev.sessao is None or ev.sessao.terminada:
                if not ev.proxima_sessao():
                    break
                ev.sessao.iniciar()
            if ev.sessao.tipo == "corrida":
                ev.sessao.avancar_volta()
            else:
                ev.sessao.avancar(300)
            passo += 1
            if passo in cortes:   # salva em JSON, recarrega o estado inteiro e continua
                st = json.loads(json.dumps(st))
                ev, _ = persistencia.restaurar(json.loads(json.dumps(persistencia.serializar(ev, "formula_alfa"))), st)
        return [(r["carro"].id, round(r["carro"].tempo_total, 6), r["pontos"]) for r in ev.resultado_corrida]

    def test_continua_exatamente_igual(self):
        self.assertEqual(self._rodar(), self._rodar(cortes=(1, 5, 40, 61, 90, 120)))


class TestImportadorGenerico(unittest.TestCase):
    """Uma página por série/época: importa, valida e simula uma corrida com o arquivo gerado."""
    ESPERADO = {  # arquivo: (equipes mínimas, monomarca?, principais por equipe)
        "1958_formula_one": (20, False, None), "1988_formula_one": (15, False, 2), "2023_formula_one": (10, False, 2),
        "2005_formula_one": (10, False, 2), "2023_formula_2": (10, True, 2), "2023_indycar": (12, True, 4),
        "2023_formula_e": (10, True, 2), "2023_btcc": (8, False, None)}

    def test_varias_series(self):
        import glob
        import json
        import tempfile
        modelo = db.carregar_arquivo(ALFA)
        arquivos = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "dados", "wikipedia_*.html.gz")))
        self.assertGreaterEqual(len(arquivos), 8)
        for arq in arquivos:
            chave = os.path.basename(arq)[len("wikipedia_"):-len(".html.gz")]
            with self.subTest(serie=chave):
                html = gzip.open(arq, "rt", encoding="utf-8").read()
                d, _ = wikipedia.importar(html, int(chave[:4]), "importada", "Importada", modelo)
                self.assertEqual(db.validar_dados(d), [])
                minimo, mono, princ = self.ESPERADO[chave]
                self.assertGreaterEqual(len(d["equipes"]), minimo)
                self.assertEqual(not d["categoria"]["regras"]["desenvolvimento_chassis_por_equipe"], mono)
                if princ:
                    self.assertEqual(d["categoria"]["regras"]["pilotos_principais_por_equipe"], princ)
                self.assertGreater(len(d["calendario"]), 5)
                self.assertTrue(all(p["nacionalidade"] for p in d["pilotos"]))
                with tempfile.TemporaryDirectory() as tmp:
                    caminho = os.path.join(tmp, f"importada_{chave[:4]}.json")
                    with open(caminho, "w", encoding="utf-8") as f:
                        json.dump(d, f)
                    st = state.novo_jogo([caminho])
                    reg = campeonato.simular_em_segundo_plano(st, "importada", st["categorias"]["importada"]
                                                              ["calendario"][0], random.Random(1))
                    self.assertTrue(reg and reg["resultado"])


class TestRodada4(unittest.TestCase):
    def test_manutencao_nao_aceita_investimento(self):
        st = novo()
        eq = st["categorias"]["formula_alfa"]["equipes"]["vortex"]
        dev.mudar_modo(eq, "chassis", "manutencao")
        with self.assertRaises(ValueError):
            dev.investir_projeto(st, "formula_alfa", eq, "chassis", {"grip": 99})
        atuais = dev.valores_atuais(st, "formula_alfa", eq, "chassis")
        self.assertEqual(dev.valores_projeto(st, "formula_alfa", eq, "chassis"),
                         {k: int(v * 0.7) for k, v in atuais.items()})

    def test_testes_coletivos_tem_resultado(self):
        st = novo()
        rng = random.Random(2)
        while st["semana"] <= 8:
            routines.avancar_semana(st, rng)
        testes = campeonato.testes_da_temporada(st, "formula_alfa")
        self.assertEqual(len(testes), 2)
        for t in testes:
            self.assertTrue(t["geral"])
            tempos = [l["melhor"] for l in t["geral"]]
            self.assertEqual(tempos, sorted(tempos))
        self.assertTrue(any("mais rápidos" in n["texto"] for n in st["noticias"]))


class TestBoxNosTreinos(unittest.TestCase):
    def _evento(self):
        from automanager.event.sessoes import Evento
        from automanager.event.inscritos import montar_inscritos
        st = novo(cid="formula_alfa", eid="tucano")
        c = st["categorias"]["formula_alfa"]
        ev = Evento(c["categoria"], dict(c["calendario"][2], prob_chuva=0),
                    montar_inscritos(st, "formula_alfa", "tucano"), random.Random(4))
        ev.proxima_sessao()
        ev.sessao.iniciar()
        return ev, next(car for car in ev.carros if car.usuario)

    def test_chamar_ajustar_e_voltar(self):
        ev, car = self._evento()
        s = ev.sessao
        while not s.pode_chamar_box(car):
            s.avancar(30)
        s.chamar_box(car)
        voltas_antes = car.voltas
        while not getattr(car, "aguardando", False):
            s.avancar(30)
        self.assertEqual(car.status, "garagem")
        self.assertLessEqual(car.voltas - voltas_antes, 2)              # termina a volta e faz a de entrada
        relogio = s.relogio
        s.avancar(300)
        self.assertEqual(car.status, "garagem")                         # espera o usuário
        self.assertGreater(s.relogio, relogio)
        car.acerto = {k: 80 for k in car.acerto}
        s.liberar(car)
        self.assertFalse(car.aguardando)
        s.avancar(400)
        self.assertEqual(car.acerto["aerodinamica"], 80)
        s.simular_ate_o_fim()
        self.assertTrue(s.terminada)

    def test_parado_no_box_ate_o_fim(self):
        ev, car = self._evento()
        s = ev.sessao
        while not s.pode_chamar_box(car):
            s.avancar(30)
        s.chamar_box(car)
        for _ in range(400):                                            # nunca libera
            if s.terminada:
                break
            s.avancar(30)
        self.assertTrue(s.terminada)
        self.assertGreaterEqual(s.relogio, s.fases[-1]["valor"] * 60)

    def test_teste_coletivo_jogado_e_registrado(self):
        st = novo(cid="formula_alfa", eid="tucano")
        rng = random.Random(1)
        while not routines.teste_do_usuario_na_semana(st):
            routines.avancar_semana(st, rng)
        pista = routines.teste_do_usuario_na_semana(st)
        from automanager.event.inscritos import montar_inscritos
        ev = campeonato.criar_evento_teste(st, "formula_alfa", pista, montar_inscritos(st, "formula_alfa", "tucano"), rng)
        while ev.proxima_sessao():
            ev.sessao.iniciar()
            ev.sessao.simular_ate_o_fim()
        campeonato.registrar_teste(st, "formula_alfa", pista, ev)
        routines.avancar_semana(st, rng)                                # não simula de novo
        testes = campeonato.testes_da_temporada(st, "formula_alfa")
        self.assertEqual(len([t for t in testes if t["evento"] == pista["id"]]), 1)
        self.assertTrue(any("Sua equipe no teste" in n["texto"] for n in st["noticias"]))
