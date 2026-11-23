"""Editor da database (JSON), com formulários explicados, listas com busca/filtro, referências pelo
nome, validação por campo e importação da Wikipedia em etapas."""
import copy
import json
import os
import re
import tkinter as tk
import unicodedata
from tkinter import ttk, messagebox, filedialog, simpledialog

from .. import db
from ..db import ATRIBUTOS_PILOTO, ATRIBUTOS_CHASSIS, NOMES_ATRIBUTOS
from ..editor import wikipedia
from ..util import PASTA_DATABASE, dinheiro
from .. import paises
from . import win9x as w
from .formularios import F, FormGenerico, TabelaEditavel, MatrizEditavel, obter


def _slug(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:28] or "novo"


# ====================================================================== esquemas
class Esquemas:
    """Campos dos formulários. As opções de referência são lidas na hora (nomes das equipes etc.)."""

    def __init__(self, editor):
        self.ed = editor

    def _lista(self, chave):
        return [(x["id"], x.get("nome", x["id"])) for x in (self.ed.dados or {}).get(chave, [])]

    def equipes(self):
        return self._lista("equipes")

    def chassis(self):
        return self._lista("chassis")

    def motores(self):
        return self._lista("motores")

    def corridas_calendario(self):
        return [(e.get("id"), f"S{e.get('semana')} {e.get('nome', e.get('id'))}")
                for e in (self.ed.dados or {}).get("calendario", []) if e.get("especie") == "corrida"]

    def nomes_equipes(self):
        return [(x.get("nome"), x.get("nome")) for x in (self.ed.dados or {}).get("equipes", [])]

    def _id_unico(self, chave):
        def valida(v, item):
            if not v:
                return "o ID é obrigatório"
            if sum(1 for x in (self.ed.dados or {}).get(chave, []) if x.get("id") == v and x is not item):
                return "já existe outro registro com este ID"
            return None
        return valida

    def _campo(self, *a, validador=None, **k):
        c = F(*a, **k)
        if validador:
            c["validador"] = validador
        return c

    def contrato(self, prefixo, extras, ajuda="Desmarque se não houver contrato.", chave="contrato",
                 rotulo="Contrato"):
        g = tuple(prefixo) + (chave,)
        return [F(g, rotulo, "grupo", ajuda)] + [dict(F(g + (k,), r, t, a, o, grupo=g), **x)
                                                     for k, r, t, a, o, x in extras] + \
            [F(g, "Duração", "duracao", "Em temporadas ou em quantidade de corridas.", grupo=g)]

    def parte_futura(self, parte, rotulo, opcoes, origens):
        g = (f"{parte}_futuro",)
        return [F(g, rotulo, "grupo", "Opcional. Já contratado para uma temporada futura (um por peça). Se a "
                                      "peça atual for comprada, o contrato dela tem de terminar antes."),
                dict(F(g + ("id",), "Chassis" if parte == "chassis" else "Motor", "ref", "", opcoes, grupo=g),
                     obrig=True),
                F(g + ("origem",), "Origem", "escolha", "", origens, grupo=g),
                dict(F(g + ("contrato", "valor_por_corrida"), "Valor por corrida (USD)", "real", "", grupo=g), min=0),
                dict(F(g + ("contrato", "inicio_ano"), "Começa em (ano)", "int", "Temporada em que o contrato começa: "
                       "depois do ano do arquivo.", grupo=g), min=1900, max=2200, obrig=True),
                F(g + ("contrato",), "Duração", "duracao", "Em temporadas ou em quantidade de corridas.", grupo=g)]

    def pilotos(self):
        return ([self._campo("id", "ID", "texto", "Identificador único (gerado pelo nome).",
                             validador=self._id_unico("pilotos")),
                 F("nome", "Nome", "texto", obrigatorio=True),
                 F("nacionalidade", "Nacionalidade", "pais", "Escolha na lista ou digite para filtrar (um país fora da lista também vale, mas fica sem bandeira)."),
                 F("idade", "Idade", "int", minimo=10, maximo=70),
                 F("ano_pico", "Ano de pico", "int", "Ano em que as habilidades chegam ao máximo. Vazio: o jogo define."),
                 F("potencial", "Potencial", "int", "Média dos atributos no pico (0-100). Vazio: o jogo estima.",
                   minimo=0, maximo=100),
                 F("aposentadoria", "Aposentadoria", "aposentadoria",
                   "Por ano (ano em que deixa de correr) ou por idade (deixa de correr ao completá-la). "
                   "Sorteio: o jogo define (entre 34 e 40 anos).")]
                + [F("wikipedia", "Artigo na Wikipedia", "texto_opcional",
                    "Título do artigo em inglês (ex.: Ayrton Senna). Vazio = usa o nome."),
                 dict(F("imagem", "Foto", "imagem",
                        "Imagem salva em database/imagens. Buscar usa o artigo acima."),
                      tipo_img="piloto")]
                + [F(("atributos", a), NOMES_ATRIBUTOS[a], "atr") for a in ATRIBUTOS_PILOTO]
                + self.contrato((), [
                    ("equipe", "Equipe", "ref", "", self.equipes, {"obrig": True}),
                    ("valor_por_corrida", "Salário por corrida (USD)", "real", "", None, {"min": 0}),
                    ("situacao", "Função", "escolha", "", [("principal", "principal"), ("teste", "teste")], {})],
                    "Sem contrato = piloto livre no mercado.")
                + [dict(F(("contrato", "corridas_definidas"), "Corridas definidas", "lista_ref",
                          "Opcional. Marque as corridas em que o piloto corre (revezamento): a duração passa a ser "
                          "por corridas, na quantidade marcada. Nenhuma marcada = corre todas enquanto durar o "
                          "contrato.", self.corridas_calendario, grupo=("contrato",)),
                        vazio_remove=True, conta_corridas=True, altura=8)]
                + self.contrato((), [
                    ("equipe", "Equipe", "ref", "", self.equipes, {"obrig": True}),
                    ("valor_por_corrida", "Salário por corrida (USD)", "real", "", None, {"min": 0}),
                    ("situacao", "Função", "escolha", "", [("principal", "principal"), ("teste", "teste")], {}),
                    ("inicio_ano", "Começa em (ano)", "int", "Temporada em que o contrato começa: depois do ano do "
                     "arquivo e depois do fim do contrato atual.", None, {"min": 1900, "max": 2200, "obrig": True})],
                    "Opcional. Piloto já contratado para uma temporada futura (um por piloto). A equipe precisa "
                    "ter vaga nesse ano.", chave="contrato_futuro", rotulo="Contrato futuro"))

    def chassis_campos(self):
        return ([self._campo("id", "ID", "texto", validador=self._id_unico("chassis")),
                 F("nome", "Nome", "texto", obrigatorio=True), F("nacionalidade", "Nacionalidade", "pais")]
                + [F("wikipedia", "Artigo na Wikipedia", "texto_opcional",
                    "Título do artigo em inglês (ex.: McLaren MCL60). Vazio = usa o nome."),
                 dict(F("logotipo", "Logotipo", "imagem",
                        "Imagem salva em database/imagens. Buscar usa o artigo acima."),
                      tipo_img="chassis")] + [
                 F("equipe", "Equipe dona", "ref", "Equipe que desenvolve o chassis. Vazio = fornecedor que vende "
                                                     "para as equipes.", self.equipes)]
                + [F(("atributos", a), NOMES_ATRIBUTOS[a], "atr") for a in ATRIBUTOS_CHASSIS]
                + self.contrato((), [("valor_por_corrida", "Preço por corrida (USD)", "real",
                                      "Preço cobrado das equipes clientes.", None, {"min": 0})],
                                "Termos oferecidos às equipes clientes."))

    def motores_campos(self):
        return ([self._campo("id", "ID", "texto", validador=self._id_unico("motores")),
                 F("nome", "Nome", "texto", obrigatorio=True), F("nacionalidade", "Nacionalidade", "pais")]
                + [F("wikipedia", "Artigo na Wikipedia", "texto_opcional",
                    "Título do artigo em inglês (ex.: Honda in Formula One). Vazio = usa o nome."),
                 dict(F("logotipo", "Logotipo", "imagem",
                        "Imagem salva em database/imagens. Buscar usa o artigo acima."),
                      tipo_img="motor")] + [
                 F("potencia", "Potência", "atr"),
                 F(("fabricante", "tipo"), "Fabricante", "escolha", "Uma equipe da categoria ou um fabricante "
                                                                     "independente.",
                   [("equipe", "equipe da categoria"), ("fabricante", "fabricante independente")]),
                 F(("fabricante", "equipe"), "Equipe fabricante", "ref", "Só quando o fabricante é uma equipe.",
                   self.equipes),
                 F(("exclusividade", "exclusivo"), "Exclusivo", "bool", "Se marcado, só a equipe abaixo (e a "
                                                                        "fabricante) pode usar."),
                 F(("exclusividade", "equipe"), "Exclusivo da equipe", "escolha", "", self.nomes_equipes)]
                + self.contrato((), [("valor_por_corrida", "Preço por corrida (USD)", "real", "", None, {"min": 0})],
                                "Termos oferecidos às equipes clientes."))

    def equipes_campos(self):
        return ([self._campo("id", "ID", "texto", validador=self._id_unico("equipes")),
                 F("nome", "Nome", "texto", obrigatorio=True), F("ativa", "Ativa", "bool",
                                                                 "Inativas podem surgir mais tarde."),
                 F("nacionalidade", "Nacionalidade", "pais"),
                 F("cor", "Cor principal", "cor", "Usada nas tabelas e telas do jogo. Vazio = cor automática."),
                 F("cor_secundaria", "Cor secundária", "cor", "Opcional (faixa na ficha de cor)."),
                 F("recursos", "Recursos", "atr", "Estrutura da equipe (0-100)."),
                 ] + [F("wikipedia", "Artigo na Wikipedia", "texto_opcional",
                    "Título do artigo em inglês (ex.: McLaren). Vazio = usa o nome."),
                 dict(F("logotipo", "Logotipo", "imagem",
                        "Imagem salva em database/imagens. Buscar usa o artigo acima."),
                      tipo_img="equipe")] + [
                 F("caixa", "Caixa inicial (USD)", "real", "Vazio = calculado pelo orçamento médio e pelos recursos."),
                 F("ano_surgimento", "Ano de surgimento", "int", "Para equipes inativas: ano em que entram. Vazio = "
                                                                 "por sorteio."),
                 F(("chassis", "id"), "Chassis", "ref", "", self.chassis),
                 F(("chassis", "origem"), "Origem do chassis", "escolha", "",
                   [("proprio", "próprio"), ("terceiros", "de fornecedor"), ("equipe", "de outra equipe")])]
                + self.contrato(("chassis",), [("valor_por_corrida", "Chassis: valor por corrida", "real", "", None,
                                                {"min": 0})], "Só para chassis de terceiros.")
                + [F(("motor", "id"), "Motor", "ref", "", self.motores),
                   F(("motor", "origem"), "Origem do motor", "escolha", "",
                     [("proprio", "próprio"), ("equipe", "de outra equipe"), ("fabricante", "de fabricante")])]
                + self.contrato(("motor",), [("valor_por_corrida", "Motor: valor por corrida", "real", "", None,
                                              {"min": 0})], "Só para motor de outra equipe ou de fabricante.")
                + self.parte_futura("chassis", "Chassis futuro", self.chassis,
                                    [("terceiros", "de fornecedor"), ("equipe", "de outra equipe")])
                + self.parte_futura("motor", "Motor futuro", self.motores,
                                    [("equipe", "de outra equipe"), ("fabricante", "de fabricante")])
                + [F("prob_fechamento", "Chance de fechar por ano", "real", "0 a 1 (ex.: 0,02 = 2%).", minimo=0, maximo=1),
                   F("prob_surgimento", "Chance de surgir por ano", "real", "0 a 1, para equipes inativas.", minimo=0,
                     maximo=1)])

    def patrocinadores_campos(self):
        g = ("contrato",)
        return [self._campo("id", "ID", "texto", validador=self._id_unico("patrocinadores")),
                F("nome", "Nome", "texto", obrigatorio=True), F("ativo", "Ativo", "bool"), F("pais", "País", "pais"),
                F("ramo", "Ramo"), F("valor_base", "Valor base (USD/temporada)", "real",
                                     "Referência para as propostas que a empresa faz.", minimo=0),
                F(("preferencia", "tipo"), "Preferência", "escolha", "",
                  [("nacionalidade_piloto", "piloto da nacionalidade"), ("nacionalidade_equipe", "equipe da nacionalidade"),
                   ("posicao_campeonato", "posição no campeonato")]),
                dict(F(("preferencia", "valor"), "Valor da preferência", "pref_valor",
                       "País (preferência por nacionalidade) ou posição máxima no campeonato – a lista muda com o "
                       "tipo de preferência."), depende=("preferencia", "tipo")),
                F(g, "Contrato", "grupo", "Sem contrato = procurando equipe."),
                F(g + ("equipe",), "Equipe", "ref", "", self.equipes, grupo=g),
                F(g + ("valor",), "Valor (USD)", "real", "", grupo=g, minimo=0),
                F(g + ("pagamento",), "Pagamento", "escolha", "", [("por_temporada", "por temporada"),
                                                                   ("por_corrida", "por corrida")], grupo=g),
                F(g + ("duracao",), "Duração", "int", "", grupo=g, minimo=1),
                F(g + ("unidade",), "Unidade da duração", "escolha", "", ["temporadas", "corridas"], grupo=g),
                F("prob_fechamento", "Chance de sair por ano", "real", minimo=0, maximo=1),
                F("prob_surgimento", "Chance de surgir por ano", "real", minimo=0, maximo=1)]

    def calendario_campos(self):
        return [self._campo("id", "ID", "texto", validador=self._id_unico("calendario")),
                F("nome", "Nome", "texto", obrigatorio=True), F("ativo", "Ativo", "bool", "Inativos podem entrar depois."),
                F("semana", "Semana", "int", "Semana do ano (1-52).", minimo=1, maximo=52),
                F("especie", "Espécie", "escolha", "", [("corrida", "corrida"), ("treino", "teste coletivo")]),
                F("local", "Local", "local", "Cidade (livre) e país (da lista; dá a bandeira)."),
                ] + [F("wikipedia", "Artigo na Wikipedia", "texto_opcional",
                    "Título do artigo em inglês (ex.: Circuit de Monaco). Vazio = usa o nome."),
                 dict(F("imagem", "Imagem da pista", "imagem",
                        "Imagem salva em database/imagens. Buscar usa o artigo acima."),
                      tipo_img="pista")] + [
                F("tipo_pista", "Tipo de pista", "escolha", "", [("mista", "mista"), ("oval", "oval"),
                                                                ("rua", "pista de rua")]),
                F("tempo_base_treino", "Tempo base treino/classif. (s)", "real", "Volta de referência nos treinos.",
                  minimo=1),
                F("tempo_base_corrida", "Tempo base corrida (s)", "real", minimo=1),
                dict(F("tempos_por_ano", "Tempos base por ano (s)", "tempos_ano",
                       "Opcional. Ano: treino / corrida, separados por ponto e vírgula (ex.: 2028: 88.4 / 90.1; "
                       "2031: 87.2 / 88.9). Anos sem valor seguem a evolução automática a partir do último ano "
                       "informado (ou do ano do arquivo)."), vazio_remove=True),
                F("voltas_corrida", "Voltas da corrida", "int", minimo=0),
                F("retas", "Retas", "atr", "Proporção de retas (a soma com as curvas é normalizada)."),
                F("curvas_alta", "Curvas de alta", "atr"), F("curvas_baixa", "Curvas de baixa", "atr"),
                F("desgaste_pneus", "Desgaste de pneus", "atr", "50 = referência."),
                F("dificuldade", "Dificuldade", "atr"),
                F("duracao_pitstop", "Perda no pit stop (s)", "real", minimo=0),
                F("prob_chuva", "Chance de chuva", "real", "0 a 1 por sessão.", minimo=0, maximo=1),
                F("prob_inativar", "Chance de sair do calendário", "real", minimo=0, maximo=1),
                F("prob_ativar", "Chance de entrar no calendário", "real", minimo=0, maximo=1),
                dict(F("anos_entrada", "Anos em que entra no calendário", "lista_num",
                       "Ex.: 2028, 2033. Pista de reserva que entra nesses anos (anos depois do ano do arquivo). "
                       "Nesses anos a chance sorteada não vale."), vazio_remove=True),
                dict(F("anos_saida", "Anos em que sai do calendário", "lista_num",
                       "Ex.: 2030, 2035. A pista sai nesses anos e fica fora até um ano de entrada (ou o sorteio). "
                       "Pode entrar e sair várias vezes."), vazio_remove=True)]


