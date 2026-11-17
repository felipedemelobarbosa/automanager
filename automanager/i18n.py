"""Idiomas do jogo: português (original), inglês e espanhol.

O código e os dados são escritos em português. A tradução acontece na hora de mostrar: tudo o que o Tkinter
exibe (rótulos, botões, menus, tabelas, abas, títulos, caixas de mensagem, diálogos de arquivo, textos
desenhados) passa por t(). Os dicionários ficam em lang/<idioma>.json no formato {"texto em português":
"tradução"}. Mensagens montadas com valores (ex.: "{0} vence o {1}.") são modelos: o texto exibido é
reconhecido pelo modelo e os valores são reaproveitados (e traduzidos também, se houver tradução para eles).

O idioma escolhido fica em config.json, na pasta do jogo.
"""
import json
import os
import re
import string

from .util import PASTA_RECURSOS, PASTA_DADOS

IDIOMAS = {"en": "English", "pt": "Português", "es": "Español"}
PASTA = os.path.join(PASTA_RECURSOS, "lang")
CONFIG = os.path.join(PASTA_DADOS, "config.json")

_atual = "pt"
_exato = {}
_modelos = []          # (prefixo, sufixo, regex, destino, letras_literais)
_cache = {}


def atual():
    return _atual


def ler_config():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def salvar_config(**valores):
    cfg = ler_config()
    cfg.update(valores)
    try:
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def _compilar(origem):
    partes = list(string.Formatter().parse(origem))
    rx, letras, prefixo, sufixo = [], 0, None, ""
    for i, (literal, campo, _spec, _conv) in enumerate(partes):
        rx.append(re.escape(literal))
        letras += len(re.findall(r"[^\W\d_]", literal))
        if prefixo is None:
            prefixo = literal
        sufixo = literal if campo is None else ""
        if campo is not None:
            seguinte = partes[i + 1][0] if i + 1 < len(partes) else ""
            # valor colado numa palavra (ex.: "S{0}", "{0}º", "{0}M"): só números
            colado = (literal and re.search(r"[^\W\d_]$", literal)) or (seguinte and re.match(r"[^\W\d_º°ª]", seguinte)) \
                or (seguinte[:1] in ("º", "ª"))
            rx.append(r"\s*([\d.,:+\-]+)" if colado else r"(.+?)")
    return prefixo or "", sufixo, re.compile("^" + "".join(rx) + "$", re.S), letras


def definir(idioma):
    """Troca o idioma (recarrega o dicionário)."""
    global _atual
    _atual = idioma if idioma in IDIOMAS else "pt"
    _exato.clear()
    _modelos.clear()
    _cache.clear()
    if _atual == "pt":
        return
    try:
        with open(os.path.join(PASTA, f"{_atual}.json"), encoding="utf-8") as f:
            dic = json.load(f)
    except (OSError, ValueError):
        dic = {}
    # textos de várias linhas: cada linha também vale sozinha (mensagens montadas por partes)
    for origem, destino in list(dic.items()):
        if isinstance(destino, str) and "\n" in origem and origem.count("\n") == destino.count("\n"):
            for lo, ld in zip(origem.split("\n"), destino.split("\n")):
                if lo.strip() and lo not in dic and not re.fullmatch(r"\s*\{\d+\}\s*", lo):
                    dic[lo] = ld
    for origem, destino in dic.items():
        if not isinstance(destino, str) or not destino:
            continue
        if re.search(r"(?<!\{)\{\d+\}(?!\})", origem):
            if re.search(r"\{\d+\}\{\d+\}", origem):
                continue                      # valores colados um no outro: impossível separar
            try:
                prefixo, sufixo, rx, letras = _compilar(origem)
            except ValueError:
                continue
            _modelos.append((prefixo, sufixo, rx, destino, letras, len(re.sub(r"\{\d+\}", "", origem))))
        else:
            literal = origem.replace("{{", "{").replace("}}", "}")
            _exato[literal] = destino.replace("{{", "{").replace("}}", "}")
            if literal.strip() and literal.strip() not in _exato:
                _exato[literal.strip()] = destino.replace("{{", "{").replace("}}", "}").strip()
    # mais específicos primeiro
    # mais específicos primeiro; entre os modelos sem texto próprio, os de lista vêm antes ("; " separa mais
    # alto que ", ") para que "{0} −{1}" não engula uma lista inteira
    def _lista(m):
        d = m[3]
        return 0 if d == "{0}; {1}" else 1 if d == "{0}, {1}" else 2
    _modelos.sort(key=lambda m: (-m[4], _lista(m) if m[4] < 3 else 0, -m[5]))


