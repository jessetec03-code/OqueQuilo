"""Acesso dos colaboradores: login, sessões e permissões por perfil.

Como funciona
- O QR Code da equipe só abre a página de login (/equipe/). Ler o QR Code não dá
  acesso a nada: é preciso usuário e senha de um colaborador cadastrado e ativo.
- A senha é guardada como hash PBKDF2-SHA256 com sal. O navegador recebe um cookie
  de sessão HttpOnly com um token aleatório; o banco guarda só o hash do token.
- Cada rota do painel declara a permissão que exige (veja `exigir`). A verificação é
  feita no servidor em toda requisição; o menu do painel só esconde o que não pode.
- As permissões de cada perfil ficam na tabela permissoes_perfil e o Administrador
  pode ajustá-las. O perfil Administrador sempre tem todas, para ninguém ficar trancado.
"""
import hashlib
import hmac
import secrets
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Depends, HTTPException, Request

from .db import DB_PATH, agora, get_conn, rows

COOKIE = "codemeat_sessao"
DURACAO_SESSAO = timedelta(hours=12)
ITERACOES = 200_000

PERFIS = {
    "garcom": "Garçom",
    "caixa": "Caixa",
    "gerente": "Gerente",
    "proprietario": "Proprietário",
    "admin": "Administrador",
}

PERMISSOES = {
    "painel": "Visão Geral: dashboard gerencial que cruza os dois pilares",
    "alimentos_registrar": "Registrar pratos: foto, reconhecimento por IA, peso total e sobra",
    "alimentos_ver": "Consultar pratos registrados e indicadores de alimentos",
    "atendimento_ver": "Ver os pedidos de atendimento das mesas em tempo real",
    "atendimento_atualizar": "Atender e resolver pedidos de atendimento",
    "cliente_ver": "Ver avaliações, sugestões, reclamações e indicadores de satisfação",
    "cliente_gerenciar": "Marcar sugestões e reclamações como tratadas",
    "relatorios": "Relatórios integrados e exportação CSV",
    "configuracoes": "Configurações, QR Codes e modo demonstração",
    "usuarios": "Gerenciar colaboradores e permissões",
}

# Permissões iniciais de cada perfil (o Administrador pode mudar em "Equipe e acessos")
PADRAO = {
    "garcom": ["atendimento_ver", "atendimento_atualizar"],
    "caixa": ["alimentos_registrar", "alimentos_ver"],
    "gerente": ["painel", "alimentos_registrar", "alimentos_ver", "atendimento_ver", "atendimento_atualizar",
                "cliente_ver", "cliente_gerenciar", "relatorios"],
    "proprietario": ["painel", "alimentos_ver", "atendimento_ver", "cliente_ver", "relatorios"],
    "admin": list(PERMISSOES),
}

# Contas criadas na 1ª execução, uma por perfil, para a demonstração.
CONTAS_INICIAIS = [
    ("admin", "Administrador", "admin"),
    ("gerente", "Gerente (demonstração)", "gerente"),
    ("garcom", "Garçom (demonstração)", "garcom"),
    ("caixa", "Caixa (demonstração)", "caixa"),
    ("proprietario", "Proprietário (demonstração)", "proprietario"),
]
ARQUIVO_ACESSOS = DB_PATH.parent / "acessos_iniciais.txt"  # fica em data/, fora do Git


# ---------- Senhas ----------

def gerar_senha(tamanho: int = 8) -> str:
    alfabeto = "abcdefghjkmnpqrstuvwxyz23456789"  # sem letras e números parecidos (l, 1, o, 0)
    return "".join(secrets.choice(alfabeto) for _ in range(tamanho))


def hash_senha(senha: str) -> str:
    sal = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", senha.encode(), sal, ITERACOES)
    return f"pbkdf2_sha256${ITERACOES}${sal.hex()}${h.hex()}"


def conferir_senha(senha: str, guardado: str) -> bool:
    try:
        _, it, sal, h = guardado.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(sal), int(it))
        return hmac.compare_digest(calc.hex(), h)
    except (ValueError, TypeError):
        return False


def validar_senha(senha: str) -> None:
    if len(senha or "") < 6:
        raise HTTPException(400, "A senha precisa ter pelo menos 6 caracteres.")


# ---------- Bloqueio por tentativas erradas ----------

_falhas: dict[str, tuple[int, float]] = {}
_lock = threading.Lock()
MAX_FALHAS = 5
BLOQUEIO_S = 120


def _bloqueado(chave: str) -> int:
    with _lock:
        n, ate = _falhas.get(chave, (0, 0.0))
        return int(ate - time.time()) if ate > time.time() else 0