NOVOS = {
    "pilotos": {"id": "novo", "nome": "Novo piloto", "nacionalidade": "", "idade": 20,
                "atributos": {a: 50 for a in ATRIBUTOS_PILOTO}, "contrato": None},
    "chassis": {"id": "ch_novo", "nome": "Novo chassis", "nacionalidade": "", "equipe": None,
                "atributos": {a: 50 for a in ATRIBUTOS_CHASSIS}, "contrato": {"valor_por_corrida": 50000, "temporadas": 1}},
    "motores": {"id": "mot_novo", "nome": "Novo motor", "nacionalidade": "", "potencia": 50,
                "fabricante": {"tipo": "fabricante"}, "exclusividade": {"exclusivo": False, "equipe": None},
                "contrato": {"valor_por_corrida": 50000, "temporadas": 1}},
    "equipes": {"id": "nova", "nome": "Nova equipe", "ativa": True, "nacionalidade": "", "recursos": 50, "caixa": None,
                "chassis": {"id": None, "origem": "proprio"}, "motor": {"id": None, "origem": "fabricante"},
                "prob_fechamento": 0.01, "prob_surgimento": 0.0},
    "patrocinadores": {"id": "pat_novo", "nome": "Novo patrocinador", "ativo": True, "pais": "", "ramo": "",
                       "valor_base": 1000000, "preferencia": {"tipo": "posicao_campeonato", "valor": 5},
                       "contrato": None, "prob_fechamento": 0.03, "prob_surgimento": 0.0},
    "calendario": {"id": "ev_novo", "nome": "Novo evento", "ativo": True, "semana": 10, "especie": "corrida",
                   "local": "", "tipo_pista": "mista", "tempo_base_treino": 90.0, "tempo_base_corrida": 92.0,
                   "voltas_corrida": 60, "retas": 40, "curvas_alta": 30, "curvas_baixa": 30, "desgaste_pneus": 50,
                   "dificuldade": 50, "duracao_pitstop": 22.0, "prob_chuva": 0.2, "prob_inativar": 0.02,
                   "prob_ativar": 0.0},
}
PREFIXO_ID = {"pilotos": "", "chassis": "ch_", "motores": "mot_", "equipes": "", "patrocinadores": "pat_",
              "calendario": "ev_"}
ABAS = [("pilotos", "Pilotos"), ("chassis", "Chassis"), ("motores", "Motores"), ("equipes", "Equipes"),
        ("patrocinadores", "Patrocinadores"), ("calendario", "Calendário")]
# referências que apontam para IDs (para renomear em cascata)
REFERENCIAS = {
    "equipes": [("pilotos", ("contrato", "equipe")), ("pilotos", ("contrato_futuro", "equipe")), ("chassis", ("equipe",)), ("motores", ("fabricante", "equipe")),
                ("patrocinadores", ("contrato", "equipe"))],
    "chassis": [("equipes", ("chassis", "id")), ("equipes", ("chassis_futuro", "id"))],
    "motores": [("equipes", ("motor", "id")), ("equipes", ("motor_futuro", "id"))],
}


def _media(d):
    v = list((d or {}).values())
    return sum(v) / len(v) if v else 0


