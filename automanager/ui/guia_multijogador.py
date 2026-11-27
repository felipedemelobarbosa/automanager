"""Guia passo a passo do multijogador (jogador e comissário), abrir pasta no sistema e o checklist da semana."""
import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk

from .. import i18n
from . import win9x as w

GUIA_JOGADOR = [
    ("Antes de começar", [
        "O comissário cadastrou você na liga com um nome e uma senha. Guarde a senha: ela assina e protege as suas "
        "ordens (ninguém mais consegue ler nem alterar o arquivo).",
        "Você recebe a liga de um destes jeitos: numa pasta compartilhada (Google Drive, Dropbox, OneDrive...), "
        "pelo canal da liga no Discord (comando !liga) ou por um arquivo que o comissário mandou.",
    ]),
    ("1. Abrir a liga", [
        "Menu inicial > Multijogador – jogador.",
        "Pasta compartilhada: clique em 'Abrir a pasta compartilhada da liga' e escolha a pasta (o jogo abre o "
        "liga.json dela).",
        "Arquivo recebido (e-mail ou Discord): clique em 'Abrir arquivo da liga' e escolha o arquivo .json da semana.",
        "Escolha o seu nome e digite a senha. Se você já tinha salvo ordens desta semana, o jogo pergunta se quer "
        "continuar a partir delas.",
    ]),
    ("2. Jogar a semana", [
        "Faça as decisões como num jogo normal: Mercado (pilotos, chassis, motor, patrocinadores), Desenvolvimento "
        "e Finanças. Tudo o que você faz entra nas ordens.",
        "Se houver corrida ou teste nesta semana, abra 'Plano do evento...' e defina, para cada piloto, acerto, "
        "pneus, ordens e paradas. Sem plano, a equipe decide sozinha.",
        "O quadro 'Próximos passos', na parte de baixo da tela, mostra o que falta.",
    ]),
    ("3. Mandar as ordens", [
        "Clique em 'Salvar ordens' (ou Ctrl+S).",
        "Pasta compartilhada: as ordens são entregues sozinhas na pasta. A barra de baixo mostra quando o comissário "
        "recebeu (ou se recusou, e por quê).",
        "Sem pasta compartilhada: o jogo grava um arquivo .ordens.json e oferece abrir a pasta dele. Mande esse "
        "arquivo ao comissário: anexe no canal da liga no Discord (ou em mensagem privada ao bot) ou por e-mail.",
        "Mudou de ideia? Altere e salve de novo antes do prazo: vale a última entrega.",
    ]),
    ("4. Semana seguinte", [
        "Quando o comissário roda a semana, sai um arquivo novo da liga. Na pasta compartilhada o jogo avisa e abre "
        "a semana nova sem pedir a senha; pelo Discord o bot posta o arquivo no canal.",
        "Abra a liga de novo (passo 1) e repita.",
    ]),
]

GUIA_COMISSARIO = [
    ("1. Criar a liga", [
        "Menu inicial > Multijogador – comissário > Criar uma liga nova: escolha as categorias, cadastre os "
        "jogadores (nome, equipe, senha) e a política para quem não mandar as ordens.",
        "Liga do zero (cada jogador cria a própria equipe): marque 'Todos os pilotos começam livres'. Nas categorias"
        " com equipes novas, as equipes da database saem e todos os pilotos, patrocinadores e fornecimentos ficam livres para os jogadores contratarem.",
        "O jogo grava o arquivo do comissário (…_comissario.json). Ele guarda as chaves dos jogadores: NÃO o "
        "distribua nem o coloque na pasta compartilhada.",
    ]),
    ("2. Entregar a liga aos jogadores", [
        "Melhor: Caixa de entrada da liga > Pasta compartilhada... e escolha uma pasta sincronizada com os jogadores "
        "(Drive, Dropbox, OneDrive, Syncthing). O jogo publica a semana nela e importa as ordens sozinho.",
        "Sem pasta compartilhada: 'Exportar arquivo para os jogadores...' e mande o arquivo (e-mail, Discord).",
        "Discord: rode o bot da liga (docs/BOT_DISCORD.md); ele posta cada semana no canal e recebe as ordens.",
        "Opcional: 'Prazo desta semana...' para marcar até quando as ordens valem.",
    ]),
    ("3. Receber as ordens", [
        "Com pasta compartilhada (ou o bot), as ordens são importadas sozinhas a cada 5 s enquanto esta tela estiver "
        "aberta; a tabela de jogadores mostra quem já mandou, a hora e as recusas (com o motivo).",
        "Arquivos recebidos à mão: 'Importar ordens...' ou 'Importar todas de uma pasta...'.",
        "Quem não vai mandar: selecione e 'Pular jogador' (a IA joga a semana dele).",
    ]),
    ("4. Rodar a semana", [
        "Clique em 'Rodar semana'. Ou marque 'Rodar sozinha quando chegarem todas as ordens' / 'Rodar sozinha no "
        "prazo'.",
        "A semana nova é publicada na pasta compartilhada (ou gere o arquivo para os jogadores) e tudo recomeça.",
        "'Exportar para HTML...' gera um site com classificação, resultados e finanças para mostrar à liga.",
        "Calendário: em Arquivo > Calendário da próxima temporada... edite o calendário do ano seguinte como no editor "
        "(eventos, semanas, voltas, pistas novas). Os jogadores o veem assim que ele é salvo; sem calendário definido, a virada segue o sorteio normal.",
    ]),
]


