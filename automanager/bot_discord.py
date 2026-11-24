"""Bot do Discord da liga multijogador (opcional). Roda no computador do comissário, junto da pasta compartilhada da
liga (veja caixa_liga.py), e faz a ponte com o canal da liga:

  - jogador manda o arquivo de ordens (anexo .json) no canal ou em mensagem privada para o bot: o bot confere
    (formato, liga, jogador, semana) e grava em ordens/ – o jogo do comissário importa sozinho e confere a assinatura;
  - quando o comissário roda a semana, o bot publica no canal o arquivo da liga da semana nova;
  - comandos: !status (quem já mandou), !liga (arquivo da semana), !prazo, !ajuda;
  - lembrete antes do prazo para quem ainda não mandou (menciona quem estiver no mapa jogador -> usuário do Discord).

Uso:  DISCORD_TOKEN=... python -m automanager.bot_discord <pasta compartilhada> [--config bot_discord.json]
Requer:  pip install "discord.py>=2.5"  (só para o bot; o jogo não depende dele). Passo a passo: docs/BOT_DISCORD.md.

Configuração (JSON, opcional): {"canal": <id do canal>, "jogadores": {"<id do jogador na liga>": <id do usuário no
Discord>}, "lembrete_horas": 12, "prefixo": "!", "idioma": "pt"|"en"|"es"}.
"""
import argparse
import asyncio
import json
import os
import time

from . import caixa_liga, i18n

ESTADO = ".bot_discord_estado.json"
PADRAO = {"canal": None, "jogadores": {}, "lembrete_horas": 12, "prefixo": "!", "idioma": "pt"}


def t(texto):
    return i18n.t(texto)


class NucleoBot:
    """Tudo o que o bot decide, sem depender do Discord (testável)."""

    def __init__(self, pasta, config=None):
        self.pasta = pasta
        self.cfg = dict(PADRAO, **(config or {}))
        self.cfg["jogadores"] = {str(k): int(v) for k, v in (self.cfg.get("jogadores") or {}).items()}
        self._estado_arq = os.path.join(pasta, ESTADO)
        self.estado = caixa_liga._ler_json(self._estado_arq) or {}

    def _gravar_estado(self):
        caixa_liga._gravar_json(self._estado_arq, self.estado)

    def status(self):
        return caixa_liga.ler_status(self.pasta)

    # ------------------------------------------------------------------ arquivos recebidos
    def arquivo_recebido(self, nome, conteudo, autor_id=None):
        """Resposta do bot a um anexo, ou None se não for um .json (o bot ignora)."""
        if not nome.lower().endswith(".json"):
            return None
        try:
            dados = json.loads(conteudo.decode("utf-8") if isinstance(conteudo, bytes) else conteudo)
        except (ValueError, UnicodeDecodeError):
            dados = None
        jid = dados.get("jogador") if isinstance(dados, dict) else None
        dono = self.cfg["jogadores"].get(str(jid)) if jid else None
        if dono is not None and autor_id is not None and int(autor_id) != dono:
            return f"❌ {nome}: " + t("estas ordens são de outro jogador da liga.")
        jid, erro = caixa_liga.entregar_bytes(self.pasta, conteudo)
        if erro:
            return f"❌ {nome}: {t(erro)}"
        s = self.status() or {}
        jog = (s.get("jogadores") or {}).get(jid, {})
        texto = "✅ " + t(f"Ordens de {jog.get('nome', jid)} ({jog.get('equipe', '')}) para a semana "
                          f"{s.get('semana')}/{s.get('ano')} recebidas. O comissário confere a assinatura ao importar.")
        if s.get("prazo") and caixa_liga.agora() > s["prazo"]:
            texto += " " + t("(entregues depois do prazo)")
        return texto

    # ------------------------------------------------------------------ textos
    def texto_status(self):
        s = self.status()
        if not s:
            return t("A liga ainda não foi publicada na pasta compartilhada.")
        linhas = [t(f"**Liga {s['nome']}** – semana {s['semana']}/{s['ano']}")
                  + (" · " + t(f"prazo {s['prazo']}") if s.get("prazo") else "")]
        icones = {"recebidas": "✅", "aguardando": "⏳", "recusadas": "❌", "pulado": "⏭", "fora": "🚫"}
        for d in (s.get("jogadores") or {}).values():
            est = d.get("estado")
            linha = f"{icones.get(est, '•')} {d['nome']} ({d.get('equipe', '')})"
            if est == "recebidas":
                linha += " – " + t(f"recebidas {str(d.get('quando', ''))[-5:]}") + \
                    (" " + t("(atrasadas)") if d.get("atrasado") else "")
            elif est == "recusadas":
                linha += " – " + t("recusadas") + f": {t(d.get('motivo', ''))}"
            elif est == "aguardando":
                linha += " – " + t("aguardando")
            linhas.append(linha)
        return "\n".join(linhas)

    def texto_prazo(self):
        s = self.status() or {}
        return t(f"Prazo da semana {s.get('semana')}/{s.get('ano')}: {s['prazo']}") if s.get("prazo") \
            else t("Sem prazo marcado para esta semana.")

    def texto_ajuda(self):
        p = self.cfg["prefixo"]
        return t("Mande o arquivo de ordens (.json) aqui como anexo.") + "\n" + "\n".join(
            f"`{p}{c}` – {t(d)}" for c, d in (("status", "quem já mandou as ordens desta semana"),
                                             ("liga", "arquivo da liga desta semana"),
                                             ("prazo", "prazo de entrega"), ("ajuda", "esta mensagem")))

    def comando(self, texto):
        """('texto', anexar_liga) para um comando, ou None se a mensagem não for comando."""
        p = self.cfg["prefixo"]
        c = (texto or "").strip().lower()
        if not c.startswith(p):
            return None
        c = c[len(p):].split()[0] if c[len(p):].split() else ""
        if c == "status":
            return self.texto_status(), False
        if c == "liga":
            s = self.status()
            return (t(f"Arquivo da liga – semana {s['semana']}/{s['ano']}.") if s else self.texto_status()), bool(s)
        if c == "prazo":
            return self.texto_prazo(), False
        if c in ("ajuda", "help"):
            return self.texto_ajuda(), False
        return None

    # ------------------------------------------------------------------ rotina (a cada minuto)
    def semana_nova(self):
        """Texto do aviso se o comissário publicou uma semana nova desde o último aviso; senão None."""
        s = self.status()
        if not s or not os.path.isfile(os.path.join(self.pasta, caixa_liga.LIGA)):
            return None
        atual = [s["ano"], s["semana"]]
        if self.estado.get("publicada") == atual:
            return None
        primeira = "publicada" not in self.estado
        self.estado["publicada"] = atual
        self._gravar_estado()
        if primeira:
            return None                                  # ao ligar o bot não repete o aviso da semana atual
        texto = "📢 " + t(f"Semana {s['semana']}/{s['ano']} publicada na liga {s['nome']}. Baixe o arquivo da liga "
                          f"(anexo), jogue e mande suas ordens aqui.")
        if s.get("prazo"):
            texto += "\n" + t(f"Prazo: {s['prazo']}")
        return texto

    def lembrete(self, momento=None):
        """Texto do lembrete (uma vez por semana) quando faltam menos de lembrete_horas para o prazo."""
        s = self.status()
        if not s or not s.get("prazo"):
            return None
        chave = f"{s['ano']}-{s['semana']}"
        if self.estado.get("lembrou") == chave:
            return None
        agora = momento or caixa_liga.agora()
        limite = time.mktime(time.strptime(s["prazo"], "%Y-%m-%d %H:%M"))
        falta_h = (limite - time.mktime(time.strptime(agora, "%Y-%m-%d %H:%M"))) / 3600
        if falta_h > float(self.cfg["lembrete_horas"]) or falta_h < 0:
            return None
        faltam = [(jid, d) for jid, d in (s.get("jogadores") or {}).items()
                  if d.get("estado") in ("aguardando", "recusadas")]
        self.estado["lembrou"] = chave
        self._gravar_estado()
        if not faltam:
            return None
        quem = ", ".join(f"<@{self.cfg['jogadores'][jid]}>" if jid in self.cfg["jogadores"] else d["nome"]
                         for jid, d in faltam)
        return "⏰ " + t(f"Faltam ordens de {quem}. Prazo: {s['prazo']}.")


