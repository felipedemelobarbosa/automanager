"""Telas do mercado: pilotos, chassis/motor e patrocinadores."""
import tkinter as tk
from tkinter import ttk, messagebox

from .. import mercado, ratings, contratos, acoes
from ..db import NOMES_ATRIBUTOS, ATRIBUTOS_PILOTO
from ..util import dinheiro
from . import win9x as w


def _ctx(st):
    cid, eid = st["usuario"]["categoria"], st["usuario"]["equipe"]
    c = st["categorias"][cid]
    return cid, c, c["equipes"][eid]


def _ligar_total(v, label, st, cid, valor_por_corrida):
    """Mostra o valor total do contrato (valor/corrida × corridas cobertas) e atualiza quando os campos mudam."""
    def atualizar(*_):
        try:
            valor = valor_por_corrida()
            n = mercado.corridas_do_contrato(st, cid, int(v["duracao"].get()), v["unidade"].get(), inicio_de(v))
        except (ValueError, tk.TclError, TypeError):
            label.configure(text="Total do contrato: -")
            return
        if valor is None:
            label.configure(text="Total do contrato: -")
            return
        label.configure(text=f"Total do contrato: {dinheiro(valor * n)}  ({n} corrida(s) × {dinheiro(valor)})")
    for k in ("duracao", "unidade", "inicio", "ano"):
        v[k].trace_add("write", atualizar)
    return atualizar


def inicio_de(v):
    """Valor do início para as ações: 'agora', 'proxima' ou o ano escolhido (int)."""
    if v["inicio"].get() == "ano":
        try:
            return int(v["ano"].get())
        except (ValueError, tk.TclError):
            return "proxima"
    return v["inicio"].get()


def _form_contrato(master, linha, unidades=("temporadas", "corridas"), com_inicio=True, ano_atual=None):
    """Campos comuns: duração, unidade e início (agora, próxima temporada ou um ano). Retorna dict de variáveis."""
    v = {"duracao": tk.IntVar(value=1), "unidade": tk.StringVar(value=unidades[0]),
         "inicio": tk.StringVar(value="proxima"), "ano": tk.IntVar(value=(ano_atual or 2000) + 2)}
    tk.Label(master, text="Duração:").grid(row=linha, column=0, sticky="w", pady=2)
    f = tk.Frame(master)
    f.grid(row=linha, column=1, sticky="w")
    ttk.Spinbox(f, from_=1, to=60, textvariable=v["duracao"], width=5).pack(side="left")
    ttk.Combobox(f, values=list(unidades), textvariable=v["unidade"], state="readonly", width=11).pack(side="left",
                                                                                                        padx=4)
    if com_inicio:
        tk.Label(master, text="Início:").grid(row=linha + 1, column=0, sticky="nw", pady=2)
        f2 = tk.Frame(master)
        f2.grid(row=linha + 1, column=1, sticky="w")
        l1 = tk.Frame(f2)
        l1.pack(anchor="w")
        ttk.Radiobutton(l1, text="Agora", value="agora", variable=v["inicio"]).pack(side="left")
        ttk.Radiobutton(l1, text="Próxima temporada", value="proxima", variable=v["inicio"]).pack(side="left", padx=6)
        if ano_atual:                                  # qualquer temporada futura (sem limite), numa 2ª linha
            l2 = tk.Frame(f2)
            l2.pack(anchor="w")
            ttk.Radiobutton(l2, text="No ano:", value="ano", variable=v["inicio"]).pack(side="left")
            ttk.Spinbox(l2, from_=ano_atual + 2, to=ano_atual + 100, textvariable=v["ano"], width=6,
                        command=lambda: v["inicio"].set("ano")).pack(side="left", padx=(2, 0))
    return v


