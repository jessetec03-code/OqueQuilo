"""Testes automáticos dos dois pilares (Reconhecimento de Alimentos e Experiência do Cliente)
e da integração entre eles.

Rodar (na pasta do projeto):  python -m pytest -q
Usa um banco temporário: não mexe no banco da demonstração.
"""
import os
import tempfile

os.environ["CODEMEAT_DB"] = os.path.join(tempfile.mkdtemp(), "teste.db")
os.environ["ANTHROPIC_API_KEY"] = ""  # testes rodam sem API paga
os.environ["MOTOR_VISAO"] = "auto"

import pytest  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from backend import auth, segmentacao, vision  # noqa: E402
from backend.db import get_conn  # noqa: E402
from backend.main import app  # noqa: E402

# Nos testes de API o modelo real não é carregado (é lento). Ele é testado com fotos reais
# em tests/test_reconhecimento_real.py. Aqui o YOLOE começa "não instalado" e cada teste
# que precisa dele troca o motor por um resultado fixo.
_instalado = segmentacao.pacotes_instalados


@pytest.fixture(autouse=True)
def _sem_modelo_real(monkeypatch):
    monkeypatch.setattr(segmentacao, "pacotes_instalados", lambda: False)

PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360f8cfc0f01f0005000201e2a9c7"
    "3e0000000049454e44ae426082"
)


def cliente():
    c = TestClient(app)
    c.__enter__()  # dispara o startup (cria o banco com dados demonstrativos)
    return c


segmentacao.pacotes_instalados = lambda: False  # o servidor de teste não pré-carrega o modelo
publico = cliente()  # sem login: como o cliente no celular ou alguém que leu o QR Code da equipe
segmentacao.pacotes_instalados = _instalado

SENHA = "senha-de-teste-123"
with get_conn() as _conn:  # um colaborador de teste por perfil, com senha conhecida
    for _perfil in auth.PERFIS:
        auth.criar_usuario(_conn, f"Teste {_perfil}", f"t_{_perfil}", _perfil, SENHA)


def entrar(perfil: str) -> TestClient:
    cl = TestClient(app)
    r = cl.post("/api/auth/login", json={"login": f"t_{perfil}", "senha": SENHA})
    assert r.status_code == 200, r.text
    return cl


c = entrar("admin")  # a maioria dos testes usa o painel como Administrador


def test_aplicacao_abre():
    assert c.get("/").status_code == 200
    assert publico.get("/cliente/?mesa=1").status_code == 200
    assert publico.get("/equipe/").status_code == 200
    d = c.get("/api/dashboard").json()
    assert {"alimentar", "cliente", "alertas", "sinais_por_hora", "ia"} <= set(d)
    assert d["origem_dos_dados"]["registros_demo"] > 0
    assert len(c.get("/api/mesas").json()["mesas"]) == 24  # mesas existem só para os QR Codes


def test_smart_tables_foi_removido():
    d = c.get("/api/dashboard").json()
    assert "mesas" not in d
    assert c.get("/api/mesas/resumo").status_code in (404, 405)
    assert c.post("/api/mesas/1/status", json={"status": "ocupada"}).status_code in (404, 405)
    for h in c.get("/api/relatorios/sinais?dias=7").json()["horas"]:
        assert "ocupacoes" not in h and "espera_limpeza_min" not in h
    assert c.get("/api/relatorios/exportar/mesas.csv").status_code == 404
    from pathlib import Path
    raiz = Path(__file__).resolve().parent.parent / "frontend"
    for arq in [*raiz.glob("**/*.js"), *raiz.glob("**/*.html")]:
        if "vendor" in arq.parts:
            continue
        txt = arq.read_text(encoding="utf-8").lower()
        assert "smart table" not in txt and "smart-tables" not in txt, arq


