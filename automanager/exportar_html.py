"""Exporta o jogo para HTML: um pequeno site estático, como os relatórios HTML de jogos de gerenciamento
(Out of the Park Baseball, Football Manager...). Abre em qualquer navegador, sem internet.

Páginas: início (resumo, líderes, próximos eventos, notícias), e por categoria: classificação (pilotos e equipes, com
a posição em cada corrida), calendário (com vencedor, pole e volta mais rápida), resultado de cada corrida, equipes
e pilotos; finanças da equipe do jogador; notícias.

Mostra o que o jogador vê no jogo: finanças e salários só da(s) equipe(s) dele; notas dos pilotos como nas telas.
Textos no idioma do jogo (i18n). Bandeiras e logotipos usados são copiados para a pasta img/.
"""
import html
import os
import shutil
import time

from . import campeonato, cores, imagens, paises, ratings, state, i18n
from .util import dinheiro, relogio, tempo_volta

NOMES_RECEITAS = {"patrocinio": "Patrocínios", "tv": "Renda de TV", "premios": "Prêmios de corrida",
                  "fornecimento": "Venda de chassis/motor", "multas": "Multas recebidas",
                  "emprestimos": "Empréstimos recebidos"}
NOMES_DESPESAS = {"salarios": "Salários de pilotos", "chassis": "Contrato de chassis", "motor": "Contrato de motor",
                  "desenvolvimento": "Desenvolvimento", "multas": "Multas pagas",
                  "emprestimos": "Parcelas de empréstimos"}
TIPOS_PISTA = {"mista": "mista", "oval": "oval", "rua": "pista de rua"}

CSS = """
:root { --azul: #0a246a; --azul2: #3a6ea5; --cinza: #ece9d8; --linha: #d4d0c8; --texto: #111; --fundo: #fff;
        --ouro: #ffdf80; --prata: #dfdfdf; --bronze: #ffbf9f; --pontos: #dfffdf; --semponto: #cfcfff;
        --abandono: #efcfff; --usuario: #fff6c8; }
* { box-sizing: border-box; }
body { margin: 0; font: 13px/1.4 Tahoma, Verdana, "Segoe UI", sans-serif; color: var(--texto); background: var(--cinza); }
header { background: linear-gradient(90deg, var(--azul), var(--azul2)); color: #fff; padding: 10px 16px; }
header h1 { margin: 0; font-size: 18px; }
header .sub { opacity: .85; font-size: 12px; }
nav { background: #d6d2c2; border-bottom: 1px solid #a09c8c; padding: 4px 12px; display: flex; flex-wrap: wrap; gap: 4px 14px; }
nav a { color: var(--azul); text-decoration: none; font-weight: bold; }
nav a:hover { text-decoration: underline; }
nav .cat { color: #555; font-weight: bold; }
main { max-width: 1180px; margin: 12px auto; padding: 0 16px; }
section { background: var(--fundo); border: 1px solid #a09c8c; margin-bottom: 14px; }
section > h2 { margin: 0; padding: 5px 10px; font-size: 13px; color: #fff; background: var(--azul); }
section > .conteudo { padding: 8px 10px; overflow-x: auto; }
.colunas { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 14px; }
table { border-collapse: collapse; width: 100%; }
th, td { padding: 3px 6px; border-bottom: 1px solid var(--linha); text-align: left; }
th, td.num, td.res, td.c { white-space: nowrap; }
th { background: #e8e5d8; font-size: 12px; position: sticky; top: 0; cursor: pointer; user-select: none; }
th.num, td.num { text-align: right; }
td.c, th.c { text-align: center; }
tr:nth-child(even) td { background: #faf9f4; }
tr.usuario td { background: var(--usuario) !important; font-weight: bold; }
img.bandeira { width: 18px; height: 12px; vertical-align: -1px; border: 1px solid #888; margin-right: 4px; }
img.logo { max-height: 40px; max-width: 90px; float: right; }
.chip { display: inline-block; width: 6px; height: 13px; vertical-align: -2px; margin-right: 5px; border: 1px solid #555; }
.res { text-align: center; font-size: 11px; min-width: 26px; padding: 2px 3px; }
.p1 { background: var(--ouro) !important; } .p2 { background: var(--prata) !important; }
.p3 { background: var(--bronze) !important; } .pts { background: var(--pontos) !important; }
.np { background: var(--semponto) !important; } .ret { background: var(--abandono) !important; }
.feito { color: #555; } .proximo td { font-weight: bold; background: #eef4ff !important; }
.legenda span { display: inline-block; padding: 1px 6px; margin-right: 6px; border: 1px solid #aaa; font-size: 11px; }
.pos { color: #070; } .neg { color: #b00; }
.noticia { padding: 3px 0; border-bottom: 1px dotted var(--linha); }
.noticia.usuario { font-weight: bold; color: #7a0000; }
.equipe-cartao { border-left: 8px solid #888; padding: 6px 10px; }
.equipe-cartao h3 { margin: 0 0 4px; font-size: 14px; }
footer { text-align: center; color: #555; font-size: 11px; padding: 10px; }
a { color: var(--azul); }
@media print { nav, footer { display: none; } body { background: #fff; } section { break-inside: avoid; } }
"""

