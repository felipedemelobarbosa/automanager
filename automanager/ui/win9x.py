"""Tema visual estilo Windows 9x para Tkinter + widgets auxiliares."""
import tkinter as tk
from tkinter import ttk

CINZA = "#c0c0c0"
CINZA_ESCURO = "#808080"
BRANCO = "#ffffff"
PRETO = "#000000"
AZUL = "#000080"
AZUL_CLARO = "#1084d0"
AMARELO_INFO = "#ffffe1"

# Fontes: Segoe UI (resolvida em aplicar(); sem Segoe UI no sistema, usa a primeira candidata que existir).
FONTE = ("Segoe UI", 9)
FONTE_NEGRITO = ("Segoe UI", 9, "bold")
FONTE_TITULO = ("Segoe UI", 10, "bold")
FONTE_GRANDE = ("Segoe UI", 28, "bold italic")
FONTE_TABELA = ("Segoe UI", 9)
CANDIDATAS = ("Segoe UI", "Tahoma", "Microsoft Sans Serif", "DejaVu Sans", "Liberation Sans", "FreeSans")


def _resolver_fontes(root):
    global FONTE, FONTE_NEGRITO, FONTE_TITULO, FONTE_GRANDE, FONTE_TABELA
    from tkinter import font as tkfont
    familias = set(tkfont.families(root))
    base = next((f for f in CANDIDATAS if f in familias), "TkDefaultFont")
    FONTE = (base, 9)
    FONTE_NEGRITO = (base, 9, "bold")
    FONTE_TITULO = (base, 10, "bold")
    FONTE_GRANDE = (base, 28, "bold italic")
    FONTE_TABELA = (base, 9)


def aplicar(root):
    _resolver_fontes(root)
    root.configure(bg=CINZA)
    root.option_add("*Font", FONTE)
    root.option_add("*Background", CINZA)
    root.option_add("*Foreground", PRETO)
    root.option_add("*activeBackground", CINZA)
    root.option_add("*activeForeground", PRETO)
    root.option_add("*selectBackground", AZUL)
    root.option_add("*selectForeground", BRANCO)
    root.option_add("*Listbox.background", BRANCO)
    root.option_add("*Entry.background", BRANCO)
    root.option_add("*Text.background", BRANCO)
    root.option_add("*Menu.activeBackground", AZUL)
    root.option_add("*Menu.activeForeground", BRANCO)
    root.option_add("*Menu.relief", "raised")
    root.option_add("*Menu.activeBorderWidth", 0)
    root.option_add("*Menu.disabledForeground", CINZA_ESCURO)
    root.option_add("*tearOff", False)

    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", background=CINZA, foreground=PRETO, font=FONTE, bordercolor=CINZA_ESCURO,
                 lightcolor=BRANCO, darkcolor=CINZA_ESCURO, troughcolor="#d4d0c8", focuscolor=PRETO,
                 selectbackground=AZUL, selectforeground=BRANCO, fieldbackground=BRANCO)
    st.configure("TButton", padding=(8, 3), relief="raised", borderwidth=2)
    st.map("TButton", relief=[("pressed", "sunken")], background=[("active", CINZA), ("disabled", CINZA)],
           foreground=[("disabled", CINZA_ESCURO)])
    st.configure("TLabelframe", relief="groove", borderwidth=2)
    st.configure("TLabelframe.Label", background=CINZA, font=FONTE)
    st.configure("Treeview", background=BRANCO, fieldbackground=BRANCO, rowheight=20, borderwidth=2,
                 relief="sunken", font=FONTE_TABELA)
    st.configure("Treeview.Heading", background=CINZA, relief="raised", borderwidth=2, font=FONTE_TABELA)
    st.map("Treeview", background=[("selected", AZUL)], foreground=[("selected", BRANCO)])
    st.map("Treeview.Heading", relief=[("pressed", "sunken")], background=[("active", CINZA)])
    st.configure("TNotebook", background=CINZA, borderwidth=2)
    st.configure("TNotebook.Tab", background=CINZA, padding=(8, 2), borderwidth=2)
    st.map("TNotebook.Tab", background=[("selected", CINZA)], expand=[("selected", (1, 2, 1, 0))])
    st.configure("TCombobox", fieldbackground=BRANCO, background=CINZA, arrowsize=13)
    st.map("TCombobox", fieldbackground=[("readonly", BRANCO)], selectbackground=[("readonly", BRANCO)],
           selectforeground=[("readonly", PRETO)])
    st.configure("TCheckbutton", background=CINZA)
    st.configure("TRadiobutton", background=CINZA)
    st.configure("TScrollbar", background=CINZA, troughcolor="#dfdfdf", arrowsize=15, relief="raised")
    st.configure("TEntry", fieldbackground=BRANCO)
    st.configure("TSpinbox", fieldbackground=BRANCO, arrowsize=10)
    st.configure("Horizontal.TScale", background=CINZA, troughcolor="#dfdfdf", sliderlength=12)
    return st


