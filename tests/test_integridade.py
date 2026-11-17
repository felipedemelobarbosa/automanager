"""Integridade da importação de ordens (checksum, assinatura, formato mínimo, reprodução do resultado), do
arquivo da liga e um campeonato multijogador de várias temporadas inteiramente por arquivos em disco."""
import copy
import json
import math
import os
import random
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, multiplayer as mp, acoes, campeonato, desenvolvimento as dev  # noqa: E402
from automanager.event import planos as planos_evento  # noqa: E402

CID = "formula_alfa"
JOGADORES = [("ana", "tucano", "a1"), ("bruno", "vortex", "b2"), ("carla", "ventura", "c3")]


def nova_liga(politica="ia"):
    st = state.novo_jogo(db.arquivos_do_ano(2026))
    mp.criar_liga(st, "Liga Integridade", [{"nome": n.capitalize(), "categoria": CID, "equipe": e, "senha": s}
                                          for n, e, s in JOGADORES], politica)
    return st


def jogada_aleatoria(st_j, rng):
    """O que um jogador faz numa semana: algumas ações de gestão válidas e planos para os eventos da semana."""
    cid, eid = st_j["usuario"]["categoria"], st_j["usuario"]["equipe"]
    eq = st_j["categorias"][cid]["equipes"][eid]
    if rng.random() < 0.15:
        acoes.executar(st_j, "emprestimo", valor=rng.choice([500000, 1000000]), prazo=None)
    if rng.random() < 0.3:
        livres = [p for p in st_j["pilotos"].values() if not p.get("contrato") and not p.get("contrato_futuro")]
        if livres:
            p = rng.choice(livres)
            acoes.executar(st_j, "proposta_piloto", piloto=p["id"], situacao="teste", valor=rng.choice([20000, 60000]),
                           duracao=1, unidade="temporadas", inicio="proxima")
    for oferta in [o for o in st_j.get("ofertas_patrocinio", []) if o["categoria"] == cid
                   and o.get("equipe", eid) == eid][:1]:
        acoes.executar(st_j, "patrocinio", patrocinador=oferta["patrocinador"], aceitar=rng.random() < 0.7)
    for parte in ("chassis", "motor"):
        if dev.pode(st_j, cid, eq, parte) and eq["financas"]["caixa"] > 3e6 and rng.random() < 0.5:
            atuais = dev.valores_atuais(st_j, cid, eq, parte)
            k = min(atuais, key=atuais.get)
            acoes.executar(st_j, "dev_investir", parte=parte, proxima=False, incrementos={k: 1})
    sess = mp.sessao(st_j)
    comp = mp._compostos(st_j, cid)
    secos = [c for c in comp if st_j["categorias"][cid]["categoria"]["pneus"]["compostos"][c]["tipo"] == "seco"]
    for ev in st_j["categorias"][cid]["calendario"]:
        if ev["semana"] != st_j["semana"] or not ev.get("ativo"):
            continue
        for p in state.pilotos_da_equipe(st_j, cid, eid):
            pl = planos_evento.plano_padrao()
            for g in pl.values():
                for k in g["acerto"]:
                    g["acerto"][k] = rng.randint(30, 70)
            if ev["especie"] == "corrida":
                v = ev["voltas_corrida"]
                n = rng.randint(1, 2)
                cortes = sorted(rng.sample(range(8, v - 5), n))
                pl["corrida"]["paradas"] = [[rng.choice(secos), b - a] for a, b in zip([0] + cortes, cortes + [v])]
                pl["corrida"]["ordens"]["agressividade"] = rng.randint(-2, 2)
            sess["planos"].setdefault(ev["id"], {})[p["id"]] = pl


