"""Busca imagens na Wikipedia (em inglês) para pilotos, equipes (logotipo) e pistas.

Usa a imagem principal do artigo (a do quadro de informações). Para chassis e motores, o importador usa o artigo
da marca (construtor / fabricante do motor), cuja imagem principal costuma ser o logotipo. Para equipes e pistas sem imagem
principal, procura no artigo um arquivo com 'logo' (equipes) ou com 'layout'/'map'/'track' (pistas).
As imagens são salvas em database/imagens (veja automanager/imagens.py) e reaproveitadas: um arquivo
que já existe não é baixado de novo.
"""
import re
import time
import urllib.error
import urllib.request

from .. import imagens
from .wikipedia import _get, AGENTE, ErroImportacao, _esperar

TAMANHO = 400
PALAVRAS = {"equipe": r"logo", "chassis": r"logo", "motor": r"logo", "pista": r"layout|map|track|circuit|course"}
EXCLUIR = r"flag|icon|commons-logo|wiki|symbol|question|edit|helmet|signature|loudspeaker"


def _resolver(d, titulos):
    """Mapa título pedido -> título final (normalizações e redirecionamentos)."""
    q = d.get("query", {})
    mapa = {t: t for t in titulos}
    for lista in (q.get("normalized", []), q.get("redirects", [])):
        for x in lista:
            for t, atual in mapa.items():
                if atual == x["from"]:
                    mapa[t] = x["to"]
    return mapa


def urls_principais(titulos):
    """{título pedido: url da miniatura} para os artigos que têm imagem principal."""
    out = {}
    titulos = [t for t in dict.fromkeys(titulos) if t]
    for i in range(0, len(titulos), 40):
        lote = titulos[i:i + 40]
        d = _get({"action": "query", "prop": "pageimages", "piprop": "thumbnail", "pithumbsize": TAMANHO,
                  "redirects": "1", "titles": "|".join(lote)})
        paginas = {p.get("title"): p for p in d.get("query", {}).get("pages", [])}
        for t, final in _resolver(d, lote).items():
            url = (paginas.get(final) or {}).get("thumbnail", {}).get("source")
            if url:
                out[t] = url
    return out


def url_alternativa(titulo, tipo):
    """Procura entre os arquivos do artigo um logotipo (equipe) ou traçado (pista)."""
    if tipo not in PALAVRAS:
        return None
    d = _get({"action": "query", "prop": "images", "imlimit": "100", "redirects": "1", "titles": titulo})
    arquivos = [im["title"] for p in d.get("query", {}).get("pages", []) for im in p.get("images", [])]
    candidatos = [a for a in arquivos if re.search(PALAVRAS[tipo], a, re.I) and not re.search(EXCLUIR, a, re.I)]
    if not candidatos:
        return None
    d = _get({"action": "query", "prop": "imageinfo", "iiprop": "url", "iiurlwidth": TAMANHO,
              "titles": candidatos[0]})
    for p in d.get("query", {}).get("pages", []):
        for info in p.get("imageinfo", []):
            return info.get("thumburl") or info.get("url")
    return None


def baixar(url, tentativas=4, timeout=30):
    for n in range(tentativas):
        req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and n < tentativas - 1:
                _esperar(e.headers.get("Retry-After"), n)
                continue
            raise ErroImportacao(f"Falha ao baixar a imagem: {e}") from e
        except OSError as e:
            raise ErroImportacao(f"Falha ao baixar a imagem (verifique a internet): {e}") from e
    raise ErroImportacao("A Wikipedia pediu para esperar (muitas requisições).")