# ====================================================================== aba de entidades
class AbaEntidades(tk.Frame):
    def __init__(self, master, editor, chave, campos):
        super().__init__(master, padx=4, pady=4)
        self.ed, self.chave = editor, chave
        esq = tk.Frame(self)
        esq.pack(side="left", fill="y")
        busca = tk.Frame(esq)
        busca.pack(fill="x")
        tk.Label(busca, text="Buscar:").pack(side="left")
        self.v_busca = tk.StringVar()
        en = ttk.Entry(busca, textvariable=self.v_busca, width=16)
        en.pack(side="left", padx=2)
        en.bind("<KeyRelease>", lambda e: self.recarregar(manter=True))
        self.cb_filtro = ttk.Combobox(busca, state="readonly", width=16)
        self.cb_filtro.pack(side="left", padx=2)
        self.cb_filtro.bind("<<ComboboxSelected>>", lambda e: self.recarregar(manter=True))
        cols = self._colunas()
        self.com_cores = True                     # ficha de cor da equipe + bandeira (calendário: só bandeira)
        fr, self.tv = w.tabela(esq, [(c, t) for c, t, _ in cols], 22, {c: lg for c, _, lg in cols},
                               estica={cols[0][0]}, cores=self.com_cores)
        fr.pack(fill="both", expand=True, pady=2)
        self.tv.bind("<<TreeviewSelect>>", lambda e: self.selecionar())
        b = tk.Frame(esq)
        b.pack(fill="x")
        w.Botao(b, "Novo...", self.novo, padx=6).pack(side="left")
        w.Botao(b, "Duplicar", self.duplicar, padx=6).pack(side="left", padx=2)
        w.Botao(b, "Excluir", self.excluir, padx=6).pack(side="left")
        dir_ = tk.Frame(self)
        dir_.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.lbl_frase = tk.Label(dir_, text="", anchor="w", justify="left", bg=w.AMARELO_INFO, relief="sunken", bd=1,
                                  wraplength=560)
        self.lbl_frase.pack(fill="x")
        self.lbl_erros = tk.Label(dir_, text="", anchor="w", justify="left", fg="#a00000", wraplength=560)
        self.lbl_erros.pack(fill="x")
        if chave == "calendario":
            w.Botao(dir_, "Calcular retas e curvas pelo mapa da pista...", self.calcular_mapa,
                    padx=6).pack(anchor="w", pady=(2, 4))
        self.form = FormGenerico(dir_, campos, ao_mudar=self._mudou)
        self.form.pack(fill="both", expand=True)
        self.atual = None
        self.id_carregado = None

    # ------------------------------------------------------------------ colunas / filtros
    def _colunas(self):
        return {
            "pilotos": [("nome", "Nome", 130), ("equipe", "Equipe", 100), ("nota", "Nota", 36), ("idade", "Id.", 30)],
            "chassis": [("nome", "Nome", 120), ("equipe", "Dono", 100), ("nota", "Nota", 40)],
            "motores": [("nome", "Nome", 130), ("equipe", "Fabricante", 100), ("nota", "Pot.", 40)],
            "equipes": [("nome", "Nome", 150), ("equipe", "Situação", 70), ("nota", "Rec.", 40)],
            "patrocinadores": [("nome", "Nome", 130), ("equipe", "Equipe", 100), ("nota", "Valor", 70)],
            "calendario": [("nome", "Nome", 160), ("equipe", "Tipo", 70), ("nota", "Sem.", 40)],
        }[self.chave]

    def _equipe_do_item(self, x):
        """Equipe ligada ao registro (a própria, a do contrato ou a dona), para a ficha de cor."""
        c = self.chave
        if c == "equipes":
            return x
        eid = {"pilotos": (x.get("contrato") or {}).get("equipe"), "chassis": x.get("equipe"),
               "motores": (x.get("fabricante") or {}).get("equipe"),
               "patrocinadores": (x.get("contrato") or {}).get("equipe")}.get(c)
        e = next((y for y in self.ed.dados.get("equipes", []) if y["id"] == eid), None)
        return e or {"id": "", "cor": w.CINZA}

    def _ficha(self, x):
        if self.chave == "calendario":
            return w.ficha(pais=paises.do_local(x.get("local")), com_cor=False)
        return w.chip_equipe(self._equipe_do_item(x), x.get("nacionalidade") or x.get("pais"))

    def _nome_equipe(self, eid):
        e = next((x for x in self.ed.dados.get("equipes", []) if x["id"] == eid), None)
        return e["nome"] if e else (eid or "")

    def _linha(self, x):
        c = self.chave
        if c == "pilotos":
            ct = x.get("contrato") or {}
            return x.get("nome", ""), self._nome_equipe(ct.get("equipe")) if ct else "livre", \
                f"{_media(x.get('atributos')):.0f}", x.get("idade", "")
        if c == "chassis":
            return x.get("nome", ""), self._nome_equipe(x.get("equipe")) if x.get("equipe") else "fornecedor", \
                f"{_media(x.get('atributos')):.0f}"
        if c == "motores":
            fab = x.get("fabricante") or {}
            return x.get("nome", ""), self._nome_equipe(fab.get("equipe")) if fab.get("tipo") == "equipe" \
                else "fabricante", x.get("potencia", "")
        if c == "equipes":
            return x.get("nome", ""), "ativa" if x.get("ativa") else "inativa", x.get("recursos", "")
        if c == "patrocinadores":
            ct = x.get("contrato") or {}
            return x.get("nome", ""), self._nome_equipe(ct.get("equipe")) if ct else "livre", \
                f"{(x.get('valor_base') or 0) / 1e6:.1f}M"
        return x.get("nome", ""), "corrida" if x.get("especie") == "corrida" else "teste", x.get("semana", "")

    def _filtros(self):
        c = self.chave
        if c == "pilotos":
            return ["Todos", "Livres"] + [e["nome"] for e in self.ed.dados.get("equipes", [])]
        if c in ("equipes", "patrocinadores", "calendario"):
            return ["Todos", "Ativos", "Inativos"]
        if c == "chassis":
            return ["Todos", "De equipes", "De fornecedores"]
        return ["Todos", "De equipes", "De fabricantes"]

    def _passa_filtro(self, x):
        f = self.cb_filtro.get() or "Todos"
        if f == "Todos":
            return True
        c = self.chave
        if c == "pilotos":
            ct = x.get("contrato")
            return not ct if f == "Livres" else (ct and self._nome_equipe(ct.get("equipe")) == f)
        if c in ("equipes", "patrocinadores", "calendario"):
            ativo = x.get("ativa", x.get("ativo"))
            return bool(ativo) == (f == "Ativos")
        if c == "chassis":
            return bool(x.get("equipe")) == (f == "De equipes")
        return ((x.get("fabricante") or {}).get("tipo") == "equipe") == (f == "De equipes")

    @property
    def lista(self):
        return self.ed.dados.setdefault(self.chave, [])

    # ------------------------------------------------------------------ lista
    def recarregar(self, manter=False):
        sel = self.atual if manter else None
        self.confirmar()
        filtros = self._filtros()
        self.cb_filtro.configure(values=filtros)
        if self.cb_filtro.get() not in filtros:
            self.cb_filtro.set("Todos")
        termo = _slug(self.v_busca.get()) if self.v_busca.get().strip() else ""
        self.tv.delete(*self.tv.get_children())
        for i, x in enumerate(self.lista):
            if termo and termo not in _slug(json.dumps(x, ensure_ascii=False)):
                continue
            if not self._passa_filtro(x):
                continue
            tags = ("cinza",) if (x.get("ativa", x.get("ativo", True)) is False) else ()
            if (self.chave, x.get("id")) in self.ed.erros_por_item:
                tags = ("erro",)
            extra = {"image": self._ficha(x)} if self.com_cores else {}
            self.tv.insert("", "end", iid=str(i), values=self._linha(x), tags=tags, **extra)
        self.tv.tag_configure("erro", foreground="#a00000")
        self.atual = None
        alvo = str(sel) if sel is not None and self.tv.exists(str(sel)) else \
            (self.tv.get_children()[0] if self.tv.get_children() else None)
        if alvo:
            self.tv.selection_set(alvo)
            self.tv.see(alvo)
            self.selecionar()
        else:
            self.form.carregar(None)
            self.lbl_frase.configure(text="")

    def selecionar(self):
        sel = self.tv.selection()
        if not sel:
            return
        i = int(sel[0])
        if self.atual is not None and self.atual != i:
            self.confirmar()
        self.atual = i
        item = self.lista[i]
        self.id_carregado = item.get("id")
        self.form.carregar(item)
        self._frase()
        erros = self.ed.erros_por_item.get((self.chave, item.get("id")), [])
        self.lbl_erros.configure(text="\n".join("⚠ " + e for e in erros))

    def ir_para(self, id_):
        self.v_busca.set("")
        self.cb_filtro.set("Todos")
        self.recarregar()
        for i, x in enumerate(self.lista):
            if x.get("id") == id_:
                self.tv.selection_set(str(i))
                self.tv.see(str(i))
                self.selecionar()
                return

    def confirmar(self):
        if self.atual is None or self.atual >= len(self.lista):
            return
        x = self.lista[self.atual]
        antes = json.dumps(x, sort_keys=True, default=str)
        self.form.salvar()
        if json.dumps(x, sort_keys=True, default=str) != antes:
            self.ed.modificado(True)
            novo_id = x.get("id")
            if self.id_carregado and novo_id and novo_id != self.id_carregado:
                self.ed.renomear_referencias(self.chave, self.id_carregado, novo_id)
                self.id_carregado = novo_id
        if self.tv.exists(str(self.atual)):
            self.tv.item(str(self.atual), values=self._linha(x))
            if self.com_cores:
                self.tv.item(str(self.atual), image=self._ficha(x))

    def _mudou(self):
        self.confirmar()
        self._frase()

    def calcular_mapa(self):
        if self.atual is None:
            return
        self.confirmar()
        try:
            import importlib
            importlib.import_module("..editor.mapa_pista", __package__)      # precisa do Pillow
            from .mapa_pista_tela import DialogoMapaPista
        except ImportError:
            messagebox.showerror("Mapa da pista", "Esta função precisa da biblioteca Pillow (pip install pillow).",
                                 parent=self)
            return
        item = self.lista[self.atual]
        r = DialogoMapaPista(self, item, (self.ed.dados or {}).get("categoria")).modal()
        if not r:
            return
        item.update(r)
        self.form.carregar(item)
        self.ed.modificado(True)
        if self.tv.exists(str(self.atual)):
            self.tv.item(str(self.atual), values=self._linha(item))
        self._frase()

    def _frase(self):
        """Resumo em linguagem natural do registro (contrato descrito em frase)."""
        if self.atual is None or self.atual >= len(self.lista):
            return
        x = self.lista[self.atual]
        c = self.chave
        from .. import i18n
        frases = []                       # uma frase por item: cada uma é traduzida inteira (i18n)
        def dur(ct):
            return f"{ct.get('corridas')} corridas" if "corridas" in ct else f"{ct.get('temporadas', 1)} temporada(s)"
        origem = {"proprio": "próprio", "equipe": "de outra equipe", "fabricante": "de fabricante", "terceiros": "de fornecedor"}
        if c == "pilotos":
            ct = x.get("contrato")
            if not ct:
                frases.append(f"{x.get('nome')} é piloto livre (sem contrato).")
            else:
                papel = "piloto principal" if ct.get("situacao", "principal") == "principal" else "piloto de testes"
                frases.append(f"{x.get('nome')} tem contrato com a {self._nome_equipe(ct.get('equipe'))} como {papel}: "
                              f"{dinheiro(ct.get('valor_por_corrida') or 0)} por corrida, por {dur(ct)}.")
            fut = x.get("contrato_futuro")
            if fut:
                papel = "piloto principal" if fut.get("situacao", "principal") == "principal" else "piloto de testes"
                frases.append(f"A partir de {fut.get('inicio_ano')}: contrato com a "
                              f"{self._nome_equipe(fut.get('equipe'))} como {papel}: "
                              f"{dinheiro(fut.get('valor_por_corrida') or 0)} por corrida, por {dur(fut)}.")
            frases.append(f"Nota média: {_media(x.get('atributos')):.0f}.")
        elif c in ("chassis", "motores"):
            ct = x.get("contrato")
            dono = x.get("equipe") if c == "chassis" else (x.get("fabricante") or {}).get("equipe")
            frases.append(f"{x.get('nome')}: da equipe {self._nome_equipe(dono)}." if dono
                          else f"{x.get('nome')}: de fornecedor independente.")
            if ct:
                frases.append(f"Vendido a {dinheiro(ct.get('valor_por_corrida') or 0)} por corrida, "
                              f"contratos de {dur(ct)}.")
            exc = x.get("exclusividade") or {}
            if exc.get("exclusivo"):
                frases.append(f"Exclusivo da {exc.get('equipe')}.")
        elif c == "equipes":
            ch = (x.get("chassis") or {})
            mo = (x.get("motor") or {})
            nome_ch = next((y["nome"] for y in self.ed.dados.get("chassis", []) if y["id"] == ch.get("id")), "nenhum")
            nome_mo = next((y["nome"] for y in self.ed.dados.get("motores", []) if y["id"] == mo.get("id")), "nenhum")
            pil = [p["nome"] for p in self.ed.dados.get("pilotos", []) if (p.get("contrato") or {}).get("equipe") == x["id"]]
            frases.append(f"{x.get('nome')} ({'ativa' if x.get('ativa') else 'inativa'}): chassis {nome_ch} "
                          f"({origem.get(ch.get('origem'), '-')}), motor {nome_mo} ({origem.get(mo.get('origem'), '-')}).")
            frases.append(f"Pilotos: {', '.join(pil)}." if pil else "Pilotos: nenhum.")
            for parte, lista in (("chassis", "chassis"), ("motor", "motores")):
                fut = x.get(f"{parte}_futuro")
                if fut:
                    nome = next((y["nome"] for y in self.ed.dados.get(lista, []) if y["id"] == fut.get("id")),
                                fut.get("id"))
                    ct = fut.get("contrato") or {}
                    frases.append(f"A partir de {ct.get('inicio_ano')}: {parte} {nome}, "
                                  f"{dinheiro(ct.get('valor_por_corrida') or 0)} por corrida, por {dur(ct)}.")
        elif c == "patrocinadores":
            ct = x.get("contrato")
            if ct:
                pag = "por temporada" if ct.get("pagamento") == "por_temporada" else "por corrida"
                frases.append(f"{x.get('nome')} ({x.get('ramo') or '-'}): patrocina a {self._nome_equipe(ct.get('equipe'))} "
                              f"com {dinheiro(ct.get('valor') or 0)} {pag}, por {ct.get('duracao')} {ct.get('unidade')}.")
            else:
                frases.append(f"{x.get('nome')} ({x.get('ramo') or '-'}): procurando equipe.")
        else:
            soma = (x.get("retas") or 0) + (x.get("curvas_alta") or 0) + (x.get("curvas_baixa") or 0) or 1
            frases.append(f"{x.get('nome')} – semana {x.get('semana')}, {x.get('local') or '-'}: "
                          f"{x.get('voltas_corrida')} voltas, {100 * (x.get('retas') or 0) / soma:.0f}% de retas, "
                          f"chance de chuva {100 * (x.get('prob_chuva') or 0):.0f}%.")
        txt = "  ".join(i18n.t(f) for f in frases)
        self.lbl_frase.configure(text=txt)

    # ------------------------------------------------------------------ ações
    def _novo_id(self, nome):
        base = PREFIXO_ID[self.chave] + _slug(nome)
        ids = {x.get("id") for x in self.lista}
        novo, n = base, 2
        while novo in ids:
            novo = f"{base}_{n}"
            n += 1
        return novo

    def novo(self, base=None):
        self.confirmar()
        nome = simpledialog.askstring("Novo", "Nome:", parent=self,
                                      initialvalue=(base or NOVOS[self.chave]).get("nome", ""))
        if not nome:
            return
        item = copy.deepcopy(base or NOVOS[self.chave])
        item["nome"] = nome
        item["id"] = self._novo_id(nome)
        self.lista.append(item)
        self.ed.modificado(True)
        self.v_busca.set("")
        self.cb_filtro.set("Todos")
        self.recarregar()
        self.ir_para(item["id"])

    def duplicar(self):
        if self.atual is not None:
            self.confirmar()
            self.novo(self.lista[self.atual])

    def excluir(self):
        if self.atual is None:
            return
        x = self.lista[self.atual]
        if messagebox.askyesno("Excluir", f"Excluir '{x.get('nome', x.get('id'))}'?", parent=self):
            del self.lista[self.atual]
            self.atual = None
            self.ed.modificado(True)
            self.recarregar()


