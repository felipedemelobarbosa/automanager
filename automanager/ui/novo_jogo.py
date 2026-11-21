"""Telas de começo de jogo: carregar categorias, escolher/criar equipe, desenvolvimento inicial."""
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser

from .. import db, state, ratings, cores
from ..db import NOMES_ATRIBUTOS, ATRIBUTOS_CHASSIS
from ..util import dinheiro
from . import win9x as w


# ===================================================================== carregar categorias
class TelaNovoJogo(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=w.CINZA)
        self.app = app
        w.BarraTitulo(self, "Começar jogo novo – carregar database").pack(fill="x", padx=4, pady=4)
        corpo = tk.Frame(self, padx=12, pady=6)
        corpo.pack(fill="both", expand=True)

        self.arquivos = []
        for c in db.todos_os_arquivos():
            try:
                self.arquivos.append(db.resumo_arquivo(c))
            except (db.ErroDatabase, KeyError) as e:
                print("Arquivo ignorado:", c, e)

        self.modo = tk.StringVar(value="unica")
        g = w.Grupo(corpo, "Modo de jogo")
        g.pack(fill="x")
        ttk.Radiobutton(g, text="Carregar categoria única", variable=self.modo, value="unica",
                        command=self._atualizar).pack(anchor="w")
        ttk.Radiobutton(g, text="Carregar múltiplas categorias para a mesma temporada", variable=self.modo,
                        value="multi", command=self._atualizar).pack(anchor="w")

        # categoria única
        self.g_unica = w.Grupo(corpo, "Categoria única")
        self.lb_unica = tk.Listbox(self.g_unica, height=8, exportselection=False, relief="sunken", bd=2)
        for a in self.arquivos:
            self.lb_unica.insert("end", f"{a['nome']}  –  {a['ano']}   ({a['equipes']} equipes)   "
                                        f"[{a['caminho'].split('database')[-1]}]")
        self.lb_unica.pack(fill="both", expand=True)
        if self.arquivos:
            self.lb_unica.selection_set(0)

        # múltiplas
        self.g_multi = w.Grupo(corpo, "Múltiplas categorias")
        self.busca = tk.StringVar(value="auto")
        linha = tk.Frame(self.g_multi)
        linha.pack(fill="x")
        ttk.Radiobutton(linha, text="Busca automática – todos os arquivos categoria_ano da temporada:",
                        variable=self.busca, value="auto", command=self._atualizar).pack(side="left")
        anos = db.anos_disponiveis()
        self.ano = tk.StringVar(value=anos[-1] if anos else "")
        cb = ttk.Combobox(linha, textvariable=self.ano, values=anos, width=8, state="readonly")
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self._atualizar())
        self.lbl_auto = tk.Label(self.g_multi, text="", anchor="w", justify="left", fg=w.AZUL)
        self.lbl_auto.pack(fill="x", padx=22)
        ttk.Radiobutton(self.g_multi, text="Seleção manual (Ctrl+clique para marcar várias):",
                        variable=self.busca, value="manual", command=self._atualizar).pack(anchor="w")
        self.lb_multi = tk.Listbox(self.g_multi, height=6, selectmode="extended", exportselection=False,
                                   relief="sunken", bd=2)
        for a in self.arquivos:
            self.lb_multi.insert("end", f"{a['nome']}  –  {a['ano']}")
        self.lb_multi.pack(fill="both", expand=True, padx=22)

        rod = tk.Frame(self, padx=12, pady=8)
        rod.pack(fill="x", side="bottom", before=corpo)
        w.Botao(rod, "< Voltar", app.menu_inicial, largura=10).pack(side="left")
        w.Botao(rod, "Avançar >", self.avancar, largura=10).pack(side="right")
        self._atualizar()

    def _atualizar(self):
        if self.modo.get() == "unica":
            self.g_multi.pack_forget()
            self.g_unica.pack(fill="both", expand=True, pady=6)
        else:
            self.g_unica.pack_forget()
            self.g_multi.pack(fill="both", expand=True, pady=6)
        arqs = db.arquivos_do_ano(self.ano.get()) if self.ano.get() else []
        nomes = [a["nome"] for a in self.arquivos if a["caminho"] in arqs]
        self.lbl_auto.configure(text=("Encontradas: " + ", ".join(nomes)) if nomes else "Nenhum arquivo encontrado.")
        self.lb_multi.configure(state="normal" if self.busca.get() == "manual" else "disabled")

    def _caminhos(self):
        if self.modo.get() == "unica":
            sel = self.lb_unica.curselection()
            return [self.arquivos[sel[0]]["caminho"]] if sel else []
        if self.busca.get() == "auto":
            return db.arquivos_do_ano(self.ano.get())
        return [self.arquivos[i]["caminho"] for i in self.lb_multi.curselection()]

    def avancar(self):
        caminhos = self._caminhos()
        if not caminhos:
            messagebox.showwarning("Novo jogo", "Selecione ao menos uma categoria.", parent=self)
            return
        try:
            st = state.novo_jogo(caminhos)
        except db.ErroDatabase as e:
            messagebox.showerror("Erro na database", str(e), parent=self)
            return
        if getattr(self.app, "criando_liga", False):
            self.app.criar_liga(st)
            return
        self.app.selecao_equipe(st)


