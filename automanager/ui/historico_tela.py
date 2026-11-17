"""Histórico: temporada atual (todas as categorias), temporadas anteriores e pontuação total."""
import tkinter as tk
from tkinter import ttk

from .. import campeonato
from ..util import dinheiro, relogio, tempo_volta
from . import win9x as w


def _achar_equipe(st, cid=None, eid=None, nome=None):
    """Equipe pelo ID ou pelo nome (em todas as categorias se cid for None); sem achar, um dict para a cor padrão."""
    cats = [st["categorias"][cid]] if cid in st["categorias"] else list(st["categorias"].values())
    for c in cats:
        if eid and eid in c["equipes"]:
            return c["equipes"][eid]
        for e in c["equipes"].values():
            if nome and e["nome"] == nome:
                return e
    return {"id": eid or nome or "?"}


def _nac(st, l):
    """Nacionalidade do piloto de uma linha de resultado (gravada na linha ou procurada pelo ID)."""
    if l.get("nacionalidade"):
        return l["nacionalidade"]
    pid = l.get("piloto") or l.get("id")
    p = st["pilotos"].get(pid) or st.get("aposentados", {}).get(pid) or {}
    return p.get("nacionalidade")


def _tabela_pilotos(master, linhas, usuario_eq=None, st=None, cid=None):
    cols = [("pos", "P"), ("nome", "Piloto"), ("nac", "Nacionalidade"), ("eq", "Equipe"), ("v", "Vitórias"),
            ("pod", "Pódios"), ("pts", "Pontos")]
    fr, tv = w.tabela(master, cols, 14, {"pos": 30, "nome": 160, "nac": 100, "eq": 150, "v": 60, "pod": 60, "pts": 60},
                      {"pos": "center", "v": "center", "pod": "center", "pts": "center"}, estica={"nome", "eq"}, cores=True)
    for i, p in enumerate(linhas, 1):
        tv.insert("", "end", image=w.chip_equipe(_achar_equipe(st, cid, nome=p.get("equipe")), p.get("nacionalidade")), values=(i, p["nome"], p.get("nacionalidade", ""), p.get("equipe", ""), p["vitorias"],
                                     p["podios"], p["pontos"]),
                  tags=("usuario",) if usuario_eq and p.get("equipe") == usuario_eq else ())
    return fr


def _tabela_equipes(master, linhas, usuario_eq=None, st=None, cid=None):
    cols = [("pos", "P"), ("nome", "Equipe"), ("v", "Vitórias"), ("pod", "Pódios"), ("pts", "Pontos")]
    fr, tv = w.tabela(master, cols, 14, {"pos": 30, "nome": 200, "v": 60, "pod": 60, "pts": 60},
                      {"pos": "center", "v": "center", "pod": "center", "pts": "center"}, estica={"nome"}, cores=True)
    for i, e in enumerate(linhas, 1):
        eq = _achar_equipe(st, cid, eid=e.get("id"), nome=e["nome"])
        tv.insert("", "end", image=w.chip_equipe(eq, eq.get("nacionalidade")), values=(i, e["nome"], e["vitorias"], e["podios"], e["pontos"]),
                  tags=("usuario",) if usuario_eq and e["nome"] == usuario_eq else ())
    return fr