def _registrar_falha(chave: str) -> None:
    with _lock:
        n, _ = _falhas.get(chave, (0, 0.0))
        n += 1
        _falhas[chave] = (0, time.time() + BLOQUEIO_S) if n >= MAX_FALHAS else (n, 0.0)


def _limpar_falhas(chave: str) -> None:
    with _lock:
        _falhas.pop(chave, None)


# ---------- Permissões ----------

def permissoes_do_perfil(conn, perfil: str) -> list[str]:
    if perfil == "admin":
        return list(PERMISSOES)
    perms = {r[0] for r in conn.execute("SELECT permissao FROM permissoes_perfil WHERE perfil = ?", (perfil,))}
    return [p for p in PERMISSOES if p in perms]


def matriz_permissoes(conn) -> dict[str, list[str]]:
    return {p: permissoes_do_perfil(conn, p) for p in PERFIS}


def definir_permissoes(conn, perfil: str, permissoes: list[str]) -> list[str]:
    if perfil not in PERFIS:
        raise HTTPException(404, "Perfil não encontrado")
    if perfil == "admin":
        raise HTTPException(400, "O perfil Administrador sempre tem todas as permissões.")
    validas = [p for p in PERMISSOES if p in set(permissoes)]
    conn.execute("DELETE FROM permissoes_perfil WHERE perfil = ?", (perfil,))
    conn.executemany("INSERT INTO permissoes_perfil (perfil, permissao) VALUES (?, ?)", [(perfil, p) for p in validas])
    return validas


# ---------- Usuários ----------

def publico(u) -> dict:
    u = dict(u)
    u.pop("senha_hash", None)
    u["perfil_nome"] = PERFIS.get(u["perfil"], u["perfil"])
    u["ativo"] = bool(u["ativo"])
    return u


def criar_usuario(conn, nome: str, login: str, perfil: str, senha: str) -> int:
    nome, login = (nome or "").strip(), (login or "").strip().lower()
    if perfil not in PERFIS:
        raise HTTPException(400, "Perfil inválido")
    if len(nome) < 2 or not (3 <= len(login) <= 30) or not login.replace(".", "").replace("_", "").isalnum():
        raise HTTPException(400, "Informe o nome e um usuário de 3 a 30 letras ou números (pode usar . e _).")
    validar_senha(senha)
    if conn.execute("SELECT 1 FROM usuarios WHERE login = ?", (login,)).fetchone():
        raise HTTPException(409, "Já existe um colaborador com esse usuário.")
    return conn.execute(
        "INSERT INTO usuarios (nome, login, perfil, senha_hash, criado_em) VALUES (?, ?, ?, ?, ?)",
        (nome, login, perfil, hash_senha(senha), agora())).lastrowid


def encerrar_sessoes(conn, usuario_id: int) -> None:
    conn.execute("DELETE FROM sessoes WHERE usuario_id = ?", (usuario_id,))


