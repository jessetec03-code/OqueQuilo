"""Configurações lidas do arquivo .env (opcional).

Nenhuma chave é obrigatória. O reconhecimento de alimentos usa o YOLOE local
(requirements-visao.txt); o Claude é opcional. Sem nenhum dos dois, o sistema
funciona em modo de marcação manual, identificado na interface.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _carregar_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for linha in env.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


_carregar_env()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5").strip()
PORTA = int(os.environ.get("PORTA", "8000"))
# Endereço público usado no QR Code (ex.: http://192.168.0.10:8000).
# Se ficar vazio, o sistema detecta o IP do computador na rede local.
URL_PUBLICA = os.environ.get("URL_PUBLICA", "").strip().rstrip("/")
# Reconhecimento de alimentos: "auto" usa o YOLOE local se instalado; senão o Claude
# (se houver chave); senão marcação manual. Também aceita "local", "claude" ou "manual".
MOTOR_VISAO = os.environ.get("MOTOR_VISAO", "auto").strip().lower()
# Pesos do YOLOE (baixados do GitHub da Ultralytics no 1º uso para data/modelos/)
YOLOE_MODELO = os.environ.get("YOLOE_MODELO", "yoloe-v8l-seg.pt").strip()
