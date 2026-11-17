"""Utilidades gerais: caminhos, formatação de dinheiro e de tempo."""
import os
import shutil
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Rodando do código-fonte (python main.py), tudo fica na pasta do jogo, como sempre. No programa empacotado
# (PyInstaller: .exe, .app, .deb), a pasta de instalação é só leitura: os arquivos que vêm com o jogo (lang,
# database original) são lidos de dentro do pacote, e o que o jogo grava (saves, ligas, config.json, database
# editada e imagens baixadas) vai para a pasta de dados do usuário.
EMPACOTADO = bool(getattr(sys, "frozen", False))


def _pasta_usuario():
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "AutoManager")
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "AutoManager")
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "automanager")


PASTA_RECURSOS = getattr(sys, "_MEIPASS", RAIZ) if EMPACOTADO else RAIZ
PASTA_DADOS = _pasta_usuario() if EMPACOTADO else RAIZ
PASTA_DATABASE = os.path.join(PASTA_DADOS, "database")
PASTA_SAVES = os.path.join(PASTA_DADOS, "saves")


def _copiar_database():
    """Programa empacotado: copia para a pasta do usuário os arquivos da database que ainda não estão lá (na
    1ª execução, todos; numa versão nova, só os novos – o que o usuário editou não é sobrescrito)."""
    origem = os.path.join(PASTA_RECURSOS, "database")
    for raiz, _pastas, arquivos in os.walk(origem):
        destino = os.path.join(PASTA_DATABASE, os.path.relpath(raiz, origem))
        for a in arquivos:
            alvo = os.path.join(destino, a)
            if not os.path.exists(alvo):
                os.makedirs(destino, exist_ok=True)
                shutil.copy2(os.path.join(raiz, a), alvo)


if EMPACOTADO:
    _copiar_database()


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def dinheiro(v, moeda="USD"):
    """Formata valor monetário: 1234567 -> 'USD 1.234.567'."""
    if v is None:
        return "-"
    sinal = "-" if v < 0 else ""
    return f"{sinal}{moeda} {abs(int(round(v))):,}".replace(",", ".")


def tempo_volta(seg):
    """83.456 -> '1:23.456'."""
    if seg is None:
        return "-"
    m = int(seg // 60)
    s = seg - m * 60
    return f"{m}:{s:06.3f}" if m else f"{s:.3f}"


def intervalo(seg):
    if seg is None:
        return "-"
    return f"+{seg:.3f}"


def relogio(seg):
    seg = max(0, int(seg))
    return f"{seg // 3600:d}:{seg % 3600 // 60:02d}:{seg % 60:02d}"
