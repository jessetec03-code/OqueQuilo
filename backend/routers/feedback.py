"""PILAR 2 · EXPERIÊNCIA DO CLIENTE

Responsável: Integrante 3.
Recebe o que o cliente envia pelo QR Code da mesa (avaliação, sugestão,
reclamação e pedido de atendimento) e entrega ao painel administrativo.
Nenhum dado pessoal é coletado: o cliente é anônimo e só a mesa é registrada.
A Bovinu'S trabalha com comanda, então não existe pedido de conta pelo QR Code.

As rotas do cliente são públicas (o cliente não faz login). As rotas do painel
exigem login de um colaborador com a permissão correspondente (backend/auth.py).
"""
import io
import socket
from datetime import date, datetime, timedelta

import segno
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .. import auth
from ..db import agora, get_conn, registrar_atividade, rows
from ..settings import PORTA, URL_PUBLICA

router = APIRouter(tags=["Experiência do Cliente"])

# Sem pedido de conta: o restaurante trabalha com comanda.
MOTIVOS_ATENDIMENTO = ["Chamar garçom", "Reposição no buffet", "Limpeza da mesa", "Outro"]
CATEGORIAS = ["Atendimento", "Comida", "Tempo de espera", "Limpeza", "Ambiente", "Preço", "Outro"]


class NovaAvaliacao(BaseModel):
    mesa: int | None = None  # número da mesa (vem do QR Code)
    nota_geral: int = Field(ge=1, le=5)
    nota_atendimento: int | None = Field(default=None, ge=1, le=5)
    nota_comida: int | None = Field(default=None, ge=1, le=5)
    comentario: str | None = Field(default=None, max_length=1000)


class NovaManifestacao(BaseModel):
    mesa: int | None = None
    tipo: str  # sugestao | reclamacao
    categoria: str
    categoria_outro: str | None = Field(default=None, max_length=60)  # obrigatório quando categoria = "Outro"
    texto: str = Field(min_length=3, max_length=1000)


class NovaSolicitacao(BaseModel):
    mesa: int
    motivo: str = "Chamar garçom"
    motivo_outro: str | None = Field(default=None, max_length=200)  # obrigatório quando motivo = "Outro"


class MudancaSolicitacao(BaseModel):
    status: str  # em_atendimento | resolvida


def _mesa_id(conn, numero: int | None, obrigatoria: bool = False) -> int | None:
    if numero is None:
        if obrigatoria:
            raise HTTPException(400, "Informe a mesa")
        return None
    r = conn.execute("SELECT id FROM mesas WHERE numero = ?", (numero,)).fetchone()
    if not r:
        raise HTTPException(404, f"Mesa {numero} não encontrada")
    return r["id"]


def _limpa(txt: str | None) -> str | None:
    txt = " ".join((txt or "").split())
    return txt or None


def _texto_outro(escolha: str, texto: str | None, campo: str) -> str | None:
    """Quando o cliente escolhe "Outro", a descrição livre é obrigatória."""
    if escolha != "Outro":
        return None
    t = _limpa(texto)
    if not t or len(t) < 3:
        raise HTTPException(400, f"Você escolheu \"Outro\": descreva {campo} (pelo menos 3 letras).")
    return t


def rotulo(escolha: str, outro: str | None) -> str:
    return f"Outro: {outro}" if escolha == "Outro" and outro else escolha


# ---------- Rotas usadas pela página do cliente (celular) ----------

@router.get("/api/mesas")
def listar_mesas():
    """Mesas cadastradas (cada uma tem o seu QR Code)."""
    with get_conn() as conn:
        return {"mesas": rows(conn.execute("SELECT id, numero, area FROM mesas ORDER BY numero"))}


@router.get("/api/cliente/opcoes")
def opcoes():
    return {"motivos_atendimento": MOTIVOS_ATENDIMENTO, "categorias": CATEGORIAS}