# ===================================================================== escolher equipe
class TelaSelecaoEquipe(tk.Frame):
    def __init__(self, master, app, st):
        super().__init__(master, bg=w.CINZA)
        self.app, self.st = app, st
        w.BarraTitulo(self, f"Escolha sua equipe – temporada {st['ano']}").pack(fill="x", padx=4, pady=4)
        corpo = tk.Frame(self, padx=10, pady=4)
        corpo.pack(fill="both", expand=True)

        self.cats = list(st["categorias"])
        topo = tk.Frame(corpo)
        topo.pack(fill="x", pady=(0, 6))
        self.cat_var = tk.StringVar()
        nomes = [st["categorias"][c]["categoria"]["nome"] for c in self.cats]
        if len(self.cats) > 1:
            tk.Label(topo, text="Categoria que você vai disputar:").pack(side="left")
            cb = ttk.Combobox(topo, values=nomes, textvariable=self.cat_var, state="readonly", width=30)
            cb.pack(side="left", padx=6)
            cb.bind("<<ComboboxSelected>>", lambda e: self._carregar())
        else:
            tk.Label(topo, text=f"Categoria: {nomes[0]}", font=w.FONTE_NEGRITO).pack(side="left")
        self.cat_var.set(nomes[0])

        meio = tk.Frame(corpo)
        meio.pack(fill="both", expand=True)
        esq = w.Grupo(meio, "Equipes")
        esq.pack(side="left", fill="both", expand=True)
        cols = [("equipe", "Equipe"), ("pais", "País"), ("recursos", "Recursos"), ("carro", "Carro"),
                ("caixa", "Orçamento")]
        fr, self.tv = w.tabela(esq, cols, 16, {"equipe": 190, "pais": 110, "recursos": 70, "carro": 60, "caixa": 130},
                               {"recursos": "center", "carro": "center", "caixa": "e"}, cores=True)
        fr.pack(fill="both", expand=True)
        self.tv.bind("<<TreeviewSelect>>", lambda e: self._detalhes())
        self.tv.bind("<Double-1>", lambda e: self.assumir())

        dir_ = w.Grupo(meio, "Detalhes")
        dir_.pack(side="left", fill="both", padx=(8, 0))
        self.txt = tk.Text(dir_, width=46, height=22, relief="sunken", bd=2, wrap="word", font=w.FONTE)
        self.txt.pack(fill="both", expand=True)

        rod = tk.Frame(self, padx=10, pady=8)
        rod.pack(fill="x", side="bottom", before=corpo)
        w.Botao(rod, "< Menu inicial", app.menu_inicial, largura=12).pack(side="left")
        w.Botao(rod, "Assumir equipe", self.assumir, largura=14).pack(side="right", padx=2)
        w.Botao(rod, "Criar minha equipe...", self.criar, largura=18).pack(side="right", padx=2)
        self._carregar()

    @property
    def cid(self):
        nomes = [self.st["categorias"][c]["categoria"]["nome"] for c in self.cats]
        return self.cats[nomes.index(self.cat_var.get())]

    def _carregar(self):
        self.tv.delete(*self.tv.get_children())
        c = self.st["categorias"][self.cid]
        cat = c["categoria"]
        for eq in sorted(c["equipes"].values(), key=lambda e: -e.get("recursos", 0)):
            if not eq.get("ativa"):
                continue
            nota = ratings.nota_geral_carro(state.chassis_da_equipe(self.st, self.cid, eq),
                                            state.motor_da_equipe(self.st, self.cid, eq), cat)
            self.tv.insert("", "end", iid=eq["id"], image=w.chip_equipe(eq, eq.get("nacionalidade")), values=(eq["nome"], eq["nacionalidade"], eq["recursos"],
                                                            f"{nota:.0f}", dinheiro(eq["financas"]["caixa"])))
        filhos = self.tv.get_children()
        if filhos:
            self.tv.selection_set(filhos[0])

    def _detalhes(self):
        sel = self.tv.selection()
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        if not sel:
            return
        c = self.st["categorias"][self.cid]
        eq = c["equipes"][sel[0]]
        ch = state.chassis_da_equipe(self.st, self.cid, eq)
        mo = state.motor_da_equipe(self.st, self.cid, eq)
        origem_m = {"proprio": "próprio", "equipe": "de outra equipe", "fabricante": "de fabricante"}
        linhas = [eq["nome"], f"País: {eq['nacionalidade']}", f"Recursos: {eq['recursos']}/100",
                  f"Orçamento: {dinheiro(eq['financas']['caixa'])}", "",
                  f"Chassis: {ch['nome'] if ch else '-'} ({'próprio' if (eq.get('chassis') or {}).get('origem') == 'proprio' else 'de terceiros'})",
                  f"Motor: {mo['nome'] if mo else '-'} ({origem_m.get((eq.get('motor') or {}).get('origem'), '-')})",
                  "", "Pilotos:"]
        bandeiras = {1: eq.get("nacionalidade")}
        for p in state.pilotos_da_equipe(self.st, self.cid, eq["id"]):
            nota = ratings.nota_geral_piloto(p, c["categoria"])
            bandeiras[len(linhas)] = p.get("nacionalidade")
            linhas.append(f"  {p['nome']} ({p['nacionalidade']}, {p['idade']} anos) – "
                          f"{'principal' if p['contrato']['situacao'] == 'principal' else 'testes'}, nota {nota:.0f}")
        from .. import i18n                   # caixa de texto: não passa pelo gancho do Tk, traduz aqui
        self.txt.insert("1.0", "\n".join(i18n.t(x) for x in linhas))
        self._imgs = []
        for i, pais in bandeiras.items():
            img = w.bandeira(pais)
            if img is not None:
                self.txt.image_create(f"{i + 1}.0", image=img, padx=2)
                self._imgs.append(img)
        self.txt.configure(state="disabled")

    def assumir(self):
        sel = self.tv.selection()
        if not sel:
            return
        eq = self.st["categorias"][self.cid]["equipes"][sel[0]]
        if not messagebox.askyesno("Assumir equipe", f"Confirmar o comando da {eq['nome']}?", parent=self):
            return
        state.escolher_equipe(self.st, self.cid, sel[0])
        self.app.gestao(self.st)

    def criar(self):
        usadas = {cores.cor_equipe(e) for e in self.st["categorias"][self.cid]["equipes"].values() if e.get("ativa")}
        r = DialogoCriarEquipe(self, usadas).modal()
        if not r:
            return
        nome, nac, cor, cor2 = r
        eq = state.criar_equipe(self.st, self.cid, nome, nac, cor=cor, cor_secundaria=cor2)
        ch, mo = state.precisa_desenvolvimento_inicial(self.st, self.cid, eq["id"])
        messagebox.showinfo("Nova equipe", f"{nome} foi criada com orçamento de "
                                           f"{dinheiro(eq['financas']['caixa'])}.", parent=self)
        if ch or mo:
            self.app.desenvolvimento_inicial(self.st)
        else:
            self.app.gestao(self.st)