class Botao(tk.Button):
    def __init__(self, master, texto, comando=None, largura=None, **kw):
        opts = dict(text=texto, command=comando, bg=CINZA, activebackground=CINZA, activeforeground=PRETO, relief="raised", bd=2,
                    padx=10, pady=2, font=FONTE, highlightthickness=1, highlightbackground=CINZA)
        if largura:
            opts["width"] = largura
        opts.update(kw)
        super().__init__(master, **opts)


class BarraTitulo(tk.Canvas):
    """Faixa azul degradê com texto branco (como a barra de título do Win98)."""

    def __init__(self, master, texto, altura=20, fonte=None):
        super().__init__(master, height=altura, highlightthickness=0, bd=0, bg=AZUL)
        self.texto = texto
        self.fonte = fonte or FONTE_TITULO
        self.bind("<Configure>", self._desenhar)

    def definir(self, texto):
        self.texto = texto
        self._desenhar()

    def _desenhar(self, _e=None):
        self.delete("all")
        w, h = max(1, self.winfo_width()), int(self["height"])
        passos = 48
        for i in range(passos):
            f = i / (passos - 1)
            r = int(0x00 + (0x10 - 0x00) * f)
            g = int(0x00 + (0x84 - 0x00) * f)
            b = int(0x80 + (0xd0 - 0x80) * f)
            x0 = int(w * i / passos)
            x1 = int(w * (i + 1) / passos) + 1
            self.create_rectangle(x0, 0, x1, h, fill=f"#{r:02x}{g:02x}{b:02x}", outline="")
        self.create_text(6, h // 2, text=self.texto, anchor="w", fill=BRANCO, font=self.fonte)


class Grupo(ttk.LabelFrame):
    def __init__(self, master, titulo, **kw):
        super().__init__(master, text=f" {titulo} ", padding=6, **kw)


class Rebaixado(tk.Frame):
    """Painel com borda afundada (campo branco do Win9x)."""

    def __init__(self, master, fundo=BRANCO, **kw):
        super().__init__(master, bg=fundo, relief="sunken", bd=2, **kw)


class BarraAtributo(tk.Canvas):
    """Barra de 0-100 em blocos azuis (como barra de progresso do Win9x)."""

    def __init__(self, master, valor=0, largura=120, altura=13):
        super().__init__(master, width=largura, height=altura, bg=BRANCO, highlightthickness=0, relief="sunken",
                         bd=1)
        self.largura, self.altura = largura, altura
        self.definir(valor)

    def definir(self, valor):
        self.delete("all")
        valor = max(0, min(100, valor or 0))
        bloco, esp = 6, 2
        util = int((self.largura - 4) * valor / 100)
        x = 2
        while x + bloco <= util + 2:
            self.create_rectangle(x, 2, x + bloco, self.altura - 1, fill=AZUL, outline=AZUL)
            x += bloco + esp


class BarraStatus(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=CINZA)
        self.campos = []

    def campo(self, texto="", largura=None, expandir=False):
        lbl = tk.Label(self, text=texto, anchor="w", relief="sunken", bd=1, padx=4, bg=CINZA)
        if largura:
            lbl.configure(width=largura)
        lbl.pack(side="left", fill="x", expand=expandir, padx=1, pady=1)
        self.campos.append(lbl)
        return lbl


_CHIPS = {}


def chip(cor, secundaria=None):
    """Quadradinho com a cor da equipe (faixa inferior com a cor secundária, se houver)."""
    chave = (cor, secundaria)
    if chave not in _CHIPS:
        img = tk.PhotoImage(width=18, height=12)
        img.put(PRETO, to=(1, 0, 17, 12))
        img.put(cor, to=(2, 1, 16, 11))
        if secundaria:
            img.put(secundaria, to=(2, 8, 16, 11))
        _CHIPS[chave] = img
    return _CHIPS[chave]


def bandeira(pais, largura=18, altura=12):
    """PhotoImage da bandeira do país (ou None)."""
    from .. import imagens
    rel = imagens.bandeira(pais)
    return imagens.foto(rel, largura, altura) if rel else None


def chip_equipe(eq, pais=None, com_cor=True):
    """Ficha da primeira coluna das tabelas: cor da equipe e, ao lado, a bandeira do país (se informado)."""
    from .. import cores
    base = chip(cores.cor_equipe(eq), cores.cor_secundaria(eq)) if com_cor else None
    if not pais:
        return base if base is not None else chip(CINZA)
    from .. import paises
    chave = ("ficha", cores.cor_equipe(eq) if com_cor else None, cores.cor_secundaria(eq) if com_cor else None,
             paises.chave(pais))
    if chave in _CHIPS:
        return _CHIPS[chave]
    flag = bandeira(pais)
    x0 = 20 if com_cor else 0
    img = tk.PhotoImage(width=x0 + 18, height=12)
    if base is not None:
        img.tk.call(img, "copy", base, "-to", 0, 0)
    if flag is not None:
        dx = x0 + (18 - flag.width()) // 2
        dy = (12 - flag.height()) // 2
        img.tk.call(img, "copy", flag, "-to", dx, dy)
        img.put(CINZA_ESCURO, to=(dx, dy, dx + flag.width(), dy + 1))      # contorno leve
        img.put(CINZA_ESCURO, to=(dx, dy + flag.height() - 1, dx + flag.width(), dy + flag.height()))
        img.put(CINZA_ESCURO, to=(dx, dy, dx + 1, dy + flag.height()))
        img.put(CINZA_ESCURO, to=(dx + flag.width() - 1, dy, dx + flag.width(), dy + flag.height()))
    _CHIPS[chave] = img
    return img


def ficha_logo(rel, pais=None):
    """Ficha com bandeira (18x12) e o logotipo reduzido (até 40x16) – listas de chassis e motores."""
    from .. import imagens, paises
    logo = imagens.foto(rel, 40, 16) if rel else None
    chave = ("logo", rel if logo is not None else None, paises.chave(pais) if pais else None)
    if chave in _CHIPS:
        return _CHIPS[chave]
    img = tk.PhotoImage(width=62, height=16)
    flag = bandeira(pais) if pais else None
    if flag is not None:
        img.tk.call(img, "copy", flag, "-to", (18 - flag.width()) // 2, (16 - flag.height()) // 2)
    if logo is not None:
        img.tk.call(img, "copy", logo, "-to", 22 + (40 - logo.width()) // 2, (16 - logo.height()) // 2)
    _CHIPS[chave] = img
    return img


def ficha(eq=None, pais=None, com_cor=True):
    return chip_equipe(eq, pais, com_cor)


class RotuloBandeira(tk.Frame):
    """Bandeira + texto (rótulos fora das tabelas)."""

    def __init__(self, master, pais, texto=None, **kw):
        super().__init__(master)
        img = bandeira(pais)
        if img is not None:
            lb = tk.Label(self, image=img)
            lb.image = img
            lb.pack(side="left", padx=(0, 4))
        self.lbl = tk.Label(self, text=pais if texto is None else texto, **kw)
        self.lbl.pack(side="left")


class FaixaEquipe(tk.Frame):
    """Faixa vertical com as cores da equipe (ao lado de títulos)."""

    def __init__(self, master, eq=None, largura=10):
        super().__init__(master, width=largura, bd=1, relief="sunken", bg=CINZA)
        self.cima = tk.Frame(self, width=largura)
        self.baixo = tk.Frame(self, width=largura)
        self.cima.pack(fill="both", expand=True)
        self.baixo.pack(fill="x")
        self.definir(eq)

    def definir(self, eq):
        from .. import cores
        prim = cores.cor_equipe(eq)
        sec = cores.cor_secundaria(eq) or prim
        self.cima.configure(bg=prim)
        self.baixo.configure(bg=sec, height=6)


class Imagem(tk.Frame):
    """Caixa de tamanho fixo com uma imagem de database/imagens (foto, logotipo, pista).
    Sem imagem: mostra o texto 'vazio' (ou some, se ocultar_vazio=True)."""

    def __init__(self, master, largura, altura, vazio="sem imagem", ocultar_vazio=False, borda=True):
        super().__init__(master, width=largura + (4 if borda else 0), height=altura + (4 if borda else 0),
                         bd=2 if borda else 0, relief="sunken", bg=BRANCO)
        self.pack_propagate(False)
        self.grid_propagate(False)
        self.largura, self.altura, self.vazio, self.ocultar_vazio = largura, altura, vazio, ocultar_vazio
        self.lbl = tk.Label(self, bg=BRANCO, fg=CINZA_ESCURO, text=vazio, wraplength=largura)
        self.lbl.pack(fill="both", expand=True)
        self.tem = False

    def definir(self, rel):
        from .. import imagens
        ph = imagens.foto(rel, self.largura, self.altura) if rel else None
        self.tem = ph is not None
        if ph is not None:
            self.lbl.configure(image=ph, text="")
            self.lbl.image = ph
        else:
            self.lbl.configure(image="", text=self.vazio)
            self.lbl.image = None
        return self.tem


def _estilo_fichas(widget):
    """Estilo das tabelas com ficha de cor/bandeira na 1ª coluna: lista sem hierarquia, então sem o espaço da
    seta de expandir (que empurrava a ficha para cima do nome da coluna seguinte)."""
    def sem_indicador(layout):
        out = []
        for nome, opc in layout:
            if "indicator" in nome:
                continue
            opc = dict(opc)
            if "children" in opc:
                opc["children"] = sem_indicador(opc["children"])
            out.append((nome, opc))
        return out
    st = ttk.Style(widget)
    st.layout("Fichas.Treeview.Item", sem_indicador(st.layout("Treeview.Item")))
    return "Fichas.Treeview"


def tabela(master, colunas, alturas=10, larguras=None, ancoras=None, estica=None, cores=False):
    """Treeview com barra de rolagem. colunas: lista de (id, título).
    cores=True: primeira coluna estreita para a ficha de cor da equipe e a bandeira
    (insert(..., image=chip_equipe(eq, pais)))."""
    frame = tk.Frame(master, bg=CINZA)
    largura_ficha = cores if (cores is not True and isinstance(cores, int) and cores > 1) else 48
    tv = ttk.Treeview(frame, columns=[c for c, _ in colunas], show="tree headings" if cores else "headings",
                      height=alturas, selectmode="browse")
    if cores:
        tv.configure(style=_estilo_fichas(tv))
        tv.heading("#0", text="")
        tv.column("#0", width=largura_ficha, minwidth=largura_ficha, stretch=False, anchor="w")
    for i, (cid, titulo) in enumerate(colunas):
        tv.heading(cid, text=titulo)
        w = (larguras or {}).get(cid, 80)
        anc = (ancoras or {}).get(cid, "w")
        tv.column(cid, width=w, minwidth=24, anchor=anc,
                  stretch=(cid in estica) if estica else (cid == colunas[0][0]))
    sb = ttk.Scrollbar(frame, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    tv.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    tv.tag_configure("usuario", background=AMARELO_INFO)
    tv.tag_configure("cinza", foreground=CINZA_ESCURO)
    return frame, tv


def centralizar(janela, largura, altura):
    janela.update_idletasks()
    sw, sh = janela.winfo_screenwidth(), janela.winfo_screenheight()
    janela.geometry(f"{largura}x{altura}+{max(0, (sw - largura) // 2)}+{max(0, (sh - altura) // 3)}")


class Dialogo(tk.Toplevel):
    """Janela modal simples com faixa de título interna."""

    def __init__(self, master, titulo, largura=420, altura=300):
        super().__init__(master, bg=CINZA)
        self.title(titulo)
        if master.winfo_toplevel().winfo_viewable():
            self.transient(master.winfo_toplevel())
        self.resizable(False, False)
        self.resultado = None
        self.corpo = tk.Frame(self, bg=CINZA, padx=10, pady=8)
        self.corpo.pack(fill="both", expand=True)
        self.rodape = tk.Frame(self, bg=CINZA, padx=10, pady=8)
        self.rodape.pack(fill="x", side="bottom")
        centralizar(self, largura, altura)
        self.protocol("WM_DELETE_WINDOW", self.cancelar)
        self.bind("<Escape>", lambda e: self.cancelar())

    def modal(self):
        self.grab_set()
        self.wait_window(self)
        return self.resultado

    def cancelar(self):
        self.resultado = None
        self.destroy()
