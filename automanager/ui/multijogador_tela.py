"""Telas do multijogador: criar liga, tela do comissário, entrada do jogador e plano de evento."""
import os
import random
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from .. import multiplayer as mp, state, caixa_liga as caixa
from ..event import planos as planos_evento
from ..event.inscritos import montar_inscritos
from ..event.modelo import PARAMETROS_ACERTO, NOMES_ACERTO, ORDENS, NOMES_ORDENS
from . import win9x as w

NOMES_POLITICA = {
    "ia": ("A IA joga o turno", "A equipe de quem não mandou o arquivo é conduzida pela IA nesta semana."),
    "repetir": ("Repetir as últimas ordens", "Repete o desenvolvimento e o plano de evento das últimas ordens; "
                                             "nada de novo no mercado."),
    "bloquear": ("Bloquear o turno", "A semana só roda com todos os arquivos (ou se o comissário pular o "
                                     "jogador, que então fica com a IA)."),
}


def pasta_liga(nome):
    return os.path.join(mp.PASTA_LIGAS, mp._slug(nome))


# ===================================================================== criar liga
class TelaCriarLiga(tk.Frame):
    def __init__(self, master, app, st):
        super().__init__(master, bg=w.CINZA)
        self.app, self.st = app, st
        self.jogadores = []
        w.BarraTitulo(self, "Nova liga multijogador – comissário").pack(fill="x", padx=4, pady=4)
        rod = tk.Frame(self, padx=8, pady=6)
        rod.pack(fill="x", side="bottom")
        w.Botao(rod, "Criar liga", self.criar, largura=14).pack(side="right", padx=2)
        w.Botao(rod, "Cancelar", app.menu_inicial, largura=10).pack(side="right", padx=2)
        corpo = tk.Frame(self, padx=12, pady=6)
        corpo.pack(fill="both", expand=True)
        f = tk.Frame(corpo)
        f.pack(fill="x")
        tk.Label(f, text="Nome da liga:").pack(side="left")
        self.v_nome = tk.StringVar(value="Minha liga")
        ttk.Entry(f, textvariable=self.v_nome, width=30).pack(side="left", padx=4)
        g = w.Grupo(corpo, "Quando um jogador não mandar o arquivo de ordens")
        g.pack(fill="x", pady=6)
        self.v_pol = tk.StringVar(value="ia")
        for k, (rot, ajuda) in NOMES_POLITICA.items():
            ttk.Radiobutton(g, text=rot, value=k, variable=self.v_pol).pack(anchor="w")
            tk.Label(g, text="      " + ajuda, fg=w.CINZA_ESCURO).pack(anchor="w")
        g2 = w.Grupo(corpo, "Jogadores (as demais equipes ficam com a IA)")
        g2.pack(fill="both", expand=True)
        fr, self.tv = w.tabela(g2, [("nome", "Jogador"), ("cat", "Categoria"), ("eq", "Equipe")], 8,
                               {"nome": 180, "cat": 180, "eq": 220}, estica={"eq"}, cores=True)
        fr.pack(fill="both", expand=True)
        b = tk.Frame(g2)
        b.pack(fill="x", pady=4)
        w.Botao(b, "Adicionar jogador...", self.adicionar, padx=6).pack(side="left")
        w.Botao(b, "Remover", self.remover, padx=6).pack(side="left", padx=4)
        tk.Label(corpo, text=f"Categorias carregadas: {', '.join(c['categoria']['nome'] for c in st['categorias'].values())}"
                             f"  ·  temporada {st['ano']}", fg=w.CINZA_ESCURO).pack(anchor="w", pady=(4, 0))

    def _carregar(self):
        self.tv.delete(*self.tv.get_children())
        for i, j in enumerate(self.jogadores):
            c = self.st["categorias"][j["categoria"]]
            if j.get("nova_equipe"):
                eq = {"id": "nova", "nome": "", "cor": "#808080"}
                nome = "(equipe nova – o jogador cria)"
            else:
                eq = c["equipes"][j["equipe"]]
                nome = eq["nome"]
            self.tv.insert("", "end", iid=str(i), image=w.chip_equipe(eq, eq.get("nacionalidade")),
                           values=(j["nome"], c["categoria"]["nome"], nome))

    def adicionar(self):
        usadas = {(j["categoria"], j["equipe"]) for j in self.jogadores if j.get("equipe")}
        r = DialogoJogador(self, self.st, usadas).modal()
        if r:
            self.jogadores.append(r)
            self._carregar()

    def remover(self):
        sel = self.tv.selection()
        if sel:
            del self.jogadores[int(sel[0])]
            self._carregar()

    def criar(self):
        try:
            mp.criar_liga(self.st, self.v_nome.get(), self.jogadores, self.v_pol.get())
        except mp.ErroLiga as e:
            messagebox.showwarning("Nova liga", str(e), parent=self)
            return
        pasta = pasta_liga(self.v_nome.get())
        caminho = mp.salvar_liga(self.st, os.path.join(pasta, f"{mp._slug(self.v_nome.get())}_comissario.json"))
        dist = mp.exportar_para_jogadores(self.st, os.path.join(pasta, mp.nome_arquivo(self.st, "liga")))
        messagebox.showinfo("Nova liga", f"Liga criada.\n\nArquivo do comissário (guarde, não distribua):\n{caminho}"
                                         f"\n\nArquivo para enviar aos jogadores:\n{dist}", parent=self)
        self.app.comissario(self.st, caminho)


