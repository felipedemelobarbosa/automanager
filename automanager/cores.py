"""Cores das equipes.

Na database, cada equipe pode ter `cor` (principal) e `cor_secundaria`, no formato "#RRGGBB".
Sem cor definida, o jogo escolhe uma cor fixa a partir do ID da equipe.
"""
import re
import zlib

PALETA = ["#c8102e", "#0033a0", "#00843d", "#ff8200", "#6a1b9a", "#ffd100", "#00a3e0", "#222222",
          "#e4007c", "#8b5a2b", "#7a7a7a", "#00b2a9", "#003b5c", "#b5e61d", "#9e1b32", "#4b0082",
          "#ff5f00", "#2e8b57", "#d4af37", "#1e90ff"]

# cores conhecidas (importação da Wikipedia): trecho do nome normalizado -> (principal, secundária)
CONHECIDAS = [
    ("ferrari", ("#dc0000", "#fff200")), ("mercedes", ("#00a19c", "#c0c0c0")), ("red bull", ("#1e2a5a", "#e10600")),
    ("mclaren", ("#ff8000", "#47c7fc")), ("williams", ("#005aff", "#ffffff")), ("alpine", ("#0090ff", "#ff87bc")),
    ("aston martin", ("#00594f", "#cedc00")), ("haas", ("#b6babd", "#e10600")), ("alfa romeo", ("#a50f2d", "#ffffff")),
    ("sauber", ("#00e701", "#000000")), ("alphatauri", ("#2b4562", "#ffffff")), ("toro rosso", ("#0032ff", "#e10600")),
    ("racing bulls", ("#6692ff", "#ffffff")), ("renault", ("#fff500", "#000000")), ("lotus", ("#1a1a1a", "#d4af37")),
    ("brabham", ("#0b3d91", "#ffffff")), ("tyrrell", ("#0b2c5e", "#ffffff")), ("jordan", ("#f5d500", "#000000")),
    ("benetton", ("#00a651", "#00a0e3")), ("minardi", ("#111111", "#f5d500")), ("toyota", ("#e30613", "#ffffff")),
    ("jaguar", ("#004225", "#ffffff")), ("bar", ("#ffffff", "#c8102e")), ("honda", ("#ffffff", "#e40521")),
    ("bmw", ("#ffffff", "#0066b1")), ("ligier", ("#005eb8", "#ffffff")), ("march", ("#ff6600", "#000000")),
    ("cooper", ("#004225", "#ffffff")), ("maserati", ("#c8102e", "#ffffff")), ("vanwall", ("#004225", "#ffd100")),
    ("brm", ("#004225", "#ff8200")), ("penske", ("#ffd100", "#1a1a1a")), ("ganassi", ("#c8102e", "#1a1a1a")),
    ("andretti", ("#ff8200", "#1a1a1a")), ("prema", ("#c8102e", "#ffffff")), ("art grand prix", ("#1a1a1a", "#ffffff")),
    ("carlin", ("#003b5c", "#ffd100")), ("dams", ("#00a3e0", "#ffffff")), ("trident", ("#003b5c", "#c0c0c0")),
    ("mp motorsport", ("#ff8200", "#ffffff")), ("campos", ("#c8102e", "#ffd100")), ("hitech", ("#c0c0c0", "#c8102e")),
    ("virtuosi", ("#1a1a1a", "#d4af37")), ("jaguar tcs", ("#1a1a1a", "#c0c0c0")), ("porsche", ("#ffffff", "#c8102e")),
    ("nissan", ("#c8102e", "#ffffff")), ("ds penske", ("#1a1a1a", "#d4af37")), ("envision", ("#00b2a9", "#ffffff")),
]


def valida(cor):
    return isinstance(cor, str) and bool(re.fullmatch(r"#[0-9a-fA-F]{6}", cor))


def cor_padrao(eid):
    return PALETA[zlib.crc32(str(eid).encode()) % len(PALETA)]


def cor_equipe(eq):
    """Cor principal da equipe (do JSON ou derivada do ID)."""
    if not eq:
        return "#808080"
    cor = eq.get("cor")
    return cor if valida(cor) else cor_padrao(eq.get("id", eq.get("nome", "")))


def cor_secundaria(eq):
    cor = (eq or {}).get("cor_secundaria")
    return cor if valida(cor) else None


def sugerir(nome_normalizado, usadas=()):
    """Cores para uma equipe importada: conhecidas pelo nome ou a próxima da paleta ainda não usada."""
    for chave, cores in CONHECIDAS:
        if re.search(rf"\b{re.escape(chave)}\b", nome_normalizado):
            return cores
    livres = [c for c in PALETA if c not in usadas] or PALETA
    return livres[0], None


def texto_legivel(cor):
    """Preto ou branco, o que tiver mais contraste sobre a cor."""
    r, g, b = (int(cor[i:i + 2], 16) for i in (1, 3, 5))
    return "#000000" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#ffffff"
