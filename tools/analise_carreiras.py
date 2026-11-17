"""Simula várias temporadas (todas as equipes com a IA) e mede:
  - evolução dos atributos dos pilotos ao longo da carreira (por idade), na estreia e na aposentadoria;
  - movimentação de pilotos entre categorias do mesmo tier e de tiers diferentes.

Uso:  python tools/analise_carreiras.py [temporadas] [--gama] [--semente N]
  --gama  acrescenta, só para a simulação, uma 3ª categoria ("Fórmula Gama", tier 2, cópia da Beta com
          equipes e pilotos próprios), para haver duas categorias no mesmo tier.
"""
import collections
import copy
import json
import os
import random
import statistics as S
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import state, db, routines, ratings  # noqa: E402
from automanager.util import PASTA_DATABASE  # noqa: E402


def media(a):
    return sum(a.values()) / len(a)


def categoria_gama(pasta, rng):
    """Cópia da Fórmula Beta com ids, nomes de equipes e pilotos próprios (tier 2)."""
    beta = next(p for p in db.arquivos_do_ano(2026) if "beta" in p)
    with open(beta, encoding="utf-8") as f:
        d = json.load(f)
    with open(os.path.join(PASTA_DATABASE, "nomes.json"), encoding="utf-8") as f:
        nomes = json.load(f)["nacionalidades"]
    d["categoria"].update({"id": "formula_gama", "nome": "Fórmula Gama"})
    ids = {e["id"]: "g_" + e["id"] for e in d["equipes"]}

    def troca(v):
        if isinstance(v, dict):
            return {k: (ids.get(x, x) if k == "equipe" and isinstance(x, str) else troca(x)) for k, x in v.items()}
        if isinstance(v, list):
            return [troca(x) for x in v]
        return v
    d = troca(d)
    for e in d["equipes"]:
        e["id"] = ids[e["id"]]
        e["nome"] = e["nome"].split()[0] + " Gama"
    usados = set()
    for p in d["pilotos"]:
        nac = p["nacionalidade"] if p["nacionalidade"] in nomes else rng.choice(list(nomes))
        while True:
            n = f"{rng.choice(nomes[nac]['nomes'])} {rng.choice(nomes[nac]['sobrenomes'])}"
            if n not in usados:
                break
        usados.add(n)
        p["nome"] = n
        p["idade"] = max(17, p.get("idade", 22) + rng.randint(-2, 2))
        p["atributos"] = {k: max(20, min(95, v + rng.randint(-5, 5))) for k, v in p["atributos"].items()}
        for k in ("ano_pico", "potencial", "ano_aposentadoria"):
            p.pop(k, None)
    caminho = os.path.join(pasta, "formula_gama_2026.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    return caminho


def categoria_de(p):
    ct = p.get("contrato") or {}
    return ct.get("categoria")


def main():
    args = sys.argv[1:]
    n = int(args[0]) if args and args[0].isdigit() else 8
    semente = int(args[args.index("--semente") + 1]) if "--semente" in args else 7
    rng = random.Random(semente)
    arquivos = list(db.arquivos_do_ano(2026))
    tmp = tempfile.mkdtemp()
    if "--gama" in args:
        arquivos.append(categoria_gama(tmp, rng))
    st = state.novo_jogo(arquivos, semente=semente)
    st["usuario"] = {"categoria": None, "equipe": None}
    cats = st["categorias"]
    tier = {cid: c["categoria"].get("tier", 1) for cid, c in cats.items()}
    nome = {cid: c["categoria"]["nome"] for cid, c in cats.items()}
    ano0 = st["ano"]

    historico = collections.defaultdict(list)    # pid -> [(ano, idade, media, categoria)]
    estreias, aposentadorias, transicoes = [], [], []
    vistos = set(st["pilotos"])
    anterior = {pid: categoria_de(p) for pid, p in st["pilotos"].items()}
    nota_cat = {}

    def foto():
        for pid, p in st["pilotos"].items():
            historico[pid].append((st["ano"], p.get("idade"), media(p["atributos"]), categoria_de(p)))
        for cid, c in cats.items():
            pil = [p for p in st["pilotos"].values() if categoria_de(p) == cid and p["contrato"]["situacao"] == "principal"]
            if pil:
                nota_cat[(st["ano"], cid)] = S.mean(ratings.nota_geral_piloto(p, c["categoria"]) for p in pil)

    foto()
    while st["ano"] < ano0 + n:
        ano = st["ano"]
        while st["ano"] == ano:
            routines.avancar_semana(st, rng)
        # início da nova temporada: aposentadorias, estreias, mudanças de categoria
        for pid, p in st.get("aposentados", {}).items():
            if p.get("aposentado_em") == st["ano"] and not p.get("_contado"):
                p["_contado"] = True
                h = historico.get(pid) or []
                pico = max(h, key=lambda x: x[2]) if h else None
                aposentadorias.append({"idade": p.get("idade"), "media": media(p["atributos"]),
                                       "categoria": anterior.get(pid), "pico_idade": pico[1] if pico else None,
                                       "pico_media": pico[2] if pico else None,
                                       "motivo": "idade" if p.get("ano_aposentadoria", 9999) <= st["ano"] else "sem equipe"})
        for pid, p in st["pilotos"].items():
            if pid not in vistos:
                vistos.add(pid)
                origem = "fictício" if p.get("ficticio") else ("arquivo de novos" if pid.startswith("novos") else "outro")
                estreias.append({"ano": st["ano"], "idade": p.get("idade"), "media": media(p["atributos"]),
                                 "potencial": p.get("potencial"), "origem": origem,
                                 "categoria": p.get("categoria_origem")})
        # semana 2: contratos da nova temporada já valem
        routines.avancar_semana(st, rng)
        atual = {pid: categoria_de(p) for pid, p in st["pilotos"].items()}
        for pid, cid in atual.items():
            antes = anterior.get(pid)
            if cid and antes and cid != antes:
                p = st["pilotos"][pid]
                tipo = "sobe de tier" if tier[cid] < tier[antes] else "desce de tier" if tier[cid] > tier[antes] \
                    else "mesmo tier"
                transicoes.append({"ano": st["ano"], "tipo": tipo, "de": antes, "para": cid, "idade": p.get("idade"),
                                   "nota": ratings.nota_geral_piloto(p, cats[cid]["categoria"])})
        anterior = atual
        foto()

    # ------------------------------------------------------------ relatório
    print(f"{n} temporadas a partir de {ano0}; categorias: " + ", ".join(f"{nome[c]} (tier {tier[c]})" for c in cats))
    print("\n== 1. Evolução ao longo da carreira (variação média anual da média dos atributos, por idade)")
    delta = collections.defaultdict(list)
    for h in historico.values():
        for (a1, i1, m1, _), (a2, i2, m2, _) in zip(h, h[1:]):
            if i1 is not None and a2 == a1 + 1:
                delta[i1].append(m2 - m1)
    faixas = [(17, 20), (21, 23), (24, 26), (27, 29), (30, 32), (33, 35), (36, 45)]
    for lo, hi in faixas:
        v = [x for i in range(lo, hi + 1) for x in delta.get(i, [])]
        if v:
            print(f"   {lo:>2}-{hi:<2} anos: {S.mean(v):+5.2f} pontos/ano  (n={len(v)})")
    picos = [max(h, key=lambda x: x[2])[1] for h in historico.values() if len(h) >= 4]
    print(f"   idade no melhor momento observado (pilotos com 4+ temporadas): média {S.mean(picos):.1f}, "
          f"mediana {S.median(picos)}")

    print("\n== 2. Estreias")
    por_origem = collections.defaultdict(list)
    for e in estreias:
        por_origem[e["origem"]].append(e)
    for o, es in por_origem.items():
        print(f"   {o}: {len(es)} ({len(es) / n:.1f}/temporada), idade média {S.mean(e['idade'] for e in es):.1f}, "
              f"atributos {S.mean(e['media'] for e in es):.1f}, potencial {S.mean(e['potencial'] for e in es if e['potencial']):.1f}")
    tiers_entrada = collections.Counter(nome.get(e["categoria"], e["categoria"]) for e in estreias)
    print(f"   entram por: {dict(tiers_entrada)}")

    print("\n== 3. Aposentadorias")
    if aposentadorias:
        print(f"   {len(aposentadorias)} ({len(aposentadorias) / n:.1f}/temporada); motivos "
              f"{dict(collections.Counter(a['motivo'] for a in aposentadorias))}")
        idades = [a["idade"] for a in aposentadorias if a["motivo"] == "idade"]
        if idades:
            print(f"   por idade: idade média {S.mean(idades):.1f} (mín {min(idades)}, máx {max(idades)})")
        sem = [a for a in aposentadorias if a["motivo"] == "sem equipe"]
        if sem:
            print(f"   sem equipe: idade média {S.mean(a['idade'] for a in sem):.1f}, atributos {S.mean(a['media'] for a in sem):.1f}")
        com_pico = [a for a in aposentadorias if a["pico_media"]]
        print(f"   atributos na aposentadoria {S.mean(a['media'] for a in aposentadorias):.1f} "
              f"(no melhor momento: {S.mean(a['pico_media'] for a in com_pico):.1f}, aos {S.mean(a['pico_idade'] for a in com_pico):.1f} anos)")

    print("\n== 4. População e nível por categoria (titulares, nota geral média)")
    for cid in cats:
        linha = [f"{a}: {nota_cat[(a, cid)]:.1f}" for a in range(ano0, ano0 + n + 1) if (a, cid) in nota_cat]
        print(f"   {nome[cid]:13} " + " | ".join(linha))
    livres = sum(1 for p in st["pilotos"].values() if not p.get("contrato"))
    print(f"   pilotos em atividade no fim: {len(st['pilotos'])} (sem contrato: {livres})")

    print("\n== 5. Movimentação entre categorias (mudança de categoria de uma temporada para a outra)")
    cont = collections.Counter(t["tipo"] for t in transicoes)
    for tipo in ("sobe de tier", "desce de tier", "mesmo tier"):
        ts = [t for t in transicoes if t["tipo"] == tipo]
        if ts:
            rotas = collections.Counter(f"{nome[t['de']]} → {nome[t['para']]}" for t in ts)
            print(f"   {tipo}: {len(ts)} ({len(ts) / n:.1f}/temporada), idade média {S.mean(t['idade'] for t in ts):.1f}, "
                  f"nota no destino {S.mean(t['nota'] for t in ts):.1f}; rotas {dict(rotas)}")
        else:
            print(f"   {tipo}: 0")
    voltas = collections.Counter()
    for pid, h in historico.items():
        cats_h = [c for _, _, _, c in h]
        for i, c in enumerate(cats_h):
            if c and i >= 2 and c not in cats_h[i - 1:i] and c in cats_h[:i - 1]:
                ultima = max(j for j in range(i - 1) if cats_h[j] == c)
                voltas[i - ultima - 1] += 1
    aposent = sum(1 for p in list(st["pilotos"].values()) + list(st.get("aposentados", {}).values()) if p.get("retornou_em"))
    print(f"   voltam a uma categoria depois de 1+ temporada fora: {sum(voltas.values())} "
          f"(temporadas fora: {dict(sorted(voltas.items()))}); aposentados que voltaram às pistas: {aposent}")
    cal = st.get("calibracao_pilotos") or {}
    print(f"   calibração dos pilotos: referência {cal.get('ref')}, ajuste acumulado do potencial "
          f"{cal.get('ajuste')}, último desvio {cal.get('ultimo_desvio')}")
    print(f"   médias das categorias (titulares): " + ", ".join(
        f"{nome[c]} {S.mean(v for (a, cc), v in nota_cat.items() if cc == c):.1f}" for c in cats))


if __name__ == "__main__":
    main()
