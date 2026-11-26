"""Aplicação principal do Code Meat.

Um único servidor FastAPI entrega a API (/api/...), o painel administrativo (/),
a página do cliente acessada pelo QR Code da mesa (/cliente/) e a página de login
da equipe acessada pelo QR Code da equipe (/equipe/).
"""
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import auth, motores, seed
from .db import UPLOAD_DIR, init_db
from .routers import dashboard, equipe, feedback, food

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def ciclo_de_vida(_app):
    init_db()
    if seed.banco_vazio():
        seed.recriar_demo()  # primeira execução: cria o banco com dados demonstrativos
    criadas = auth.garantir_acessos_iniciais()  # primeira execução: uma conta por perfil
    if criadas:
        auth.imprimir_acessos(criadas)
    threading.Thread(target=motores.preaquecer, daemon=True).start()  # carrega o YOLOE sem travar o início
    yield


app = FastAPI(
    lifespan=ciclo_de_vida,
    title="Code Meat | Intelligence Platform",
    description="API integrada: Reconhecimento de Alimentos e Experiência do Cliente. "
                "As rotas do painel exigem login de um colaborador (POST /api/auth/login).",
    version="1.0.0",
)


app.include_router(equipe.router)  # antes de feedback: /api/qrcode/equipe.svg vem antes de /api/qrcode/{numero}.svg
app.include_router(dashboard.router)
app.include_router(food.router)
app.include_router(feedback.router)

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/uploads/{nome}", include_in_schema=False)
def foto_prato(nome: str, u: dict = auth.exigir("alimentos_ver", "alimentos_registrar")):
    """Fotos dos pratos: só para colaboradores com acesso ao Reconhecimento de Alimentos."""
    arq = (UPLOAD_DIR / nome).resolve()
    if arq.parent != UPLOAD_DIR.resolve() or not arq.is_file():
        raise HTTPException(404, "Foto não encontrada")
    return FileResponse(arq)


@app.get("/", include_in_schema=False)
def painel(request: Request):
    if not auth.usuario_atual(request):
        return RedirectResponse("/equipe/")  # o painel só abre depois do login
    return FileResponse(FRONTEND / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/equipe", include_in_schema=False)
def equipe_sem_barra():
    return RedirectResponse("/equipe/")


@app.get("/equipe/", include_in_schema=False)
def equipe_login():
    return FileResponse(FRONTEND / "equipe" / "index.html")


@app.get("/cliente", include_in_schema=False)
def cliente_sem_barra():
    return RedirectResponse("/cliente/")


@app.get("/cliente/", include_in_schema=False)
def cliente():
    return FileResponse(FRONTEND / "cliente" / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(FRONTEND / "img" / "logo.svg", media_type="image/svg+xml")
