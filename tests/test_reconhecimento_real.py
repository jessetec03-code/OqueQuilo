"""Teste do reconhecimento REAL (sem simulação) com fotos reais de pratos.

Só roda quando o YOLOE está instalado (requirements-visao.txt) e existe a pasta
tests/fotos_reais com as fotos e o gabarito.json. Caso contrário, é pulado e o
pytest mostra o motivo. As fotos não vão para o GitHub (podem ser pessoais).
"""
from pathlib import Path

import pytest

from backend import segmentacao

PASTA = Path(__file__).parent / "fotos_reais"

pytestmark = [
    pytest.mark.skipif(not segmentacao.pacotes_instalados(), reason="YOLOE não instalado (requirements-visao.txt)"),
    pytest.mark.skipif(not (PASTA / "gabarito.json").is_file(), reason="sem fotos em tests/fotos_reais"),
]


def test_reconhece_categorias_em_fotos_reais():
    from scripts.avaliar_reconhecimento import avaliar

    res = avaliar(PASTA)
    print(res)
    # Critérios mínimos definidos ANTES de rodar: metade das categorias encontradas e quase nenhum palpite errado.
    assert res["cobertura_pct"] >= 50
    assert res["precisao_pct"] >= 90
    for foto in res["por_foto"]:
        assert foto["acertos"], f"nenhuma categoria correta em {foto['foto']}"