class PainelTemporada(ttk.Notebook):
    """Classificação de pilotos e equipes + resultado de cada corrida de uma categoria/ano."""

    def __init__(self, master, st, cid, ano, financas=False):
        super().__init__(master)
        self.st = st
        temp = st.get("temporadas", {}).get(str(ano), {}).get(cid, {"corridas": [], "final": None})
        if temp.get("final"):
            pil, eqs = temp["final"]["pilotos"], temp["final"]["equipes"]
        else:
            pil, eqs = campeonato.classificacao(st, cid, ano)
        u = st["usuario"]
        nome_u = st["categorias"][u["categoria"]]["equipes"][u["equipe"]]["nome"] if cid == u["categoria"] else None
        self.cid = cid
        self.add(_tabela_pilotos(self, pil, nome_u, st, cid), text="Pilotos")
        self.add(_tabela_equipes(self, eqs, nome_u, st, cid), text="Equipes")
        # corridas
        f = tk.Frame(self, padx=4, pady=4)
        self.corridas = temp["corridas"]
        self.lb = tk.Listbox(f, width=34, relief="sunken", bd=2, exportselection=False)
        for r in self.corridas:
            self.lb.insert("end", f"S{r['semana']:02d}  {r['nome']}")
        self.lb.pack(side="left", fill="y")
        dir_ = tk.Frame(f)
        dir_.pack(side="left", fill="both", expand=True, padx=(6, 0))
        self.lbl = tk.Label(dir_, text="Selecione uma corrida.", anchor="w", justify="left")
        self.lbl.pack(fill="x")
        cols = [("pos", "P"), ("nome", "Piloto"), ("eq", "Equipe"), ("grid", "Grid"), ("v", "Voltas"),
                ("tempo", "Tempo/Status"), ("pit", "Pit"), ("pts", "Pts")]
        fr, self.tv = w.tabela(dir_, cols, 14, {"pos": 30, "nome": 140, "eq": 130, "grid": 40, "v": 45, "tempo": 100,
                                                "pit": 30, "pts": 35},
                               {k: "center" for k in ("pos", "grid", "v", "pit", "pts")}, estica={"nome", "eq"},
                               cores=True)
        fr.pack(fill="both", expand=True)
        self.lb.bind("<<ListboxSelect>>", self._corrida)
        self.add(f, text=f"Corridas ({len(self.corridas)})")
        # regulamento: regras em vigor (temporada atual) e mudanças anunciadas/aplicadas no ano
        from .. import regulamento
        reg = st["categorias"][cid].get("regulamento") or {}
        linhas = regulamento.descricao_atual(st, cid) if ano == st["ano"] else []
        linhas += [h["texto"] for h in reg.get("historico", [])
                   if (h["ano"] == ano or h.get("anunciado_em") == ano) and h["texto"] not in linhas]
        if linhas:
            fr_r = tk.Frame(self, padx=8, pady=8)
            for x in linhas:
                tk.Label(fr_r, text=x, anchor="w", justify="left", wraplength=880).pack(fill="x", pady=1)
            self.add(fr_r, text="Regulamento")
        # testes coletivos
        self.testes = temp.get("testes", [])
        if self.testes:
            ft = tk.Frame(self, padx=4, pady=4)
            self.lb_t = tk.Listbox(ft, width=34, relief="sunken", bd=2, exportselection=False)
            self.itens_t = []
            for t in self.testes:
                self.lb_t.insert("end", f"S{t['semana']:02d}  {t['nome']} – geral")
                self.itens_t.append((t, None))
                for d in t["dias"]:
                    self.lb_t.insert("end", f"        {d['nome']} ({d['clima']})")
                    self.itens_t.append((t, d))
            self.lb_t.pack(side="left", fill="y")
            dir_t = tk.Frame(ft)
            dir_t.pack(side="left", fill="both", expand=True, padx=(6, 0))
            self.lbl_t = tk.Label(dir_t, text="Selecione um teste.", anchor="w", justify="left")
            self.lbl_t.pack(fill="x")
            cols_t = [("pos", "P"), ("nome", "Piloto"), ("eq", "Equipe"), ("t", "Melhor volta"), ("gap", "Diferença"),
                      ("v", "Voltas")]
            fr_t, self.tv_t = w.tabela(dir_t, cols_t, 14, {"pos": 30, "nome": 150, "eq": 150, "t": 90, "gap": 80,
                                                           "v": 50},
                                       {"pos": "center", "t": "e", "gap": "e", "v": "center"}, estica={"nome", "eq"},
                                       cores=True)
            fr_t.pack(fill="both", expand=True)
            self.lb_t.bind("<<ListboxSelect>>", self._teste)
            self.add(ft, text=f"Testes coletivos ({len(self.testes)})")
        if financas:
            self.add(self._financas(cid, ano), text="Finanças da sua equipe")

    def _corrida(self, _e=None):
        sel = self.lb.curselection()
        if not sel:
            return
        r = self.corridas[sel[0]]
        extra = f"Pole: {r.get('pole') or '-'}"
        if r.get("volta_rapida"):
            extra += f"   |   Volta mais rápida: {r['volta_rapida']['nome']}"
        self.lbl.configure(text=f"{r['nome']} – {r['local']}\n{extra}")
        self.tv.delete(*self.tv.get_children())
        lider = r["resultado"][0]["tempo"] if r["resultado"] else 0
        for l in r["resultado"]:
            if l["status"] != "Fim":
                t = l["status"]
            elif l["pos"] == 1:
                t = relogio(l["tempo"])
            else:
                t = f"+{l['tempo'] - lider:.3f}"
            self.tv.insert("", "end", image=w.chip_equipe(_achar_equipe(self.st, self.cid, eid=l["equipe"]),
                                                          _nac(self.st, l)),
                           values=(l["pos"], l["nome"], l["equipe_nome"], l.get("grid") or "", l["voltas"],
                                              t, l.get("paradas", ""), l["pontos"]))

    def _teste(self, _e=None):
        sel = self.lb_t.curselection()
        if not sel:
            return
        t, d = self.itens_t[sel[0]]
        linhas = d["resultado"] if d else t["geral"]
        self.lbl_t.configure(text=f"{t['nome']} – {t['local']} – {d['nome'] + ' (' + d['clima'] + ')' if d else 'melhor volta de todos os dias'}")
        self.tv_t.delete(*self.tv_t.get_children())
        u = self.st["usuario"]
        lider = next((l["melhor"] for l in linhas if l.get("melhor")), None)
        for l in linhas:
            gap = f"+{l['melhor'] - lider:.3f}" if l.get("melhor") and lider and l["melhor"] != lider else ""
            self.tv_t.insert("", "end", image=w.chip_equipe(_achar_equipe(self.st, self.cid, eid=l["equipe"]),
                                                            _nac(self.st, l)),
                             values=(l["pos"], l["nome"], l["equipe_nome"], tempo_volta(l.get("melhor")),
                                                gap, l.get("voltas_total", l.get("voltas", ""))),
                             tags=("usuario",) if l["equipe"] == u["equipe"] else ())

    def _financas(self, cid, ano):
        f = tk.Frame(self, padx=10, pady=10)
        u = self.st["usuario"]
        hist = self.st["categorias"].get(cid, {}).get("historico_financas", {}).get(u["equipe"], {}).get(str(ano))
        if cid != u["categoria"] or not hist:
            tk.Label(f, text="Sem dados financeiros da sua equipe nesta categoria/ano.").pack(anchor="w")
            return f
        rec, desp = sum(hist["receitas"].values()), sum(hist["despesas"].values())
        linhas = [("Receitas", rec)] + [(f"   {k}", v) for k, v in hist["receitas"].items()] + \
                 [("Despesas", desp)] + [(f"   {k}", v) for k, v in hist["despesas"].items()] + [("Balanço", rec - desp)]
        for i, (n, v) in enumerate(linhas):
            fonte = w.FONTE if n.startswith("   ") else w.FONTE_NEGRITO
            tk.Label(f, text=n, font=fonte).grid(row=i, column=0, sticky="w")
            tk.Label(f, text=dinheiro(v), font=fonte).grid(row=i, column=1, sticky="e", padx=20)
        return f


