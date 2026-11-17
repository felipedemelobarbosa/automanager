"""Protótipo de tela do evento (NÃO integrado ao restante do jogo).

O usuário escolhe uma categoria, um evento e uma equipe. Antes de cada sessão define o
acerto inicial de cada piloto; durante a sessão dá ordens (agressividade, uso do motor,
uso do carro), liga/desliga a estratégia automática e pode chamar o piloto ao box.
"""
import random
import tkinter as tk
from tkinter import ttk, messagebox

from .. import db, state
from ..event.sessoes import Evento
from ..event.inscritos import montar_inscritos
from ..event.modelo import PARAMETROS_ACERTO, NOMES_ACERTO, ORDENS, NOMES_ORDENS
from .. import paises
from . import win9x as w
from ..util import tempo_volta

VELOCIDADES = [("Lenta", 10, 0.5), ("Normal", 30, 1), ("Rápida", 90, 2), ("Muito rápida", 300, 5)]
NOMES_CURTOS_ACERTO = {"aerodinamica": "Asa", "cambio": "Relação", "suspensao": "Suspensão", "freios": "Freios"}
DIRECAO_ACERTO = {"aerodinamica": ("menos", "mais"), "cambio": ("mais curto", "mais longo"),
                  "suspensao": ("mais macia", "mais dura"), "freios": ("mais suaves", "mais fortes")}