def abrir_no_sistema(caminho):
    """Abre a pasta (ou arquivo) no gerenciador de arquivos do sistema."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(caminho)                                       # noqa: S606 – só no Windows
        elif sys.platform == "darwin":
            subprocess.Popen(["open", caminho])
        else:
            subprocess.Popen(["xdg-open", caminho])
        return True
    except OSError:
        return False


def _config_guia():
    return (i18n.ler_config() or {}).get("guia_mp_oculto") or []


def guia_oculto(papel):
    return papel in _config_guia()


def ocultar_guia(papel, ocultar=True):
    atual = set(_config_guia())
    (atual.add if ocultar else atual.discard)(papel)
    i18n.salvar_config(guia_mp_oculto=sorted(atual))


class DialogoGuia(w.Dialogo):
    """Guia do multijogador. `acoes`: [(rótulo, função)] – botões no rodapé (ex.: abrir a liga). resultado = a
    função escolhida (chamada pelo chamador depois de fechar) ou None."""

    def __init__(self, master, papel="jogador", acoes=()):
        titulo = "Multijogador – guia do jogador" if papel == "jogador" else "Multijogador – guia do comissário"
        super().__init__(master, titulo, 760, 560)
        self.papel = papel
        w.BarraTitulo(self.corpo, titulo).pack(fill="x")
        fr = tk.Frame(self.corpo)
        fr.pack(fill="both", expand=True, pady=(4, 0))
        txt = tk.Text(fr, wrap="word", relief="sunken", bd=2, padx=8, pady=6, font=w.FONTE, bg=w.BRANCO,
                      cursor="arrow", height=20)
        sb = ttk.Scrollbar(fr, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        txt.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        txt.tag_configure("titulo", font=w.FONTE_NEGRITO, foreground=w.AZUL, spacing1=8, spacing3=2)
        txt.tag_configure("passo", lmargin1=12, lmargin2=28, spacing1=2)
        for secao, passos in (GUIA_JOGADOR if papel == "jogador" else GUIA_COMISSARIO):
            txt.insert("end", i18n.t(secao) + "\n", "titulo")
            for p in passos:
                txt.insert("end", "•  " + i18n.t(p) + "\n", "passo")
        txt.configure(state="disabled")
        self.v_ocultar = tk.BooleanVar(value=guia_oculto(papel))
        ttk.Checkbutton(self.rodape, text="Não mostrar este guia ao entrar", variable=self.v_ocultar).pack(side="left")
        w.Botao(self.rodape, "Fechar", self._fechar, largura=10).pack(side="right", padx=2)
        for rot, f in reversed(list(acoes)):
            w.Botao(self.rodape, rot, lambda f=f: self._escolher(f), padx=8).pack(side="right", padx=2)

    def _guardar(self):
        ocultar_guia(self.papel, bool(self.v_ocultar.get()))

    def _escolher(self, f):
        self._guardar()
        self.resultado = f
        self.destroy()

    def _fechar(self):
        self._guardar()
        self.destroy()


def passos_do_jogador(st, salvas):
    """Linhas do quadro 'Próximos passos' do jogador: [(feito, texto)]. `salvas` = None ou
    {"ano", "semana", "quando", "assinatura_conteudo", "pasta"} da última vez que salvou."""
    from .. import multiplayer as mp
    from ..event.inscritos import montar_inscritos
    from .multijogador_tela import eventos_da_semana
    s = mp.sessao(st)
    n_acoes = len(s.get("acoes", []))
    linhas = [(n_acoes > 0, i18n.t(f"Decisões da semana (Mercado, Desenvolvimento, Finanças): {n_acoes} ação(ões) "
                                    f"registrada(s)."))]
    eventos = eventos_da_semana(st)
    if eventos:
        u = st["usuario"]
        total = com_plano = 0
        for ev in eventos:
            for i in montar_inscritos(st, u["categoria"], u["equipe"], ev):
                if i["usuario"]:
                    total += 1
                    com_plano += i["piloto"]["id"] in s["planos"].get(ev["id"], {})
        linhas.append((total > 0 and com_plano == total,
                       i18n.t(f"Plano do evento: {com_plano} de {total} piloto(s) com plano (sem plano, a equipe "
                              f"decide sozinha).")))
    else:
        linhas.append((True, i18n.t("Plano do evento: não há corrida nem teste nesta semana.")))
    atual = (n_acoes, sum(len(v) for v in s.get("planos", {}).values()), repr(s.get("acoes")), repr(s.get("planos")))
    if not salvas or (salvas["ano"], salvas["semana"]) != (st["ano"], st["semana"]):
        linhas.append((False, i18n.t("Salvar ordens: ainda não salvas nesta semana (Ctrl+S).")))
    elif salvas["conteudo"] != atual:
        linhas.append((False, i18n.t(f"Salvar ordens: você mudou algo depois de salvar às {salvas['quando']} – salve "
                                     f"de novo.")))
    else:
        onde = i18n.t("entregues na pasta compartilhada") if salvas.get("pasta") else \
            i18n.t("arquivo salvo – mande ao comissário")
        linhas.append((True, i18n.t(f"Salvar ordens: salvas às {salvas['quando']} ({onde}).")))
    return linhas, atual