class TestOrdens(unittest.TestCase):
    def setUp(self):
        self.st = nova_liga()
        self.pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.pasta)

    def _ordens(self, jid="ana", senha="a1", faz=None, st=None):
        dist = mp.versao_jogadores(st or self.st)
        sj = mp.entrar(dist, jid, senha)
        if faz:
            faz(sj)
        return sj, mp.ordens_da_sessao(sj)

    def test_ida_e_volta_identica(self):
        """O que o comissário guarda é byte a byte o que o jogador exportou; o checksum confere de novo."""
        sj, o = self._ordens(faz=lambda s: jogada_aleatoria(s, random.Random(1)))
        caminho = mp.salvar_ordens(sj, os.path.join(self.pasta, "o.json"))
        lido = mp.ler_ordens(caminho)
        self.assertEqual(lido, o)
        mp.importar_ordens(self.st, lido)
        guardado = self.st["multiplayer"]["recebidas"]["ana"]
        self.assertEqual(mp._canonico(guardado), mp._canonico(o))
        corpo = {k: v for k, v in guardado.items() if k not in ("checksum", "assinatura")}
        self.assertEqual(mp._hash(corpo), guardado["checksum"])

    def test_estado_do_comissario_igual_ao_do_jogador(self):
        """Depois de aplicar as ordens, a equipe no jogo do comissário fica igual à que o jogador viu."""
        rng = random.Random(7)

        def faz(s):
            acoes.executar(s, "emprestimo", valor=1000000, prazo=None)
            jogada_aleatoria(s, rng)
        sj, o = self._ordens(faz=faz)
        mp.importar_ordens(self.st, o)
        copia = copy.deepcopy(self.st)
        with acoes.como(copia, CID, "tucano"):
            for a in o["acoes"]:
                self.assertIsNone(acoes.aplicar(copia, a["acao"], a))
        self.assertEqual(mp.impressao_equipe(copia, CID, "tucano"), mp.impressao_equipe(sj, CID, "tucano"))
        self.assertEqual(copia["categorias"][CID]["equipes"]["tucano"], sj["categorias"][CID]["equipes"]["tucano"])

    def test_so_o_necessario(self):
        sj, o = self._ordens(faz=lambda s: jogada_aleatoria(s, random.Random(2)))
        self.assertEqual(set(o), set(mp.CAMPOS_ORDENS))
        txt = json.dumps(o)
        for proibido in ("categorias", "pilotos\":", "noticias", "temporadas", "_chave", "verificador"):
            self.assertNotIn(proibido, txt)
        for a in o["acoes"]:
            self.assertIn(a["acao"], ("proposta_piloto", "rescindir_piloto", "contratar_parte", "rescindir_parte",
                                      "patrocinio", "emprestimo", "quitar_emprestimo", "dev_modo", "dev_investir"))
        meus = {p["id"] for p in state.pilotos_da_equipe(sj, CID, "tucano")}
        for ev_id, por_piloto in o["planos"].items():
            ev = next(e for e in sj["categorias"][CID]["calendario"] if e["id"] == ev_id)
            self.assertEqual(ev["semana"], sj["semana"])
            self.assertLessEqual(set(por_piloto), meus)

    def test_planos_de_outros_eventos_e_pilotos_descartados(self):
        def faz(s):
            sess = mp.sessao(s)
            outro = next(e for e in s["categorias"][CID]["calendario"] if e["semana"] > s["semana"] + 3)
            sess["planos"][outro["id"]] = {"x": planos_evento.plano_padrao()}
            sess["planos"]["inexistente"] = {"y": {}}
        _, o = self._ordens(faz=faz)
        self.assertEqual(o["planos"], {})

    def _recusa(self, o, msg=None):
        with self.assertRaises(mp.ErroLiga) as ctx:
            mp.importar_ordens(self.st, o)
        if msg:
            self.assertIn(msg, str(ctx.exception))

    def test_recusas(self):
        _, o = self._ordens(faz=lambda s: acoes.executar(s, "emprestimo", valor=1000000, prazo=None))
        a = copy.deepcopy(o); a["extra"] = 1; self._recusa(a, "formato")
        a = copy.deepcopy(o); del a["planos"]; self._recusa(a, "formato")
        a = copy.deepcopy(o); a["versao"] = 1; self._recusa(a, "formato")
        a = copy.deepcopy(o); a["checksum"] = "0" * 64; self._recusa(a, "Checksum")
        a = copy.deepcopy(o); a["acoes"][0]["valor"] = 9e9; self._recusa(a, "Checksum")
        # alterado e com checksum recalculado: a assinatura (que depende da senha) ainda pega
        a = copy.deepcopy(o); a["acoes"][0]["valor"] = 9e9
        a["checksum"] = mp._hash({k: v for k, v in a.items() if k not in ("checksum", "assinatura")})
        self._recusa(a, "Assinatura")
        a = copy.deepcopy(o); a["resultado_esperado"] = "f" * 64
        a["checksum"] = mp._hash({k: v for k, v in a.items() if k not in ("checksum", "assinatura")})
        self._recusa(a, "Assinatura")
        mp.importar_ordens(self.st, o)                # a original continua válida

    def test_arquivo_da_liga_antigo_nao_reproduz(self):
        """Jogador usou um arquivo da liga de outra situação (caixa diferente): o resultado não bate."""
        velho = copy.deepcopy(self.st)
        velho["categorias"][CID]["equipes"]["tucano"]["financas"]["caixa"] += 5e6
        _, o = self._ordens(st=velho, faz=lambda s: acoes.executar(s, "emprestimo", valor=1000000, prazo=None))
        self._recusa(o, "não reproduzem")

    def test_checksum_do_arquivo_da_liga(self):
        caminho = mp.exportar_para_jogadores(self.st, os.path.join(self.pasta, "jog.json"))
        st2 = mp.carregar_liga(caminho)
        self.assertEqual(st2["multiplayer"]["papel"], "jogador")
        with open(caminho, encoding="utf-8") as f:
            d = json.load(f)
        d["categorias"][CID]["equipes"]["tucano"]["financas"]["caixa"] += 1
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(d, f)
        with self.assertRaises(mp.ErroLiga):
            mp.carregar_liga(caminho)

    def test_arquivo_da_liga_sem_segredos(self):
        caminho = mp.exportar_para_jogadores(self.st, os.path.join(self.pasta, "jog.json"))
        with open(caminho, encoding="utf-8") as f:
            txt = f.read()
        self.assertNotIn("\"chave\"", txt)
        self.assertNotIn("\"recebidas\"", txt)