class DialogoJogador(w.Dialogo):
    def __init__(self, master, st, usadas):
        super().__init__(master, "Jogador", 560, 350)
        self.st = st
        f = self.corpo
        tk.Label(f, text="Nome do jogador:").grid(row=0, column=0, sticky="w", pady=2)
        self.v_nome = tk.StringVar()
        ttk.Entry(f, textvariable=self.v_nome, width=28).grid(row=0, column=1, sticky="w")
        tk.Label(f, text="Categoria:").grid(row=1, column=0, sticky="w", pady=2)
        self.cats = list(st["categorias"])
        self.cb_cat = ttk.Combobox(f, state="readonly", width=26,
                                   values=[st["categorias"][c]["categoria"]["nome"] for c in self.cats])
        self.cb_cat.grid(row=1, column=1, sticky="w")
        self.cb_cat.bind("<<ComboboxSelected>>", lambda e: self._equipes())
        tk.Label(f, text="Equipe:").grid(row=2, column=0, sticky="nw", pady=2)
        g = tk.Frame(f)
        g.grid(row=2, column=1, sticky="w")
        self.v_tipo = tk.StringVar(value="existente")
        ttk.Radiobutton(g, text="Equipe existente:", value="existente", variable=self.v_tipo,
                        command=self._tipo).grid(row=0, column=0, sticky="w")
        self.cb_eq = ttk.Combobox(g, state="readonly", width=24)
        self.cb_eq.grid(row=1, column=0, sticky="w", padx=(18, 0))
        ttk.Radiobutton(g, text="Equipe nova – o jogador cria ao abrir a liga", value="nova", variable=self.v_tipo,
                        command=self._tipo).grid(row=2, column=0, sticky="w", pady=(4, 0))
        tk.Label(g, text="Nome, país, cores e o carro inicial (desenvolvimento ou compra, conforme a categoria) "
                         "são escolhidos pelo jogador e vão nas ordens dele.", fg=w.CINZA_ESCURO, wraplength=330,
                 justify="left").grid(row=3, column=0, sticky="w", padx=(18, 0))
        tk.Label(f, text="Senha:").grid(row=3, column=0, sticky="w", pady=2)
        self.v_s1, self.v_s2 = tk.StringVar(), tk.StringVar()
        ttk.Entry(f, textvariable=self.v_s1, show="*", width=20).grid(row=3, column=1, sticky="w")
        tk.Label(f, text="Confirme a senha:").grid(row=4, column=0, sticky="w", pady=2)
        ttk.Entry(f, textvariable=self.v_s2, show="*", width=20).grid(row=4, column=1, sticky="w")
        tk.Label(f, text="O jogador digita a senha para abrir a liga e assinar as ordens.", fg=w.CINZA_ESCURO,
                 wraplength=420, justify="left").grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.usadas = usadas
        self.cb_cat.current(0)
        self._equipes()
        w.Botao(self.rodape, "Cancelar", self.cancelar, largura=10).pack(side="right", padx=2)
        w.Botao(self.rodape, "OK", self.ok, largura=10).pack(side="right", padx=2)

    def _tipo(self):
        self.cb_eq.configure(state="readonly" if self.v_tipo.get() == "existente" else "disabled")

    def _equipes(self):
        cid = self.cats[self.cb_cat.current()]
        self.equipes = [e for e in self.st["categorias"][cid]["equipes"].values()
                        if e.get("ativa") and (cid, e["id"]) not in self.usadas]
        self.cb_eq.configure(values=[e["nome"] for e in self.equipes])
        if self.equipes:
            self.cb_eq.current(0)

    def ok(self):
        if not self.v_nome.get().strip() or not self.v_s1.get():
            messagebox.showwarning("Jogador", "Informe nome e senha.", parent=self)
            return
        if self.v_s1.get() != self.v_s2.get():
            messagebox.showwarning("Jogador", "As senhas não conferem.", parent=self)
            return
        r = {"nome": self.v_nome.get().strip(), "categoria": self.cats[self.cb_cat.current()],
             "senha": self.v_s1.get()}
        if self.v_tipo.get() == "nova":
            r["nova_equipe"] = True
        else:
            i = self.cb_eq.current()
            if i < 0 or not self.equipes:
                return
            r["equipe"] = self.equipes[i]["id"]
        self.resultado = r
        self.destroy()


