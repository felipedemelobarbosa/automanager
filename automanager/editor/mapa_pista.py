"""Retas e curvas a partir do mapa da pista (Wikipedia ou arquivo do usuário).

1. Obtém o mapa: imagem principal do artigo do circuito na Wikipedia (o SVG é baixado já desenhado em PNG)
   ou um arquivo de imagem do computador. O comprimento oficial vem do quadro do artigo (length_km) ou é
   informado pelo usuário: ele dá a escala (metros por pixel).
2. Reconhece o traçado: pixels escuros/coloridos (cinzas médios e claros – traçados antigos, áreas – ficam de
   fora), fecha tracejados, afina até sobrar a linha mais grossa do desenho (a pista), reduz a um esqueleto de
   1 pixel e procura o laço fechado mais longo que segue reto nos cruzamentos.
   Se o reconhecimento falhar ou errar, o usuário marca o traçado clicando sobre o mapa.
3. Mede o raio de curva ao longo da volta e classifica cada trecho como reta, curva de alta ou de baixa –
   pelo raio (metros) ou pela velocidade estimada de curva (km/h), com limites ajustáveis na categoria.
Requer a biblioteca Pillow.
"""
import io
import math
import re
from collections import deque

from PIL import Image, ImageChops, ImageFilter

from .wikipedia import _get, ErroImportacao
from .imagens_wiki import baixar

PADRAO = {"criterio": "raio", "raio_reta": 400, "raio_baixa": 80, "vel_reta": 250, "vel_baixa": 150,
          "aderencia": 2.0}
VIZ = [(-1, -1), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0)]
ANEL = [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)]
LADO = 900


class ErroMapa(Exception):
    pass


def config(categoria):
    cfg = dict(PADRAO)
    cfg.update({k: v for k, v in ((categoria or {}).get("mapa_pista") or {}).items() if v is not None})
    return cfg


# ------------------------------------------------------------------ obter o mapa
def da_wikipedia(titulo):
    """(imagem PIL, comprimento em km ou None, nome do arquivo) do artigo do circuito."""
    d = _get({"action": "query", "prop": "pageimages|revisions", "piprop": "name", "rvprop": "content",
              "rvslots": "main", "rvsection": "0", "titles": titulo, "redirects": "1"})
    paginas = d.get("query", {}).get("pages", [])
    if not paginas or paginas[0].get("missing"):
        raise ErroMapa(f"Artigo '{titulo}' não encontrado na Wikipedia.")
    p = paginas[0]
    texto = ((p.get("revisions") or [{}])[0].get("slots", {}).get("main", {}).get("content") or "")
    comp = None
    m = re.search(r"\|\s*length_km\s*=\s*([\d.]+)", texto)
    if m:
        comp = float(m.group(1))
    else:
        m = re.search(r"\|\s*length_mi\s*=\s*([\d.]+)", texto)
        if m:
            comp = round(float(m.group(1)) * 1.609344, 3)
    arquivo = p.get("pageimage")
    if not arquivo:
        raise ErroMapa(f"O artigo '{p.get('title', titulo)}' não tem mapa (imagem principal).")
    d = _get({"action": "query", "prop": "imageinfo", "iiprop": "url", "iiurlwidth": 1000,
              "titles": "File:" + arquivo})
    info = ((d.get("query", {}).get("pages") or [{}])[0].get("imageinfo") or [{}])[0]
    url = info.get("thumburl") or info.get("url")
    if not url:
        raise ErroMapa("Não foi possível obter o mapa.")
    try:
        return abrir(baixar(url)), comp, arquivo
    except ErroImportacao as e:
        raise ErroMapa(str(e)) from e


def abrir(dados):
    """Imagem (bytes ou caminho) em RGB sobre fundo branco, com o maior lado <= LADO."""
    im = Image.open(io.BytesIO(dados) if isinstance(dados, bytes) else dados)
    im.load()
    return abrir_imagem(im)


def abrir_imagem(im):
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        fundo = Image.new("RGBA", im.size, (255, 255, 255, 255))
        fundo.alpha_composite(im)
        im = fundo
    im = im.convert("RGB")
    f = LADO / max(im.size)
    if f < 1:
        im = im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS)
    return im