# ====================================================================== aba Categoria (formulários por seção)
class AbaCategoria(ttk.Notebook):
    COMPOSTO = [F("nome", "Nome", obrigatorio=True),
                F("tipo", "Tipo", "escolha", "", [("seco", "seco"), ("chuva_leve", "chuva leve"),
                                                  ("chuva_pesada", "chuva forte")]),
                F("ritmo", "Ritmo", "real", "Multiplicador do tempo com pneu novo (menor = mais rápido).", minimo=0.5,
                  maximo=1.5),
                F("degradacao", "Degradação por volta", "real", "Fração do tempo perdida a cada volta de uso.",
                  minimo=0),
                F("vida", "Vida (voltas)", "real", "Voltas até o cliff, em pista e carro de referência.", minimo=1),
                F("cliff", "Intensidade do cliff", "real", "Perda extra por (voltas além da vida)^1,5.", minimo=0),
                F("aquecimento_voltas", "Voltas de aquecimento", "int", minimo=0),
                F("sensibilidade_termica", "Sensibilidade térmica", "real",
                  "Quanto agressividade e uso do carro aceleram o desgaste.", minimo=0)]
    EFEITO = [F("tempo", "Tempo", "real", "Multiplicador do tempo de volta."),
              F("peso_chassis", "Peso do chassis", "real"), F("peso_motor", "Peso do motor", "real"),
              F("peso_piloto", "Peso do piloto", "real"), F("acidentes", "Acidentes", "real", "Multiplicador do risco."),
              F("aleatoriedade", "Aleatoriedade", "real"), F("ultrapassagem", "Ultrapassagem", "real")]
    TREINO = [F("nome", "Nome", obrigatorio=True),
              F("limite", "Limite", "escolha", "", [("tempo", "por tempo (min)"), ("voltas", "por voltas")]),
              F("valor", "Valor", "int", "Minutos ou voltas.", minimo=1)]
    ETAPA = [F("nome", "Nome", obrigatorio=True),
             F("modelo", "Modelo", "escolha", "Como o grid é formado.",
               [("tempo", "sessão(ões) por tempo/voltas"), ("grupos", "grupos intercalados"),
                ("volta_unica", "volta única"), ("corrida_classificatoria", "corrida classificatória"),
                ("campeonato", "pela classificação do campeonato")]),
             F("limite", "Limite (tempo/grupos)", "escolha", "Sem fases: limite da sessão.",
               [("tempo", "tempo"), ("voltas", "voltas")]),
             F("valor", "Valor (min ou voltas)", "int", minimo=1),
             F("grupos", "Nº de grupos", "int", "Modelo 'grupos'.", minimo=1),
             F("voltas_cronometradas", "Voltas cronometradas", "int", "Modelo 'volta única'.", minimo=1),
             F("criterio", "Critério", "escolha", "Volta única: melhor volta ou média.",
               [("melhor_volta", "melhor volta"), ("media", "média das voltas")]),
             F("ordem_saida", "Ordem de saída", "escolha", "Volta única.",
               [("campeonato_invertido", "campeonato invertido"), ("campeonato", "campeonato"),
                ("aleatoria", "aleatória")]),
             F("voltas", "Voltas da bateria", "int", "Corrida classificatória.", minimo=1),
             F("grid", "Grid da bateria", "escolha", "Corrida classificatória.",
               [("anterior", "resultado anterior"), ("campeonato_invertido", "campeonato invertido"),
                ("campeonato", "campeonato"), ("aleatorio", "aleatório")]),
             F("invertido", "Invertido", "bool", "Modelo 'campeonato'.")]
    FASE = [F("nome", "Nome", obrigatorio=True),
            F("limite", "Limite", "escolha", "", [("tempo", "tempo (min)"), ("voltas", "voltas")]),
            F("valor", "Valor", "int", minimo=1),
            F("eliminados", "Eliminados ao fim", "int", "0 = sem eliminação.", minimo=0)]

    def __init__(self, master, editor):
        super().__init__(master)
        self.ed = editor
        self.paineis = []
        self._form("Geral", [
            F("id", "ID da categoria", "texto", "Usado no nome do arquivo: <id>_<ano>.json", obrigatorio=True),
            F("nome", "Nome", obrigatorio=True), F("ano", "Ano", "int", minimo=1900, maximo=2200),
            F("moeda", "Moeda"),
            F("tier", "Tier", "int", "Nível da categoria: 1 = topo, 2, 3...", minimo=1),
            F(("mobilidade", "de_tier_inferior"), "Vinda de tier inferior", "real",
              "Multiplicador da chance de pilotos subirem para esta categoria."),
            F(("mobilidade", "de_tier_superior"), "Vinda de tier superior", "real", "Pilotos descendo de nível."),
            F(("mobilidade", "mesmo_tier"), "Vinda do mesmo tier", "real", "Entre categorias do mesmo nível."),
            F(("mobilidade", "retorno", "prob_anual"), "Retorno de aposentado: chance por temporada", "real",
              "Chance de um ex-piloto da categoria voltar às pistas (cai com o tempo fora). Padrão 0,04 "
              "(≈ 1 retorno por temporada na F1).", minimo=0, maximo=1),
            F(("mobilidade", "retorno", "anos_maximos_fora"), "Retorno: máximo de temporadas parado", "int",
              "Padrão 6.", minimo=1),
            F(("mobilidade", "retorno", "idade_maxima"), "Retorno: idade máxima", "int", "Padrão 40.", minimo=17),
            F(("carreira", "calibracao_automatica"), "Manter o nível dos pilotos da database", "bool",
              "Estreantes com nível e potencial da database e correção suave por temporada. Padrão ligado.")])
        self._form("Regras", [
            F(("regras", "pilotos_principais_por_equipe"), "Pilotos principais por equipe", "int", minimo=1),
            F(("regras", "pilotos_minimos_por_equipe"), "Mínimo de pilotos titulares por equipe", "int",
              "Em cada corrida. Abaixo dele o PC contrata na hora e o jogador não avança a semana. Vazio = sem "
              "mínimo.", minimo=1),
            F(("regras", "pilotos_de_teste"), "Há pilotos de teste", "bool"),
            F(("regras", "pilotos_de_teste_por_equipe"), "Pilotos de teste por equipe", "int", minimo=0),
            F(("regras", "desenvolvimento_chassis_por_equipe"), "Equipes desenvolvem o chassis", "bool",
              "Sem isso, chassis são comprados de fornecedores."),
            F(("regras", "fontes_de_chassis_permitidas"), "Origens de chassis permitidas", "multi",
              "Vazio = só próprio (com desenvolvimento de chassis) ou só de fornecedor (sem). Com desenvolvimento, "
              "marcar fornecedor e/ou outra equipe deixa cada equipe escolher entre desenvolver e comprar.",
              [("proprio", "próprio"), ("fabricante", "de fornecedor"), ("equipe", "de outra equipe")]),
            F(("regras", "clientes_por_chassis"), "Clientes por chassis", "int",
              "Quantas equipes podem comprar o chassis de uma mesma equipe. Padrão 2. 0 = sem limite.", minimo=0),
            F(("regras", "desenvolvimento_motor_por_equipe"), "Há motor próprio", "bool"),
            F(("regras", "equipes_com_desenvolvimento_de_motor"), "Equipes que podem ter motor próprio", "lista_ref",
              "Nenhuma marcada = todas.", lambda: [(e["id"], e["nome"]) for e in (self.ed.dados or {}).get("equipes", [])]),
            F(("regras", "fontes_de_motor_permitidas"), "Origens de motor permitidas", "multi", "",
              [("proprio", "próprio"), ("equipe", "de outra equipe"), ("fabricante", "de fabricante")]),
            F(("regras", "testes_coletivos"), "Há testes coletivos", "bool"),
            F(("regras", "orcamento_medio"), "Orçamento médio (USD)", "real", minimo=0),
            F(("regras", "inflacao_media_anual"), "Inflação média anual", "real", "Ex.: 0,03 = 3%."),
            F(("regras", "patrocinios"), "Há patrocínios", "bool"),
            F(("regras", "renda_tv", "ativa"), "Há renda de TV", "bool"),
            F(("regras", "renda_tv", "ano_inicio"), "TV: a partir do ano", "int",
              "Antes desse ano não há renda de TV (nem sempre houve transmissão). Vazio = sempre.", minimo=1800),
            F(("regras", "renda_tv", "valor_medio_por_equipe"), "TV: valor médio por equipe", "real", minimo=0),
            F(("regras", "renda_tv", "fator_por_posicao_campeonato"), "TV: fator por posição", "lista_num",
              "Pela classificação final de equipes da temporada anterior: 1º, 2º, ... (ex.: 1.4, 1.3, 1.2). No 1º ano "
              "do jogo, 1,0 para todas; equipe nova recebe o fator do último lugar."),
            F(("regras", "premios_corrida", "ativa"), "Há prêmios por corrida", "bool",
              "Pagos à equipe depois de cada corrida."),
            F(("regras", "premios_corrida", "vitoria"), "Prêmio: vitória (USD)", "real", minimo=0),
            F(("regras", "premios_corrida", "podio"), "Prêmio: pódio, por carro (USD)", "real",
              "1º a 3º lugar (o vencedor recebe também o da vitória).", minimo=0),
            F(("regras", "premios_corrida", "por_ponto"), "Prêmio: por ponto marcado (USD)", "real", minimo=0),
            F(("regras", "importancia_carro"), "Importância do carro", "real", "Carro + piloto = 1.", minimo=0, maximo=1),
            F(("regras", "importancia_piloto"), "Importância do piloto", "real", minimo=0, maximo=1),
            F(("regras", "idade_pilotos", "idade_maxima"), "Idade máxima dos pilotos", "int",
              "Acima dela a categoria não contrata e o contrato termina na virada de temporada. Vazio = sem limite.",
              minimo=15),
            F(("regras", "idade_pilotos", "preferida_ate"), "Idade preferida (até)", "int",
              "Categorias de base: as equipes do PC preferem pilotos até esta idade. Vazio = sem preferência.",
              minimo=15),
            F(("regras", "idade_pilotos", "penalidade_por_ano"), "Penalidade por ano acima da idade preferida", "real",
              "Pontos tirados da nota do piloto na escolha das equipes do PC. Ex.: 4.", minimo=0),
            F(("regras", "motores_por_temporada"), "Motores por piloto na temporada", "int",
              "Cota. Vazio = sem cota (troca livre quando o motor chega ao fim da vida útil).", minimo=1),
            F(("regras", "penalidade_motor_grid"), "Punição por motor além da cota", "int",
              "Posições perdidas no grid. Padrão 10.", minimo=0),
            F(("regras", "lastro_por_posicao"), "Lastro de sucesso (kg)", "lista_num",
              "Por posição no campeonato: 1º, 2º, ... (ex.: 54, 45, 39). Vazio = sem lastro."),
            F(("regras", "lastro_tempo_por_kg"), "Tempo por kg de lastro", "real",
              "Fração do tempo de volta por kg. Padrão 0,00007 (≈ 0,06 s a cada 10 kg numa volta de 90 s).",
              minimo=0),
            F(("regras", "bandeira_vermelha", "relogio_durante_suspensao"), "Bandeira vermelha (oval com chuva): relógio",
              "escolha", "Parado: a espera não tira tempo de pista nem conta para o tempo máximo da corrida. "
                         "Corre: a espera conta.", [("parado", "parado"), ("corre", "corre")]),
            F(("regras", "bandeira_vermelha", "limite_espera_sessao_min"), "Limite de espera – treinos/classificação (min)",
              "int", "Passou sem secar: a sessão é encerrada e valem os tempos feitos. 0 = sem limite. Padrão 60.",
              minimo=0),
            F(("regras", "bandeira_vermelha", "limite_espera_corrida_min"), "Limite de espera – corrida (min)", "int",
              "Passou sem secar: a corrida termina na volta da bandeira vermelha (se nem largou, é cancelada e ninguém "
              "pontua). 0 = sem limite. Padrão 120.", minimo=0),
            F(("regras", "batida_grave", "prob_por_volta"), "Batida grave: chance por volta (corrida)", "real",
              "Vários carros abandonam juntos. × 3 na 1ª volta, × acidentes do clima, × dificuldade. Padrão 0,0015.",
              minimo=0, maximo=1),
            F(("regras", "batida_grave", "fator_treinos"), "Batida grave: fator em treinos/classificação", "real",
              "Padrão 0,5.", minimo=0),
            F(("regras", "batida_grave", "carros_min"), "Batida grave: mínimo de carros", "int", "Padrão 2.", minimo=2),
            F(("regras", "batida_grave", "carros_max"), "Batida grave: máximo de carros", "int", "Padrão 5.", minimo=2),
            F(("regras", "batida_grave", "prob_encerrar_sessao"), "Batida grave: chance de encerrar a sessão", "real",
              "Senão, bandeira vermelha e relargada. Padrão 0,2.", minimo=0, maximo=1),
            F(("regras", "batida_grave", "prob_lesao"), "Batida grave: chance de lesão (por piloto)", "real",
              "Padrão 0,06.", minimo=0, maximo=1),
            F(("regras", "batida_grave", "prob_morte"), "Batida grave: chance de morte (por piloto)", "real",
              "Padrão 0,002.", minimo=0, maximo=1),
            F(("regras", "batida_grave", "lesao_corridas"), "Lesão: corridas fora (mín., máx.)", "lista_num",
              "Ex.: 1, 6.") ,
            F(("regras", "batida_grave", "lesao_perda_atributos"), "Lesão: perda por atributo (mín., máx.)", "lista_num",
              "Pontos perdidos em físico, concentração e condução. Ex.: 1, 6."),
            F(("regras", "negociacao_partes", "ativa"), "Negociação de chassis e motor", "bool",
              "Desligado (padrão): preço de tabela. Ligado: o fornecedor pede um valor escondido (tabela ± variação) "
              "e responde às ofertas na semana seguinte."),
            F(("regras", "negociacao_partes", "variacao"), "Negociação: variação do preço pedido", "real",
              "Fração do preço de tabela. Padrão 0,15 (±15%).", minimo=0, maximo=0.9),
            F(("regras", "evolucao_fornecedores", "ativa"), "Peças de fornecedor mudam a cada temporada", "bool",
              "Chassis e motores que nenhuma equipe desenvolve. Padrão ligado."),
            F(("regras", "evolucao_fornecedores", "variacao_anual"), "Fornecedores: atualização anual (± pontos)", "int",
              "Padrão 2.", minimo=0),
            F(("regras", "evolucao_fornecedores", "prob_novo_modelo"), "Fornecedores: chance de modelo novo", "real",
              "Por temporada. Padrão 0,25 (≈ 1 a cada 4 anos).", minimo=0, maximo=1),
            F(("regras", "evolucao_fornecedores", "novo_modelo"), "Fornecedores: modelo novo (mín., máx. pontos)",
              "lista_num", "Padrão -3, 8."),
            F(("regras", "evolucao_fornecedores", "reversao"), "Fornecedores: volta ao nível da database", "real",
              "Fração da distância até o nível inicial, por temporada. Padrão 0,2.", minimo=0, maximo=1)])
        self._form("Regulamento", [
            F(("regulamento", "ativo"), "Mudanças de regulamento", "bool",
              "Anunciadas no meio da temporada para a seguinte. Padrão desligado (temporadas importadas)."),
            F(("regulamento", "semana_anuncio"), "Semana do anúncio", "int", "Padrão 30.", minimo=1, maximo=52),
            F(("regulamento", "prob_grande_mudanca"), "Grande mudança: chance por temporada", "real",
              "Padrão 0,2 (F1: ~1 a cada 4 anos).", minimo=0, maximo=1),
            F(("regulamento", "perda_grande_mudanca"), "Grande mudança: perda extra do chassis (mín., máx.)", "lista_num",
              "Fração somada à perda da manutenção. Padrão 0,15, 0,30."),
            F(("regulamento", "aumento_importancia_carro"), "Grande mudança: aumento da importância do carro",
              "lista_num", "Mín., máx. Padrão 0,05, 0,10."),
            F(("regulamento", "convergencia_por_temporada"), "Volta da importância do carro por temporada", "real",
              "Sem grande mudança, a importância do carro volta ao valor da database. Padrão 0,02.", minimo=0),
            F(("regulamento", "prob_limite_desenvolvimento"), "Limite de desenvolvimento: chance por temporada", "real",
              "Uma parte (chassis ou motor) que as equipes desenvolvem. Padrão 0,15.", minimo=0, maximo=1),
            F(("regulamento", "limite_duracao"), "Limite: duração em temporadas (mín., máx.)", "lista_num",
              "Padrão 2, 4."),
            F(("regulamento", "prob_congelamento"), "Limite: chance de ser congelamento", "real",
              "Senão, pontos por atributo por temporada. Padrão 0,5.", minimo=0, maximo=1),
            F(("regulamento", "limite_pontos_por_temporada"), "Limite: pontos por atributo (mín., máx.)", "lista_num",
              "Padrão 2, 5."),
            F(("regulamento", "prob_ajuste_importancia"), "Ajuste da importância do carro: chance", "real",
              "Padrão 0,15.", minimo=0, maximo=1),
            F(("regulamento", "ajuste_importancia"), "Ajuste da importância do carro (±)", "real", "Padrão 0,03.",
              minimo=0),
            F(("regulamento", "importancia_carro_min"), "Importância do carro: mínima", "real", "Padrão 0,3.",
              minimo=0, maximo=1),
            F(("regulamento", "importancia_carro_max"), "Importância do carro: máxima", "real", "Padrão 0,8.",
              minimo=0, maximo=1),
            F(("evolucao_tempo_base", "ativa"), "Tempo base das pistas evolui por ano", "bool",
              "Padrão ligado. Anos com tempos informados na pista usam esses tempos."),
            F(("evolucao_tempo_base", "ganho_por_temporada"), "Tempo base: queda por temporada (regras estáveis)",
              "real", "Fração. Padrão 0,012 (−1,2%; F1: 1 a 2% por ano).", minimo=0, maximo=0.2),
            F(("evolucao_tempo_base", "grande_mudanca"), "Tempo base: aumento na grande mudança", "real",
              "Fração. Padrão 0,03 (+3%; o chassis mais fraco já soma ~0,5%).", minimo=0, maximo=0.5),
            F(("evolucao_tempo_base", "ganho_sem_regulamento"), "Tempo base: queda por temporada sem regulamento",
              "real", "Com as mudanças de regulamento desligadas. Padrão 0,002 (−0,2%, média de longo prazo da F1).",
              minimo=0, maximo=0.2)])
        self._form("Pontuação e pit stop", [
            F(("pontuacao", "posicoes"), "Pontos por posição", "lista_num", "1º, 2º, 3º... separados por vírgula."),
            F(("pontuacao", "volta_mais_rapida"), "Volta mais rápida", "int", minimo=0),
            F(("pontuacao", "pole"), "Pole position", "int", minimo=0),
            F(("pontuacao", "corrida_interrompida", "distancia_minima"), "Corrida interrompida: distância p/ pontos integrais",
              "real", "Fração das voltas (ex.: 0,5). Abaixo dela, pontuação parcial. Sem volta completa, ninguém pontua.",
              minimo=0, maximo=1),
            F(("pontuacao", "corrida_interrompida", "pontos_parciais"), "Corrida interrompida: pontuação parcial",
              "escolha", "Metade dos pontos ou proporcional à distância completada.",
              [("metade", "metade"), ("proporcional", "proporcional")]),
            F(("regras_pitstop", "obrigatorio"), "Parada obrigatória", "bool",
              "Sem penalidade de tempo: quem não para sofre com pneu/combustível."),
            F(("regras_pitstop", "paradas_minimas"), "Paradas mínimas", "int", minimo=0),
            F(("regras_pitstop", "reabastecimento"), "Reabastecimento", "bool"),
            F(("regras_pitstop", "troca_de_pneus"), "Troca de pneus", "bool"),
            F(("regras_pitstop", "dois_compostos_secos"), "Obrigatório usar dois compostos secos", "bool",
              "Corrida seca: cada carro usa pelo menos 2 compostos secos diferentes. Quem usou pneu de chuva fica "
              "dispensado."),
            F(("regras_pitstop", "penalidade_dois_compostos_s"), "Penalidade (dois compostos) em segundos", "int",
              "0 = desclassificação.", minimo=0),
            F(("regras_pitstop", "segundos_por_volta_de_combustivel"), "Segundos por volta de combustível", "real",
              minimo=0)])
        # pneus
        fp = tk.Frame(self, padx=6, pady=6)
        tk.Label(fp, text="Compostos (degradação por composto; pista e carro multiplicam a degradação e "
                          "dividem a vida)", anchor="w").pack(fill="x")
        self.t_comp = TabelaEditavel(fp, lambda: obter(self.ed.dados, ("categoria", "pneus", "compostos")),
                                     [(("nome",), "Nome", 110), (("tipo",), "Tipo", 80), (("ritmo",), "Ritmo", 60),
                                      (("degradacao",), "Degr.", 60), (("vida",), "Vida", 50)],
                                     self.COMPOSTO, modo="dicionario", rotulo_chave="ID", ao_mudar=self._mod,
                                     novo=lambda: {"nome": "Novo", "tipo": "seco", "ritmo": 1.0, "degradacao": 0.0006,
                                                   "vida": 25, "cliff": 0.004, "aquecimento_voltas": 1,
                                                   "sensibilidade_termica": 1.0}, altura=6)
        self.t_comp.pack(fill="x")
        self.f_pneus = FormGenerico(fp, [
            F(("pneus", "compostos_disponiveis"), "Compostos disponíveis", "lista_ref",
              "Marque os compostos usados nesta categoria.",
              lambda: [(k, v.get("nome", k)) for k, v in (
                  obter(self.ed.dados, ("categoria", "pneus", "compostos")) or {}).items()]),
            F(("pneus", "penalidade_aquecimento"), "Penalidade de aquecimento", "real", minimo=0),
            F(("pneus", "desgaste_critico"), "Desgaste crítico (%)", "real", "Acima disso o pneu pode furar."),
            F(("pneus", "desgaste_quebra"), "Desgaste de quebra (%)", "real", "Acima disso o furo tende a abandono.")],
            ao_mudar=self._mod_form, rolagem=False)
        self.f_pneus.pack(fill="x", pady=(6, 0))
        self.add(fp, text="Pneus")
        # clima
        fc = tk.Frame(self, padx=6, pady=6)
        self.t_clima = TabelaEditavel(fc, lambda: obter(self.ed.dados, ("categoria", "clima", "efeitos")),
                                      [(("tempo",), "Tempo", 60), (("peso_motor",), "Motor", 60),
                                       (("acidentes",), "Acidentes", 70)], self.EFEITO, modo="dicionario",
                                      rotulo_chave="Clima", ao_mudar=self._mod, altura=3)
        self.t_clima.pack(fill="x")
        self.f_clima = FormGenerico(fc, [
            F(("clima", "proporcao_chuva_forte"), "Proporção de chuva forte", "real", minimo=0, maximo=1),
            F(("clima", "estabilidade_por_10min"), "Estabilidade (por 10 min)", "real",
              "Chance de o clima não tentar mudar a cada 10 minutos. Não altera quanto chove: isso é o prob_chuva de cada pista.", minimo=0, maximo=1)], ao_mudar=self._mod_form,
            rolagem=False)
        self.f_clima.pack(fill="x", pady=(6, 0))
        self.add(fc, text="Clima")
        # formato do evento
        fe = tk.Frame(self, padx=6, pady=4)
        nb = ttk.Notebook(fe)
        nb.pack(fill="both", expand=True)
        f1 = tk.Frame(nb, padx=4, pady=4)
        self.t_treinos = TabelaEditavel(f1, lambda: obter(self.ed.dados, ("categoria", "formato_evento",
                                                                          "treinos_livres")),
                                        [(("nome",), "Nome", 150), (("limite",), "Limite", 70), (("valor",), "Valor", 50)],
                                        self.TREINO, ao_mudar=self._mod,
                                        novo=lambda: {"nome": "Treino livre", "limite": "tempo", "valor": 60})
        self.t_treinos.pack(fill="x")
        nb.add(f1, text="Treinos livres")
        f2 = tk.Frame(nb, padx=4, pady=4)
        tk.Label(f2, text="Etapas da classificação (na ordem). O grid sai da última etapa.", anchor="w").pack(fill="x")
        self.t_etapas = TabelaEditavel(f2, self._etapas, [(("nome",), "Nome", 140), (("modelo",), "Modelo", 140)],
                                       self.ETAPA, ao_mudar=self._etapa_mudou,
                                       novo=lambda: {"nome": "Classificação", "modelo": "tempo", "limite": "tempo",
                                                     "valor": 30}, altura=4)
        self.t_etapas.pack(fill="x")
        tk.Label(f2, text="Fases da etapa selecionada (modelo 'tempo'):", anchor="w").pack(fill="x", pady=(6, 0))
        self.t_fases = TabelaEditavel(f2, self._fases, [(("nome",), "Nome", 100), (("limite",), "Limite", 60),
                                                        (("valor",), "Valor", 50), (("eliminados",), "Elim.", 50)],
                                      self.FASE, ao_mudar=self._mod, altura=3,
                                      novo=lambda: {"nome": "Q", "limite": "tempo", "valor": 15, "eliminados": 0})
        self.t_fases.pack(fill="x")
        self.t_etapas.tv.bind("<<TreeviewSelect>>", lambda e: (self.t_etapas._selecionar(), self.t_fases.recarregar()),
                              add="+")
        nb.add(f2, text="Classificação")
        f3 = tk.Frame(nb, padx=4, pady=4)
        self.f_corrida = FormGenerico(f3, [
            F(("formato_evento", "corrida", "nome"), "Nome"),
            F(("formato_evento", "corrida", "tempo_maximo_min"), "Tempo máximo (min)", "int", "0 = sem limite.",
              minimo=0),
            F(("formato_evento", "corrida", "grid_invertido_top"), "Inverter os N primeiros do grid", "int",
              "0 = grid normal.", minimo=0)], ao_mudar=self._mod_form, rolagem=False)
        self.f_corrida.pack(fill="x")
        nb.add(f3, text="Corrida")
        self.add(fe, text="Formato do evento")
        self._form("Desenvolvimento", [
            F("desenvolvimento", "Desenvolvimento por equipe", "grupo", "Desmarque se a categoria não tem."),
            F(("desenvolvimento", "perda_manutencao"), "Perda na manutenção", "real",
              "Fração perdida em cada atributo ao manter o carro (ex.: 0,30).", grupo="desenvolvimento", minimo=0,
              maximo=1),
            F(("desenvolvimento", "calibracao_automatica"), "Calibração automática dos custos", "bool",
              "Padrão ligado: o jogo ajusta o custo por ponto para que chassis e motores fiquem, em média, no nível "
              "da database ao longo das temporadas.", grupo="desenvolvimento"),
            F(("desenvolvimento", "chassis", "custo_por_ponto"), "Chassis: custo por ponto", "real",
              grupo="desenvolvimento", minimo=0),
            F(("desenvolvimento", "chassis", "limite_custo_fixo"), "Chassis: custo fixo até", "int",
              "Acima deste nível o ponto fica progressivamente mais caro.", grupo="desenvolvimento"),
            F(("desenvolvimento", "chassis", "escala_progressiva"), "Chassis: escala progressiva", "real",
              "Menor = encarece mais rápido.", grupo="desenvolvimento", minimo=1),
            F(("desenvolvimento", "motor", "custo_por_ponto"), "Motor: custo por ponto", "real",
              grupo="desenvolvimento", minimo=0),
            F(("desenvolvimento", "motor", "limite_custo_fixo"), "Motor: custo fixo até", "int", grupo="desenvolvimento"),
            F(("desenvolvimento", "motor", "escala_progressiva"), "Motor: escala progressiva", "real",
              grupo="desenvolvimento", minimo=1),
            F("desenvolvimento_inicial", "Investimento inicial (equipe criada)", "grupo"),
            F(("desenvolvimento_inicial", "chassis", "custo_por_ponto"), "Inicial: chassis por ponto", "real",
              grupo="desenvolvimento_inicial"),
            F(("desenvolvimento_inicial", "chassis", "atributo_base"), "Inicial: chassis base", "int",
              grupo="desenvolvimento_inicial"),
            F(("desenvolvimento_inicial", "chassis", "atributo_maximo"), "Inicial: chassis máximo", "int",
              grupo="desenvolvimento_inicial"),
            F(("desenvolvimento_inicial", "motor", "custo_por_ponto"), "Inicial: motor por ponto", "real",
              grupo="desenvolvimento_inicial"),
            F(("desenvolvimento_inicial", "motor", "atributo_base"), "Inicial: motor base", "int",
              grupo="desenvolvimento_inicial"),
            F(("desenvolvimento_inicial", "motor", "atributo_maximo"), "Inicial: motor máximo", "int",
              grupo="desenvolvimento_inicial")])
        fm = tk.Frame(self)
        self.f_merc = FormGenerico(fm, [
            F(("simulacao", "mercado_pilotos", "salario_minimo_por_corrida"), "Salário mínimo por corrida", "real"),
            F(("simulacao", "mercado_pilotos", "salario_maximo_por_corrida"), "Salário máximo por corrida", "real"),
            F(("simulacao", "mercado_pilotos", "fracao_orcamento_pilotos"), "Fração do caixa para pilotos", "real"),
            F(("simulacao", "mercado_pilotos", "peso_salario_na_escolha"), "Peso do salário na escolha", "real",
              "Piloto escolhe por salário + perspectivas da equipe."),
            F(("simulacao", "mercado_pilotos", "peso_perspectiva_na_escolha"), "Peso das perspectivas", "real"),
            F(("simulacao", "mercado_pilotos", "semana_inicio_propostas"), "Semana de início das propostas", "int",
              minimo=1, maximo=52),
            F(("contratos", "fator_multa"), "Fator da multa", "real",
              "Multa = fator × valor por corrida × corridas restantes."),
            F(("mercado_patrocinio", "prob_busca_semanal"), "Patrocínio: chance de busca/semana", "real"),
            F(("mercado_patrocinio", "peso_desempenho"), "Patrocínio: peso do desempenho", "real"),
            F(("mercado_patrocinio", "validade_oferta_semanas"), "Patrocínio: validade da oferta", "int"),
            F(("financas", "reserva_minima"), "Reserva mínima (fração do orçamento)", "real"),
            F(("financas", "uso_do_excedente"), "Uso do excedente de caixa", "real"),
            F(("financas", "juros_anual"), "Juros dos empréstimos (ao ano)", "real"),
            F(("financas", "limite_emprestimo"), "Limite de empréstimo", "real",
              "× orçamento médio × (0,5 + recursos/100)."),
            F(("financas", "prazo_temporadas"), "Prazo padrão (temporadas)", "int", minimo=1),
            F(("financas", "semanas_para_falencia"), "Semanas até a falência", "int", minimo=1)],
            ao_mudar=self._mod_form)
        self.f_merc.pack(fill="both", expand=True)
        tk.Label(fm, text="Equipes que podem surgir (ano vazio = por sorteio):", anchor="w").pack(fill="x")
        self.t_novas = TabelaEditavel(fm, lambda: self._lista_cat("novas_equipes"),
                                      [(("equipe",), "Equipe", 150), (("ano",), "Ano", 60)],
                                      [F("equipe", "Equipe", "ref", "", lambda: [(e["id"], e["nome"]) for e in
                                                                                (self.ed.dados or {}).get("equipes", [])]),
                                       F("ano", "Ano", "int")], ao_mudar=self._mod, altura=3,
                                      novo=lambda: {"equipe": None, "ano": None})
        self.t_novas.pack(fill="x")
        self.add(fm, text="Mercado e economia")
        # ponderação
        fpd = tk.Frame(self, padx=4, pady=4)
        tk.Label(fpd, text="Peso de cada atributo em cada característica da pista (células vazias = 0).",
                 anchor="w").pack(fill="x")
        nb2 = ttk.Notebook(fpd)
        nb2.pack(fill="both", expand=True)
        carac = ["retas", "curvas_alta", "curvas_baixa", "desgaste", "dificuldade", "chuva", "sessao_treino",
                 "sessao_classificacao", "sessao_corrida"]
        rot_c = {"retas": "Retas", "curvas_alta": "Curvas de alta", "curvas_baixa": "Curvas de baixa",
                 "desgaste": "Desgaste", "dificuldade": "Dificuldade", "chuva": "Chuva", "sessao_treino": "Treino",
                 "sessao_classificacao": "Classificação", "sessao_corrida": "Corrida"}
        self.matrizes = []
        for bloco, atrs in (("piloto", ATRIBUTOS_PILOTO), ("chassis", ATRIBUTOS_CHASSIS), ("motor", ["potencia"])):
            m = MatrizEditavel(nb2, lambda b=bloco: obter(self.ed.dados, ("categoria", "ponderacao", b)), carac, atrs,
                               rot_c, {a: NOMES_ATRIBUTOS[a] for a in atrs}, ao_mudar=self._mod)
            nb2.add(m, text=bloco.capitalize())
            self.matrizes.append(m)
        m = MatrizEditavel(nb2, self._pesos_gerais, ["peso_caracteristicas", "importancia_motor_por_caracteristica"],
                           ["retas", "curvas_alta", "curvas_baixa", "desgaste", "dificuldade", "chuva", "sessao"],
                           {"peso_caracteristicas": "Peso da característica",
                            "importancia_motor_por_caracteristica": "Importância do motor"}, ao_mudar=self._mod)
        nb2.add(m, text="Pesos gerais")
        self.matrizes.append(m)
        self.add(fpd, text="Ponderação")
        self._form("Mapa da pista", [
            F(("mapa_pista", "criterio"), "Critério padrão", "escolha",
              "Calendário > 'Calcular retas e curvas pelo mapa': como classificar cada trecho da volta.",
              [("raio", "pelo raio da curva (m)"), ("velocidade", "pela velocidade estimada (km/h)")]),
            F(("mapa_pista", "criterio_oval"), "Critério padrão em ovais", "escolha",
              "Pistas do tipo oval. Pela velocidade: as curvas de um superspeedway (raio ~300 m) contam como reta, "
              "e ele vira superspeedway no jogo. Padrão: pela velocidade.",
              [("velocidade", "pela velocidade estimada (km/h)"), ("raio", "pelo raio da curva (m)")]),
            F(("mapa_pista", "raio_reta"), "Reta: raio a partir de (m)", "int", "Padrão 400.", minimo=1),
            F(("mapa_pista", "raio_baixa"), "Curva de baixa: raio abaixo de (m)", "int",
              "Padrão 80. Entre os dois = curva de alta.", minimo=1),
            F(("mapa_pista", "vel_reta"), "Reta: velocidade a partir de (km/h)", "int", "Padrão 250.", minimo=1),
            F(("mapa_pista", "vel_baixa"), "Curva de baixa: abaixo de (km/h)", "int", "Padrão 150.", minimo=1),
            F(("mapa_pista", "aderencia"), "Aderência em curva (g)", "real",
              "Converte raio em velocidade: v = raiz(aderência × g × raio). Padrão 2,0 (carro com asas).",
              minimo=0.5, maximo=6)])
        self._form("Simulação", [F(("simulacao",) + (k if isinstance(k, tuple) else (k,)), r, "real", a) for k, r, a in (
            ("amplitude_desempenho", "Amplitude de desempenho", "Diferença máxima de tempo entre nota 0 e 100."),
            ("dispersao_consistencia", "Dispersão por consistência",
             "Só piora a volta: k × (1,5 − 0,316·√(consistência/5)) × acaso. Padrão 0,006."),
            ("forma_sigma", "Variação da forma por evento", "Padrão 0,0015 (≈ 0,13 s numa volta de 90 s)."),
            ("penalidade_chuva", "Penalidade cúbica na chuva", "Piloto + carro ruins no molhado. Padrão 0,0035."),
            ("evolucao_pista", "Evolução da pista", "Ganho total da pista verde à emborrachada. Padrão 0,012."),
            ("voltas_emborrachamento", "Voltas para emborrachar (por carro)", "Padrão 15. A chuva lava parte."),
            ("aprendizado_por_volta", "Aprendizado por volta", ""),
            ("penalidade_maxima_acerto", "Penalidade máxima do acerto", "Limita voltas irreais por acerto ruim."),
            ("reducao_maxima_acerto_piloto", "Redução pelo atributo 'acerto'", ""),
            ("efeito_combustivel_por_volta", "Efeito do combustível por volta", ""),
            ("taxa_erro_volta", "Taxa de erro por volta", ""), ("taxa_acidente_base", "Taxa de acidente", ""),
            ("taxa_quebra_base", "Taxa de quebra", ""), ("ultrapassagem_base", "Ultrapassagem base", ""),
            ("risco_colisao_disputa", "Risco de colisão na disputa", ""),
            ("distancia_minima_s", "Distância mínima entre carros (s)", ""),
            ("fator_erro_classificacao", "Erros na classificação (fator)", "Padrão 0,5."),
            ("trafego_volta_rapida", "Tráfego na volta rápida", "Chance com 10 carros na pista. Padrão 0,05."),
            ("limites_pista", "Volta apagada (limites da pista)", "Padrão 0,012."),
            ("ar_sujo", "Ar sujo", "Perda atrás de outro carro (fração, mais nas curvas de alta). Padrão 0,01."),
            ("fator_ultrapassagem_rua", "Ultrapassagem em pista de rua (fator)", "Padrão 0,6."),
            ("ultrapassagem_retas_referencia", "Retas de referência p/ ultrapassagem",
             "Proporção de retas em que o fator da pista é 1. Padrão 0,4."),
            ("ultrapassagem_expoente_retas", "Expoente das retas na ultrapassagem",
             "Fator da pista = (retas / referência)^expoente. Padrão 2."),
            ("ultrapassagem_sensibilidade_ritmo", "Ultrapassagem: peso da diferença de ritmo",
             "Com o mesmo ritmo quase não se passa. Padrão 1,2."),
            ("ultrapassagem_expoente_ritmo", "Ultrapassagem: expoente da diferença de ritmo",
             "2 = diferença pequena quase nunca basta, grande (pneu novo, carro melhor) sim. Padrão 2."),
            ("variacao_estrategia_s", "Variação de estratégia das equipes (s)",
             "0 = todas seguem a ótima. Equipes com mais recursos variam menos. Padrão 6."),
            ("variacao_stint", "Variação do tamanho dos stints", "Fração. Padrão 0,1."),
            (("oval", "vacuo"), "Oval: ganho no vácuo", "Fração do tempo de volta colado no carro da frente. Padrão 0,012."),
            (("oval", "compressao_pelotao"), "Oval: compressão do pelotão",
             "0 a 1: quanto o pelotão do superspeedway aproxima o ritmo dos carros. Padrão 0,6."),
            (("oval", "piso_ultrapassagem_pelotao"), "Oval: facilidade de passar no pelotão", "Padrão 0,4."),
            (("oval", "multiplicador_batida_pelotao"), "Oval: risco de 'Big One' no pelotão", "Padrão 6."),
            (("oval", "amarelas_detritos_por_corrida"), "Oval: amarelas por detritos (por corrida)",
             "Média por corrida, além das batidas. Padrão 6."),
            (("oval", "alcance_relargada_s"), "Oval: alcance na relargada (s)",
             "Relargada em fila dupla: disputa quem está até essa distância do carro da frente. Padrão 0,8."),
            (("oval", "colisao_oval_curto"), "Oval curto: multiplicador de contato", "Padrão 2,5."),
            (("oval", "amarelas_oval_curto"), "Oval curto: multiplicador de amarelas por detritos",
             "No oval curto pleno (50% de curvas de baixa). Padrão 2."),
            (("oval", "ultrapassagem_oval_curto"), "Oval curto: chance de ultrapassagem",
             "Multiplicador no oval curto pleno (pista estreita). Padrão 0,7."),
            ("dano_para_reparo", "Dano que leva ao box", "Fração do tempo de volta. Padrão 0,006."),
            ("prob_sc_acidente", "Safety car após acidente (chance)", "Pista de rua × 1,35. Padrão 0,45."),
            ("fracao_sc", "Safety car x VSC", "Fração de safety car (o resto é VSC). Padrão 0,65."),
            ("prob_vsc_quebra", "VSC após quebra (chance)", "Padrão 0,3."),
            ("ritmo_sc", "Ritmo sob safety car", "Multiplicador do tempo de volta. Padrão 1,4."),
            ("ritmo_vsc", "Ritmo sob VSC", "Padrão 1,35."),
            ("pit_sob_sc", "Pit stop sob safety car", "Fração do tempo normal da parada. Padrão 0,55."),
            ("pit_sob_vsc", "Pit stop sob VSC", "Padrão 0,7."),
            ("vida_motor_voltas", "Vida do motor (voltas)", "0 = sem desgaste de motor. Padrão 700."),
            ("perda_potencia_motor", "Perda de potência no fim da vida", "Pontos de potência. Padrão 3."),
            ("intervalo_grid_s", "Intervalo no grid (s)", ""))])
        self.arvore = ArvoreJSON(self, editor)
        self.add(self.arvore, text="Avançado (árvore)")

    # ------------------------------------------------------------------ auxiliares
    def _form(self, titulo, campos):
        f = FormGenerico(self, [dict(c, c=("categoria",) + c["c"]) if c["g"] is None else
                                dict(c, c=("categoria",) + c["c"], g=("categoria",) + tuple(c["g"])) for c in campos],
                         ao_mudar=self._mod_form)
        self.add(f, text=titulo)
        self.paineis.append(f)

    def _lista_cat(self, chave):
        cat = obter(self.ed.dados, ("categoria",))
        return cat.setdefault(chave, []) if cat is not None else None

    def _etapas(self):
        fmt = obter(self.ed.dados, ("categoria", "formato_evento"))
        if fmt is None:
            return None
        cl = fmt.get("classificacao")
        if isinstance(cl, dict):
            fmt["classificacao"] = [cl]
        elif cl is None:
            fmt["classificacao"] = []
        return fmt["classificacao"]

    def _fases(self):
        et = self._etapas()
        if not et or self.t_etapas.atual is None or int(self.t_etapas.atual) >= len(et):
            return None
        e = et[int(self.t_etapas.atual)]
        if e.get("modelo", "tempo") != "tempo":
            return None
        return e.setdefault("fases", [])

    def _etapa_mudou(self):
        self._mod()
        self.t_fases.recarregar()

    def _pesos_gerais(self):
        p = obter(self.ed.dados, ("categoria", "ponderacao"))
        return p

    def _mod(self):
        self.ed.modificado(True)

    def _mod_form(self):
        for f in self.paineis + [self.f_pneus, self.f_clima, self.f_corrida, self.f_merc]:
            f.salvar()
        self.ed.modificado(True)

    def recarregar(self):
        for f in self.paineis + [self.f_pneus, self.f_clima, self.f_corrida, self.f_merc]:
            f.carregar(self.ed.dados if f in self.paineis else self.ed.dados.get("categoria"))
        for t in (self.t_comp, self.t_clima, self.t_treinos, self.t_etapas, self.t_novas):
            t.recarregar()
        self.t_fases.recarregar()
        for m in self.matrizes:
            m.recarregar()
        self.arvore.recarregar()

    def confirmar(self):
        for f in self.paineis:
            f.salvar()
        cat = self.ed.dados.get("categoria")
        for f in (self.f_pneus, self.f_clima, self.f_corrida, self.f_merc):
            if f.item is cat:
                f.salvar()