def test_cliente_qr_avaliacao_e_solicitacao_chegam_ao_painel():
    svg = c.get("/api/qrcode/3.svg")
    assert svg.status_code == 200 and svg.headers["content-type"].startswith("image/svg")
    antes = c.get("/api/cliente/resumo").json()
    assert c.post("/api/avaliacoes", json={"mesa": 3, "nota_geral": 5, "nota_comida": 4, "comentario": "Teste"}).status_code == 201
    assert c.post("/api/avaliacoes", json={"mesa": 3, "nota_geral": 9}).status_code == 422
    s = publico.post("/api/solicitacoes", json={"mesa": 3, "motivo": "Chamar garçom"})
    assert s.status_code == 201
    assert publico.post("/api/manifestacoes", json={"mesa": 3, "tipo": "reclamacao", "categoria": "Limpeza", "texto": "Mesa suja"}).status_code == 201
    depois = c.get("/api/cliente/resumo").json()
    assert depois["avaliacoes"] == antes["avaliacoes"] + 1
    assert depois["reclamacoes_novas"] == antes["reclamacoes_novas"] + 1
    # integração: o pedido aparece nos alertas da Visão Geral
    alertas = c.get("/api/alertas").json()["alertas"]
    assert any(a["mesa"] == 3 and "Chamar garçom" in a["texto"] for a in alertas)
    assert c.post(f"/api/solicitacoes/{s.json()['id']}/status", json={"status": "resolvida"}).status_code == 200
    assert not any(a.get("id") == s.json()["id"] and a["modulo"] == "cliente" and "Chamar garçom" in a["texto"]
                   for a in c.get("/api/alertas").json()["alertas"])


def test_pedir_a_conta_foi_removido():
    """A Bovinu'S trabalha com comanda: o cliente não pede a conta pelo QR Code."""
    assert "Pedir a conta" not in publico.get("/api/cliente/opcoes").json()["motivos_atendimento"]
    assert publico.post("/api/solicitacoes", json={"mesa": 2, "motivo": "Pedir a conta"}).status_code == 400
    from pathlib import Path
    raiz = Path(__file__).resolve().parent.parent
    for arq in [*(raiz / "frontend").glob("**/*.js"), *(raiz / "frontend").glob("**/*.html"), *(raiz / "backend").glob("**/*.py")]:
        if "vendor" in arq.parts:
            continue
        assert "pedir a conta" not in arq.read_text(encoding="utf-8").lower().replace('"pedir a conta" not', ""), arq


def test_opcao_outro_exige_texto_e_aparece_no_painel():
    r = publico.post("/api/solicitacoes", json={"mesa": 6, "motivo": "Outro"})
    assert r.status_code == 400 and "Outro" in r.json()["detail"]
    r = publico.post("/api/solicitacoes", json={"mesa": 6, "motivo": "Outro", "motivo_outro": "  Trazer   cadeirinha de bebê "})
    assert r.status_code == 201
    sol = next(x for x in c.get("/api/solicitacoes?abertas=true").json()["solicitacoes"] if x["id"] == r.json()["id"])
    assert sol["motivo"] == "Outro" and sol["motivo_outro"] == "Trazer cadeirinha de bebê"
    assert any("Outro: Trazer cadeirinha de bebê" in a["descricao"] for a in c.get("/api/atividades?limite=5").json()["atividades"])
    # outro pedido "Outro" com texto diferente não é tratado como duplicado
    assert publico.post("/api/solicitacoes", json={"mesa": 6, "motivo": "Outro", "motivo_outro": "Mais guardanapos"}).json()["id"] != r.json()["id"]
    # sugestão/reclamação: categoria obrigatória; "Outro" exige o assunto
    base = {"mesa": 6, "tipo": "sugestao", "texto": "Teria como ter tomada perto da mesa?"}
    assert publico.post("/api/manifestacoes", json=base).status_code == 422
    assert publico.post("/api/manifestacoes", json={**base, "categoria": "Outro"}).status_code == 400
    m = publico.post("/api/manifestacoes", json={**base, "categoria": "Outro", "categoria_outro": "Estrutura"})
    assert m.status_code == 201
    lst = c.get("/api/manifestacoes?tipo=sugestao&limite=5").json()["manifestacoes"]
    assert lst[0]["categoria"] == "Outro" and lst[0]["categoria_outro"] == "Estrutura"
    assert "categoria_outro" in c.get("/api/relatorios/exportar/manifestacoes.csv").text