# ------------------------------------------------------------------ reconhecer o traçado
def mascara(im, limiar=150):
    """Tinta do traçado: pixels escuros ou coloridos; cinzas médios/claros (traçados antigos, fundos) ficam de fora."""
    r, g, b = im.split()
    mn = ImageChops.darker(ImageChops.darker(r, g), b)
    mx = ImageChops.lighter(ImageChops.lighter(r, g), b)
    escuro = mn.point(lambda v: 255 if v < limiar else 0)
    cinza = ImageChops.multiply(ImageChops.subtract(mx, mn).point(lambda v: 255 if v < 30 else 0),
                                mn.point(lambda v: 255 if v > 90 else 0))
    return ImageChops.subtract(escuro, cinza)


def componentes(mask):
    w, h = mask.size
    px = mask.load()
    vistos = set()
    comps = []
    for y in range(h):
        for x in range(w):
            if px[x, y] and (x, y) not in vistos:
                comp = []
                q = deque([(x, y)]); vistos.add((x, y))
                while q:
                    cx, cy = q.popleft(); comp.append((cx, cy))
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            nx, ny = cx + dx, cy + dy
                            if 0 <= nx < w and 0 <= ny < h and px[nx, ny] and (nx, ny) not in vistos:
                                vistos.add((nx, ny)); q.append((nx, ny))
                comps.append(comp)
    return comps


def bbox(c):
    xs = [p[0] for p in c]; ys = [p[1] for p in c]
    return min(xs), min(ys), max(xs), max(ys)


def diag(c):
    x0, y0, x1, y1 = bbox(c); return math.hypot(x1 - x0, y1 - y0)

VIZ = [(-1, -1), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0)]


def esqueleto(pts):
    """Zhang-Suen sobre um conjunto de pixels."""
    s = set(pts)
    mudou = True
    while mudou:
        mudou = False
        for passo in (0, 1):
            remover = []
            for (x, y) in s:
                p = [((x + dx, y + dy) in s) for dx, dy in [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)]]
                b = sum(p)
                if b < 2 or b > 6:
                    continue
                a = sum(1 for i in range(8) if not p[i] and p[(i + 1) % 8])
                if a != 1:
                    continue
                p2, p4, p6, p8 = p[0], p[2], p[4], p[6]
                if passo == 0 and (p2 and p4 and p6 or p4 and p6 and p8):
                    continue
                if passo == 1 and (p2 and p4 and p8 or p2 and p6 and p8):
                    continue
                remover.append((x, y))
            if remover:
                mudou = True
                s.difference_update(remover)
    return s


def vizinhos(s, p):
    x, y = p
    return [(x + dx, y + dy) for dx, dy in VIZ if (x + dx, y + dy) in s]


def podar(s):
    """Remove pontas soltas até sobrarem só laços."""
    s = set(s)
    fila = deque(p for p in s if len(vizinhos(s, p)) <= 1)
    while fila:
        p = fila.popleft()
        if p not in s or len(vizinhos(s, p)) > 1:
            continue
        s.discard(p)
        for v in vizinhos(s, p):
            if len(vizinhos(s, v)) <= 1:
                fila.append(v)
    return s


def ramos(s, p):
    """Quantos ramos saem do pixel (transições vazio->cheio ao redor)."""
    x, y = p
    v = [((x + dx, y + dy) in s) for dx, dy in ANEL]
    return sum(1 for i in range(8) if not v[i] and v[(i + 1) % 8])