class TestMultiTemporada(unittest.TestCase):
    """Três jogadores, ações e planos aleatórios toda semana, tudo passando por arquivos em disco."""

    def test_duas_temporadas_por_arquivos(self):
        rng = random.Random(2026)
        pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, pasta)
        st = nova_liga()
        liga = mp.salvar_liga(st, os.path.join(pasta, "comissario.json"))
        ano0 = st["ano"]
        semanas = importadas = 0
        while st["ano"] < ano0 + 2:
            st = mp.carregar_liga(liga)
            dist = mp.exportar_para_jogadores(st, os.path.join(pasta, "liga_jogadores.json"))
            for jid, _, senha in JOGADORES:
                if rng.random() < 0.1:
                    continue                                       # às vezes alguém não manda (política: IA)
                sj = mp.entrar(mp.carregar_liga(dist), jid, senha)
                jogada_aleatoria(sj, rng)
                arq = mp.salvar_ordens(sj, os.path.join(pasta, f"{jid}.json"))
                self.assertEqual(mp.importar_ordens(st, mp.ler_ordens(arq)), jid)
                importadas += 1
            r = mp.rodar_semana(st, random.Random(rng.random()))
            self.assertEqual(r["erros"], [], f"semana {st['semana']}/{st['ano']}")
            mp.salvar_liga(st, liga)
            semanas += 1
            self._invariantes(st)
        self.assertGreater(semanas, 100)
        self.assertGreater(importadas, 250)
        anos = {int(c["ano"]) for c in campeonato.campeoes(st)}
        self.assertLessEqual({ano0, ano0 + 1}, anos)

    def _invariantes(self, st):
        c = st["categorias"][CID]
        for eq in c["equipes"].values():
            for k, v in eq["financas"].items():
                if isinstance(v, (int, float)):
                    self.assertTrue(math.isfinite(v), (eq["id"], k))
        # nenhum piloto em dois lugares; nenhuma equipe acima das vagas
        for cid, cc in st["categorias"].items():
            regras = cc["categoria"]["regras"]
            for eq in cc["equipes"].values():
                if not eq.get("ativa"):
                    continue
                pil = state.pilotos_da_equipe(st, cid, eq["id"])
                principais = [p for p in pil if p["contrato"]["situacao"] == "principal"]
                # titular lesionado mantém o contrato; quem o substitui tem 'substituto_de' (sai quando ele voltar)
                lesionados = [p for p in principais if p.get("lesao")]
                ativos = [p for p in principais if not p.get("lesao")]
                self.assertLessEqual(len(ativos), regras["pilotos_principais_por_equipe"], eq["id"])
                substitutos = [p for p in ativos if p["contrato"].get("substituto_de")]
                self.assertLessEqual(len(principais) - len(substitutos), regras["pilotos_principais_por_equipe"],
                                     (eq["id"], [p["nome"] for p in principais]))
                self.assertLessEqual(len(substitutos), len(lesionados) + 0, eq["id"])
        for j in st["multiplayer"]["jogadores"].values():
            self.assertTrue(c["equipes"][j["equipe"]].get("ativa") or j.get("eliminado"))


if __name__ == "__main__":
    unittest.main()