# ====================================================================== árvore (modo avançado)
class ArvoreJSON(tk.Frame):
    def __init__(self, master, editor):
        super().__init__(master, padx=4, pady=4)
        self.editor = editor
        tk.Label(self, text="Modo avançado: todas as definições da categoria. Clique duas vezes num valor para "
                            "editar (número, true/false, null, texto ou JSON).", anchor="w").pack(fill="x")
        fr = tk.Frame(self)
        fr.pack(fill="both", expand=True)
        self.tv = ttk.Treeview(fr, columns=("valor",), show="tree headings")
        self.tv.heading("#0", text="Campo")
        self.tv.heading("valor", text="Valor")
        self.tv.column("#0", width=360)
        self.tv.column("valor", width=420)
        sb = ttk.Scrollbar(fr, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tv.bind("<Double-1>", lambda e: self.editar())
        b = tk.Frame(self)
        b.pack(fill="x", pady=4)
        w.Botao(b, "Editar valor", self.editar).pack(side="left")
        w.Botao(b, "Adicionar campo/item", self.adicionar).pack(side="left", padx=4)
        w.Botao(b, "Remover", self.remover).pack(side="left")
        self.caminhos = {}

    def recarregar(self):
        abertos = {self.caminhos[i] for i in self.caminhos if self.tv.exists(i) and self.tv.item(i, "open")}
        self.tv.delete(*self.tv.get_children())
        self.caminhos = {}
        self._inserir("", "categoria", self.editor.dados.get("categoria", {}), ("categoria",), abertos)

    def _inserir(self, pai, nome, valor, caminho, abertos):
        if isinstance(valor, (dict, list)):
            resumo = f"{{{len(valor)} campos}}" if isinstance(valor, dict) else f"[{len(valor)} itens]"
            if isinstance(valor, list) and all(not isinstance(x, (dict, list)) for x in valor):
                resumo = json.dumps(valor, ensure_ascii=False)
            iid = self.tv.insert(pai, "end", text=str(nome), values=(resumo,), open=caminho in abertos or pai == "")
            self.caminhos[iid] = caminho
            itens = valor.items() if isinstance(valor, dict) else enumerate(valor)
            for k, v in itens:
                self._inserir(iid, k, v, caminho + (k,), abertos)
        else:
            iid = self.tv.insert(pai, "end", text=str(nome), values=(json.dumps(valor, ensure_ascii=False),))
            self.caminhos[iid] = caminho

    def _obj(self, caminho):
        d = self.editor.dados
        for k in caminho:
            d = d[k]
        return d

    @staticmethod
    def _parse(txt):
        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            return txt

    def editar(self):
        sel = self.tv.selection()
        if not sel:
            return
        cam = self.caminhos[sel[0]]
        txt = simpledialog.askstring("Editar valor", f"{'.'.join(map(str, cam))}:",
                                     initialvalue=json.dumps(self._obj(cam), ensure_ascii=False), parent=self)
        if txt is None:
            return
        self._obj(cam[:-1])[cam[-1]] = self._parse(txt)
        self.editor.modificado(True)
        self.recarregar()

    def adicionar(self):
        sel = self.tv.selection()
        cam = self.caminhos[sel[0]] if sel else ("categoria",)
        alvo = self._obj(cam)
        if not isinstance(alvo, (dict, list)):
            cam = cam[:-1]
            alvo = self._obj(cam)
        if isinstance(alvo, dict):
            chave = simpledialog.askstring("Novo campo", "Nome do campo:", parent=self)
            if not chave:
                return
            txt = simpledialog.askstring("Novo campo", "Valor:", initialvalue="0", parent=self)
            if txt is None:
                return
            alvo[chave] = self._parse(txt)
        else:
            txt = simpledialog.askstring("Novo item", "Valor:", initialvalue="0", parent=self)
            if txt is None:
                return
            alvo.append(self._parse(txt))
        self.editor.modificado(True)
        self.recarregar()

    def remover(self):
        sel = self.tv.selection()
        if not sel:
            return
        cam = self.caminhos[sel[0]]
        if len(cam) <= 1 or not messagebox.askyesno("Remover", f"Remover '{'.'.join(map(str, cam))}'?", parent=self):
            return
        del self._obj(cam[:-1])[cam[-1]]
        self.editor.modificado(True)
        self.recarregar()


# ====================================================================== janela principal do editor
TIPO_ERRO = {"piloto": "pilotos", "chassis": "chassis", "motor": "motores", "equipe": "equipes",
             "patrocinador": "patrocinadores", "calendário": "calendario"}


class JanelaEditor(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master, bg=w.CINZA)
        self.title("AutoManager – Editor da database")
        w.centralizar(self, 1180, 720)
        self.dados = None
        self.caminho = None
        self._mod = False
        self.erros_por_item = {}
        self.esq = Esquemas(self)
        barra = tk.Frame(self, relief="raised", bd=1)
        barra.pack(fill="x")
        for txt, cmd in (("Novo...", self.novo), ("Abrir...", self.abrir), ("Salvar", self.salvar),
                         ("Salvar como...", lambda: self.salvar(como=True)),
                         ("Duplicar p/ outro ano...", self.duplicar_ano), ("Validar", self.validar),
                         ("Importar da Wikipedia...", self.importar),
                         ("Buscar imagens...", self.buscar_imagens),
                         ("Imagens de pasta...", self.imagens_de_pasta)):
            w.Botao(barra, txt, cmd, padx=6).pack(side="left", padx=1, pady=2)
        self.status = w.BarraStatus(self)
        self.status.pack(fill="x", side="bottom")
        self.st_arq = self.status.campo("", expandir=True)
        self.st_mod = self.status.campo("", 14)
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=4, pady=4)
        self.aba_cat = AbaCategoria(self.nb, self)
        self.nb.add(self.aba_cat, text="Categoria")
        campos = {"pilotos": self.esq.pilotos(), "chassis": self.esq.chassis_campos(),
                  "motores": self.esq.motores_campos(), "equipes": self.esq.equipes_campos(),
                  "patrocinadores": self.esq.patrocinadores_campos(), "calendario": self.esq.calendario_campos()}
        self.abas = {}
        for chave, nome in ABAS:
            a = AbaEntidades(self.nb, self, chave, campos[chave])
            self.nb.add(a, text=nome)
            self.abas[chave] = a
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self._trocou_aba())
        self.protocol("WM_DELETE_WINDOW", self.fechar)
        self._habilitar(False)
        self.st_arq.configure(text="Nenhum arquivo aberto. Use Novo, Abrir ou Importar da Wikipedia.")

    # ------------------------------------------------------------ estado
    def _habilitar(self, sim):
        for i in range(len(self.nb.tabs())):
            self.nb.tab(i, state="normal" if sim else "disabled")

    def modificado(self, sim):
        self._mod = sim
        self.st_mod.configure(text="modificado" if sim else "")

    def confirmar_forms(self):
        """Grava o formulário da aba visível (as outras já gravaram ao serem deixadas)."""
        if self.dados is None or not self.nb.select():
            return
        atual = self.nb.nametowidget(self.nb.select())
        if hasattr(atual, "confirmar"):
            atual.confirmar()

    def _trocou_aba(self):
        if self.dados is None or not self.nb.select():
            return
        anterior = getattr(self, "_aba_atual", None)
        if anterior is not None:
            anterior.confirmar()
        atual = self.nb.nametowidget(self.nb.select())
        self._aba_atual = atual
        if atual is self.aba_cat:
            self.aba_cat.recarregar()
        elif isinstance(atual, AbaEntidades):
            atual.recarregar(manter=True)

    def renomear_referencias(self, chave, antigo, novo):
        for alvo, caminho in REFERENCIAS.get(chave, []):
            for x in self.dados.get(alvo, []):
                if obter(x, caminho) == antigo:
                    d = x
                    for k in caminho[:-1]:
                        d = d[k]
                    d[caminho[-1]] = novo
        for aba in self.abas.values():                  # recarrega formulários abertos (evita gravar o ID antigo)
            if aba.atual is not None and aba.chave != chave and aba.atual < len(aba.lista):
                aba.form.carregar(aba.lista[aba.atual])
        if chave == "equipes":
            regras = obter(self.dados, ("categoria", "regras")) or {}
            lst = regras.get("equipes_com_desenvolvimento_de_motor") or []
            regras["equipes_com_desenvolvimento_de_motor"] = [novo if x == antigo else x for x in lst]
            for n in obter(self.dados, ("categoria", "novas_equipes")) or []:
                if n.get("equipe") == antigo:
                    n["equipe"] = novo

    def carregar_dados(self, dados, caminho):
        self.dados = dados
        self.caminho = caminho
        self.erros_por_item = {}
        self._habilitar(True)
        self._aba_atual = None
        self.nb.select(0)
        self.aba_cat.recarregar()
        for a in self.abas.values():
            a.atual = None
            a.recarregar()
        c = dados.get("categoria", {})
        self.st_arq.configure(text=f"{c.get('nome', '?')} {c.get('ano', '')} – {caminho or '(não salvo)'}")
        self.modificado(caminho is None)

    def _descartar_ok(self):
        return not self._mod or messagebox.askyesno("Editor", "Descartar as alterações não salvas?", parent=self)

    # ------------------------------------------------------------ ações
    def novo(self):
        if not self._descartar_ok():
            return
        r = DialogoNovo(self, db.todos_os_arquivos()).modal()
        if not r:
            return
        cid, nome, ano, modelo = r
        base = db.carregar_arquivo(modelo, validar=False) if modelo else None
        cat = copy.deepcopy(base["categoria"]) if base else {"regras": {}}
        cat.update({"id": cid, "nome": nome, "ano": ano})
        self.carregar_dados({"versao_formato": 1, "categoria": cat, "pilotos": [], "chassis": [], "motores": [],
                             "equipes": [], "patrocinadores": [], "calendario": []}, None)

    def abrir(self):
        if not self._descartar_ok():
            return
        caminho = filedialog.askopenfilename(parent=self, initialdir=PASTA_DATABASE, title="Abrir database",
                                             filetypes=[("Database JSON", "*.json")])
        if caminho:
            try:
                self.carregar_dados(db.carregar_arquivo(caminho, validar=False), caminho)
            except db.ErroDatabase as e:
                messagebox.showerror("Abrir", str(e), parent=self)

    def _caminho_padrao(self, ano=None):
        c = self.dados["categoria"]
        ano = ano or c.get("ano")
        return os.path.join(PASTA_DATABASE, str(ano), f"{c.get('id', 'categoria')}_{ano}.json")

    def validar(self, mostrar_ok=True):
        if not self.dados:
            return True
        self.confirmar_forms()
        erros = db.validar_dados(self.dados)
        self.erros_por_item = {}
        for e in erros:
            m = re.match(r"^(piloto|chassis|motor|equipe|patrocinador|calendário) ([^\s:]+)", e)
            if m:
                self.erros_por_item.setdefault((TIPO_ERRO[m.group(1)], m.group(2)), []).append(e)
        for a in self.abas.values():
            a.recarregar(manter=True)
        if erros:
            DialogoLista(self, "Validação", f"{len(erros)} problema(s). Clique duas vezes para ir ao registro:",
                         erros, ao_abrir=self._ir_para_erro).modal()
            return False
        if mostrar_ok:
            messagebox.showinfo("Validação", "Nenhum problema encontrado.", parent=self)
        return True

    def _ir_para_erro(self, texto):
        m = re.match(r"^(piloto|chassis|motor|equipe|patrocinador|calendário) ([^\s:]+)", texto)
        if m:
            aba = self.abas[TIPO_ERRO[m.group(1)]]
            self.nb.select(aba)
            aba.ir_para(m.group(2))
        else:
            self.nb.select(self.aba_cat)

    def salvar(self, como=False, caminho=None, dados=None):
        if not self.dados:
            return
        self.confirmar_forms()
        dados = dados or self.dados
        if dados is self.dados and not self.validar(mostrar_ok=False):
            if not messagebox.askyesno("Salvar", "Há problemas de validação. Salvar mesmo assim?", parent=self):
                return
        if caminho is None:
            caminho = self.caminho
            if como or not caminho:
                padrao = self._caminho_padrao()
                os.makedirs(os.path.dirname(padrao), exist_ok=True)
                caminho = filedialog.asksaveasfilename(parent=self, initialdir=os.path.dirname(padrao),
                                                       initialfile=os.path.basename(padrao), defaultextension=".json",
                                                       filetypes=[("Database JSON", "*.json")])
                if not caminho:
                    return
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        if dados is self.dados:
            self.caminho = caminho
            self.modificado(False)
            self.st_arq.configure(text=f"{self.dados['categoria'].get('nome')} – {caminho}")
        messagebox.showinfo("Salvar", f"Arquivo salvo:\n{caminho}", parent=self)

    def duplicar_ano(self):
        if not self.dados:
            return
        self.confirmar_forms()
        ano_atual = int(self.dados["categoria"].get("ano", 2026))
        ano = simpledialog.askinteger("Duplicar", "Duplicar para o ano:", initialvalue=ano_atual + 1, parent=self)
        if not ano:
            return
        novo = copy.deepcopy(self.dados)
        novo["categoria"]["ano"] = ano
        for p in novo.get("pilotos", []):
            p["idade"] = p.get("idade", 20) + (ano - ano_atual)
        caminho = self._caminho_padrao(ano)
        if os.path.exists(caminho) and not messagebox.askyesno("Duplicar", f"{caminho} já existe. Substituir?",
                                                                 parent=self):
            return
        self.salvar(caminho=caminho, dados=novo)
        self.carregar_dados(novo, caminho)

    def importar(self):
        if not self._descartar_ok():
            return
        dados = AssistenteImportacao(self, db.todos_os_arquivos()).modal()
        if dados:
            self.carregar_dados(dados, None)

    def buscar_imagens(self):
        if not self.dados:
            return
        self.confirmar_forms()
        r = DialogoImagens(self, self.dados).modal()
        if r is None:
            return
        obtidas, avisos = r
        if obtidas:
            self.modificado(True)
        for a in self.abas.values():
            a.recarregar(manter=True)
        mostrar_resultado_imagens(self, obtidas, avisos)

    def imagens_de_pasta(self):
        if not self.dados:
            return
        self.confirmar_forms()
        pasta = filedialog.askdirectory(parent=self, title="Pasta com as imagens")
        if not pasta:
            return
        from .. import imagens
        feitos, sem_par = imagens.importar_pasta(self.dados, pasta)
        if feitos:
            self.modificado(True)
        for a in self.abas.values():
            a.recarregar(manter=True)
        itens = feitos + ([""] + ["Sem correspondência (renomeie com o nome do piloto/equipe/chassis/motor/pista "
                                  "ou país):"] + sem_par if sem_par else [])
        DialogoLista(self, "Imagens de pasta", f"{len(feitos)} imagem(ns) associada(s) e copiadas para "
                                               "database/imagens.", itens or ["Nenhuma imagem encontrada."]).modal()

    def fechar(self):
        self.confirmar_forms()
        if self._descartar_ok():
            self.destroy()