def grafo(s):
    """Nós = grupos de pixels de junção (3+ ramos, com os vizinhos imediatos); arestas = trechos entre nós,
    ordenados do começo ao fim."""
    junc = {p for p in s if ramos(s, p) >= 3}
    junc |= {v for p in junc for v in vizinhos(s, p)}          # engorda a junção: corta os trechos limpos
    no_de, nos = {}, []
    for p in junc:
        if p in no_de:
            continue
        grupo, q = [], deque([p])
        no_de[p] = len(nos)
        while q:
            c = q.popleft(); grupo.append(c)
            for v in vizinhos(s, c):
                if v in junc and v not in no_de:
                    no_de[v] = len(nos); q.append(v)
        nos.append(grupo)
    resto = s - junc
    arestas = []
    while resto:
        p = next(iter(resto))
        comp, q = {p}, deque([p])
        while q:
            c = q.popleft()
            for v in vizinhos(s, c):
                if v in resto and v not in comp:
                    comp.add(v); q.append(v)
        resto -= comp
        if len(comp) < 3:
            continue
        toques = [(c, no_de[v]) for c in comp for v in vizinhos(s, c) if v in no_de]
        if not toques:                                   # laço sem junção
            ini = min(comp)
            arestas.append((None, None, _anel(comp, ini)))
            continue
        ini, na = toques[0]
        dist, pred = _bfs_pred(comp, ini)
        cands = [(c, n) for c, n in toques if math.hypot(c[0] - ini[0], c[1] - ini[1]) > 3]
        if not cands:                                    # ponta solta
            continue
        fim, nb = max(cands, key=lambda t: dist[t[0]])
        cam = [fim]
        while cam[-1] != ini:
            cam.append(pred[cam[-1]])
        cam.reverse()
        arestas.append((na, nb, [nos[na][0]] + cam + [nos[nb][0]]))
    return nos, arestas


def _bfs_pred(comp, ini):
    dist, pred, q = {ini: 0}, {}, deque([ini])
    while q:
        c = q.popleft()
        for dx, dy in VIZ:
            v = (c[0] + dx, c[1] + dy)
            if v in comp and v not in dist:
                dist[v] = dist[c] + 1; pred[v] = c; q.append(v)
    return dist, pred


def _anel(comp, ini):
    cam, vis, cur = [ini], {ini}, ini
    while True:
        nx = [v for v in ((cur[0] + dx, cur[1] + dy) for dx, dy in VIZ) if v in comp and v not in vis]
        if not nx:
            break
        nx.sort(key=lambda u: abs(u[0] - cur[0]) + abs(u[1] - cur[1]))
        cur = nx[0]; vis.add(cur); cam.append(cur)
    return cam + [ini]


def _dir(cadeia, inicio=True, n=10):
    a = cadeia[0] if inicio else cadeia[-1]
    b = cadeia[min(n, len(cadeia) - 1)] if inicio else cadeia[max(0, len(cadeia) - 1 - n)]
    return math.atan2(b[1] - a[1], b[0] - a[0])     # direção saindo do nó para dentro da aresta


def _comp(c):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(c, c[1:]))


def laco_grafo(s):
    nos, arestas = grafo(s)
    soltos = [a for a in arestas if a[0] is None]
    melhor = max(soltos, key=lambda a: _comp(a[2]))[2] if soltos else []
    ligadas = [a for a in arestas if a[0] is not None]
    por_no = {}
    for i, (a, b, c) in enumerate(ligadas):
        por_no.setdefault(a, []).append((i, True))
        por_no.setdefault(b, []).append((i, False))
    ordem = sorted(range(len(ligadas)), key=lambda i: -_comp(ligadas[i][2]))[:6]
    for i0 in ordem:
        for sentido in (True, False):
            usadas = {i0}
            trilha = list(ligadas[i0][2] if sentido else ligadas[i0][2][::-1])
            no = ligadas[i0][1] if sentido else ligadas[i0][0]
            chegada = _dir(ligadas[i0][2], inicio=not sentido)   # aponta do nó de chegada para trás
            chegada = chegada + math.pi
            fechou = False
            for _ in range(len(ligadas) + 2):
                opcoes = []
                for j, sai_inicio in por_no.get(no, []):
                    if j == i0 and len(usadas) > 1 and (sai_inicio == sentido):
                        opcoes.append((j, sai_inicio))
                    elif j not in usadas:
                        opcoes.append((j, sai_inicio))
                if not opcoes:
                    break
                def giro(o):
                    d = _dir(ligadas[o[0]][2], inicio=o[1])
                    return abs((d - chegada + math.pi) % (2 * math.pi) - math.pi)
                j, sai_inicio = min(opcoes, key=giro)
                if j == i0:
                    fechou = True
                    break
                usadas.add(j)
                c = ligadas[j][2] if sai_inicio else ligadas[j][2][::-1]
                trilha.extend(c[1:])
                no = ligadas[j][1] if sai_inicio else ligadas[j][0]
                chegada = _dir(ligadas[j][2], inicio=not sai_inicio) + math.pi
            if fechou and _comp(trilha) > _comp(melhor):
                melhor = trilha
    return melhor


