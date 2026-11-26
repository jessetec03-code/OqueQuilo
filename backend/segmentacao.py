"""Reconhecimento LOCAL de alimentos com segmentação (motor padrão do Code Meat).

Motor: YOLOE (Ultralytics, licença AGPL-3.0), modelo de segmentação de vocabulário
aberto: recebe uma lista de nomes em texto e devolve, para cada região encontrada,
a classe, a confiança e o contorno (máscara) na foto. Roda no próprio computador,
sem internet depois do primeiro download dos pesos e sem custo de API.

É opcional: depende de requirements-visao.txt (ultralytics + CLIP). Sem esses
pacotes, o sistema continua funcionando com marcação manual (ou com o Claude, se
configurado).

Regras de honestidade aplicadas aqui:
- abaixo de CONF_IDENTIFICADO a região aparece como "Não identificado";
  o sistema não chuta um alimento.
- objetos que não são comida (prato, talher, copo, mesa) são listados à parte.
- o modelo NÃO mede peso. O peso total vem da balança, é informado ou é simulado.

O modelo não foi treinado com pratos brasileiros. Ele reconhece categorias gerais
(carne, arroz, feijão...) a partir de descrições em inglês. Veja as limitações em
docs/RECONHECIMENTO.md.
"""
from __future__ import annotations

import io
import os
import threading
import time
from importlib.util import find_spec
from pathlib import Path

from .settings import YOLOE_MODELO

RAIZ = Path(__file__).resolve().parent.parent
PASTA_MODELOS = RAIZ / "data" / "modelos"

# Limiares de confiança (0 a 1), calibrados com fotos reais de pratos (ver docs/TESTES.md)
CONF_MINIMA = 0.20        # abaixo disso a região é descartada
CONF_IDENTIFICADO = 0.35  # entre a mínima e este valor: "Não identificado"
CONF_ALTA = 0.55          # a partir daqui: confiança alta

# Texto enviado ao modelo (inglês) -> (categoria exibida, detalhe em português, tipo)
# As categorias seguem o pedido do restaurante: carnes, arroz, feijão, batata frita,
# salada, frango, linguiça e acompanhamentos.
PROMPTS: list[tuple[str, str, str, str]] = [
    ("steak", "Carne", "carne", "alimento"),
    ("grilled meat", "Carne", "carne grelhada", "alimento"),
    ("ground beef", "Carne", "carne moída", "alimento"),
    ("sliced beef", "Carne", "carne fatiada", "alimento"),
    ("rice", "Arroz", "arroz", "alimento"),
    ("white rice", "Arroz", "arroz branco", "alimento"),
    ("beans", "Feijão", "feijão", "alimento"),
    ("pinto beans", "Feijão", "feijão carioca", "alimento"),
    ("bean stew", "Feijão", "feijão com caldo", "alimento"),
    ("french fries", "Batata frita", "batata frita", "alimento"),
    ("salad", "Salada", "salada", "alimento"),
    ("lettuce", "Salada", "alface", "alimento"),
    ("cherry tomato", "Salada", "tomate", "alimento"),
    ("cucumber slices", "Salada", "pepino", "alimento"),
    ("chicken", "Frango", "frango", "alimento"),
    ("grilled chicken breast", "Frango", "frango grelhado", "alimento"),
    ("fried chicken", "Frango", "frango frito", "alimento"),
    ("sausage", "Linguiça", "linguiça", "alimento"),
    ("pasta", "Acompanhamentos", "massa", "alimento"),
    ("gnocchi", "Acompanhamentos", "nhoque", "alimento"),
    ("mashed potato", "Acompanhamentos", "purê", "alimento"),
    ("potato salad", "Acompanhamentos", "maionese", "alimento"),
    ("carrot", "Acompanhamentos", "legumes", "alimento"),
    ("beet", "Acompanhamentos", "beterraba", "alimento"),
    ("breadcrumbs", "Acompanhamentos", "farofa", "alimento"),
    ("crumbs with bacon", "Acompanhamentos", "farofa", "alimento"),
    ("plate", "Prato", "prato", "objeto"),
    ("bowl", "Prato", "tigela", "objeto"),
    ("fork", "Talher", "garfo", "objeto"),
    ("knife", "Talher", "faca", "objeto"),
    ("glass", "Copo", "copo", "objeto"),
]
CATEGORIAS = ["Carne", "Arroz", "Feijão", "Batata frita", "Salada", "Frango", "Linguiça", "Acompanhamentos"]


class ErroSegmentacao(Exception):
    pass


_trava = threading.Lock()
_modelo = None
_erro_carga: str | None = None


def pacotes_instalados() -> bool:
    return find_spec("ultralytics") is not None and find_spec("clip") is not None


def disponivel() -> bool:
    return pacotes_instalados() and _erro_carga is None


def carregado() -> bool:
    return _modelo is not None


def status() -> dict:
    if not pacotes_instalados():
        return {"disponivel": False, "carregado": False, "modelo": YOLOE_MODELO,
                "mensagem": "Reconhecimento local não instalado (rode: pip install -r requirements-visao.txt e reinicie)."}
    if _erro_carga:
        return {"disponivel": False, "carregado": False, "modelo": YOLOE_MODELO,
                "mensagem": f"Não foi possível carregar o modelo local: {_erro_carga}"}
    return {"disponivel": True, "carregado": carregado(), "modelo": YOLOE_MODELO,
            "mensagem": "Reconhecimento local ativo (IA no próprio computador, sem custo de API)."
            if carregado() else "Reconhecimento local instalado. O modelo carrega na primeira foto (alguns segundos)."}