# ====================================================================== pilotos
class JanelaPilotos(w.Dialogo):
    def __init__(self, master, st):
        super().__init__(master, "Mercado – Pilotos", 1140, 670)
        self.st = st
        self.cid, self.c, self.eq = _ctx(st)
        self.cat = self.c["categoria"]
        w.BarraTitulo(self.corpo, "Mercado de pilotos – livres ou com contrato terminando").pack(fill="x")
        topo = tk.Frame(self.corpo)
        topo.pack(fill="x", pady=4)
        self.filtro = tk.StringVar(value="proxima")
        ttk.Radiobutton(topo, text="Disponíveis agora (sem contrato)", value="agora", variable=self.filtro,
                        command=self.carregar).pack(side="left")
        ttk.Radiobutton(topo, text="Disponíveis para a próxima temporada", value="proxima", variable=self.filtro,
                        command=self.carregar).pack(side="left", padx=8)
        ttk.Radiobutton(topo, text="Com contrato (multa)", value="contrato", variable=self.filtro,
                        command=self.carregar).pack(side="left")
        tk.Label(topo, text="Categoria de origem:").pack(side="left", padx=(16, 2))
        self.cats = ["Todas"] + [x["categoria"]["nome"] for x in st["categorias"].values()]
        self.cb_cat = ttk.Combobox(topo, values=self.cats, state="readonly", width=18)
        self.cb_cat.current(0)
        self.cb_cat.pack(side="left")
        self.cb_cat.bind("<<ComboboxSelected>>", lambda e: self.carregar())
        self.lbl_vagas = tk.Label(self.corpo, text="", anchor="w", fg=w.AZUL)
        self.lbl_vagas.pack(fill="x")

        meio = tk.Frame(self.corpo)
        meio.pack(fill="both", expand=True)
        cols = [("nome", "Piloto"), ("nac", "Nacionalidade"), ("idade", "Idade"), ("cat", "Categoria"),
                ("sit", "Situação"), ("nota", "Nota"), ("pedido", "Pede/corrida (est.)"), ("multa", "Multa")]
        fr, self.tv = w.tabela(meio, cols, 18, {"nome": 130, "nac": 85, "idade": 36, "cat": 85, "sit": 120,
                                                "nota": 36, "pedido": 132, "multa": 80},
                               {"idade": "center", "nota": "center", "pedido": "e", "multa": "e"}, estica={"nome"},
                               cores=True)
        fr.pack(side="left", fill="both", expand=True)
        self.tv.bind("<<TreeviewSelect>>", lambda e: self.detalhes())

        dir_ = tk.Frame(meio, padx=6)
        dir_.pack(side="left", fill="y")
        topo_dir = tk.Frame(dir_)
        topo_dir.pack(fill="x")
        self.foto = w.Imagem(topo_dir, 84, 104, vazio="sem foto")
        self.foto.pack(side="left", anchor="n", padx=(0, 4))
        self.g_atr = w.Grupo(topo_dir, "Atributos")
        self.g_atr.pack(side="left", fill="x", expand=True)
        g = w.Grupo(dir_, "Proposta da sua equipe")
        g.pack(fill="x", pady=(6, 0))
        tk.Label(g, text="Função:").grid(row=0, column=0, sticky="w")
        funcoes = ["principal"] + (["teste"] if self.cat["regras"].get("pilotos_de_teste") else [])
        self.v_sit = tk.StringVar(value="principal")
        ttk.Combobox(g, values=funcoes, textvariable=self.v_sit, state="readonly", width=12).grid(row=0, column=1,
                                                                                                  sticky="w")
        tk.Label(g, text="Salário/corrida (USD):").grid(row=1, column=0, sticky="w")
        self.v_sal = tk.StringVar(value="0")
        ttk.Entry(g, textvariable=self.v_sal, width=14).grid(row=1, column=1, sticky="w")
        self.v_ct = _form_contrato(g, 2, ano_atual=st["ano"])
        self.lbl_total = tk.Label(g, text="", fg=w.AZUL, font=w.FONTE_NEGRITO, wraplength=240, justify="left")
        self.lbl_total.grid(row=4, column=0, columnspan=2, sticky="w")
        self._total = _ligar_total(self.v_ct, self.lbl_total, st, self.cid, self._valor)
        self.v_sal.trace_add("write", self._total)
        w.Botao(g, "Enviar proposta", self.propor).grid(row=5, column=0, columnspan=2, pady=6)
        tk.Label(g, text="O piloto responde na semana seguinte. O valor que ele pede é uma estimativa da sua "
                         "equipe – o real pode ser maior ou menor.", fg=w.CINZA_ESCURO, wraplength=240,
                 justify="left").grid(row=6, column=0, columnspan=2)
        g2 = w.Grupo(dir_, "Propostas pendentes")
        g2.pack(fill="both", expand=True, pady=(6, 0))
        self.lb_pend = tk.Listbox(g2, height=5, width=40, relief="sunken", bd=2)
        self.lb_pend.pack(fill="both", expand=True)
        w.Botao(self.rodape, "Fechar", self.destroy, largura=10).pack(side="right")
        self.carregar()

    def carregar(self):
        st = self.st
        self.tv.delete(*self.tv.get_children())
        filtro_cat = self.cb_cat.get()
        for p in st["pilotos"].values():
            f = self.filtro.get()
            ct = p.get("contrato")
            if f == "agora":
                ok = not ct                            # inclui quem está livre até um contrato futuro
            elif f == "proxima":
                ok = mercado.livre_proxima(st, p)
            else:
                ok = bool(ct) and not p.get("contrato_futuro") and not (
                    ct.get("categoria") == self.cid and ct.get("equipe") == self.eq["id"])
            if not ok:
                continue
            valor_multa = mercado.multa(st, ct, ct["categoria"]) if (f == "contrato" and ct) else 0
            origem = mercado.categoria_do_piloto(p)
            nome_cat = st["categorias"][origem]["categoria"]["nome"] if origem in st["categorias"] else "-"
            if filtro_cat != "Todas" and nome_cat != filtro_cat:
                continue
            ct = p.get("contrato")
            if ct:
                eqn = st["categorias"][ct["categoria"]]["equipes"].get(ct["equipe"], {}).get("nome", "?")
                sit = f"Termina ({eqn})"
            elif p.get("contrato_futuro"):
                sit = f"Livre (assinou para {p['contrato_futuro'].get('inicio_ano')})"
            else:
                sit = "Livre"
            nota = ratings.nota_geral_piloto(p, self.cat)
            eq_atual = st["categorias"][ct["categoria"]]["equipes"].get(ct["equipe"]) if ct else None
            self.tv.insert("", "end", iid=p["id"], image=w.chip_equipe(eq_atual, p.get("nacionalidade"), com_cor=bool(eq_atual)),
                           values=(p["nome"], p["nacionalidade"], p["idade"], nome_cat, sit,
                                                           f"{nota:.0f}", self._faixa(p),
                                                           dinheiro(valor_multa) if valor_multa else "-"))
        if hasattr(self, "_total"):
            self._total()
        filhos = sorted(self.tv.get_children(), key=lambda i: -float(self.tv.set(i, "nota")))
        for i, iid in enumerate(filhos):
            self.tv.move(iid, "", i)
        vag_a, vag_p = mercado.vagas(st, self.cid, self.eq)
        fmt = lambda d: ", ".join(f"{v} {k}" for k, v in d.items() if v) or "nenhuma"  # noqa: E731
        self.lbl_vagas.configure(text=f"Vagas da sua equipe – agora: {fmt(vag_a)}   |   próxima temporada: {fmt(vag_p)}")
        self.lb_pend.delete(0, "end")
        for chave, pr in st.get("propostas_usuario", {}).items():
            if pr.get("equipe", self.eq["id"]) != self.eq["id"] or pr.get("categoria", self.cid) != self.cid:
                continue
            p = st["pilotos"].get(pr.get("piloto", chave))
            if p:
                quando = "agora" if pr["quando"] == "atual" else str(pr.get("ano_inicio") or self.st["ano"] + 1)
                self.lb_pend.insert("end", f"{p['nome']} – {dinheiro(pr['valor_por_corrida'])} – "
                                           f"{pr['duracao']} {pr['unidade']} ({quando})")

    def _faixa(self, p):
        _, lo, hi = mercado.pedido_estimado(self.st, p, self.cat, self.eq["id"])
        moeda = self.cat.get("moeda", "USD")
        if hi >= 1e6:
            return f"~{moeda} {lo / 1e6:.1f}–{hi / 1e6:.1f} mi"
        return f"~{moeda} {lo / 1e3:.0f}–{hi / 1e3:.0f} mil"

    def _valor(self):
        txt = self.v_sal.get().replace(".", "").replace(",", ".")
        return float(txt) if txt.strip() else None

    def detalhes(self):
        sel = self.tv.selection()
        for ch in self.g_atr.winfo_children():
            ch.destroy()
        if not sel:
            self.foto.definir(None)
            return
        p = self.st["pilotos"][sel[0]]
        self.foto.definir(p.get("imagem"))
        for i, k in enumerate(ATRIBUTOS_PILOTO):
            v = p["atributos"].get(k, 0)
            tk.Label(self.g_atr, text=NOMES_ATRIBUTOS[k], width=16, anchor="w").grid(row=i, column=0, sticky="w")
            w.BarraAtributo(self.g_atr, v, 90).grid(row=i, column=1, padx=2)
            tk.Label(self.g_atr, text=str(v), width=3).grid(row=i, column=2)
        self.v_sal.set(str(int(mercado.pedido_estimado(self.st, p, self.cat, self.eq["id"])[0])))
        self.v_ct["inicio"].set("proxima" if self.filtro.get() == "proxima" else "agora")

    def propor(self):
        sel = self.tv.selection()
        if not sel:
            messagebox.showinfo("Proposta", "Selecione um piloto.", parent=self)
            return
        try:
            valor = float(self.v_sal.get().replace(".", "").replace(",", "."))
            dur = int(self.v_ct["duracao"].get())
        except (ValueError, tk.TclError):
            messagebox.showwarning("Proposta", "Valores inválidos.", parent=self)
            return
        erro = acoes.executar(self.st, "proposta_piloto", piloto=sel[0], situacao=self.v_sit.get(), valor=valor,
                              duracao=dur, unidade=self.v_ct["unidade"].get(), inicio=inicio_de(self.v_ct))
        if erro:
            messagebox.showwarning("Proposta", erro, parent=self)
        else:
            messagebox.showinfo("Proposta", "Proposta enviada. A resposta sai na próxima semana.", parent=self)
        self.carregar()