# ---------------------------------------------------------------------- conector do Discord
def rodar(pasta, config):
    try:
        import discord
    except ImportError:
        raise SystemExit("O bot precisa do discord.py:  pip install \"discord.py>=2.5\"")
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Defina a variável de ambiente DISCORD_TOKEN com o token do bot.")
    nucleo = NucleoBot(pasta, config)
    i18n.definir(nucleo.cfg.get("idioma") or "pt")
    intents = discord.Intents.default()
    intents.message_content = True                    # ler os comandos (ative 'Message Content Intent' no portal)
    cliente = discord.Client(intents=intents)
    canal_id = nucleo.cfg.get("canal")

    def arquivo_liga():
        s = nucleo.status() or {}
        return discord.File(os.path.join(pasta, caixa_liga.LIGA),
                            filename=f"liga_{s.get('ano')}_s{int(s.get('semana') or 0):02d}.json")

    async def rotina():
        await cliente.wait_until_ready()
        canal = cliente.get_channel(int(canal_id)) if canal_id else None
        while not cliente.is_closed():
            if canal:
                aviso = nucleo.semana_nova()
                if aviso:
                    await canal.send(aviso, file=arquivo_liga())
                lembrete = nucleo.lembrete()
                if lembrete:
                    await canal.send(lembrete)
            await asyncio.sleep(60)

    @cliente.event
    async def on_ready():
        print(f"Bot conectado como {cliente.user}. Pasta da liga: {pasta}")
        cliente.loop.create_task(rotina())

    @cliente.event
    async def on_message(msg):
        if msg.author == cliente.user or msg.author.bot:
            return
        privado = isinstance(msg.channel, discord.DMChannel)
        if canal_id and not privado and msg.channel.id != int(canal_id):
            return                                      # só o canal da liga e mensagens privadas
        for anexo in msg.attachments:
            resposta = nucleo.arquivo_recebido(anexo.filename, await anexo.read(), msg.author.id)
            if resposta:
                await msg.reply(resposta)
        r = nucleo.comando(msg.content)
        if r:
            texto, anexar = r
            await msg.reply(texto, file=arquivo_liga() if anexar else None)

    cliente.run(token)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Bot do Discord da liga multijogador do AutoManager.")
    ap.add_argument("pasta", help="pasta compartilhada da liga (a que o comissário escolheu no jogo)")
    ap.add_argument("--config", help="arquivo JSON de configuração (canal, jogadores, lembrete_horas, idioma)")
    a = ap.parse_args(argv)
    config = {}
    if a.config:
        with open(a.config, encoding="utf-8") as f:
            config = json.load(f)
    rodar(a.pasta, config)


if __name__ == "__main__":
    main()
