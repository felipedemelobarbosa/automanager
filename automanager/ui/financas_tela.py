"""Finanças: previsão da temporada e empréstimos."""
import tkinter as tk
from tkinter import ttk, messagebox

from .. import economia, acoes
from ..util import dinheiro
from . import win9x as w


class JanelaFinancas(w.Dialogo):
    def __init__(self, master, st):
        super().__init__(master, "Finanças", 760, 520)
        self.st = st
        self.cid, eid = st["usuario"]["categoria"], st["usuario"]["equipe"]
        self.eq = st["categorias"][self.cid]["equipes"][eid]
        self.conf = economia.cfg(st, self.cid)
        w.BarraTitulo(self.corpo, f"Finanças – {self.eq['nome']}").pack(fill="x", pady=(0, 4))
        self.g_res = w.Grupo(self.corpo, "Resumo")
        self.g_res.pack(fill="x")
        g = w.Grupo(self.corpo, "Empréstimos")
        g.pack(fill="both", expand=True, pady=(6, 0))
        cols = [("data", "Tomado em"), ("valor", "Valor"), ("saldo", "Saldo devedor"), ("parcela", "Parcela/corrida"),
                ("rest", "Parcelas restantes"), ("juros", "Juros a.a.")]
        fr, self.tv = w.tabela(g, cols, 5, {"data": 90, "valor": 110, "saldo": 120, "parcela": 110, "rest": 110,
                                            "juros": 70}, {k: "e" for k in ("valor", "saldo", "parcela")},
                               estica={"saldo"})
        fr.pack(fill="both", expand=True)
        b = tk.Frame(g)
        b.pack(fill="x", pady=4)
        w.Botao(b, "Quitar selecionado", self.quitar).pack(side="left")
        g2 = w.Grupo(self.corpo, "Novo empréstimo")
        g2.pack(fill="x", pady=(6, 0))
        tk.Label(g2, text="Valor (USD):").grid(row=0, column=0, sticky="w")
        self.v_valor = tk.StringVar(value="0")
        ttk.Entry(g2, textvariable=self.v_valor, width=16).grid(row=0, column=1, sticky="w", padx=4)
        tk.Label(g2, text="Prazo (temporadas):").grid(row=0, column=2, sticky="w", padx=(12, 0))
        self.v_prazo = tk.IntVar(value=self.conf["prazo_temporadas"])
        ttk.Spinbox(g2, from_=1, to=10, textvariable=self.v_prazo, width=5, command=self.simular).grid(
            row=0, column=3, sticky="w", padx=4)
        w.Botao(g2, "Simular", self.simular).grid(row=0, column=4, padx=6)
        w.Botao(g2, "Tomar empréstimo", self.tomar).grid(row=0, column=5)
        self.lbl_sim = tk.Label(g2, text="", anchor="w", fg=w.AZUL)
        self.lbl_sim.grid(row=1, column=0, columnspan=6, sticky="w", pady=(4, 0))
        w.Botao(self.rodape, "Fechar", self.destroy, largura=10).pack(side="right")
        self.carregar()

    def carregar(self):
        for ch in self.g_res.winfo_children():
            ch.destroy()
        st, cid, eq = self.st, self.cid, self.eq
        rec = economia.receita_prevista(st, cid, eq)
        fixas = economia.despesas_fixas_previstas(st, cid, eq)
        linhas = [("Caixa", eq["financas"]["caixa"]), ("Dívida total", economia.divida(eq)),
                  ("Crédito disponível", economia.limite_credito(st, cid, eq)),
                  ("Receita prevista na temporada (TV + patrocínios)", rec),
                  ("Despesas fixas previstas (salários, contratos, parcelas)", fixas),
                  ("Sobra prevista para desenvolvimento", rec - fixas)]
        for i, (n, v) in enumerate(linhas):
            tk.Label(self.g_res, text=n, anchor="w").grid(row=i, column=0, sticky="w")
            tk.Label(self.g_res, text=dinheiro(v), anchor="e", font=w.FONTE_NEGRITO,
                     fg="#a00000" if v < 0 else w.PRETO).grid(row=i, column=1, sticky="e", padx=20)
        tk.Label(self.g_res, text=f"Juros: {self.conf['juros_anual'] * 100:.1f}% ao ano. Falência após "
                                  f"{self.conf['semanas_para_falencia']} semanas com caixa negativo e sem crédito.",
                 fg=w.CINZA_ESCURO).grid(row=len(linhas), column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.tv.delete(*self.tv.get_children())
        for i, e in enumerate(eq.get("emprestimos", [])):
            self.tv.insert("", "end", iid=str(i), values=(f"{e['ano']} S{e['semana']:02d}", dinheiro(e["valor"]),
                                                          dinheiro(e["saldo"]), dinheiro(e["parcela"]),
                                                          e["parcelas_restantes"], f"{e['juros_anual'] * 100:.1f}%"))

    def _valor(self):
        try:
            return float(self.v_valor.get().replace(".", "").replace(",", "."))
        except ValueError:
            return 0.0

    def simular(self):
        v = self._valor()
        if v <= 0:
            self.lbl_sim.configure(text="Informe um valor.")
            return
        e = economia.simular_emprestimo(self.st, self.cid, v, self.v_prazo.get())
        total = e["parcela"] * e["parcelas_restantes"]
        self.lbl_sim.configure(text=f"{e['parcelas_restantes']} parcelas de {dinheiro(e['parcela'])} por corrida – "
                                    f"total {dinheiro(total)} (juros {dinheiro(total - v)}).")

    def tomar(self):
        v = self._valor()
        erro = acoes.executar(self.st, "emprestimo", valor=v, prazo=self.v_prazo.get())
        if erro:
            messagebox.showwarning("Empréstimo", erro, parent=self)
        self.carregar()

    def quitar(self):
        sel = self.tv.selection()
        if not sel:
            return
        erro = acoes.executar(self.st, "quitar_emprestimo", indice=int(sel[0]))
        if erro:
            messagebox.showwarning("Quitar", erro, parent=self)
        self.carregar()