# ===================================================================== comissário
class TelaComissario(tk.Frame):
    def __init__(self, master, app, st, caminho):
        super().__init__(master, bg=w.CINZA)
        self.app, self.st, self.caminho = app, st, caminho
        m = st["multiplayer"]
        topo = tk.Frame(self)
        topo.pack(fill="x", padx=4, pady=(4, 2))
        caixa = tk.Frame(topo, bg=w.AZUL, relief="sunken", bd=2)
        caixa.pack(side="right", padx=(4, 0))
        self.lbl_semana = tk.Label(caixa, text="", bg=w.AZUL, fg=w.BRANCO, font=(w.FONTE[0], 15, "bold"), padx=10)
        self.lbl_semana.pack()
        self.lbl_sub = tk.Label(caixa, text="", bg=w.AZUL, fg="#ffff80", font=w.FONTE_NEGRITO, padx=10)
        self.lbl_sub.pack()
        self.titulo = w.BarraTitulo(topo, "")
        self.titulo.pack(side="left", fill="x", expand=True, anchor="n")
        rod = tk.Frame(self, padx=6, pady=4)
        rod.pack(fill="x", side="bottom")
        w.Botao(rod, "Rodar semana  >>", self.rodar, largura=16, font=w.FONTE_NEGRITO).pack(side="right", padx=4)
        self.status = w.BarraStatus(rod)
        self.status.pack(side="left", fill="x", expand=True)
        self.st_msg = self.status.campo("", expandir=True)
        corpo = tk.Frame(self, padx=6, pady=2)
        corpo.pack(fill="both", expand=True)
        g = w.Grupo(corpo, "Jogadores – ordens desta semana")
        g.pack(fill="x")
        fr, self.tv = w.tabela(g, [("nome", "Jogador"), ("eq", "Equipe"), ("est", "Situação")], 6,
                               {"nome": 180, "eq": 220, "est": 220}, estica={"est"}, cores=True)
        fr.pack(fill="x")
        b = tk.Frame(g)
        b.pack(fill="x", pady=4)
        w.Botao(b, "Importar ordens...", self.importar, padx=6).pack(side="left")
        w.Botao(b, "Pular jogador (IA nesta semana)", self.pular, padx=6).pack(side="left", padx=4)
        w.Botao(b, "Exportar arquivo para os jogadores...", self.exportar, padx=6).pack(side="left")
        w.Botao(b, "Exportar para HTML...", self.exportar_html, padx=6).pack(side="left", padx=4)
        self.lbl_pol = tk.Label(g, text="", fg=w.CINZA_ESCURO, anchor="w", justify="left")
        self.lbl_pol.pack(fill="x")
        # --- caixa de entrada: pasta compartilhada, prazo, importação em lote, histórico
        gc = w.Grupo(corpo, "Caixa de entrada da liga")
        gc.pack(fill="x", pady=(6, 0))
        lc = tk.Frame(gc)
        lc.pack(fill="x")
        self.lbl_pasta = tk.Label(lc, text="", anchor="w", justify="left")
        self.lbl_pasta.pack(side="left", fill="x", expand=True)
        w.Botao(lc, "Pasta compartilhada...", self.escolher_pasta, padx=6).pack(side="left", padx=2)
        w.Botao(lc, "Desligar", self.desligar_pasta, padx=6).pack(side="left")
        w.Botao(lc, "Pasta privada do bot...", self.escolher_privada, padx=6).pack(side="left", padx=(8, 0))
        lc2 = tk.Frame(gc)
        lc2.pack(fill="x", pady=(4, 0))
        auto = m.setdefault("auto", {})
        self.v_todas = tk.BooleanVar(value=bool(auto.get("todas")))
        self.v_prazo = tk.BooleanVar(value=bool(auto.get("prazo")))
        ttk.Checkbutton(lc2, text="Rodar sozinha quando chegarem todas as ordens", variable=self.v_todas,
                        command=self._auto).pack(side="left")
        ttk.Checkbutton(lc2, text="Rodar sozinha no prazo", variable=self.v_prazo,
                        command=self._auto).pack(side="left", padx=10)
        lc3 = tk.Frame(gc)
        lc3.pack(fill="x", pady=(4, 2))
        w.Botao(lc3, "Prazo desta semana...", self.definir_prazo, padx=6).pack(side="left")
        w.Botao(lc3, "Importar todas de uma pasta...", self.importar_pasta, padx=6).pack(side="left", padx=4)
        w.Botao(lc3, "Histórico de envios...", self.historico_envios, padx=6).pack(side="left")
        self.lbl_prazo = tk.Label(lc3, text="", fg=w.CINZA_ESCURO, anchor="w")
        self.lbl_prazo.pack(side="left", padx=10)
        self.vistos = {}
        g2 = w.Grupo(corpo, "Notícias")
        g2.pack(fill="both", expand=True, pady=(6, 0))
        self.lb = tk.Listbox(g2, relief="sunken", bd=2)
        sb = ttk.Scrollbar(g2, orient="vertical", command=self.lb.yview)
        self.lb.configure(yscrollcommand=sb.set)
        self.lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._menu()
        self.atualizar()
        self.status_msg(f"Arquivo do comissário: {caminho}")
        app.root.title(f"AutoManager – Liga {m['nome']} (comissário)")
        self._agendado = None
        if self.pasta():
            self._publicar()
        self._vigiar()

    def status_msg(self, t):
        self.st_msg.configure(text=t)

    def _menu(self):
        from . import historico_tela
        app, st = self.app, self.st
        mb = tk.Menu(app.root)
        arq = tk.Menu(mb)
        arq.add_command(label="Salvar liga", command=self.salvar)
        arq.add_command(label="Exportar arquivo para os jogadores...", command=self.exportar)
        arq.add_separator()
        arq.add_command(label="Política para ordens ausentes...", command=self.politica)
        arq.add_separator()
        arq.add_command(label="Fechar liga", command=app.fechar_jogo)
        mb.add_cascade(label="Arquivo", menu=arq, underline=0)
        hist = tk.Menu(mb)
        hist.add_command(label="Temporada atual...", command=lambda: historico_tela.JanelaTemporadaAtual(self, st).modal())
        hist.add_command(label="Temporadas anteriores...",
                         command=lambda: historico_tela.JanelaTemporadasAnteriores(self, st).modal())
        hist.add_command(label="Pontuação total (hall da fama)...",
                         command=lambda: historico_tela.JanelaTotal(self, st).modal())
        mb.add_cascade(label="Histórico", menu=hist, underline=0)
        app.root.config(menu=mb)

    def atualizar(self):
        st, m = self.st, self.st["multiplayer"]
        from ..routines import SEMANAS_POR_TEMPORADA
        self.titulo.definir(f"Liga {m['nome']}  –  comissário")
        self.lbl_semana.configure(text=f"SEMANA {st['semana']} / {SEMANAS_POR_TEMPORADA}")
        eventos = [e["nome"] for c in st["categorias"].values() for e in c["calendario"]
                   if e.get("ativo") and e["semana"] == st["semana"]]
        self.lbl_sub.configure(text=f"{st['ano']} · {len(eventos)} evento(s)" if eventos else str(st["ano"]))
        self.tv.delete(*self.tv.get_children())
        recusas = caixa.recusas_da_semana(st)
        for jid, nome, eqn, est in mp.situacao(st):
            ult = next((x for x in reversed(m.get("envios", [])) if x["jogador"] == jid and x["resultado"] == "aceita"
                        and (x["ano"], x["semana"]) == (st["ano"], st["semana"])), None)
            if est == "ordens recebidas" and ult:
                est = f"ordens recebidas às {ult['quando'][-5:]}" + (" (atrasadas)" if ult.get("atrasado") else "")
            elif est == "aguardando" and jid in recusas:
                est = f"recusadas: {recusas[jid]}"
            j = m["jogadores"][jid]
            eq = st["categorias"][j["categoria"]]["equipes"].get(j["equipe"]) or {"id": "nova", "nome": "", "cor": "#808080"}
            self.tv.insert("", "end", iid=jid, image=w.chip_equipe(eq, eq.get("nacionalidade")),
                           values=(nome, eqn, est), tags=("cinza",) if j.get("eliminado") else ())
        pasta = self.pasta()
        privada = m.get("pasta_ordens_privada")
        self.lbl_pasta.configure(text=(f"Pasta compartilhada: {pasta}" if pasta else
                                       "Sem pasta compartilhada: os arquivos vão e voltam à mão (ou pelo bot).")
                                 + (f"\nPasta privada do bot: {privada}" if privada else ""))
        pr = caixa.prazo(st)
        self.lbl_prazo.configure(text=f"Prazo: {pr}" + (" (vencido)" if caixa.atrasado(st) else "") if pr
                                 else "Sem prazo nesta semana.")
        rot, ajuda = NOMES_POLITICA[m["politica"]]
        self.lbl_pol.configure(text=f"Política para ordens ausentes: {rot} – {ajuda}"
                                    + (f"\nEventos desta semana: {', '.join(eventos)}" if eventos else ""))
        self.lb.delete(0, "end")
        cats = st["categorias"]
        for n in reversed(st["noticias"][-400:]):
            nome_cat = cats[n["categoria"]]["categoria"]["nome"] if n.get("categoria") in cats else ""
            self.lb.insert("end", f"[{n['ano']} S{n['semana']:02d}] {nome_cat + ': ' if nome_cat else ''}{n['texto']}")
            if n.get("tipo") == "usuario":
                self.lb.itemconfigure("end", fg="#a00000")

    def salvar(self):
        mp.salvar_liga(self.st, self.caminho)
        self.status_msg(f"Liga salva em {self.caminho}")

    # ------------------------------------------------------------------ caixa de entrada
    def pasta(self):
        return self.st["multiplayer"].get("pasta_compartilhada")

    def escolher_pasta(self):
        d = filedialog.askdirectory(parent=self, title="Pasta compartilhada da liga (Drive, Dropbox, OneDrive...)")
        if not d:
            return
        if os.path.commonpath([os.path.abspath(self.caminho), os.path.abspath(d)]) == os.path.abspath(d):
            messagebox.showwarning("Pasta compartilhada", "Escolha outra pasta: o arquivo do comissário (com as "
                                                          "chaves dos jogadores) não pode ficar na pasta "
                                                          "compartilhada.", parent=self)
            return
        self.st["multiplayer"]["pasta_compartilhada"] = d
        self._publicar()
        self.salvar()
        self.atualizar()
        messagebox.showinfo("Pasta compartilhada", f"A liga foi publicada em:\n{d}\n\nOs jogadores abrem o "
                                                   f"liga.json dessa pasta; as ordens deles voltam para a subpasta "
                                                   f"ordens e são importadas sozinhas.", parent=self)

    def escolher_privada(self):
        """Pasta onde o bot do Discord grava as ordens recebidas, fora da pasta compartilhada (só o comissário vê).
        Vazio (cancelar) tira a pasta privada."""
        d = filedialog.askdirectory(parent=self, title="Pasta privada onde o bot grava as ordens (fora da pasta "
                                                       "compartilhada)")
        m = self.st["multiplayer"]
        if not d:
            m.pop("pasta_ordens_privada", None)
        elif self.pasta() and os.path.commonpath([os.path.abspath(d), os.path.abspath(self.pasta())]) == \
                os.path.abspath(self.pasta()):
            messagebox.showwarning("Pasta privada do bot", "A pasta privada tem de ficar fora da pasta compartilhada.",
                                   parent=self)
            return
        else:
            m["pasta_ordens_privada"] = d
        self.salvar()
        self.atualizar()

    def desligar_pasta(self):
        self.st["multiplayer"].pop("pasta_compartilhada", None)
        self.salvar()
        self.atualizar()

    def _auto(self):
        self.st["multiplayer"]["auto"] = {"todas": bool(self.v_todas.get()), "prazo": bool(self.v_prazo.get())}
        self.salvar()

    def _publicar(self):
        try:
            caixa.publicar(self.st, self.pasta(), caixa.recusas_da_semana(self.st))
        except OSError as e:
            self.status_msg(f"Não foi possível publicar na pasta compartilhada: {e}")

    def _vigiar(self):
        """A cada 5 s: importa as ordens novas da pasta compartilhada e, se marcado, roda a semana sozinha."""
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        pasta = self.pasta()
        privada = self.st["multiplayer"].get("pasta_ordens_privada")
        if (pasta and os.path.isdir(pasta)) or privada:
            res = caixa.varrer(self.st, pasta, self.vistos, privada)
            if res:
                self.salvar()
                if pasta:
                    caixa.escrever_status(self.st, pasta, caixa.recusas_da_semana(self.st))
                nomes = self.st["multiplayer"]["jogadores"]
                self.status_msg("; ".join(f"{nomes[j]['nome'] if j in nomes else os.path.basename(c)}: "
                                          f"{'ordens recebidas' if r == 'aceita' else r}" for c, j, r in res))
                self.atualizar()
        motivo = caixa.deve_rodar_sozinha(self.st)
        if motivo:
            self.rodar(auto=motivo)
        self._agendado = self.after(5000, self._vigiar)

    def definir_prazo(self):
        from tkinter import simpledialog
        atual = caixa.prazo(self.st) or ""
        r = simpledialog.askstring("Prazo desta semana", "Data e hora (AAAA-MM-DD HH:MM). Vazio = sem prazo.",
                                   initialvalue=atual, parent=self)
        if r is None:
            return
        try:
            caixa.definir_prazo(self.st, r)
        except ValueError:
            messagebox.showwarning("Prazo desta semana", "Use o formato AAAA-MM-DD HH:MM (ex.: 2026-12-01 20:00).",
                                   parent=self)
            return
        self.salvar()
        if self.pasta():
            caixa.escrever_status(self.st, self.pasta(), caixa.recusas_da_semana(self.st))
        self.atualizar()

    def importar_pasta(self):
        d = filedialog.askdirectory(parent=self, title="Pasta com os arquivos de ordens",
                                    initialdir=os.path.dirname(self.caminho))
        if not d:
            return
        self._mostrar_importacao(caixa.importar_pasta(self.st, d))

    def _mostrar_importacao(self, res):
        if any(r == "aceita" for _, _, r in res):
            self.salvar()
            if self.pasta():
                caixa.escrever_status(self.st, self.pasta(), caixa.recusas_da_semana(self.st))
        self.atualizar()
        if not res:
            messagebox.showinfo("Importar ordens", "Nenhum arquivo de ordens encontrado.", parent=self)
            return
        nomes = self.st["multiplayer"]["jogadores"]
        linhas = [f"{os.path.basename(c)} – {nomes[j]['nome'] if j in nomes else '?'}: "
                  f"{'aceitas' if r == 'aceita' else 'recusadas – ' + r}" for c, j, r in res]
        messagebox.showinfo("Importar ordens", "\n\n".join(linhas), parent=self)

    def historico_envios(self):
        DialogoEnvios(self, self.st).modal()

    def importar(self):
        caminhos = filedialog.askopenfilenames(parent=self, title="Arquivos de ordens dos jogadores",
                                               initialdir=os.path.dirname(self.caminho),
                                               filetypes=[("Ordens (JSON)", "*.json"), ("Todos", "*.*")])
        if caminhos:
            self._mostrar_importacao(caixa.importar_arquivos(self.st, caminhos))

    def pular(self):
        sel = self.tv.selection()
        if not sel:
            messagebox.showinfo("Pular jogador", "Selecione o jogador.", parent=self)
            return
        mp.pular(self.st, sel[0])
        self.atualizar()

    def politica(self):
        r = DialogoPolitica(self, self.st["multiplayer"]["politica"]).modal()
        if r:
            self.st["multiplayer"]["politica"] = r
            self.salvar()
            self.atualizar()

    def exportar(self):
        caminho = filedialog.asksaveasfilename(
            parent=self, title="Arquivo da liga para os jogadores", initialdir=os.path.dirname(self.caminho),
            initialfile=mp.nome_arquivo(self.st, "liga"), defaultextension=".json",
            filetypes=[("Liga (JSON)", "*.json")])
        if caminho:
            mp.exportar_para_jogadores(self.st, caminho)
            self.status_msg(f"Arquivo para os jogadores: {caminho}")

    def exportar_html(self):
        """Site da liga visto pelo comissário: finanças de todas as equipes de jogadores."""
        from .exportar_tela import exportar
        exportar(self, self.st)

    def rodar(self, auto=None):
        """auto: 'todas' ou 'prazo' quando a semana roda sozinha (sem perguntas; o resultado vai para a barra)."""
        ok, pend = mp.pode_rodar(self.st)
        if auto and not ok:
            return
        if not ok:
            nomes = ", ".join(self.st["multiplayer"]["jogadores"][j]["nome"] for j in pend)
            messagebox.showwarning("Rodar semana", f"Faltam as ordens de: {nomes}.\n\nImporte os arquivos ou pule os "
                                                   "jogadores.", parent=self)
            return
        falta = [self.st["multiplayer"]["jogadores"][j]["nome"] for j in mp.faltando(self.st)]
        if falta and not auto and not messagebox.askyesno(
                "Rodar semana", f"Sem ordens de: {', '.join(falta)}.\nPolítica: "
                                f"{NOMES_POLITICA[self.st['multiplayer']['politica']][0]}.\n\nRodar a semana?",
                parent=self):
            return
        self.config(cursor="watch")
        self.update()
        try:
            r = mp.rodar_semana(self.st, random.Random())
        except mp.ErroLiga as e:
            if auto:
                self.status_msg(f"A semana não rodou sozinha: {e}")
            else:
                messagebox.showwarning("Rodar semana", str(e), parent=self)
            return
        finally:
            self.config(cursor="")
        self.salvar()
        dist = mp.exportar_para_jogadores(self.st, os.path.join(os.path.dirname(self.caminho),
                                                                mp.nome_arquivo(self.st, "liga")))
        nomes = self.st["multiplayer"]["jogadores"]
        linhas = [f"Semana concluída. {len(r['noticias'])} notícia(s).",
                  f"Ordens aplicadas: {', '.join(nomes[j]['nome'] for j in r['recebidas']) or 'nenhuma'}"]
        if r["repetidas"]:
            linhas.append(f"Últimas ordens repetidas: {', '.join(nomes[j]['nome'] for j in r['repetidas'])}")
        if r["ia"]:
            linhas.append(f"Conduzidos pela IA: {', '.join(nomes[j]['nome'] for j in r['ia'])}")
        if r["erros"]:
            linhas.append(f"Ordens não executadas: {len(r['erros'])} (veja as notícias)")
        if self.pasta():
            self._publicar()
            linhas.append(f"\nPublicada na pasta compartilhada:\n{self.pasta()}")
        else:
            linhas.append(f"\nArquivo para enviar aos jogadores:\n{dist}")
        self.vistos.clear()
        self.atualizar()
        if auto:
            self.status_msg(("Todas as ordens chegaram" if auto == "todas" else "Prazo vencido")
                            + f": semana rodada sozinha. {linhas[0]}")
        else:
            messagebox.showinfo("Rodar semana", "\n".join(linhas), parent=self)

    def destroy(self):
        if getattr(self, "_agendado", None):
            try:
                self.after_cancel(self._agendado)
            except tk.TclError:
                pass
        super().destroy()


