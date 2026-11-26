"""Reconhecimento de alimentos por visão computacional.

Motor utilizado: modelo multimodal Claude (Anthropic), acessado pela API oficial.
- Só é ativado quando existe ANTHROPIC_API_KEY no arquivo .env.
- Sem chave, o sistema funciona em modo manual: o operador marca os alimentos,
  e a interface identifica claramente que a marcação foi manual.

O que a IA faz: diz QUAIS alimentos aparecem na foto e onde aproximadamente.
O que a IA NÃO faz: medir peso. O peso vem da balança ou é informado.
"""
import base64
import json

from .settings import ANTHROPIC_API_KEY, CLAUDE_MODEL

CATALOGO = [  # sugestões para a marcação manual e nomes pedidos ao Claude (além das categorias gerais)
    "Arroz", "Feijão", "Farofa", "Salada verde", "Tomate", "Batata frita", "Mandioca",
    "Picanha", "Fraldinha", "Alcatra", "Frango", "Linguiça", "Costela", "Carne de porco",
    "Peixe", "Macarrão", "Vinagrete", "Legumes", "Pão de alho", "Queijo coalho", "Polenta",
    "Purê", "Maionese", "Sobremesa",
]

ESQUEMA = {
    "type": "object",
    "properties": {
        "prato_identificado": {"type": "boolean"},
        "descricao": {"type": "string"},
        "itens": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "alimento": {"type": "string"},
                    "confianca": {"type": "string", "enum": ["alta", "media", "baixa"]},
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "largura": {"type": "number"},
                    "altura": {"type": "number"},
                },
                "required": ["alimento", "confianca", "x", "y", "largura", "altura"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["prato_identificado", "descricao", "itens"],
    "additionalProperties": False,
}

INSTRUCAO = (
    "Você é o módulo de visão computacional de um restaurante self-service de almoço por quilo no Brasil. "
    "Liste os alimentos visíveis nesta foto de prato. Use, sempre que possível, exatamente um destes nomes: "
    + ", ".join(CATALOGO)
    + ". Se um alimento não estiver na lista, use um nome curto em português. "
    "Para cada alimento, informe a confiança (alta, media ou baixa) e a região aproximada onde ele aparece, "
    "com x, y, largura e altura como frações de 0 a 1 da imagem (x e y são o canto superior esquerdo). "
    "Não estime pesos nem quantidades. Se a imagem não mostrar um prato de comida, "
    "retorne prato_identificado=false e itens vazio. A descrição deve ter no máximo uma frase."
)


def biblioteca_instalada() -> bool:
    """O pacote 'anthropic' é opcional (requirements-ia.txt). Sem ele, o sistema roda em modo manual."""
    try:
        import anthropic  # noqa: F401
    except Exception:  # não instalado ou instalação incompleta
        return False
    return True


def ia_disponivel() -> bool:
    return bool(ANTHROPIC_API_KEY) and biblioteca_instalada()


def status() -> dict:
    if ia_disponivel():
        return {"ia_disponivel": True, "modo": "ia", "motor": "IA em nuvem (opcional)", "modelo": CLAUDE_MODEL,
                "mensagem": "Reconhecimento por IA ativo. O operador confirma os itens antes de salvar."}
    if ANTHROPIC_API_KEY:
        motivo = ("A chave está no .env, mas o pacote da IA não está instalado "
                  "(rode: pip install -r requirements-ia.txt e reinicie).")
    else:
        motivo = "IA não configurada (sem ANTHROPIC_API_KEY no .env)."
    return {"ia_disponivel": False, "modo": "manual", "motor": None,
            "mensagem": motivo + " Os alimentos são marcados manualmente pelo operador."}


class ErroVisao(Exception):
    pass


def reconhecer(imagem: bytes, media_type: str) -> dict:
    """Envia a imagem ao modelo e devolve {prato_identificado, descricao, itens}."""
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=60, max_retries=1)
    try:
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2000,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": ESQUEMA}},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                                 "data": base64.standard_b64encode(imagem).decode()}},
                    {"type": "text", "text": INSTRUCAO},
                ],
            }],
        )
    except anthropic.AuthenticationError as e:
        raise ErroVisao("Chave da API inválida. Confira ANTHROPIC_API_KEY no arquivo .env.") from e
    except anthropic.RateLimitError as e:
        raise ErroVisao("Limite de uso da API atingido. Tente novamente em instantes.") from e
    except anthropic.APIStatusError as e:
        raise ErroVisao(f"A API de visão respondeu com erro {e.status_code}.") from e
    except anthropic.APIConnectionError as e:
        raise ErroVisao("Sem conexão com a API de visão. Verifique a internet.") from e

    if resp.stop_reason == "refusal":
        raise ErroVisao("A IA não analisou esta imagem. Faça a marcação manual.")
    texto = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as e:
        raise ErroVisao("Resposta da IA em formato inesperado. Faça a marcação manual.") from e

    itens = []
    for it in dados.get("itens", []):
        clamp = lambda v: max(0.0, min(1.0, float(v)))
        itens.append({
            "alimento": str(it["alimento"]).strip()[:60],
            "confianca": it.get("confianca", "media"),
            "regiao": {"x": clamp(it["x"]), "y": clamp(it["y"]),
                       "largura": clamp(it["largura"]), "altura": clamp(it["altura"])},
        })
    return {"prato_identificado": bool(dados.get("prato_identificado")),
            "descricao": dados.get("descricao", ""), "itens": itens, "motor": "IA em nuvem (opcional)", "modelo": CLAUDE_MODEL}
