"""Pasta compartilhada da liga, caixa de entrada do comissário (prazo, histórico, importação em lote) e o núcleo do
bot do Discord – sem Discord: o bot é testado pelas mesmas funções que o conector chama."""
import copy
import json
import os
import random
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import db, state, multiplayer as mp, caixa_liga as caixa, bot_discord  # noqa: E402

ALFA = "formula_alfa"


def liga():
    st = state.novo_jogo(db.arquivos_do_ano(2026), semente=4)
    mp.criar_liga(st, "Liga Teste", [{"nome": "Ana", "categoria": ALFA, "equipe": "tucano", "senha": "a"},
                                     {"nome": "Bia", "categoria": ALFA, "equipe": "vortex", "senha": "b"}])
    return st


class Base(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.pasta)
        self.st = liga()
        self.ids = {j["nome"]: jid for jid, j in self.st["multiplayer"]["jogadores"].items()}
        caixa.publicar(self.st, self.pasta)

    def jogador(self, nome, senha):
        st_liga = mp.carregar_liga(os.path.join(self.pasta, caixa.LIGA))
        return mp.entrar(st_liga, self.ids[nome], senha)


class TestPastaCompartilhada(Base):
    def test_publicar_entregar_importar(self):
        self.assertTrue(caixa.eh_pasta_da_liga(self.pasta))
        with open(os.path.join(self.pasta, caixa.LIGA), encoding="utf-8") as f:
            publicado = json.load(f)
        for segredo in ("recebidas", "envios", "auto", "pasta_compartilhada"):
            self.assertNotIn(segredo, publicado["multiplayer"])             # nada do comissário vai para a pasta
        self.assertTrue(all("chave" not in j for j in publicado["multiplayer"]["jogadores"].values()))
        self.assertEqual(os.listdir(os.path.join(self.pasta, caixa.PASTA_SEMANAS)),
                         [mp.nome_arquivo(self.st, "liga")])
        ana = self.jogador("Ana", "a")
        caixa.entregar_ordens(ana, self.pasta)
        vistos = {}
        res = caixa.varrer(self.st, self.pasta, vistos)
        self.assertEqual([(j, r) for _, j, r in res], [(self.ids["Ana"], "aceita")])
        self.assertEqual(caixa.varrer(self.st, self.pasta, vistos), [])          # não reprocessa
        caixa.escrever_status(self.st, self.pasta, caixa.recusas_da_semana(self.st))
        s = caixa.ler_status(self.pasta)
        self.assertEqual(s["jogadores"][self.ids["Ana"]]["estado"], "recebidas")
        self.assertEqual(s["jogadores"][self.ids["Bia"]]["estado"], "aguardando")
        self.assertEqual(self.st["multiplayer"]["envios"][-1]["resultado"], "aceita")

    def test_recusa_com_motivo_e_semana_antiga(self):
        bia = self.jogador("Bia", "b")
        ordens = mp.ordens_da_sessao(bia)
        ordens["acoes"].append({"acao": "dev_investir"})                       # arquivo alterado
        caixa._gravar_json(caixa.caminho_ordens(self.pasta, self.ids["Bia"]), ordens)
        res = caixa.varrer(self.st, self.pasta, {})
        self.assertIn("Checksum não confere", res[0][2])
        caixa.escrever_status(self.st, self.pasta, caixa.recusas_da_semana(self.st))
        s = caixa.ler_status(self.pasta)["jogadores"][self.ids["Bia"]]
        self.assertEqual(s["estado"], "recusadas")
        self.assertIn("Checksum", s["motivo"])
        mp.rodar_semana(self.st, random.Random(1))                             # semana seguinte: o arquivo velho
        self.assertEqual(caixa.varrer(self.st, self.pasta, {}), [])            # é ignorado sem aviso

    def test_nova_semana_e_reentrada_sem_senha(self):
        ana = self.jogador("Ana", "a")
        mp.rodar_semana(self.st, random.Random(1))
        caixa.publicar(self.st, self.pasta)
        self.assertEqual(caixa.semana_publicada(self.pasta), (self.st["ano"], self.st["semana"]))
        st_liga = mp.carregar_liga(os.path.join(self.pasta, caixa.LIGA))
        nova = mp.entrar_com_chave(st_liga, self.ids["Ana"], mp.sessao(ana)["_chave"])
        self.assertEqual(nova["semana"], self.st["semana"])
        with self.assertRaises(mp.ErroLiga):
            mp.entrar_com_chave(st_liga, self.ids["Bia"], mp.sessao(ana)["_chave"])


class TestCaixaDeEntrada(Base):
    def test_prazo_atraso_e_rodar_sozinha(self):
        self.assertIsNone(caixa.prazo(self.st))
        with self.assertRaises(ValueError):
            caixa.definir_prazo(self.st, "amanhã")
        caixa.definir_prazo(self.st, "2000-01-01 10:00")                         # já passou
        self.assertTrue(caixa.atrasado(self.st))
        caixa.publicar(self.st, self.pasta)                                       # os jogadores veem o prazo
        self.assertEqual(caixa.prazo(self.jogador("Ana", "a")), "2000-01-01 10:00")
        self.assertIsNone(caixa.deve_rodar_sozinha(self.st))
        self.st["multiplayer"]["auto"] = {"prazo": True}
        self.assertEqual(caixa.deve_rodar_sozinha(self.st), "prazo")
        self.st["multiplayer"]["auto"] = {"todas": True}
        self.assertIsNone(caixa.deve_rodar_sozinha(self.st))
        for nome, senha in (("Ana", "a"), ("Bia", "b")):
            caixa.entregar_ordens(self.jogador(nome, senha), self.pasta)
        res = caixa.varrer(self.st, self.pasta, {})
        self.assertTrue(all(r == "aceita" for _, _, r in res))
        self.assertTrue(all(x["atrasado"] for x in self.st["multiplayer"]["envios"]))
        self.assertEqual(caixa.deve_rodar_sozinha(self.st), "todas")
        mp.rodar_semana(self.st, random.Random(1))
        self.assertIsNone(caixa.prazo(self.st))                                   # o prazo era só daquela semana

    def test_importar_pasta_com_motivos(self):
        lote = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, lote)
        mp.salvar_ordens(self.jogador("Ana", "a"), os.path.join(lote, "ana.json"))
        with open(os.path.join(lote, "lixo.json"), "w") as f:
            f.write("{}")
        res = {os.path.basename(c): r for c, _, r in caixa.importar_pasta(self.st, lote)}
        self.assertEqual(res["ana.json"], "aceita")
        self.assertIn("não é um arquivo de ordens", res["lixo.json"])


