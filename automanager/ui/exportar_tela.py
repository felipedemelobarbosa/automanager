"""Exportar para HTML: escolher a pasta, gerar o site e oferecer abrir no navegador (jogo e tela do comissário)."""
import os
import webbrowser
from tkinter import filedialog, messagebox

from .. import exportar_html


def exportar(parent, st):
    base = filedialog.askdirectory(parent=parent, title="Pasta onde salvar o HTML")
    if not base:
        return None
    pasta = os.path.join(base, f"AutoManager_{st['ano']}_S{st['semana']:02d}")
    parent.config(cursor="watch")
    parent.update()
    try:
        indice = exportar_html.exportar(st, pasta)
    except OSError as erro:
        messagebox.showerror("Exportar para HTML", f"Não foi possível gravar os arquivos:\n{erro}", parent=parent)
        return None
    finally:
        parent.config(cursor="")
    if messagebox.askyesno("Exportar para HTML", f"Páginas geradas em:\n{pasta}\n\nAbrir no navegador?", parent=parent):
        webbrowser.open("file://" + os.path.abspath(indice))
    return indice