class DialogoEnvios(w.Dialogo):
    """Histórico da caixa de entrada: cada arquivo de ordens recebido, quando e se foi aceito."""

    def __init__(self, master, st):
        super().__init__(master, "Histórico de envios", 900, 460)
        m = st["multiplayer"]
        fr, tv = w.tabela(self.corpo, [("sem", "Semana"), ("jog", "Jogador"), ("quando", "Recebido em"),
                                       ("arq", "Arquivo"), ("res", "Resultado")], 16,
                          {"sem": 80, "jog": 120, "quando": 120, "arq": 180, "res": 360}, estica={"res"})
        fr.pack(fill="both", expand=True)
        for x in reversed(m.get("envios", [])):
            j = m["jogadores"].get(x["jogador"], {})
            res = "aceitas" if x["resultado"] == "aceita" else f"recusadas – {x['resultado']}"
            tv.insert("", "end", values=(f"{x['semana']}/{x['ano']}", j.get("nome", x["jogador"]),
                                         x["quando"] + (" (atrasadas)" if x.get("atrasado") else ""), x["arquivo"], res))
        if not m.get("envios"):
            tk.Label(self.corpo, text="Nenhum arquivo recebido ainda.").pack(anchor="w")
        w.Botao(self.rodape, "Fechar", self.destroy, largura=10).pack(side="right")


