"""MODO DEMONSTRAÇÃO · dados DEMONSTRATIVOS do Code Meat.

Tudo o que este arquivo cria é fictício e fica marcado com origem_dado='demo'
(e pesagens com origem 'simulado'). Serve para a apresentação ter gráficos e
indicadores com volume. Não representa dados reais da Bovinu'S.

A nota média das avaliações FICTÍCIAS pode ser escolhida (Configurações > Modo
demonstração). Isso só muda quais notas fictícias são geradas: as avaliações reais
nunca são alteradas e o cálculo da média é sempre a média simples das notas gravadas.

Uso:  python run.py --reset   (apaga os registros e recria os dados demonstrativos)
"""
import math
import random
from datetime import datetime, timedelta

from .db import config_ler, get_conn, init_db, registrar_atividade

DEMO = "demo"
PADRAO_DEMO = {"media_alvo": 4.7, "avaliacoes": 360, "dias": 30}

SOBRA_TIPICA = {  # probabilidade ilustrativa de o alimento sobrar no prato
    "Arroz": 0.32, "Salada": 0.24, "Acompanhamentos": 0.18, "Carne": 0.10, "Feijão": 0.08,
    "Batata frita": 0.10, "Frango": 0.12, "Linguiça": 0.09,
}
# Mesmas categorias usadas pelo reconhecimento automático (backend/segmentacao.py)
BASE = ["Arroz", "Feijão"]
OPCIONAIS = ["Salada", "Batata frita", "Acompanhamentos"]
CARNES = ["Carne", "Frango", "Linguiça"]
COMENTARIOS = {
    5: ["Carne no ponto certo, voltaremos!", "Atendimento muito atencioso.", "Saladas sempre fresquinhas.",
        "Buffet bem variado e tudo quentinho.", "Melhor almoço da região.", "Ótimo custo-benefício no almoço.",
        "Equipe rápida e simpática.", None, None, None, None],
    4: ["Comida muito boa, só demorou um pouco para liberar a mesa.", "Gostei bastante, voltarei.",
        "Carnes ótimas, salada poderia ter mais opções.", None, None, None],
    3: ["Comida boa, mas o salão estava cheio e barulhento.", "Demorou a reposição de algumas carnes.", None],
    2: ["Demorou para liberarem a mesa.", "Faltou reposição de farofa no buffet."],
    1: ["A mesa estava suja quando sentamos.", "Esperamos muito para sermos atendidos."],
}
SUGESTOES = [("Comida", "Poderiam ter opção vegetariana no buffet."),
             ("Ambiente", "Música um pouco mais baixa no almoço."),
             ("Atendimento", "Mais agilidade para liberar as mesas no horário de pico."),
             ("Preço", "Combo de almoço com bebida inclusa."),
             ("Outro", "Ter cadeirinha de bebê disponível.", "Acessibilidade")]
RECLAMACOES = [("Limpeza", "Esperamos uns 10 minutos com a mesa suja."),
               ("Tempo de espera", "Fila grande para pegar mesa às 12h30."),
               ("Comida", "Arroz estava frio."),
               ("Atendimento", "Chamamos o garçom duas vezes até sermos atendidos.")]
MOTIVOS = ["Chamar garçom", "Chamar garçom", "Reposição no buffet", "Limpeza da mesa"]


def _iso(d: datetime) -> str:
    return d.isoformat(timespec="seconds")


def config_demo(conn) -> dict:
    """Parâmetros do modo demonstração salvos em Configurações (ou os padrões)."""
    return {
        "media_alvo": float(config_ler(conn, "demo_media_alvo", PADRAO_DEMO["media_alvo"])),
        "avaliacoes": int(config_ler(conn, "demo_avaliacoes", PADRAO_DEMO["avaliacoes"])),
        "dias": int(config_ler(conn, "demo_dias", PADRAO_DEMO["dias"])),
    }


def garantir_mesas(conn) -> list[int]:
    """24 mesas (20 no salão e 4 na varanda), usadas só para os QR Codes. Não duplica."""
    for numero in range(1, 25):
        area = "Salão" if numero <= 20 else "Varanda"
        conn.execute("INSERT OR IGNORE INTO mesas (numero, area) VALUES (?, ?)", (numero, area))
    return [r[0] for r in conn.execute("SELECT id FROM mesas ORDER BY numero")]


