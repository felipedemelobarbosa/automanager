"""Multijogador: o comissário define o calendário da próxima temporada (com o formulário do editor) e os jogadores
o consultam."""
import copy
import tkinter as tk
from tkinter import ttk, messagebox

from .. import calendario_liga, paises
from . import win9x as w
from .editor_tela import AbaEntidades, Esquemas


class _EditorCalendario:
    """O mínimo do editor de database que a aba de calendário usa."""

    def __init__(self, categoria, eventos):
        self.dados = {"categoria": categoria, "calendario": eventos}
        self.erros_por_item = {}
        self.alterado = False

    def modificado(self, valor=True):
        self.alterado = self.alterado or valor

    def renomear_referencias(self, chave, antigo, novo):
        pass                                      # no meio da liga, só o calendário é editado


def _base(st, cid):
    d = calendario_liga.proximo(st, cid)
    return copy.deepcopy(d["eventos"] if d else st["categorias"][cid]["calendario"])


class DialogoCalendarioProximo(w.Dialogo):
    """Comissário: edita o calendário da próxima temporada de uma categoria. resultado = cid salvo (ou None)."""

    def __init__(self, master, st):
        self.ano = st["ano"] + 1
        super().__init__(master, f"Calendário da temporada {self.ano}", 1180, 700)
        self.resizable(True, True)
        self.st = st
        self.cids = list(st["categorias"])
        topo = tk.Frame(self.corpo)
        topo.pack(fill="x")
        tk.Label(topo, text="Categoria:").pack(side="left")
        self.cb = ttk.Combobox(topo, state="readonly", width=28,
                               values=[st["categorias"][c]["categoria"]["nome"] for c in self.cids])
        self.cb.pack(side="left", padx=4)
        self.cb.bind("<<ComboboxSelected>>", lambda e: self._trocar())
        self.lbl_estado = tk.Label(topo, text="", fg=w.CINZA_ESCURO)
        self.lbl_estado.pack(side="left", padx=8)
        tk.Label(self.corpo, text=f"Edite como no editor da database: ative ou desative eventos, mude semanas e voltas, "
                                  f"crie pistas novas (Novo... / Duplicar). Vale a partir de {self.ano}; os jogadores "
                                  f"veem o calendário assim que ele é salvo. Sem calendário definido, a virada segue "
                                  f"o sorteio normal (entradas e saídas da database).",
                 fg=w.CINZA_ESCURO, wraplength=1120, justify="left").pack(anchor="w", pady=(4, 4))
        self.area = tk.Frame(self.corpo)
        self.area.pack(fill="both", expand=True)
        self.aba = None
        w.Botao(self.rodape, "Fechar", self.cancelar, largura=10).pack(side="right", padx=2)
        w.Botao(self.rodape, f"Salvar calendário de {self.ano}", self._salvar, padx=8).pack(side="right", padx=2)
        self.b_sorteio = w.Botao(self.rodape, "Voltar ao sorteio", self._voltar_sorteio, padx=8)
        self.b_sorteio.pack(side="left", padx=2)
        cid0 = st["usuario"].get("categoria") if st["usuario"].get("categoria") in self.cids else self.cids[0]
        self.cb.current(self.cids.index(cid0))
        self._trocar()

    def cid(self):
        return self.cids[self.cb.current()]

    def _trocar(self):
        if self.aba is not None:
            self.aba.destroy()
        cid = self.cid()
        self.ed = _EditorCalendario(self.st["categorias"][cid]["categoria"], _base(self.st, cid))
        self.aba = AbaEntidades(self.area, self.ed, "calendario", Esquemas(self.ed).calendario_campos())
        self.aba.pack(fill="both", expand=True)
        self.aba.recarregar()
        definido = calendario_liga.proximo(self.st, cid) is not None
        self.lbl_estado.configure(text=f"Calendário de {self.ano} já definido pelo comissário." if definido
                                  else f"Ainda não definido: {self.ano} segue o sorteio normal.")
        self.b_sorteio.configure(state="normal" if definido else "disabled")

    def _salvar(self):
        self.aba.confirmar()
        cid = self.cid()
        erro = calendario_liga.definir(self.st, cid, self.ed.dados["calendario"])
        if erro:
            messagebox.showwarning("Calendário", erro, parent=self)
            return
        self.resultado = cid
        messagebox.showinfo("Calendário", f"Calendário de {self.ano} salvo. Os jogadores o recebem no arquivo da "
                                          f"liga (já publicado na pasta compartilhada, se houver).", parent=self)
        self._trocar()

    def _voltar_sorteio(self):
        cid = self.cid()
        if messagebox.askyesno("Calendário", f"Descartar o calendário definido? Em {self.ano} vale o sorteio "
                                             f"normal.", parent=self):
            calendario_liga.limpar(self.st, cid)
            self.resultado = cid
            self._trocar()


class DialogoVerCalendario(w.Dialogo):
    """Jogadores (e comissário): calendário da categoria nesta temporada e, se definido, o da próxima."""

    def __init__(self, master, st, cid):
        c = st["categorias"][cid]
        super().__init__(master, f"Calendário – {c['categoria']['nome']}", 760, 560)
        prox = calendario_liga.proximo(st, cid)
        nb = ttk.Notebook(self.corpo)
        nb.pack(fill="both", expand=True)
        abas = [(f"Temporada {st['ano']}", c["calendario"])]
        if prox:
            abas.append((f"Temporada {prox['ano']} (definida pelo comissário)", prox["eventos"]))
        for titulo, eventos in abas:
            fr = tk.Frame(nb)
            nb.add(fr, text=titulo)
            t, tv = w.tabela(fr, [("sem", "Sem."), ("nome", "Evento"), ("local", "Local"), ("tipo", "Tipo"),
                                  ("voltas", "Voltas")], 18,
                             {"sem": 44, "nome": 240, "local": 190, "tipo": 110, "voltas": 60}, estica={"nome"},
                             cores=True)
            t.pack(fill="both", expand=True)
            for ev in sorted((e for e in eventos if e.get("ativo")), key=lambda e: e["semana"]):
                tv.insert("", "end", image=w.ficha(pais=paises.do_local(ev.get("local")), com_cor=False),
                          values=(ev["semana"], ev["nome"], ev.get("local", ""),
                                  "corrida" if ev["especie"] == "corrida" else "teste coletivo",
                                  ev.get("voltas_corrida", "") if ev["especie"] == "corrida" else ""))
        if not prox:
            tk.Label(self.corpo, text=f"O comissário ainda não definiu o calendário de {st['ano'] + 1}: na virada vale "
                                      f"o sorteio normal.", fg=w.CINZA_ESCURO).pack(anchor="w", pady=(4, 0))
        w.Botao(self.rodape, "Fechar", self.cancelar, largura=10).pack(side="right")
