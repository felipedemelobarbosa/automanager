"""Editor: calcula os percentuais de retas e curvas de uma pista a partir do mapa (Wikipedia ou arquivo)."""
import base64
import io
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from . import win9x as w

CORES = {"reta": "#1060e0", "alta": "#10a010", "baixa": "#e01010"}
NOMES = {"retas": "Retas", "curvas_alta": "Curvas de alta", "curvas_baixa": "Curvas de baixa"}
LARG, ALT = 640, 450


class DialogoMapaPista(w.Dialogo):
    """Resultado: {"retas", "curvas_alta", "curvas_baixa"} (somam 100) e, se buscado, o artigo usado."""

    def __init__(self, master, evento, categoria):
        super().__init__(master, "Retas e curvas pelo mapa da pista", 1000, 700)
        from ..editor import mapa_pista as mp
        self.mp = mp
        self.ev = evento
        self.cfg = mp.config(categoria)
        self.im = None              # imagem PIL do mapa
        self.laco = None            # traçado reconhecido (pontos na imagem)
        self.marcados = []          # pontos marcados à mão
        self.marcando = False
        self.res = None
        self.artigo_usado = None
        w.BarraTitulo(self.corpo, f"{evento.get('nome', '')} – {evento.get('local', '')}").pack(fill="x")

        # --- fonte do mapa
        f1 = tk.Frame(self.corpo)
        f1.pack(fill="x", pady=(6, 2))
        tk.Label(f1, text="Artigo do circuito (Wikipedia em inglês):").pack(side="left")
        self.v_artigo = tk.StringVar(value=evento.get("wikipedia") or "")
        ttk.Entry(f1, textvariable=self.v_artigo, width=34).pack(side="left", padx=4)
        w.Botao(f1, "Buscar mapa na Wikipedia", self.buscar, padx=6).pack(side="left")
        w.Botao(f1, "Abrir arquivo do computador...", self.abrir_arquivo, padx=6).pack(side="left", padx=4)
        from .. import imagens
        if imagens.existe(evento.get("imagem")):
            w.Botao(f1, "Usar a imagem da pista", self.usar_imagem, padx=6).pack(side="left")

        # --- parâmetros
        f2 = tk.Frame(self.corpo)
        f2.pack(fill="x", pady=2)
        tk.Label(f2, text="Comprimento (km):").pack(side="left")
        self.v_km = tk.StringVar()
        ttk.Entry(f2, textvariable=self.v_km, width=7).pack(side="left", padx=(2, 10))
        tk.Label(f2, text="Critério:").pack(side="left")
        # oval: pela velocidade – as curvas de um superspeedway (raio ~300 m) passariam por curvas pelo raio
        self.v_crit = tk.StringVar(value=self.cfg["criterio_oval"] if evento.get("tipo_pista") == "oval"
                                   else self.cfg["criterio"])
        for val, rot in (("raio", "raio (m)"), ("velocidade", "velocidade (km/h)")):
            ttk.Radiobutton(f2, text=rot, value=val, variable=self.v_crit, command=self.desenhar).pack(side="left")
        w.Botao(f2, "Recalcular", self.calcular, padx=6).pack(side="left", padx=12)
        f3 = tk.Frame(self.corpo)                     # limites numa linha própria (não empurram o botão)
        f3.pack(fill="x", pady=2)
        self.v_lim = {}
        for k, rot in (("raio_reta", "Reta se raio ≥"), ("raio_baixa", "baixa se <"), ("vel_reta", "  Reta se vel. ≥"),
                       ("vel_baixa", "baixa se <"), ("aderencia", "  Aderência (g)")):
            tk.Label(f3, text=rot).pack(side="left")
            v = tk.StringVar(value=str(self.cfg[k]))
            ttk.Entry(f3, textvariable=v, width=5).pack(side="left", padx=1)
            self.v_lim[k] = v

        # --- mapa + resultado
        meio = tk.Frame(self.corpo)
        meio.pack(fill="both", expand=True, pady=4)
        self.cv = tk.Canvas(meio, width=LARG, height=ALT, bg=w.BRANCO, relief="sunken", bd=2, highlightthickness=0)
        self.cv.pack(side="left")
        self.cv.bind("<Button-1>", self.clique)
        dir_ = tk.Frame(meio, padx=8)
        dir_.pack(side="left", fill="both", expand=True)
        g = w.Grupo(dir_, "Resultado")
        g.pack(fill="x")
        self.lbl_res = tk.Label(g, text="Busque ou abra um mapa.", justify="left", anchor="w", wraplength=290)
        self.lbl_res.pack(fill="x")
        leg = tk.Frame(g)
        leg.pack(fill="x", pady=(6, 0))
        for k, rot in (("reta", "reta"), ("alta", "curva de alta"), ("baixa", "curva de baixa")):
            tk.Label(leg, text="■", fg=CORES[k]).pack(side="left")
            tk.Label(leg, text=rot).pack(side="left", padx=(0, 8))
        g2 = w.Grupo(dir_, "Traçado reconhecido errado ou não reconhecido?")
        g2.pack(fill="x", pady=(8, 0))
        tk.Label(g2, text="Marque o traçado à mão: clique ao longo da pista, em ordem, dando a volta completa "
                          "(mais pontos nas curvas). O laço fecha sozinho.", justify="left", wraplength=290,
                 fg=w.CINZA_ESCURO).pack(fill="x")
        b = tk.Frame(g2)
        b.pack(fill="x", pady=4)
        self.btn_marcar = w.Botao(b, "Marcar à mão", self.alternar_marcacao, padx=6)
        self.btn_marcar.pack(side="left")
        w.Botao(b, "Desfazer ponto", self.desfazer, padx=6).pack(side="left", padx=2)
        w.Botao(b, "Limpar", self.limpar, padx=6).pack(side="left")
        self.lbl_status = tk.Label(dir_, text="", fg=w.CINZA_ESCURO, justify="left", wraplength=290, anchor="w")
        self.lbl_status.pack(fill="x", pady=(8, 0))

        w.Botao(self.rodape, "Cancelar", self.cancelar, largura=10).pack(side="right", padx=2)
        w.Botao(self.rodape, "Aplicar na pista", self.aplicar, largura=16).pack(side="right", padx=2)
        if self.v_artigo.get():
            self.after(100, lambda: self.im is None and self.buscar())

    # ------------------------------------------------------------------ fontes
    def _ocupado(self, sim):
        self.config(cursor="watch" if sim else "")
        self.update()

    def buscar(self):
        titulo = self.v_artigo.get().strip()
        if not titulo:
            messagebox.showinfo("Mapa", "Informe o artigo do circuito na Wikipedia (em inglês).", parent=self)
            return
        self._ocupado(True)
        try:
            im, km, arquivo = self.mp.da_wikipedia(titulo)
        except self.mp.ErroMapa as e:
            messagebox.showwarning("Mapa", str(e), parent=self)
            return
        finally:
            self._ocupado(False)
        self.artigo_usado = titulo
        if km:
            self.v_km.set(f"{km:g}")
        self.carregar(im, f"Mapa: {arquivo}" + (f"  ·  comprimento do artigo: {km:g} km" if km else
                                                  "  ·  o artigo não informa o comprimento: preencha"))

    def abrir_arquivo(self):
        caminho = filedialog.askopenfilename(parent=self, title="Mapa da pista",
                                             filetypes=[("Imagens", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
                                                        ("Todos os arquivos", "*.*")])
        if not caminho:
            return
        try:
            im = self.mp.abrir(caminho)
        except Exception as e:                       # formato não suportado
            messagebox.showerror("Mapa", f"Não foi possível abrir a imagem:\n{e}", parent=self)
            return
        self.carregar(im, f"Arquivo: {caminho}  ·  informe o comprimento da pista")

    def usar_imagem(self):
        from .. import imagens
        self.carregar(self.mp.abrir(imagens.caminho_absoluto(self.ev["imagem"])),
                      "Imagem da pista cadastrada  ·  informe o comprimento da pista")

    def carregar(self, im, texto):
        self.im = im
        self.marcados = []
        self.laco = None
        self.res = None
        self.lbl_status.configure(text=texto)
        self._ocupado(True)
        try:
            self.laco = self.mp.tracar(im)
        except self.mp.ErroMapa as e:
            self.lbl_status.configure(text=texto + "\n\n" + str(e))
        finally:
            self._ocupado(False)
        f = min(LARG / im.width, ALT / im.height)
        self.f = f
        mostra = im.resize((max(1, round(im.width * f)), max(1, round(im.height * f))))
        buf = io.BytesIO()
        mostra.save(buf, "PNG")
        self.foto = tk.PhotoImage(data=base64.b64encode(buf.getvalue()))
        self.calcular()

    # ------------------------------------------------------------------ marcação manual
    def alternar_marcacao(self):
        if self.im is None:
            return
        self.marcando = not self.marcando
        self.btn_marcar.configure(relief="sunken" if self.marcando else "raised")
        if self.marcando and not self.marcados:
            self.res = None
            self.desenhar()

    def clique(self, e):
        if not self.marcando or self.im is None:
            return
        self.marcados.append((e.x / self.f, e.y / self.f))
        self.calcular()

    def desfazer(self):
        if self.marcados:
            self.marcados.pop()
            self.calcular()

    def limpar(self):
        self.marcados = []
        self.calcular()

    # ------------------------------------------------------------------ conta
    def _ler_cfg(self):
        try:
            for k, v in self.v_lim.items():
                self.cfg[k] = float(v.get().replace(",", "."))
            km = float(self.v_km.get().replace(",", "."))
            if km <= 0:
                raise ValueError
            return km
        except ValueError:
            return None

    def calcular(self):
        self.res = None
        laco = self.mp.spline_fechada(self.marcados) if len(self.marcados) >= 4 else \
            (None if self.marcados or self.marcando else self.laco)
        km = self._ler_cfg()
        if laco and km:
            self.res = self.mp.analisar(laco, km, self.cfg)
        elif laco and not km:
            self.lbl_res.configure(text="Informe o comprimento da pista (km) e clique em Recalcular.")
        self.desenhar()

    def desenhar(self):
        cv = self.cv
        cv.delete("all")
        if self.im is None:
            return
        cv.create_image(0, 0, image=self.foto, anchor="nw")
        f = self.f
        if self.res:
            pts = self.res["pontos"]
            cl = self.res["classes"][self.v_crit.get()]
            n = len(pts)
            for i in range(n):
                a, b = pts[i], pts[(i + 1) % n]
                cv.create_line(a[0] * f, a[1] * f, b[0] * f, b[1] * f, fill=CORES[cl[i]], width=4)
        for i, (x, y) in enumerate(self.marcados):
            cv.create_oval(x * f - 3, y * f - 3, x * f + 3, y * f + 3, outline="#000000", fill="#ffff00")
            if i:
                px, py = self.marcados[i - 1]
                cv.create_line(px * f, py * f, x * f, y * f, fill="#808000", dash=(2, 2))
        if self.res:
            p = self.res["percentuais"]
            crit = self.v_crit.get()
            outro = "velocidade" if crit == "raio" else "raio"
            linhas = [f"Critério escolhido ({'raio' if crit == 'raio' else 'velocidade'}):"]
            linhas += [f"   {NOMES[k]}: {p[crit][k]}%" for k in NOMES]
            linhas += ["", f"Pelo outro critério ({outro}):"] + [f"   {NOMES[k]}: {p[outro][k]}%" for k in NOMES]
            fonte = "marcado à mão" if len(self.marcados) >= 4 else "reconhecido automaticamente"
            linhas += ["", f"Traçado {fonte}. Menor raio: {min(self.res['raios']):.0f} m."]
            self.lbl_res.configure(text="\n".join(linhas))
        elif self.marcando:
            self.lbl_res.configure(text=f"Marcando: {len(self.marcados)} ponto(s). Com 4 ou mais, a conta aparece.")
        elif self.laco is None:
            self.lbl_res.configure(text="Traçado não reconhecido: use 'Marcar à mão'.")

    def aplicar(self):
        if not self.res:
            messagebox.showinfo("Mapa", "Ainda não há resultado para aplicar.", parent=self)
            return
        self.resultado = dict(self.res["percentuais"][self.v_crit.get()])
        if self.artigo_usado:
            self.resultado["wikipedia"] = self.artigo_usado
        self.destroy()