# ====================================================================== chassis / motor
class JanelaPartes(w.Dialogo):
    def __init__(self, master, st, parte):
        nome = "Chassis" if parte == "chassis" else "Motor"
        neg = bool(mercado.negociacao(st["categorias"][st["usuario"]["categoria"]]["categoria"]))
        super().__init__(master, f"Mercado – {nome}", 820, 590 if neg else 510)
        self.st, self.parte = st, parte
        self.cid, self.c, self.eq = _ctx(st)
        self.neg = bool(mercado.negociacao(self.c["categoria"]))
        w.BarraTitulo(self.corpo, f"Contratos de {nome.lower()}").pack(fill="x")
        topo = tk.Frame(self.corpo)
        topo.pack(fill="x", pady=4)
        self.logo = w.Imagem(topo, 120, 50, vazio="sem logotipo")
        self.logo.pack(side="right")
        self.lbl_atual = tk.Label(topo, text="", anchor="w", justify="left", fg=w.AZUL)
        self.lbl_atual.pack(side="left", fill="x", expand=True)
        cols = [("nome", nome), ("orig", "Fornecedor"), ("nota", "Nota" if parte == "chassis" else "Potência"),
                ("valor", "Preço de tabela" if self.neg else "Valor/corrida"), ("disp", "Disponibilidade")]
        fr, self.tv = w.tabela(self.corpo, cols, 10, {"nome": 160, "orig": 150, "nota": 70, "valor": 110, "disp": 180},
                               {"nota": "center", "valor": "e"}, estica={"nome", "disp"}, cores=70)
        fr.pack(fill="both", expand=True)
        self.tv.bind("<<TreeviewSelect>>", lambda e: (self._logo(), self._oferta_padrao(), self._total()))
        g = w.Grupo(self.corpo, "Proposta ao fornecedor" if self.neg else "Fechar contrato")
        g.pack(fill="x", pady=(6, 0))
        self.v_ct = _form_contrato(g, 0, ano_atual=st["ano"])
        self.v_oferta = tk.StringVar()
        if self.neg:
            # negociação: o preço de tabela é referência; o fornecedor responde na semana seguinte
            tk.Label(g, text="Oferta por corrida (USD):").grid(row=3, column=0, sticky="w", pady=2)
            ttk.Entry(g, textvariable=self.v_oferta, width=14).grid(row=3, column=1, sticky="w")
            tk.Label(g, text="O fornecedor responde na semana seguinte. O preço que ele quer de verdade pode ser maior "
                             "ou menor que o de tabela.", fg=w.AZUL, anchor="w", justify="left", wraplength=640
                     ).grid(row=4, column=0, columnspan=4, sticky="w")
            self.v_oferta.trace_add("write", lambda *_: self._total())
        self.lbl_total = tk.Label(g, text="", fg=w.AZUL, font=w.FONTE_NEGRITO)
        self.lbl_total.grid(row=2, column=0, columnspan=4, sticky="w")
        self._total = _ligar_total(self.v_ct, self.lbl_total, st, self.cid, self._valor)
        w.Botao(g, "Enviar proposta" if self.neg else "Fechar contrato", self.fechar).grid(row=0, column=2, rowspan=2,
                                                                                           padx=20)
        w.Botao(g, "Rescindir contrato atual...", self.rescindir).grid(row=0, column=3, rowspan=2)
        w.Botao(self.rodape, "Fechar", self.destroy, largura=10).pack(side="right")
        self.carregar()

    def carregar(self):
        self.tv.delete(*self.tv.get_children())
        cat = self.c["categoria"]
        for ent, ok, motivo in mercado.opcoes(self.st, self.cid, self.eq, self.parte):
            if self.parte == "motor" and ent["fabricante"]["tipo"] == "equipe":
                orig = "Equipe " + self.c["equipes"][ent["fabricante"]["equipe"]]["nome"]
            elif self.parte == "chassis" and ent.get("equipe") in self.c["equipes"]:
                orig = "Equipe " + self.c["equipes"][ent["equipe"]]["nome"]
            else:
                orig = "Fabricante" if self.parte == "motor" else "Fornecedor de chassis"
            self.tv.insert("", "end", iid=ent["id"], tags=() if ok else ("cinza",),
                           image=w.ficha_logo(ent.get("logotipo"), ent.get("nacionalidade")),
                           values=(ent["nome"], orig, f"{mercado.nota_parte(ent, self.parte, cat):.0f}",
                                   dinheiro(ent["contrato"]["valor_por_corrida"]), "Disponível" if ok else motivo))
        info = self.eq.get(self.parte) or {}
        tabela = self.c["chassis" if self.parte == "chassis" else "motores"]
        atual = tabela.get(info.get("id"), {}).get("nome", "nenhum") if info.get("id") else "nenhum"
        txt = f"Atual: {atual}"
        if info.get("contrato"):
            txt += f" – {contratos.descricao(info['contrato'])} restante(s), " \
                   f"{dinheiro(info['contrato']['valor_por_corrida'])}/corrida"
        fut = self.eq.get(f"{self.parte}_futuro")
        if fut:
            ano_f = mercado._ano_futuro_parte(self.st, fut)
            nome_f = tabela.get(fut['id'], {}).get('nome', fut['id'])
            if ano_f == self.st["ano"] + 1:
                txt += f"\nPróxima temporada: {nome_f} ({contratos.descricao(fut['contrato'])})"
            else:
                txt += f"\nA partir de {ano_f}: {nome_f} ({contratos.descricao(fut['contrato'])})"
        pr = mercado.proposta_parte_pendente(self.st, self.cid, self.eq["id"], self.parte)
        if pr:
            txt += f"\nProposta aguardando resposta: {tabela.get(pr['id'], {}).get('nome', pr['id'])} – " \
                   f"{dinheiro(pr['valor_por_corrida'])}/corrida"
        self.lbl_atual.configure(text=txt)
        self._logo()

    def _valor(self):
        sel = self.tv.selection()
        tabela = self.c["chassis" if self.parte == "chassis" else "motores"]
        if self.neg:
            try:
                return float(self.v_oferta.get().replace(".", "").replace(",", ".")) if sel else None
            except ValueError:
                return None
        return tabela[sel[0]]["contrato"]["valor_por_corrida"] if sel and sel[0] in tabela else None

    def _oferta_padrao(self):
        sel = self.tv.selection()
        tabela = self.c["chassis" if self.parte == "chassis" else "motores"]
        if self.neg and sel and sel[0] in tabela:
            self.v_oferta.set(f"{tabela[sel[0]]['contrato']['valor_por_corrida']:.0f}")

    def _logo(self):
        tabela = self.c["chassis" if self.parte == "chassis" else "motores"]
        sel = self.tv.selection()
        ent = tabela.get(sel[0]) if sel else tabela.get((self.eq.get(self.parte) or {}).get("id"))
        self.logo.definir((ent or {}).get("logotipo"))

    def fechar(self):
        sel = self.tv.selection()
        if not sel:
            return
        try:
            dur = int(self.v_ct["duracao"].get())
        except (ValueError, tk.TclError):
            return
        rescindir = False
        inicio = inicio_de(self.v_ct)
        ano_ini = mercado.ano_de_inicio(self.st, inicio)
        if self.parte == "chassis" and ano_ini == self.st["ano"] + 1 \
                and (self.eq.get("chassis") or {}).get("origem") == "proprio" \
                and not messagebox.askyesno("Comprar chassis", f"Comprar o chassis de {self.st['ano'] + 1} encerra o "
                                                               f"projeto do chassis próprio (o que foi investido nele "
                                                               f"se perde).\n\nContinuar?", parent=self):
            return
        if ano_ini == self.st["ano"] and mercado.tem_parte_ativa(self.eq, self.parte) \
                and (self.eq.get(self.parte) or {}).get("origem") != "proprio":
            valor = mercado.multa_parte(self.st, self.cid, self.eq, self.parte)
            if not messagebox.askyesno("Trocar agora", f"Para trocar agora é preciso rescindir o contrato atual.\n"
                                                       f"Multa: {dinheiro(valor)}\n\nContinuar?", parent=self):
                return
            rescindir = True
        atual = (self.eq.get(self.parte) or {}).get("contrato")
        if ano_ini > self.st["ano"] and atual and (self.eq.get(self.parte) or {}).get("origem") != "proprio" \
                and mercado.fim_do_contrato(self.st, atual, self.cid) >= ano_ini:
            # o contrato atual vai além do início do novo: multa só pelas temporadas que se sobrepõem
            valor = mercado.multa_parte(self.st, self.cid, self.eq, self.parte, ano_ini)
            if not messagebox.askyesno("Contrato atual", f"O contrato atual vai até "
                                       f"{mercado.fim_do_contrato(self.st, atual, self.cid)}. Para o novo começar em "
                                       f"{ano_ini}, ele termina ao fim de {ano_ini - 1}.\nMulta: {dinheiro(valor)}"
                                       f"\n\nContinuar?", parent=self):
                return
            rescindir = True
        if self.neg:
            valor = self._valor()
            if not valor or valor <= 0:
                messagebox.showwarning("Proposta", "Informe a oferta por corrida.", parent=self)
                return
            erro = acoes.executar(self.st, "proposta_parte", parte=self.parte, id=sel[0], valor=valor, duracao=dur,
                                  unidade=self.v_ct["unidade"].get(), inicio=inicio,
                                  rescindir=rescindir)
            if erro:
                messagebox.showwarning("Proposta", erro, parent=self)
            else:
                messagebox.showinfo("Proposta", "Proposta enviada. O fornecedor responde na semana seguinte.",
                                    parent=self)
            self.carregar()
            return
        erro = acoes.executar(self.st, "contratar_parte", parte=self.parte, id=sel[0], duracao=dur,
                              unidade=self.v_ct["unidade"].get(), inicio=inicio, rescindir=rescindir)
        if erro:
            messagebox.showwarning("Contrato", erro, parent=self)
        else:
            messagebox.showinfo("Contrato", "Contrato fechado.", parent=self)
        self.carregar()


    def rescindir(self):
        if not mercado.tem_parte_ativa(self.eq, self.parte) or (self.eq.get(self.parte) or {}).get("origem") == "proprio":
            return
        valor = mercado.multa_parte(self.st, self.cid, self.eq, self.parte)
        if messagebox.askyesno("Rescindir", f"Rescindir o contrato atual de {self.parte}?\nMulta: {dinheiro(valor)}\n\n"
                                            "A equipe ficará sem a peça até fechar outro contrato.", parent=self):
            acoes.executar(self.st, "rescindir_parte", parte=self.parte)
            self.carregar()


