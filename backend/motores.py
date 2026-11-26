"""Escolha do motor de reconhecimento de alimentos.

Ordem padrão (MOTOR_VISAO=auto no .env):
  1. YOLOE local (backend/segmentacao.py): gratuito, roda no computador, com segmentação.
  2. Claude (backend/vision.py): opcional, precisa de ANTHROPIC_API_KEY e tem custo por uso.
  3. Manual: o operador marca os alimentos. A tela sempre informa qual foi o método.
"""
from . import segmentacao, vision
from .settings import MOTOR_VISAO

METODO = {"local": "ia_local", "claude": "ia_claude"}
NOMES = {"local": "IA local", "claude": "IA em nuvem (opcional)"}


def _disponivel(motor: str) -> bool:
    return segmentacao.disponivel() if motor == "local" else vision.ia_disponivel() if motor == "claude" else False


def motor_ativo() -> str | None:
    if MOTOR_VISAO in ("local", "claude"):
        return MOTOR_VISAO if _disponivel(MOTOR_VISAO) else None
    if MOTOR_VISAO == "manual":
        return None
    for m in ("local", "claude"):
        if _disponivel(m):
            return m
    return None


def metodo_valido(metodo: str) -> bool:
    """Um registro só pode ser marcado como reconhecido por IA se aquele motor estiver disponível."""
    return any(METODO[m] == metodo and _disponivel(m) for m in METODO)


def status() -> dict:
    ativo = motor_ativo()
    local, claude = segmentacao.status(), vision.status()
    if ativo == "local":
        msg = local["mensagem"]
    elif ativo == "claude":
        msg = claude["mensagem"] + " (Reconhecimento local não está ativo: " + local["mensagem"] + ")"
    elif MOTOR_VISAO == "manual":
        msg = "Reconhecimento automático desligado (MOTOR_VISAO=manual). Os alimentos são marcados pelo operador."
    else:
        msg = local["mensagem"] + " Enquanto isso, os alimentos são marcados manualmente pelo operador."
    return {
        "ia_disponivel": ativo is not None,
        "modo": "ia" if ativo else "manual",
        "motor_ativo": ativo,
        "motor": NOMES[ativo] if ativo else None,  # nome exibido na tela; o modelo técnico fica em "motores"
        "segmentacao": ativo == "local",
        "mensagem": msg,
        "motores": {"local": local, "claude": claude},
    }


def reconhecer(dados: bytes, tipo: str) -> dict:
    """Executa o motor ativo. Levanta segmentacao.ErroSegmentacao ou vision.ErroVisao."""
    ativo = motor_ativo()
    if ativo == "local":
        r = segmentacao.reconhecer(dados)
    else:
        r = vision.reconhecer(dados, tipo)
        # Mesmo formato do motor local: confiança baixa vira "Não identificado"
        r["regioes"] = [{
            "tipo": "alimento", "alimento": it["alimento"] if it["confianca"] != "baixa" else "Não identificado",
            "detalhe": None, "confianca_pct": None, "confianca": it["confianca"] if it["confianca"] != "baixa" else None,
            "identificado": it["confianca"] != "baixa", "regiao": it["regiao"], "poligono": [],
        } for it in r["itens"]]
        r["itens"] = [{"alimento": it["alimento"], "confianca": it["confianca"], "confianca_pct": None, "detalhes": []}
                      for it in r["itens"] if it["confianca"] != "baixa"]
        r.update(objetos=[], nao_identificados=sum(1 for g in r["regioes"] if not g["identificado"]), tempo_ms=None)
    r["metodo"] = METODO[ativo]
    return r


def preaquecer() -> None:
    """Carrega o modelo local em segundo plano ao iniciar o servidor (a 1ª foto fica rápida)."""
    if motor_ativo() == "local":
        try:
            segmentacao.carregar()
        except segmentacao.ErroSegmentacao:
            pass  # o status passa a mostrar o motivo