def carregar():
    """Carrega o modelo uma única vez (thread-safe). Na 1ª vez baixa os pesos do GitHub."""
    global _modelo, _erro_carga
    with _trava:
        if _modelo is not None:
            return _modelo
        try:
            from ultralytics import YOLOE

            PASTA_MODELOS.mkdir(parents=True, exist_ok=True)
            anterior = os.getcwd()
            os.chdir(PASTA_MODELOS)  # o Ultralytics baixa o codificador de texto na pasta atual
            try:
                m = YOLOE(YOLOE_MODELO)
                nomes = [p[0] for p in PROMPTS]
                m.set_classes(nomes, m.get_text_pe(nomes))
            finally:
                os.chdir(anterior)
            _modelo = m
        except Exception as e:  # sem internet no 1º uso, pesos corrompidos, etc.
            _erro_carga = f"{type(e).__name__}: {e}"[:300]
            raise ErroSegmentacao("Não foi possível carregar o modelo de reconhecimento local.") from e
        return _modelo


def abrir_imagem(dados: bytes):
    """Abre a foto, corrige a rotação do celular (EXIF) e converte para RGB."""
    from PIL import Image, ImageOps

    try:
        im = Image.open(io.BytesIO(dados))
        im = ImageOps.exif_transpose(im).convert("RGB")
    except Exception as e:  # inclui UnidentifiedImageError e erros de plugins do Ultralytics
        raise ErroSegmentacao("O arquivo não é uma imagem válida ou está corrompido.") from e
    return im


def _simplificar(poligono, max_pontos: int = 80) -> list[list[float]]:
    pts = [[round(float(x), 4), round(float(y), 4)] for x, y in poligono]
    if len(pts) > max_pontos:
        passo = len(pts) / max_pontos
        pts = [pts[int(i * passo)] for i in range(max_pontos)]
    return pts


def nivel(conf: float) -> str | None:
    if conf >= CONF_ALTA:
        return "alta"
    if conf >= CONF_IDENTIFICADO:
        return "media"
    return None


def reconhecer(dados: bytes) -> dict:
    """Segmenta a foto e devolve regiões (com contorno), alimentos identificados e objetos."""
    im = abrir_imagem(dados)
    modelo = carregar()
    inicio = time.perf_counter()
    with _trava:  # uma inferência por vez (CPU)
        r = modelo.predict(im, conf=CONF_MINIMA, imgsz=640, verbose=False)[0]
    ms = round((time.perf_counter() - inicio) * 1000)

    regioes = []
    poligonos = r.masks.xyn if r.masks is not None else []
    for i, (cls, conf, caixa) in enumerate(zip(r.boxes.cls.tolist(), r.boxes.conf.tolist(), r.boxes.xyxyn.tolist())):
        _, categoria, detalhe, tipo = PROMPTS[int(cls)]
        x1, y1, x2, y2 = caixa
        conf = float(conf)
        identificado = tipo == "objeto" or conf >= CONF_IDENTIFICADO
        regioes.append({
            "tipo": tipo,
            "alimento": categoria if identificado else "Não identificado",
            "detalhe": detalhe if identificado else None,
            "confianca_pct": round(conf * 100),
            "confianca": nivel(conf),
            "identificado": identificado,
            "regiao": {"x": round(x1, 4), "y": round(y1, 4), "largura": round(x2 - x1, 4), "altura": round(y2 - y1, 4)},
            "poligono": _simplificar(poligonos[i]) if i < len(poligonos) and len(poligonos[i]) >= 3 else [],
        })
    regioes.sort(key=lambda g: (g["tipo"] != "alimento", not g["identificado"], -g["confianca_pct"]))

    # Lista resumida por categoria (maior confiança de cada uma), usada para confirmar o registro
    itens: dict[str, dict] = {}
    for g in regioes:
        if g["tipo"] != "alimento" or not g["identificado"]:
            continue
        atual = itens.get(g["alimento"])
        if not atual:
            itens[g["alimento"]] = {"alimento": g["alimento"], "confianca": g["confianca"],
                                    "confianca_pct": g["confianca_pct"], "detalhes": [g["detalhe"]], "regioes": 1}
        else:
            atual["regioes"] += 1
            if g["detalhe"] not in atual["detalhes"]:
                atual["detalhes"].append(g["detalhe"])
    alimentos = sorted(itens.values(), key=lambda a: -a["confianca_pct"])
    nao_id = sum(1 for g in regioes if g["tipo"] == "alimento" and not g["identificado"])
    objetos = sorted({g["alimento"] for g in regioes if g["tipo"] == "objeto"})
    if alimentos:
        desc = f"{len(alimentos)} categoria(s) de alimento identificada(s)"
    else:
        desc = "Nenhum alimento identificado com confiança suficiente"
    if nao_id:
        desc += f", {nao_id} região(ões) não identificada(s)"
    return {
        "prato_identificado": bool(alimentos) or "Prato" in objetos,
        "descricao": desc + ".",
        "itens": [{"alimento": a["alimento"], "confianca": a["confianca"], "confianca_pct": a["confianca_pct"],
                   "detalhes": a["detalhes"]} for a in alimentos],
        "regioes": regioes,
        "objetos": objetos,
        "nao_identificados": nao_id,
        "largura_px": im.width,
        "altura_px": im.height,
        "tempo_ms": ms,
        "motor": "IA local",
        "modelo": YOLOE_MODELO.removesuffix(".pt"),
    }
