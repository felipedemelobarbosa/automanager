"""Imagens do jogo: fotos de pilotos, logotipos de equipes e pistas.

Ficam em database/imagens/<pilotos|equipes|pistas>/<arquivo>.png. No JSON, o campo guarda o caminho
relativo a database/imagens:
  piloto     "imagem":   "pilotos/max_verstappen.png"
  equipe     "logotipo": "equipes/mclaren.png"
  calendário "imagem":   "pistas/circuit_de_monaco.png"
  chassis    "logotipo": "chassis/mclaren_mcl60.png"
  motor      "logotipo": "motores/honda.png"
Bandeiras: database/imagens/bandeiras/<país em português, sem acentos>.png (ex.: brasil.png), achadas pela
nacionalidade – não precisam de campo no JSON.
O jogo só lê arquivos locais. A busca na Wikipedia é feita no editor (automanager/editor/imagens_wiki.py).
Usa a biblioteca Pillow (pip install pillow) para ler JPG e redimensionar; sem ela, só PNG/GIF sem redimensionar.
"""
import io
import os
import re
import unicodedata

from .util import PASTA_DATABASE

PASTA_IMAGENS = os.path.join(PASTA_DATABASE, "imagens")
TIPOS = {"piloto": ("pilotos", "imagem"), "equipe": ("equipes", "logotipo"), "pista": ("pistas", "imagem"),
         "chassis": ("chassis", "logotipo"), "motor": ("motores", "logotipo")}
LADO_BANDEIRA = 64                         # bandeiras: database/imagens/bandeiras/<país>.png (já vêm no jogo)
LADO_MAXIMO = 480                         # maior lado salvo em disco

try:
    from PIL import Image
    TEM_PILLOW = True
except ImportError:                          # pragma: no cover
    TEM_PILLOW = False

_CACHE = {}


def campo(tipo):
    """Nome do campo no JSON para o tipo ('piloto', 'equipe' ou 'pista')."""
    return TIPOS[tipo][1]


def nome_arquivo(tipo, titulo):
    s = unicodedata.normalize("NFKD", titulo or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_") or "sem_nome"
    return f"{TIPOS[tipo][0]}/{s[:80]}.png"


def caminho_absoluto(rel):
    return os.path.join(PASTA_IMAGENS, *str(rel).replace("\\", "/").split("/"))


def existe(rel):
    return bool(rel) and os.path.isfile(caminho_absoluto(rel))


def bandeira(pais):
    """Caminho relativo da bandeira do país (português ou inglês) ou None se não houver arquivo."""
    from . import paises
    if not pais:
        return None
    rel = f"bandeiras/{paises.chave(pais)}.png"
    return rel if existe(rel) else None


def salvar_bytes(dados, rel, lado=LADO_MAXIMO):
    """Converte para PNG (com Pillow) e grava. Retorna o caminho relativo ou levanta ValueError."""
    destino = caminho_absoluto(rel)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    if TEM_PILLOW:
        img = Image.open(io.BytesIO(dados))
        img.load()
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        img.thumbnail((lado, lado))
        img.save(destino, "PNG")
    else:
        if not dados.startswith(b"\x89PNG"):
            raise ValueError("imagem não é PNG e a biblioteca Pillow não está instalada (pip install pillow)")
        with open(destino, "wb") as f:
            f.write(dados)
    _CACHE.clear()
    return rel


def foto(rel, largura, altura):
    """PhotoImage da imagem ajustada à caixa largura x altura (mantém a proporção) ou None."""
    if not existe(rel):
        return None
    arq = caminho_absoluto(rel)
    chave = (arq, largura, altura, os.path.getmtime(arq))
    if chave in _CACHE:
        return _CACHE[chave]
    try:
        import base64
        import tkinter as tk
        if TEM_PILLOW:                      # redimensiona e entrega ao Tk como PNG (não depende de ImageTk)
            img = Image.open(arq)
            img.load()
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")
            img.thumbnail((largura, altura))
            buf = io.BytesIO()
            img.save(buf, "PNG")
            ph = tk.PhotoImage(data=base64.b64encode(buf.getvalue()))
        else:
            ph = tk.PhotoImage(file=arq)
            f = max(1, -(-ph.width() // largura), -(-ph.height() // altura))
            if f > 1:
                ph = ph.subsample(f, f)
    except Exception:                        # arquivo corrompido ou formato não suportado
        return None
    _CACHE[chave] = ph
    return ph


# ---------------------------------------------------------------- imagens de uma pasta local
EXTENSOES = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
PASTAS_TIPO = {"pilotos": "piloto", "equipes": "equipe", "chassis": "chassis", "motores": "motor",
               "pistas": "pista", "bandeiras": "bandeira"}
COLECOES = {"piloto": "pilotos", "equipe": "equipes", "chassis": "chassis", "motor": "motores", "pista": "calendario"}


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def importar_arquivo(caminho, tipo, titulo):
    """Copia (convertendo para PNG) um arquivo local para database/imagens. Retorna o caminho relativo."""
    with open(caminho, "rb") as f:
        dados = f.read()
    return salvar_bytes(dados, nome_arquivo(tipo, titulo))


def _nomes(tipo, x):
    nomes = {x.get("nome"), x.get("id"), x.get("wikipedia")}
    if tipo == "pista":
        local = x.get("local") or ""
        nomes |= {local, local.split(",")[0]}
    return {_norm(n) for n in nomes if n}


def importar_pasta(dados, pasta):
    """Associa as imagens de uma pasta aos registros pelo nome do arquivo (sem extensão, sem diferenciar
    acentos e maiúsculas): nome, ID ou artigo da Wikipedia; nas pistas também o local. Subpastas pilotos/,
    equipes/, chassis/, motores/, pistas/ e bandeiras/ limitam o tipo; arquivos soltos valem para todos.
    Bandeiras: arquivo com o nome do país (português ou inglês). Retorna (associações, arquivos sem par)."""
    from . import paises
    feitos, sem_par = [], []
    for raiz, _dirs, arquivos in os.walk(pasta):
        sub = os.path.basename(raiz).lower() if os.path.abspath(raiz) != os.path.abspath(pasta) else None
        tipos = [PASTAS_TIPO[sub]] if sub in PASTAS_TIPO else list(COLECOES) + ["bandeira"]
        for arq in sorted(arquivos):
            base, ext = os.path.splitext(arq)
            if ext.lower() not in EXTENSOES:
                continue
            chave = _norm(base)
            caminho = os.path.join(raiz, arq)
            achou = False
            try:
                for tipo in tipos:
                    if tipo == "bandeira":
                        continue
                    for x in dados.get(COLECOES[tipo], []):
                        if chave in _nomes(tipo, x):
                            x[campo(tipo)] = importar_arquivo(caminho, tipo, x.get("wikipedia") or x.get("nome")
                                                              or x.get("id"))
                            feitos.append(f"{arq} → {x.get('nome', x.get('id'))} ({tipo})")
                            achou = True
                if not achou and "bandeira" in tipos:
                    pt = paises.em_portugues(base)
                    if pt in paises.PT_PARA_EN or sub == "bandeiras":
                        with open(caminho, "rb") as f:
                            salvar_bytes(f.read(), f"bandeiras/{paises.chave(pt)}.png", LADO_BANDEIRA)
                        feitos.append(f"{arq} → bandeira de {pt}")
                        achou = True
            except (OSError, ValueError) as e:
                sem_par.append(f"{arq}: não foi possível ler ({e})")
                continue
            if not achou:
                sem_par.append(arq)
    return feitos, sem_par