JS = """
document.querySelectorAll('table.ordenavel th').forEach(function (th, i) {
  th.addEventListener('click', function () {
    var tb = th.closest('table').tBodies[0], linhas = Array.from(tb.rows), asc = th.dataset.ord !== 'asc';
    th.closest('tr').querySelectorAll('th').forEach(function (x) { delete x.dataset.ord; });
    th.dataset.ord = asc ? 'asc' : 'desc';
    function v(r) { var c = r.cells[i]; var s = (c.dataset.v !== undefined ? c.dataset.v : c.textContent).trim();
      var n = parseFloat(s.replace(/[^0-9.,-]/g, '').replace(/\\./g, '').replace(',', '.'));
      return (c.dataset.v !== undefined || /^[-+]?[\\d.,]+/.test(s.replace(/^USD\\s*/, ''))) && !isNaN(n) ? n : s.toLowerCase(); }
    linhas.sort(function (a, b) { var x = v(a), y = v(b); return (x > y ? 1 : x < y ? -1 : 0) * (asc ? 1 : -1); });
    linhas.forEach(function (r) { tb.appendChild(r); });
  });
});
"""


def t(texto):
    return i18n.t(texto)


def e(x):
    return html.escape("" if x is None else str(x))


class Exportador:
    def __init__(self, st, pasta):
        self.st = st
        self.pasta = pasta
        self.img = os.path.join(pasta, "img")
        self.copiadas = {}
        sessao = (st.get("multiplayer") or {}).get("sessao")
        u = st.get("usuario") or {}
        # equipe(s) do jogador: no multijogador, a de quem está logado; senão, a do jogador (mesmo com a IA no comando)
        self.humanas = {(u["categoria"], u["equipe"])} if sessao and u.get("equipe") \
            else state.humanas(st, com_ia_no_comando=True)

    # ------------------------------------------------------------------ utilidades
    def _imagem(self, rel):
        """Copia a imagem para img/ (uma vez) e devolve o caminho relativo da página, ou None."""
        if not rel or not imagens.existe(rel):
            return None
        if rel not in self.copiadas:
            destino = "img/" + rel.replace("\\", "/").replace("/", "_")
            os.makedirs(self.img, exist_ok=True)
            shutil.copyfile(imagens.caminho_absoluto(rel), os.path.join(self.pasta, destino))
            self.copiadas[rel] = destino
        return self.copiadas[rel]

    def bandeira(self, pais):
        src = self._imagem(imagens.bandeira(pais)) if pais else None
        return f'<img class="bandeira" src="{src}" alt="" title="{e(t(paises.em_portugues(pais)))}">' if src else ""

    def chip(self, eq):
        if not eq:
            return ""
        return (f'<span class="chip" style="background:{cores.cor_equipe(eq)};'
                f'border-right:3px solid {cores.cor_secundaria(eq)}"></span>')

    def equipe(self, cid, eid):
        return self.st["categorias"][cid]["equipes"].get(eid)

    def eh_usuario(self, cid, eid):
        return (cid, eid) in self.humanas

    def link_equipe(self, cid, eid, nome=None):
        eq = self.equipe(cid, eid)
        nome = nome or (eq or {}).get("nome", eid)
        return f'{self.chip(eq)}<a href="{cid}-equipes.html#{e(eid)}">{e(nome)}</a>'

    def nav(self):
        partes = [f'<a href="index.html">{t("Início")}</a>']
        for cid, c in self.st["categorias"].items():
            partes.append(f'<span class="cat">{e(c["categoria"]["nome"])}:</span>'
                          f'<a href="{cid}-classificacao.html">{t("Campeonato")}</a>'
                          f'<a href="{cid}-calendario.html">{t("Calendário")}</a>'
                          f'<a href="{cid}-equipes.html">{t("Equipes")}</a>'
                          f'<a href="{cid}-pilotos.html">{t("Pilotos")}</a>')
        if self.humanas:
            partes.append(f'<a href="financas.html">{t("Finanças")}</a>')
        partes.append(f'<a href="noticias.html">{t("Notícias")}</a>')
        return "<nav>" + " ".join(partes) + "</nav>"

    def pagina(self, nome, titulo, corpo):
        st = self.st
        u = st.get("usuario") or {}
        sub = f'{t("Temporada")} {st["ano"]} · {t("Semana")} {st["semana"]}/52'
        if u.get("equipe") and not st.get("multiplayer"):
            sub += f' · {e(state.equipe_usuario(st)["nome"])}'
        html_ = (f'<!DOCTYPE html>\n<html lang="{i18n.atual()}"><head><meta charset="utf-8">'
                 f'<meta name="viewport" content="width=device-width, initial-scale=1">'
                 f'<title>{e(titulo)} – AutoManager</title><link rel="stylesheet" href="estilo.css"></head><body>'
                 f'<header><h1>{e(titulo)}</h1><div class="sub">{sub}</div></header>{self.nav()}<main>{corpo}</main>'
                 f'<footer>AutoManager · {t("Exportado em")} {time.strftime("%Y-%m-%d %H:%M")}</footer>'
                 f'<script src="ordenar.js"></script></body></html>')
        with open(os.path.join(self.pasta, nome), "w", encoding="utf-8") as f:
            f.write(html_)

    @staticmethod
    def secao(titulo, conteudo, id_=None):
        ident = f' id="{e(id_)}"' if id_ else ""
        return f'<section{ident}><h2>{e(titulo)}</h2><div class="conteudo">{conteudo}</div></section>'

    @staticmethod
    def tabela_html(cabecalho_html, linhas):
        trs = "".join(f'<tr class="{ct}">' + "".join(cels) + "</tr>" for ct, cels in linhas)
        return f'<table class="ordenavel"><thead><tr>{cabecalho_html}</tr></thead><tbody>{trs}</tbody></table>'

    def local(self, texto):
        """'Serra Azul, Brasil' com o país no idioma do jogo."""
        partes = (texto or "").rsplit(",", 1)
        return f'{partes[0].strip()}, {t(partes[1].strip())}' if len(partes) == 2 else t(texto or "")

    @staticmethod
    def tabela(cabecalho, linhas, ordenavel=True):
        """cabecalho: [(texto, classe)]; linhas: [(classe_tr, [html das células])]."""
        th = "".join(f'<th class="{c}">{e(x)}</th>' for x, c in cabecalho)
        trs = "".join(f'<tr class="{ct}">' + "".join(cel for cel in cels) + "</tr>" for ct, cels in linhas)
        return f'<table class="{"ordenavel" if ordenavel else ""}"><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>'

    # ------------------------------------------------------------------ dados
    def corridas(self, cid):
        return self.st.get("temporadas", {}).get(str(self.st["ano"]), {}).get(cid, {}).get("corridas", [])

    def calendario(self, cid):
        return sorted((ev for ev in self.st["categorias"][cid]["calendario"] if ev.get("ativo")),
                      key=lambda ev: ev["semana"])

    def classificacao(self, cid):
        return campeonato.classificacao(self.st, cid)

    # ------------------------------------------------------------------ páginas
    def exportar(self):
        os.makedirs(self.pasta, exist_ok=True)
        with open(os.path.join(self.pasta, "estilo.css"), "w", encoding="utf-8") as f:
            f.write(CSS)
        with open(os.path.join(self.pasta, "ordenar.js"), "w", encoding="utf-8") as f:
            f.write(JS)
        for cid in self.st["categorias"]:
            self.pag_classificacao(cid)
            self.pag_calendario(cid)
            self.pag_equipes(cid)
            self.pag_pilotos(cid)
            for r in self.corridas(cid):
                self.pag_corrida(cid, r)
        if self.humanas:
            self.pag_financas()
        self.pag_noticias()
        self.pag_inicio()
        return os.path.join(self.pasta, "index.html")

    def pag_inicio(self):
        st = self.st
        blocos = []
        for cid, eid in sorted(self.humanas):
            if not st.get("multiplayer"):
                blocos.append(self.secao(t("Sua equipe"), self._cartao_equipe(cid, eid)))
        cols = []
        for cid, c in st["categorias"].items():
            pil, eqs = self.classificacao(cid)
            linhas_p = [("usuario" if self._eid_de(cid, p["equipe"]) in [x for _, x in self.humanas] else "",
                         [f'<td class="num">{i}</td>', f'<td>{self.bandeira(p["nacionalidade"])}{e(p["nome"])}</td>',
                          f'<td>{e(p["equipe"])}</td>', f'<td class="num">{p["pontos"]:g}</td>'])
                        for i, p in enumerate(pil[:10], 1)]
            linhas_e = [("usuario" if self.eh_usuario(cid, x["id"]) else "",
                         [f'<td class="num">{i}</td>', f'<td>{self.link_equipe(cid, x["id"], x["nome"])}</td>',
                          f'<td class="num">{x["pontos"]:g}</td>']) for i, x in enumerate(eqs[:10], 1)]
            proximos = [ev for ev in self.calendario(cid) if ev["semana"] >= st["semana"]
                        and not campeonato.ja_disputado(st, cid, ev["id"])][:3]
            prox = "".join(f'<div>{t("Semana")} {ev["semana"]}: {self.bandeira(paises.do_local(ev.get("local")))}'
                           f'{e(ev["nome"])} <span class="feito">({e(self.local(ev.get("local")))})</span></div>'
                           for ev in proximos) or t("Temporada encerrada.")
            corpo = (f'<p><b>{t("Próximos eventos")}</b></p>{prox}'
                     f'<p><b>{t("Pilotos")}</b> – <a href="{cid}-classificacao.html">{t("classificação completa")}</a></p>'
                     + (self.tabela([("P", "num"), (t("Piloto"), ""), (t("Equipe"), ""), (t("Pts"), "num")], linhas_p,
                                    False) if linhas_p else f'<p>{t("Nenhuma corrida disputada ainda.")}</p>')
                     + f'<p><b>{t("Equipes")}</b></p>'
                     + (self.tabela([("P", "num"), (t("Equipe"), ""), (t("Pts"), "num")], linhas_e, False)
                        if linhas_e else ""))
            cols.append(self.secao(c["categoria"]["nome"], corpo))
        blocos.append(f'<div class="colunas">{"".join(cols)}</div>')
        campeoes = campeonato.campeoes(st)
        if campeoes:
            linhas = [("", [f'<td class="num">{e(x.get("ano"))}</td>', f'<td>{e(x.get("categoria_nome") or x.get("categoria"))}</td>',
                            f'<td>{self.bandeira(x.get("nacionalidade"))}{e(x.get("piloto"))}</td>',
                            f'<td>{e(x.get("equipe"))}</td>'])
                      for x in sorted(campeoes, key=lambda x: (-int(x.get("ano", 0)), str(x.get("categoria"))))]
            blocos.append(self.secao(t("Campeões"), self.tabela(
                [(t("Ano"), "num"), (t("Categoria"), ""), (t("Piloto"), ""), (t("Equipe"), "")], linhas)))
        blocos.append(self.secao(t("Últimas notícias"), self._noticias(25) +
                                 f'<p><a href="noticias.html">{t("Todas as notícias")}</a></p>'))
        self.pagina("index.html", f'AutoManager – {t("Temporada")} {st["ano"]}', "".join(blocos))

    @staticmethod
    def _marca(p):
        if p.get("lesao"):
            return ", " + t("lesionado")
        if (p.get("contrato") or {}).get("substituto_de"):
            return ", " + t("substituto")
        return ""

    def _eid_de(self, cid, nome_equipe):
        return next((eid for eid, eq in self.st["categorias"][cid]["equipes"].items() if eq["nome"] == nome_equipe),
                    None)

    def _cartao_equipe(self, cid, eid):
        st = self.st
        c = st["categorias"][cid]
        eq = c["equipes"][eid]
        ch, mo = state.chassis_da_equipe(st, cid, eq), state.motor_da_equipe(st, cid, eq)
        pos = campeonato.posicao_equipe(st, cid, eid)
        logo = self._imagem(eq.get("logotipo"))
        pil = [p for p in state.pilotos_da_equipe(st, cid, eid)]
        pilotos = ", ".join(f'{self.bandeira(p.get("nacionalidade"))}{e(p["nome"])} '
                            f'({e(t(p["contrato"]["situacao"]) + self._marca(p))})' for p in pil) or "-"
        caixa = ""
        if self.eh_usuario(cid, eid):
            caixa = f'<div>{t("Caixa")}: <b>{dinheiro(eq["financas"]["caixa"])}</b></div>'
        return (f'<div class="equipe-cartao" style="border-left-color:{cores.cor_equipe(eq)}">'
                + (f'<img class="logo" src="{logo}" alt="">' if logo else "")
                + f'<h3>{self.bandeira(eq.get("nacionalidade"))}{e(eq["nome"])}</h3>'
                f'<div>{t("Categoria")}: {e(c["categoria"]["nome"])} · {t("Posição no campeonato")}: '
                f'{pos or "-"} · {t("Recursos")}: {eq.get("recursos", "-")}/100</div>'
                f'<div>{t("Chassis")}: {e((ch or {}).get("nome", "-"))} · {t("Motor")}: {e((mo or {}).get("nome", "-"))}</div>'
                f'<div>{t("Pilotos")}: {pilotos}</div>{caixa}</div>')

    # --- classificação, com a posição em cada corrida (como nas tabelas da Wikipedia)
    def pag_classificacao(self, cid):
        st = self.st
        c = st["categorias"][cid]
        corridas = self.corridas(cid)
        cal = [ev for ev in self.calendario(cid) if ev["especie"] == "corrida"]
        por_evento = {r["evento"]: r for r in corridas}
        pil, eqs = self.classificacao(cid)
        # colunas das corridas: bandeira + 3 letras da cidade (como nas tabelas da Wikipedia); nome completo na dica
        cols = "".join(f'<th class="c" title="{e(ev["nome"])}">{self.bandeira(paises.do_local(ev.get("local")))}<br>'
                       f'{e((ev.get("local") or ev["nome"]).split(",")[0][:3].upper())}</th>' for ev in cal)
        fim = "".join(f'<th class="num">{e(x)}</th>' for x in (t("Vitórias"), t("Pódios"), t("Pts")))
        cab_p = f'<th class="num">P</th><th>{e(t("Piloto"))}</th><th>{e(t("Equipe"))}</th>{cols}{fim}'
        cab_e = f'<th class="num">P</th><th>{e(t("Equipe"))}</th>{cols}{fim}'

        def celula(r, filtro):
            if not r:
                return '<td class="res"></td>'
            if r.get("cancelada"):
                return '<td class="res">C</td>'
            ls = [l for l in r["resultado"] if filtro(l)]
            if not ls:
                return '<td class="res"></td>'
            out = []
            for l in ls:
                if l["status"] != "Fim":
                    out.append(("ret", t("Ab")))
                else:
                    cl = {1: "p1", 2: "p2", 3: "p3"}.get(l["pos"], "pts" if l["pontos"] > 0 else "np")
                    out.append((cl, str(l["pos"])))
            if len(out) == 1:
                return f'<td class="res {out[0][0]}" title="{e(r["nome"])}">{out[0][1]}</td>'
            melhor = min(out, key=lambda x: int(x[1]) if x[1].isdigit() else 99)
            return f'<td class="res {melhor[0]}" title="{e(r["nome"])}">{" / ".join(x[1] for x in out)}</td>'

        linhas = []
        for i, p in enumerate(pil, 1):
            eid = self._eid_de(cid, p["equipe"])
            linhas.append(("usuario" if self.eh_usuario(cid, eid) else "",
                           [f'<td class="num">{i}</td>', f'<td>{self.bandeira(p["nacionalidade"])}{e(p["nome"])}</td>',
                            f'<td>{self.link_equipe(cid, eid, p["equipe"]) if eid else e(p["equipe"])}</td>']
                           + [celula(por_evento.get(ev["id"]), lambda l, pid=p["id"]: l["piloto"] == pid) for ev in cal]
                           + [f'<td class="num">{p["vitorias"]}</td>', f'<td class="num">{p["podios"]}</td>',
                              f'<td class="num"><b>{p["pontos"]:g}</b></td>']))
        linhas_e = []
        for i, x in enumerate(eqs, 1):
            linhas_e.append(("usuario" if self.eh_usuario(cid, x["id"]) else "",
                             [f'<td class="num">{i}</td>', f'<td>{self.link_equipe(cid, x["id"], x["nome"])}</td>']
                             + [celula(por_evento.get(ev["id"]), lambda l, eid=x["id"]: l["equipe"] == eid) for ev in cal]
                             + [f'<td class="num">{x["vitorias"]}</td>', f'<td class="num">{x["podios"]}</td>',
                                f'<td class="num"><b>{x["pontos"]:g}</b></td>']))
        legenda = (f'<p class="legenda"><span class="p1">1º</span><span class="p2">2º</span><span class="p3">3º</span>'
                   f'<span class="pts">{t("nos pontos")}</span><span class="np">{t("sem pontos")}</span>'
                   f'<span class="ret">{t("Ab")} = {t("abandono")}</span> C = {t("corrida cancelada")}</p>')
        nota = "" if corridas else f'<p>{t("Nenhuma corrida disputada ainda.")}</p>'
        corpo = (self.secao(t("Campeonato de pilotos"), nota + legenda + self.tabela_html(cab_p, linhas))
                 + self.secao(t("Campeonato de equipes"), self.tabela_html(cab_e, linhas_e)))
        self.pagina(f"{cid}-classificacao.html", f'{c["categoria"]["nome"]} {st["ano"]} – {t("Campeonato")}', corpo)

    def pag_calendario(self, cid):
        st = self.st
        c = st["categorias"][cid]
        por_evento = {r["evento"]: r for r in self.corridas(cid)}
        testes = {x["evento"] for x in campeonato.testes_da_temporada(st, cid)}
        linhas = []
        proximo = next((ev["id"] for ev in self.calendario(cid) if ev["semana"] >= st["semana"]
                        and not campeonato.ja_disputado(st, cid, ev["id"]) and ev["id"] not in testes), None)
        for ev in self.calendario(cid):
            r = por_evento.get(ev["id"])
            vencedor = pole = vmr = ""
            if r and r.get("resultado") and not r.get("cancelada"):
                v = r["resultado"][0]
                vencedor = f'{self.bandeira(v["nacionalidade"])}{e(v["nome"])} ({e(v["equipe_nome"])})'
                pole = e(r.get("pole") or "")
                vmr = e((r.get("volta_rapida") or {}).get("nome", ""))
            elif r and r.get("cancelada"):
                vencedor = t("Cancelada")
            nome = (f'<a href="{cid}-corrida-{e(ev["id"])}.html">{e(ev["nome"])}</a>' if r else e(ev["nome"]))
            if ev["especie"] != "corrida":
                nome += f' <span class="feito">({t("teste coletivo")}{", " + t("feito") if ev["id"] in testes else ""})</span>'
            cl = "proximo" if ev["id"] == proximo else ("feito" if r or ev["id"] in testes else "")
            linhas.append((cl, [f'<td class="num">{ev["semana"]}</td>', f'<td>{nome}</td>',
                                f'<td>{self.bandeira(paises.do_local(ev.get("local")))}{e(self.local(ev.get("local")))}</td>',
                                f'<td>{e(t(TIPOS_PISTA.get(ev.get("tipo_pista"), ev.get("tipo_pista", ""))))}</td>',
                                f'<td class="num">{ev.get("voltas_corrida") or ""}</td>',
                                f'<td>{vencedor}</td>', f'<td>{pole}</td>', f'<td>{vmr}</td>']))
        corpo = self.secao(t("Calendário"), self.tabela(
            [(t("Semana"), "num"), (t("Evento"), ""), (t("Local"), ""), (t("Tipo"), ""), (t("Voltas"), "num"),
             (t("Vencedor"), ""), (t("Pole"), ""), (t("Volta mais rápida"), "")], linhas))
        self.pagina(f"{cid}-calendario.html", f'{c["categoria"]["nome"]} {st["ano"]} – {t("Calendário")}', corpo)

    def pag_corrida(self, cid, r):
        st = self.st
        c = st["categorias"][cid]
        lider = r["resultado"][0]["tempo"] if r.get("resultado") else 0
        linhas = []
        for l in r.get("resultado", []):
            if l["status"] != "Fim":
                tempo = e(t(l["status"]))
            elif l["pos"] == 1:
                tempo = relogio(l["tempo"])
            else:
                tempo = f'+{l["tempo"] - lider:.3f}'
            linhas.append(("usuario" if self.eh_usuario(cid, l["equipe"]) else "",
                           [f'<td class="num">{l["pos"]}</td>', f'<td>{self.bandeira(l.get("nacionalidade"))}{e(l["nome"])}</td>',
                            f'<td>{self.link_equipe(cid, l["equipe"], l["equipe_nome"])}</td>',
                            f'<td class="num">{l.get("grid") or ""}</td>', f'<td class="num">{l.get("voltas", "")}</td>',
                            f'<td class="num">{tempo}</td>', f'<td class="num">{l.get("paradas", "")}</td>',
                            f'<td class="num">{l["pontos"]:g}</td>']))
        info = f'<p>{e(self.local(r.get("local")))} · {t("Semana")} {r.get("semana", "")}'
        if r.get("pole"):
            info += f' · {t("Pole")}: {e(r["pole"])}'
        if r.get("volta_rapida"):
            vr = r["volta_rapida"]
            info += f' · {t("Volta mais rápida")}: {e(vr.get("nome"))}'
            if vr.get("tempo"):
                info += f' ({tempo_volta(vr["tempo"])})'
        info += "</p>"
        if r.get("cancelada"):
            info += f'<p><b>{t("Corrida cancelada: não vale pontos.")}</b></p>'
        corpo = self.secao(r["nome"], info + self.tabela(
            [("P", "num"), (t("Piloto"), ""), (t("Equipe"), ""), (t("Grid"), "num"), (t("Voltas"), "num"),
             (t("Tempo/Status"), "num"), (t("Pit"), "num"), (t("Pts"), "num")], linhas))
        self.pagina(f"{cid}-corrida-{r['evento']}.html", f'{c["categoria"]["nome"]} {st["ano"]} – {r["nome"]}', corpo)

    def pag_equipes(self, cid):
        st = self.st
        c = st["categorias"][cid]
        _, eqs = self.classificacao(cid)
        pontos = {x["id"]: x for x in eqs}
        ativas = sorted((eq for eq in c["equipes"].values() if eq.get("ativa")),
                        key=lambda eq: (-pontos.get(eq["id"], {}).get("pontos", 0), eq["nome"]))
        linhas = []
        cartoes = []
        for eq in ativas:
            ch, mo = state.chassis_da_equipe(st, cid, eq), state.motor_da_equipe(st, cid, eq)
            pil = [p for p in state.pilotos_da_equipe(st, cid, eq["id"]) if p["contrato"]["situacao"] == "principal"]
            x = pontos.get(eq["id"], {})
            linhas.append(("usuario" if self.eh_usuario(cid, eq["id"]) else "",
                           [f'<td>{self.chip(eq)}<a href="#{e(eq["id"])}">{e(eq["nome"])}</a></td>',
                            f'<td>{self.bandeira(eq.get("nacionalidade"))}{e(t(eq.get("nacionalidade", "")))}</td>',
                            f'<td>{e((ch or {}).get("nome", "-"))}</td>', f'<td>{e((mo or {}).get("nome", "-"))}</td>',
                            f'<td>{", ".join(e(p["nome"] + self._marca(p)) for p in pil) or "-"}</td>',
                            f'<td class="num">{eq.get("recursos", "")}</td>', f'<td class="num">{x.get("vitorias", 0)}</td>',
                            f'<td class="num">{x.get("pontos", 0):g}</td>']))
            cartoes.append(self.secao(eq["nome"], self._cartao_equipe(cid, eq["id"]) + self._tabela_pilotos(
                cid, state.pilotos_da_equipe(st, cid, eq["id"]), equipe=False), id_=eq["id"]))
        corpo = self.secao(t("Equipes"), self.tabela(
            [(t("Equipe"), ""), (t("País"), ""), (t("Chassis"), ""), (t("Motor"), ""), (t("Pilotos titulares"), ""),
             (t("Recursos"), "num"), (t("Vitórias"), "num"), (t("Pts"), "num")], linhas)) + "".join(cartoes)
        self.pagina(f"{cid}-equipes.html", f'{c["categoria"]["nome"]} {st["ano"]} – {t("Equipes")}', corpo)

    def _tabela_pilotos(self, cid, pilotos, equipe=True):
        st = self.st
        c = st["categorias"][cid]
        pil, _ = self.classificacao(cid)
        pts = {p["id"]: p for p in pil}
        linhas = []
        for p in pilotos:
            ct = p.get("contrato") or {}
            meu = ct and self.eh_usuario(ct.get("categoria"), ct.get("equipe"))
            nota = ratings.nota_geral_piloto(p, c["categoria"])
            x = pts.get(p["id"], {})
            if ct and ct.get("categoria") == cid:
                eq_html = self.link_equipe(cid, ct["equipe"])
                papel = t(ct["situacao"]) + self._marca(p)
                dur = (f'{ct["corridas"]} {t("corr.")}' if "corridas" in ct else f'{ct.get("temporadas", 1)} {t("temp.")}')
            else:
                eq_html, papel, dur = f'<i>{t("livre")}</i>', "", ""
            cels = [f'<td>{self.bandeira(p.get("nacionalidade"))}{e(p["nome"])}</td>',
                    f'<td>{e(t(p.get("nacionalidade", "")))}</td>', f'<td class="num">{p.get("idade", "")}</td>']
            if equipe:
                cels.append(f'<td>{eq_html}</td>')
            cels += [f'<td>{e(papel)}</td>', f'<td class="num">{dur}</td>',
                     f'<td class="num">{dinheiro(ct.get("valor_por_corrida")) if meu else ""}</td>',
                     f'<td class="num">{nota:.0f}</td>', f'<td class="num">{x.get("vitorias", 0)}</td>',
                     f'<td class="num">{x.get("pontos", 0):g}</td>']
            linhas.append(("usuario" if meu else "", cels))
        cab = [(t("Piloto"), ""), (t("Nacionalidade"), ""), (t("Idade"), "num")] + \
              ([(t("Equipe"), "")] if equipe else []) + \
              [(t("Função"), ""), (t("Contrato"), "num"), (t("Salário/corrida"), "num"), (t("Nota"), "num"),
               (t("Vitórias"), "num"), (t("Pts"), "num")]
        return self.tabela(cab, linhas)

    def pag_pilotos(self, cid):
        st = self.st
        c = st["categorias"][cid]
        com = [p for p in st["pilotos"].values() if (p.get("contrato") or {}).get("categoria") == cid]
        livres = [p for p in st["pilotos"].values() if not p.get("contrato")
                  and (p.get("categoria_atual") or p.get("categoria_origem")) == cid]
        ordem = {"principal": 0, "teste": 1}
        com.sort(key=lambda p: (self.equipe(cid, p["contrato"]["equipe"]) or {}).get("nome", "") +
                 str(ordem.get(p["contrato"]["situacao"], 2)) + p["nome"])
        livres.sort(key=lambda p: -ratings.nota_geral_piloto(p, c["categoria"]))
        corpo = (self.secao(t("Pilotos com contrato"), self._tabela_pilotos(cid, com))
                 + self.secao(t("Pilotos livres"), self._tabela_pilotos(cid, livres)))
        self.pagina(f"{cid}-pilotos.html", f'{c["categoria"]["nome"]} {st["ano"]} – {t("Pilotos")}', corpo)

    def pag_financas(self):
        st = self.st
        blocos = []
        for cid, eid in sorted(self.humanas):
            c = st["categorias"][cid]
            eq = c["equipes"][eid]
            hist = dict(c.get("historico_financas", {}).get(eid, {}))
            hist[str(st["ano"])] = eq["financas"]["ano"]
            anos = sorted(hist, key=int, reverse=True)
            chaves_r = list(dict.fromkeys(k for a in anos for k in hist[a]["receitas"]))
            chaves_d = list(dict.fromkeys(k for a in anos for k in hist[a]["despesas"]))
            cab = [("", "")] + [(f'{a}{" *" if a == str(st["ano"]) else ""}', "num") for a in anos]

            def linha(nome, valores, negrito=False):
                b0, b1 = ("<b>", "</b>") if negrito else ("", "")
                return ("", [f'<td>{b0}{e(nome)}{b1}</td>'] + [
                    f'<td class="num {"neg" if v < 0 else ""}">{b0}{dinheiro(v)}{b1}</td>' for v in valores])
            linhas = [linha(t("Receitas"), [sum(hist[a]["receitas"].values()) for a in anos], True)]
            linhas += [linha("   " + t(NOMES_RECEITAS.get(k, k)), [hist[a]["receitas"].get(k, 0) for a in anos])
                       for k in chaves_r]
            linhas += [linha(t("Despesas"), [sum(hist[a]["despesas"].values()) for a in anos], True)]
            linhas += [linha("   " + t(NOMES_DESPESAS.get(k, k)), [hist[a]["despesas"].get(k, 0) for a in anos])
                       for k in chaves_d]
            linhas += [linha(t("Balanço"), [sum(hist[a]["receitas"].values()) - sum(hist[a]["despesas"].values())
                                            for a in anos], True)]
            resumo = (f'<p>{t("Caixa")}: <b class="{"neg" if eq["financas"]["caixa"] < 0 else "pos"}">'
                      f'{dinheiro(eq["financas"]["caixa"])}</b> · * {t("temporada em andamento")}</p>')
            emp = eq.get("emprestimos") or []
            tab_emp = ""
            if emp:
                tab_emp = f'<p><b>{t("Empréstimos")}</b></p>' + self.tabela(
                    [(t("Valor"), "num"), (t("Saldo devedor"), "num"), (t("Parcela/corrida"), "num"),
                     (t("Parcelas restantes"), "num")],
                    [("", [f'<td class="num">{dinheiro(x.get("valor"))}</td>', f'<td class="num">{dinheiro(x.get("saldo"))}</td>',
                           f'<td class="num">{dinheiro(x.get("parcela"))}</td>',
                           f'<td class="num">{x.get("parcelas_restantes", "")}</td>']) for x in emp])
            blocos.append(self.secao(f'{t("Finanças")} – {eq["nome"]}', resumo + self.tabela(cab, linhas, False) + tab_emp))
        self.pagina("financas.html", t("Finanças"), "".join(blocos))

    def _noticias(self, n=None):
        """Como a lista de notícias do jogo: todas, com destaque só para as da(s) equipe(s) do jogador."""
        mostrar = list(reversed(self.st.get("noticias", [])))[:n] if n else list(reversed(self.st.get("noticias", [])))
        minhas = {eid for _, eid in self.humanas}

        def destaque(x):
            return x.get("tipo") == "usuario" and (x.get("equipe") is None or x["equipe"] in minhas)
        return "".join(f'<div class="noticia {"usuario" if destaque(x) else ""}">'
                       f'[{x["ano"]} {t("S")}{x["semana"]:02d}] {e(t(x["texto"]))}</div>' for x in mostrar)

    def pag_noticias(self):
        self.pagina("noticias.html", t("Notícias"), self.secao(t("Notícias"), self._noticias()))


def exportar(st, pasta):
    """Gera o site em `pasta` e devolve o caminho do index.html."""
    return Exportador(st, pasta).exportar()
