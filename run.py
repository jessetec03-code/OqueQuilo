"""Inicia o Code Meat.

    python run.py                      -> inicia o sistema
    python run.py --reset              -> apaga os registros e recria os dados demonstrativos (faz backup antes)
    python run.py --redefinir-acessos  -> gera senhas novas para as contas iniciais da equipe

Depois abra http://localhost:8000 no navegador.
"""
import socket
import sys

import uvicorn

from backend.routers.feedback import ip_rede_local as ip_local
from backend.settings import PORTA

if __name__ == "__main__":
    if "--reset" in sys.argv:
        from backend.seed import recriar_demo
        recriar_demo()
        print("Banco recriado com dados demonstrativos (backup anterior em data/backups/).")
    if "--redefinir-acessos" in sys.argv:
        from backend import auth
        from backend.db import init_db
        init_db()
        auth.imprimir_acessos(auth.redefinir_acessos_iniciais())
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as teste:
        if teste.connect_ex(("127.0.0.1", PORTA)) == 0:
            print(f"\n  A porta {PORTA} já está em uso: o Code Meat provavelmente já está aberto em outra janela.")
            print(f"  Use essa janela (http://localhost:{PORTA}) ou feche-a e rode de novo.")
            print("  Para usar outra porta: defina PORTA=8001 no arquivo .env.\n")
            sys.exit(1)
    ip = ip_local()
    print("\n" + "=" * 60)
    print("  CODE MEAT | INTELLIGENCE PLATFORM")
    print("=" * 60)
    print(f"  Painel (neste computador):  http://localhost:{PORTA}")
    print(f"  Celular na mesma rede Wi-Fi: http://{ip}:{PORTA}/cliente/?mesa=1")
    print(f"  Login da equipe:            http://{ip}:{PORTA}/equipe/")
    print("  Usuários e senhas da equipe: data/acessos_iniciais.txt")
    print("  Para encerrar: Ctrl + C")
    print("=" * 60 + "\n")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=PORTA, log_level="warning")