def laco_busca(s, max_giro=1.3, peso_giro=0.25):
    """Procura, entre as trilhas fechadas do grafo, a mais longa com mudanças de direção suaves nos cruzamentos."""
    nos, arestas = grafo(s)
    soltos = [a for a in arestas if a[0] is None]
    melhor, melhor_nota = (max(soltos, key=lambda a: _comp(a[2]))[2] if soltos else []), 0
    if melhor:
        melhor_nota = _comp(melhor)
    lig = [a for a in arestas if a[0] is not None]
    comp = [_comp(a[2]) for a in lig]
    por_no = {}
    for i, (a, b, c) in enumerate(lig):
        por_no.setdefault(a, []).append((i, True))
        por_no.setdefault(b, []).append((i, False))
    total_ops = [0]

    def chegada(i, sai_inicio):
        return _dir(lig[i][2], inicio=not sai_inicio) + math.pi

    def dfs(i0, s0, no, ch, usadas, trilha, giros):
        nonlocal melhor, melhor_nota
        total_ops[0] += 1
        if total_ops[0] > 20000:
            return
        for j, sai in por_no.get(no, []):
            g = abs((_dir(lig[j][2], inicio=sai) - ch + math.pi) % (2 * math.pi) - math.pi)
            if g > max_giro:
                continue
            if j == i0 and sai == s0:
                L = sum(comp[k] for k in trilha)
                nota = L * (1 - peso_giro * (giros + g))
                if nota > melhor_nota:
                    melhor_nota = nota
                    pts = []
                    for k, sk_ in zip(trilha, sentidos):
                        c = lig[k][2] if sk_ else lig[k][2][::-1]
                        pts.extend(c if not pts else c[1:])
                    melhor = pts
                continue
            if j in usadas:
                continue
            usadas.add(j); trilha.append(j); sentidos.append(sai)
            dfs(i0, s0, lig[j][1] if sai else lig[j][0], chegada(j, sai), usadas, trilha, giros + g)
            usadas.discard(j); trilha.pop(); sentidos.pop()

    for i0 in sorted(range(len(lig)), key=lambda i: -comp[i])[:4]:
        for s0 in (True, False):
            sentidos = [s0]
            total_ops[0] = 0
            dfs(i0, s0, lig[i0][1] if s0 else lig[i0][0], chegada(i0, s0), {i0}, [i0], 0.0)
    return melhor


def tracar(im):
    """Lista de pontos (x, y) do laço da pista na imagem. Levanta ErroMapa se não reconhecer."""
    m = mascara(im).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
    cs0 = componentes(m)
    if not cs0:
        raise ErroMapa("Nenhum traçado encontrado na imagem.")
    nucleos = [max(cs0, key=len)]
    d0 = diag(nucleos[0])
    mk = m
    for _ in range(1, 10):
        mk = mk.filter(ImageFilter.MinFilter(3))
        cs = componentes(mk)
        if not cs:
            break
        c = max(cs, key=len)
        if diag(c) < 0.6 * d0 or len(c) < 0.35 * len(nucleos[-1]):
            break
        nucleos.append(c)
    # a linha mais grossa do desenho (a pista) é a que sobrevive mais à erosão: tenta do nível mais erodido
    # para o menos erodido e fica com o primeiro que forma um laço fechado convincente
    for core in reversed(nucleos[1:] or nucleos):
        sk = podar(esqueleto(core))
        laco = max([laco_busca(sk), laco_grafo(sk)], key=_comp)
        if len(laco) >= 50 and _comp(laco) >= 0.5 * max(im.size):
            return laco
    raise ErroMapa("Não reconheci o traçado neste mapa. Marque-o clicando sobre o mapa.")


