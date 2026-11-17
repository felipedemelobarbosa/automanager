"""Sensibilidade do modelo a cada atributo, corrida após corrida.

Para um piloto do meio do pelotão (e o carro dele), cada atributo é posto em 30 e em 90 – o resto igual – e o
mesmo fim de semana completo (treinos, classificação, corrida) é simulado com as mesmas sementes nas duas
versões. Mede posição de largada, posição final, ritmo médio de corrida e abandonos.

Uso:  python tools/analise_atributos.py [n_corridas] [mista|rua|chuva]
"""
import copy
import os
import random
import statistics as S
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import state, db  # noqa: E402
from automanager.db import ATRIBUTOS_PILOTO, ATRIBUTOS_CHASSIS  # noqa: E402
from automanager.event.sessoes import Evento  # noqa: E402
from automanager.event.inscritos import montar_inscritos  # noqa: E402

CID = "formula_alfa"


def preparar(tipo):
    st = state.novo_jogo(db.arquivos_do_ano(2026))
    c = st["categorias"][CID]
    corridas = [e for e in c["calendario"] if e["especie"] == "corrida"]
    if tipo == "rua":
        pista = next(e for e in corridas if e["tipo_pista"] == "rua")
    else:
        pista = next(e for e in corridas if e["tipo_pista"] == "mista")
    pista = dict(pista, prob_chuva=1.0 if tipo == "chuva" else 0.0)
    cat = copy.deepcopy(c["categoria"])
    if tipo == "chuva":
        cat["clima"]["estabilidade_por_10min"] = 1.0
    return st, c, pista, cat


def rodar(st, c, pista, cat, alvo, mexer, seeds):
    grid, final, ritmo, dnf = [], [], [], 0
    for seed in seeds:
        ins = copy.deepcopy(montar_inscritos(st, CID, None, pista))
        for i in ins:
            i["piloto"]["forma"] = 0.0
        eu = next(i for i in ins if i["piloto"]["id"] == alvo)
        mexer(eu)
        ev = Evento(cat, pista, ins, random.Random(seed))
        if cat["clima"].get("estabilidade_por_10min") == 1.0:
            ev.clima.estado = "chuva_pesada"
        while ev.proxima_sessao():
            ev.sessao.iniciar()
            ev.sessao.simular_ate_o_fim()
        carro = next(x for x in ev.carros if x.id == alvo)
        grid.append(ev.grid.index(carro) + 1)
        pos = next(r["pos"] for r in ev.resultado_corrida if r["carro"] is carro)
        if carro.status != "fim":
            dnf += 1
        else:
            final.append(pos)
            ritmo.append(carro.tempo_total / max(1, carro.voltas))
    return S.mean(grid), (S.mean(final) if final else None), (S.mean(ritmo) if ritmo else None), dnf


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    tipo = sys.argv[2] if len(sys.argv) > 2 else "mista"
    so = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None     # ex.: classificacao,potencia
    st, c, pista, cat = preparar(tipo)
    ins = montar_inscritos(st, CID, None, pista)
    # piloto do meio do pelotão (pela nota geral)
    from automanager import ratings
    ordem = sorted(ins, key=lambda i: -ratings.nota_geral_piloto(i["piloto"], cat))
    alvo = ordem[len(ordem) // 2]["piloto"]["id"]
    nome = ordem[len(ordem) // 2]["piloto"]["nome"]
    seeds = list(range(100, 100 + n))
    print(f"Pista: {pista['nome']} ({tipo}) – piloto analisado: {nome} – {n} fins de semana por variante\n")
    print(f"{'atributo':28s} {'grid 30→90':>12s} {'final 30→90':>12s} {'ritmo s/volta (90−30)':>22s} {'abandonos 30/90':>16s}")
    linhas = []
    for grupo, attrs in (("piloto", ATRIBUTOS_PILOTO), ("chassis", ATRIBUTOS_CHASSIS), ("motor", ["potencia"])):
        for a in attrs:
            if so and a not in so and f"{grupo}.{a}" not in so:
                continue
            res = {}
            for v in (30, 90):
                def mexer(i, v=v, a=a, grupo=grupo):
                    if grupo == "piloto":
                        i["piloto"]["atributos"][a] = v
                    elif grupo == "chassis":
                        i["chassis"]["atributos"][a] = v
                    else:
                        i["motor"]["potencia"] = v
                res[v] = rodar(st, c, pista, cat, alvo, mexer, seeds)
            g30, f30, r30, d30 = res[30]
            g90, f90, r90, d90 = res[90]
            dr = (r90 - r30) if (r30 and r90) else None
            linhas.append((grupo, a, g30 - g90, (f30 or 0) - (f90 or 0), dr))
            print(f"{grupo + '.' + a:28s} {g30:5.1f}→{g90:<5.1f} {(f30 or 0):6.1f}→{(f90 or 0):<5.1f} "
                  f"{(dr if dr is not None else float('nan')):22.3f} {d30:>8d}/{d90:<7d}")
    print("\nMaior efeito na posição final (posições ganhas de 30 para 90):")
    for g, a, dg, df, dr in sorted(linhas, key=lambda x: -x[3])[:8]:
        print(f"  {g}.{a}: {df:+.1f} posições (grid {dg:+.1f})")


if __name__ == "__main__":
    main()
