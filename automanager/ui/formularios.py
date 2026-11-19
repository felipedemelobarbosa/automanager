"""Componentes do editor: formulário genérico com ajuda e validação por campo, tabela editável
(listas ou dicionários de registros) e editor de matriz."""
import re
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, colorchooser, filedialog

from . import win9x as w

VERMELHO = "#a00000"


def F(caminho, rotulo, tipo="texto", ajuda="", opcoes=None, grupo=None, obrigatorio=False, minimo=None, maximo=None):
    """Descrição de um campo de formulário."""
    if isinstance(caminho, str):
        caminho = (caminho,)
    if isinstance(grupo, str):
        grupo = (grupo,)
    return {"c": tuple(caminho), "r": rotulo, "t": tipo, "a": ajuda, "o": opcoes, "g": grupo,
            "obrig": obrigatorio, "min": minimo, "max": maximo}


def obter(d, caminho):
    for k in caminho:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def definir(d, caminho, valor):
    for k in caminho[:-1]:
        if not isinstance(d.get(k), dict):
            d[k] = {}
        d = d[k]
    d[caminho[-1]] = valor


# ====================================================================== formulário genérico
class FormGenerico(tk.Frame):
    """Gera widgets a partir da lista de campos. Cada campo mostra uma explicação à direita;
    valores inválidos ficam em vermelho com a mensagem no lugar da explicação."""

    def __init__(self, master, campos, ao_mudar=None, rolagem=True, largura_ajuda=330):
        super().__init__(master)
        self.campos = campos
        self.ao_mudar = ao_mudar
        self.item = None
        self._carregando = False
        if rolagem:
            canvas = tk.Canvas(self, highlightthickness=0, bg=w.CINZA)
            sb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
            self.interno = tk.Frame(canvas)
            self.interno.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=self.interno, anchor="nw")
            canvas.configure(yscrollcommand=sb.set)
            canvas.pack(side="left", fill="both", expand=True)
            sb.pack(side="right", fill="y")
            canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(
                -1 * (ev.delta // 120), "units")))
            canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        else:
            self.interno = self
        self.widgets = []
        for i, c in enumerate(campos):
            lbl = tk.Label(self.interno, text=c["r"] + ":", anchor="w")
            lbl.grid(row=i, column=0, sticky="nw", padx=4, pady=1)
            var, ws = self._criar(i, c)
            ajuda = tk.Label(self.interno, text=c["a"], anchor="w", justify="left", fg=w.CINZA_ESCURO,
                             wraplength=largura_ajuda)
            ajuda.grid(row=i, column=2, sticky="w", padx=6)
            self.widgets.append({"campo": c, "var": var, "ws": ws, "lbl": lbl, "ajuda": ajuda})
        self.interno.columnconfigure(2, weight=1)

    # ------------------------------------------------------------------ criação
    def _avisar(self, *_):
        if not self._carregando:
            self.validar()
            if self.ao_mudar:
                self.ao_mudar()

    def _criar(self, linha, c):
        f = self.interno
        t = c["t"]
        if t in ("grupo", "bool"):
            v = tk.BooleanVar()
            cb = ttk.Checkbutton(f, variable=v, text="possui" if t == "grupo" else "",
                                 command=lambda: (self._grupos(), self._avisar()))
            cb.grid(row=linha, column=1, sticky="w")
            return v, [cb]
        if t == "atr":
            v = tk.IntVar()
            fr = tk.Frame(f)
            fr.grid(row=linha, column=1, sticky="w")
            esc = tk.Scale(fr, from_=0, to=100, orient="horizontal", variable=v, length=170, bd=1,
                           highlightthickness=0, troughcolor="#dfdfdf", showvalue=True, sliderlength=14, width=9,
                           command=lambda _x: self._avisar())
            esc.pack(side="left")
            return v, [esc]
        if t in ("escolha", "ref"):
            v = tk.StringVar()
            cb = ttk.Combobox(f, textvariable=v, state="readonly", width=30)
            cb.grid(row=linha, column=1, sticky="w")
            cb.bind("<<ComboboxSelected>>", self._avisar)
            return v, [cb]
        if t == "duracao":
            v = (tk.StringVar(), tk.StringVar())
            fr = tk.Frame(f)
            fr.grid(row=linha, column=1, sticky="w")
            sp = ttk.Spinbox(fr, from_=1, to=99, textvariable=v[0], width=5, command=self._avisar)
            sp.pack(side="left")
            sp.bind("<KeyRelease>", self._avisar)
            cb = ttk.Combobox(fr, textvariable=v[1], values=["temporadas", "corridas"], state="readonly", width=11)
            cb.pack(side="left", padx=4)
            cb.bind("<<ComboboxSelected>>", self._avisar)
            return v, [sp, cb]
        if t == "imagem":
            v = tk.StringVar()
            fr = tk.Frame(f)
            fr.grid(row=linha, column=1, sticky="w", pady=2)
            prev = w.Imagem(fr, 110, 80)
            prev.pack(side="left")
            bs = tk.Frame(fr)
            bs.pack(side="left", padx=4, anchor="n")
            b1 = w.Botao(bs, "Buscar na Wikipedia", lambda c=c, var=v: self._buscar_imagem(c, var), padx=4)
            b1.pack(fill="x")
            b3 = w.Botao(bs, "Escolher arquivo...", lambda c=c, var=v: self._arquivo_imagem(c, var), padx=4)
            b3.pack(fill="x", pady=(2, 0))
            b2 = w.Botao(bs, "Remover", lambda var=v: (var.set(""), self._avisar()), padx=4)
            b2.pack(fill="x", pady=2)
            lbl = tk.Label(bs, text="", fg=w.CINZA_ESCURO, wraplength=150, justify="left")
            lbl.pack(fill="x")
            v.trace_add("write", lambda *_a, var=v: (prev.definir(var.get()),
                                                     lbl.configure(text=var.get() or "(nenhuma)")))
            return v, [b1, b3, b2]
        if t == "aposentadoria":
            v = (tk.StringVar(), tk.StringVar())
            fr = tk.Frame(f)
            fr.grid(row=linha, column=1, sticky="w")
            cb = ttk.Combobox(fr, textvariable=v[0], values=["(sorteio)", "por ano", "por idade"], state="readonly",
                              width=10)
            cb.pack(side="left")
            cb.bind("<<ComboboxSelected>>", self._avisar)
            en = ttk.Entry(fr, textvariable=v[1], width=8)
            en.pack(side="left", padx=4)
            en.bind("<KeyRelease>", self._avisar)
            return v, [cb, en]
        if t == "cor":
            v = tk.StringVar()
            fr = tk.Frame(f)
            fr.grid(row=linha, column=1, sticky="w")
            en = ttk.Entry(fr, textvariable=v, width=10)
            en.pack(side="left")
            amostra = tk.Button(fr, text="  Escolher...  ", relief="raised", bd=2, padx=4)
            amostra.pack(side="left", padx=4)

            def escolher(var=v):
                atual = var.get() if re.fullmatch(r"#[0-9a-fA-F]{6}", var.get() or "") else "#808080"
                novo = colorchooser.askcolor(color=atual, parent=self)[1]
                if novo:
                    var.set(novo)
                    self._avisar()

            def pintar(*_a, var=v, b=amostra):
                cor = var.get()
                if re.fullmatch(r"#[0-9a-fA-F]{6}", cor or ""):
                    from .. import cores
                    b.configure(bg=cor, activebackground=cor, fg=cores.texto_legivel(cor),
                                activeforeground=cores.texto_legivel(cor))
                else:
                    b.configure(bg=w.CINZA, activebackground=w.CINZA, fg=w.PRETO, activeforeground=w.PRETO)
            amostra.configure(command=escolher)
            v.trace_add("write", pintar)
            en.bind("<KeyRelease>", self._avisar)
            return v, [en, amostra]
        if t == "multi":
            vs = {}
            fr = tk.Frame(f)
            fr.grid(row=linha, column=1, sticky="w")
            for op in c["o"]:
                valor, rot = op if isinstance(op, tuple) else (op, op)
                vs[valor] = tk.BooleanVar()
                ttk.Checkbutton(fr, text=rot, variable=vs[valor], command=self._avisar).pack(side="left")
            return vs, list(fr.winfo_children())
        if t == "lista_ref":
            fr = tk.Frame(f)
            fr.grid(row=linha, column=1, sticky="w")
            lb = tk.Listbox(fr, selectmode="multiple", height=c.get("altura", 5), width=32, exportselection=False,
                            relief="sunken", bd=2)
            sb = ttk.Scrollbar(fr, orient="vertical", command=lb.yview)
            lb.configure(yscrollcommand=sb.set)
            lb.pack(side="left")
            sb.pack(side="left", fill="y")
            lb.bind("<<ListboxSelect>>", self._avisar)
            return lb, [lb]
        v = tk.StringVar()
        en = ttk.Entry(f, textvariable=v, width=34 if t in ("texto", "texto_opcional", "lista_num", "auto", "tempos_ano")
                       else 16)
        en.grid(row=linha, column=1, sticky="w")
        en.bind("<KeyRelease>", self._avisar)
        return v, [en]

    def _arquivo_imagem(self, c, var):
        from .. import imagens
        if self.item is None:
            return
        caminho = filedialog.askopenfilename(parent=self, title="Escolher imagem",
                                             filetypes=[("Imagens", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
                                                        ("Todos os arquivos", "*.*")])
        if not caminho:
            return
        self._avisar()
        titulo = self.item.get("wikipedia") or self.item.get("nome") or self.item.get("id") or "imagem"
        try:
            rel = imagens.importar_arquivo(caminho, c.get("tipo_img", "piloto"), titulo)
        except (OSError, ValueError) as e:
            messagebox.showerror("Imagem", f"Não foi possível usar o arquivo:\n{e}", parent=self)
            return
        var.set(rel)
        self._avisar()

    def _buscar_imagem(self, c, var):
        from ..editor import imagens_wiki
        from ..editor.wikipedia import ErroImportacao
        if self.item is None:
            return
        self._avisar()                                  # grava o que foi digitado (ex.: artigo)
        w_art = next((wd for wd in self.widgets if wd["campo"]["c"] == ("wikipedia",)), None)
        titulo = (w_art["var"].get().strip() if w_art else "") or str(self.item.get("nome") or "").strip()
        if not titulo:
            messagebox.showinfo("Imagem", "Informe o artigo da Wikipedia (ou o nome).", parent=self)
            return
        self.config(cursor="watch")
        self.update()
        try:
            rel = imagens_wiki.buscar(c.get("tipo_img", "piloto"), titulo)
        except ErroImportacao as e:
            messagebox.showerror("Imagem", str(e), parent=self)
            return
        finally:
            self.config(cursor="")
        if not rel:
            messagebox.showinfo("Imagem", f"O artigo '{titulo}' não tem imagem utilizável (ou não existe).\n"
                                          "Confira o título do artigo (em inglês).", parent=self)
            return
        if w_art and not w_art["var"].get().strip():
            w_art["var"].set(titulo)
        var.set(rel)
        self._avisar()

    # ------------------------------------------------------------------ opções dinâmicas
    @staticmethod
    def _opcoes(c):
        o = c["o"]
        o = o() if callable(o) else (o or [])
        return [x if isinstance(x, tuple) else (x, str(x)) for x in o]

    # ------------------------------------------------------------------ carregar / salvar
    def carregar(self, item):
        self._carregando = True
        self.item = item
        for wd in self.widgets:
            c, var = wd["campo"], wd["var"]
            v = obter(item, c["c"]) if item is not None else None
            t = c["t"]
            if t == "grupo":
                var.set(v is not None)
            elif t == "bool":
                var.set(bool(v))
            elif t == "atr":
                var.set(int(v or 0))
            elif t == "aposentadoria":
                if item and item.get("idade_aposentadoria") is not None:
                    var[0].set("por idade")
                    var[1].set(str(item["idade_aposentadoria"]))
                elif item and item.get("ano_aposentadoria") is not None:
                    var[0].set("por ano")
                    var[1].set(str(item["ano_aposentadoria"]))
                else:
                    var[0].set("(sorteio)")
                    var[1].set("")
            elif t == "duracao":
                d = v or {}
                var[0].set(str(d.get("corridas", d.get("temporadas", 1))))
                var[1].set("corridas" if "corridas" in d else "temporadas")
            elif t in ("escolha", "ref"):
                ops = self._opcoes(c)
                rotulos = [f"{r} ({k})" if t == "ref" and r != str(k) else r for k, r in ops]
                if t == "ref":
                    rotulos = ["(nenhum)"] + rotulos
                    ops = [(None, "(nenhum)")] + ops
                wd["ws"][0].configure(values=rotulos)
                wd["mapa"] = dict(zip(rotulos, [k for k, _ in ops]))
                atual = next((rot for rot, k in wd["mapa"].items() if k == v), "" if v is None else str(v))
                var.set(atual)
            elif t == "multi":
                for k, bv in var.items():
                    bv.set(k in (v or []))
            elif t == "lista_ref":
                ops = self._opcoes(c)
                wd["mapa"] = [k for k, _ in ops]
                var.delete(0, "end")
                for k, r in ops:
                    var.insert("end", f"{r} ({k})" if r != k else r)
                for i, k in enumerate(wd["mapa"]):
                    if k in (v or []):
                        var.selection_set(i)
            elif t == "lista_num":
                var.set(", ".join(str(x) for x in (v or [])))
            elif t == "tempos_ano":                  # {"2028": [treino, corrida]} -> "2028: 88.4 / 90.1; ..."
                var.set("; ".join(f"{a}: {x[0]} / {x[1]}" for a, x in sorted((v or {}).items())))
            else:
                var.set("" if v is None else str(v))
        self._grupos()
        self._carregando = False
        self.validar()

    def _grupos(self):
        ativos = {wd["campo"]["c"]: wd["var"].get() for wd in self.widgets if wd["campo"]["t"] == "grupo"}
        for wd in self.widgets:
            g = wd["campo"]["g"]
            if g is None:
                continue
            ligado = ativos.get(tuple(g), True)
            for x in wd["ws"]:
                try:
                    if isinstance(x, ttk.Combobox):
                        x.configure(state="readonly" if ligado else "disabled")
                    else:
                        x.configure(state="normal" if ligado else "disabled")
                except tk.TclError:
                    pass

    def _valor(self, wd):
        """(ok, valor ou mensagem)."""
        c, var, t = wd["campo"], wd["var"], wd["campo"]["t"]
        if t in ("bool", "grupo"):
            return True, bool(var.get())
        if t == "atr":
            return True, int(var.get())
        if t == "aposentadoria":
            modo = var[0].get()
            if modo not in ("por ano", "por idade"):
                return True, (None, None)
            try:
                n = int(var[1].get().strip())
            except ValueError:
                return False, "informe um número inteiro"
            if modo == "por idade" and not 15 <= n <= 80:
                return False, "idade entre 15 e 80"
            if modo == "por ano" and not 1900 <= n <= 2200:
                return False, "ano inválido"
            return True, ("ano_aposentadoria" if modo == "por ano" else "idade_aposentadoria", n)
        if t == "duracao":
            try:
                n = int(var[0].get())
                if n < 1:
                    raise ValueError
            except ValueError:
                return False, "duração deve ser um inteiro ≥ 1"
            return True, (n, var[1].get() or "temporadas")
        if t in ("escolha", "ref"):
            mapa = wd.get("mapa") or {}
            bruto = var.get()
            valor = mapa.get(bruto, bruto or None)
            if c["obrig"] and valor is None:
                return False, "escolha uma opção"
            return True, valor
        if t == "multi":
            return True, [k for k, bv in var.items() if bv.get()]
        if t == "lista_ref":
            return True, [wd["mapa"][i] for i in var.curselection()]
        bruto = str(var.get()).strip()
        if t == "tempos_ano":
            out = {}
            try:
                for parte in [x for x in bruto.split(";") if x.strip()]:
                    ano, tempos = parte.split(":")
                    treino, corrida = tempos.split("/")
                    out[str(int(ano.strip()))] = [float(treino.strip().replace(",", ".")),
                                                  float(corrida.strip().replace(",", "."))]
            except ValueError:
                return False, "use ano: treino / corrida; separados por ponto e vírgula"
            return True, out
            try:
                return True, [float(x) if "." in x else int(x) for x in bruto.replace(";", ",").split(",") if x.strip()]
            except ValueError:
                return False, "use números separados por vírgula"
        if t in ("int", "real"):
            if bruto == "":
                if c["obrig"]:
                    return False, "campo obrigatório"
                return True, None
            try:
                v = int(bruto) if t == "int" else float(bruto.replace(",", "."))
            except ValueError:
                return False, "número inválido"
            if c["min"] is not None and v < c["min"]:
                return False, f"mínimo {c['min']}"
            if c["max"] is not None and v > c["max"]:
                return False, f"máximo {c['max']}"
            if t == "real" and v == int(v) and abs(v) >= 1000:
                v = int(v)
            return True, v
        if t == "auto":
            return True, int(bruto) if bruto.isdigit() else bruto
        if t in ("imagem", "texto_opcional"):
            return True, bruto or None
        if t == "cor":
            if bruto == "":
                return True, None
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", bruto):
                return False, "use o formato #RRGGBB (ou o botão Escolher)"
            return True, bruto.lower()
        if c["obrig"] and not bruto:
            return False, "campo obrigatório"
        return True, bruto

    def validar(self):
        """Marca em vermelho os campos inválidos. Retorna a lista de (rótulo, mensagem)."""
        erros = []
        desligados = {wd["campo"]["c"] for wd in self.widgets if wd["campo"]["t"] == "grupo" and not wd["var"].get()}
        for wd in self.widgets:
            if wd["campo"]["g"] is not None and tuple(wd["campo"]["g"]) in desligados:
                ok, v = True, None                     # grupo desmarcado (ex.: sem contrato): não há o que validar
            else:
                ok, v = self._valor(wd)
            extra = wd["campo"].get("validador")
            if ok and extra:
                msg = extra(v, self.item)
                if msg:
                    ok, v = False, msg
            wd["lbl"].configure(fg=w.PRETO if ok else VERMELHO)
            wd["ajuda"].configure(text=wd["campo"]["a"] if ok else f"⚠ {v}", fg=w.CINZA_ESCURO if ok else VERMELHO)
            if not ok:
                erros.append((wd["campo"]["r"], v))
        return erros

    def salvar(self):
        """Grava no item (campos inválidos não são gravados). Preserva campos que o formulário não conhece."""
        it = self.item
        if it is None:
            return
        grupos = {}
        for wd in self.widgets:
            if wd["campo"]["t"] == "grupo":
                ligado = bool(wd["var"].get())
                grupos[wd["campo"]["c"]] = ligado
                if not ligado:
                    definir(it, wd["campo"]["c"], None)
                elif not isinstance(obter(it, wd["campo"]["c"]), dict):
                    definir(it, wd["campo"]["c"], {})
        for wd in self.widgets:
            c = wd["campo"]
            if c["t"] == "grupo" or (c["g"] is not None and not grupos.get(tuple(c["g"]), True)):
                continue
            ok, v = self._valor(wd)
            if not ok:
                continue
            if c["t"] == "aposentadoria":
                it.pop("ano_aposentadoria", None)
                it.pop("idade_aposentadoria", None)
                if v[0]:
                    it[v[0]] = v[1]
                continue
            if c["t"] == "lista_ref" and v and c.get("conta_corridas"):
                pai = obter(it, c["c"][:-1])
                if isinstance(pai, dict):          # a duração passa a ser a quantidade de corridas escolhidas
                    pai.pop("temporadas", None)
                    pai["corridas"] = len(v)
                    for wd2 in self.widgets:
                        if wd2["campo"]["t"] == "duracao" and wd2["campo"]["c"] == c["c"][:-1]:
                            self._carregando = True
                            wd2["var"][0].set(str(len(v)))
                            wd2["var"][1].set("corridas")
                            self._carregando = False
            if c["t"] in ("lista_ref", "lista_num", "tempos_ano") and not v and c.get("vazio_remove"):
                pai = obter(it, c["c"][:-1]) if len(c["c"]) > 1 else it
                if isinstance(pai, dict):
                    pai.pop(c["c"][-1], None)
                continue
            if c["t"] == "duracao":
                d = obter(it, c["c"])
                if not isinstance(d, dict):
                    continue
                d.pop("temporadas", None)
                d.pop("corridas", None)
                d[v[1]] = v[0]
                continue
            if v is None and c["t"] in ("int", "real", "auto", "cor", "imagem", "texto_opcional"):
                # vazio = usar o padrão do jogo: remove a chave em vez de gravar null
                pai = obter(it, c["c"][:-1]) if len(c["c"]) > 1 else it
                if isinstance(pai, dict):
                    pai.pop(c["c"][-1], None)
                continue
            definir(it, c["c"], v)


# ====================================================================== tabela editável
class TabelaEditavel(tk.Frame):
    """Lista (ou dicionário) de registros: tabela em cima, formulário do registro selecionado embaixo."""

    def __init__(self, master, obter_dados, colunas, campos, modo="lista", novo=None, ao_mudar=None,
                 altura=6, rotulo_chave="Chave"):
        super().__init__(master)
        self.obter_dados = obter_dados
        self.colunas = colunas                     # [(caminho, título, largura)]
        self.modo = modo
        self.novo = novo
        self.ao_mudar = ao_mudar
        self.rotulo_chave = rotulo_chave
        cols = ([("__chave", rotulo_chave, 110)] if modo == "dicionario" else []) + \
            [("c%d" % i, t, lg) for i, (_, t, lg) in enumerate(colunas)]
        fr, self.tv = w.tabela(self, [(c, t) for c, t, _ in cols], altura, {c: lg for c, _, lg in cols},
                               estica={cols[0][0]})
        fr.pack(fill="x")
        self.tv.bind("<<TreeviewSelect>>", lambda e: self._selecionar())
        b = tk.Frame(self)
        b.pack(fill="x", pady=2)
        w.Botao(b, "Adicionar", self.adicionar, padx=6).pack(side="left")
        w.Botao(b, "Remover", self.remover, padx=6).pack(side="left", padx=2)
        if modo == "lista":
            w.Botao(b, "↑", lambda: self.mover(-1), padx=6).pack(side="left")
            w.Botao(b, "↓", lambda: self.mover(1), padx=6).pack(side="left", padx=2)
        self.form = FormGenerico(self, campos, ao_mudar=self._mudou, rolagem=False, largura_ajuda=300)
        self.form.pack(fill="x", pady=(2, 0))
        self.atual = None

    def _itens(self):
        d = self.obter_dados()
        if d is None:
            return []
        return list(d.items()) if self.modo == "dicionario" else list(enumerate(d))

    def recarregar(self):
        self.tv.delete(*self.tv.get_children())
        for chave, reg in self._itens():
            vals = ([chave] if self.modo == "dicionario" else []) + \
                [self._fmt(obter(reg, cam)) for cam, _, _ in self.colunas]
            self.tv.insert("", "end", iid=str(chave), values=vals)
        self.atual = None
        filhos = self.tv.get_children()
        if filhos:
            self.tv.selection_set(filhos[0])
            self._selecionar()
        else:
            self.form.carregar(None)

    @staticmethod
    def _fmt(v):
        if isinstance(v, list):
            return ", ".join(str(x) for x in v)
        if isinstance(v, bool):
            return "sim" if v else "não"
        return "" if v is None else str(v)

    def _registro(self, iid):
        d = self.obter_dados()
        if self.modo == "dicionario":
            return d.get(iid)
        return d[int(iid)]

    def _selecionar(self):
        sel = self.tv.selection()
        if not sel:
            return
        self.atual = sel[0]
        self.form.carregar(self._registro(sel[0]))

    def _mudou(self):
        if self.atual is None:
            return
        self.form.salvar()
        reg = self._registro(self.atual)
        vals = ([self.atual] if self.modo == "dicionario" else []) + \
            [self._fmt(obter(reg, cam)) for cam, _, _ in self.colunas]
        self.tv.item(self.atual, values=vals)
        if self.ao_mudar:
            self.ao_mudar()

    def adicionar(self):
        d = self.obter_dados()
        if d is None:
            return
        reg = self.novo() if self.novo else {}
        if self.modo == "dicionario":
            chave = simpledialog.askstring("Adicionar", f"{self.rotulo_chave} do novo registro:", parent=self)
            if not chave or chave in d:
                return
            d[chave] = reg
        else:
            d.append(reg)
        self.recarregar()
        ultimo = self.tv.get_children()[-1] if self.modo == "lista" else chave
        self.tv.selection_set(ultimo)
        self._selecionar()
        if self.ao_mudar:
            self.ao_mudar()

    def remover(self):
        if self.atual is None:
            return
        if not messagebox.askyesno("Remover", "Remover o registro selecionado?", parent=self):
            return
        d = self.obter_dados()
        if self.modo == "dicionario":
            d.pop(self.atual, None)
        else:
            d.pop(int(self.atual))
        self.recarregar()
        if self.ao_mudar:
            self.ao_mudar()

    def mover(self, passo):
        if self.atual is None or self.modo != "lista":
            return
        d = self.obter_dados()
        i = int(self.atual)
        j = i + passo
        if 0 <= j < len(d):
            d[i], d[j] = d[j], d[i]
            self.recarregar()
            self.tv.selection_set(str(j))
            self._selecionar()
            if self.ao_mudar:
                self.ao_mudar()


# ====================================================================== matriz
class MatrizEditavel(tk.Frame):
    """Edita uma matriz {linha: {coluna: número}} (células vazias = peso zero / ausente)."""

    def __init__(self, master, obter_matriz, linhas, colunas, rotulos_linhas=None, rotulos_colunas=None,
                 ao_mudar=None):
        super().__init__(master)
        self.obter_matriz = obter_matriz
        self.linhas, self.colunas = linhas, colunas
        self.ao_mudar = ao_mudar
        self.vars = {}
        tk.Label(self, text="").grid(row=0, column=0)
        for j, col in enumerate(colunas):
            tk.Label(self, text=(rotulos_colunas or {}).get(col, col), font=w.FONTE_TABELA, wraplength=60,
                     justify="center").grid(row=0, column=j + 1, padx=1, sticky="s")
        for i, lin in enumerate(linhas):
            tk.Label(self, text=(rotulos_linhas or {}).get(lin, lin), anchor="w").grid(row=i + 1, column=0, sticky="w",
                                                                                     padx=(0, 4))
            for j, col in enumerate(colunas):
                v = tk.StringVar()
                en = ttk.Entry(self, textvariable=v, width=6, justify="center")
                en.grid(row=i + 1, column=j + 1, padx=1, pady=1)
                en.bind("<KeyRelease>", lambda e, a=lin, b=col: self._mudou(a, b))
                self.vars[(lin, col)] = (v, en)

    def recarregar(self):
        m = self.obter_matriz() or {}
        for (lin, col), (v, en) in self.vars.items():
            x = (m.get(lin) or {}).get(col)
            v.set("" if x is None else str(x))
            en.configure(foreground=w.PRETO)

    def _mudou(self, lin, col):
        m = self.obter_matriz()
        if m is None:
            return
        v, en = self.vars[(lin, col)]
        bruto = v.get().strip().replace(",", ".")
        if bruto == "":
            (m.get(lin) or {}).pop(col, None)
            en.configure(foreground=w.PRETO)
        else:
            try:
                m.setdefault(lin, {})[col] = float(bruto)
                en.configure(foreground=w.PRETO)
            except ValueError:
                en.configure(foreground=VERMELHO)
                return
        if self.ao_mudar:
            self.ao_mudar()