# ------------------------------------------------------------------ medir
def reamostrar(pts, n=400):
    """n pontos igualmente espaçados ao longo do laço fechado."""
    pts = list(pts)
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    acum = [0.0]
    for a, b in zip(pts, pts[1:]):
        acum.append(acum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    total = acum[-1]
    out, j = [], 0
    for i in range(n):
        alvo = total * i / n
        while acum[j + 1] < alvo:
            j += 1
        seg = acum[j + 1] - acum[j] or 1.0
        t = (alvo - acum[j]) / seg
        out.append((pts[j][0] + (pts[j + 1][0] - pts[j][0]) * t, pts[j][1] + (pts[j + 1][1] - pts[j][1]) * t))
    return out, total


def suavizar(pts, janela=2, vezes=2):
    n = len(pts)
    for _ in range(vezes):
        pts = [(sum(pts[(i + k) % n][0] for k in range(-janela, janela + 1)) / (2 * janela + 1),
                sum(pts[(i + k) % n][1] for k in range(-janela, janela + 1)) / (2 * janela + 1)) for i in range(n)]
    return pts


def _raio(a, b, c):
    ab, bc, ca = math.dist(a, b), math.dist(b, c), math.dist(c, a)
    area2 = abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
    return float("inf") if area2 < 1e-9 else ab * bc * ca / (2 * area2)


def spline_fechada(pontos, por_trecho=12):
    """Catmull-Rom fechada pelos pontos marcados pelo usuário."""
    n = len(pontos)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = pontos[i - 1], pontos[i], pontos[(i + 1) % n], pontos[(i + 2) % n]
        for k in range(por_trecho):
            t = k / por_trecho
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * p1[d] + (-p0[d] + p2[d]) * t + (2 * p0[d] - 5 * p1[d] + 4 * p2[d] - p3[d]) * t2
                                    + (-p0[d] + 3 * p1[d] - 3 * p2[d] + p3[d]) * t3) for d in (0, 1)))
    return out


def analisar(laco, comprimento_km, cfg, n=400):
    """Classifica a volta. Retorna dict com pontos (para desenhar), raios (m), velocidades (km/h), classes por
    critério e percentuais {"raio": {...}, "velocidade": {...}} em retas/curvas_alta/curvas_baixa."""
    pts, perimetro = reamostrar(laco, n)
    pts = suavizar(pts)
    escala = comprimento_km * 1000.0 / perimetro               # metros por pixel
    # mede o raio com pontos a ~25 m de cada lado: suficiente para não confundir a "escada" de pixels com curva
    passo = max(2, round(25.0 / (comprimento_km * 1000.0 / n)))
    raios = [_raio(pts[i - passo], pts[i], pts[(i + passo) % n]) * escala for i in range(n)]
    # o raio de cada trecho é o menor da vizinhança (o ápice manda na velocidade da curva)
    raios = [min(raios[(i + k) % n] for k in (-1, 0, 1)) for i in range(n)]
    vels = [min(400.0, math.sqrt(cfg["aderencia"] * 9.81 * r) * 3.6) if r != float("inf") else 400.0 for r in raios]

    def classes(valores, reta, baixa):
        return ["reta" if v >= reta else "baixa" if v < baixa else "alta" for v in valores]

    cl = {"raio": classes(raios, cfg["raio_reta"], cfg["raio_baixa"]),
          "velocidade": classes(vels, cfg["vel_reta"], cfg["vel_baixa"])}
    perc = {}
    for crit, cs in cl.items():
        r = {k: 100.0 * cs.count(c) / n for k, c in (("retas", "reta"), ("curvas_alta", "alta"),
                                                       ("curvas_baixa", "baixa"))}
        inteiros = {k: int(v) for k, v in r.items()}
        falta = 100 - sum(inteiros.values())
        for k in sorted(r, key=lambda k: -(r[k] - int(r[k])))[:falta]:
            inteiros[k] += 1
        perc[crit] = inteiros
    return {"pontos": pts, "raios": raios, "velocidades": vels, "classes": cl, "percentuais": perc,
            "escala": escala}
