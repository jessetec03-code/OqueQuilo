"""Banco de dados central do Code Meat (SQLite).

Os dois pilares (Reconhecimento de Alimentos e Experiência do Cliente)
gravam e leem deste mesmo arquivo. Toda tabela de registros possui a coluna
`origem_dado`, que vale 'demo' para dados demonstrativos criados pelo seed e
'real' para tudo o que é registrado durante o uso do sistema.
"""
import os
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("CODEMEAT_DB", ROOT / "data" / "codemeat_v2.db"))
UPLOAD_DIR = ROOT / "data" / "uploads"

SCHEMA = """
-- Mesas existem só para identificar de onde veio o QR Code do cliente
CREATE TABLE IF NOT EXISTS mesas (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    numero  INTEGER NOT NULL UNIQUE,
    area    TEXT    NOT NULL DEFAULT 'Salão'
);

CREATE TABLE IF NOT EXISTS registros_prato (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    mesa_id                INTEGER REFERENCES mesas(id),
    imagem                 TEXT,             -- nome do arquivo em data/uploads
    metodo_reconhecimento  TEXT NOT NULL,    -- ia_local (YOLOE) | ia_claude | manual
    observacao             TEXT,
    criado_em              TEXT NOT NULL,
    origem_dado            TEXT NOT NULL DEFAULT 'real'
);

CREATE TABLE IF NOT EXISTS itens_reconhecidos (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    registro_id  INTEGER NOT NULL REFERENCES registros_prato(id) ON DELETE CASCADE,
    alimento     TEXT    NOT NULL,
    confianca    TEXT,                -- alta | media | baixa (só quando veio da IA)
    origem       TEXT    NOT NULL,    -- ia | manual
    sobrou       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pesagens (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    registro_id  INTEGER NOT NULL REFERENCES registros_prato(id) ON DELETE CASCADE,
    tipo         TEXT    NOT NULL,    -- total | residual
    peso_g       REAL    NOT NULL,
    origem       TEXT    NOT NULL,    -- informado | balanca | estimativa_ia | simulado
    criado_em    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS avaliacoes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    mesa_id           INTEGER REFERENCES mesas(id),
    nota_geral        INTEGER NOT NULL CHECK (nota_geral BETWEEN 1 AND 5),
    nota_atendimento  INTEGER CHECK (nota_atendimento BETWEEN 1 AND 5),
    nota_comida       INTEGER CHECK (nota_comida BETWEEN 1 AND 5),
    comentario        TEXT,
    criado_em         TEXT NOT NULL,
    origem_dado       TEXT NOT NULL DEFAULT 'real'
);

CREATE TABLE IF NOT EXISTS manifestacoes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    mesa_id      INTEGER REFERENCES mesas(id),
    tipo         TEXT NOT NULL,              -- sugestao | reclamacao
    categoria    TEXT NOT NULL DEFAULT 'Outro',
    categoria_outro TEXT,                    -- texto livre quando a categoria é "Outro"
    texto        TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'nova', -- nova | resolvida
    criado_em    TEXT NOT NULL,
    origem_dado  TEXT NOT NULL DEFAULT 'real'
);

CREATE TABLE IF NOT EXISTS solicitacoes_atendimento (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    mesa_id       INTEGER NOT NULL REFERENCES mesas(id),
    motivo        TEXT NOT NULL,
    motivo_outro  TEXT,                              -- texto livre quando o motivo é "Outro"
    status        TEXT NOT NULL DEFAULT 'pendente', -- pendente | em_atendimento | resolvida
    criado_em     TEXT NOT NULL,
    atendido_em   TEXT,
    resolvido_em  TEXT,
    origem_dado   TEXT NOT NULL DEFAULT 'real'
);

CREATE TABLE IF NOT EXISTS atividades (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    modulo        TEXT NOT NULL,   -- alimentar | cliente | sistema
    tipo          TEXT NOT NULL,
    descricao     TEXT NOT NULL,
    referencia_id INTEGER,
    criado_em     TEXT NOT NULL,
    origem_dado   TEXT NOT NULL DEFAULT 'real'
);

-- Acesso dos colaboradores (login pelo QR Code da equipe) e permissões por perfil
CREATE TABLE IF NOT EXISTS usuarios (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    nome           TEXT NOT NULL,
    login          TEXT NOT NULL UNIQUE COLLATE NOCASE,
    perfil         TEXT NOT NULL,           -- garcom | caixa | gerente | proprietario | admin
    senha_hash     TEXT NOT NULL,           -- PBKDF2-SHA256 com sal (a senha nunca é gravada)
    ativo          INTEGER NOT NULL DEFAULT 1,
    criado_em      TEXT NOT NULL,
    ultimo_acesso  TEXT
);

CREATE TABLE IF NOT EXISTS sessoes (
    token_hash  TEXT PRIMARY KEY,            -- SHA-256 do token do cookie
    usuario_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    criado_em   TEXT NOT NULL,
    expira_em   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS permissoes_perfil (
    perfil     TEXT NOT NULL,
    permissao  TEXT NOT NULL,
    PRIMARY KEY (perfil, permissao)
);

-- Parâmetros do sistema (ex.: nota média alvo do modo demonstração)
CREATE TABLE IF NOT EXISTS configuracoes (
    chave  TEXT PRIMARY KEY,
    valor  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_itens_registro ON itens_reconhecidos(registro_id);
CREATE INDEX IF NOT EXISTS idx_pesagens_registro ON pesagens(registro_id);
CREATE INDEX IF NOT EXISTS idx_atividades_data ON atividades(criado_em);
"""