@router.post("/api/avaliacoes", status_code=201)
def criar_avaliacao(body: NovaAvaliacao):
    with get_conn() as conn:
        mesa_id = _mesa_id(conn, body.mesa)
        ts = agora()
        cur = conn.execute(
            "INSERT INTO avaliacoes (mesa_id, nota_geral, nota_atendimento, nota_comida, comentario, criado_em)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (mesa_id, body.nota_geral, body.nota_atendimento, body.nota_comida,
             _limpa(body.comentario), ts),
        )
        onde = f"Mesa {body.mesa}" if body.mesa else "Sem mesa"
        registrar_atividade(conn, "cliente", "avaliacao",
                            f"{onde}: nova avaliação, nota {body.nota_geral}/5", cur.lastrowid, ts)
    return {"id": cur.lastrowid, "mensagem": "Avaliação recebida. Obrigado!"}


@router.post("/api/manifestacoes", status_code=201)
def criar_manifestacao(body: NovaManifestacao):
    if body.tipo not in ("sugestao", "reclamacao"):
        raise HTTPException(400, "tipo deve ser 'sugestao' ou 'reclamacao'")
    if body.categoria not in CATEGORIAS:
        raise HTTPException(400, "Escolha sobre o que é a mensagem.")
    outro = _texto_outro(body.categoria, body.categoria_outro, "o assunto")
    with get_conn() as conn:
        mesa_id = _mesa_id(conn, body.mesa)
        ts = agora()
        cur = conn.execute(
            "INSERT INTO manifestacoes (mesa_id, tipo, categoria, categoria_outro, texto, criado_em) VALUES (?, ?, ?, ?, ?, ?)",
            (mesa_id, body.tipo, body.categoria, outro, body.texto.strip(), ts),
        )
        nome = "Reclamação" if body.tipo == "reclamacao" else "Sugestão"
        onde = f"Mesa {body.mesa}" if body.mesa else "Sem mesa"
        registrar_atividade(conn, "cliente", body.tipo, f"{onde}: {nome} ({rotulo(body.categoria, outro)})", cur.lastrowid, ts)
    return {"id": cur.lastrowid, "mensagem": f"{nome} registrada. A equipe vai analisar."}


@router.post("/api/solicitacoes", status_code=201)
def criar_solicitacao(body: NovaSolicitacao):
    if body.motivo not in MOTIVOS_ATENDIMENTO:
        raise HTTPException(400, "Escolha uma das opções de atendimento.")
    motivo = body.motivo
    outro = _texto_outro(motivo, body.motivo_outro, "do que você precisa")
    with get_conn() as conn:
        mesa_id = _mesa_id(conn, body.mesa, obrigatoria=True)
        aberta = conn.execute(
            "SELECT id FROM solicitacoes_atendimento WHERE mesa_id = ? AND motivo = ? AND status != 'resolvida'"
            " AND COALESCE(LOWER(motivo_outro), '') = COALESCE(LOWER(?), '')",
            (mesa_id, motivo, outro),
        ).fetchone()
        if aberta:
            return {"id": aberta["id"], "mensagem": "Seu pedido já foi recebido. A equipe está a caminho."}
        ts = agora()
        cur = conn.execute(
            "INSERT INTO solicitacoes_atendimento (mesa_id, motivo, motivo_outro, criado_em) VALUES (?, ?, ?, ?)",
            (mesa_id, motivo, outro, ts),
        )
        registrar_atividade(conn, "cliente", "solicitacao",
                            f"Mesa {body.mesa} pediu atendimento: {rotulo(motivo, outro)}", cur.lastrowid, ts)
    return {"id": cur.lastrowid, "mensagem": "Pedido enviado. A equipe foi avisada."}


# ---------- Rotas do painel administrativo ----------

ORIGENS = ("real", "demo")


def _origem(origem: str | None) -> str | None:
    """Filtro de origem dos dados: None (todos), 'real' ou 'demo'."""
    if origem in (None, "", "todos"):
        return None
    if origem not in ORIGENS:
        raise HTTPException(400, "origem deve ser 'todos', 'real' ou 'demo'")
    return origem