class DialogoPolitica(w.Dialogo):
    def __init__(self, master, atual):
        super().__init__(master, "Ordens ausentes", 520, 260)
        self.v = tk.StringVar(value=atual)
        for k, (rot, ajuda) in NOMES_POLITICA.items():
            ttk.Radiobutton(self.corpo, text=rot, value=k, variable=self.v).pack(anchor="w")
            tk.Label(self.corpo, text="      " + ajuda, fg=w.CINZA_ESCURO, wraplength=470,
                     justify="left").pack(anchor="w")
        w.Botao(self.rodape, "Cancelar", self.cancelar, largura=10).pack(side="right", padx=2)
        w.Botao(self.rodape, "OK", self.ok, largura=10).pack(side="right", padx=2)

    def ok(self):
        self.resultado = self.v.get()
        self.destroy()


# ===================================================================== jogador
class DialogoEntrar(w.Dialogo):
    def __init__(self, master, st_liga):
        super().__init__(master, "Entrar na liga", 420, 260)
        m = st_liga["multiplayer"]
        self.st_liga = st_liga
        w.BarraTitulo(self.corpo, f"Liga {m['nome']} – semana {st_liga['semana']}/{st_liga['ano']}").pack(fill="x")
        self.ids = [jid for jid, j in m["jogadores"].items() if not j.get("eliminado")]
        f = tk.Frame(self.corpo)
        f.pack(fill="x", pady=8)
        tk.Label(f, text="Jogador:").grid(row=0, column=0, sticky="w", pady=2)
        rot = []
        for jid in self.ids:
            j = m["jogadores"][jid]
            eq = st_liga["categorias"][j["categoria"]]["equipes"].get(j.get("equipe"))
            rot.append(f"{j['nome']} – {eq['nome'] if eq else '(equipe nova – a criar)'}")
        self.cb = ttk.Combobox(f, state="readonly", width=34, values=rot)
        self.cb.grid(row=0, column=1, sticky="w")
        if rot:
            self.cb.current(0)
        tk.Label(f, text="Senha:").grid(row=1, column=0, sticky="w", pady=2)
        self.v_senha = tk.StringVar()
        en = ttk.Entry(f, textvariable=self.v_senha, show="*", width=20)
        en.grid(row=1, column=1, sticky="w")
        en.focus_set()
        self.bind("<Return>", lambda e: self.ok())
        w.Botao(self.rodape, "Cancelar", self.cancelar, largura=10).pack(side="right", padx=2)
        w.Botao(self.rodape, "Entrar", self.ok, largura=10).pack(side="right", padx=2)

    def ok(self):
        if self.cb.current() < 0:
            return
        try:
            self.resultado = mp.entrar(self.st_liga, self.ids[self.cb.current()], self.v_senha.get())
        except mp.ErroLiga as e:
            messagebox.showwarning("Entrar", str(e), parent=self)
            return
        self.destroy()