# ====================================================================== patrocinadores
class JanelaPatrocinadores(w.Dialogo):
    def __init__(self, master, st):
        super().__init__(master, "Mercado – Patrocinadores", 760, 460)
        self.st = st
        self.cid, self.c, self.eq = _ctx(st)
        w.BarraTitulo(self.corpo, "Patrocinadores").pack(fill="x")
        g1 = w.Grupo(self.corpo, "Patrocinadores da sua equipe")
        g1.pack(fill="both", expand=True, pady=(4, 0))
        cols = [("nome", "Empresa"), ("ramo", "Ramo"), ("valor", "Valor"), ("pag", "Pagamento"), ("rest", "Restante")]
        fr, self.tv1 = w.tabela(g1, cols, 5, {"nome": 160, "ramo": 120, "valor": 110, "pag": 110, "rest": 100},
                                {"valor": "e"}, estica={"nome"}, cores=True)
        fr.pack(fill="both", expand=True)
        g2 = w.Grupo(self.corpo, "Ofertas recebidas")
        g2.pack(fill="both", expand=True, pady=(6, 0))
        cols2 = [("nome", "Empresa"), ("ramo", "Ramo"), ("valor", "Valor"), ("pag", "Pagamento"), ("dur", "Duração")]
        fr2, self.tv2 = w.tabela(g2, cols2, 5, {"nome": 160, "ramo": 120, "valor": 110, "pag": 110, "dur": 100},
                                 {"valor": "e"}, estica={"nome"}, cores=True)
        fr2.pack(fill="both", expand=True)
        b = tk.Frame(g2)
        b.pack(fill="x", pady=4)
        w.Botao(b, "Aceitar", lambda: self.responder(True), largura=10).pack(side="left")
        w.Botao(b, "Recusar", lambda: self.responder(False), largura=10).pack(side="left", padx=4)
        w.Botao(self.rodape, "Fechar", self.destroy, largura=10).pack(side="right")
        self.carregar()

    def carregar(self):
        self.tv1.delete(*self.tv1.get_children())
        for pat in self.c["patrocinadores"].values():
            ct = pat.get("contrato")
            if ct and ct.get("equipe") == self.eq["id"]:
                self.tv1.insert("", "end", image=w.ficha(pais=pat.get("pais"), com_cor=False), values=(pat["nome"], pat["ramo"], dinheiro(ct["valor"]),
                                                   ct["pagamento"].replace("_", " "), f"{ct['duracao']} {ct['unidade']}"))
        self.tv2.delete(*self.tv2.get_children())
        self.ofertas = [o for o in self.st.get("ofertas_patrocinio", []) if o["categoria"] == self.cid]
        for i, o in enumerate(self.ofertas):
            pat = self.c["patrocinadores"][o["patrocinador"]]
            self.tv2.insert("", "end", iid=str(i), image=w.ficha(pais=pat.get("pais"), com_cor=False),
                            values=(pat["nome"], pat["ramo"], dinheiro(o["valor"]),
                                                           o["pagamento"].replace("_", " "),
                                                           f"{o['duracao']} {o['unidade']}"))

    def responder(self, aceitar):
        sel = self.tv2.selection()
        if not sel:
            return
        acoes.executar(self.st, "patrocinio", patrocinador=self.ofertas[int(sel[0])]["patrocinador"], aceitar=aceitar)
        self.carregar()