# ====================================================================== diálogos
def mostrar_resultado_imagens(master, obtidas, avisos):
    texto = f"{obtidas} imagem(ns) obtida(s), salvas em database/imagens."
    if avisos:
        DialogoLista(master, "Buscar imagens", texto + " Avisos:", avisos).modal()
    else:
        messagebox.showinfo("Buscar imagens", texto, parent=master)


class DialogoImagens(w.Dialogo):
    """Busca na Wikipedia as imagens que faltam (fotos, logotipos e pistas), com barra de progresso."""

    def __init__(self, master, dados):
        super().__init__(master, "Buscar imagens na Wikipedia", 460, 170)
        import threading
        self.dados = dados
        self._parar = False
        self._prog = (0, 1, "Preparando...")
        self._fim = None
        w.BarraTitulo(self.corpo, "Baixando fotos, logotipos e pistas").pack(fill="x", pady=(0, 8))
        self.barra = ttk.Progressbar(self.corpo, length=420, mode="determinate")
        self.barra.pack(fill="x")
        self.lbl = tk.Label(self.corpo, text="", anchor="w")
        self.lbl.pack(fill="x", pady=4)
        self.btn = w.Botao(self.rodape, "Interromper", self.cancelar, largura=12)
        self.btn.pack(side="right")
        threading.Thread(target=self._trabalho, daemon=True).start()
        self.after(100, self._acompanhar)

    def _trabalho(self):
        from ..editor import imagens_wiki
        try:
            prog = lambda a, b, t: setattr(self, "_prog", (a, b, t))  # noqa: E731
            n, avisos = imagens_wiki.buscar_todas(self.dados, prog, lambda: self._parar)
            if not self._parar:          # bandeiras dos países do arquivo que ainda não existem
                n2, av2 = imagens_wiki.buscar_bandeiras(imagens_wiki.paises_do_arquivo(self.dados), prog,
                                                        lambda: self._parar)
                n, avisos = n + n2, avisos + av2
            self._fim = (n, avisos)
        except Exception as e:                       # erro de rede etc.: devolve como aviso
            self._fim = (0, [str(e)])

    def _acompanhar(self):
        a, b, t = self._prog
        self.barra.configure(maximum=max(1, b), value=a)
        self.lbl.configure(text=f"{a}/{b} – {t}")
        if self._fim is not None:
            self.resultado = self._fim
            self.destroy()
            return
        self.after(150, self._acompanhar)

    def cancelar(self):
        self._parar = True                           # termina a imagem atual e devolve o que já foi obtido
        self.btn.configure(state="disabled")
        self.lbl.configure(text="Interrompendo...")