def test_alimentos_modo_manual_foto_registro_retorno():
    st = c.get("/api/alimentar/status").json()
    assert st["modo"] == "manual" and not st["ia_disponivel"]
    up = c.post("/api/alimentar/analisar", files={"imagem": ("prato.png", PNG_1PX, "image/png")})
    assert up.status_code == 200, up.text
    img = up.json()["imagem"]
    assert c.get(f"/uploads/{img}").status_code == 200
    assert publico.get(f"/uploads/{img}").status_code == 401  # fotos só para a equipe
    assert c.get("/uploads/..%2Fcodemeat_v2.db").status_code == 404
    antes = c.get("/api/alimentar/resumo").json()
    r = c.post("/api/alimentar/registros", json={
        "mesa": 5, "imagem": img, "metodo_reconhecimento": "ia_local",  # sem motor de IA, deve virar manual
        "itens": [{"alimento": "Arroz", "origem": "ia"}, {"alimento": "Picanha"}],
        "peso_total_g": 500, "origem_peso": "informado"})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    reg = c.get(f"/api/alimentar/registros/{rid}").json()
    assert reg["metodo_reconhecimento"] == "manual"
    assert all(i["origem"] == "manual" for i in reg["itens"])
    assert reg["peso_total_origem"] == "informado"
    arroz = next(i for i in reg["itens"] if i["alimento"] == "Arroz")
    assert c.post(f"/api/alimentar/registros/{rid}/retorno", json={"peso_residual_g": 600}).status_code == 400
    assert c.post(f"/api/alimentar/registros/{rid}/retorno",
                  json={"peso_residual_g": 50, "itens_sobra": [arroz["id"]]}).status_code == 200
    reg = c.get(f"/api/alimentar/registros/{rid}").json()
    assert reg["desperdicio_pct"] == 10.0
    depois = c.get("/api/alimentar/resumo").json()
    assert depois["registros"] == antes["registros"] + 1
    assert depois["pratos_com_retorno"] == antes["pratos_com_retorno"] + 1
    assert c.post("/api/alimentar/analisar", files={"imagem": ("x.txt", b"oi", "text/plain")}).status_code == 400


def test_imagem_invalida_e_rejeitada():
    r = c.post("/api/alimentar/analisar", files={"imagem": ("falsa.jpg", b"isto nao e uma imagem", "image/jpeg")})
    assert r.status_code == 400 and "imagem válida" in r.json()["detail"]
    r = c.post("/api/alimentar/analisar", files={"imagem": ("vazia.jpg", b"", "image/jpeg")})
    assert r.status_code == 400


def test_atividades_e_exportacao():
    at = c.get("/api/atividades?limite=200").json()["atividades"]
    modulos = {a["modulo"] for a in at if a["origem_dado"] == "real"}
    assert {"alimentar", "cliente"} <= modulos and "mesas" not in modulos
    csv = c.get("/api/relatorios/exportar/pratos.csv")
    assert csv.status_code == 200 and "origem_dado" in csv.text


def test_remover_demo_preserva_registros_reais():
    reais = c.get("/api/sistema").json()["registros_reais"]
    media_real = c.get("/api/cliente/resumo?origem=real").json()["media_geral"]
    assert c.post("/api/sistema/demo/remover").status_code == 200
    s = c.get("/api/sistema").json()
    assert s["registros_demo"] == 0 and s["registros_reais"] == reais
    assert c.get("/api/dashboard").status_code == 200
    assert c.post("/api/sistema/demo/recriar").status_code == 200
    s = c.get("/api/sistema").json()
    assert s["registros_demo"] > 0 and s["registros_reais"] == reais
    assert c.get("/api/cliente/resumo?origem=real").json()["media_geral"] == media_real