def buscar_bandeiras(lista_paises, progresso=None, cancelado=lambda: False, pausa=0.1):
    """Baixa as bandeiras que faltam (países em português ou inglês). Retorna (obtidas, avisos)."""
    from .. import paises
    faltam = {}
    for p in lista_paises:
        if p and not imagens.bandeira(p):
            faltam.setdefault(paises.chave(p), paises.em_portugues(p))
    avisos, obtidas = [], 0
    if not faltam:
        return 0, avisos
    arquivos = {k: "File:" + paises.arquivo_wikimedia(pt) for k, pt in faltam.items()}
    urls = {}
    lista = list(arquivos.items())
    for i in range(0, len(lista), 40):
        lote = lista[i:i + 40]
        d = _get({"action": "query", "prop": "imageinfo", "iiprop": "url", "iiurlwidth": 120,
                  "titles": "|".join(t for _, t in lote)})
        mapa = _resolver(d, [t for _, t in lote])
        info = {p.get("title"): (p.get("imageinfo") or [{}])[0] for p in d.get("query", {}).get("pages", [])}
        for k, t in lote:
            ii = info.get(mapa[t]) or {}
            if ii.get("thumburl") or ii.get("url"):
                urls[k] = ii.get("thumburl") or ii.get("url")
    for n, (k, pt) in enumerate(faltam.items(), 1):
        if cancelado():
            break
        if progresso:
            progresso(n - 1, len(faltam), f"Bandeira: {pt}")
        if k not in urls:
            avisos.append(f"Bandeira não encontrada: {pt}")
            continue
        try:
            imagens.salvar_bytes(baixar(urls[k]), f"bandeiras/{k}.png", imagens.LADO_BANDEIRA)
            obtidas += 1
            time.sleep(pausa)
        except (ErroImportacao, ValueError, OSError) as e:
            avisos.append(f"Bandeira de {pt}: {e}")
    return obtidas, avisos


def paises_do_arquivo(dados):
    out = set()
    for k in ("pilotos", "equipes", "chassis", "motores", "patrocinadores"):
        out.update(x.get("nacionalidade") or x.get("pais") for x in dados.get(k, [])
                   if x.get("nacionalidade") or x.get("pais"))
    from ..paises import do_local
    out.update(do_local(e.get("local")) for e in dados.get("calendario", []) if e.get("local"))
    return out


def buscar(tipo, titulo, substituir=False):
    """Baixa a imagem de um artigo. Retorna o caminho relativo salvo ou None se o artigo não tiver imagem."""
    rel = imagens.nome_arquivo(tipo, titulo)
    if imagens.existe(rel) and not substituir:
        return rel
    url = urls_principais([titulo]).get(titulo) or url_alternativa(titulo, tipo)
    if not url:
        return None
    try:
        return imagens.salvar_bytes(baixar(url), rel)
    except ValueError as e:
        raise ErroImportacao(str(e)) from e


def buscar_todas(dados, progresso=None, cancelado=lambda: False, pausa=0.2):
    """Busca as imagens de todos os pilotos, equipes e pistas de um arquivo de database que tenham o campo
    'wikipedia' (título do artigo) e ainda não tenham imagem. Grava os caminhos nos próprios registros.
    progresso(feitos, total, texto). Retorna (quantidade obtida, lista de avisos)."""
    itens = [("piloto", x) for x in dados.get("pilotos", [])] + \
            [("equipe", x) for x in dados.get("equipes", [])] + \
            [("pista", x) for x in dados.get("calendario", [])] + \
            [("chassis", x) for x in dados.get("chassis", [])] + \
            [("motor", x) for x in dados.get("motores", [])]
    itens = [(t, x) for t, x in itens if x.get("wikipedia") and not imagens.existe(x.get(imagens.campo(t)))]
    avisos, obtidas = [], 0
    if not itens:
        return 0, avisos
    if progresso:
        progresso(0, len(itens), "Consultando os artigos...")
    principais = {}
    for tipo in ("piloto", "equipe", "pista", "chassis", "motor"):
        principais.update({(tipo, k): v for k, v in
                           urls_principais([x["wikipedia"] for t, x in itens if t == tipo]).items()})
    for n, (tipo, x) in enumerate(itens, 1):
        if cancelado():
            avisos.append("Busca de imagens interrompida.")
            break
        if progresso:
            progresso(n - 1, len(itens), f"{x.get('nome', x['wikipedia'])}")
        rel = imagens.nome_arquivo(tipo, x["wikipedia"])
        try:
            if not imagens.existe(rel):
                url = principais.get((tipo, x["wikipedia"])) or url_alternativa(x["wikipedia"], tipo)
                if not url:
                    avisos.append(f"Sem imagem no artigo '{x['wikipedia']}' ({x.get('nome', '')}).")
                    continue
                imagens.salvar_bytes(baixar(url), rel)
                time.sleep(pausa)
            x[imagens.campo(tipo)] = rel
            obtidas += 1
        except (ErroImportacao, ValueError, OSError) as e:
            avisos.append(f"{x.get('nome', x['wikipedia'])}: {e}")
            if "esperar" in str(e):
                break
    if progresso:
        progresso(len(itens), len(itens), "Concluído.")
    return obtidas, avisos
