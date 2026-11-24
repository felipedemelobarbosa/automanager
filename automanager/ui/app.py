"""Janela principal, menu inicial e diálogos de abrir/salvar jogo."""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from .. import VERSAO, state, db, i18n
from ..util import dinheiro
from . import win9x as w


class App:
    def __init__(self):
        i18n.iniciar()
        i18n.instalar()
        self.root = tk.Tk()
        self.root.title("AutoManager")
        w.aplicar(self.root)
        w.centralizar(self.root, 1100, 720)
        self.root.minsize(960, 640)
        self.estado = None
        self.tela = None
        self.root.protocol("WM_DELETE_WINDOW", self.sair)
        self.menu_inicial()

    def trocar(self, fabrica, *args):
        if self.tela is not None:
            self.tela.destroy()
        self.root.config(menu=tk.Menu(self.root))
        self.tela = fabrica(self.root, self, *args)
        self.tela.pack(fill="both", expand=True)

    # ------------------------------------------------------------ navegação
    def menu_inicial(self):
        self.estado = None
        self.criando_liga = False
        self.caminho_liga = None
        self.pasta_liga_jogador = None
        self.liga_compartilhada = False
        self.root.title("AutoManager")
        self.trocar(MenuInicial)

    def novo_jogo(self):
        from .novo_jogo import TelaNovoJogo
        self.criando_liga = False
        self.trocar(TelaNovoJogo)

    # ------------------------------------------------------------ multijogador
    def multi_comissario(self):
        r = DialogoEscolha(self.root, "Multijogador – comissário", "O que deseja fazer?",
                           [("nova", "Criar uma liga nova"), ("abrir", "Abrir uma liga (arquivo do comissário)"),
                            ("guia", "Ver o guia passo a passo")]).modal()
        if r == "guia":
            from .guia_multijogador import DialogoGuia
            DialogoGuia(self.root, "comissario").modal()
            return self.multi_comissario()
        if r == "nova":
            from .novo_jogo import TelaNovoJogo
            self.criando_liga = True
            self.trocar(TelaNovoJogo)
        elif r == "abrir":
            from tkinter import filedialog
            from .. import multiplayer as mp
            import os
            caminho = filedialog.askopenfilename(parent=self.root, title="Arquivo do comissário",
                                                 initialdir=mp.PASTA_LIGAS if os.path.isdir(mp.PASTA_LIGAS) else None,
                                                 filetypes=[("Liga (JSON)", "*.json"), ("Todos", "*.*")])
            if not caminho:
                return
            try:
                st = mp.carregar_liga(caminho)
            except (OSError, ValueError, KeyError, db.ErroDatabase, mp.ErroLiga) as e:
                messagebox.showerror("AutoManager", f"Não foi possível abrir a liga:\n{e}", parent=self.root)
                return
            if st["multiplayer"].get("papel") != "comissario":
                messagebox.showwarning("AutoManager", "Este é o arquivo distribuído aos jogadores. Abra o arquivo do "
                                                      "comissário (…_comissario.json).", parent=self.root)
                return
            self.comissario(st, caminho)

    def criar_liga(self, estado):
        from .multijogador_tela import TelaCriarLiga
        self.estado = estado
        self.criando_liga = False
        self.trocar(TelaCriarLiga, estado)

    def comissario(self, estado, caminho):
        from .multijogador_tela import TelaComissario
        self.estado = estado
        self.caminho_liga = caminho
        self.trocar(TelaComissario, estado, caminho)

    def multi_jogador(self):
        """Jogador: guia passo a passo (pode ser ocultado) com os dois jeitos de abrir a liga."""
        from .guia_multijogador import DialogoGuia, guia_oculto
        abrir = [("Abrir a pasta compartilhada da liga...", self._abrir_pasta_liga),
                 ("Abrir arquivo da liga...", self._abrir_arquivo_liga)]
        if guia_oculto("jogador"):
            r = DialogoEscolha(self.root, "Multijogador – jogador", "Como você recebeu a liga?",
                               [("pasta", "Numa pasta compartilhada (Drive, Dropbox...)"),
                                ("arquivo", "Num arquivo (e-mail, Discord)"), ("guia", "Ver o guia passo a passo")]
                               ).modal()
            f = {"pasta": self._abrir_pasta_liga, "arquivo": self._abrir_arquivo_liga}.get(r)
            if r == "guia":
                f = DialogoGuia(self.root, "jogador", abrir).modal()
        else:
            f = DialogoGuia(self.root, "jogador", abrir).modal()
        if f:
            f()

    def _abrir_pasta_liga(self):
        from tkinter import filedialog
        import os
        from .. import caixa_liga
        d = filedialog.askdirectory(parent=self.root, title="Pasta compartilhada da liga")
        if not d:
            return
        if not caixa_liga.eh_pasta_da_liga(d):
            messagebox.showwarning("AutoManager", "Esta pasta não tem o arquivo da liga (liga.json). Escolha a pasta "
                                                  "que o comissário compartilhou.", parent=self.root)
            return
        self._entrar_na_liga(os.path.join(d, caixa_liga.LIGA))

    def _abrir_arquivo_liga(self):
        from tkinter import filedialog
        caminho = filedialog.askopenfilename(parent=self.root, title="Arquivo da liga (recebido do comissário)",
                                             filetypes=[("Liga (JSON)", "*.json"), ("Todos", "*.*")])
        if caminho:
            self._entrar_na_liga(caminho)

    def _entrar_na_liga(self, caminho):
        import os
        from .. import multiplayer as mp
        from .multijogador_tela import DialogoEntrar, caminho_ordens_padrao
        try:
            st_liga = mp.carregar_liga(caminho)
        except (OSError, ValueError, KeyError, db.ErroDatabase, mp.ErroLiga) as e:
            messagebox.showerror("AutoManager", f"Não foi possível abrir a liga:\n{e}", parent=self.root)
            return
        st = DialogoEntrar(self.root, st_liga).modal()
        if not st:
            return
        from .. import caixa_liga
        self.pasta_liga_jogador = os.path.dirname(caminho)
        # liga.json de uma pasta compartilhada (com o status do comissário): as ordens vão direto para ela
        self.liga_compartilhada = os.path.basename(caminho) == caixa_liga.LIGA \
            and caixa_liga.ler_status(self.pasta_liga_jogador) is not None
        anterior = caixa_liga.caminho_ordens(self.pasta_liga_jogador, mp.sessao(st)["jogador"]) \
            if self.liga_compartilhada else caminho_ordens_padrao(st, self.pasta_liga_jogador)
        if not os.path.exists(anterior):
            # o nome do arquivo leva a equipe: procura as ordens deste jogador nesta semana com qualquer equipe
            import glob
            base = mp.nome_arquivo(st, mp.sessao(st)["jogador"]).replace(".json", "")
            achados = sorted(glob.glob(os.path.join(glob.escape(self.pasta_liga_jogador), base + "*.ordens.json")))
            anterior = achados[-1] if achados else anterior
        if os.path.exists(anterior) and messagebox.askyesno(
                "Ordens salvas", f"Já existem ordens suas para esta semana:\n{anterior}\n\nContinuar a partir delas?",
                parent=self.root):
            try:
                erros = mp.retomar_ordens(st, mp.ler_ordens(anterior))
                if erros:
                    messagebox.showwarning("Ordens salvas", "Algumas ações não puderam ser refeitas:\n" +
                                           "\n".join(erros), parent=self.root)
            except mp.ErroLiga as e:
                messagebox.showwarning("Ordens salvas", str(e), parent=self.root)
        self.abrir_equipe(st)

    def selecao_equipe(self, estado):
        from .novo_jogo import TelaSelecaoEquipe
        self.estado = estado
        self.trocar(TelaSelecaoEquipe, estado)

    def desenvolvimento_inicial(self, estado):
        from .novo_jogo import TelaDesenvolvimentoInicial
        self.estado = estado
        self.trocar(TelaDesenvolvimentoInicial, estado)

    def abrir_equipe(self, estado):
        """Equipe recém-criada ainda sem o carro inicial vai para o desenvolvimento inicial; senão, gestão."""
        from .. import state, acoes, multiplayer as mp
        u = estado.get("usuario") or {}
        sess = mp.sessao(estado)
        if sess is not None and not u.get("equipe"):
            # vaga de equipe nova: o jogador cria a equipe agora (vai nas ordens dele)
            from .. import cores
            from .novo_jogo import DialogoCriarEquipe
            cid = u["categoria"]
            usadas = {cores.cor_equipe(e) for e in estado["categorias"][cid]["equipes"].values() if e.get("ativa")}
            while True:
                r = DialogoCriarEquipe(self.root, usadas).modal()
                if not r:
                    self.menu_inicial()
                    return
                nome, nac, cor, cor2 = r
                erro = acoes.executar(estado, "criar_equipe", jogador=sess["jogador"], nome=nome, nacionalidade=nac,
                                      cor=cor, cor_secundaria=cor2)
                if not erro:
                    break
                messagebox.showwarning("Criar equipe", erro, parent=self.root)
            eq = state.equipe_usuario(estado)
            messagebox.showinfo("Nova equipe", f"{eq['nome']} foi criada com orçamento de "
                                               f"{dinheiro(eq['financas']['caixa'])}.", parent=self.root)
        eq = state.equipe_usuario(estado) if u.get("equipe") else {}
        if eq.get("dev_inicial_pendente"):
            self.desenvolvimento_inicial(estado)
        else:
            self.gestao(estado)

    def gestao(self, estado):
        from .gestao import TelaGestao
        self.estado = estado
        self.trocar(TelaGestao, estado)

    def evento(self, estado, pista, inscritos, ev=None, teste=False):
        """Evento da categoria do usuário (corrida ou teste coletivo): abre a tela do evento; ao terminar grava
        o resultado e avança a semana. `ev` já pronto = evento retomado de um jogo salvo."""
        import random
        from ..event.sessoes import Evento
        from ..event import persistencia
        from .evento_tela import TelaEvento
        from .. import campeonato, routines
        self.estado = estado
        cid = estado["usuario"]["categoria"]
        if ev is None and teste:
            ev = campeonato.criar_evento_teste(estado, cid, pista, inscritos, random.Random())
        elif ev is None:
            ev = Evento(estado["categorias"][cid]["categoria"], pista, inscritos, random.Random(),
                        ordem_campeonato=campeonato.ordem(estado, cid))
        teste = getattr(ev, "modo", "corrida") == "teste"

        geometria = self.root.geometry()

        def salvar():
            estado["evento_em_andamento"] = persistencia.serializar(ev, cid)
            try:
                self.salvar_jogo()
            finally:
                estado.pop("evento_em_andamento", None)

        def terminar(ev_):
            estado.pop("evento_em_andamento", None)
            if teste:
                campeonato.registrar_teste(estado, cid, pista, ev_)
            else:
                campeonato.registrar_corrida(estado, cid, pista, ev_)
            routines.avancar_semana(estado)
            self._maximizar(False)
            self.root.geometry(geometria)
            self.gestao(estado)

        self._maximizar(True)
        self.root.title(f"AutoManager – {pista['nome']}")
        self.trocar(lambda master, app: TelaEvento(master, ev, terminar, salvar))

    def _maximizar(self, sim):
        try:
            self.root.state("zoomed" if sim else "normal")          # Windows
        except tk.TclError:
            try:
                self.root.attributes("-zoomed", sim)                 # Linux (X11)
            except tk.TclError:
                pass

    def abrir_jogo(self):
        caminho = DialogoCarregar(self.root).modal()
        if not caminho:
            return
        try:
            st = state.carregar(caminho)
        except (OSError, ValueError, KeyError, db.ErroDatabase) as e:
            messagebox.showerror("AutoManager", f"Não foi possível carregar o jogo:\n{e}", parent=self.root)
            return
        dados_ev = st.pop("evento_em_andamento", None)
        if dados_ev:
            from ..event import persistencia
            ev, pista = persistencia.restaurar(dados_ev, st)
            self.evento(st, pista, None, ev)
            return
        self.abrir_equipe(st)

    def salvar_jogo(self, como=False):
        if not self.estado:
            return
        nome = self.estado.get("nome_save")
        if como or not nome:
            u = self.estado["usuario"]
            sugestao = nome or f"{u['equipe']}_{self.estado['ano']}"
            nome = simpledialog.askstring("Salvar jogo", "Nome do jogo salvo:", initialvalue=sugestao,
                                          parent=self.root)
            if not nome:
                return
        caminho = state.salvar(self.estado, nome)
        messagebox.showinfo("Salvar jogo", f"Jogo salvo em:\n{caminho}", parent=self.root)

    def opcoes(self):
        messagebox.showinfo("Opções", "Tela de opções aguardando definição.\n(Item pendente no controle do projeto.)",
                            parent=self.root)

    def editor(self):
        from .editor_tela import JanelaEditor
        JanelaEditor(self.root)

    def fechar_jogo(self):
        if self.estado and not messagebox.askyesno("Fechar jogo", "Fechar o jogo atual? Alterações não salvas "
                                                                  "serão perdidas.", parent=self.root):
            return
        self.menu_inicial()

    def sair(self):
        if self.estado and not messagebox.askyesno("Sair", "Sair do AutoManager? Alterações não salvas serão "
                                                           "perdidas.", parent=self.root):
            return
        self.root.destroy()

    def executar(self):
        self.root.mainloop()