class JanelaTemporadaAtual(w.Dialogo):
    def __init__(self, master, st):
        super().__init__(master, f"Histórico – temporada {st['ano']}", 980, 600)
        w.BarraTitulo(self.corpo, f"Temporada {st['ano']} – todas as categorias").pack(fill="x", pady=(0, 4))
        nb = ttk.Notebook(self.corpo)
        nb.pack(fill="both", expand=True)
        for cid, c in st["categorias"].items():
            nb.add(PainelTemporada(nb, st, cid, st["ano"]), text=c["categoria"]["nome"])
        w.Botao(self.rodape, "Fechar", self.destroy, largura=10).pack(side="right")


class JanelaTemporadasAnteriores(w.Dialogo):
    def __init__(self, master, st):
        super().__init__(master, "Histórico – temporadas anteriores", 980, 620)
        self.st = st
        w.BarraTitulo(self.corpo, "Temporadas anteriores").pack(fill="x", pady=(0, 4))
        topo = tk.Frame(self.corpo)
        topo.pack(fill="x")
        self.anos = sorted((a for a, cats in st.get("temporadas", {}).items()
                            if any(t.get("final") for t in cats.values())), reverse=True)
        self.cats = list(st["categorias"])
        tk.Label(topo, text="Ano:").pack(side="left")
        self.cb_ano = ttk.Combobox(topo, values=self.anos, state="readonly", width=8)
        self.cb_ano.pack(side="left", padx=4)
        tk.Label(topo, text="Categoria:").pack(side="left", padx=(10, 0))
        self.cb_cat = ttk.Combobox(topo, values=[st["categorias"][c]["categoria"]["nome"] for c in self.cats],
                                   state="readonly", width=22)
        self.cb_cat.pack(side="left", padx=4)
        self.area = tk.Frame(self.corpo)
        self.area.pack(fill="both", expand=True, pady=4)
        g = w.Grupo(self.corpo, "Campeões")
        g.pack(fill="x")
        cols = [("ano", "Ano"), ("cat", "Categoria"), ("pil", "Piloto"), ("eq", "Equipe")]
        fr, tv = w.tabela(g, cols, 4, {"ano": 60, "cat": 140, "pil": 180, "eq": 180}, estica={"pil", "eq"}, cores=True)
        fr.pack(fill="x")
        for c in reversed(campeonato.campeoes(st)):
            tv.insert("", "end", image=w.chip_equipe(_achar_equipe(st, nome=c["equipe"]), c.get("nacionalidade")),
                      values=(c["ano"], c["categoria"], c["piloto"], c["equipe"]))
        w.Botao(self.rodape, "Fechar", self.destroy, largura=10).pack(side="right")
        if not self.anos:
            tk.Label(self.area, text="Ainda não há temporadas encerradas.").pack(anchor="w")
            return
        self.cb_ano.current(0)
        ucat = (st.get("usuario") or {}).get("categoria")
        self.cb_cat.current(self.cats.index(ucat) if ucat in self.cats else 0)
        for cb in (self.cb_ano, self.cb_cat):
            cb.bind("<<ComboboxSelected>>", lambda e: self.mostrar())
        self.mostrar()

    def mostrar(self):
        for ch in self.area.winfo_children():
            ch.destroy()
        PainelTemporada(self.area, self.st, self.cats[self.cb_cat.current()], int(self.cb_ano.get()),
                        financas=True).pack(fill="both", expand=True)


