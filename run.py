"""Inicia o Code Meat.

    python run.py            -> inicia o sistema
    python run.py --reset    -> apaga o banco e recria os dados demonstrativos

Depois abra http://localhost:8000 no navegador.
"""
import sys

import uvicorn

from backend.routers.feedback import ip_rede_local as ip_local
from backend.settings import PORTA

if __name__ == "__main__":
    if "--reset" in sys.argv:
        from backend.seed import recriar_demo
        recriar_demo()
        print("Banco recriado com dados demonstrativos.")
    ip = ip_local()
    print("\n" + "=" * 60)
    print("  CODE MEAT | INTELLIGENCE PLATFORM")
    print("=" * 60)
    print(f"  Painel (neste computador):  http://localhost:{PORTA}")
    print(f"  Celular na mesma rede Wi-Fi: http://{ip}:{PORTA}/cliente/?mesa=1")
    print("  Para encerrar: Ctrl + C")
    print("=" * 60 + "\n")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=PORTA, log_level="warning")
