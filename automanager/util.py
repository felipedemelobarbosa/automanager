"""Utilidades gerais: caminhos, formatação de dinheiro e de tempo."""
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_DATABASE = os.path.join(RAIZ, "database")
PASTA_SAVES = os.path.join(RAIZ, "saves")


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