def notas_com_media(n: int, alvo: float, rnd: random.Random) -> list[int]:
    """n notas de 1 a 5, predominantemente positivas, com média o mais perto possível do alvo.

    Distribuição p(k) proporcional a exp(t*k): t é ajustado para a média bater com o alvo.
    Depois as contagens são arredondadas e corrigidas uma a uma até a média ficar no alvo.
    """
    alvo = min(4.98, max(1.02, alvo))

    def media(t):
        w = [math.exp(t * k) for k in range(1, 6)]
        return sum(k * x for k, x in zip(range(1, 6), w)) / sum(w)

    lo, hi = -12.0, 12.0
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if media(mid) < alvo else (lo, mid)
    w = [math.exp(lo * k) for k in range(1, 6)]
    p = [x / sum(w) for x in w]
    cont = [int(n * x) for x in p]
    for i in sorted(range(5), key=lambda i: n * p[i] - cont[i], reverse=True)[: n - sum(cont)]:
        cont[i] += 1
    soma_alvo = round(alvo * n)
    for _ in range(4 * n):  # corrige para a soma das notas bater com a média alvo
        soma = sum((k + 1) * c for k, c in enumerate(cont))
        if soma == soma_alvo:
            break
        if soma < soma_alvo:  # sobe uma nota (da maior faixa possível abaixo de 5)
            k = next((k for k in range(3, -1, -1) if cont[k]), None)
            if k is None:
                break
            cont[k] -= 1
            cont[k + 1] += 1
        else:
            k = next((k for k in range(4, 0, -1) if cont[k]), None)
            if k is None:
                break
            cont[k] -= 1
            cont[k - 1] += 1
    notas = [k + 1 for k, c in enumerate(cont) for _ in range(c)]
    rnd.shuffle(notas)
    return notas


def prato(conn, rnd, quando: datetime, mesa_id: int | None, com_retorno: bool = True):
    itens = BASE[: rnd.choice([1, 2, 2])] + rnd.sample(OPCIONAIS, rnd.randint(1, 2)) + rnd.sample(CARNES, rnd.randint(1, 2))
    pico = 13 <= quando.hour < 14
    cur = conn.execute(
        "INSERT INTO registros_prato (mesa_id, imagem, metodo_reconhecimento, observacao, criado_em, origem_dado) VALUES (?, NULL, 'manual', ?, ?, ?)",
        (mesa_id, "Registro demonstrativo (sem foto)", _iso(quando), DEMO))
    rid = cur.lastrowid
    total = rnd.randint(330, 760)
    sobra_g = 0
    for nome in itens:
        p = SOBRA_TIPICA.get(nome, 0.1) * (1.35 if pico else 1.0)
        sobrou = com_retorno and rnd.random() < p
        if sobrou:
            sobra_g += rnd.randint(15, 70)
        conn.execute("INSERT INTO itens_reconhecidos (registro_id, alimento, confianca, origem, sobrou) VALUES (?, ?, NULL, 'manual', ?)",
                     (rid, nome, int(sobrou)))
    conn.execute("INSERT INTO pesagens (registro_id, tipo, peso_g, origem, criado_em) VALUES (?, 'total', ?, 'simulado', ?)",
                 (rid, total, _iso(quando)))
    if com_retorno:
        volta = quando + timedelta(minutes=rnd.randint(25, 50))
        conn.execute("INSERT INTO pesagens (registro_id, tipo, peso_g, origem, criado_em) VALUES (?, 'residual', ?, 'simulado', ?)",
                     (rid, min(sobra_g, total), _iso(volta)))
    return rid


