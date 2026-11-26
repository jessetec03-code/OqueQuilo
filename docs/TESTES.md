# Lista de testes

## Última execução: 26/11/2026, fim da manhã (adequação ao almoço por quilo)

Rodados de novo depois da adequação ao almoço por quilo, num banco novo. O que mudou no código: a ilustração do topo das páginas do cliente e do login (agora um prato de self-service sobre a balança; só CSS e uma imagem SVG), dois textos dos dados demonstrativos e o texto de instrução do motor de visão opcional. Nenhuma regra de negócio, tela ou função foi alterada ou removida. As páginas do cliente e da equipe continuam sem rolagem lateral no celular (largura 390 px).

- `python -m pytest -q`: **18 testes aprovados**.
- `node tests/e2e/fluxo_completo.js`: **53 de 53 verificações aprovadas** (mesma cobertura da rodada anterior, descrita abaixo).
- Reconhecimento real usado no vídeo e nas capturas, com uma foto de teste da equipe (prato de self-service com arroz, feijão, salada e frango): Salada 94%, Arroz 59%, Feijão 55% e 1 região não identificada (abaixo de 35%). O frango desse prato não entrou na lista. Resultado sem edição.
- Instalação do zero a partir do `.zip` em pasta limpa, com um ambiente Python novo e só o `requirements.txt` (sem a IA local): o sistema abriu, criou as contas iniciais e respondeu como esperado. Página do cliente (200), login do administrador (200), senha errada recusada (401), painel sem login recusado (401), avaliação e chamado pelo QR Code gravados (201), CSV de Relatórios liberado para o administrador (200) e recusado para o garçom (403), garçom sem permissão para criar usuários (403).

## Execução anterior: 26/11/2026, manhã (depois do ajuste visual)

Rodados num banco novo depois da troca da ilustração do topo das páginas do cliente e do login (só CSS e uma imagem SVG; nenhuma regra mudou). Também foi conferido que essas páginas não ganharam rolagem lateral no celular (largura 390 px).

- `python -m pytest -q`: **18 testes aprovados** (API, integração, login e permissões por perfil, opção "Outro", modo demonstração, remoção do pedido de conta e reconhecimento real com fotos). Num ambiente sem a IA local: 17 aprovados e 1 ignorado (o de reconhecimento real).
- `node tests/e2e/fluxo_completo.js`: **53 de 53 verificações aprovadas** no navegador Chromium (painel no computador e páginas no celular emulado): login e perfis, reconhecimento real com contornos, página do cliente com "Outro", painel, integração na Visão Geral, CSV só em Relatórios, modo demonstração, Equipe e acessos, garçom no celular, caixa, gerente, proprietário e saída.
- Instalação do zero a partir do `.zip`, num ambiente Python limpo: o sistema abriu, criou as contas iniciais, recebeu uma avaliação real separada das demonstrativas e respeitou as permissões do garçom.
- A equipe rodou a plataforma num computador Windows com o reconhecimento local funcionando.

## Primeira rodada (25/11/2026, noite)

Executados com:
- `python -m pytest -q`: 12 testes (11 de API e integração + 1 de reconhecimento real com 6 fotos).
- `node tests/e2e/fluxo_completo.js`: 20 checagens no navegador Chromium (painel em 1440 px e cliente em celular emulado).
- Teste de câmera no celular emulado (Pixel 7) com câmera falsa alimentada por uma foto real de prato.

Ambiente: Linux, Python 3.13, CPU Intel Xeon 2,1 GHz (4 núcleos), sem placa de vídeo.

Legenda: ✅ Aprovado · ⚠️ Com ressalvas · ❌ Não implementado

## Os 8 testes obrigatórios