# ===================================================================== menu inicial
class MenuInicial(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=w.CINZA_ESCURO)
        self.app = app
        # "área de trabalho" + janela central
        janela = tk.Frame(self, bg=w.CINZA, relief="raised", bd=2)
        janela.place(relx=0.5, rely=0.45, anchor="center", width=380, height=480)
        w.BarraTitulo(janela, "AutoManager").pack(fill="x", padx=2, pady=2)
        tk.Label(janela, text="AutoManager", font=w.FONTE_GRANDE, fg=w.AZUL).pack(pady=(18, 0))
        tk.Label(janela, text="Gerenciamento de equipes de automobilismo").pack()
        tk.Frame(janela, height=2, bd=1, relief="sunken").pack(fill="x", padx=16, pady=12)
        botoes = tk.Frame(janela)
        botoes.pack()
        for texto, cmd in (("Começar jogo novo", app.novo_jogo), ("Carregar jogo", app.abrir_jogo),
                           ("Multijogador – comissário", app.multi_comissario),
                           ("Multijogador – jogador", app.multi_jogador),
                           ("Opções", app.opcoes), ("Abrir editor", app.editor), ("Sair", app.sair)):
            w.Botao(botoes, texto, cmd, largura=22).pack(pady=3)
        tk.Label(janela, text=f"versão {VERSAO}", fg=w.CINZA_ESCURO).pack(side="bottom", pady=4)
        idi = tk.Frame(janela)
        idi.pack(side="bottom", pady=(0, 2))
        tk.Label(idi, text="Idioma / Language / Idioma:").pack(side="left")
        self.codigos = list(i18n.IDIOMAS)
        self.cb_idioma = ttk.Combobox(idi, state="readonly", width=11, values=list(i18n.IDIOMAS.values()))
        self.cb_idioma.current(self.codigos.index(i18n.atual()))
        self.cb_idioma.pack(side="left", padx=4)
        self.cb_idioma.bind("<<ComboboxSelected>>", self._idioma)

    def _idioma(self, _e=None):
        codigo = self.codigos[self.cb_idioma.current()]
        if codigo != i18n.atual():
            i18n.definir(codigo)
            i18n.salvar_config(idioma=codigo)
            self.app.menu_inicial()


