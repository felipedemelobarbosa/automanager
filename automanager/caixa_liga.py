"""Pasta compartilhada da liga multijogador (Google Drive, Dropbox, OneDrive, Syncthing...) e caixa de entrada do
comissário. Usado pelo jogo do comissário, pelo jogo dos jogadores e pelo bot do Discord.

Estrutura da pasta:
  liga.json                arquivo da liga para os jogadores (o da semana atual; o comissário publica a cada semana)
  semanas/<arquivo>.json   cópia de cada semana publicada
  ordens/<jogador>.json    ordens de cada jogador (o jogo dele grava aqui; o bot também)
  status.json              situação publicada pelo comissário: semana, prazo e, por jogador, recebidas / aguardando /
                           rejeitadas (com o motivo)
O arquivo do comissário (com as chaves dos jogadores) NUNCA vai para a pasta compartilhada.
"""
import json
import os
import time

from . import multiplayer as mp

LIGA = "liga.json"
STATUS = "status.json"
PASTA_ORDENS = "ordens"
PASTA_SEMANAS = "semanas"


def agora():
    return time.strftime("%Y-%m-%d %H:%M")


def _gravar_json(caminho, dados):
    os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
    os.replace(tmp, caminho)                      # troca atômica: quem lê nunca vê o arquivo pela metade
    return caminho


def _ler_json(caminho):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def eh_pasta_da_liga(pasta):
    return bool(pasta) and os.path.isfile(os.path.join(pasta, LIGA))


# ---------------------------------------------------------------- prazo e histórico (no estado da liga)
def prazo(st):
    """Prazo de entrega da semana atual ('AAAA-MM-DD HH:MM') ou None. Vale só para a semana em que foi marcado."""
    p = st["multiplayer"].get("prazo") or {}
    return p.get("quando") if (p.get("ano"), p.get("semana")) == (st["ano"], st["semana"]) else None


def definir_prazo(st, quando):
    """quando: 'AAAA-MM-DD HH:MM' ou vazio para tirar. Levanta ValueError se o formato estiver errado."""
    quando = (quando or "").strip()
    if not quando:
        st["multiplayer"].pop("prazo", None)
        return None
    time.strptime(quando, "%Y-%m-%d %H:%M")
    st["multiplayer"]["prazo"] = {"ano": st["ano"], "semana": st["semana"], "quando": quando}
    return quando


def atrasado(st, momento=None):
    p = prazo(st)
    return bool(p) and (momento or agora()) > p


def registrar_envio(st, jid, arquivo, resultado):
    """Histórico da caixa de entrada: quem mandou o quê, quando, e se foi aceito (ou o motivo da recusa)."""
    m = st["multiplayer"]
    m.setdefault("envios", []).append({"ano": st["ano"], "semana": st["semana"], "jogador": jid,
                                       "quando": agora(), "arquivo": os.path.basename(arquivo or ""),
                                       "resultado": resultado, "atrasado": atrasado(st)})
    del m["envios"][:-500]                        # guarda os 500 mais recentes


# ---------------------------------------------------------------- caixa de entrada (qualquer pasta)
def importar_arquivos(st, caminhos):
    """Importa vários arquivos de ordens. [(arquivo, jid ou None, 'aceita' ou motivo da recusa)]."""
    out = []
    for c in caminhos:
        jid = None
        try:
            dados = mp.ler_ordens(c)
            jid = dados.get("jogador")
            jid = mp.importar_ordens(st, dados)
            res = "aceita"
        except mp.ErroLiga as e:
            res = str(e)
        if jid in st["multiplayer"]["jogadores"]:
            registrar_envio(st, jid, c, res)
        out.append((c, jid, res))
    return out


def importar_pasta(st, pasta):
    proprios = {LIGA, STATUS, ".bot_discord_estado.json"}          # arquivos da própria liga: não são ordens
    caminhos = sorted(os.path.join(pasta, n) for n in os.listdir(pasta)
                      if n.lower().endswith(".json") and n not in proprios)
    return importar_arquivos(st, caminhos)


# ---------------------------------------------------------------- pasta compartilhada: comissário
def publicar(st, pasta, recusas=None):
    """Publica a semana atual: liga.json (versão dos jogadores), cópia em semanas/ e status.json."""
    nome = mp.nome_arquivo(st, "liga")
    mp.exportar_para_jogadores(st, os.path.join(pasta, PASTA_SEMANAS, nome))
    mp.exportar_para_jogadores(st, os.path.join(pasta, LIGA))
    os.makedirs(os.path.join(pasta, PASTA_ORDENS), exist_ok=True)
    escrever_status(st, pasta, recusas)
    return os.path.join(pasta, LIGA)