def resumo_cliente(conn, origem: str | None = None) -> dict:
    """Indicadores de satisfação. A média é sempre a média simples das notas gravadas:
    nada é ajustado aqui. O filtro de origem separa registros reais de demonstrativos."""
    f, p = ("WHERE origem_dado = ?", (origem,)) if origem else ("", ())
    e = (f + " AND") if f else "WHERE"
    a = conn.execute(
        f"SELECT COUNT(*) n, AVG(nota_geral) g, AVG(nota_atendimento) at, AVG(nota_comida) c,"
        f" SUM(nota_geral >= 4) pos FROM avaliacoes {f}", p).fetchone()
    dist = {i: 0 for i in range(1, 6)}
    for r in conn.execute(f"SELECT nota_geral, COUNT(*) n FROM avaliacoes {f} GROUP BY nota_geral", p):
        dist[r["nota_geral"]] = r["n"]
    man = {r["tipo"]: r["n"] for r in conn.execute(
        f"SELECT tipo, COUNT(*) n FROM manifestacoes {f} GROUP BY tipo", p)}
    novas = {r["tipo"]: r["n"] for r in conn.execute(
        f"SELECT tipo, COUNT(*) n FROM manifestacoes {e} status = 'nova' GROUP BY tipo", p)}
    sol = {r["status"]: r["n"] for r in conn.execute(
        f"SELECT status, COUNT(*) n FROM solicitacoes_atendimento {f} GROUP BY status", p)}
    tempos = [r[0] for r in conn.execute(
        "SELECT (julianday(COALESCE(atendido_em, resolvido_em)) - julianday(criado_em)) * 1440"
        f" FROM solicitacoes_atendimento {e} COALESCE(atendido_em, resolvido_em) IS NOT NULL", p)]
    categorias = rows(conn.execute(
        f"SELECT categoria, COUNT(*) n FROM manifestacoes {e} tipo = 'reclamacao'"
        " GROUP BY categoria ORDER BY n DESC", p))
    por_origem = {r["origem_dado"]: {"avaliacoes": r["n"], "media_geral": round(r["g"], 2) if r["g"] else None}
                  for r in conn.execute("SELECT origem_dado, COUNT(*) n, AVG(nota_geral) g FROM avaliacoes GROUP BY origem_dado")}
    r2 = lambda v: round(v, 2) if v is not None else None
    return {
        "origem": origem or "todos",
        "satisfeitos_pct": round(a["pos"] / a["n"] * 100, 1) if a["n"] else None,
        "por_origem": {o: por_origem.get(o, {"avaliacoes": 0, "media_geral": None}) for o in ORIGENS},
        "avaliacoes": a["n"],
        "media_geral": r2(a["g"]),
        "media_atendimento": r2(a["at"]),
        "media_comida": r2(a["c"]),
        "distribuicao": dist,
        "sugestoes": man.get("sugestao", 0),
        "reclamacoes": man.get("reclamacao", 0),
        "sugestoes_novas": novas.get("sugestao", 0),
        "reclamacoes_novas": novas.get("reclamacao", 0),
        "reclamacoes_por_categoria": categorias,
        "solicitacoes_pendentes": sol.get("pendente", 0),
        "solicitacoes_em_atendimento": sol.get("em_atendimento", 0),
        "solicitacoes_resolvidas": sol.get("resolvida", 0),
        "tempo_resposta_medio_min": round(sum(tempos) / len(tempos), 1) if tempos else None,
    }


@router.get("/api/cliente/resumo")
def resumo(origem: str | None = None, u: dict = auth.exigir("cliente_ver")):
    with get_conn() as conn:
        return resumo_cliente(conn, _origem(origem))


