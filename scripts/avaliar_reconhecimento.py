"""Avalia o reconhecimento local (YOLOE) com fotos reais de pratos.

Uso (na pasta do projeto, com requirements-visao.txt instalado):
    python -m scripts.avaliar_reconhecimento tests/fotos_reais

A pasta precisa ter as fotos (.jpg/.jpeg/.png) e um arquivo gabarito.json com as
categorias que REALMENTE aparecem em cada foto, por exemplo:
    {"IMG_6164.jpeg": ["Arroz", "Feijão", "Carne", "Salada"]}

Saída: tabela por foto (acertos, faltas e falsos positivos por categoria) e imagens
com os contornos desenhados em <pasta>/resultado/. Nada é inventado: o script só
compara o que o modelo devolveu com o gabarito escrito por uma pessoa.
"""
import json
import sys
from pathlib import Path

from backend import segmentacao

CORES = [(225, 29, 72), (14, 165, 233), (124, 58, 237), (245, 158, 11), (22, 163, 74), (234, 88, 12), (219, 39, 119), (13, 148, 136)]


def desenhar(dados: bytes, r: dict, destino: Path) -> None:
    from PIL import Image, ImageDraw

    im = segmentacao.abrir_imagem(dados).convert("RGBA")
    w, h = im.size
    camada = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    for g in r["regioes"]:
        if g["tipo"] != "alimento" or len(g["poligono"]) < 3:
            continue
        cor = CORES[segmentacao.CATEGORIAS.index(g["alimento"]) % len(CORES)] if g["identificado"] else (150, 150, 150)
        d.polygon([(x * w, y * h) for x, y in g["poligono"]], fill=cor + (95,), outline=cor + (255,), width=3)
    for g in r["regioes"]:
        if g["tipo"] == "alimento" and g["identificado"]:
            d.text((g["regiao"]["x"] * w + 6, g["regiao"]["y"] * h + 6), f'{g["alimento"]} {g["confianca_pct"]}%', fill=(255, 255, 255, 255))
    Image.alpha_composite(im, camada).convert("RGB").save(destino, quality=88)


def avaliar(pasta: Path) -> dict:
    gabarito = json.loads((pasta / "gabarito.json").read_text(encoding="utf-8"))
    saida = pasta / "resultado"
    saida.mkdir(exist_ok=True)
    linhas, tp, fp, total = [], 0, 0, 0
    for nome, esperado in gabarito.items():
        dados = (pasta / nome).read_bytes()
        r = segmentacao.reconhecer(dados)
        achou = {i["alimento"] for i in r["itens"]}
        esperado = set(esperado)
        acertos, faltas, falsos = achou & esperado, esperado - achou, achou - esperado
        tp, fp, total = tp + len(acertos), fp + len(falsos), total + len(esperado)
        desenhar(dados, r, saida / f"{Path(nome).stem}_segmentado.jpg")
        linhas.append({"foto": nome, "ms": r["tempo_ms"], "acertos": sorted(acertos), "faltaram": sorted(faltas),
                       "falsos_positivos": sorted(falsos), "nao_identificados": r["nao_identificados"],
                       "confiancas": {i["alimento"]: i["confianca_pct"] for i in r["itens"]}})
    return {"fotos": len(linhas), "categorias_esperadas": total, "acertos": tp, "falsos_positivos": fp,
            "cobertura_pct": round(tp / total * 100, 1) if total else None,
            "precisao_pct": round(tp / (tp + fp) * 100, 1) if tp + fp else None, "por_foto": linhas}


if __name__ == "__main__":
    pasta = Path(sys.argv[1] if len(sys.argv) > 1 else "tests/fotos_reais")
    res = avaliar(pasta)
    print(f"Modelo: {segmentacao.YOLOE_MODELO} | limiar 'identificado': {segmentacao.CONF_IDENTIFICADO:.0%}")
    print(f"{'Foto':<16}{'ms':>6}  Acertos | Faltaram | Falsos positivos | Não identificados")
    for l in res["por_foto"]:
        print(f"{l['foto']:<16}{l['ms']:>6}  {', '.join(l['acertos']) or '-'} | {', '.join(l['faltaram']) or '-'} | "
              f"{', '.join(l['falsos_positivos']) or '-'} | {l['nao_identificados']}")
    print(f"\nCategorias corretas: {res['acertos']} de {res['categorias_esperadas']} ({res['cobertura_pct']}%) · "
          f"falsos positivos: {res['falsos_positivos']} · precisão: {res['precisao_pct']}%")
    print(f"Imagens com contornos: {pasta / 'resultado'}")
    (pasta / "resultado" / "avaliacao.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