def iniciar():
    definir(ler_config().get("idioma", "pt"))


def t(texto, _nivel=0):
    """Traduz um texto exibido (exato, por modelo ou linha a linha). Sem tradução, devolve o original."""
    if _atual == "pt" or not isinstance(texto, str) or not texto or _nivel > 3:
        return texto
    if texto in _cache:
        return _cache[texto]
    r = _traduzir(texto, _nivel)
    if len(_cache) < 20000:
        _cache[texto] = r
    return r


_PREFIXO = re.compile(r"^\[(V\s*\d+|\d+:\d{2}(?::\d{2})?|\d{4} S\d+)\](\s+)(\S.*)$", re.S)


def _prefixo(p):
    """[V 12] (volta), [0:31:00] (relógio da sessão), [2026 S05] (semana): só a letra muda de idioma."""
    if p.startswith("V"):
        return _exato.get("[V{0}]", "[V{0}]").replace("{0}", p[1:].strip())
    m = re.fullmatch(r"(\d{4}) S(\d+)", p)
    if m:
        return _exato.get("[{0} S{1}]", "[{0} S{1}]").replace("{0}", m.group(1)).replace("{1}", m.group(2))
    return f"[{p}]"


def _equilibrado(g):
    n = 0
    for c in g:
        n += (c == "(") - (c == ")")
        if n < 0:
            return False
    return n == 0


def _traduzir(s, nivel):
    if s in _exato:
        return _exato[s]
    # linhas de log e notícias com volta/relógio/semana na frente: traduz a frase sem o prefixo (assim nenhum
    # modelo genérico como "{0} em {1}" engole o prefixo junto com o começo da frase)
    m = _PREFIXO.match(s)
    if m:
        return _prefixo(m.group(1)) + m.group(2) + t(m.group(3), nivel)
    nucleo = s.strip()
    if not re.search(r"[^\W\d_]", nucleo):
        return s
    if nucleo.endswith(":") and nucleo[:-1].rstrip() in _exato:
        # rótulo de campo: "Caixa inicial (USD):" usa a chave sem os dois pontos
        ini = s[:len(s) - len(s.lstrip())]
        fim = s[len(s.rstrip()):]
        return ini + _exato[nucleo[:-1].rstrip()].rstrip(":") + ":" + fim
    if nucleo != s and nucleo in _exato:
        ini = s[:len(s) - len(s.lstrip())]
        fim = s[len(s.rstrip()):]
        return ini + _exato[nucleo] + fim
    tentou_miolo = False
    for prefixo, sufixo, rx, destino, letras, _tam in _modelos:
        if letras < 3 and "\n" in s:
            continue                          # modelos genéricos não atravessam linhas (vale a tradução por linha)
        if letras < 3 and nucleo != s and not tentou_miolo:
            # antes dos modelos genéricos, a frase sem os espaços em volta (" Chassis – ... progressivo ")
            tentou_miolo = True
            r = t(nucleo, nivel)
            if r != nucleo:
                return s[:len(s) - len(s.lstrip())] + r + s[len(s.rstrip()):]
        if not s.startswith(prefixo) or not s.endswith(sufixo):
            continue
        m = rx.match(s)
        if not m or not all(_equilibrado(g) for g in m.groups()):
            continue                          # um valor com parênteses desencontrados é um corte errado da frase
        sep = destino[3:-3] if destino.startswith("{0}") and destino.endswith("{1}") else None
        if sep in (", ", "; ") and not prefixo and not sufixo and sep in s:
            # listas ("Físico −5, Concentração −4, Condução −2"): cada item no mesmo nível, sem aninhar um
            # nível por vírgula (o limite de profundidade cortaria o fim das listas longas)
            r = sep.join(t(x, nivel + 1) for x in s.split(sep))
            if r != s:
                return r
            continue
        trad = [t(g, nivel + 1) for g in m.groups()]
        try:
            r = destino.format(*trad)
        except (IndexError, KeyError, ValueError):
            continue
        # modelos quase sem texto próprio ("{0} · {1}") só valem se mudarem alguma coisa
        if letras < 3 and r == s:
            continue
        return r
    if nucleo != s and "\n" not in nucleo:
        # espaços em volta (" Título do grupo "): nenhum modelo com os espaços serviu, traduz o miolo
        r = t(nucleo, nivel)
        if r != nucleo:
            return s[:len(s) - len(s.lstrip())] + r + s[len(s.rstrip()):]
    if "\n" in s:
        # várias linhas: uma a uma (antes de tirar a pontuação em volta, que cortaria o ponto final da última)
        r = "\n".join(t(linha, nivel) for linha in s.split("\n"))
        if r != s:
            return r
    # símbolos/pontuação em volta: "✓ Treino livre", "Idade:", "(nenhum)"
    m = re.match(r"^([\W\d_]*?)([^\W\d_].*?[^\W\d_.]?)([\W_]*)$", s, re.S)
    if m and (m.group(1) or m.group(3)) and m.group(2) != s:
        meio = t(m.group(2), nivel + 1)
        if meio != m.group(2):
            return m.group(1) + meio + m.group(3)
    if "\n" in s:
        return "\n".join(t(linha, nivel) for linha in s.split("\n"))
    return s


