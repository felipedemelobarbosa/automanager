"""Países: nome em inglês (Wikipedia) -> nome em português (database) e arquivo da bandeira na Wikimedia."""
import re
import unicodedata

# inglês -> português
PAISES = {
    "Argentina": "Argentina", "Australia": "Austrália", "Austria": "Áustria", "Belgium": "Bélgica",
    "Brazil": "Brasil", "Canada": "Canadá", "China": "China", "Colombia": "Colômbia", "Denmark": "Dinamarca",
    "Finland": "Finlândia", "France": "França", "Germany": "Alemanha", "West Germany": "Alemanha Ocidental",
    "East Germany": "Alemanha Oriental", "Hungary": "Hungria", "India": "Índia", "Indonesia": "Indonésia",
    "Ireland": "Irlanda", "Republic of Ireland": "Irlanda", "Italy": "Itália", "Japan": "Japão",
    "Malaysia": "Malásia", "Mexico": "México", "Monaco": "Mônaco", "Netherlands": "Holanda",
    "New Zealand": "Nova Zelândia", "Poland": "Polônia", "Portugal": "Portugal", "Russia": "Rússia",
    "South Africa": "África do Sul", "Spain": "Espanha", "Sweden": "Suécia", "Switzerland": "Suíça",
    "Thailand": "Tailândia", "United Kingdom": "Reino Unido", "United States": "Estados Unidos",
    "Venezuela": "Venezuela", "Chile": "Chile", "Uruguay": "Uruguai", "Czech Republic": "República Tcheca",
    "Czechia": "República Tcheca", "Bahrain": "Bahrein", "Saudi Arabia": "Arábia Saudita",
    "Azerbaijan": "Azerbaijão", "Singapore": "Singapura", "Qatar": "Catar",
    "United Arab Emirates": "Emirados Árabes Unidos", "Turkey": "Turquia", "Korea": "Coreia do Sul",
    "South Korea": "Coreia do Sul", "Israel": "Israel", "Liechtenstein": "Liechtenstein", "Estonia": "Estônia",
    "England": "Inglaterra", "Scotland": "Escócia", "Wales": "País de Gales", "Northern Ireland": "Irlanda do Norte",
    "Luxembourg": "Luxemburgo", "Norway": "Noruega", "Iceland": "Islândia", "Greece": "Grécia",
    "Slovakia": "Eslováquia", "Slovenia": "Eslovênia", "Croatia": "Croácia", "Serbia": "Sérvia",
    "Ukraine": "Ucrânia", "Latvia": "Letônia", "Lithuania": "Lituânia", "Romania": "Romênia",
    "Bulgaria": "Bulgária", "Belarus": "Bielorrússia", "Kazakhstan": "Cazaquistão", "Andorra": "Andorra",
    "San Marino": "San Marino", "Malta": "Malta", "Cyprus": "Chipre", "Soviet Union": "União Soviética",
    "Rhodesia": "Rodésia", "Zimbabwe": "Zimbábue", "Kenya": "Quênia", "Morocco": "Marrocos", "Egypt": "Egito",
    "Algeria": "Argélia", "Philippines": "Filipinas", "Taiwan": "Taiwan", "Hong Kong": "Hong Kong",
    "Macau": "Macau", "Vietnam": "Vietnã", "Pakistan": "Paquistão", "Sri Lanka": "Sri Lanka", "Iran": "Irã",
    "Lebanon": "Líbano", "Kuwait": "Kuwait", "Oman": "Omã", "Peru": "Peru", "Ecuador": "Equador",
    "Paraguay": "Paraguai", "Bolivia": "Bolívia", "Costa Rica": "Costa Rica", "Guatemala": "Guatemala",
    "Puerto Rico": "Porto Rico", "Cuba": "Cuba", "Dominican Republic": "República Dominicana",
    "Jamaica": "Jamaica", "Barbados": "Barbados", "Panama": "Panamá", "El Salvador": "El Salvador",
}
# português -> título do arquivo da bandeira (Wikimedia Commons), quando não é "Flag of <inglês>.svg"
ARQUIVOS_ESPECIAIS = {
    "China": "Flag of the People's Republic of China.svg", "Alemanha Ocidental": "Flag of Germany.svg",
    "Rodésia": "Flag of Rhodesia (1968–1979).svg", "Taiwan": "Flag of the Republic of China.svg",
    "Holanda": "Flag of the Netherlands.svg", "Reino Unido": "Flag of the United Kingdom.svg",
    "Estados Unidos": "Flag of the United States.svg", "República Tcheca": "Flag of the Czech Republic.svg",
    "Emirados Árabes Unidos": "Flag of the United Arab Emirates.svg", "Filipinas": "Flag of the Philippines.svg",
    "República Dominicana": "Flag of the Dominican Republic.svg", "União Soviética": "Flag of the Soviet Union.svg",
    "Coreia do Sul": "Flag of South Korea.svg", "Irlanda": "Flag of Ireland.svg",
    "Irlanda do Norte": "Flag of Northern Ireland (1953–1972).svg",
}
PT_PARA_EN = {}
for _en, _pt in PAISES.items():
    PT_PARA_EN.setdefault(_pt, _en)


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


_POR_NORMA = {_norm(pt): pt for pt in PT_PARA_EN}
_POR_NORMA.update({_norm(en): pt for en, pt in PAISES.items()})


def em_portugues(nome):
    """Nome do país em português (aceita português ou inglês, sem diferenciar acentos/maiúsculas)."""
    return _POR_NORMA.get(_norm(nome), (nome or "").strip())


def do_local(local):
    """'Serra Azul, Brasil' -> 'Brasil'."""
    return (local or "").split(",")[-1].strip()


def arquivo_wikimedia(pais_pt):
    pais_pt = em_portugues(pais_pt)
    if pais_pt in ARQUIVOS_ESPECIAIS:
        return ARQUIVOS_ESPECIAIS[pais_pt]
    en = PT_PARA_EN.get(pais_pt, pais_pt)
    return f"Flag of {en}.svg"


def chave(pais):
    """Nome do arquivo local da bandeira (sem pasta/extensão)."""
    return _norm(em_portugues(pais))