def test_modo_demonstracao_media_configuravel_sem_tocar_nos_reais():
    real = c.get("/api/cliente/resumo?origem=real").json()
    r = c.post("/api/sistema/demo/recriar", json={"media_alvo": 4.8, "avaliacoes": 300, "dias": 30})
    assert r.status_code == 200 and r.json()["avaliacoes_demo"] == 300
    demo = c.get("/api/cliente/resumo?origem=demo").json()
    assert demo["avaliacoes"] == 300 and abs(demo["media_geral"] - 4.8) <= 0.01
    assert demo["distribuicao"]["5"] > demo["distribuicao"]["1"]  # predominantemente positivas
    depois = c.get("/api/cliente/resumo?origem=real").json()
    assert (depois["avaliacoes"], depois["media_geral"]) == (real["avaliacoes"], real["media_geral"])
    todos = c.get("/api/cliente/resumo").json()
    assert todos["avaliacoes"] == demo["avaliacoes"] + real["avaliacoes"]
    assert c.get("/api/sistema").json()["demo"]["media_alvo"] == 4.8
    p = c.get("/api/cliente/periodo?dias=30").json()
    assert len(p["serie"]) == 30 and sum(d["avaliacoes"] for d in p["serie"]) > 0
    assert [x["periodo"] for x in p["periodos"]][:2] == ["Hoje", "Últimos 7 dias"]
    assert c.post("/api/sistema/demo/recriar", json={"media_alvo": 6, "avaliacoes": 300, "dias": 30}).status_code == 422
    assert c.get("/api/cliente/resumo?origem=qualquer").status_code == 400


def test_login_e_permissoes_verificadas_no_servidor():
    # sem login: painel redireciona para o login e a API recusa
    assert publico.get("/", follow_redirects=False).headers["location"] == "/equipe/"
    for rota in ("/api/dashboard", "/api/cliente/resumo", "/api/solicitacoes", "/api/alimentar/registros",
                 "/api/relatorios/exportar/avaliacoes.csv", "/api/usuarios", "/api/sistema"):
        assert publico.get(rota).status_code == 401, rota
    # o QR Code da equipe só abre a página de login
    qr = publico.get("/api/qrcode/equipe.svg")
    assert qr.status_code == 200 and qr.headers["content-type"].startswith("image/svg")
    # senha errada e bloqueio após várias tentativas
    assert publico.post("/api/auth/login", json={"login": "t_garcom", "senha": "errada"}).status_code == 401
    for _ in range(5):
        publico.post("/api/auth/login", json={"login": "t_caixa", "senha": "errada"})
    assert publico.post("/api/auth/login", json={"login": "t_caixa", "senha": SENHA}).status_code == 429
    auth._limpar_falhas("t_caixa")

    garcom = entrar("garcom")
    eu = garcom.get("/api/auth/eu").json()["usuario"]
    assert eu["perfil"] == "garcom" and "senha_hash" not in eu
    assert garcom.get("/api/solicitacoes?abertas=true").status_code == 200
    sid = publico.post("/api/solicitacoes", json={"mesa": 8, "motivo": "Limpeza da mesa"}).json()["id"]
    assert garcom.post(f"/api/solicitacoes/{sid}/status", json={"status": "em_atendimento"}).status_code == 200
    for rota in ("/api/dashboard", "/api/cliente/resumo", "/api/relatorios/exportar/avaliacoes.csv",
                 "/api/usuarios", "/api/sistema", "/api/alimentar/registros"):
        assert garcom.get(rota).status_code == 403, rota
    assert garcom.post("/api/sistema/demo/remover").status_code == 403

    caixa = entrar("caixa")
    assert caixa.get("/api/alimentar/registros").status_code == 200
    assert caixa.get("/api/solicitacoes").status_code == 403
    assert caixa.get("/api/cliente/resumo").status_code == 403

    gerente = entrar("gerente")
    for rota in ("/api/dashboard", "/api/cliente/resumo", "/api/relatorios/exportar/avaliacoes.csv"):
        assert gerente.get(rota).status_code == 200, rota
    assert gerente.get("/api/usuarios").status_code == 403

    dono = entrar("proprietario")
    assert dono.get("/api/dashboard").status_code == 200 and dono.get("/api/relatorios/sinais").status_code == 200
    assert dono.post(f"/api/solicitacoes/{sid}/status", json={"status": "resolvida"}).status_code == 403
    assert dono.post("/api/alimentar/registros", json={"itens": [{"alimento": "Arroz"}]}).status_code == 403

    # cabeçalho mostra só o que o perfil pode ver
    assert "reclamacoes_novas" not in garcom.get("/api/cabecalho").json()
    assert "pedidos_abertos" in garcom.get("/api/cabecalho").json()


