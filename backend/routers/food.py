"""PILAR 1 · RECONHECIMENTO INTELIGENTE DE ALIMENTOS

Responsável: Integrante 1.
Fluxo em duas etapas, como na proposta original:
  1. Prato servido: foto (câmera ou upload) + reconhecimento e segmentação dos
     alimentos (YOLOE local; Claude opcional) + peso total do prato.
  2. Prato devolvido: peso residual + marcação de quais alimentos sobraram.
Cada peso é salvo com a sua origem (informado, balança, estimativa da IA ou
simulado), para que nenhum número apareça como medição sem ser.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from .. import auth, motores, segmentacao, vision
from ..db import UPLOAD_DIR, agora, get_conn, registrar_atividade, rows

router = APIRouter(prefix="/api/alimentar", tags=["Reconhecimento de Alimentos"])

TIPOS_IMAGEM = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_BYTES = 10 * 1024 * 1024
ORIGENS_PESO = ("informado", "balanca", "simulado")


class Item(BaseModel):
    alimento: str = Field(min_length=1, max_length=60)
    origem: str = "manual"          # ia | manual
    confianca: str | None = None    # alta | media | baixa
    sobrou: bool = False


class NovoRegistro(BaseModel):
    mesa: int | None = None
    imagem: str | None = None
    metodo_reconhecimento: str = "manual"   # ia_local | ia_claude | manual
    itens: list[Item] = Field(min_length=1)
    peso_total_g: float | None = Field(default=None, gt=0, le=5000)
    peso_residual_g: float | None = Field(default=None, ge=0, le=5000)
    origem_peso: str = "informado"
    observacao: str | None = Field(default=None, max_length=500)


class Retorno(BaseModel):
    peso_residual_g: float = Field(ge=0, le=5000)
    origem_peso: str = "informado"
    itens_sobra: list[int] = []   # ids de itens_reconhecidos que sobraram


@router.get("/status")
def status_ia(u: dict = auth.exigir()):
    return {**motores.status(), "catalogo": vision.CATALOGO, "categorias": segmentacao.CATEGORIAS}


@router.post("/analisar")
async def analisar(imagem: UploadFile = File(...), u: dict = auth.exigir("alimentos_registrar")):
    """Recebe a foto do prato (câmera ou upload), salva e reconhece os alimentos com o motor ativo."""
    tipo = (imagem.content_type or "").lower()
    if tipo not in TIPOS_IMAGEM:
        raise HTTPException(400, "Formato não aceito. Envie uma foto JPG, PNG ou WEBP.")
    dados = await imagem.read()
    if not dados:
        raise HTTPException(400, "Arquivo vazio.")
    if len(dados) > MAX_BYTES:
        raise HTTPException(400, "Imagem maior que 10 MB. Use uma foto menor.")
    try:
        segmentacao.abrir_imagem(dados)  # garante que é uma imagem de verdade antes de salvar
    except segmentacao.ErroSegmentacao as e:
        raise HTTPException(400, str(e)) from e
    nome = f"{uuid.uuid4().hex}{TIPOS_IMAGEM[tipo]}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / nome).write_bytes(dados)

    st = motores.status()
    resposta = {"imagem": nome, "imagem_url": f"/uploads/{nome}", **st,
                "itens": [], "regioes": [], "objetos": [], "descricao": None, "erro": None, "metodo": "manual"}
    if not st["ia_disponivel"]:
        return resposta
    try:
        resposta.update(await run_in_threadpool(motores.reconhecer, dados, tipo))
    except (vision.ErroVisao, segmentacao.ErroSegmentacao) as e:
        resposta.update(erro=str(e), modo="manual", metodo="manual")
    except Exception as e:  # falha inesperada do modelo: não derruba o fluxo, cai para o manual
        resposta.update(erro=f"Falha no reconhecimento ({type(e).__name__}). Marque os alimentos manualmente.",
                        modo="manual", metodo="manual")
    return resposta


@router.post("/registros", status_code=201)
def criar_registro(body: NovoRegistro, u: dict = auth.exigir("alimentos_registrar")):
    if body.origem_peso not in ORIGENS_PESO:
        raise HTTPException(400, f"origem_peso deve ser: {', '.join(ORIGENS_PESO)}")
    if body.peso_total_g and body.peso_residual_g and body.peso_residual_g > body.peso_total_g:
        raise HTTPException(400, "O peso residual não pode ser maior que o peso total.")
    metodo = body.metodo_reconhecimento
    if not body.imagem or not motores.metodo_valido(metodo):
        metodo = "manual"  # sem foto ou sem o motor de IA disponível, não houve reconhecimento por IA
    if body.imagem and not (UPLOAD_DIR / body.imagem).is_file():
        raise HTTPException(400, "Imagem não encontrada. Envie a foto novamente.")
    with get_conn() as conn:
        mesa_id = None
        if body.mesa is not None:
            r = conn.execute("SELECT id FROM mesas WHERE numero = ?", (body.mesa,)).fetchone()
            if not r:
                raise HTTPException(404, f"Mesa {body.mesa} não encontrada")
            mesa_id = r["id"]
        ts = agora()
        cur = conn.execute(
            "INSERT INTO registros_prato (mesa_id, imagem, metodo_reconhecimento, observacao, criado_em)"
            " VALUES (?, ?, ?, ?, ?)",
            (mesa_id, body.imagem, metodo, (body.observacao or "").strip() or None, ts),
        )
        rid = cur.lastrowid
        vistos = set()
        for it in body.itens:
            nome = it.alimento.strip()
            if nome.lower() in vistos:
                continue
            vistos.add(nome.lower())
            origem = "ia" if it.origem == "ia" and metodo != "manual" else "manual"
            conn.execute(
                "INSERT INTO itens_reconhecidos (registro_id, alimento, confianca, origem, sobrou) VALUES (?, ?, ?, ?, ?)",
                (rid, nome, it.confianca if origem == "ia" else None, origem, int(it.sobrou)),
            )
        if body.peso_total_g:
            conn.execute("INSERT INTO pesagens (registro_id, tipo, peso_g, origem, criado_em) VALUES (?, 'total', ?, ?, ?)",
                         (rid, body.peso_total_g, body.origem_peso, ts))
        if body.peso_residual_g is not None:
            conn.execute("INSERT INTO pesagens (registro_id, tipo, peso_g, origem, criado_em) VALUES (?, 'residual', ?, ?, ?)",
                         (rid, body.peso_residual_g, body.origem_peso, ts))
        peso = f", {body.peso_total_g:.0f} g" if body.peso_total_g else ""
        registrar_atividade(conn, "alimentar", "registro",
                            f"Prato #{rid} registrado: {len(vistos)} alimento(s){peso}", rid, ts)
    return {"id": rid}


@router.post("/registros/{rid}/retorno")
def registrar_retorno(rid: int, body: Retorno, u: dict = auth.exigir("alimentos_registrar")):
    """Etapa 2: o prato volta do salão e o restaurante registra a sobra."""
    if body.origem_peso not in ORIGENS_PESO:
        raise HTTPException(400, f"origem_peso deve ser: {', '.join(ORIGENS_PESO)}")
    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM registros_prato WHERE id = ?", (rid,)).fetchone():
            raise HTTPException(404, "Registro não encontrado")
        total = conn.execute("SELECT peso_g FROM pesagens WHERE registro_id = ? AND tipo = 'total'", (rid,)).fetchone()
        if total and body.peso_residual_g > total["peso_g"]:
            raise HTTPException(400, "O peso residual não pode ser maior que o peso total.")
        ts = agora()
        conn.execute("DELETE FROM pesagens WHERE registro_id = ? AND tipo = 'residual'", (rid,))
        conn.execute("INSERT INTO pesagens (registro_id, tipo, peso_g, origem, criado_em) VALUES (?, 'residual', ?, ?, ?)",
                     (rid, body.peso_residual_g, body.origem_peso, ts))
        conn.execute("UPDATE itens_reconhecidos SET sobrou = 0 WHERE registro_id = ?", (rid,))
        if body.itens_sobra:
            marcas = ",".join("?" * len(body.itens_sobra))
            conn.execute(f"UPDATE itens_reconhecidos SET sobrou = 1 WHERE registro_id = ? AND id IN ({marcas})",
                         (rid, *body.itens_sobra))
        registrar_atividade(conn, "alimentar", "retorno",
                            f"Prato #{rid} devolvido: sobra de {body.peso_residual_g:.0f} g", rid, ts)
    return {"ok": True}


def _montar_registros(conn, where: str = "", params: tuple = (), limite: int = 50) -> list[dict]:
    regs = rows(conn.execute(
        "SELECT r.*, m.numero AS mesa FROM registros_prato r LEFT JOIN mesas m ON m.id = r.mesa_id"
        f" {where} ORDER BY r.criado_em DESC, r.id DESC LIMIT ?", (*params, limite)))
    if not regs:
        return []
    ids = [r["id"] for r in regs]
    marcas = ",".join("?" * len(ids))
    itens = rows(conn.execute(f"SELECT * FROM itens_reconhecidos WHERE registro_id IN ({marcas}) ORDER BY id", ids))
    pes = rows(conn.execute(f"SELECT * FROM pesagens WHERE registro_id IN ({marcas})", ids))
    for r in regs:
        r["itens"] = [i for i in itens if i["registro_id"] == r["id"]]
        r["imagem_url"] = f"/uploads/{r['imagem']}" if r["imagem"] else None
        for tipo in ("total", "residual"):
            p = next((p for p in pes if p["registro_id"] == r["id"] and p["tipo"] == tipo), None)
            r[f"peso_{tipo}_g"] = p["peso_g"] if p else None
            r[f"peso_{tipo}_origem"] = p["origem"] if p else None
        r["desperdicio_pct"] = (
            round(r["peso_residual_g"] / r["peso_total_g"] * 100, 1)
            if r["peso_total_g"] and r["peso_residual_g"] is not None else None
        )
    return regs


@router.get("/registros")
def listar(limite: int = 50, u: dict = auth.exigir("alimentos_ver", "alimentos_registrar")):
    with get_conn() as conn:
        return {"registros": _montar_registros(conn, limite=min(max(limite, 1), 500))}


@router.get("/registros/{rid}")
def detalhe(rid: int, u: dict = auth.exigir("alimentos_ver", "alimentos_registrar")):
    with get_conn() as conn:
        regs = _montar_registros(conn, "WHERE r.id = ?", (rid,), 1)
    if not regs:
        raise HTTPException(404, "Registro não encontrado")
    return regs[0]


def resumo_alimentar(conn) -> dict:
    total_regs = conn.execute("SELECT COUNT(*) FROM registros_prato").fetchone()[0]
    hoje = datetime.now().date().isoformat()
    regs_hoje = conn.execute("SELECT COUNT(*) FROM registros_prato WHERE criado_em >= ?", (hoje,)).fetchone()[0]
    # Desperdício só é calculado onde existem as duas pesagens do mesmo prato.
    par = conn.execute(
        "SELECT COUNT(*) n, SUM(t.peso_g) servido, SUM(r.peso_g) sobra FROM pesagens t"
        " JOIN pesagens r ON r.registro_id = t.registro_id AND r.tipo = 'residual' WHERE t.tipo = 'total'"
    ).fetchone()
    servido_total = conn.execute("SELECT SUM(peso_g) FROM pesagens WHERE tipo = 'total'").fetchone()[0] or 0
    n_totais = conn.execute("SELECT COUNT(*) FROM pesagens WHERE tipo = 'total'").fetchone()[0]
    origens = {r["origem"]: r["n"] for r in conn.execute("SELECT origem, COUNT(*) n FROM pesagens GROUP BY origem")}
    metodos = {r["metodo_reconhecimento"]: r["n"] for r in conn.execute(
        "SELECT metodo_reconhecimento, COUNT(*) n FROM registros_prato GROUP BY metodo_reconhecimento")}
    # Incidência de sobras: em quantos pratos o alimento apareceu e em quantos sobrou.
    # Considera apenas pratos que já tiveram o retorno registrado.
    alimentos = rows(conn.execute(
        "SELECT i.alimento, COUNT(*) pratos, SUM(i.sobrou) sobras FROM itens_reconhecidos i"
        " WHERE i.registro_id IN (SELECT registro_id FROM pesagens WHERE tipo = 'residual')"
        " GROUP BY i.alimento"))
    for a in alimentos:
        a["incidencia_sobra_pct"] = round(a["sobras"] / a["pratos"] * 100, 1) if a["pratos"] else 0
    mais_servidos = rows(conn.execute(
        "SELECT alimento, COUNT(*) pratos FROM itens_reconhecidos GROUP BY alimento ORDER BY pratos DESC, alimento LIMIT 8"))
    mais_sobras = sorted([a for a in alimentos if a["pratos"] >= 2],
                         key=lambda a: (-a["incidencia_sobra_pct"], -a["pratos"]))[:8]
    por_hora = rows(conn.execute(
        "SELECT CAST(strftime('%H', p.criado_em) AS INTEGER) hora, COUNT(DISTINCT p.id) pratos,"
        " SUM(t.peso_g) servido, SUM(r.peso_g) sobra"
        " FROM registros_prato p"
        " LEFT JOIN pesagens t ON t.registro_id = p.id AND t.tipo = 'total'"
        " LEFT JOIN pesagens r ON r.registro_id = p.id AND r.tipo = 'residual'"
        " GROUP BY hora ORDER BY hora"))
    for h in por_hora:
        h["desperdicio_pct"] = round(h["sobra"] / h["servido"] * 100, 1) if h["servido"] and h["sobra"] is not None else None
    return {
        "registros": total_regs,
        "registros_hoje": regs_hoje,
        "pratos_com_retorno": par["n"] or 0,
        "peso_servido_total_g": round(servido_total, 1),
        "peso_servido_medio_g": round(servido_total / n_totais, 1) if n_totais else None,
        "peso_residual_total_g": round(par["sobra"] or 0, 1),
        "desperdicio_pct": round(par["sobra"] / par["servido"] * 100, 1) if par["servido"] else None,
        "origem_pesagens": origens,
        "metodos_reconhecimento": metodos,
        "mais_servidos": mais_servidos,
        "mais_sobras": mais_sobras,
        "por_hora": por_hora,
        "aguardando_retorno": conn.execute(
            "SELECT COUNT(*) FROM registros_prato WHERE id NOT IN (SELECT registro_id FROM pesagens WHERE tipo = 'residual')"
        ).fetchone()[0],
    }


@router.get("/resumo")
def resumo(u: dict = auth.exigir("alimentos_ver", "alimentos_registrar")):
    with get_conn() as conn:
        return resumo_alimentar(conn)