class DialogoLista(w.Dialogo):
    def __init__(self, master, titulo, texto, itens, ao_abrir=None):
        super().__init__(master, titulo, 680, 400)
        tk.Label(self.corpo, text=texto, justify="left", anchor="w").pack(fill="x")
        self.lb = tk.Listbox(self.corpo, relief="sunken", bd=2)
        self.lb.pack(fill="both", expand=True, pady=4)
        for i in itens:
            self.lb.insert("end", i)
        if ao_abrir:
            def abrir(_e=None):
                sel = self.lb.curselection()
                if sel:
                    txt = self.lb.get(sel[0])
                    self.destroy()
                    ao_abrir(txt)
            self.lb.bind("<Double-1>", abrir)
        w.Botao(self.rodape, "OK", self.destroy, largura=10).pack(side="right")


class DialogoNovo(w.Dialogo):
    def __init__(self, master, modelos):
        super().__init__(master, "Novo arquivo", 480, 230)
        self.modelos = modelos
        f = self.corpo
        self.v = {k: tk.StringVar() for k in ("id", "nome", "ano")}
        self.v["ano"].set("2026")
        for i, (k, r) in enumerate((("nome", "Nome da categoria:"), ("id", "ID (gerado pelo nome):"), ("ano", "Ano:"))):
            tk.Label(f, text=r).grid(row=i, column=0, sticky="w", pady=2)
            ttk.Entry(f, textvariable=self.v[k], width=30).grid(row=i, column=1, sticky="w")
        self.v["nome"].trace_add("write", lambda *a: self.v["id"].set(_slug(self.v["nome"].get())))
        tk.Label(f, text="Copiar regras de:").grid(row=3, column=0, sticky="w", pady=2)
        self.cb = ttk.Combobox(f, state="readonly", width=36,
                               values=["(em branco)"] + [os.path.basename(m) for m in modelos])
        self.cb.current(1 if modelos else 0)
        self.cb.grid(row=3, column=1, sticky="w")
        w.Botao(self.rodape, "Cancelar", self.cancelar, largura=10).pack(side="right", padx=2)
        w.Botao(self.rodape, "OK", self.ok, largura=10).pack(side="right", padx=2)

    def ok(self):
        cid, nome = self.v["id"].get().strip(), self.v["nome"].get().strip()
        if not cid or not nome or not self.v["ano"].get().isdigit():
            messagebox.showwarning("Novo", "Preencha nome, ID e ano.", parent=self)
            return
        modelo = self.modelos[self.cb.current() - 1] if self.cb.current() > 0 else None
        self.resultado = (cid, nome, int(self.v["ano"].get()), modelo)
        self.destroy()