def test_administrador_gerencia_colaboradores_e_permissoes():
    novo = c.post("/api/usuarios", json={"nome": "Ana Garçonete", "login": "ana", "perfil": "garcom", "senha": "abc12345"})
    assert novo.status_code == 201
    assert c.post("/api/usuarios", json={"nome": "Outra", "login": "ana", "perfil": "garcom", "senha": "abc12345"}).status_code == 409
    assert c.post("/api/usuarios", json={"nome": "X", "login": "xx", "perfil": "chefe", "senha": "123"}).status_code == 422
    ana = TestClient(app)
    assert ana.post("/api/auth/login", json={"login": "ANA", "senha": "abc12345"}).status_code == 200
    assert ana.get("/api/cliente/resumo").status_code == 403
    # o administrador dá ao garçom acesso às avaliações: vale na hora, verificado no servidor
    assert c.put("/api/permissoes/garcom", json={"permissoes": ["atendimento_ver", "atendimento_atualizar", "cliente_ver", "inventada"]}).json()["permissoes"] == ["atendimento_ver", "atendimento_atualizar", "cliente_ver"]
    assert ana.get("/api/cliente/resumo").status_code == 200
    c.put("/api/permissoes/garcom", json={"permissoes": auth.PADRAO["garcom"]})
    assert ana.get("/api/cliente/resumo").status_code == 403
    assert c.put("/api/permissoes/admin", json={"permissoes": []}).status_code == 400
    # desativar encerra a sessão
    assert c.patch(f"/api/usuarios/{novo.json()['id']}", json={"ativo": False}).status_code == 200
    assert ana.get("/api/auth/eu").status_code == 401
    assert ana.post("/api/auth/login", json={"login": "ana", "senha": "abc12345"}).status_code == 401
    # o administrador não se desativa
    eu = c.get("/api/auth/eu").json()["usuario"]
    assert c.patch(f"/api/usuarios/{eu['id']}", json={"ativo": False}).status_code == 400
    # nenhuma senha sai pela API
    assert all("senha_hash" not in u for u in c.get("/api/usuarios").json()["usuarios"])
    with get_conn() as conn:
        h = conn.execute("SELECT senha_hash FROM usuarios WHERE login = 'ana'").fetchone()[0]
    assert "abc12345" not in h and h.startswith("pbkdf2_sha256$")


def test_sair_encerra_a_sessao():
    cl = entrar("gerente")
    assert cl.get("/api/auth/eu").status_code == 200
    assert cl.post("/api/auth/sair").status_code == 200
    assert cl.get("/api/auth/eu").status_code == 401


REGIAO = {"x": .1, "y": .1, "largura": .3, "altura": .3}