# ===================================================================== escolha simples
class DialogoEscolha(w.Dialogo):
    def __init__(self, master, titulo, texto, opcoes):
        super().__init__(master, titulo, 380, 110 + 34 * len(opcoes))
        tk.Label(self.corpo, text=texto).pack(anchor="w", pady=(0, 6))
        for chave, rot in opcoes:
            w.Botao(self.corpo, rot, lambda k=chave: self._ok(k), largura=36).pack(pady=2)
        w.Botao(self.rodape, "Cancelar", self.cancelar, largura=10).pack(side="right")

    def _ok(self, k):
        self.resultado = k
        self.destroy()


# ===================================================================== diálogo carregar
class DialogoCarregar(w.Dialogo):
    def __init__(self, master):
        super().__init__(master, "Carregar jogo", 640, 360)
        tk.Label(self.corpo, text="Jogos salvos na pasta do jogo:").pack(anchor="w")
        cols = [("nome", "Nome"), ("equipe", "Equipe"), ("categoria", "Categoria"), ("data", "Ano/Semana"),
                ("mod", "Salvo em")]
        fr, self.tv = w.tabela(self.corpo, cols, 10, {"nome": 140, "equipe": 150, "categoria": 110, "data": 80,
                                                      "mod": 110})
        fr.pack(fill="both", expand=True, pady=4)
        self.saves = state.listar_saves()
        for i, s in enumerate(self.saves):
            self.tv.insert("", "end", iid=str(i), values=(s["nome"], s["equipe"], s["categoria"],
                                                          f"{s['ano']} / {s['semana']}", s["modificado"]))
        if not self.saves:
            tk.Label(self.corpo, text="Nenhum jogo salvo encontrado.", fg=w.CINZA_ESCURO).pack(anchor="w")
        self.tv.bind("<Double-1>", lambda e: self.ok())
        w.Botao(self.rodape, "Cancelar", self.cancelar, largura=10).pack(side="right", padx=2)
        w.Botao(self.rodape, "Abrir", self.ok, largura=10).pack(side="right", padx=2)

    def ok(self):
        sel = self.tv.selection()
        if not sel:
            return
        self.resultado = self.saves[int(sel[0])]["caminho"]
        self.destroy()