| # | Teste | Estado | Como foi verificado |
|---|---|---|---|
| 1 | Fotografias reais de pratos | ✅ | 6 fotos reais de celular (pratos com arroz, feijão, carnes, frango, linguiça, salada, farofa, massa). Rodadas pelo modelo real, sem simulação |
| 2 | Categorias identificadas corretamente | ⚠️ | **14 de 23** categorias presentes foram encontradas (61%); **nenhuma categoria inventada**. Faltaram principalmente frango, feijão e carne em pratos misturados. Detalhes em [RECONHECIMENTO.md](RECONHECIMENTO.md#resultados-com-fotos-reais) |
| 3 | Segmentação | ✅ | Contornos desenhados sobre cada alimento, conferidos visualmente. ⚠️ Em 1 foto um contorno "Arroz" ficou sobre a farofa |
| 4 | Captura pela câmera do celular | ✅ | Celular emulado: botão "Abrir câmera" (getUserMedia), vídeo 720×960, captura, reconhecimento e câmera desligada ao fechar. Pelo IP da rede (HTTP): botão "Tirar foto" com `capture="environment"`. ⚠️ Falta a equipe repetir num celular físico |
| 5 | Upload | ✅ | Upload por arquivo e arrastar; arquivo que não é imagem é recusado no navegador e no servidor |
| 6 | Integração com a interface | ✅ | Foto → processando → contornos → confiança → conferência → peso total → registro salvo com método "IA local" → indicadores atualizados |
| 7 | Experiência do cliente continua funcionando | ✅ | Avaliação, pedido de atendimento e reclamação pelo celular; fila em tempo real; resolver pedido; alertas na Visão Geral |
| 8 | Smart Table não aparece mais | ✅ | Menu, telas, dashboard, relatórios, exportações e textos verificados por teste automático (busca por "smart table" e por indicadores de ocupação) e pelo navegador. Rotas `/api/mesas/resumo` e de status respondem 404 |

## Reconhecimento de Alimentos (detalhe)

| Teste | Estado | Como foi verificado |
|---|---|---|
| Modelo carrega e reconhece no computador, sem API paga | ✅ | YOLOE `yoloe-v8l-seg`, 0,4 a 0,9 s por foto em CPU; carga inicial cerca de 5 s |
| Confiança exibida por alimento | ✅ | Barra e percentual; selo Alta/Média |
| Confiança baixa vira "Não identificado" | ✅ | Regiões abaixo de 35% aparecem cinzas e sem nome |
| Prato, talheres e copos separados da comida | ✅ | Listados como "objetos ignorados" |
| Permissão da câmera negada | ✅ | Mensagem explicando como liberar ou usar "Enviar foto" |
| Aparelho sem câmera | ✅ | Mensagem específica |
| Falha no envio da foto | ✅ | Mensagem de erro e volta para a captura |
| Imagem inválida | ✅ | Mensagem no navegador; servidor responde 400 |
| Erro do modelo | ✅ | Aviso na tela e marcação manual aberta (teste automático e no navegador) |
| Sem o YOLOE instalado | ✅ | Sistema funciona em modo manual e avisa como instalar |
| Claude como alternativa | ⚠️ | Testado com resposta simulada (sem gastar a API). Não testado com chave real |
| Peso total informado ou simulado | ✅ | Origem gravada (`informado`/`simulado`); nunca peso por alimento |
| Prato devolvido (sobra) | ✅ | Sobra maior que o peso total é recusada |
| Balança física | ❌ | Fora do escopo; opção aparece desativada |

## Experiência do Cliente

| Teste | Estado | Como foi verificado |
|---|---|---|
| O QR Code direciona para a página correta? | ✅ | SVG gerado com `/cliente/?mesa=N`; página abre com o número da mesa |
| Leitura do QR Code por um celular real | ⚠️ | Depende de o celular estar no mesmo Wi-Fi do notebook. Teste no local antes da apresentação |
| Avaliação por emojis e estrelas | ✅ | Nota inválida (9) é recusada |
| Pedido de atendimento | ✅ | Pedido duplicado da mesma mesa não cria outro |
| Sugestões e reclamações | ✅ | Com categoria |
| Painel de satisfação, reclamações e pedidos | ✅ | Indicadores, gráficos, fila em tempo real e alertas na Visão Geral |

## Integração

| Teste | Estado | Como foi verificado |
|---|---|---|
| Os dois pilares usam a estrutura central? | ✅ | Mesmo banco e mesma linha do tempo `atividades` |
| Dashboard coerente? | ✅ | Contagens conferidas antes e depois do fluxo completo |
| Links e botões sem funcionamento | ✅ | Todas as telas abertas sem erro de JavaScript |
| Dados demonstrativos separados dos reais | ✅ | "Remover dados demonstrativos" preserva os registros reais |
| Executar em outro computador seguindo as instruções | ⚠️ | Testado em Linux com Python 3.13, num ambiente limpo e **sem Git** (o pacote CLIP vem em `pacotes/`). A lista de pacotes para Windows (Python 3.13, 64 bits) foi resolvida sem erro e sem Git. A equipe rodou a plataforma num Windows em 26/11 |

## Como repetir os testes

```bash
python -m pytest -q                                   # API, integração e reconhecimento real (se o YOLOE e as fotos existirem)
python -m scripts.avaliar_reconhecimento tests/fotos_reais   # tabela de acertos e imagens com contornos
python run.py   # e, em outro terminal:
npm install playwright && node tests/e2e/fluxo_completo.js
```

As fotos de teste ficam em `tests/fotos_reais/` e não vão para o GitHub. Só o `gabarito.json` é publicado.