class AssistenteImportacao(w.Dialogo):
    """Importação em etapas: 1) encontrar a página; 2) baixar e conferir a prévia; 3) aplicar no editor."""

    def __init__(self, master, modelos):
        super().__init__(master, "Importar da Wikipedia", 860, 600)
        self.modelos = modelos
        self.dados = None
        self.etapa = 0
        self.titulo = w.BarraTitulo(self.corpo, "")
        self.titulo.pack(fill="x", pady=(0, 6))
        self.area = tk.Frame(self.corpo)
        self.area.pack(fill="both", expand=True)
        self.v = {k: tk.StringVar() for k in ("serie", "ano", "pagina", "id", "nome")}
        self.v["serie"].set("Formula One")
        self.v["ano"].set("2023")
        self.v["id"].set("formula_1")
        self.v["nome"].set("Fórmula 1")
        self.btn_voltar = w.Botao(self.rodape, "< Voltar", self.voltar, largura=10)
        self.btn_voltar.pack(side="left")
        w.Botao(self.rodape, "Cancelar", self.cancelar, largura=10).pack(side="right", padx=2)
        self.btn_avancar = w.Botao(self.rodape, "Avançar >", self.avancar, largura=12)
        self.btn_avancar.pack(side="right", padx=2)
        self._mostrar()

    def _limpar(self):
        for ch in self.area.winfo_children():
            ch.destroy()

    def _mostrar(self):
        self._limpar()
        self.btn_voltar.configure(state="normal" if self.etapa > 0 else "disabled")
        if self.etapa == 0:
            self._etapa_pagina()
        elif self.etapa == 1:
            self._etapa_previa()

    # ---------------------------------------------------------------- etapa 1
    def _etapa_pagina(self):
        self.titulo.definir("Etapa 1 de 3 – encontre a página da temporada (Wikipedia em inglês)")
        self.btn_avancar.configure(text="Avançar >")
        f = self.area
        tk.Label(f, text="Série (em inglês):").grid(row=0, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.v["serie"], width=34).grid(row=0, column=1, sticky="w", padx=4)
        tk.Label(f, text="Ano:").grid(row=0, column=2, sticky="w")
        ttk.Entry(f, textvariable=self.v["ano"], width=8).grid(row=0, column=3, sticky="w", padx=4)
        w.Botao(f, "Buscar páginas", self.buscar).grid(row=0, column=4, padx=6)
        tk.Label(f, text="Ex.: Formula One, FIA Formula 2 Championship, IndyCar Series, Formula E, "
                         "British Touring Car Championship.", fg=w.CINZA_ESCURO).grid(row=1, column=0, columnspan=5,
                                                                                     sticky="w")
        tk.Label(f, text="Resultados (clique para escolher):").grid(row=2, column=0, columnspan=5, sticky="w",
                                                                   pady=(8, 0))
        self.lb = tk.Listbox(f, height=10, width=80, relief="sunken", bd=2, exportselection=False)
        self.lb.grid(row=3, column=0, columnspan=5, sticky="we")
        self.lb.bind("<<ListboxSelect>>", lambda e: self.v["pagina"].set(self.lb.get(self.lb.curselection()[0]))
                     if self.lb.curselection() else None)
        tk.Label(f, text="Página escolhida (ou cole o título/link):").grid(row=4, column=0, columnspan=2, sticky="w",
                                                                          pady=(8, 0))
        ttk.Entry(f, textvariable=self.v["pagina"], width=70).grid(row=5, column=0, columnspan=5, sticky="w")
        if not self.v["pagina"].get():
            self.v["pagina"].set(wikipedia.titulo_sugerido(self.v["ano"].get()))
        g = w.Grupo(f, "Arquivo a ser criado")
        g.grid(row=6, column=0, columnspan=5, sticky="we", pady=(10, 0))
        tk.Label(g, text="Nome da categoria:").grid(row=0, column=0, sticky="w")
        ttk.Entry(g, textvariable=self.v["nome"], width=30).grid(row=0, column=1, sticky="w", padx=4)
        tk.Label(g, text="ID:").grid(row=0, column=2, sticky="w")
        ttk.Entry(g, textvariable=self.v["id"], width=20).grid(row=0, column=3, sticky="w", padx=4)
        tk.Label(g, text="Copiar regras de:").grid(row=1, column=0, sticky="w", pady=4)
        self.cb_modelo = ttk.Combobox(g, state="readonly", width=40, values=[os.path.basename(m) for m in self.modelos])
        if self.modelos:
            self.cb_modelo.current(getattr(self, "_modelo_idx", 0))
        self.cb_modelo.grid(row=1, column=1, columnspan=3, sticky="w", padx=4)
        tk.Label(g, text="Pneus, clima, formato do evento, ponderação etc. vêm desse arquivo; o resto vem da página.",
                 fg=w.CINZA_ESCURO).grid(row=2, column=0, columnspan=4, sticky="w")

    def buscar(self):
        texto = f"{self.v['ano'].get()} {self.v['serie'].get()}".strip()
        self.config(cursor="watch")
        self.update()
        try:
            titulos = wikipedia.buscar_titulos(texto)
        except wikipedia.ErroImportacao as e:
            messagebox.showerror("Buscar", str(e), parent=self)
            return
        finally:
            self.config(cursor="")
        self.lb.delete(0, "end")
        for t in titulos:
            self.lb.insert("end", t)
        if not titulos:
            self.lb.insert("end", "(nada encontrado)")

    # ---------------------------------------------------------------- etapa 2
    def _etapa_previa(self):
        self.titulo.definir("Etapa 2 de 3 – confira o que foi encontrado")
        self.btn_avancar.configure(text="Aplicar no editor")
        d = self.dados
        c = d["categoria"]
        r = c["regras"]
        f = self.area
        resumo = (f"Página: {self.v['pagina'].get()}\n"
                  f"{len(d['equipes'])} equipes · {len(d['pilotos'])} pilotos · {len(d['chassis'])} chassis · "
                  f"{len(d['motores'])} motores · {len(d['calendario'])} corridas\n"
                  f"Pilotos principais por equipe: {r.get('pilotos_principais_por_equipe')} · "
                  f"{'equipes desenvolvem o chassis' if r.get('desenvolvimento_chassis_por_equipe') else 'chassis de fornecedores (monomarca)'}"
                  f" · motor próprio: {', '.join(r.get('equipes_com_desenvolvimento_de_motor') or []) or 'nenhum'}\n"
                  f"Pontuação: {c['pontuacao'].get('posicoes')} · pole {c['pontuacao'].get('pole', 0)} · "
                  f"volta mais rápida {c['pontuacao'].get('volta_mais_rapida', 0)}")
        tk.Label(f, text=resumo, justify="left", anchor="w", bg=w.AMARELO_INFO, relief="sunken", bd=1).pack(fill="x")
        nb = ttk.Notebook(f)
        nb.pack(fill="both", expand=True, pady=6)
        cols = [("eq", "Equipe"), ("nac", "País"), ("ch", "Chassis"), ("mo", "Motor"), ("pil", "Pilotos")]
        fr, tv = w.tabela(nb, cols, 10, {"eq": 160, "nac": 90, "ch": 140, "mo": 140, "pil": 260}, estica={"pil"},
                          cores=True)
        nomes_ch = {x["id"]: x["nome"] for x in d["chassis"]}
        nomes_mo = {x["id"]: x["nome"] for x in d["motores"]}
        for e in d["equipes"]:
            pil = [p["nome"] for p in d["pilotos"] if (p.get("contrato") or {}).get("equipe") == e["id"]]
            tv.insert("", "end", image=w.chip_equipe(e, e.get("nacionalidade")), values=(e["nome"], e["nacionalidade"],
                                         f"{nomes_ch.get((e.get('chassis') or {}).get('id'), '-')} ({(e.get('chassis') or {}).get('origem', '')})",
                                         f"{nomes_mo.get((e.get('motor') or {}).get('id'), '-')} ({(e.get('motor') or {}).get('origem', '')})",
                                         ", ".join(pil)))
        nb.add(fr, text="Equipes")
        fr2, tv2 = w.tabela(nb, [("s", "Semana"), ("n", "Corrida"), ("l", "Local"), ("t", "Tipo")], 10,
                            {"s": 60, "n": 260, "l": 260, "t": 70}, estica={"n"}, cores=True)
        for ev in d["calendario"]:
            tv2.insert("", "end", image=w.ficha(pais=paises.do_local(ev.get("local")), com_cor=False), values=(ev["semana"], ev["nome"], ev["local"], ev["tipo_pista"]))
        nb.add(fr2, text="Calendário")
        if not hasattr(self, "v_imagens"):
            self.v_imagens = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, variable=self.v_imagens, text="Baixar também as imagens da Wikipedia (fotos dos pilotos, "
                                                          "logotipos das equipes e pistas)").pack(anchor="w")
        lb = tk.Listbox(nb, relief="sunken", bd=2)
        for a in self.avisos:
            lb.insert("end", a)
        nb.add(lb, text=f"Avisos ({len(self.avisos)})")

    # ---------------------------------------------------------------- navegação
    def avancar(self):
        if self.etapa == 0:
            if not self.v["ano"].get().isdigit() or not self.v["pagina"].get().strip() or not self.modelos:
                messagebox.showwarning("Importar", "Informe o ano e a página.", parent=self)
                return
            self._modelo_idx = self.cb_modelo.current()
            self.config(cursor="watch")
            self.update()
            try:
                html = wikipedia.baixar_html(self.v["pagina"].get())
                self.dados, self.avisos = wikipedia.importar(
                    html, int(self.v["ano"].get()), self.v["id"].get().strip() or "categoria",
                    self.v["nome"].get().strip() or "Categoria",
                    db.carregar_arquivo(self.modelos[self._modelo_idx], validar=False))
            except wikipedia.ErroImportacao as e:
                messagebox.showerror("Importar", str(e), parent=self)
                return
            finally:
                self.config(cursor="")
            self.etapa = 1
            self._mostrar()
        else:
            if self.v_imagens.get():
                r = DialogoImagens(self, self.dados).modal()
                if r:
                    mostrar_resultado_imagens(self, *r)
            self.resultado = self.dados
            self.destroy()

    def voltar(self):
        if self.etapa > 0:
            self.etapa -= 1
            self._mostrar()