# ---------------------------------------------------------------- ganchos no Tkinter
def _traduz_opcoes(d, chaves=("text", "label", "title")):
    if isinstance(d, dict):
        for k in chaves:
            if isinstance(d.get(k), str):
                d[k] = t(d[k])
    return d


def instalar():
    """Faz o Tkinter traduzir tudo o que exibe. Chamar uma vez, antes de criar janelas."""
    import tkinter as tk
    from tkinter import ttk, messagebox, simpledialog, filedialog

    if getattr(tk, "_automanager_i18n", False):
        return
    tk._automanager_i18n = True

    base_init = tk.BaseWidget.__init__

    def novo_init(self, master, widgetName, cnf={}, kw={}, extra=()):
        if widgetName not in ("entry", "text", "spinbox", "ttk::entry", "ttk::combobox", "ttk::spinbox"):
            if isinstance(cnf, dict) and "text" in cnf:
                cnf = dict(cnf)
                _traduz_opcoes(cnf, ("text",))
            if isinstance(kw, dict) and "text" in kw:
                kw = dict(kw)
                _traduz_opcoes(kw, ("text",))
        base_init(self, master, widgetName, cnf, kw, extra)
    tk.BaseWidget.__init__ = novo_init

    # combobox: mostra os valores traduzidos, mas get() e a variável ligada devolvem o valor original
    def _cb_valores(cb, valores):
        if isinstance(valores, str) or not isinstance(valores, (list, tuple)):
            return valores
        rev = cb.__dict__.setdefault("_i18n_rev", {})
        out = []
        for v in valores:
            if isinstance(v, str):
                tv = t(v)
                rev.setdefault(tv, v)
                out.append(tv)
            else:
                out.append(v)
        return out

    def _cb_ligar(cb, var):
        if var is None or isinstance(var, str) or getattr(var, "_i18n_ligada", False):
            return
        orig_get, orig_set = var.get, var.set

        def get():
            v = orig_get()
            return cb.__dict__.get("_i18n_rev", {}).get(v, v)

        def set_(v):
            orig_set(t(v) if isinstance(v, str) else v)
        var.get, var.set, var._i18n_ligada = get, set_, True
        atual_ = orig_get()
        if isinstance(atual_, str) and atual_:
            orig_set(t(atual_))

    cb_init = ttk.Combobox.__init__

    def novo_cb_init(self, master=None, **kw):
        self.__dict__["_i18n_rev"] = {}
        if "values" in kw:
            kw["values"] = _cb_valores(self, kw["values"])
        cb_init(self, master, **kw)
        _cb_ligar(self, kw.get("textvariable"))
    ttk.Combobox.__init__ = novo_cb_init

    cb_get, cb_set = ttk.Combobox.get, ttk.Combobox.set

    def novo_cb_get(self):
        v = cb_get(self)
        return self.__dict__.get("_i18n_rev", {}).get(v, v)

    def novo_cb_set(self, value):
        return cb_set(self, t(value) if isinstance(value, str) else value)
    ttk.Combobox.get, ttk.Combobox.set = novo_cb_get, novo_cb_set

    base_conf = tk.Misc.configure

    def novo_conf(self, cnf=None, **kw):
        if isinstance(self, ttk.Combobox):
            if isinstance(cnf, dict) and "values" in cnf:
                cnf = dict(cnf)
                cnf["values"] = _cb_valores(self, cnf["values"])
            if "values" in kw:
                kw["values"] = _cb_valores(self, kw["values"])
            if "textvariable" in kw:
                _cb_ligar(self, kw["textvariable"])
        elif not isinstance(self, (tk.Entry, tk.Text, ttk.Entry)):
            if isinstance(cnf, dict) and "text" in cnf:
                cnf = _traduz_opcoes(dict(cnf), ("text",))
            _traduz_opcoes(kw, ("text",))
        return base_conf(self, cnf, **kw)
    tk.Misc.configure = tk.Misc.config = novo_conf

    base_titulo = tk.Wm.wm_title

    def novo_titulo(self, string=None):
        return base_titulo(self, t(string) if isinstance(string, str) else string)
    tk.Wm.wm_title = tk.Wm.title = novo_titulo

    for nome in ("add", "insert", "entryconfigure"):
        orig = getattr(tk.Menu, nome)

        def emb(self, *a, _orig=orig, **kw):
            a = [(_traduz_opcoes(dict(x), ("label",)) if isinstance(x, dict) else x) for x in a]
            _traduz_opcoes(kw, ("label",))
            return _orig(self, *a, **kw)
        setattr(tk.Menu, nome, emb)
    tk.Menu.entryconfig = tk.Menu.entryconfigure

    lb_insert = tk.Listbox.insert

    def novo_lb_insert(self, index, *elementos):
        return lb_insert(self, index, *[t(e) if isinstance(e, str) else e for e in elementos])
    tk.Listbox.insert = novo_lb_insert

    cv_text = tk.Canvas.create_text

    def novo_cv_text(self, *a, **kw):
        _traduz_opcoes(kw, ("text",))
        return cv_text(self, *a, **kw)
    tk.Canvas.create_text = novo_cv_text

    def _valores(kw):
        if isinstance(kw.get("values"), (list, tuple)):
            kw["values"] = [t(v) if isinstance(v, str) else v for v in kw["values"]]
        _traduz_opcoes(kw, ("text",))
        return kw

    tv_heading, tv_insert, tv_item, tv_set = ttk.Treeview.heading, ttk.Treeview.insert, ttk.Treeview.item, \
        ttk.Treeview.set

    def novo_heading(self, column, option=None, **kw):
        return tv_heading(self, column, option, **_traduz_opcoes(kw, ("text",)))

    def novo_insert(self, parent, index, iid=None, **kw):
        return tv_insert(self, parent, index, iid, **_valores(kw))

    def novo_item(self, item, option=None, **kw):
        return tv_item(self, item, option, **_valores(kw))

    def novo_set(self, item, column=None, value=None):
        return tv_set(self, item, column, t(value) if isinstance(value, str) else value)
    ttk.Treeview.heading, ttk.Treeview.insert, ttk.Treeview.item, ttk.Treeview.set = \
        novo_heading, novo_insert, novo_item, novo_set

    nb_add, nb_tab = ttk.Notebook.add, ttk.Notebook.tab

    def novo_nb_add(self, child, **kw):
        return nb_add(self, child, **_traduz_opcoes(kw, ("text",)))

    def novo_nb_tab(self, tab_id, option=None, **kw):
        return nb_tab(self, tab_id, option, **_traduz_opcoes(kw, ("text",)))
    ttk.Notebook.add, ttk.Notebook.tab = novo_nb_add, novo_nb_tab

    def caixa(orig):
        def f(title=None, message=None, **kw):
            return orig(t(title) if isinstance(title, str) else title,
                        t(message) if isinstance(message, str) else message, **kw)
        return f
    for nome in ("showinfo", "showwarning", "showerror", "askyesno", "askokcancel", "askquestion",
                 "askretrycancel", "askyesnocancel"):
        setattr(messagebox, nome, caixa(getattr(messagebox, nome)))

    ask = simpledialog.askstring

    def novo_ask(title, prompt, **kw):
        return ask(t(title), t(prompt), **kw)
    simpledialog.askstring = novo_ask

    def arquivo(orig):
        def f(*a, **kw):
            _traduz_opcoes(kw, ("title",))
            if kw.get("filetypes"):
                kw["filetypes"] = [(t(d), p) for d, p in kw["filetypes"]]
            return orig(*a, **kw)
        return f
    for nome in ("askopenfilename", "askopenfilenames", "asksaveasfilename", "askdirectory"):
        setattr(filedialog, nome, arquivo(getattr(filedialog, nome)))
