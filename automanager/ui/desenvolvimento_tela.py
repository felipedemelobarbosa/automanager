"""Tela de desenvolvimento: carro desta temporada e carro da próxima temporada."""
import tkinter as tk
from tkinter import ttk, messagebox

from .. import desenvolvimento as dev, acoes, regulamento
from ..db import NOMES_ATRIBUTOS
from ..util import dinheiro
from . import win9x as w


class PainelDev(tk.Frame):
    """Uma aba: lista de atributos de cada parte com alvo e custo."""

    def __init__(self, master, janela, proxima):
        super().__init__(master, padx=6, pady=6)
        self.j, self.proxima = janela, proxima
        st, cid, eq = janela.st, janela.cid, janela.eq
        self.linhas = {}       # (parte, atributo) -> (IntVar, label custo, valor atual)
        self.modos = {}
        cfg = dev.config(st, cid)
        perda = cfg.get('perda_manutencao', 0.3) * 100
        texto = (f"Carro da PRÓXIMA temporada – escolha UMA das opções:\n"
                 f"• Manutenção: o carro atual, como estiver no fim da temporada, com perda de {perda:.0f}% em cada "
                 f"atributo. Não há investimento (melhorar o carro desta temporada também melhora a manutenção).\n"
                 f"• Projeto novo: começa do zero e recebe investimento ponto a ponto."
                 if proxima else "Investimento no carro DESTA temporada: a evolução vale na hora.")
        if proxima and dev.cliente(st, cid, eq, "chassis") and not dev.pode(st, cid, eq, "motor"):
            texto = ("Carro da PRÓXIMA temporada – chassis: escolha UMA das opções:\n"
                     "• Comprar no Mercado: contrato com um fornecedor ou outra equipe (Mercado > Chassis).\n"
                     "• Projeto novo: chassis próprio, começa do zero e recebe investimento ponto a ponto.")
        tk.Label(self, text=texto, justify="left", wraplength=700).pack(anchor="w", pady=(0, 6))
        avisos = []                         # regulamento: limites e grande mudança
        for parte in dev.PARTES:
            if not dev.pode(st, cid, eq, parte):
                continue
            nome = "chassis" if parte == "chassis" else "motor"
            if proxima:
                if not dev.projeto_permitido(st, cid, parte):
                    avisos.append(f"Regulamento: o {nome} atual passa para {st['ano'] + 1} sem perda; não há projeto novo.")
                else:
                    extra = regulamento.perda_extra(st, cid, parte)
                    if extra:
                        avisos.append(f"Regulamento {st['ano'] + 1}: grande mudança – a manutenção do {nome} perde "
                                      f"{dev.perda_manutencao(st, cid, parte) * 100:.0f}% (mais {extra * 100:.0f}%).")
                    lim = regulamento.limite(st, cid, parte, st["ano"] + 1)
                    if lim is not None:
                        avisos.append(f"Regulamento {st['ano'] + 1}: desenvolvimento do {nome} "
                                      + ("congelado." if lim == 0 else f"limitado a {lim} pontos por atributo."))
            else:
                lim = regulamento.limite(st, cid, parte)
                if lim is not None:
                    avisos.append(f"Regulamento: desenvolvimento do {nome} congelado nesta temporada." if lim == 0 else
                                  f"Regulamento: no máximo {lim} pontos por atributo do {nome} nesta temporada.")
        for a in avisos:
            tk.Label(self, text=a, justify="left", fg="#a00000", anchor="w").pack(anchor="w")
        if proxima:                         # chassis comprado no Mercado (categoria que deixa escolher)
            from .. import state as _st
            prox = st["ano"] + 1
            fut = eq.get("chassis_futuro") if dev.comprado_para(st, eq, "chassis", prox) else None
            info = None
            if fut:
                nome_fut = st["categorias"][cid]["chassis"].get(fut["id"], {}).get("nome", fut["id"])
                info = f"Chassis de {prox} comprado no Mercado: {nome_fut}. Não há projeto próprio do chassis."
            elif dev.cliente_pode_voltar(st, cid, eq, "chassis"):
                info = (f"Chassis comprado: para {prox}, compre de novo no Mercado (Mercado > Chassis) ou faça um "
                        f"projeto novo (do zero).")
            elif dev.cliente(st, cid, eq, "chassis"):
                info = f"Chassis comprado, com contrato também para {prox}."
            elif dev.pode(st, cid, eq, "chassis") and _st.compra_de_chassis(st["categorias"][cid]["categoria"]):
                info = (f"Também é possível comprar o chassis de {prox} no Mercado (Mercado > Chassis, início na "
                        f"próxima temporada); o que foi investido no projeto se perde.")
            if info:
                tk.Label(self, text=info, justify="left", fg=w.AZUL, anchor="w", wraplength=700).pack(anchor="w")
        linha = tk.Frame(self)
        linha.pack(fill="both", expand=True)
        for parte in dev.PARTES:
            if not (dev.pode_projeto if proxima else dev.pode)(st, cid, eq, parte):
                continue
            c = cfg[parte]
            g = w.Grupo(linha, f"{'Chassis' if parte == 'chassis' else 'Motor'} – {dinheiro(c['custo_por_ponto'])}/ponto "
                               f"até {c.get('limite_custo_fixo', 50)}, depois progressivo")
            g.pack(side="left", fill="both", expand=parte == "chassis", padx=(0, 6))
            if proxima:
                v = tk.StringVar(value=dev.projeto(eq, parte)["modo"])
                self.modos[parte] = v
                f = tk.Frame(g)
                f.grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 4))
                ttk.Radiobutton(f, text="Comprar no Mercado" if dev.cliente(st, cid, eq, parte)
                                else "Manutenção do carro atual", value="manutencao", variable=v,
                                command=lambda p=parte: self._modo(p)).pack(side="left")
                rb = ttk.Radiobutton(f, text="Projeto novo (do zero)", value="novo", variable=v,
                                     command=lambda p=parte: self._modo(p))
                rb.pack(side="left", padx=8)
                if not dev.projeto_permitido(st, cid, parte):
                    rb.state(["disabled"])
            if proxima:
                self.avisos = getattr(self, "avisos", {})
                self.avisos[parte] = tk.Label(g, text="", fg=w.AZUL, anchor="w", justify="left")
                self.avisos[parte].grid(row=99, column=0, columnspan=5, sticky="w", pady=(4, 0))
            for col, t in enumerate(("Atributo", "Atual" if not proxima else "Próx. ano", "Alvo", "Custo")):
                tk.Label(g, text=t, font=w.FONTE_NEGRITO).grid(row=1, column=col, sticky="w", padx=3)
            for i, k in enumerate(dev.atributos_da_parte(parte), start=2):
                tk.Label(g, text=NOMES_ATRIBUTOS[k], anchor="w", width=15).grid(row=i, column=0, sticky="w")
                lbl_v = tk.Label(g, text="", width=4)
                lbl_v.grid(row=i, column=1)
                var = tk.IntVar()
                sp = ttk.Spinbox(g, from_=0, to=100, textvariable=var, width=5, command=self.recalcular)
                sp.grid(row=i, column=2, padx=3, pady=1)
                sp.bind("<KeyRelease>", lambda e: self.recalcular())
                lbl_c = tk.Label(g, text="", width=14, anchor="e")
                lbl_c.grid(row=i, column=3)
                self.linhas[(parte, k)] = [var, lbl_v, lbl_c, sp, 0]
        self.carregar()

    def _valores(self, parte):
        st, cid, eq = self.j.st, self.j.cid, self.j.eq
        return dev.valores_projeto(st, cid, eq, parte) if self.proxima else dev.valores_atuais(st, cid, eq, parte)

    def carregar(self):
        eq = self.j.eq
        for (parte, k), lin in self.linhas.items():
            v = self._valores(parte)[k]
            lin[4] = v
            lin[0].set(v)
            lin[1].configure(text=str(v))
            st, cid = self.j.st, self.j.cid
            manut = self.proxima and (dev.projeto(eq, parte)["modo"] != "novo" or not dev.projeto_permitido(st, cid, parte))
            tetos = None if self.proxima else dev.tetos_atual(st, cid, eq, parte)
            congelado = tetos is not None and tetos[k] <= v
            lin[3].configure(from_=v, to=tetos[k] if tetos else 100,
                             state="disabled" if manut or congelado else "normal")
        for parte, lbl in getattr(self, "avisos", {}).items():
            if dev.cliente(self.j.st, self.j.cid, eq, parte) and dev.projeto(eq, parte)["modo"] != "novo":
                lbl.configure(text="Sem projeto: o chassis da próxima temporada vem do Mercado.")
            elif not dev.projeto_permitido(self.j.st, self.j.cid, parte):
                lbl.configure(text="Regulamento: o carro atual continua, sem perda (sem investimento).")
            elif dev.projeto(eq, parte)["modo"] == "novo":
                lbl.configure(text="Projeto novo: defina os alvos e clique em Investir.")
            else:
                lbl.configure(text=f"Manutenção: valores do carro atual com a perda de "
                                   f"{dev.perda_manutencao(self.j.st, self.j.cid, parte) * 100:.0f}% (sem investimento).")
        self.recalcular()

    def _modo(self, parte):
        eq = self.j.eq
        novo = self.modos[parte].get()
        if dev.projeto(eq, parte)["investido"] and not messagebox.askyesno(
                "Trocar para manutenção", "Voltar para a manutenção descarta o que já foi investido no projeto "
                                          "novo. Continuar?", parent=self):
            self.modos[parte].set(dev.projeto(eq, parte)["modo"])
            return
        acoes.executar(self.j.st, "dev_modo", parte=parte, modo=novo)
        self.carregar()

    def alvos(self):
        out = {}
        for (parte, k), lin in self.linhas.items():
            try:
                alvo = int(lin[0].get())
            except (tk.TclError, ValueError):
                alvo = lin[4]
            if alvo > lin[4]:
                out.setdefault(parte, {})[k] = min(100, alvo)
        return out

    def recalcular(self):
        total = 0.0
        st, cid = self.j.st, self.j.cid
        for (parte, k), lin in self.linhas.items():
            try:
                alvo = int(lin[0].get())
            except (tk.TclError, ValueError):
                alvo = lin[4]
            custo = dev.custo_ate(dev.config(st, cid)[parte], lin[4], min(100, alvo)) if alvo > lin[4] else 0
            total += custo
            lin[2].configure(text=dinheiro(custo) if custo else "-")
        self.total = total
        self.j.atualizar_resumo()

    def investir(self):
        st = self.j.st
        alvos = self.alvos()
        if not alvos:
            return
        for parte, a in alvos.items():
            incrementos = {k: v - self.linhas[(parte, k)][4] for k, v in a.items()}
            erro = acoes.executar(st, "dev_investir", parte=parte, proxima=bool(self.proxima), incrementos=incrementos)
            if erro:
                messagebox.showwarning("Desenvolvimento", erro, parent=self)
                break
        self.carregar()


