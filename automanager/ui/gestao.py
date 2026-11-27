"""Página geral de gestão da equipe."""
import tkinter as tk
from tkinter import messagebox

from .. import state, ratings, routines, mercado, desenvolvimento, contratos, economia, acoes, multiplayer, campeonato
from . import mercado_tela, desenvolvimento_tela, historico_tela, financas_tela
from ..event.inscritos import montar_inscritos
from ..db import NOMES_ATRIBUTOS, ATRIBUTOS_CHASSIS
from ..util import dinheiro
from .. import paises
from . import win9x as w



class TelaGestao(tk.Frame):
    def __init__(self, master, app, st):
        super().__init__(master, bg=w.CINZA)
        self.app, self.st = app, st
        self.jogador = multiplayer.sessao(st) is not None          # modo jogador do multijogador
        self._menu()
        topo = tk.Frame(self)
        topo.pack(fill="x", padx=4, pady=(4, 2))
        caixa_sem = tk.Frame(topo, bg=w.AZUL, relief="sunken", bd=2)
        caixa_sem.pack(side="right", padx=(4, 0))
        self.lbl_semana = tk.Label(caixa_sem, text="", bg=w.AZUL, fg=w.BRANCO, font=(w.FONTE[0], 15, "bold"), padx=10)
        self.lbl_semana.pack()
        self.lbl_semana_sub = tk.Label(caixa_sem, text="", bg=w.AZUL, fg="#ffff80", font=w.FONTE_NEGRITO, padx=10)
        self.lbl_semana_sub.pack()
        self.logo = w.Imagem(topo, 110, 52, ocultar_vazio=True)
        self.logo_visivel = False
        esq_topo = tk.Frame(topo)
        esq_topo.pack(side="left", fill="both", expand=True)
        self.esq_topo = esq_topo
        linha_tit = tk.Frame(esq_topo)
        linha_tit.pack(fill="x")
        self.faixa = w.FaixaEquipe(linha_tit, largura=14)
        self.faixa.pack(side="left", fill="y", padx=(0, 2))
        self.titulo = w.BarraTitulo(linha_tit, "")
        self.titulo.pack(side="left", fill="x", expand=True)
        self.linha_tempo = tk.Canvas(esq_topo, height=30, bg=w.BRANCO, highlightthickness=0, relief="sunken", bd=1)
        self.linha_tempo.pack(fill="x", pady=(2, 0))
        self.linha_tempo.bind("<Configure>", lambda e: self._desenhar_linha_tempo())

        # --- rodapé
        rod = tk.Frame(self, padx=6, pady=4)
        rod.pack(fill="x", side="bottom")
        if self.jogador:
            w.Botao(rod, "Salvar ordens  >>", self.salvar_ordens, largura=16, font=w.FONTE_NEGRITO).pack(
                side="right", padx=4)
            w.Botao(rod, "Plano do evento...", self.plano_evento, largura=16).pack(side="right", padx=4)
        else:
            w.Botao(rod, "Continuar  >>", self.continuar, largura=14, font=w.FONTE_NEGRITO).pack(side="right", padx=4)
            w.Botao(rod, "Simular temporada", self.simular_temporada, largura=17).pack(side="right", padx=2)
            w.Botao(rod, "Próximo evento", self.proximo_evento, largura=15).pack(side="right", padx=2)
        self.status = w.BarraStatus(rod)
        self.status.pack(side="left", fill="x", expand=True)
        if self.jogador:                                  # multijogador: o que falta fazer nesta semana
            self.g_passos = tk.Frame(self, bg=w.AMARELO_INFO, relief="sunken", bd=1, padx=6, pady=3)
            self.g_passos.pack(fill="x", side="bottom", padx=6)
            tk.Label(self.g_passos, text="Próximos passos desta semana", bg=w.AMARELO_INFO,
                     font=w.FONTE_NEGRITO).pack(anchor="w")
            self.lbl_passos = [tk.Label(self.g_passos, text="", bg=w.AMARELO_INFO, anchor="w") for _ in range(3)]
            for l in self.lbl_passos:
                l.pack(anchor="w")
        self.st_data = self.status.campo("", 22)
        self.st_cat = self.status.campo("", 26)
        self.st_msg = self.status.campo("", expandir=True)
        self.app.root.bind("<F5>", lambda e: self.continuar())
        corpo = tk.Frame(self, padx=6, pady=2)
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(0, weight=1, uniform="c")
        corpo.columnconfigure(1, weight=1, uniform="c")
        corpo.rowconfigure(1, weight=1)

        # --- carro
        self.g_carro = w.Grupo(corpo, "Carro")
        self.g_carro.grid(row=0, column=0, sticky="nsew", padx=3, pady=3)
        # --- finanças + próximo evento
        dir_top = tk.Frame(corpo)
        dir_top.grid(row=0, column=1, sticky="nsew", padx=3, pady=3)
        self.g_fin = w.Grupo(dir_top, "Finanças")
        self.g_fin.pack(fill="x")
        self.g_evt = w.Grupo(dir_top, "Próximo evento")
        self.g_evt.pack(fill="both", expand=True, pady=(6, 0))
        # --- pilotos
        g_pil = w.Grupo(corpo, "Pilotos da equipe")
        g_pil.grid(row=1, column=0, sticky="nsew", padx=3, pady=3)
        cols = [("nome", "Nome"), ("nac", "Nacionalidade"), ("idade", "Idade"), ("sit", "Situação"),
                ("valor", "Valor/corrida"), ("contrato", "Contrato"), ("nota", "Nota")]
        fr, self.tv_pil = w.tabela(g_pil, cols, 4, {"nome": 116, "nac": 78, "idade": 36, "sit": 60, "valor": 88,
                                                    "contrato": 56, "nota": 36},
                                   {"idade": "center", "valor": "e", "contrato": "center", "nota": "center"}, estica={"nome"},
                                   cores=True)
        self.foto_pil = w.Imagem(g_pil, 84, 104, vazio="sem foto")
        self.foto_pil.pack(side="right", anchor="n", padx=(4, 0))
        fr.pack(fill="both", expand=True)
        self.tv_pil.bind("<<TreeviewSelect>>", lambda e: self._foto_piloto())
        bp = tk.Frame(g_pil)
        bp.pack(fill="x", pady=(4, 0))
        w.Botao(bp, "Rescindir contrato...", self.rescindir).pack(side="left")
        w.Botao(bp, "Promover a titular", self.promover, padx=6).pack(side="left", padx=4)
        self.lbl_pil_futuro = tk.Label(bp, text="", anchor="w", justify="left", fg=w.AZUL)
        self.lbl_pil_futuro.pack(side="left", fill="x", padx=8)
        # --- notícias
        g_not = w.Grupo(corpo, "Notícias")
        g_not.grid(row=1, column=1, sticky="nsew", padx=3, pady=3)
        fr2 = tk.Frame(g_not)
        fr2.pack(fill="both", expand=True)
        self.lb_not = tk.Listbox(fr2, relief="sunken", bd=2, activestyle="none")
        sb = tk.Scrollbar(fr2, command=self.lb_not.yview)
        self.lb_not.configure(yscrollcommand=sb.set)
        self.lb_not.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.lb_not.bind("<<ListboxSelect>>", self._noticia_detalhe)
        self.lbl_not = tk.Label(g_not, text="", anchor="w", justify="left", wraplength=480, bg=w.AMARELO_INFO,
                                relief="sunken", bd=1, height=3)
        self.lbl_not.pack(fill="x", pady=(4, 0))

        self.atualizar()
        self._avisou_semana = False
        self._agendado_pasta = None
        self._agendado_passos = None
        if self.jogador:
            self._vigiar_pasta()
            self._atualizar_passos()

    # ------------------------------------------------------------------ menu
    def _menu(self):
        app = self.app
        st = self.st
        cid = st["usuario"]["categoria"]
        regras = st["categorias"][cid]["categoria"]["regras"]
        eq = state.equipe_usuario(st)
        mb = tk.Menu(app.root)
        arq = tk.Menu(mb)
        if self.jogador:
            arq.add_command(label="Salvar ordens...", command=self.salvar_ordens, accelerator="Ctrl+S")
            arq.add_command(label="Plano do evento...", command=self.plano_evento)
            arq.add_command(label="Calendário (esta e a próxima temporada)...", command=self.ver_calendario)
            arq.add_command(label="Guia do multijogador...", command=self.guia_multijogador)
            arq.add_separator()
            arq.add_command(label="Exportar para HTML...", command=self.exportar_html)
            arq.add_separator()
            arq.add_command(label="Fechar liga", command=app.fechar_jogo)
        else:
            arq.add_command(label="Abrir jogo salvo...", command=app.abrir_jogo)
            arq.add_command(label="Salvar jogo", command=app.salvar_jogo, accelerator="Ctrl+S")
            arq.add_command(label="Salvar como...", command=lambda: app.salvar_jogo(como=True))
            arq.add_separator()
            arq.add_command(label="Exportar para HTML...", command=self.exportar_html)
            arq.add_separator()
            arq.add_command(label="Opções...", command=app.opcoes)
            arq.add_separator()
            arq.add_command(label="Fechar jogo", command=app.fechar_jogo)
        mb.add_cascade(label="Arquivo", menu=arq, underline=0)

        merc = tk.Menu(mb)
        merc.add_command(label="Pilotos...", command=lambda: self._abrir(mercado_tela.JanelaPilotos, st))
        if mercado.opcoes(st, cid, eq, "chassis"):
            merc.add_command(label="Chassis...", command=lambda: self._abrir(mercado_tela.JanelaPartes, st, "chassis"))
        if mercado.opcoes(st, cid, eq, "motor"):
            merc.add_command(label="Motor...", command=lambda: self._abrir(mercado_tela.JanelaPartes, st, "motor"))
        if regras.get("patrocinios"):
            merc.add_command(label="Patrocinadores...", command=lambda: self._abrir(mercado_tela.JanelaPatrocinadores, st))
        mb.add_cascade(label="Mercado", menu=merc, underline=0)

        dev = tk.Menu(mb)
        if any(desenvolvimento.pode(st, cid, eq, p) or desenvolvimento.pode_projeto(st, cid, eq, p)
               for p in desenvolvimento.PARTES):
            dev.add_command(label=f"Carro desta temporada ({st['ano']})...",
                            command=lambda: self._abrir(desenvolvimento_tela.JanelaDesenvolvimento, st, 0))
            dev.add_command(label=f"Carro da próxima temporada ({st['ano'] + 1})...",
                            command=lambda: self._abrir(desenvolvimento_tela.JanelaDesenvolvimento, st, 1))
        else:
            dev.add_command(label="(sem desenvolvimento para sua equipe nesta categoria)", state="disabled")
        mb.add_cascade(label="Desenvolvimento", menu=dev, underline=0)

        fin = tk.Menu(mb)
        fin.add_command(label="Finanças e empréstimos...", command=lambda: self._abrir(financas_tela.JanelaFinancas, st))
        mb.add_cascade(label="Finanças", menu=fin, underline=0)

        hist = tk.Menu(mb)
        hist.add_command(label="Temporada atual...", command=lambda: self._abrir(historico_tela.JanelaTemporadaAtual, st))
        hist.add_command(label="Temporadas anteriores...",
                         command=lambda: self._abrir(historico_tela.JanelaTemporadasAnteriores, st))
        hist.add_command(label="Pontuação total (hall da fama)...",
                         command=lambda: self._abrir(historico_tela.JanelaTotal, st))
        mb.add_cascade(label="Histórico", menu=hist, underline=0)
        app.root.config(menu=mb)
        app.root.bind("<Control-s>", lambda e: self.salvar_ordens() if self.jogador else app.salvar_jogo())

    def _abrir(self, classe, *args):
        classe(self, *args).modal()
        self._menu()
        self.atualizar()

    # ------------------------------------------------------------------ atualização
    def atualizar(self):
        st = self.st
        cid = st["usuario"]["categoria"]
        c = st["categorias"][cid]
        cat = c["categoria"]
        eq = state.equipe_usuario(st)
        self.app.root.title(f"AutoManager – {eq['nome']}")
        if self.jogador:
            m = st["multiplayer"]
            self.titulo.definir(f"{eq['nome']}  –  {cat['nome']} {st['ano']}  ·  Liga {m['nome']} – "
                                f"{m['jogadores'][m['sessao']['jogador']]['nome']}")
        else:
            self.titulo.definir(f"{eq['nome']}  –  {cat['nome']} {st['ano']}")
        self.faixa.definir(eq)
        tem_logo = self.logo.definir(eq.get("logotipo"))
        if tem_logo and not self.logo_visivel:
            self.logo.pack(side="left", padx=(0, 4), before=self.esq_topo)
        elif not tem_logo and self.logo_visivel:
            self.logo.pack_forget()
        self.logo_visivel = tem_logo
        self.after_idle(self._oferecer_reserva)
        self.st_data.configure(text=f"Semana {st['semana']} / {routines.SEMANAS_POR_TEMPORADA} – {st['ano']}")
        self.lbl_semana.configure(text=f"SEMANA {st['semana']} / {routines.SEMANAS_POR_TEMPORADA}")
        prox = state.proximo_evento(st, cid)
        if prox:
            falta = prox["semana"] - st["semana"]
            quando = "ESTA SEMANA" if falta == 0 else f"em {falta} sem."
            tipo = "Corrida" if prox["especie"] == "corrida" else "Teste"
            self.lbl_semana_sub.configure(text=f"{st['ano']} · {tipo} {quando}")
        else:
            self.lbl_semana_sub.configure(text=f"{st['ano']} · fim da temporada")
        self._desenhar_linha_tempo()
        self.st_cat.configure(text=f"Categorias carregadas: {len(st['categorias'])}")
        self._carro(cid, eq, cat)
        self._financas(eq)
        self._evento(cid)
        self._pilotos(cid, eq, cat)
        self._noticias()

    def _desenhar_linha_tempo(self):
        """52 semanas: corridas (azul), testes coletivos (verde), semana atual em destaque, passadas em cinza."""
        cv = self.linha_tempo
        cv.delete("all")
        from tkinter import font as tkfont
        fonte_num = tkfont.Font(cv, family=w.FONTE[0], size=6)
        altura = 28 + fonte_num.metrics("linespace") + 2   # a altura acompanha a fonte (escala do Windows)
        if int(cv.cget("height")) != altura:
            cv.configure(height=altura)
        st = self.st
        n = routines.SEMANAS_POR_TEMPORADA
        largura = max(cv.winfo_width(), 200)
        passo = (largura - 8) / n
        cid = st["usuario"]["categoria"]
        eventos = {}
        for ev in st["categorias"][cid]["calendario"]:
            if ev.get("ativo"):
                eventos[ev["semana"]] = ev
        for i in range(1, n + 1):
            x0 = 4 + (i - 1) * passo
            x1 = x0 + passo - 1
            ev = eventos.get(i)
            cor = "#e8e8e8" if i < st["semana"] else w.BRANCO
            if ev:
                cor = ("#9fb6d8" if i < st["semana"] else "#2050c0") if ev["especie"] == "corrida" else \
                    ("#a8d0a8" if i < st["semana"] else "#2a9d3a")
            cv.create_rectangle(x0, 6, x1, 22, fill=cor, outline=w.CINZA_ESCURO)
            if i == st["semana"]:
                cv.create_rectangle(x0 - 2, 2, x1 + 2, 26, outline="#e00000", width=3)
            if i % 4 == 1:                    # números abaixo da faixa (e do destaque da semana atual)
                cv.create_text(x0 + 1, 28, text=str(i), anchor="nw", font=fonte_num, fill=w.CINZA_ESCURO)

    def _limpar(self, frame):
        for ch in frame.winfo_children():
            ch.destroy()

    def _carro(self, cid, eq, cat):
        g = self.g_carro
        self._limpar(g)
        ch = state.chassis_da_equipe(self.st, cid, eq)
        mo = state.motor_da_equipe(self.st, cid, eq)
        if not ch and not mo:
            tk.Label(g, text="A equipe ainda não tem chassis nem motor.\n"
                             "Eles serão obtidos pelo Mercado / Desenvolvimento (aguardando definição).",
                     justify="left", fg=w.CINZA_ESCURO).pack(anchor="w")
            return
        origem_ch = "próprio" if (eq.get("chassis") or {}).get("origem") == "proprio" else "de terceiros"
        origem_mo = {"proprio": "próprio", "equipe": "de outra equipe", "fabricante": "de fabricante"}.get(
            (eq.get("motor") or {}).get("origem"), "-")
        topo = tk.Frame(g)
        topo.pack(fill="x")
        for i, (ent, rot, origem) in enumerate(((ch, "Chassis", origem_ch), (mo, "Motor", origem_mo))):
            img = w.Imagem(topo, 48, 20, borda=False)
            if img.definir((ent or {}).get("logotipo")):
                img.grid(row=i, column=0, sticky="w", padx=(0, 4))
            else:
                img.destroy()
            w.RotuloBandeira(topo, (ent or {}).get("nacionalidade"), f"{rot}: {ent['nome'] if ent else '(nenhum)'}  "
                                                                     f"[{origem}]",
                             font=w.FONTE_NEGRITO).grid(row=i, column=1, sticky="w")
        nota = ratings.nota_geral_carro(ch, mo, cat)
        tk.Label(topo, text=f"Nota geral: {nota:.0f}", fg=w.AZUL).grid(row=0, column=2, rowspan=2, padx=12)
        grade = tk.Frame(g)
        grade.pack(fill="x", pady=(4, 0))
        itens = [(NOMES_ATRIBUTOS[k], ch["atributos"].get(k, 0)) for k in ATRIBUTOS_CHASSIS] if ch else []
        if mo:
            itens.append(("Potência (motor)", mo.get("potencia", 0)))
        for i, (nome, v) in enumerate(itens):
            col = (i % 2) * 3
            lin = i // 2
            tk.Label(grade, text=nome, width=14, anchor="w").grid(row=lin, column=col, sticky="w")
            w.BarraAtributo(grade, v, 84).grid(row=lin, column=col + 1, padx=2, pady=1)
            tk.Label(grade, text=f"{v:>3}", width=3).grid(row=lin, column=col + 2, padx=(0, 6))

    def _financas(self, eq):
        g = self.g_fin
        self._limpar(g)
        fa = eq["financas"]["ano"]
        rec = sum(fa["receitas"].values())
        desp = sum(fa["despesas"].values())
        nomes_r = {"patrocinio": "Patrocínios", "tv": "Renda de TV", "premios": "Prêmios de corrida",
                   "fornecimento": "Venda de chassis/motor",
                   "multas": "Multas recebidas",
                   "emprestimos": "Empréstimos recebidos"}
        nomes_d = {"salarios": "Salários de pilotos", "chassis": "Contrato de chassis", "motor": "Contrato de motor",
                   "desenvolvimento": "Desenvolvimento", "multas": "Multas pagas", "emprestimos": "Parcelas de empréstimos"}
        linhas = [("Receitas", rec, True)] + [("   " + nomes_r.get(k, k), v, False) for k, v in fa["receitas"].items()] + \
                 [("Despesas", desp, True)] + [("   " + nomes_d.get(k, k), v, False) for k, v in fa["despesas"].items()]
        for i, (n, v, neg) in enumerate(linhas):
            tk.Label(g, text=n, anchor="w", font=w.FONTE_NEGRITO if neg else w.FONTE).grid(row=i, column=0, sticky="w")
            tk.Label(g, text=dinheiro(v), anchor="e", font=w.FONTE_NEGRITO if neg else w.FONTE).grid(
                row=i, column=1, sticky="e", padx=(20, 0))
        i = len(linhas)
        tk.Frame(g, height=2, bd=1, relief="sunken").grid(row=i, column=0, columnspan=2, sticky="ew", pady=3)
        bal = rec - desp
        tk.Label(g, text=f"Balanço do ano ({self.st['ano']})", font=w.FONTE_NEGRITO).grid(row=i + 1, column=0, sticky="w")
        tk.Label(g, text=dinheiro(bal), font=w.FONTE_NEGRITO, fg="#006000" if bal >= 0 else "#a00000").grid(
            row=i + 1, column=1, sticky="e")
        tk.Label(g, text="Caixa", font=w.FONTE_NEGRITO).grid(row=i + 2, column=0, sticky="w")
        cx = eq["financas"]["caixa"]
        tk.Label(g, text=dinheiro(cx), font=w.FONTE_NEGRITO, fg=w.AZUL if cx >= 0 else "#a00000").grid(
            row=i + 2, column=1, sticky="e")
        if eq.get("emprestimos"):
            tk.Label(g, text="Dívida (empréstimos)").grid(row=i + 3, column=0, sticky="w")
            tk.Label(g, text=dinheiro(economia.divida(eq)), fg="#a00000").grid(row=i + 3, column=1, sticky="e")
        g.columnconfigure(1, weight=1)

    def _evento(self, cid):
        g = self.g_evt
        self._limpar(g)
        ev = state.proximo_evento(self.st, cid)
        if not ev:
            tk.Label(g, text="Não há mais eventos nesta temporada.").pack(anchor="w")
            return
        faltam = ev["semana"] - self.st["semana"]
        quando = "ESTA SEMANA" if faltam == 0 else f"em {faltam} semana(s)"
        tipos = {"mista": "mista", "oval": "oval", "rua": "pista de rua"}
        img = w.Imagem(g, 150, 96, borda=False)
        if img.definir(ev.get("imagem")):
            img.pack(side="right", anchor="n", padx=(4, 0))
        else:
            img.destroy()
        w.RotuloBandeira(g, paises.do_local(ev.get("local")), ev["nome"], font=w.FONTE_NEGRITO).pack(anchor="w")
        info = [f"{'Corrida' if ev['especie'] == 'corrida' else 'Teste coletivo'} – semana {ev['semana']} ({quando})",
                f"Local: {ev['local']}   |   Pista {tipos.get(ev['tipo_pista'], ev['tipo_pista'])}",
                f"Retas {ev['retas']}  •  Curvas de alta {ev['curvas_alta']}  •  Curvas de baixa {ev['curvas_baixa']}",
                f"Desgaste de pneus {ev['desgaste_pneus']}  •  Dificuldade {ev['dificuldade']}  •  "
                f"Chuva {ev['prob_chuva'] * 100:.0f}%"]
        if ev["especie"] == "corrida":
            info.append(f"{ev['voltas_corrida']} voltas")
        for t in info:
            tk.Label(g, text=t, anchor="w").pack(anchor="w")

    def _pilotos(self, cid, eq, cat):
        tv = self.tv_pil
        tv.delete(*tv.get_children())
        pil = state.pilotos_da_equipe(self.st, cid, eq["id"])
        for p in pil:
            ct = p["contrato"]
            nota = ratings.nota_geral_piloto(p, cat)
            tv.insert("", "end", iid=p["id"], image=w.ficha(pais=p["nacionalidade"], com_cor=False),
                      values=(p["nome"], p["nacionalidade"], p["idade"],
                                         "Principal" if ct["situacao"] == "principal" else "Testes",
                                         dinheiro(ct["valor_por_corrida"]),
                                         contratos.descricao(ct), f"{nota:.0f}"))
        if not pil:
            tv.insert("", "end", values=("(nenhum piloto contratado)", "", "", "", "", "", ""), tags=("cinza",))
        if pil:
            tv.selection_set(pil[0]["id"])
        self._foto_piloto()
        fut = state.pilotos_da_equipe(self.st, cid, eq["id"], futuro=True)
        por_ano = {}
        for p in fut:
            por_ano.setdefault(int(p["contrato_futuro"].get("inicio_ano") or self.st["ano"] + 1), []).append(p["nome"])
        partes = []
        for ano in sorted(por_ano):
            if ano == self.st["ano"] + 1:
                partes.append("Contratados para a próxima temporada: " + ", ".join(por_ano[ano]))
            else:
                partes.append(f"Contratados para {ano}: " + ", ".join(por_ano[ano]))
        self.lbl_pil_futuro.configure(text="\n".join(partes))

    def _foto_piloto(self):
        sel = self.tv_pil.selection()
        p = self.st["pilotos"].get(sel[0]) if sel else None
        self.foto_pil.definir((p or {}).get("imagem"))

    def promover(self):
        """O piloto de testes selecionado assume um carro (no lugar de um titular lesionado ou numa vaga aberta)."""
        sel = self.tv_pil.selection()
        p = self.st["pilotos"].get(sel[0]) if sel else None
        if not p or (p.get("contrato") or {}).get("situacao") != "teste":
            messagebox.showinfo("Promover a titular", "Selecione o piloto de testes na lista de pilotos da equipe.",
                                parent=self)
            return
        erro = acoes.executar(self.st, "promover_piloto", piloto=p["id"])
        if erro:
            messagebox.showwarning("Promover a titular", erro, parent=self)
        self.atualizar()

    def _oferecer_reserva(self):
        """Titular lesionado sem substituto e um piloto de testes disponível: pergunta (uma vez) se ele assume."""
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        u = self.st["usuario"]
        ausente = mercado.lesionado_sem_substituto(self.st, u["categoria"], u["equipe"])
        reservas = mercado.reservas_disponiveis(self.st, u["categoria"], u["equipe"])
        if not ausente or not reservas:
            return
        perguntadas = self.app.__dict__.setdefault("_reserva_perguntada", set())
        chave = (self.st["ano"], ausente["id"], ausente["lesao"].get("evento"))
        if chave in perguntadas:
            return
        perguntadas.add(chave)
        r = reservas[0]
        if messagebox.askyesno("Piloto lesionado", f"{ausente['nome']} está lesionado e fica fora de "
                                                   f"{ausente['lesao'].get('corridas', '?')} corrida(s).\n\n"
                                                   f"Colocar o piloto de testes {r['nome']} no carro até ele voltar?",
                               parent=self):
            erro = acoes.executar(self.st, "promover_piloto", piloto=r["id"])
            if erro:
                messagebox.showwarning("Piloto lesionado", erro, parent=self)
            self.atualizar()

    def rescindir(self):
        sel = self.tv_pil.selection()
        if not sel or sel[0] not in self.st["pilotos"]:
            messagebox.showinfo("Rescindir", "Selecione um piloto da equipe.", parent=self)
            return
        p = self.st["pilotos"][sel[0]]
        ct = p["contrato"]
        valor = mercado.multa(self.st, ct, ct["categoria"])
        if messagebox.askyesno("Rescindir contrato",
                               f"Rescindir o contrato de {p['nome']}?\n\nRestam "
                               f"{mercado.corridas_restantes_contrato(self.st, ct, ct['categoria'])} corridas de "
                               f"contrato.\nMulta: {dinheiro(valor)}", parent=self):
            acoes.executar(self.st, "rescindir_piloto", piloto=p["id"])
            self.atualizar()

    def _noticias(self):
        lb = self.lb_not
        lb.delete(0, "end")
        self._lista_noticias = list(reversed(self.st["noticias"][-300:]))
        cats = self.st["categorias"]
        for n in self._lista_noticias:
            pref = f"[{n['ano']} S{n['semana']:02d}]"
            nome_cat = cats[n["categoria"]]["categoria"]["nome"] if n.get("categoria") in cats else ""
            lb.insert("end", f"{pref} {nome_cat + ': ' if nome_cat and nome_cat not in n['texto'] else ''}{n['texto']}")
            if n.get("tipo") == "usuario" and (not self.jogador or n.get("equipe") in (None, self.st["usuario"]["equipe"])):
                lb.itemconfigure("end", fg="#a00000")
        self.lbl_not.configure(text="")

    def _noticia_detalhe(self, _e=None):
        sel = self.lb_not.curselection()
        if sel:
            n = self._lista_noticias[sel[0]]
            self.lbl_not.configure(text=n["texto"])

    # ------------------------------------------------------------------ multijogador (jogador)
    def ver_calendario(self):
        from .calendario_liga_tela import DialogoVerCalendario
        DialogoVerCalendario(self, self.st, self.st["usuario"]["categoria"]).modal()

    def plano_evento(self):
        from .multijogador_tela import DialogoPlanoEvento
        DialogoPlanoEvento(self, self.st).modal()
        self.atualizar()

    # ------------------------------------------------------------------ multijogador: pasta compartilhada
    def _pasta_liga(self):
        return self.app.pasta_liga_jogador if getattr(self.app, "liga_compartilhada", False) else None

    def _vigiar_pasta(self):
        """Jogador: mostra o prazo e a situação das ordens dele (status.json do comissário) e avisa quando uma
        semana nova é publicada na pasta compartilhada. Repete a cada 20 s."""
        from .. import caixa_liga
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        pasta = self._pasta_liga()
        st = self.st
        jid = multiplayer.sessao(st)["jogador"]
        prazo = caixa_liga.prazo(st)
        partes = [f"Prazo: {prazo}" + (" (vencido)" if caixa_liga.atrasado(st) else "")] if prazo else []
        s = caixa_liga.ler_status(pasta) if pasta else None
        if s and (s.get("ano"), s.get("semana")) == (st["ano"], st["semana"]):
            j = (s.get("jogadores") or {}).get(jid) or {}
            if j.get("estado") == "recebidas":
                partes.append(f"Suas ordens foram recebidas pelo comissário às {str(j.get('quando', ''))[-5:]}.")
            elif j.get("estado") == "recusadas":
                partes.append(f"Suas ordens foram recusadas: {j.get('motivo', '')}")
            else:
                partes.append("O comissário ainda não recebeu suas ordens.")
        if partes:
            from .. import i18n
            self.st_msg.configure(text="  ·  ".join(i18n.t(x) for x in partes))
        if s and (s.get("ano"), s.get("semana")) > (st["ano"], st["semana"]) and not self._avisou_semana:
            self._avisou_semana = True
            if messagebox.askyesno("Nova semana", f"O comissário publicou a semana {s['semana']}/{s['ano']}.\n\n"
                                                  f"Abrir agora?", parent=self):
                self._abrir_semana_nova(pasta, jid)
                return
        self._agendado_pasta = self.after(20000, self._vigiar_pasta)

    def _abrir_semana_nova(self, pasta, jid):
        import os
        from .. import caixa_liga
        try:
            st_liga = multiplayer.carregar_liga(os.path.join(pasta, caixa_liga.LIGA))
            novo = multiplayer.entrar_com_chave(st_liga, jid, multiplayer.sessao(self.st)["_chave"])
        except (OSError, ValueError, multiplayer.ErroLiga) as e:
            messagebox.showerror("Nova semana", f"Não foi possível abrir a semana nova:\n{e}", parent=self)
            return
        self.app.abrir_equipe(novo)

    def salvar_ordens(self):
        from tkinter import filedialog
        import os
        from .multijogador_tela import eventos_da_semana, caminho_ordens_padrao, resumo_jogador
        if not self.jogador:
            return
        sess = multiplayer.sessao(self.st)
        sem_plano = []
        for ev in eventos_da_semana(self.st):
            u = self.st["usuario"]
            for i in montar_inscritos(self.st, u["categoria"], u["equipe"], ev):
                if i["usuario"] and i["piloto"]["id"] not in sess["planos"].get(ev["id"], {}):
                    sem_plano.append(f"{i['piloto']['nome']} ({ev['nome']})")
        if sem_plano and not messagebox.askyesno(
                "Salvar ordens", "Sem plano de evento para:\n" + "\n".join(sem_plano) +
                "\n\nA equipe decidirá automaticamente para eles. Salvar mesmo assim?", parent=self):
            return
        pasta = self._pasta_liga()
        if pasta:                                   # pasta compartilhada: entrega direto, sem escolher arquivo
            from .. import caixa_liga
            try:
                caminho = caixa_liga.entregar_ordens(self.st, pasta)
            except OSError as e:
                messagebox.showerror("Salvar ordens", f"Não foi possível gravar na pasta compartilhada:\n{e}",
                                     parent=self)
                return
            self._registrar_salvas(pasta)
            messagebox.showinfo("Salvar ordens", f"{resumo_jogador(self.st)}\n\nEntregues na pasta compartilhada:\n"
                                                 f"{caminho}\n\nO comissário recebe sozinho; a situação aparece na "
                                                 f"barra de baixo. Você pode continuar mexendo e salvar de novo (vale a "
                                                 f"última entrega).", parent=self)
            self._vigiar_pasta_agora()
            return
        padrao = caminho_ordens_padrao(self.st, self.app.pasta_liga_jogador or os.getcwd())
        caminho = filedialog.asksaveasfilename(parent=self, title="Salvar ordens desta semana",
                                               initialdir=os.path.dirname(padrao), initialfile=os.path.basename(padrao),
                                               defaultextension=".json", filetypes=[("Ordens (JSON)", "*.json")])
        if not caminho:
            return
        multiplayer.salvar_ordens(self.st, caminho)
        self._registrar_salvas(None)
        if messagebox.askyesno("Salvar ordens", f"{resumo_jogador(self.st)}\n\nArquivo:\n{caminho}\n\n"
                                                "Agora mande este arquivo ao comissário: anexe no canal da liga no "
                                                "Discord (ou em mensagem privada ao bot) ou por e-mail. Ele vai "
                                                "cifrado: só o comissário consegue ler.\n\nVocê pode continuar "
                                                "mexendo e salvar de novo (vale o último arquivo que o comissário "
                                                "importar).\n\nAbrir a pasta do arquivo?", parent=self):
            from .guia_multijogador import abrir_no_sistema
            abrir_no_sistema(os.path.dirname(caminho))

    # ------------------------------------------------------------------ ação
    def _minimo_de_pilotos(self):
        """Corrida nesta semana e a equipe abaixo do mínimo de titulares: os pilotos respondem já às propostas
        pendentes; se ainda faltar, a semana não avança."""
        u = self.st["usuario"]
        falta, ev = mercado.faltam_pilotos(self.st, u["categoria"], u["equipe"])
        if falta <= 0:
            return True
        mercado.responder_agora(self.st, u["categoria"], u["equipe"])
        falta, ev = mercado.faltam_pilotos(self.st, u["categoria"], u["equipe"])
        if falta <= 0:
            self.atualizar()
            return True
        minimo = mercado.minimo_pilotos(self.st, u["categoria"])
        messagebox.showwarning("Pilotos", f"A categoria exige {minimo} pilotos titulares por equipe e sua equipe tem "
                                          f"{minimo - falta} para o {ev['nome']}.\n\nContrate em Mercado > Pilotos (ou promova seu piloto de "
                                          f"testes em Pilotos da equipe > Promover a titular). "
                                          f"Com a corrida nesta semana, os pilotos respondem às propostas quando "
                                          f"você clica em Continuar.", parent=self)
        self.atualizar()
        return False

    def continuar(self):
        if self.jogador:                                  # no multijogador quem avança a semana é o comissário
            self.salvar_ordens()
            return
        teste = routines.teste_do_usuario_na_semana(self.st)
        if teste and not routines.corrida_do_usuario_na_semana(self.st):
            u = self.st["usuario"]
            inscritos = montar_inscritos(self.st, u["categoria"], u["equipe"], teste)
            if any(i["usuario"] for i in inscritos) and messagebox.askyesno(
                    "Teste coletivo", f"{teste['nome']} em {teste['local']}.\n\nParticipar do teste na pista?\n"
                                      "(Não = sua equipe testa no modo automático.)", parent=self):
                self.app.evento(self.st, teste, inscritos, teste=True)
                return
        if not self._minimo_de_pilotos():
            return
        pista = routines.corrida_do_usuario_na_semana(self.st)
        if pista:
            u = self.st["usuario"]
            inscritos = montar_inscritos(self.st, u["categoria"], u["equipe"], pista)
            if any(i["usuario"] for i in inscritos):
                messagebox.showinfo("Fim de semana de corrida", f"Chegou a hora do {pista['nome']}!", parent=self)
                self.app.evento(self.st, pista, inscritos)
                return
            messagebox.showwarning("Fim de semana de corrida",
                                   f"Sua equipe não tem carro completo ou pilotos para o {pista['nome']}.\n"
                                   "O evento será disputado sem ela.", parent=self)
        novas = routines.avancar_semana(self.st)
        if self._fim_de_jogo():
            return
        self.atualizar()
        self.st_msg.configure(text=f"{len(novas)} notícia(s) nesta semana." if novas else "Semana sem novidades.")

    def exportar_html(self):
        """Gera um site (index.html + páginas) com classificação, calendário, resultados, equipes, pilotos,
        finanças da sua equipe, temporadas anteriores e notícias, para abrir no navegador."""
        from .exportar_tela import exportar
        exportar(self, self.st)

    def _fim_de_jogo(self):
        if not self.st.get("fim_de_jogo"):
            return False
        messagebox.showerror("Fim de jogo", "Sua equipe faliu: sem caixa e sem crédito, encerrou as atividades.\n\n"
                                            "Você pode carregar um jogo salvo ou começar outro.", parent=self)
        self.app.estado = None
        self.app.menu_inicial()
        return True

    def _evento_na_semana(self):
        return routines.corrida_do_usuario_na_semana(self.st) or routines.teste_do_usuario_na_semana(self.st)

    def _progresso(self, texto):
        self.st_msg.configure(text=texto)
        self.config(cursor="watch")
        self.update()

    def proximo_evento(self):
        """Avança as semanas sem evento da sua categoria e para na semana do próximo (corrida ou teste), que você
        disputa com Continuar. Com um evento nesta semana, é o próprio Continuar. Para também no início de uma nova
        temporada."""
        if self.jogador:
            return
        if self._evento_na_semana():
            self.continuar()
            return
        ano, semanas = self.st["ano"], 0
        try:
            while not self._evento_na_semana() and semanas < 60:
                routines.avancar_semana(self.st)
                semanas += 1
                if self._fim_de_jogo():
                    return
                if self.st["ano"] != ano:
                    break                              # nova temporada: para no início dela
                self._progresso(f"Semana {self.st['semana']}...")
        finally:
            self.config(cursor="")
        self.atualizar()
        ev = self._evento_na_semana()
        self.st_msg.configure(text=f"{semanas} semana(s) avançada(s). Próximo evento: {ev['nome']}." if ev
                              else f"{semanas} semana(s) avançada(s). Começa a temporada {self.st['ano']}.")

    def simular_temporada(self):
        """Simula até o fim da temporada, com as corridas e os testes da sua equipe no automático (acerto e
        estratégia da IA). Para se a equipe ficar abaixo do mínimo de pilotos para uma corrida."""
        if self.jogador:
            return
        ano = self.st["ano"]
        if not messagebox.askyesno("Simular temporada", f"Simular até o fim da temporada {ano}?\n\nAté lá a IA "
                                                        f"conduz sua equipe como faz com as dela: desenvolvimento, "
                                                        f"contratos, pilotos e finanças. Suas corridas e testes são "
                                                        f"disputados no automático.", parent=self):
            return
        u = self.st["usuario"]
        self.st["ia_conduz_usuario"] = True
        try:
            while self.st["ano"] == ano:
                pista = routines.corrida_do_usuario_na_semana(self.st)
                if pista:
                    self.config(cursor="")
                    if not self._minimo_de_pilotos():
                        return
                    self._progresso(f"Semana {self.st['semana']}: {pista['nome']}...")
                    campeonato.simular_em_segundo_plano(self.st, u["categoria"], pista)
                routines.avancar_semana(self.st)
                if self._fim_de_jogo():
                    return
                self._progresso(f"Semana {self.st['semana']}...")
        finally:
            self.st.pop("ia_conduz_usuario", None)
            if self.winfo_exists():
                self.config(cursor="")
        self.atualizar()
        self.st_msg.configure(text=f"Temporada {ano} simulada. Começa a temporada {self.st['ano']}.")

    def guia_multijogador(self):
        from .guia_multijogador import DialogoGuia
        DialogoGuia(self, "jogador").modal()

    def _atualizar_passos(self):
        """Quadro 'Próximos passos' do jogador (decisões, plano do evento, ordens salvas). A cada 2 s."""
        from .guia_multijogador import passos_do_jogador
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        linhas, _ = passos_do_jogador(self.st, getattr(self.app, "_ordens_salvas", None))
        for lbl, (feito, texto) in zip(self.lbl_passos, linhas):
            lbl.configure(text=("✔  " if feito else "➜  ") + texto, fg="#006000" if feito else w.PRETO)
        self._agendado_passos = self.after(2000, self._atualizar_passos)

    def _registrar_salvas(self, pasta):
        import time
        from .guia_multijogador import passos_do_jogador
        _, conteudo = passos_do_jogador(self.st, None)
        self.app._ordens_salvas = {"ano": self.st["ano"], "semana": self.st["semana"],
                                   "quando": time.strftime("%H:%M"), "conteudo": conteudo, "pasta": bool(pasta)}

    def _vigiar_pasta_agora(self):
        if self._agendado_pasta:
            try:
                self.after_cancel(self._agendado_pasta)
            except tk.TclError:
                pass
        self._vigiar_pasta()

    def destroy(self):
        for k in ("_agendado_passos",):
            if getattr(self, k, None):
                try:
                    self.after_cancel(getattr(self, k))
                except tk.TclError:
                    pass
        if getattr(self, "_agendado_pasta", None):
            try:
                self.after_cancel(self._agendado_pasta)
            except tk.TclError:
                pass
        try:
            self.app.root.unbind("<F5>")
            self.app.root.unbind("<Control-s>")
        except tk.TclError:
            pass
        super().destroy()