def test_motor_local_segmentacao_no_fluxo(monkeypatch):
    """Caminho padrão (YOLOE local) com o modelo substituído por um resultado fixo (o modelo real é testado com fotos reais)."""
    monkeypatch.setattr(segmentacao, "pacotes_instalados", lambda: True)
    monkeypatch.setattr(segmentacao, "carregado", lambda: True)
    monkeypatch.setattr(segmentacao, "reconhecer", lambda dados: {
        "prato_identificado": True, "descricao": "teste", "motor": "YOLOE local (teste)", "tempo_ms": 10,
        "itens": [{"alimento": "Arroz", "confianca": "alta", "confianca_pct": 84, "detalhes": ["arroz"]}],
        "regioes": [
            {"tipo": "alimento", "alimento": "Arroz", "detalhe": "arroz", "confianca_pct": 84, "confianca": "alta",
             "identificado": True, "regiao": REGIAO, "poligono": [[.1, .1], [.4, .1], [.4, .4]]},
            {"tipo": "alimento", "alimento": "Não identificado", "detalhe": None, "confianca_pct": 25, "confianca": None,
             "identificado": False, "regiao": REGIAO, "poligono": []},
            {"tipo": "objeto", "alimento": "Prato", "detalhe": "prato", "confianca_pct": 90, "confianca": "alta",
             "identificado": True, "regiao": REGIAO, "poligono": []}],
        "objetos": ["Prato"], "nao_identificados": 1, "largura_px": 1, "altura_px": 1})
    st = c.get("/api/alimentar/status").json()
    assert st["motor_ativo"] == "local" and st["segmentacao"] and "Carne" in st["categorias"]
    up = c.post("/api/alimentar/analisar", files={"imagem": ("prato.png", PNG_1PX, "image/png")}).json()
    assert up["metodo"] == "ia_local" and up["erro"] is None
    assert up["regioes"][0]["poligono"] and up["nao_identificados"] == 1 and up["objetos"] == ["Prato"]
    r = c.post("/api/alimentar/registros", json={"imagem": up["imagem"], "metodo_reconhecimento": "ia_local",
               "itens": [{"alimento": "Arroz", "origem": "ia", "confianca": "alta"}, {"alimento": "Carne"}],
               "peso_total_g": 480, "origem_peso": "simulado"})
    reg = c.get(f"/api/alimentar/registros/{r.json()['id']}").json()
    assert reg["metodo_reconhecimento"] == "ia_local" and reg["peso_total_origem"] == "simulado"
    assert {i["alimento"]: i["origem"] for i in reg["itens"]} == {"Arroz": "ia", "Carne": "manual"}


def test_falha_do_modelo_local_cai_para_manual(monkeypatch):
    monkeypatch.setattr(segmentacao, "pacotes_instalados", lambda: True)

    def falha(dados):
        raise segmentacao.ErroSegmentacao("Não foi possível carregar o modelo de reconhecimento local.")
    monkeypatch.setattr(segmentacao, "reconhecer", falha)
    up = c.post("/api/alimentar/analisar", files={"imagem": ("prato.png", PNG_1PX, "image/png")}).json()
    assert up["itens"] == [] and up["metodo"] == "manual" and "modelo" in up["erro"]


def test_fluxo_com_claude_simulado_no_teste(monkeypatch):
    """Caminho opcional do Claude, sem gastar a API: o motor é substituído por um resultado fixo."""
    monkeypatch.setattr(vision, "ia_disponivel", lambda: True)
    monkeypatch.setattr(vision, "reconhecer", lambda dados, tipo: {
        "prato_identificado": True, "descricao": "Prato de teste", "motor": "teste",
        "itens": [{"alimento": "Arroz", "confianca": "alta", "regiao": REGIAO},
                  {"alimento": "Farofa", "confianca": "baixa", "regiao": REGIAO}]})
    up = c.post("/api/alimentar/analisar", files={"imagem": ("prato.png", PNG_1PX, "image/png")}).json()
    assert up["metodo"] == "ia_claude" and [i["alimento"] for i in up["itens"]] == ["Arroz"]
    assert up["regioes"][1]["alimento"] == "Não identificado"  # confiança baixa não vira palpite
    r = c.post("/api/alimentar/registros", json={"imagem": up["imagem"], "metodo_reconhecimento": "ia_claude",
               "itens": [{"alimento": "Arroz", "origem": "ia", "confianca": "alta"}, {"alimento": "Feijão"}]})
    reg = c.get(f"/api/alimentar/registros/{r.json()['id']}").json()
    assert reg["metodo_reconhecimento"] == "ia_claude"
    origens = {i["alimento"]: i["origem"] for i in reg["itens"]}
    assert origens == {"Arroz": "ia", "Feijão": "manual"}


def test_erro_do_claude_cai_para_modo_manual(monkeypatch):
    def falha(dados, tipo):
        raise vision.ErroVisao("Sem conexão com a API de visão.")
    monkeypatch.setattr(vision, "ia_disponivel", lambda: True)
    monkeypatch.setattr(vision, "reconhecer", falha)
    up = c.post("/api/alimentar/analisar", files={"imagem": ("prato.png", PNG_1PX, "image/png")}).json()
    assert up["itens"] == [] and up["modo"] == "manual" and up["metodo"] == "manual" and "conexão" in up["erro"]
