"""PLATAFORMA CENTRAL · Visão geral, alertas, relatórios e configurações.

Responsável: Integrante 1 (integração).
Este é o ponto onde os dois pilares se encontram: os indicadores abaixo são
calculados diretamente das tabelas de cada módulo no mesmo banco.
"""
import csv
import io
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from pydantic import BaseModel, Field

from .. import auth, motores, seed
from ..db import agora, backup, config_gravar, get_conn, registrar_atividade, rows
from .feedback import resumo_cliente, rotulo
from .food import resumo_alimentar


def minutos_desde(iso: str, ref: datetime | None = None) -> float:
    ref = ref or datetime.now()
    return max(0.0, (ref - datetime.fromisoformat(iso)).total_seconds() / 60)

router = APIRouter(tags=["Plataforma central"])


def alertas(conn) -> list[dict]:
    lista = []
    for s in rows(conn.execute(
            "SELECT s.id, s.motivo, s.motivo_outro, s.criado_em, m.numero FROM solicitacoes_atendimento s"
            " JOIN mesas m ON m.id = s.mesa_id WHERE s.status = 'pendente' ORDER BY s.criado_em")):
        lista.append({"nivel": "alto", "modulo": "cliente", "mesa": s["numero"], "id": s["id"],
                      "texto": f"Mesa {s['numero']}: {rotulo(s['motivo'], s['motivo_outro'])} (há {minutos_desde(s['criado_em']):.0f} min)",
                      "desde": s["criado_em"], "acao": "cliente"})
    for r in rows(conn.execute(
            "SELECT x.id, x.categoria, x.categoria_outro, x.criado_em, m.numero FROM manifestacoes x LEFT JOIN mesas m ON m.id = x.mesa_id"
            " WHERE x.tipo = 'reclamacao' AND x.status = 'nova' ORDER BY x.criado_em")):
        onde = f"Mesa {r['numero']}" if r["numero"] else "Cliente"
        lista.append({"nivel": "medio", "modulo": "cliente", "mesa": r["numero"], "id": r["id"],
                      "texto": f"{onde}: reclamação sobre {(r['categoria_outro'] or r['categoria']).lower()}",
                      "desde": r["criado_em"], "acao": "cliente"})
    return lista


def origem_dos_dados(conn) -> dict:
    tabelas = ["registros_prato", "avaliacoes", "manifestacoes", "solicitacoes_atendimento"]
    demo = sum(conn.execute(f"SELECT COUNT(*) FROM {t} WHERE origem_dado = 'demo'").fetchone()[0] for t in tabelas)
    real = sum(conn.execute(f"SELECT COUNT(*) FROM {t} WHERE origem_dado = 'real'").fetchone()[0] for t in tabelas)
    return {"registros_demo": demo, "registros_reais": real}