class TestNucleoDoBot(Base):
    def bot(self, **cfg):
        return bot_discord.NucleoBot(self.pasta, cfg)

    def test_recebe_ordens_e_status(self):
        b = self.bot(jogadores={self.ids["Bia"]: 222})
        self.assertIsNone(b.arquivo_recebido("foto.png", b"x"))
        self.assertIn("não é um JSON", b.arquivo_recebido("x.json", b"nada"))
        ana = json.dumps(mp.ordens_da_sessao(self.jogador("Ana", "a"))).encode()
        self.assertTrue(b.arquivo_recebido("ana.json", ana, 111).startswith("✅"))
        self.assertTrue(os.path.isfile(caixa.caminho_ordens(self.pasta, self.ids["Ana"])))
        bia = json.dumps(mp.ordens_da_sessao(self.jogador("Bia", "b"))).encode()
        self.assertIn("outro jogador", b.arquivo_recebido("bia.json", bia, 111))      # Bia é o usuário 222
        outra = json.loads(ana)
        outra["liga"] = "outra"
        self.assertIn("outra liga", b.arquivo_recebido("o.json", json.dumps(outra).encode(), 111))
        # o comissário importa sozinho; o !status do bot mostra
        caixa.varrer(self.st, self.pasta, {})
        caixa.escrever_status(self.st, self.pasta, caixa.recusas_da_semana(self.st))
        texto, anexar = b.comando("!status")
        self.assertIn("✅ Ana", texto)
        self.assertIn("⏳ Bia", texto)
        self.assertEqual(b.comando("!liga")[1], True)
        self.assertIsNone(b.comando("bom dia"))

    def test_semana_nova_e_lembrete(self):
        b = self.bot(jogadores={self.ids["Bia"]: 222}, lembrete_horas=12)
        self.assertIsNone(b.semana_nova())                                       # ao ligar, não repete o aviso
        mp.rodar_semana(self.st, random.Random(1))
        caixa.definir_prazo(self.st, "2030-01-10 20:00")
        caixa.publicar(self.st, self.pasta)
        aviso = b.semana_nova()
        self.assertIn(f"Semana {self.st['semana']}/{self.st['ano']}", aviso)
        self.assertIn("Prazo: 2030-01-10 20:00", aviso)
        self.assertIsNone(b.semana_nova())                                       # uma vez só
        self.assertIsNone(b.lembrete("2030-01-09 12:00"))                         # faltam 32 h
        lem = b.lembrete("2030-01-10 10:00")                                      # faltam 10 h
        self.assertIn("<@222>", lem)
        self.assertIn("Ana", lem)
        self.assertIsNone(b.lembrete("2030-01-10 11:00"))                         # uma vez por semana


try:
    import discord  # noqa: F401
except ImportError:
    discord = None


@unittest.skipUnless(discord, "discord.py não instalado (só o bot precisa dele)")
class TestConectorDiscord(Base):
    """O conector de verdade (bot_discord.rodar), com mensagens falsas no lugar do Discord – sem rede."""

    def test_mensagens(self):
        import asyncio
        capturado = {}
        orig = discord.Client.run
        discord.Client.run = lambda self, token: capturado.setdefault("cliente", self)
        os.environ["DISCORD_TOKEN"] = "teste"
        try:
            bot_discord.rodar(self.pasta, {"canal": 999})
        finally:
            discord.Client.run = orig
            os.environ.pop("DISCORD_TOKEN", None)
        cliente = capturado["cliente"]
        respostas = []

        class Anexo:
            def __init__(self, nome, dados):
                self.filename, self._d = nome, dados

            async def read(self):
                return self._d

        class Msg:
            def __init__(self, conteudo="", anexos=(), canal=999):
                self.author = type("U", (), {"id": 111, "bot": False})()
                self.channel = type("C", (), {"id": canal})()
                self.content, self.attachments = conteudo, list(anexos)

            async def reply(self, texto, file=None):
                respostas.append((texto, file))

        ordens = json.dumps(mp.ordens_da_sessao(self.jogador("Ana", "a"))).encode()
        asyncio.run(cliente.on_message(Msg(anexos=[Anexo("ana.json", ordens)])))
        asyncio.run(cliente.on_message(Msg("!liga")))
        asyncio.run(cliente.on_message(Msg("!status", canal=123)))                # outro canal: ignorado
        self.assertTrue(respostas[0][0].startswith("✅"))
        self.assertTrue(os.path.isfile(caixa.caminho_ordens(self.pasta, self.ids["Ana"])))
        self.assertIsInstance(respostas[1][1], discord.File)                      # !liga anexa o arquivo
        respostas[1][1].close()
        self.assertEqual(len(respostas), 2)


if __name__ == "__main__":
    unittest.main()
