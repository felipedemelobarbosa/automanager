"""O guia de edição da database (docs/GUIA_DATABASE.md) tem de citar todos os campos do editor: um campo novo no
editor sem entrada no guia faz este teste falhar (lembrete para atualizar o guia)."""
import ast
import os
import re
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def campos_do_editor():
    """Chaves (último nível) de todos os campos dos formulários do editor."""
    arvore = ast.parse(open(os.path.join(RAIZ, "automanager", "ui", "editor_tela.py"), encoding="utf-8").read())
    chaves = set()
    for n in ast.walk(arvore):
        if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "F" and n.args:
            try:
                cam = ast.literal_eval(n.args[0])
            except ValueError:
                continue                           # caminho calculado (atributos, contrato): conferido à parte
            chaves.add(cam if isinstance(cam, str) else cam[-1])
        # aba Simulação: lista de (chave ou (grupo, chave), rótulo, ajuda) dentro de _form("Simulação", ...)
        if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "_form" and n.args \
                and isinstance(n.args[0], ast.Constant) and n.args[0].value == "Simulação":
            for t in ast.walk(n.args[1]):
                if isinstance(t, ast.Tuple) and len(t.elts) == 3 and isinstance(t.elts[1], ast.Constant):
                    k = ast.literal_eval(t.elts[0])
                    chaves.add(k if isinstance(k, str) else k[-1])
    return chaves


class TestGuiaDatabase(unittest.TestCase):
    def test_todos_os_campos_do_editor_estao_no_guia(self):
        guia = open(os.path.join(RAIZ, "docs", "GUIA_DATABASE.md"), encoding="utf-8").read()
        citados = set()
        for trecho in re.findall(r"`([^`]+)`", guia):
            citados.update(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", trecho))
        faltam = sorted(campos_do_editor() - citados)
        self.assertEqual(faltam, [], "campos do editor sem entrada em docs/GUIA_DATABASE.md – atualize o guia")


if __name__ == "__main__":
    unittest.main()