class DialogoCriarEquipe(w.Dialogo):
    def __init__(self, master, usadas=()):
        super().__init__(master, "Criar equipe", 380, 235)
        w.BarraTitulo(self.corpo, "Dados da nova equipe").pack(fill="x", pady=(0, 8))
        f = tk.Frame(self.corpo)
        f.pack(fill="x")
        tk.Label(f, text="Nome da equipe:").grid(row=0, column=0, sticky="w", pady=3)
        self.nome = ttk.Entry(f, width=30)
        self.nome.grid(row=0, column=1, columnspan=2, sticky="w", pady=3)
        tk.Label(f, text="Nacionalidade:").grid(row=1, column=0, sticky="w", pady=3)
        self.nac = w.CampoPais(f, width=28)
        self.nac.grid(row=1, column=1, columnspan=2, sticky="w", pady=3)
        livres = [c for c in cores.PALETA if c not in usadas] or cores.PALETA
        self.cores = {"cor": livres[0], "cor_secundaria": "#ffffff"}
        self.botoes = {}
        for i, (k, rot) in enumerate((("cor", "Cor principal:"), ("cor_secundaria", "Cor secundária:"))):
            tk.Label(f, text=rot).grid(row=2 + i, column=0, sticky="w", pady=3)
            b = tk.Button(f, text="Escolher...", width=12, relief="raised", bd=2,
                          command=lambda k=k: self._escolher(k))
            b.grid(row=2 + i, column=1, sticky="w", pady=3)
            self.botoes[k] = b
        self.faixa = w.FaixaEquipe(f, largura=16)
        self.faixa.grid(row=2, column=2, rowspan=2, sticky="ns", padx=8)
        self._pintar()
        self.nome.focus_set()
        w.Botao(self.rodape, "Cancelar", self.cancelar, largura=10).pack(side="right", padx=2)
        w.Botao(self.rodape, "OK", self.ok, largura=10).pack(side="right", padx=2)
        self.bind("<Return>", lambda e: self.ok())

    def _escolher(self, k):
        novo = colorchooser.askcolor(color=self.cores[k], parent=self)[1]
        if novo:
            self.cores[k] = novo.lower()
            self._pintar()

    def _pintar(self):
        for k, b in self.botoes.items():
            cor = self.cores[k]
            b.configure(bg=cor, activebackground=cor, fg=cores.texto_legivel(cor),
                        activeforeground=cores.texto_legivel(cor), text=cor)
        self.faixa.definir({"cor": self.cores["cor"], "cor_secundaria": self.cores["cor_secundaria"]})

    def ok(self):
        nome, nac = self.nome.get().strip(), self.nac.valor()
        if not nome or not nac:
            messagebox.showwarning("Criar equipe", "Informe o nome e a nacionalidade.", parent=self)
            return
        self.resultado = (nome, nac, self.cores["cor"], self.cores["cor_secundaria"])
        self.destroy()