# ===================================================================== plano de evento
def eventos_da_semana(st):
    cid = st["usuario"]["categoria"]
    c = st["categorias"][cid]
    regras = c["categoria"]["regras"]
    return [e for e in c["calendario"] if e.get("ativo") and e["semana"] == st["semana"]
            and (e["especie"] == "corrida" or regras.get("testes_coletivos"))]


class DialogoPlanoEvento(w.Dialogo):
    """Plano dos eventos da semana para os pilotos da equipe do jogador."""

    def __init__(self, master, st):
        super().__init__(master, "Plano do evento", 900, 690)
        self.st = st
        self.sessao = mp.sessao(st)
        cid = st["usuario"]["categoria"]
        cat = st["categorias"][cid]["categoria"]
        disp = cat["pneus"].get("compostos_disponiveis") or list(cat["pneus"]["compostos"])
        self.comp = {k: v for k, v in cat["pneus"]["compostos"].items() if k in disp}
        self.troca = cat["regras_pitstop"].get("troca_de_pneus", True)
        self.dois_compostos = bool(cat["regras_pitstop"].get("dois_compostos_secos")) and self.troca
        self.nomes_comp = {k: v["nome"] for k, v in self.comp.items()}
        self.reabastece = bool(cat["regras_pitstop"].get("reabastecimento"))
        self.eventos = eventos_da_semana(st)
        self.widgets = {}
        if not self.eventos:
            tk.Label(self.corpo, text="Não há evento da sua categoria nesta semana.").pack(anchor="w")
            w.Botao(self.rodape, "Fechar", self.destroy, largura=10).pack(side="right")
            return
        tk.Label(self.corpo, justify="left", anchor="w", wraplength=860, fg=w.CINZA_ESCURO,
                 text="Você não acompanha o evento ao vivo: defina o acerto, os pneus, as ordens e a estratégia de "
                      "cada piloto. 'Automático' deixa a escolha com a equipe. Se o clima pedir outro tipo de pneu "
                      "(chuva/seco), a equipe troca e assume a estratégia.").pack(fill="x")
        nb_ev = ttk.Notebook(self.corpo)
        nb_ev.pack(fill="both", expand=True, pady=4)
        for ev in self.eventos:
            fr_ev = tk.Frame(nb_ev)
            nb_ev.add(fr_ev, text=f"{ev['nome']} ({'corrida' if ev['especie'] == 'corrida' else 'teste coletivo'})")
            nb_p = ttk.Notebook(fr_ev)
            nb_p.pack(fill="both", expand=True)
            inscritos = [i for i in montar_inscritos(st, cid, st["usuario"]["equipe"], ev) if i["usuario"]]
            if not inscritos:
                tk.Label(fr_ev, text="Sua equipe não tem carro completo ou pilotos para este evento.").pack()
            for i in inscritos:
                p = i["piloto"]
                atual = self.sessao["planos"].get(ev["id"], {}).get(p["id"]) or planos_evento.plano_padrao()
                fr_p = tk.Frame(nb_p, padx=4, pady=4)
                nb_p.add(fr_p, text=p["nome"])
                grupos = ["treino"] if ev["especie"] == "treino" else list(planos_evento.GRUPOS)
                self.widgets[(ev["id"], p["id"])] = self._piloto(fr_p, atual, grupos, ev)
        w.Botao(self.rodape, "Cancelar", self.cancelar, largura=10).pack(side="right", padx=2)
        w.Botao(self.rodape, "Gravar plano", self.ok, largura=14).pack(side="right", padx=2)

    def _piloto(self, master, plano, grupos, ev):
        nomes = {"treino": "Treinos livres" if ev["especie"] == "corrida" else "Dias de teste",
                 "classificacao": "Classificação", "corrida": "Corrida"}
        out = {}
        for col, grupo in enumerate(grupos):
            g = w.Grupo(master, nomes[grupo])
            g.grid(row=0, column=col, sticky="nsew", padx=3)
            master.columnconfigure(col, weight=1)
            dados = plano.get(grupo) or planos_evento.grupo_padrao(grupo)
            v = {"acerto": {}, "ordens": {}}
            r = 0
            tk.Label(g, text="Acerto", font=w.FONTE_NEGRITO).grid(row=r, column=0, sticky="w")
            r += 1
            for k in PARAMETROS_ACERTO:
                var = tk.IntVar(value=dados["acerto"].get(k, 50))
                tk.Label(g, text=NOMES_ACERTO[k], anchor="w").grid(row=r, column=0, sticky="w")
                tk.Scale(g, from_=0, to=100, orient="horizontal", variable=var, length=110, bd=1, highlightthickness=0,
                         troughcolor="#dfdfdf", sliderlength=14, width=9).grid(row=r, column=1)
                v["acerto"][k] = var
                r += 1
            tk.Label(g, text="Ordens ao piloto", font=w.FONTE_NEGRITO).grid(row=r, column=0, sticky="w", pady=(4, 0))
            r += 1
            for k in ORDENS:
                var = tk.IntVar(value=dados["ordens"].get(k, 0))
                tk.Label(g, text=NOMES_ORDENS[k], anchor="w").grid(row=r, column=0, sticky="w")
                tk.Scale(g, from_=-2, to=2, resolution=1, orient="horizontal", variable=var, length=110, bd=1,
                         highlightthickness=0, troughcolor="#dfdfdf", sliderlength=14, width=9).grid(row=r, column=1)
                v["ordens"][k] = var
                r += 1
            opcoes = ["Automático"] + [self.nomes_comp[k] for k in self.comp]
            tk.Label(g, text="Pneu" if grupo != "corrida" else "Pneu de largada").grid(row=r, column=0, sticky="w",
                                                                                     pady=(4, 0))
            cb = ttk.Combobox(g, state="readonly", values=opcoes, width=14)
            cb.set(self.nomes_comp.get(dados.get("pneu"), "Automático"))
            cb.grid(row=r, column=1, sticky="w", pady=(4, 0))
            v["pneu"] = cb
            r += 1
            if grupo == "corrida":
                if self.reabastece:
                    tk.Label(g, text="Combustível (voltas)").grid(row=r, column=0, sticky="w")
                    v["combustivel"] = tk.StringVar(value="" if dados.get("combustivel") is None
                                                    else str(dados["combustivel"]))
                    ttk.Entry(g, textvariable=v["combustivel"], width=6).grid(row=r, column=1, sticky="w")
                    tk.Label(g, text="(vazio = automático)", fg=w.CINZA_ESCURO).grid(row=r + 1, column=1, sticky="w")
                    r += 2
                tk.Label(g, text="Paradas", font=w.FONTE_NEGRITO).grid(row=r, column=0, sticky="w", pady=(4, 0))
                r += 1
                manual = isinstance(dados.get("paradas"), list)
                v["modo_par"] = tk.StringVar(value="manual" if manual else "auto")
                ttk.Radiobutton(g, text="Automático (equipe decide)", value="auto",
                                variable=v["modo_par"]).grid(row=r, column=0, columnspan=2, sticky="w")
                r += 1
                ttk.Radiobutton(g, text="Plano de stints:", value="manual",
                                variable=v["modo_par"]).grid(row=r, column=0, columnspan=2, sticky="w")
                r += 1
                v["stints"] = []
                stints = dados["paradas"] if manual else []
                for i in range(4):
                    fr = tk.Frame(g)
                    fr.grid(row=r, column=0, columnspan=2, sticky="w", padx=12)
                    tk.Label(fr, text=f"Stint {i + 1}:").pack(side="left")
                    cbs = ttk.Combobox(fr, state="readonly", values=["-"] + [self.nomes_comp[k] for k in self.comp],
                                       width=12)
                    vv = tk.StringVar(value=str(stints[i][1]) if i < len(stints) else "")
                    cbs.set(self.nomes_comp.get(stints[i][0], "-") if i < len(stints) else "-")
                    cbs.pack(side="left", padx=2)
                    ttk.Spinbox(fr, from_=1, to=200, textvariable=vv, width=5).pack(side="left")
                    tk.Label(fr, text="voltas").pack(side="left", padx=2)
                    v["stints"].append((cbs, vv))
                    r += 1
                tk.Label(g, text=f"Corrida: {ev.get('voltas_corrida', '?')} voltas. O 1º stint define o pneu de "
                                 "largada.", fg=w.CINZA_ESCURO, wraplength=250, justify="left").grid(
                    row=r, column=0, columnspan=2, sticky="w")
            out[grupo] = v
        return out

    def _ler(self, v, grupo):
        inv = {n: k for k, n in self.nomes_comp.items()}
        d = {"acerto": {k: int(x.get()) for k, x in v["acerto"].items()},
             "ordens": {k: int(x.get()) for k, x in v["ordens"].items()},
             "pneu": inv.get(v["pneu"].get(), "auto")}
        if grupo == "corrida":
            d["combustivel"] = None
            if "combustivel" in v and v["combustivel"].get().strip():
                try:
                    d["combustivel"] = max(1, int(v["combustivel"].get()))
                except ValueError:
                    raise ValueError("Combustível: use um número de voltas.")
            d["paradas"] = "auto"
            if v["modo_par"].get() == "manual":
                stints = []
                for cb, vv in v["stints"]:
                    if cb.get() in inv:
                        try:
                            stints.append([inv[cb.get()], max(1, int(vv.get()))])
                        except ValueError:
                            raise ValueError("Informe as voltas de cada stint.")
                if not stints:
                    raise ValueError("Plano de stints vazio: escolha os pneus e as voltas, ou use automático.")
                d["paradas"] = stints
                d["pneu"] = stints[0][0]
        return d

    def ok(self):
        avisos = []
        try:
            novos = {}
            for (evid, pid), grupos in self.widgets.items():
                plano = {g: self._ler(v, g) for g, v in grupos.items()}
                novos.setdefault(evid, {})[pid] = plano
                ev = next(e for e in self.eventos if e["id"] == evid)
                par = plano.get("corrida", {}).get("paradas")
                if isinstance(par, list) and sum(n for _, n in par) != ev.get("voltas_corrida"):
                    avisos.append(f"{self.st['pilotos'][pid]['nome']}: os stints somam {sum(n for _, n in par)} "
                                  f"voltas (corrida de {ev.get('voltas_corrida')}). O último stint vai até o fim.")
                if isinstance(par, list) and self.dois_compostos:
                    secos = {k for k, _ in par if self.comp[k].get("tipo") == "seco"}
                    if len(secos) < 2 and len(secos) == len({k for k, _ in par}):
                        avisos.append(f"{self.st['pilotos'][pid]['nome']}: a categoria exige dois compostos secos "
                                      f"diferentes na corrida seca; este plano usa só um.")
        except ValueError as e:
            messagebox.showwarning("Plano do evento", str(e), parent=self)
            return
        for evid, d in novos.items():
            self.sessao["planos"].setdefault(evid, {}).update(d)
        if avisos:
            messagebox.showinfo("Plano do evento", "\n".join(avisos), parent=self)
        self.destroy()


def resumo_jogador(st):
    """Texto curto do que já está nas ordens desta semana."""
    s = mp.sessao(st)
    n_planos = sum(len(v) for v in s.get("planos", {}).values())
    return f"{len(s.get('acoes', []))} ação(ões) e {n_planos} plano(s) de piloto nas ordens desta semana."


def caminho_ordens_padrao(st, pasta):
    """liga_ano_semana_jogador_equipe.ordens.json – o nome da equipe identifica o arquivo."""
    u = st["usuario"]
    eq = st["categorias"][u["categoria"]]["equipes"].get(u.get("equipe")) or {}
    sufixo = mp.sessao(st)["jogador"] + (f"_{mp._slug(eq['nome'])}" if eq.get("nome") else "")
    return os.path.join(pasta, mp.nome_arquivo(st, sufixo).replace(".json", ".ordens.json"))


def nome_equipe(st):
    return state.equipe_usuario(st)["nome"]
