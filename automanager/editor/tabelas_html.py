"""Extrai tabelas HTML (com rowspan/colspan) usando só a biblioteca padrão.

Cada célula vira texto; quebras de linha (<br>, <li>, <p>, <div>) viram '\\n' para separar
vários itens na mesma célula. Países de ícones de bandeira (span.flagicon) são guardados
numa grade paralela, assim como os links para artigos (texto do link, título do artigo).
"""
from html.parser import HTMLParser
import re

_BLOCOS = {"br", "li", "p", "div"}


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tabelas = []
        self._pilha = []
        self._celula = None
        self._ignorar = 0
        self._titulo = ""
        self._em_titulo = False
        self._buf_titulo = []
        self._flag = 0
        self._flag_lido = False
        self._link = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("h2", "h3", "h4"):
            self._em_titulo, self._buf_titulo = True, []
        if tag == "table":
            self._pilha.append({"classe": a.get("class", ""), "titulo_secao": self._titulo, "linhas": [],
                                "linha": None})
            return
        if not self._pilha:
            return
        t = self._pilha[-1]
        if tag == "tr":
            t["linha"] = []
        elif tag in ("td", "th") and t["linha"] is not None:
            def num(v):
                try:
                    return max(1, int(re.sub(r"\D", "", v or "1") or 1))
                except ValueError:
                    return 1
            self._celula = {"txt": [], "rs": num(a.get("rowspan")), "cs": num(a.get("colspan")), "th": tag == "th",
                            "paises": [], "links": []}
        elif tag in ("sup", "style", "script") or (tag == "span" and "display:none" in (a.get("style") or "")):
            self._ignorar += 1
        elif tag == "span" and (self._flag or "flagicon" in (a.get("class") or "")):
            if not self._flag:
                self._flag_lido = False          # um país por ícone de bandeira
            self._flag += 1
        if self._celula is not None and tag not in ("td", "th"):
            if tag in _BLOCOS:
                self._celula["txt"].append("\n")
            href = a.get("href") or ""
            if tag == "a" and not self._flag and not self._ignorar and href.startswith("/wiki/") \
                    and ":" not in href[6:] and a.get("title"):
                self._link = {"titulo": a["title"], "txt": []}
            if self._flag and tag in ("a", "img") and not self._flag_lido:
                pais = a.get("title") or a.get("alt")
                if pais:
                    self._celula["paises"].append(pais)
                    self._flag_lido = True

    def handle_endtag(self, tag):
        if tag in ("h2", "h3", "h4") and self._em_titulo:
            self._em_titulo = False
            self._titulo = "".join(self._buf_titulo).strip()
        if tag in ("sup", "style", "script") and self._ignorar:
            self._ignorar -= 1
        if tag == "span" and self._flag:
            self._flag -= 1
        if tag == "a" and self._link is not None:
            if self._celula is not None:
                self._celula["links"].append(("".join(self._link["txt"]).strip(), self._link["titulo"]))
            self._link = None
        if not self._pilha:
            return
        t = self._pilha[-1]
        if tag in ("td", "th") and self._celula is not None and t["linha"] is not None:
            c = self._celula
            texto = "".join(c["txt"])
            texto = "\n".join(re.sub(r"[ \t\r\f\v\xa0]+", " ", x).strip() for x in texto.split("\n"))
            texto = re.sub(r"\n+", "\n", texto).strip("\n")
            t["linha"].append((texto, c["rs"], c["cs"], c["th"], "\n".join(c["paises"]), c["links"]))
            self._celula = None
            self._flag = 0
        elif tag == "tr" and t["linha"] is not None:
            t["linhas"].append(t["linha"])
            t["linha"] = None
        elif tag == "table":
            self.tabelas.append(self._pilha.pop())

    def handle_data(self, data):
        if self._em_titulo:
            self._buf_titulo.append(data)
        if self._celula is not None and not self._ignorar:
            self._celula["txt"].append(data)
            if self._link is not None:
                self._link["txt"].append(data)


def extrair_tabelas(html):
    """Retorna lista de {"classe", "secao", "grade": [[texto]], "paises": [[texto]],
    "links": [[[(texto, título do artigo)]]], "cabecalho_linhas": n}."""
    p = _Parser()
    p.feed(html)
    out = []
    for t in p.tabelas:
        grade, paises, links, pendentes = [], [], [], {}
        cab = 0
        for i, linha in enumerate(t["linhas"]):
            nova, nova_p, nova_l, col = [], [], [], 0
            celulas = list(linha)
            while celulas or col in pendentes:
                if col in pendentes:
                    txt, pais, lk, resta = pendentes[col]
                    nova.append(txt)
                    nova_p.append(pais)
                    nova_l.append(lk)
                    if resta <= 1:
                        del pendentes[col]
                    else:
                        pendentes[col] = (txt, pais, lk, resta - 1)
                    col += 1
                    continue
                txt, rs, cs, th, pais, lk = celulas.pop(0)
                for _ in range(cs):
                    nova.append(txt)
                    nova_p.append(pais)
                    nova_l.append(lk)
                    if rs > 1:
                        pendentes[col] = (txt, pais, lk, rs - 1)
                    col += 1
            if linha and all(c[3] for c in linha) and i == cab:
                cab += 1
            grade.append(nova)
            paises.append(nova_p)
            links.append(nova_l)
        out.append({"classe": t["classe"], "secao": t["titulo_secao"], "grade": grade, "paises": paises,
                    "links": links,
                    "cabecalho_linhas": cab})
    return out
