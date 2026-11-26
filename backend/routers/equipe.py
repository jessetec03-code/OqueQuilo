"""ACESSO DA EQUIPE · login dos colaboradores, perfis e permissões.

O QR Code da equipe abre /equipe/, a página de login. As permissões são
verificadas no servidor em cada rota do painel (backend/auth.py).
"""
import io

import segno
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from .. import auth
from ..db import get_conn, registrar_atividade
from .feedback import url_base

router = APIRouter(tags=["Acesso da equipe"])


class Login(BaseModel):
    login: str = Field(min_length=1, max_length=60)
    senha: str = Field(min_length=1, max_length=200)


class TrocaSenha(BaseModel):
    senha_atual: str
    senha_nova: str = Field(min_length=6, max_length=200)


class NovoUsuario(BaseModel):
    nome: str = Field(min_length=2, max_length=80)
    login: str = Field(min_length=3, max_length=30)
    perfil: str
    senha: str = Field(min_length=6, max_length=200)


class MudancaUsuario(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=80)
    perfil: str | None = None
    ativo: bool | None = None
    senha: str | None = Field(default=None, min_length=6, max_length=200)


class Permissoes(BaseModel):
    permissoes: list[str]


# ---------- Login ----------

@router.post("/api/auth/login")
def login(body: Login, request: Request):
    token, u = auth.entrar(body.login, body.senha)
    resp = JSONResponse({"usuario": u})
    resp.set_cookie(auth.COOKIE, token, max_age=int(auth.DURACAO_SESSAO.total_seconds()), httponly=True,
                    samesite="lax", secure=request.url.scheme == "https", path="/")
    return resp


@router.post("/api/auth/sair")
def logout(request: Request):
    auth.sair(request.cookies.get(auth.COOKIE))
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth.COOKIE, path="/")
    return resp


@router.get("/api/auth/eu")
def eu(u: dict = auth.exigir()):
    return {"usuario": u, "perfis": auth.PERFIS}


@router.post("/api/auth/senha")
def trocar_senha(body: TrocaSenha, request: Request, u: dict = auth.exigir()):
    with get_conn() as conn:
        atual = conn.execute("SELECT senha_hash FROM usuarios WHERE id = ?", (u["id"],)).fetchone()
        if not auth.conferir_senha(body.senha_atual, atual[0]):
            raise HTTPException(400, "A senha atual não confere.")
        auth.validar_senha(body.senha_nova)
        conn.execute("UPDATE usuarios SET senha_hash = ? WHERE id = ?", (auth.hash_senha(body.senha_nova), u["id"]))
        # Encerra as outras sessões deste colaborador e mantém a atual
        token = request.cookies.get(auth.COOKIE) or ""
        conn.execute("DELETE FROM sessoes WHERE usuario_id = ? AND token_hash != ?", (u["id"], auth._hash_token(token)))
    return {"ok": True}


@router.get("/api/qrcode/equipe.svg")
def qr_equipe(request: Request):
    """QR Code da equipe: abre só a página de login. Não dá acesso a nada sozinho."""
    buf = io.BytesIO()
    segno.make(f"{url_base(request)}/equipe/", error="m").save(buf, kind="svg", scale=8, border=2, dark="#121417")
    return Response(buf.getvalue(), media_type="image/svg+xml")


# ---------- Administração de colaboradores ----------

@router.get("/api/usuarios")
def listar(u: dict = auth.exigir("usuarios")):
    with get_conn() as conn:
        return {"usuarios": auth.listar_usuarios(conn), "perfis": auth.PERFIS}


@router.post("/api/usuarios", status_code=201)
def criar(body: NovoUsuario, u: dict = auth.exigir("usuarios")):
    with get_conn() as conn:
        uid = auth.criar_usuario(conn, body.nome, body.login, body.perfil, body.senha)
        registrar_atividade(conn, "sistema", "usuario", f"Colaborador cadastrado: {body.nome.strip()} ({auth.PERFIS[body.perfil]})", uid)
    return {"id": uid}


@router.patch("/api/usuarios/{uid}")
def alterar(uid: int, body: MudancaUsuario, u: dict = auth.exigir("usuarios")):
    with get_conn() as conn:
        alvo = conn.execute("SELECT * FROM usuarios WHERE id = ?", (uid,)).fetchone()
        if not alvo:
            raise HTTPException(404, "Colaborador não encontrado")
        if body.perfil is not None and body.perfil not in auth.PERFIS:
            raise HTTPException(400, "Perfil inválido")
        perde_admin = alvo["perfil"] == "admin" and alvo["ativo"] and (
            (body.perfil is not None and body.perfil != "admin") or body.ativo is False)
        if perde_admin and auth.admins_ativos(conn) <= 1:
            raise HTTPException(400, "É preciso manter pelo menos um Administrador ativo.")
        if uid == u["id"] and (body.ativo is False or (body.perfil and body.perfil != u["perfil"])):
            raise HTTPException(400, "Você não pode desativar nem mudar o próprio perfil.")
        if body.nome is not None:
            conn.execute("UPDATE usuarios SET nome = ? WHERE id = ?", (body.nome.strip(), uid))
        if body.perfil is not None:
            conn.execute("UPDATE usuarios SET perfil = ? WHERE id = ?", (body.perfil, uid))
        if body.ativo is not None:
            conn.execute("UPDATE usuarios SET ativo = ? WHERE id = ?", (int(body.ativo), uid))
        if body.senha is not None:
            auth.validar_senha(body.senha)
            conn.execute("UPDATE usuarios SET senha_hash = ? WHERE id = ?", (auth.hash_senha(body.senha), uid))
        if body.perfil is not None or body.ativo is False or body.senha is not None:
            if uid != u["id"]:
                auth.encerrar_sessoes(conn, uid)  # o colaborador precisa entrar de novo
        registrar_atividade(conn, "sistema", "usuario", f"Acesso de {alvo['nome']} atualizado por {u['nome']}", uid)
    return {"ok": True}


@router.get("/api/permissoes")
def permissoes(u: dict = auth.exigir("usuarios")):
    with get_conn() as conn:
        return {"perfis": auth.PERFIS, "permissoes": auth.PERMISSOES, "matriz": auth.matriz_permissoes(conn),
                "padrao": auth.PADRAO}


@router.put("/api/permissoes/{perfil}")
def definir(perfil: str, body: Permissoes, u: dict = auth.exigir("usuarios")):
    with get_conn() as conn:
        perms = auth.definir_permissoes(conn, perfil, body.permissoes)
        registrar_atividade(conn, "sistema", "permissoes", f"Permissões do perfil {auth.PERFIS[perfil]} alteradas por {u['nome']}")
    return {"perfil": perfil, "permissoes": perms}