def satisfacao_por_periodo(conn, dias: int = 30, origem: str | None = None) -> dict:
    """Indicadores de satisfação por dia e por período (hoje, 7 dias, 30 dias e total)."""
    f, p = (" AND origem_dado = ?", (origem,)) if origem else ("", ())
    hoje = date.today()
    inicio = hoje - timedelta(days=dias - 1)
    serie = {(inicio + timedelta(days=i)).isoformat(): {"data": (inicio + timedelta(days=i)).isoformat(), "avaliacoes": 0,
             "nota_media": None, "satisfeitos_pct": None, "reclamacoes": 0, "solicitacoes": 0} for i in range(dias)}
    for r in conn.execute(
            "SELECT substr(criado_em, 1, 10) d, COUNT(*) n, AVG(nota_geral) g, SUM(nota_geral >= 4) pos FROM avaliacoes"
            f" WHERE criado_em >= ?{f} GROUP BY d", (inicio.isoformat(), *p)):
        if r["d"] in serie:
            serie[r["d"]].update(avaliacoes=r["n"], nota_media=round(r["g"], 2), satisfeitos_pct=round(r["pos"] / r["n"] * 100, 1))
    for tabela, campo, extra in (("manifestacoes", "reclamacoes", " AND tipo = 'reclamacao'"),
                                 ("solicitacoes_atendimento", "solicitacoes", "")):
        for r in conn.execute(f"SELECT substr(criado_em, 1, 10) d, COUNT(*) n FROM {tabela}"
                              f" WHERE criado_em >= ?{extra}{f} GROUP BY d", (inicio.isoformat(), *p)):
            if r["d"] in serie:
                serie[r["d"]][campo] = r["n"]

    def periodo(nome: str, desde: date | None) -> dict:
        w, q = ("WHERE criado_em >= ?" + f, (desde.isoformat(), *p)) if desde else (("WHERE 1=1" + f), p)
        a = conn.execute(f"SELECT COUNT(*) n, AVG(nota_geral) g, SUM(nota_geral >= 4) pos FROM avaliacoes {w}", q).fetchone()
        rec = conn.execute(f"SELECT COUNT(*) FROM manifestacoes {w} AND tipo = 'reclamacao'", q).fetchone()[0]
        sol = conn.execute(f"SELECT COUNT(*) FROM solicitacoes_atendimento {w}", q).fetchone()[0]
        return {"periodo": nome, "avaliacoes": a["n"], "nota_media": round(a["g"], 2) if a["g"] else None,
                "satisfeitos_pct": round(a["pos"] / a["n"] * 100, 1) if a["n"] else None,
                "reclamacoes": rec, "solicitacoes": sol}

    return {
        "dias": dias, "origem": origem or "todos", "serie": list(serie.values()),
        "periodos": [periodo("Hoje", hoje), periodo("Últimos 7 dias", hoje - timedelta(days=6)),
                     periodo("Últimos 30 dias", hoje - timedelta(days=29)), periodo("Todo o histórico", None)],
    }


@router.get("/api/cliente/periodo")
def periodo(dias: int = 30, origem: str | None = None, u: dict = auth.exigir("cliente_ver")):
    with get_conn() as conn:
        return satisfacao_por_periodo(conn, max(7, min(dias, 90)), _origem(origem))


@router.get("/api/avaliacoes")
def listar_avaliacoes(limite: int = 100, origem: str | None = None, u: dict = auth.exigir("cliente_ver")):
    origem = _origem(origem)
    with get_conn() as conn:
        return {"avaliacoes": rows(conn.execute(
            "SELECT a.*, m.numero AS mesa FROM avaliacoes a LEFT JOIN mesas m ON m.id = a.mesa_id"
            + (" WHERE a.origem_dado = ?" if origem else "")
            + " ORDER BY a.criado_em DESC, a.id DESC LIMIT ?", ((origem,) if origem else ()) + (min(limite, 500),)))}


@router.get("/api/manifestacoes")
def listar_manifestacoes(tipo: str | None = None, limite: int = 100, origem: str | None = None,
                         u: dict = auth.exigir("cliente_ver")):
    origem = _origem(origem)
    sql = ("SELECT x.*, m.numero AS mesa FROM manifestacoes x LEFT JOIN mesas m ON m.id = x.mesa_id WHERE 1=1")
    params: list = []
    if tipo:
        sql += " AND x.tipo = ?"
        params.append(tipo)
    if origem:
        sql += " AND x.origem_dado = ?"
        params.append(origem)
    sql += " ORDER BY x.criado_em DESC, x.id DESC LIMIT ?"
    params.append(min(limite, 500))
    with get_conn() as conn:
        return {"manifestacoes": rows(conn.execute(sql, params))}