# ===================================================================== desenvolvimento inicial
class TelaDesenvolvimentoInicial(tk.Frame):
    """Só na criação da equipe: distribuir dinheiro no chassis e/ou motor iniciais."""

    def __init__(self, master, app, st):
        super().__init__(master, bg=w.CINZA)
        self.app, self.st = app, st
        u = st["usuario"]
        self.cid, self.eid = u["categoria"], u["equipe"]
        self.eq = state.equipe_usuario(st)
        self.di = {p: state.config_dev_inicial(st, self.cid, p) for p in ("chassis", "motor")}
        self.precisa_ch, self.pode_mo = state.precisa_desenvolvimento_inicial(st, self.cid, self.eid)
        w.BarraTitulo(self, f"{self.eq['nome']} – desenvolvimento inicial do carro").pack(fill="x", padx=4, pady=4)
        corpo = tk.Frame(self, padx=12, pady=4)
        corpo.pack(fill="both", expand=True)
        tk.Label(corpo, justify="left", text="Distribua o orçamento da equipe no desenvolvimento do chassis e/ou do "
                                             "motor iniciais. O dinheiro investido sai do caixa.").pack(anchor="w")

        self.vars_ch = {}
        self.vars_mo = None
        self.motor_proprio = tk.BooleanVar(value=self.pode_mo)
        self.pode_comprar_ch = self.precisa_ch and state.compra_de_chassis(st["categorias"][self.cid]["categoria"])
        self.chassis_proprio = tk.BooleanVar(value=True)
        self.escalas_ch = []
        linha = tk.Frame(corpo)
        linha.pack(fill="both", expand=True, pady=6)
        if self.precisa_ch:
            cfg = self.di.get("chassis", {"custo_por_ponto": 100000, "atributo_base": 35, "atributo_maximo": 85})
            g = w.Grupo(linha, f"Chassis – {dinheiro(cfg['custo_por_ponto'])} por ponto")
            g.pack(side="left", fill="both", expand=True)
            topo = 0
            if self.pode_comprar_ch:
                fr = tk.Frame(g)
                fr.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
                ttk.Radiobutton(fr, text="Desenvolver chassis próprio", value=True, variable=self.chassis_proprio,
                                command=self._recalcular).pack(side="left")
                ttk.Radiobutton(fr, text="Comprar no Mercado", value=False, variable=self.chassis_proprio,
                                command=self._recalcular).pack(side="left", padx=8)
                topo = 1
            for i, k in enumerate(ATRIBUTOS_CHASSIS, start=topo):
                v = tk.IntVar(value=cfg["atributo_base"])
                self.vars_ch[k] = v
                tk.Label(g, text=NOMES_ATRIBUTOS[k], width=16, anchor="w").grid(row=i, column=0, sticky="w")
                esc = tk.Scale(g, from_=cfg["atributo_base"], to=cfg["atributo_maximo"], orient="horizontal", variable=v,
                               length=220, showvalue=True, command=lambda _v: self._recalcular(), bd=1,
                               highlightthickness=0, troughcolor="#dfdfdf", sliderrelief="raised")
                esc.grid(row=i, column=1)
                self.escalas_ch.append(esc)
            if self.pode_comprar_ch:
                tk.Label(g, text="Comprando, o chassis vem de um fornecedor ou de outra equipe (Mercado > Chassis).",
                         fg=w.CINZA_ESCURO, justify="left", wraplength=360).grid(row=len(ATRIBUTOS_CHASSIS) + 1,
                                                                               column=0, columnspan=2, sticky="w")
        g2 = w.Grupo(linha, "Motor")
        g2.pack(side="left", fill="both", padx=(8, 0))
        if self.pode_mo:
            cfg = self.di.get("motor", {"custo_por_ponto": 200000, "atributo_base": 40, "atributo_maximo": 85})
            ttk.Checkbutton(g2, text="Desenvolver motor próprio", variable=self.motor_proprio,
                            command=self._recalcular).pack(anchor="w")
            tk.Label(g2, text=f"Potência – {dinheiro(cfg['custo_por_ponto'])} por ponto").pack(anchor="w", pady=(6, 0))
            self.vars_mo = tk.IntVar(value=cfg["atributo_base"])
            self.esc_mo = tk.Scale(g2, from_=cfg["atributo_base"], to=cfg["atributo_maximo"], orient="horizontal",
                                   variable=self.vars_mo, length=220, command=lambda _v: self._recalcular(), bd=1,
                                   highlightthickness=0, troughcolor="#dfdfdf")
            self.esc_mo.pack(anchor="w")
            tk.Label(g2, text="Sem motor próprio, o motor deverá ser\ncomprado de outra equipe ou fabricante\n"
                              "no Mercado (aguardando definição).", justify="left", fg=w.CINZA_ESCURO
                     ).pack(anchor="w", pady=6)
        else:
            tk.Label(g2, text="Esta categoria/equipe não permite\nmotor próprio. O motor deverá ser\ncomprado de "
                              "outra equipe ou de um\nfabricante no Mercado\n(aguardando definição).",
                     justify="left").pack(anchor="w")

        res = w.Grupo(corpo, "Resumo")
        res.pack(fill="x")
        self.lbl = tk.Label(res, text="", justify="left", anchor="w", font=w.FONTE_NEGRITO)
        self.lbl.pack(fill="x")
        rod = tk.Frame(self, padx=12, pady=8)
        rod.pack(fill="x", side="bottom", before=corpo)
        self.btn = w.Botao(rod, "Confirmar desenvolvimento", self.confirmar, largura=24)
        self.btn.pack(side="right")
        self._recalcular()

    def _custo(self):
        total = 0.0
        if self.precisa_ch and self.chassis_proprio.get():
            cfg = self.di.get("chassis", {"custo_por_ponto": 100000, "atributo_base": 35})
            total += sum(v.get() - cfg["atributo_base"] for v in self.vars_ch.values()) * cfg["custo_por_ponto"]
        if self.pode_mo and self.motor_proprio.get():
            cfg = self.di.get("motor", {"custo_por_ponto": 200000, "atributo_base": 40})
            total += (self.vars_mo.get() - cfg["atributo_base"]) * cfg["custo_por_ponto"]
        return total

    def _recalcular(self):
        if self.vars_mo is not None:
            self.esc_mo.configure(state="normal" if self.motor_proprio.get() else "disabled")
        for esc in self.escalas_ch:
            esc.configure(state="normal" if self.chassis_proprio.get() else "disabled")
        custo = self._custo()
        caixa = self.eq["financas"]["caixa"]
        sobra = caixa - custo
        self.lbl.configure(text=f"Caixa: {dinheiro(caixa)}     Investimento: {dinheiro(custo)}     "
                                f"Restante: {dinheiro(sobra)}", fg=w.PRETO if sobra >= 0 else "#a00000")
        self.btn.configure(state="normal" if sobra >= 0 else "disabled")

    def confirmar(self):
        from .. import acoes
        if self._custo() > self.eq["financas"]["caixa"]:
            return
        comprar = self.pode_comprar_ch and not self.chassis_proprio.get()
        attrs = {k: v.get() for k, v in self.vars_ch.items()} if self.precisa_ch and not comprar else None
        pot = self.vars_mo.get() if (self.pode_mo and self.motor_proprio.get()) else None
        # passa por acoes: no multijogador a decisão vai para o arquivo de ordens (o custo é recalculado lá)
        erro = acoes.executar(self.st, "dev_inicial", chassis=attrs, potencia=pot, comprar_chassis=comprar)
        if erro:
            messagebox.showwarning("Desenvolvimento inicial", erro, parent=self)
            return
        self.app.gestao(self.st)