class JanelaDesenvolvimento(w.Dialogo):
    def __init__(self, master, st, aba=0):
        super().__init__(master, "Desenvolvimento", 820, 600)
        self.st = st
        self.cid, self.eid = st["usuario"]["categoria"], st["usuario"]["equipe"]
        self.eq = st["categorias"][self.cid]["equipes"][self.eid]
        w.BarraTitulo(self.corpo, f"Desenvolvimento – {self.eq['nome']}").pack(fill="x", pady=(0, 4))
        self.nb = ttk.Notebook(self.corpo)
        self.nb.pack(fill="both", expand=True)
        self.paineis = []
        self.lbl = tk.Label(self.rodape, text="", font=w.FONTE_NEGRITO, anchor="w")
        self.lbl.pack(side="left", fill="x", expand=True)
        w.Botao(self.rodape, "Fechar", self.destroy, largura=10).pack(side="right", padx=2)
        self.btn = w.Botao(self.rodape, "Investir", self.investir, largura=10)
        self.btn.pack(side="right", padx=2)
        for proxima, titulo in ((False, f"Carro desta temporada ({st['ano']})"),
                                (True, f"Carro da próxima temporada ({st['ano'] + 1})")):
            p = PainelDev(self.nb, self, proxima)
            self.nb.add(p, text=titulo)
            self.paineis.append(p)
        self.nb.select(aba)
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self.atualizar_resumo())
        self.atualizar_resumo()

    def painel(self):
        return self.paineis[self.nb.index(self.nb.select())] if self.paineis and self.nb.select() else None

    def atualizar_resumo(self):
        p = self.painel()
        if not p or not hasattr(p, "total") or not hasattr(self, "lbl"):
            return
        caixa = self.eq["financas"]["caixa"]
        self.lbl.configure(text=f"Caixa: {dinheiro(caixa)}    Investimento: {dinheiro(p.total)}    "
                                f"Restante: {dinheiro(caixa - p.total)}",
                           fg=w.PRETO if caixa >= p.total else "#a00000")
        self.btn.configure(state="normal" if 0 < p.total <= caixa else "disabled")

    def investir(self):
        p = self.painel()
        if p:
            p.investir()
            for outro in self.paineis:
                outro.carregar()