def agora() -> str:
    """Data e hora local do servidor, sem fuso, com precisão de segundos."""
    return datetime.now().isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_conn():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# Colunas acrescentadas depois da primeira versão. Bancos antigos recebem as colunas
# sem perder nenhum registro (e com cópia de segurança antes da alteração).
COLUNAS_NOVAS = [
    ("solicitacoes_atendimento", "motivo_outro", "TEXT"),
    ("manifestacoes", "categoria_outro", "TEXT"),
]
BACKUP_DIR = DB_PATH.parent / "backups"


def _colunas(conn, tabela: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({tabela})")}


def backup(motivo: str = "manual") -> Path | None:
    """Copia o arquivo do banco para data/backups/ (antes de qualquer mudança de estrutura)."""
    if not DB_PATH.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    destino = BACKUP_DIR / f"{DB_PATH.stem}-{datetime.now():%Y%m%d-%H%M%S}-{motivo}.db"
    origem = sqlite3.connect(DB_PATH)
    copia = sqlite3.connect(destino)
    try:
        origem.backup(copia)  # cópia consistente mesmo com o servidor rodando
    finally:
        copia.close()
        origem.close()
    return destino


def init_db() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    existia = DB_PATH.exists()
    with get_conn() as conn:
        tabelas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        faltando = [(t, c, tipo) for t, c, tipo in COLUNAS_NOVAS if t in tabelas and c not in _colunas(conn, t)]
    if existia and faltando:
        backup("antes-da-atualizacao")
        with get_conn() as conn:
            for tabela, coluna, tipo in faltando:
                conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def config_ler(conn, chave: str, padrao: str | None = None) -> str | None:
    r = conn.execute("SELECT valor FROM configuracoes WHERE chave = ?", (chave,)).fetchone()
    return r[0] if r else padrao


def config_gravar(conn, chave: str, valor) -> None:
    conn.execute("INSERT INTO configuracoes (chave, valor) VALUES (?, ?)"
                 " ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor", (chave, str(valor)))


def rows(cursor) -> list[dict]:
    return [dict(r) for r in cursor.fetchall()]


def registrar_atividade(conn, modulo: str, tipo: str, descricao: str,
                        referencia_id: int | None = None,
                        criado_em: str | None = None,
                        origem_dado: str = "real") -> None:
    """Linha do tempo única da plataforma: todo módulo registra aqui."""
    conn.execute(
        "INSERT INTO atividades (modulo, tipo, descricao, referencia_id, criado_em, origem_dado)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (modulo, tipo, descricao, referencia_id, criado_em or agora(), origem_dado),
    )