class JanelaTotal(w.Dialogo):
    def __init__(self, master, st):
        super().__init__(master, "Histórico – pontuação total", 900, 560)
        self.st = st
        w.BarraTitulo(self.corpo, "Pontuação somada de todas as temporadas").pack(fill="x", pady=(0, 4))
        topo = tk.Frame(self.corpo)
        topo.pack(fill="x")
        self.cats = [None] + list(st["categorias"])
        tk.Label(topo, text="Categoria:").pack(side="left")
        self.cb = ttk.Combobox(topo, state="readonly", width=24,
                               values=["Todas (total geral)"] + [st["categorias"][c]["categoria"]["nome"]
                                                                 for c in self.cats[1:]])
        self.cb.current(0)
        self.cb.pack(side="left", padx=4)
        self.cb.bind("<<ComboboxSelected>>", lambda e: self.mostrar())
        self.area = tk.Frame(self.corpo)
        self.area.pack(fill="both", expand=True, pady=4)
        w.Botao(self.rodape, "Fechar", self.destroy, largura=10).pack(side="right")
        self.mostrar()

    def mostrar(self):
        for ch in self.area.winfo_children():
            ch.destroy()
        pil, eqs = campeonato.total_geral(self.st, self.cats[self.cb.current()])
        nb = ttk.Notebook(self.area)
        nb.pack(fill="both", expand=True)
        cols = [("pos", "P"), ("nome", "Piloto"), ("nac", "Nacionalidade"), ("temp", "Temporadas"), ("tit", "Títulos"),
                ("v", "Vitórias"), ("pod", "Pódios"), ("pts", "Pontos")]
        cen = {k: "center" for k in ("pos", "temp", "tit", "v", "pod", "pts")}
        fr, tv = w.tabela(nb, cols, 16, {"pos": 30, "nome": 180, "nac": 100, "temp": 80, "tit": 55, "v": 60, "pod": 60,
                                         "pts": 60}, cen, estica={"nome"}, cores=True)
        for i, p in enumerate(pil, 1):
            tv.insert("", "end", image=w.ficha(pais=p.get("nacionalidade"), com_cor=False), values=(i, p["nome"], p["nacionalidade"], p["temporadas"], p["titulos"], p["vitorias"],
                                         p["podios"], p["pontos"]))
        nb.add(fr, text="Pilotos")
        cols = [("pos", "P"), ("nome", "Equipe"), ("temp", "Temporadas"), ("tit", "Títulos"), ("v", "Vitórias"),
                ("pod", "Pódios"), ("pts", "Pontos")]
        fr2, tv2 = w.tabela(nb, cols, 16, {"pos": 30, "nome": 220, "temp": 80, "tit": 55, "v": 60, "pod": 60,
                                           "pts": 60}, cen, estica={"nome"}, cores=True)
        for i, e in enumerate(eqs, 1):
            eq = _achar_equipe(self.st, nome=e["nome"])
            tv2.insert("", "end", image=w.chip_equipe(eq, eq.get("nacionalidade")), values=(i, e["nome"], e["temporadas"], e["titulos"], e["vitorias"], e["podios"],
                                          e["pontos"]))
        nb.add(fr2, text="Equipes")