def sinais_por_hora(conn, dias: int = 7) -> list[dict]:
    """Cruza os dois pilares por faixa horária: pratos e desperdício x satisfação e pedidos."""
    desde = (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds")
    horas = {h: {"hora": h, "pratos": 0, "desperdicio_pct": None, "avaliacoes": 0, "nota_media": None,
                 "reclamacoes": 0, "solicitacoes": 0} for h in range(11, 16)}
    acum = {h: {"s": 0.0, "t": 0.0, "n": 0} for h in horas}

    def hora(iso):
        return datetime.fromisoformat(iso).hour

    for r in rows(conn.execute(
            "SELECT p.criado_em, t.peso_g total, r.peso_g sobra FROM registros_prato p"
            " LEFT JOIN pesagens t ON t.registro_id = p.id AND t.tipo = 'total'"
            " LEFT JOIN pesagens r ON r.registro_id = p.id AND r.tipo = 'residual' WHERE p.criado_em >= ?", (desde,))):
        h = hora(r["criado_em"])
        if h in horas:
            horas[h]["pratos"] += 1
            if r["total"] and r["sobra"] is not None:
                acum[h]["s"] += r["sobra"]
                acum[h]["t"] += r["total"]
    for r in rows(conn.execute("SELECT criado_em, nota_geral FROM avaliacoes WHERE criado_em >= ?", (desde,))):
        h = hora(r["criado_em"])
        if h in horas:
            horas[h]["avaliacoes"] += 1
            acum[h]["n"] += r["nota_geral"]
    for r in conn.execute("SELECT criado_em FROM manifestacoes WHERE tipo = 'reclamacao' AND criado_em >= ?", (desde,)):
        if hora(r[0]) in horas:
            horas[hora(r[0])]["reclamacoes"] += 1
    for r in conn.execute("SELECT criado_em FROM solicitacoes_atendimento WHERE criado_em >= ?", (desde,)):
        if hora(r[0]) in horas:
            horas[hora(r[0])]["solicitacoes"] += 1
    for h, d in horas.items():
        if acum[h]["t"]:
            d["desperdicio_pct"] = round(acum[h]["s"] / acum[h]["t"] * 100, 1)
        if d["avaliacoes"]:
            d["nota_media"] = round(acum[h]["n"] / d["avaliacoes"], 2)
    return list(horas.values())


@router.get("/api/dashboard")
def dashboard(u: dict = auth.exigir("painel")):
    with get_conn() as conn:
        return {
            "gerado_em": agora(),
            "alimentar": resumo_alimentar(conn),
            "cliente": resumo_cliente(conn),
            "alertas": alertas(conn),
            "sinais_por_hora": sinais_por_hora(conn),
            "atividades": rows(conn.execute("SELECT * FROM atividades ORDER BY criado_em DESC, id DESC LIMIT 12")),
            "origem_dos_dados": origem_dos_dados(conn),
            "ia": motores.status(),
        }


@router.get("/api/alertas")
def listar_alertas(u: dict = auth.exigir("painel", "cliente_ver", "atendimento_ver")):
    with get_conn() as conn:
        return {"alertas": alertas(conn)}


@router.get("/api/cabecalho")
def cabecalho(u: dict = auth.exigir()):
    """Dados do topo do painel para qualquer colaborador logado (só o que o perfil pode ver)."""
    with get_conn() as conn:
        o = origem_dos_dados(conn)
        d = {"usuario": u, "dados_demonstrativos": o["registros_demo"] > 0}
        if auth.pode(u, "atendimento_ver"):
            d["pedidos_abertos"] = conn.execute(
                "SELECT COUNT(*) FROM solicitacoes_atendimento WHERE status = 'pendente'").fetchone()[0]
        if auth.pode(u, "cliente_ver"):
            d["reclamacoes_novas"] = conn.execute(
                "SELECT COUNT(*) FROM manifestacoes WHERE tipo = 'reclamacao' AND status = 'nova'").fetchone()[0]
        return d


@router.get("/api/atividades")
def atividades(limite: int = 50, modulo: str | None = None, u: dict = auth.exigir("painel", "relatorios")):
    sql, params = "SELECT * FROM atividades", []
    if modulo:
        sql += " WHERE modulo = ?"
        params.append(modulo)
    sql += " ORDER BY criado_em DESC, id DESC LIMIT ?"
    params.append(min(max(limite, 1), 500))
    with get_conn() as conn:
        return {"atividades": rows(conn.execute(sql, params))}


@router.get("/api/relatorios/sinais")
def relatorio_sinais(dias: int = 7, u: dict = auth.exigir("relatorios")):
    with get_conn() as conn:
        return {"dias": dias, "horas": sinais_por_hora(conn, max(1, min(dias, 90)))}


EXPORTS = {
    "pratos": "SELECT p.id, m.numero AS mesa, p.metodo_reconhecimento, p.criado_em, p.origem_dado,"
              " (SELECT peso_g FROM pesagens WHERE registro_id = p.id AND tipo = 'total') AS peso_total_g,"
              " (SELECT peso_g FROM pesagens WHERE registro_id = p.id AND tipo = 'residual') AS peso_residual_g,"
              " (SELECT origem FROM pesagens WHERE registro_id = p.id AND tipo = 'total') AS origem_peso,"
              " (SELECT GROUP_CONCAT(alimento || CASE sobrou WHEN 1 THEN ' (sobrou)' ELSE '' END, '; ')"
              "   FROM itens_reconhecidos WHERE registro_id = p.id) AS alimentos"
              " FROM registros_prato p LEFT JOIN mesas m ON m.id = p.mesa_id ORDER BY p.criado_em",
    "avaliacoes": "SELECT a.id, m.numero AS mesa, a.nota_geral, a.nota_atendimento, a.nota_comida, a.comentario,"
                  " a.criado_em, a.origem_dado FROM avaliacoes a LEFT JOIN mesas m ON m.id = a.mesa_id ORDER BY a.criado_em",
    "manifestacoes": "SELECT x.id, m.numero AS mesa, x.tipo, x.categoria, x.categoria_outro, x.texto, x.status, x.criado_em, x.origem_dado"
                     " FROM manifestacoes x LEFT JOIN mesas m ON m.id = x.mesa_id ORDER BY x.criado_em",
    "solicitacoes": "SELECT s.id, m.numero AS mesa, s.motivo, s.motivo_outro, s.status, s.criado_em, s.atendido_em, s.resolvido_em, s.origem_dado"
                    " FROM solicitacoes_atendimento s JOIN mesas m ON m.id = s.mesa_id ORDER BY s.criado_em",
}


@router.get("/api/relatorios/exportar/{nome}.csv")
def exportar(nome: str, u: dict = auth.exigir("relatorios")):
    if nome not in EXPORTS:
        raise HTTPException(404, "Relatório não encontrado")
    with get_conn() as conn:
        cur = conn.execute(EXPORTS[nome])
        cab = [c[0] for c in cur.description]
        dados = cur.fetchall()
    buf = io.StringIO()
    buf.write("﻿")  # BOM: o Excel abre os acentos corretamente
    w = csv.writer(buf, delimiter=";")
    w.writerow(cab)
    w.writerows(dados)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="codemeat_{nome}.csv"'})


# ---------- Configurações e modo demonstração ----------

class ConfigDemo(BaseModel):
    media_alvo: float = Field(ge=1, le=5)          # nota média desejada para as avaliações FICTÍCIAS
    avaliacoes: int = Field(ge=20, le=2000)        # quantas avaliações fictícias gerar
    dias: int = Field(ge=7, le=90)                 # período coberto pelo histórico fictício


@router.get("/api/sistema")
def sistema(u: dict = auth.exigir("configuracoes")):
    with get_conn() as conn:
        return {"ia": motores.status(), **origem_dos_dados(conn), "demo": seed.config_demo(conn),
                "media_por_origem": resumo_cliente(conn)["por_origem"]}


@router.post("/api/sistema/demo/recriar")
def recriar_demo(body: ConfigDemo | None = None, u: dict = auth.exigir("configuracoes")):
    """Gera de novo SÓ os dados demonstrativos. Registros reais e colaboradores não são tocados."""
    backup("antes-de-recriar-demo")
    with get_conn() as conn:
        if body:
            config_gravar(conn, "demo_media_alvo", round(body.media_alvo, 2))
            config_gravar(conn, "demo_avaliacoes", body.avaliacoes)
            config_gravar(conn, "demo_dias", body.dias)
        seed.remover_demo(conn)
        info = seed.popular(conn, **seed.config_demo(conn))
    return {"ok": True, **info}


@router.post("/api/sistema/demo/remover")
def remover_demo(u: dict = auth.exigir("configuracoes")):
    """Remove só os dados demonstrativos e mantém os registros reais."""
    backup("antes-de-remover-demo")
    with get_conn() as conn:
        seed.remover_demo(conn)
        registrar_atividade(conn, "sistema", "demo", "Dados demonstrativos removidos", None, agora())
    return {"ok": True}
