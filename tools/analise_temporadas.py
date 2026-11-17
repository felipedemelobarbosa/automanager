"""Evolução em várias temporadas (todas as equipes com a IA): pilotos (curva de idade, aposentadoria, estreias),
chassis e motores (desenvolvimento), equipes (caixa, falências) e campeões.

Uso:  python tools/analise_temporadas.py [n_temporadas]
"""
import os
import random
import statistics as S
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automanager import state, db, routines, ratings, campeonato  # noqa: E402


def media(xs):
    return S.mean(xs) if xs else float("nan")


def foto(st):
    cats = {}
    for cid, c in st["categorias"].items():
        cat = c["categoria"]
        eqs = [e for e in c["equipes"].values() if e.get("ativa")]
        ch = [ratings.nota_geral_chassis(state.chassis_da_equipe(st, cid, e), cat) for e in eqs
              if state.chassis_da_equipe(st, cid, e)]
        mo = [state.motor_da_equipe(st, cid, e)["potencia"] for e in eqs if state.motor_da_equipe(st, cid, e)]
        caixa = [e["financas"]["caixa"] for e in eqs]
        pil = [p for p in st["pilotos"].values() if (p.get("contrato") or {}).get("categoria") == cid
               and p["contrato"]["situacao"] == "principal"]
        notas = [ratings.nota_geral_piloto(p, cat) for p in pil]
        cats[cid] = {"equipes": len(eqs), "chassis": ch, "motor": mo, "caixa": caixa, "notas_pil": notas}
    idades = {"≤24": [], "25-30": [], "31+": []}
    for p in st["pilotos"].values():
        n = sum(p["atributos"].values()) / len(p["atributos"])
        k = "≤24" if p.get("idade", 25) <= 24 else "25-30" if p["idade"] <= 30 else "31+"
        idades[k].append(n)
    return cats, idades


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    st = state.novo_jogo(db.arquivos_do_ano(2026))
    st["usuario"] = {"categoria": None, "equipe": None}          # todas as equipes com a IA
    rng = random.Random(2026)
    acompanhar = sorted(st["pilotos"].values(), key=lambda p: p.get("idade", 25))
    jovem, veterano = acompanhar[0]["id"], acompanhar[-1]["id"]
    traj = {jovem: [], veterano: []}
    ano0 = st["ano"]
    print(f"{'ano':>5} {'cat':12} {'eq':>3} {'chassis méd/mín/máx':>22} {'motor méd/mín/máx':>20} "
          f"{'pilotos méd/máx':>16} {'caixa médio (M)':>16}")
    falidas = 0
    while st["ano"] < ano0 + n:
        ano = st["ano"]
        while st["ano"] == ano:
            noticias = routines.avancar_semana(st, rng)
            falidas += sum(1 for x in noticias if x["texto"].startswith("FALÊNCIA"))
            if st["semana"] == 52:
                cats, idades = foto(st)
                for cid, d in cats.items():
                    nome = st["categorias"][cid]["categoria"]["nome"]
                    print(f"{ano:>5} {nome[:12]:12} {d['equipes']:>3} "
                          f"{media(d['chassis']):6.1f}/{min(d['chassis']):5.1f}/{max(d['chassis']):5.1f}  "
                          f"{media(d['motor']):6.1f}/{min(d['motor']):4.0f}/{max(d['motor']):4.0f}  "
                          f"{media(d['notas_pil']):6.1f}/{max(d['notas_pil']):5.1f}  "
                          f"{media(d['caixa']) / 1e6:12.1f}")
                print(f"      média dos atributos por idade: " + ", ".join(
                    f"{k}: {media(v):.1f} ({len(v)})" for k, v in idades.items()))
                for pid in traj:
                    p = st["pilotos"].get(pid) or st.get("aposentados", {}).get(pid)
                    if p:
                        traj[pid].append((ano, p.get("idade"), round(sum(p["atributos"].values()) / len(p["atributos"]), 1),
                                          "aposentado" if pid in st.get("aposentados", {}) else ""))
    print()
    print("Campeões:", ", ".join(f"{c['ano']} {c['categoria']}: {c['piloto']} ({c['equipe']})" for c in campeonato.campeoes(st)))
    print("Aposentados no período:", len(st.get("aposentados", {})), "| pilotos em atividade:", len(st["pilotos"]),
          "| falências:", falidas)
    for pid, t in traj.items():
        nome = (st["pilotos"].get(pid) or st["aposentados"][pid])["nome"]
        print(f"Trajetória de {nome}: " + "; ".join(f"{a} ({i} anos) média {m} {x}".strip() for a, i, m, x in t))


if __name__ == "__main__":
    main()