class PainelFeedback(w.Grupo):
    """Último comentário do piloto (aba escolhida à direita) sobre o acerto: nota do setup e, para cada ajuste,
    uma régua com o valor atual (ponto) e uma seta na direção pedida – curta = um pouco, longa = bem."""
    L, H = 58, 14

    def __init__(self, master):
        super().__init__(master, "Feedback do acerto")
        self.carro = None
        self._chave = None
        pequena = (w.FONTE[0], 8)
        self.lbl_topo = tk.Label(self, text="", anchor="w", font=pequena)
        self.lbl_topo.pack(fill="x")
        frm = tk.Frame(self)
        frm.pack(anchor="w", pady=1)
        self.linhas = {}
        for i, k in enumerate(PARAMETROS_ACERTO):
            tk.Label(frm, text=NOMES_CURTOS_ACERTO[k], width=9, anchor="w", font=pequena).grid(row=i, column=0, sticky="w")
            cv = tk.Canvas(frm, width=self.L, height=self.H, bg=w.CINZA, highlightthickness=0)
            cv.grid(row=i, column=1, padx=2, pady=1)
            lb = tk.Label(frm, text="", anchor="w", font=pequena)
            lb.grid(row=i, column=2, sticky="w")
            self.linhas[k] = (cv, lb)
        self.lbl_texto = tk.Label(self, text="", wraplength=185, justify="left", anchor="w", font=pequena)
        self.lbl_texto.pack(fill="x", pady=(2, 0))

    def mostrar(self, carro):
        self.carro = carro
        self._chave = None
        self.atualizar()

    def atualizar(self):
        c = self.carro
        if c is None:
            return
        fb = getattr(c, "feedback", None)
        chave = (c.id, id(fb))
        if chave == self._chave:
            return
        self._chave = chave
        self.configure(text=f" Feedback do acerto – {c.nome.split()[-1]} ")
        if not fb:
            self.lbl_topo.configure(text="Sem comentário ainda", fg=w.CINZA_ESCURO)
            for cv, lb in self.linhas.values():
                cv.delete("all")
                lb.configure(text="")
            self.lbl_texto.configure(text="O piloto comenta o acerto quando volta aos boxes nos treinos e na "
                                          "classificação.", fg=w.CINZA_ESCURO)
            return
        nota = int(fb.get("nota", 1))
        self.lbl_topo.configure(text=f"{fb['sessao']}, volta {fb['volta']} · Setup {'★' * nota}{'☆' * (5 - nota)}",
                                fg=w.PRETO)
        L, H = self.L, self.H
        for k, (cv, lb) in self.linhas.items():
            d = fb["diffs"].get(k, 0.0)
            cv.delete("all")
            cv.create_line(3, H // 2, L - 3, H // 2, fill=w.CINZA_ESCURO, width=2)
            x = 3 + (L - 6) * (fb.get("acerto") or c.acerto).get(k, 50) / 100   # acerto que o piloto testou
            if abs(d) < 7:
                cor, txt = "#3c9a3c", "ok ✓"
            else:
                grande = abs(d) > 22
                cor = "#c03030" if grande else "#d09a10"
                x2 = max(3, min(L - 3, x + (22 if grande else 11) * (1 if d > 0 else -1)))
                cv.create_line(x, H // 2, x2, H // 2, fill=cor, width=4, arrow="last", arrowshape=(7, 8, 4))
                palavra = DIRECAO_ACERTO[k][1 if d > 0 else 0]
                txt = f"bem {palavra}" if grande else palavra
            cv.create_oval(x - 4, H // 2 - 4, x + 4, H // 2 + 4, fill=w.BRANCO, outline=w.PRETO)
            lb.configure(text=txt, fg=cor)
        self.lbl_texto.configure(text=f"{c.nome} (sua equipe) {fb['texto']}.", fg=w.PRETO)
TIPOS_PISTA = {"mista": "Mista", "oval": "Oval", "rua": "Rua"}


# ============================================================================ configuração
class DialogoConfigEvento(w.Dialogo):
    def __init__(self, master):
        super().__init__(master, "Protótipo de evento", 460, 250)
        w.BarraTitulo(self.corpo, "Configurar evento de teste").pack(fill="x", pady=(0, 8))
        self.arquivos = db.todos_os_arquivos()
        f = tk.Frame(self.corpo)
        f.pack(fill="x")
        self.v_cat, self.v_ev, self.v_eq = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.v_seed = tk.StringVar()
        tk.Label(f, text="Categoria:").grid(row=0, column=0, sticky="w", pady=3)
        self.cb_cat = ttk.Combobox(f, textvariable=self.v_cat, state="readonly", width=40,
                                   values=[db.resumo_arquivo(a)["nome"] + f" ({db.resumo_arquivo(a)['ano']})"
                                           for a in self.arquivos])
        self.cb_cat.grid(row=0, column=1, pady=3)
        tk.Label(f, text="Evento:").grid(row=1, column=0, sticky="w", pady=3)
        self.cb_ev = ttk.Combobox(f, textvariable=self.v_ev, state="readonly", width=40)
        self.cb_ev.grid(row=1, column=1, pady=3)
        tk.Label(f, text="Sua equipe:").grid(row=2, column=0, sticky="w", pady=3)
        self.cb_eq = ttk.Combobox(f, textvariable=self.v_eq, state="readonly", width=40)
        self.cb_eq.grid(row=2, column=1, pady=3)
        tk.Label(f, text="Semente (opcional):").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Entry(f, textvariable=self.v_seed, width=12).grid(row=3, column=1, sticky="w", pady=3)
        self.cb_cat.bind("<<ComboboxSelected>>", lambda e: self._carregar())
        w.Botao(self.rodape, "Sair", self.cancelar, largura=10).pack(side="right", padx=2)
        w.Botao(self.rodape, "Iniciar", self.ok, largura=10).pack(side="right", padx=2)
        if self.arquivos:
            self.cb_cat.current(0)
            self._carregar()

    def _carregar(self):
        caminho = self.arquivos[self.cb_cat.current()]
        self.st = state.novo_jogo([caminho])
        self.cid = list(self.st["categorias"])[0]
        c = self.st["categorias"][self.cid]
        self.eventos = [e for e in c["calendario"] if e["especie"] == "corrida" and e.get("voltas_corrida")]
        self.cb_ev["values"] = [f"{e['nome']} – {e['local']}" for e in self.eventos]
        self.cb_ev.current(0)
        self.equipes = [e for e in c["equipes"].values() if e.get("ativa") and
                        state.chassis_da_equipe(self.st, self.cid, e) and state.motor_da_equipe(self.st, self.cid, e)]
        self.cb_eq["values"] = [e["nome"] for e in self.equipes]
        self.cb_eq.current(0)

    def ok(self):
        seed = self.v_seed.get().strip()
        rng = random.Random(int(seed)) if seed.isdigit() else random.Random()
        eq = self.equipes[self.cb_eq.current()]
        pista = self.eventos[self.cb_ev.current()]
        cat = self.st["categorias"][self.cid]["categoria"]
        ev = Evento(cat, pista, montar_inscritos(self.st, self.cid, eq["id"], pista), rng)
        if not any(c.usuario for c in ev.carros):
            messagebox.showwarning("Evento", "A equipe escolhida não tem pilotos principais.", parent=self)
            return
        self.resultado = ev
        self.destroy()


# ============================================================================ painel do piloto
class PainelPiloto(tk.Frame):
    def __init__(self, master, tela, carro):
        super().__init__(master, padx=4, pady=4)
        self.tela, self.carro = tela, carro
        ev = tela.ev
        comp = ev.cat["pneus"]["compostos"]
        self.compostos = ev.compostos_disponiveis()
        self.nomes_comp = [comp[k]["nome"] for k in self.compostos]

        info = tk.Frame(self)
        info.pack(fill="x")
        w.RotuloBandeira(info, carro.piloto.get("nacionalidade"), carro.nome, font=w.FONTE_NEGRITO).pack(anchor="w")
        linha_cm = tk.Frame(info)
        linha_cm.pack(anchor="w")
        for logo, nome, sep in ((carro.logo_chassis, carro.nome_chassis, " / "), (carro.logo_motor, carro.nome_motor, "")):
            img = w.Imagem(linha_cm, 40, 16, borda=False)
            if img.definir(logo):
                img.pack(side="left", padx=(0, 2))
            else:
                img.destroy()
            tk.Label(linha_cm, text=nome + sep, fg=w.CINZA_ESCURO).pack(side="left")
        self.lbl_estado = tk.Label(info, text="", anchor="w", justify="left", bg=w.AMARELO_INFO, relief="sunken", bd=1,
                                   width=36, height=4)
        self.lbl_estado.pack(fill="x", pady=(2, 4))

        # acerto inicial
        self.g_acerto = w.Grupo(self, "Acerto inicial da sessão")
        self.g_acerto.pack(fill="x")
        self.v_acerto = {}
        self.escalas = []
        for i, k in enumerate(PARAMETROS_ACERTO):
            v = tk.IntVar(value=50)
            self.v_acerto[k] = v
            tk.Label(self.g_acerto, text=NOMES_ACERTO[k], anchor="w", width=16).grid(row=i, column=0, sticky="w")
            e = tk.Scale(self.g_acerto, from_=0, to=100, orient="horizontal", variable=v, length=110, bd=1,
                         highlightthickness=0, troughcolor="#dfdfdf", showvalue=True, sliderlength=16, width=10)
            e.grid(row=i, column=1)
            self.escalas.append(e)
        n = len(PARAMETROS_ACERTO)
        tk.Label(self.g_acerto, text="Pneu inicial", anchor="w").grid(row=n, column=0, sticky="w", pady=2)
        self.cb_pneu = ttk.Combobox(self.g_acerto, values=self.nomes_comp, state="readonly", width=14)
        self.cb_pneu.grid(row=n, column=1, sticky="w")
        self.cb_pneu.current(min(2, len(self.compostos) - 1))
        tk.Label(self.g_acerto, text="Combustível (voltas)", anchor="w").grid(row=n + 1, column=0, sticky="w")
        self.v_comb = tk.StringVar(value="")
        self.sp_comb = ttk.Spinbox(self.g_acerto, from_=1, to=400, textvariable=self.v_comb, width=6)
        self.sp_comb.grid(row=n + 1, column=1, sticky="w")
        self.lbl_comb = tk.Label(self.g_acerto, text="", fg=w.CINZA_ESCURO, anchor="w")
        self.lbl_comb.grid(row=n + 2, column=0, columnspan=2, sticky="w")

        # ordens
        g_ord = w.Grupo(self, "Ordens ao piloto (durante a sessão)")
        g_ord.pack(fill="x", pady=(6, 0))
        self.v_ordens = {}
        for i, k in enumerate(ORDENS):
            v = tk.IntVar(value=0)
            self.v_ordens[k] = v
            tk.Label(g_ord, text=NOMES_ORDENS[k], anchor="w", width=13).grid(row=i, column=0, sticky="w")
            tk.Label(g_ord, text="-", fg=w.CINZA_ESCURO).grid(row=i, column=1)
            tk.Scale(g_ord, from_=-2, to=2, resolution=1, orient="horizontal", variable=v, length=100, bd=1,
                     highlightthickness=0, troughcolor="#dfdfdf", showvalue=True, sliderlength=16, width=10,
                     command=lambda _x, k=k: self._ordem(k)).grid(row=i, column=2)
            tk.Label(g_ord, text="+", fg=w.CINZA_ESCURO).grid(row=i, column=3)

        # estratégia / box
        g_box = w.Grupo(self, "Box")
        g_box.pack(fill="x", pady=(6, 0))
        self.v_auto = tk.BooleanVar(value=True)
        ttk.Checkbutton(g_box, text="Estratégia automática", variable=self.v_auto,
                        command=self._auto).grid(row=0, column=0, sticky="w")
        self.cb_box = ttk.Combobox(g_box, values=self.nomes_comp, state="readonly", width=14)
        self.cb_box.grid(row=1, column=0, sticky="w", pady=2)
        self.cb_box.current(min(2, len(self.compostos) - 1))
        self.btn_box = w.Botao(g_box, "Chamar ao box", self._box)
        self.btn_box.grid(row=1, column=1, padx=4)
        self.btn_volta = w.Botao(g_box, "Voltar à pista", self._voltar)
        self.btn_volta.grid(row=0, column=1, padx=4)
        self.lbl_box = tk.Label(g_box, text="", fg=w.CINZA_ESCURO, justify="left", wraplength=250)
        self.lbl_box.grid(row=2, column=0, columnspan=2, sticky="w")
        self._acerto_liberado = None

    # ------------------------------------------------------------------
    def preparar_sessao(self, tipo):
        """Libera o acerto para a nova sessão e mostra o acerto atual."""
        for k, v in self.v_acerto.items():
            v.set(self.carro.acerto[k])
        regras = self.tela.ev.cat["regras_pitstop"]
        if tipo == "corrida":
            voltas = getattr(self.tela.ev.sessao, "total_voltas", self.tela.ev.pista["voltas_corrida"])
            if regras.get("reabastecimento"):
                self.v_comb.set(str(self.carro.combustivel_inicial or voltas // 2))
                self.sp_comb.configure(state="normal", to=voltas + 1)
                self.lbl_comb.configure(text=f"Reabastecimento permitido – corrida de {voltas} voltas")
            else:
                self.v_comb.set(str(voltas + 1))
                self.sp_comb.configure(state="disabled")
                self.lbl_comb.configure(text="Sem reabastecimento: tanque cheio")
        else:
            self.v_comb.set("")
            self.sp_comb.configure(state="disabled")
            self.lbl_comb.configure(text="Treino/classificação: definido pela equipe")
        self.travar_acerto(False)
        self.btn_box.configure(state="disabled")

    def sincronizar(self):
        """Mostra nos controles o acerto/ordens que estão no carro (jogo carregado)."""
        c = self.carro
        for k, v in self.v_acerto.items():
            v.set(c.acerto.get(k, 50))
        for k, v in self.v_ordens.items():
            v.set(c.ordens.get(k, 0))
        self.v_auto.set(c.estrategia_auto)
        if c.pneu_inicial in self.compostos:
            self.cb_pneu.current(self.compostos.index(c.pneu_inicial))
        if c.combustivel_inicial is not None and str(self.sp_comb.cget("state")) == "normal":
            self.v_comb.set(str(c.combustivel_inicial))

    def travar_acerto(self, travar):
        estado = "disabled" if travar else "normal"
        for e in self.escalas:
            e.configure(state=estado)
        self.cb_pneu.configure(state="disabled" if travar else "readonly")

    def aplicar_acerto(self, tipo):
        c = self.carro
        c.acerto = {k: v.get() for k, v in self.v_acerto.items()}
        c.pneu_inicial = self.compostos[self.cb_pneu.current()]
        c.ordens = {k: v.get() for k, v in self.v_ordens.items()}
        c.estrategia_auto = self.v_auto.get()
        c.combustivel_inicial = None
        if tipo == "corrida":
            try:
                c.combustivel_inicial = max(1, int(self.v_comb.get()))
            except ValueError:
                c.combustivel_inicial = None
        self.travar_acerto(True)
        self._acerto_liberado = False
        self.btn_box.configure(state="normal")

    def _ordem(self, k):
        self.carro.ordens[k] = self.v_ordens[k].get()

    def _auto(self):
        self.carro.estrategia_auto = self.v_auto.get()

    def _box(self):
        s = self.tela.ev.sessao
        if s is None or not s.iniciada or s.terminada:
            return
        if s.tipo == "corrida":
            if self.carro.status != "pista":
                return
            if not self.tela.ev.cat["regras_pitstop"].get("troca_de_pneus", True):
                # sem troca de pneus na categoria: a parada é só para combustível/reparo
                self.carro.chamado_box = self.carro.pneu
                self.tela.registrar(f"Equipe chama {self.carro.nome} ao box (sem troca de pneus nesta categoria).")
                return
            self.carro.chamado_box = self.compostos[self.cb_box.current()]
            self.tela.registrar(f"Equipe chama {self.carro.nome} ao box ({self.nomes_comp[self.cb_box.current()]}).")
        elif hasattr(s, "chamar_box"):
            s.chamar_box(self.carro)

    def _voltar(self):
        """Treinos/classificação/teste: aplica o acerto e o pneu escolhidos e manda o piloto de volta."""
        s = self.tela.ev.sessao
        c = self.carro
        if s is None or not getattr(c, "aguardando", False) or not hasattr(s, "liberar"):
            return
        c.acerto = {k: v.get() for k, v in self.v_acerto.items()}
        c.pneu_inicial = self.compostos[self.cb_pneu.current()]
        c._cache.clear()
        s.liberar(c)

    def atualizar(self):
        c = self.carro
        ev = self.tela.ev
        pneu = ev.cat["pneus"]["compostos"][c.pneu]["nome"] if c.pneu else "-"
        status = {"pista": "Na pista", "garagem": "No box", "fim": "Fim", "abandono": f"Abandono ({c.motivo})",
                  "eliminado": "Eliminado"}.get(c.status, c.status)
        txt = f"Posição: {c.posicao or '-'}   |   {status}\nPneu: {pneu}  desgaste {c.desgaste:.0f}%"
        if self.tela.ev.sessao and self.tela.ev.sessao.tipo == "corrida":
            txt += f"\nCombustível: {c.combustivel:.1f} voltas   |   Paradas: {c.paradas}"
        if c.chamado_box or getattr(c, "recolher", False):
            txt += "\n>> Chamado ao box"
        if getattr(c, "aguardando", False):
            txt += "\n>> No box: ajuste o acerto e clique em 'Voltar à pista'"
        self.lbl_estado.configure(text=txt)
        s = ev.sessao
        rodando = bool(s and s.iniciada and not s.terminada)
        if s is not None and s.tipo != "corrida" and hasattr(s, "pode_chamar_box"):
            esperando = getattr(c, "aguardando", False)
            self.btn_box.configure(state="normal" if (rodando and s.pode_chamar_box(c)) else "disabled")
            self.btn_volta.configure(state="normal" if (rodando and esperando) else "disabled")
            self.lbl_box.configure(text="")
            if rodando and esperando != self._acerto_liberado:
                self.travar_acerto(not esperando)      # acerto liberado só com o carro parado no box
                self._acerto_liberado = esperando
        else:
            self.btn_volta.configure(state="disabled")
            self.lbl_box.configure(text="")


# ============================================================================ tela do evento
class TelaEvento(tk.Frame):
    def __init__(self, master, ev, ao_terminar=None, ao_salvar=None):
        """ao_terminar(ev): chamado ao fechar o evento (jogo integrado). Sem ele, é o protótipo isolado.
        ao_salvar(): salva o jogo com o evento em andamento."""
        super().__init__(master, bg=w.CINZA)
        self.ev = ev
        self.ao_terminar = ao_terminar
        self.ao_salvar = ao_salvar
        self.rodando = False
        self.acumulado_voltas = 0.0
        self.log_mostrado = 0
        pista = ev.pista
        self.titulo = w.BarraTitulo(self, f"{pista['nome']}  –  {pista['local']}  ({ev.cat['nome']})")
        self.titulo.pack(fill="x", padx=4, pady=(4, 2))

        # barra de informações
        info = w.BarraStatus(self)
        info.pack(fill="x", padx=4)
        self.lbl_sessao = info.campo("", 24)
        self.lbl_clima = info.campo("", 18)
        self.lbl_prog = info.campo("", expandir=True)

        # controles (rodapé) – empacotados antes do corpo para nunca sumirem
        ctrl = tk.Frame(self, padx=4, pady=4)
        ctrl.pack(fill="x", side="bottom")
        self.btn_iniciar = w.Botao(ctrl, "Iniciar sessão", self.iniciar, largura=13)
        self.btn_iniciar.pack(side="left", padx=2)
        self.btn_pausa = w.Botao(ctrl, "Pausar", self.pausar, largura=9)
        self.btn_pausa.pack(side="left", padx=2)
        tk.Label(ctrl, text="Velocidade:").pack(side="left", padx=(10, 2))
        self.cb_vel = ttk.Combobox(ctrl, values=[v[0] for v in VELOCIDADES], state="readonly", width=12)
        self.cb_vel.current(1)
        self.cb_vel.pack(side="left")
        self.btn_fim = w.Botao(ctrl, "Simular até o fim", self.ate_o_fim, largura=16)
        self.btn_fim.pack(side="left", padx=8)
        self.btn_prox = w.Botao(ctrl, "Próxima sessão >>", self.proxima, largura=16)
        self.btn_prox.pack(side="right", padx=2)
        self.btn_tudo = w.Botao(ctrl, "Simular evento inteiro", self.simular_tudo, largura=20)
        self.btn_tudo.pack(side="right", padx=2)
        if ao_salvar:
            w.Botao(ctrl, "Salvar jogo", self.salvar, largura=11).pack(side="right", padx=(2, 12))

        corpo = tk.Frame(self, padx=4)
        corpo.pack(fill="both", expand=True)

        # coluna esquerda: programação + pista
        esq = tk.Frame(corpo, width=200)
        esq.pack(side="left", fill="y")
        g_prog = w.Grupo(esq, "Programação")
        g_prog.pack(fill="x")
        self.lb_prog = tk.Listbox(g_prog, height=len(ev.programacao) + 1, width=20, relief="sunken", bd=2,
                                  activestyle="none", exportselection=False)
        self.lb_prog.pack(fill="x")
        g_pista = w.Grupo(esq, "Pista")
        g_pista.pack(fill="x", pady=(6, 0))
        w.RotuloBandeira(g_pista, paises.do_local(pista.get("local")), pista.get("local", "")).pack(anchor="w")
        img = w.Imagem(g_pista, 170, 100, borda=False)
        if img.definir(pista.get("imagem")):
            img.pack(anchor="center", pady=(0, 2))
        else:
            img.destroy()
        for t in (f"Tipo: {TIPOS_PISTA.get(pista['tipo_pista'], pista['tipo_pista'])}",
                  f"Retas: {pista['retas']}", f"Curvas de alta: {pista['curvas_alta']}",
                  f"Curvas de baixa: {pista['curvas_baixa']}", f"Desgaste de pneus: {pista['desgaste_pneus']}",
                  f"Dificuldade: {pista['dificuldade']}", f"Pit stop: {pista['duracao_pitstop']:.1f} s",
                  f"Chance de chuva: {pista['prob_chuva'] * 100:.0f}%", f"Voltas (corrida): {pista['voltas_corrida']}"):
            tk.Label(g_pista, text=t, anchor="w").pack(anchor="w")
        g_reg = w.Grupo(esq, "Regras de pit stop")
        g_reg.pack(fill="x", pady=(6, 0))
        r = ev.cat["regras_pitstop"]
        for t in (f"Parada obrigatória: {'sim (' + str(r.get('paradas_minimas', 0)) + ')' if r.get('obrigatorio') else 'não'}",
                  f"Reabastecimento: {'sim' if r.get('reabastecimento') else 'não'}"):
            tk.Label(g_reg, text=t, anchor="w").pack(anchor="w")
        self.p_feedback = PainelFeedback(esq)
        self.p_feedback.pack(fill="x", pady=(6, 0))

        # coluna direita: painel da equipe do usuário
        dir_ = tk.Frame(corpo)
        dir_.pack(side="right", fill="y", padx=(4, 0))
        meus = [c for c in ev.carros if c.usuario]
        cab = tk.Frame(dir_)
        cab.pack(fill="x")
        w.FaixaEquipe(cab, meus[0].equipe, largura=12).pack(side="left", fill="y", padx=(0, 2))
        logo = w.Imagem(cab, 56, 20, borda=False)
        if logo.definir(meus[0].equipe.get("logotipo")):
            logo.pack(side="left", padx=(0, 2))
        else:
            logo.destroy()
        bt = w.BarraTitulo(cab, f"Sua equipe: {meus[0].equipe['nome']}")
        bt.configure(width=1)               # não alarga o painel: a largura vem das abas abaixo
        bt.pack(side="left", fill="x", expand=True)
        nb = ttk.Notebook(dir_)
        nb.pack(fill="both", expand=True, pady=(2, 0))
        self.paineis = []
        for c in meus:
            p = PainelPiloto(nb, self, c)
            nb.add(p, text=c.nome.split()[-1])
            self.paineis.append(p)
        self.nb = nb
        # o painel de feedback acompanha o piloto da aba escolhida
        nb.bind("<<NotebookTabChanged>>", lambda e: self._feedback_da_aba())
        self._feedback_da_aba()

        # centro: cronometragem + log
        meio = tk.Frame(corpo)
        meio.pack(side="left", fill="both", expand=True, padx=(4, 0))
        g_tab = w.Grupo(meio, "Cronometragem")
        g_tab.pack(fill="both", expand=True)
        cols = [("pos", "P"), ("piloto", "Piloto"), ("equipe", "Equipe"), ("melhor", "Melhor"),
                ("ultima", "Última"), ("gap", "Diferença"), ("voltas", "V"), ("pneu", "Pneu"), ("desg", "Desg."),
                ("paradas", "Pit"), ("status", "Status"), ("pontos", "Pts")]
        larg = {"pos": 24, "piloto": 100, "equipe": 84, "melhor": 60, "ultima": 60, "gap": 70, "voltas": 28,
                "pneu": 66, "desg": 38, "paradas": 26, "status": 56, "pontos": 28}
        anc = {k: "center" for k in ("pos", "voltas", "desg", "paradas", "pontos")}
        anc.update({"melhor": "e", "ultima": "e", "gap": "e"})
        fr, self.tv = w.tabela(g_tab, cols, 14, larg, anc, estica={"piloto", "equipe"}, cores=True)
        fr.pack(fill="both", expand=True)
        g_log = w.Grupo(meio, "Acontecimentos")
        g_log.pack(fill="x", pady=(4, 0))
        fr2 = tk.Frame(g_log)
        fr2.pack(fill="x")
        self.lb_log = tk.Listbox(fr2, height=7, relief="sunken", bd=2, activestyle="none")
        sb = tk.Scrollbar(fr2, command=self.lb_log.yview)
        self.lb_log.configure(yscrollcommand=sb.set)
        self.lb_log.pack(side="left", fill="x", expand=True)
        sb.pack(side="right", fill="y")

        if ev.sessao is None:
            self.proxima()
        else:
            self._retomar()
        self._after = self.after(100, self._tick)

    def _retomar(self):
        """Evento carregado de um jogo salvo: reconstrói a tela no ponto em que parou."""
        s = self.ev.sessao
        self.registrar(f"===== Jogo carregado: {s.nome} =====")
        for p in self.paineis:
            p.preparar_sessao(s.tipo)
            p.sincronizar()
            if s.iniciada:
                p.travar_acerto(True)
                p.btn_box.configure(state="normal" if s.tipo == "corrida" else "disabled")
        if s.iniciada and not s.terminada:
            self.btn_iniciar.configure(state="disabled")
            self.btn_pausa.configure(state="normal", text="Continuar")
            self.btn_fim.configure(state="normal")
            self.btn_prox.configure(state="disabled")
        elif not s.iniciada:
            self.btn_iniciar.configure(state="normal")
            for b in (self.btn_pausa, self.btn_fim, self.btn_prox):
                b.configure(state="disabled")
        self.rodando = False
        self._atualizar()

    def salvar(self):
        rodava = self.rodando
        self.rodando = False
        try:
            self.ao_salvar()
        finally:
            self.rodando = rodava

    def destroy(self):
        try:
            self.after_cancel(self._after)
        except (tk.TclError, AttributeError, ValueError):
            pass
        super().destroy()

    # ------------------------------------------------------------------ fluxo
    def registrar(self, texto):
        self.lb_log.insert("end", texto)
        self.lb_log.see("end")

    def proxima(self):
        if self.ev.sessao and not self.ev.sessao.terminada:
            return
        s = self.ev.proxima_sessao()
        if not s:
            self._resultado_final()
            return
        self.log_mostrado = 0
        self.acumulado_voltas = 0.0
        self.registrar(f"===== {s.nome} – defina o acerto inicial e clique em 'Iniciar sessão' =====")
        for p in self.paineis:
            p.preparar_sessao(s.tipo)
        self.btn_iniciar.configure(state="normal")
        self.btn_pausa.configure(state="disabled")
        self.btn_fim.configure(state="disabled")
        self.btn_prox.configure(state="disabled")
        self._atualizar()

    def iniciar(self):
        s = self.ev.sessao
        if not s or s.iniciada:
            return
        for p in self.paineis:
            p.aplicar_acerto(s.tipo)
        s.iniciar()
        self.rodando = True
        self.btn_iniciar.configure(state="disabled")
        self.btn_pausa.configure(state="normal", text="Pausar")
        self.btn_fim.configure(state="normal")

    def pausar(self):
        self.rodando = not self.rodando
        self.btn_pausa.configure(text="Pausar" if self.rodando else "Continuar")

    def ate_o_fim(self):
        s = self.ev.sessao
        if s and s.iniciada and not s.terminada:
            s.simular_ate_o_fim()
            self._atualizar()

    def _tick(self):
        s = self.ev.sessao
        if self.rodando and s and s.iniciada and not s.terminada:
            _, seg, voltas = VELOCIDADES[self.cb_vel.current()]
            if s.tipo == "corrida":
                self.acumulado_voltas += voltas * 0.1
                while self.acumulado_voltas >= 1 and not s.terminada:
                    s.avancar_volta()
                    self.acumulado_voltas -= 1
            else:
                s.avancar(seg * 0.1)
            self._atualizar()
        self._after = self.after(100, self._tick)

    def _fim_sessao(self):
        self.rodando = False
        self.btn_pausa.configure(state="disabled")
        self.btn_fim.configure(state="disabled")
        ultimo = self.ev.indice >= len(self.ev.programacao) - 1
        self.btn_prox.configure(state="normal", text="Ver resultado final" if ultimo else "Próxima sessão >>")

    # ------------------------------------------------------------------ tela
    def _atualizar(self):
        ev, s = self.ev, self.ev.sessao
        self.lb_prog.delete(0, "end")
        for i, nome in enumerate(ev.nomes_sessoes):
            marca = "✓ " if i < ev.indice or (i == ev.indice and s and s.terminada) else \
                ("▶ " if i == ev.indice else "   ")
            self.lb_prog.insert("end", marca + nome)
        if s:
            self.lbl_sessao.configure(text=f"Sessão: {s.nome}")
            self.lbl_prog.configure(text=s.descricao_progresso() if s.iniciada else "Aguardando início")
        self.lbl_clima.configure(text=f"Clima: {ev.clima.nome}")
        sel = self.tv.selection()
        self.tv.delete(*self.tv.get_children())
        if s and s.iniciada:
            for l in s.linhas_classificacao():
                c = l["carro"]
                self.tv.insert("", "end", iid=c.id, tags=("usuario",) if c.usuario else (),
                               image=w.chip_equipe(c.equipe, c.piloto.get("nacionalidade")),
                               values=(l["pos"], c.nome, c.equipe["nome"], l["melhor"], l["ultima"], l["gap"],
                                       l["voltas"], l["pneu"], l["desgaste"], l.get("paradas", ""), l["status"],
                                       l.get("pontos", "")))
            if sel and self.tv.exists(sel[0]):
                self.tv.selection_set(sel[0])
            while self.log_mostrado < len(s.log):
                self.registrar(s.log[self.log_mostrado])
                self.log_mostrado += 1
            if s.terminada:
                self._fim_sessao()
        for p in self.paineis:
            p.atualizar()
        self.p_feedback.atualizar()

    def _feedback_da_aba(self):
        try:
            i = self.nb.index("current")
        except tk.TclError:
            return
        if 0 <= i < len(self.paineis):
            self.p_feedback.mostrar(self.paineis[i].carro)

    def simular_tudo(self):
        """Simula todas as sessões restantes com o acerto/ordens atuais dos painéis."""
        if not messagebox.askyesno("Simular evento", "Simular todas as sessões restantes com o acerto atual?",
                                   parent=self):
            return
        while True:
            s = self.ev.sessao
            if s and not s.iniciada:
                self.iniciar()
            if s and not s.terminada:
                s.simular_ate_o_fim()
            self._atualizar()
            if self.ev.indice >= len(self.ev.programacao) - 1:
                break
            self.proxima()
        self.rodando = False

    def _resultado_final(self):
        res = self.ev.resultado_corrida or []
        linhas = [f"{r['pos']:>2}. {r['carro'].nome} ({r['carro'].equipe['nome']}) – {r['pontos']} pts"
                  for r in res[:10]]
        if not res and self.ev.historico_sessoes:          # teste coletivo: melhores voltas de todos os dias
            melhor = {}
            for d in self.ev.historico_sessoes:
                for l in d["linhas"]:
                    if l.get("melhor") and (l["piloto"] not in melhor or l["melhor"] < melhor[l["piloto"]]["melhor"]):
                        melhor[l["piloto"]] = l
            ordem = sorted(melhor.values(), key=lambda l: l["melhor"])
            linhas = [f"{i:>2}. {l['nome']} ({l['equipe_nome']}) – {tempo_volta(l['melhor'])}"
                      for i, l in enumerate(ordem[:10], 1)]
        messagebox.showinfo("Resultado final", "Fim do evento.\n\n" + "\n".join(linhas), parent=self)
        self.btn_prox.configure(state="disabled")
        self.btn_tudo.configure(state="disabled")
        if self.ao_terminar:
            self.ao_terminar(self.ev)


def executar():
    from .. import i18n
    i18n.iniciar()
    i18n.instalar()
    root = tk.Tk()
    root.title("AutoManager – Protótipo de evento")
    w.aplicar(root)
    w.centralizar(root, 1280, 760)
    root.withdraw()
    ev = DialogoConfigEvento(root).modal()
    if not ev:
        root.destroy()
        return
    root.deiconify()
    root.minsize(1180, 700)
    TelaEvento(root, ev).pack(fill="both", expand=True)
    root.mainloop()