def admins_ativos(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM usuarios WHERE perfil = 'admin' AND ativo = 1").fetchone()[0]


def _escrever_acessos(linhas: list[tuple[str, str, str]]) -> Path:
    ARQUIVO_ACESSOS.parent.mkdir(parents=True, exist_ok=True)
    texto = ["ACESSOS INICIAIS DO CODE MEAT (gerados neste computador; NÃO publique este arquivo)",
             "Entre em http://localhost:8000/equipe/ (ou pelo QR Code da equipe) e troque as senhas.", ""]
    texto += [f"{PERFIS[p]:<14} usuário: {login:<13} senha: {senha}" for login, senha, p in linhas]
    ARQUIVO_ACESSOS.write_text("\n".join(texto) + "\n", encoding="utf-8")
    return ARQUIVO_ACESSOS


def garantir_acessos_iniciais() -> list[tuple[str, str, str]] | None:
    """Na 1ª execução: permissões padrão e uma conta por perfil, com senhas aleatórias.

    As senhas aparecem no terminal e em data/acessos_iniciais.txt (fora do Git).
    Devolve as contas criadas, ou None se já existiam.
    """
    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM permissoes_perfil LIMIT 1").fetchone():
            for perfil, perms in PADRAO.items():
                if perfil != "admin":
                    definir_permissoes(conn, perfil, perms)
        if conn.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone():
            return None
        criadas = []
        for login, nome, perfil in CONTAS_INICIAIS:
            senha = gerar_senha()
            criar_usuario(conn, nome, login, perfil, senha)
            criadas.append((login, senha, perfil))
    _escrever_acessos(criadas)
    return criadas


def redefinir_acessos_iniciais() -> list[tuple[str, str, str]]:
    """Gera senhas novas para as contas iniciais (e recria as que faltarem). Uso: python run.py --redefinir-acessos"""
    garantir_acessos_iniciais()
    novas = []
    with get_conn() as conn:
        for login, nome, perfil in CONTAS_INICIAIS:
            senha = gerar_senha()
            u = conn.execute("SELECT id FROM usuarios WHERE login = ?", (login,)).fetchone()
            if u:
                conn.execute("UPDATE usuarios SET senha_hash = ?, perfil = ?, ativo = 1 WHERE id = ?",
                             (hash_senha(senha), perfil, u[0]))
                encerrar_sessoes(conn, u[0])
            else:
                criar_usuario(conn, nome, login, perfil, senha)
            novas.append((login, senha, perfil))
    _escrever_acessos(novas)
    return novas


def imprimir_acessos(contas: list[tuple[str, str, str]]) -> None:
    print("\n  ACESSOS DA EQUIPE (anote; também salvos em data/acessos_iniciais.txt)")
    for login, senha, perfil in contas:
        print(f"    {PERFIS[perfil]:<14} usuário: {login:<13} senha: {senha}")
    print("  Troque as senhas em Equipe e acessos. Este arquivo não vai para o GitHub.\n")


# ---------- Sessões ----------

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def entrar(login: str, senha: str) -> tuple[str, dict]:
    chave = (login or "").strip().lower()
    espera = _bloqueado(chave)
    if espera:
        raise HTTPException(429, f"Muitas tentativas erradas. Tente de novo em {espera} segundos.")
    with get_conn() as conn:
        u = conn.execute("SELECT * FROM usuarios WHERE login = ?", (chave,)).fetchone()
        if not u or not u["ativo"] or not conferir_senha(senha or "", u["senha_hash"]):
            _registrar_falha(chave)
            raise HTTPException(401, "Usuário ou senha incorretos, ou colaborador desativado.")
        _limpar_falhas(chave)
        token = secrets.token_urlsafe(32)
        agora_dt = datetime.now()
        conn.execute("DELETE FROM sessoes WHERE expira_em < ?", (agora_dt.isoformat(timespec="seconds"),))
        conn.execute("INSERT INTO sessoes (token_hash, usuario_id, criado_em, expira_em) VALUES (?, ?, ?, ?)",
                     (_hash_token(token), u["id"], agora_dt.isoformat(timespec="seconds"),
                      (agora_dt + DURACAO_SESSAO).isoformat(timespec="seconds")))
        conn.execute("UPDATE usuarios SET ultimo_acesso = ? WHERE id = ?", (agora(), u["id"]))
        return token, {**publico(u), "permissoes": permissoes_do_perfil(conn, u["perfil"])}


def sair(token: str | None) -> None:
    if token:
        with get_conn() as conn:
            conn.execute("DELETE FROM sessoes WHERE token_hash = ?", (_hash_token(token),))


def usuario_da_sessao(token: str | None) -> dict | None:
    if not token:
        return None
    with get_conn() as conn:
        u = conn.execute(
            "SELECT u.* FROM sessoes s JOIN usuarios u ON u.id = s.usuario_id"
            " WHERE s.token_hash = ? AND s.expira_em > ? AND u.ativo = 1",
            (_hash_token(token), agora())).fetchone()
        if not u:
            return None
        return {**publico(u), "permissoes": permissoes_do_perfil(conn, u["perfil"])}


def usuario_atual(request: Request) -> dict | None:
    return usuario_da_sessao(request.cookies.get(COOKIE))


def exigir(*permissoes: str):
    """Dependência do FastAPI: exige login e (se informadas) ao menos uma das permissões."""
    def verificar(request: Request) -> dict:
        u = usuario_atual(request)
        if not u:
            raise HTTPException(401, "Faça login com o seu usuário da equipe.")
        if permissoes and not set(permissoes) & set(u["permissoes"]):
            raise HTTPException(403, "O seu perfil não tem acesso a esta função.")
        return u
    return Depends(verificar)


def pode(u: dict, permissao: str) -> bool:
    return permissao in u.get("permissoes", [])


def listar_usuarios(conn) -> list[dict]:
    return [publico(u) for u in rows(conn.execute(
        "SELECT * FROM usuarios ORDER BY CASE perfil WHEN 'admin' THEN 0 WHEN 'proprietario' THEN 1"
        " WHEN 'gerente' THEN 2 WHEN 'caixa' THEN 3 ELSE 4 END, nome"))]