def escrever_status(st, pasta, recusas=None):
    """status.json: o que o jogo dos jogadores e o bot mostram (sem nada secreto)."""
    m = st["multiplayer"]
    recusas = recusas or {}
    jogadores = {}
    for jid, nome, eqn, est in mp.situacao(st):
        rec = (m.get("recebidas") or {}).get(jid)
        ult = next((x for x in reversed(m.get("envios", [])) if x["jogador"] == jid
                    and (x["ano"], x["semana"]) == (st["ano"], st["semana"]) and x["resultado"] == "aceita"), None)
        d = {"nome": nome, "equipe": eqn, "estado": "recebidas" if rec else
             "pulado" if jid in m.get("pular", []) else "fora" if m["jogadores"][jid].get("eliminado") else "aguardando"}
        if ult:
            d["quando"] = ult["quando"]
            d["atrasado"] = ult["atrasado"]
        if not rec and jid in recusas:
            d["estado"] = "recusadas"
            d["motivo"] = recusas[jid]
        jogadores[jid] = d
    return _gravar_json(os.path.join(pasta, STATUS), {
        "liga": m["id"], "nome": m["nome"], "ano": st["ano"], "semana": st["semana"], "prazo": prazo(st),
        "politica": m["politica"], "atualizado_em": agora(), "jogadores": jogadores})


def varrer(st, pasta, vistos):
    """Comissário: importa as ordens novas da pasta compartilhada. `vistos` ({arquivo: (mtime, tamanho)}) evita
    reprocessar o mesmo arquivo. Retorna [(arquivo, jid, resultado)] dos arquivos novos ou alterados; ordens de
    outra semana (antigas) são ignoradas sem aviso."""
    d = os.path.join(pasta, PASTA_ORDENS)
    if not os.path.isdir(d):
        return []
    novos = []
    for n in sorted(os.listdir(d)):
        if not n.lower().endswith(".json") or n.endswith(".tmp"):
            continue
        c = os.path.join(d, n)
        try:
            marca = (os.path.getmtime(c), os.path.getsize(c))
        except OSError:
            continue
        if vistos.get(c) == marca:
            continue
        vistos[c] = marca
        dados = _ler_json(c)
        if isinstance(dados, dict) and (dados.get("ano"), dados.get("semana")) != (st["ano"], st["semana"]):
            continue                                       # ordens de uma semana que já passou
        rec = (st["multiplayer"].get("recebidas") or {}).get((dados or {}).get("jogador"))
        if rec and rec.get("checksum") == (dados or {}).get("checksum"):
            continue                                       # já importadas
        novos.append(c)
    return importar_arquivos(st, novos)


def recusas_da_semana(st):
    """{jid: motivo} da última recusa de cada jogador nesta semana (para o status)."""
    out = {}
    for x in st["multiplayer"].get("envios", []):
        if (x["ano"], x["semana"]) == (st["ano"], st["semana"]):
            if x["resultado"] == "aceita":
                out.pop(x["jogador"], None)
            else:
                out[x["jogador"]] = x["resultado"]
    return out


def deve_rodar_sozinha(st, momento=None):
    """Rodar a semana sem o comissário clicar: com todas as ordens (opção 'todas') ou no prazo (opção 'prazo')."""
    auto = st["multiplayer"].get("auto") or {}
    if auto.get("todas") and not mp.faltando(st):
        return "todas"
    if auto.get("prazo") and atrasado(st, momento):
        ok, _ = mp.pode_rodar(st)
        return "prazo" if ok else None
    return None


# ---------------------------------------------------------------- pasta compartilhada: jogador e bot
def ler_status(pasta):
    return _ler_json(os.path.join(pasta, STATUS))


def semana_publicada(pasta):
    """(ano, semana) do liga.json da pasta, sem carregar o jogo inteiro (pelo status.json); None se não houver."""
    s = ler_status(pasta)
    return (s["ano"], s["semana"]) if s and "ano" in s else None


def caminho_ordens(pasta, jid):
    return os.path.join(pasta, PASTA_ORDENS, f"{jid}.json")


def entregar_ordens(st_jogador, pasta):
    """Jogador: grava as ordens desta semana na pasta compartilhada (substitui as anteriores dele)."""
    jid = mp.sessao(st_jogador)["jogador"]
    return _gravar_json(caminho_ordens(pasta, jid), mp.ordens_da_sessao(st_jogador))


def entregar_bytes(pasta, conteudo):
    """Bot: confere um arquivo de ordens recebido (formato, liga, jogador e semana, pelo status.json) e grava na
    pasta. A assinatura (senha) é conferida pelo comissário ao importar. Retorna (jid, None) ou (None, motivo)."""
    try:
        dados = json.loads(conteudo.decode("utf-8") if isinstance(conteudo, bytes) else conteudo)
    except (ValueError, UnicodeDecodeError):
        return None, "o arquivo não é um JSON válido."
    if not isinstance(dados, dict) or dados.get("formato") != mp.FORMATO_ORDENS:
        return None, "não é um arquivo de ordens do AutoManager."
    s = ler_status(pasta)
    if not s:
        return None, "a liga ainda não foi publicada na pasta compartilhada."
    if dados.get("liga") != s.get("liga"):
        return None, "as ordens são de outra liga."
    jid = dados.get("jogador")
    if jid not in s.get("jogadores", {}):
        return None, "jogador desconhecido nesta liga."
    if (dados.get("ano"), dados.get("semana")) != (s["ano"], s["semana"]):
        return None, f"as ordens são da semana {dados.get('semana')}/{dados.get('ano')}; a liga está na semana " \
                     f"{s['semana']}/{s['ano']}."
    _gravar_json(caminho_ordens(pasta, jid), dados)
    return jid, None