@router.post("/api/manifestacoes/{item_id}/resolver")
def resolver_manifestacao(item_id: int, u: dict = auth.exigir("cliente_gerenciar")):
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM manifestacoes WHERE id = ?", (item_id,)).fetchone()
        if not r:
            raise HTTPException(404, "Registro não encontrado")
        conn.execute("UPDATE manifestacoes SET status = 'resolvida' WHERE id = ?", (item_id,))
        nome = "Reclamação" if r["tipo"] == "reclamacao" else "Sugestão"
        registrar_atividade(conn, "cliente", "manifestacao_resolvida", f"{nome} #{item_id} marcada como tratada", item_id)
    return {"ok": True}


@router.get("/api/solicitacoes")
def listar_solicitacoes(abertas: bool = False, limite: int = 100, u: dict = auth.exigir("atendimento_ver")):
    sql = ("SELECT s.*, m.numero AS mesa FROM solicitacoes_atendimento s JOIN mesas m ON m.id = s.mesa_id")
    if abertas:
        sql += " WHERE s.status != 'resolvida'"
    sql += " ORDER BY CASE s.status WHEN 'pendente' THEN 0 WHEN 'em_atendimento' THEN 1 ELSE 2 END, s.criado_em DESC LIMIT ?"
    with get_conn() as conn:
        return {"solicitacoes": rows(conn.execute(sql, (min(limite, 500),)))}


@router.post("/api/solicitacoes/{item_id}/status")
def mudar_solicitacao(item_id: int, body: MudancaSolicitacao, u: dict = auth.exigir("atendimento_atualizar")):
    if body.status not in ("em_atendimento", "resolvida"):
        raise HTTPException(400, "status deve ser 'em_atendimento' ou 'resolvida'")
    with get_conn() as conn:
        s = conn.execute(
            "SELECT s.*, m.numero FROM solicitacoes_atendimento s JOIN mesas m ON m.id = s.mesa_id WHERE s.id = ?",
            (item_id,)).fetchone()
        if not s:
            raise HTTPException(404, "Solicitação não encontrada")
        ts = agora()
        if body.status == "em_atendimento":
            conn.execute("UPDATE solicitacoes_atendimento SET status = ?, atendido_em = COALESCE(atendido_em, ?) WHERE id = ?",
                         (body.status, ts, item_id))
            desc = f"Mesa {s['numero']}: atendimento iniciado por {u['nome']} ({rotulo(s['motivo'], s['motivo_outro'])})"
        else:
            conn.execute("UPDATE solicitacoes_atendimento SET status = ?, atendido_em = COALESCE(atendido_em, ?), resolvido_em = ? WHERE id = ?",
                         (body.status, ts, ts, item_id))
            desc = f"Mesa {s['numero']}: pedido resolvido por {u['nome']} ({rotulo(s['motivo'], s['motivo_outro'])})"
        registrar_atividade(conn, "cliente", "solicitacao_" + body.status, desc, item_id, ts)
    return {"ok": True}


# ---------- QR Code ----------

def ip_rede_local() -> str:
    """Descobre o IP do computador na rede local (para o celular acessar)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # não envia nada, só escolhe a interface
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def url_base(request: Request | None = None) -> str:
    if URL_PUBLICA:
        return URL_PUBLICA
    host = request.url.hostname if request else None
    if host and host not in ("localhost", "127.0.0.1", "0.0.0.0"):
        porta = request.url.port
        return f"{request.url.scheme}://{host}" + (f":{porta}" if porta else "")
    return f"http://{ip_rede_local()}:{PORTA}"


@router.get("/api/qrcode/info")
def qr_info(request: Request, u: dict = auth.exigir()):
    base = url_base(request)
    return {"url_base": base, "exemplo": f"{base}/cliente/?mesa=1", "equipe": f"{base}/equipe/",
            "rede_local": base.startswith("http://") and not URL_PUBLICA}


@router.get("/api/qrcode/{numero}.svg")
def qr_mesa(numero: int, request: Request):
    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM mesas WHERE numero = ?", (numero,)).fetchone():
            raise HTTPException(404, "Mesa não encontrada")
    url = f"{url_base(request)}/cliente/?mesa={numero}"
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="svg", scale=8, border=2, dark="#121417")
    return Response(buf.getvalue(), media_type="image/svg+xml")
