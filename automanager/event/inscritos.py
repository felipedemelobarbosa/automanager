"""Monta a lista de inscritos de um evento a partir do estado do jogo."""
from .. import state, contratos


def montar_inscritos(st, cid, equipe_usuario, pista=None):
    """pista: evento do calendário. Em corridas, pilotos com 'corridas_definidas' só entram nas corridas da lista;
    cada equipe alinha no máximo 'pilotos_principais_por_equipe' carros (escalados primeiro)."""
    c = st["categorias"][cid]
    limite = c["categoria"]["regras"].get("pilotos_principais_por_equipe") or 99
    evento_id = pista.get("id") if pista and pista.get("especie") == "corrida" else None
    inscritos = []
    for eq in c["equipes"].values():
        if not eq.get("ativa"):
            continue
        ch = state.chassis_da_equipe(st, cid, eq)
        mo = state.motor_da_equipe(st, cid, eq)
        if not ch or not mo:
            continue
        pilotos = [p for p in state.pilotos_da_equipe(st, cid, eq["id"])
                   if p["contrato"]["situacao"] == "principal" and contratos.escalado(p["contrato"], evento_id)
                   and not p.get("lesao")]                          # lesionado não corre
        if evento_id is not None:
            pilotos.sort(key=lambda p: 0 if p["contrato"].get("corridas_definidas") else 1)
        # mais titulares que carros (titular voltou de lesão): correm os contratos mais antigos
        pilotos.sort(key=lambda p: (0 if (evento_id is not None and p["contrato"].get("corridas_definidas")) else 1,
                                    p["contrato"].get("inicio_ano") or 0))
        for p in pilotos[:limite]:
            inscritos.append({"piloto": p, "equipe": eq, "chassis": ch, "motor": mo,
                              "usuario": eq["id"] == equipe_usuario})
    return inscritos