def _manifestacao(conn, rnd, mesas, tipo, item, quando, status):
    cat, txt = item[0], item[1]
    outro = item[2] if len(item) > 2 else None
    conn.execute("INSERT INTO manifestacoes (mesa_id, tipo, categoria, categoria_outro, texto, status, criado_em, origem_dado)"
                 " VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (rnd.choice(mesas), tipo, cat, outro, txt, status, _iso(quando), DEMO))


def popular(conn, media_alvo: float = PADRAO_DEMO["media_alvo"], avaliacoes: int = PADRAO_DEMO["avaliacoes"],
            dias: int = PADRAO_DEMO["dias"], agora: datetime | None = None, semente: int = 42) -> dict:
    """Cria os dados demonstrativos. Não apaga nada: chame remover_demo antes para recriar."""
    rnd = random.Random(semente)
    agora = agora or datetime.now().replace(microsecond=0)
    mesas = garantir_mesas(conn)
    hoje0 = agora.replace(hour=0, minute=0, second=0)

    # 1) Pratos, manifestações e pedidos dos almoços anteriores
    for d in range(dias, 0, -1):
        inicio = (hoje0 - timedelta(days=d)).replace(hour=11, minute=30)
        for _ in range(rnd.randint(22, 30)):
            prato(conn, rnd, inicio + timedelta(minutes=int(rnd.triangular(0, 200, 75))), rnd.choice(mesas))
        if rnd.random() < 0.45:
            _manifestacao(conn, rnd, mesas, "sugestao", rnd.choice(SUGESTOES), inicio + timedelta(minutes=rnd.randint(30, 180)), "resolvida")
        if rnd.random() < 0.5:
            _manifestacao(conn, rnd, mesas, "reclamacao", rnd.choice(RECLAMACOES), inicio + timedelta(minutes=rnd.randint(50, 150)), "resolvida")
        for _ in range(rnd.randint(4, 8)):
            c = inicio + timedelta(minutes=rnd.randint(10, 190))
            at = c + timedelta(minutes=rnd.uniform(1, 6))
            conn.execute(
                "INSERT INTO solicitacoes_atendimento (mesa_id, motivo, status, criado_em, atendido_em, resolvido_em, origem_dado) VALUES (?, ?, 'resolvida', ?, ?, ?, ?)",
                (rnd.choice(mesas), rnd.choice(MOTIVOS), _iso(c), _iso(at), _iso(at + timedelta(minutes=rnd.uniform(1, 4))), DEMO))

    # 2) Avaliações: volume escolhido e média alvo (só para as fictícias)
    notas = notas_com_media(avaliacoes, media_alvo, rnd)
    hoje_inicio = hoje0.replace(hour=11, minute=30)
    hoje_ok = agora > hoje_inicio + timedelta(minutes=20)
    for i, nota in enumerate(notas):
        if hoje_ok and i < max(3, avaliacoes // (dias * 2)):  # algumas avaliações de hoje, antes de agora
            quando = hoje_inicio + timedelta(seconds=rnd.randint(0, int(min((agora - hoje_inicio).total_seconds(), 12600)) - 60))
        else:
            dia = hoje0 - timedelta(days=rnd.randint(1, dias))
            quando = dia.replace(hour=11, minute=30) + timedelta(minutes=int(rnd.triangular(10, 215, 90)))
        com = rnd.choice(COMENTARIOS[nota])
        conn.execute(
            "INSERT INTO avaliacoes (mesa_id, nota_geral, nota_atendimento, nota_comida, comentario, criado_em, origem_dado) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (rnd.choice(mesas), nota, max(1, min(5, nota + rnd.choice([-1, 0, 0, 0, 1]))),
             max(1, min(5, nota + rnd.choice([0, 0, 0, 1, -1]))), com, _iso(quando), DEMO))

    # 3) Movimento de hoje: pratos recentes, pedidos em aberto e uma reclamação nova
    for i in range(6):
        prato(conn, rnd, agora - timedelta(minutes=10 * (i + 1)), rnd.choice(mesas), com_retorno=i >= 2)
    for numero, motivo, outro, min_atras in [(1, "Chamar garçom", None, 3), (4, "Outro", "Trazer uma cadeirinha de bebê", 1)]:
        conn.execute("INSERT INTO solicitacoes_atendimento (mesa_id, motivo, motivo_outro, status, criado_em, origem_dado)"
                     " VALUES (?, ?, ?, 'pendente', ?, ?)", (mesas[numero - 1], motivo, outro, _iso(agora - timedelta(minutes=min_atras)), DEMO))
    conn.execute("INSERT INTO manifestacoes (mesa_id, tipo, categoria, texto, status, criado_em, origem_dado) VALUES (?, 'reclamacao', 'Limpeza', ?, 'nova', ?, ?)",
                 (mesas[4], "Sentamos e a mesa ainda estava com restos do cliente anterior.", _iso(agora - timedelta(minutes=12)), DEMO))

    # Linha do tempo de hoje, derivada dos registros demonstrativos acima
    hoje = agora.date().isoformat()
    for r in conn.execute("SELECT id, criado_em FROM registros_prato WHERE criado_em >= ? AND origem_dado = 'demo'", (hoje,)).fetchall():
        registrar_atividade(conn, "alimentar", "registro", f"Prato #{r[0]} registrado", r[0], r[1], DEMO)
    for r in conn.execute("SELECT s.id, s.criado_em, s.motivo, s.motivo_outro, m.numero FROM solicitacoes_atendimento s JOIN mesas m ON m.id = s.mesa_id"
                          " WHERE s.criado_em >= ? AND s.origem_dado = 'demo'", (hoje,)).fetchall():
        motivo = f"Outro: {r[3]}" if r[2] == "Outro" and r[3] else r[2]
        registrar_atividade(conn, "cliente", "solicitacao", f"Mesa {r[4]} pediu atendimento: {motivo}", r[0], r[1], DEMO)
    for r in conn.execute("SELECT x.id, x.criado_em, x.categoria, m.numero FROM manifestacoes x JOIN mesas m ON m.id = x.mesa_id"
                          " WHERE x.criado_em >= ? AND x.tipo = 'reclamacao' AND x.origem_dado = 'demo'", (hoje,)).fetchall():
        registrar_atividade(conn, "cliente", "reclamacao", f"Mesa {r[3]}: Reclamação ({r[2]})", r[0], r[1], DEMO)
    for r in conn.execute("SELECT a.id, a.criado_em, a.nota_geral, m.numero FROM avaliacoes a JOIN mesas m ON m.id = a.mesa_id"
                          " WHERE a.criado_em >= ? AND a.origem_dado = 'demo'", (hoje,)).fetchall():
        registrar_atividade(conn, "cliente", "avaliacao", f"Mesa {r[3]}: nova avaliação, nota {r[2]}/5", r[0], r[1], DEMO)
    media = sum(notas) / len(notas) if notas else None
    registrar_atividade(conn, "sistema", "demo",
                        f"Dados demonstrativos gerados: {len(notas)} avaliações fictícias (média {media:.2f}) em {dias} dias",
                        None, _iso(agora), DEMO)
    return {"avaliacoes_demo": len(notas), "media_demo": round(media, 2) if media else None, "dias": dias}


def apagar_tudo(conn) -> None:
    """Apaga os registros dos dois pilares (reais e demonstrativos). Colaboradores e configurações ficam."""
    for t in ("atividades", "solicitacoes_atendimento", "manifestacoes", "avaliacoes",
              "pesagens", "itens_reconhecidos", "registros_prato", "mesas"):
        conn.execute(f"DELETE FROM {t}")
    conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('atividades', 'solicitacoes_atendimento', 'manifestacoes',"
                 " 'avaliacoes', 'pesagens', 'itens_reconhecidos', 'registros_prato', 'mesas')")


def remover_demo(conn) -> None:
    """Remove só os registros demonstrativos, preservando o que foi registrado de verdade."""
    conn.execute("DELETE FROM registros_prato WHERE origem_dado = 'demo'")  # cascata em itens e pesagens
    for t in ("avaliacoes", "manifestacoes", "solicitacoes_atendimento", "atividades"):
        conn.execute(f"DELETE FROM {t} WHERE origem_dado = 'demo'")


def recriar_demo() -> None:
    """python run.py --reset: apaga os registros (com backup antes) e recria a demonstração."""
    from .db import backup
    init_db()
    backup("antes-do-reset")
    with get_conn() as conn:
        apagar_tudo(conn)
        popular(conn, **config_demo(conn))


def banco_vazio() -> bool:
    init_db()
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM mesas").fetchone()[0] == 0


if __name__ == "__main__":
    recriar_demo()
    print("Banco recriado com dados demonstrativos.")
