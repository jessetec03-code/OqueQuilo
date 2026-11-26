# Guia da equipe: rodar, testar e colaborar

Este guia é para quem nunca configurou um projeto Python. Siga na ordem.

## 1. Instalar o que precisa (uma vez por computador)

1. **Python 3.10 ou mais recente:** baixe em https://www.python.org/downloads/.
   No Windows, na primeira tela do instalador, marque **"Add Python to PATH"**. Prefira este instalador ao Python da Microsoft Store (veja a seção 8).
2. **Git (só para enviar alterações pelo GitHub):** baixe em https://git-scm.com/downloads e instale com as opções padrão. Para instalar e rodar o projeto **não precisa de Git**.
3. **Conferir:** abra o terminal (Windows: tecla Windows, digite **cmd**, Enter. Mac: abra o app **Terminal**) e rode:
   ```
   python --version
   ```
   Deve aparecer algo como `Python 3.12.x`. No Mac, se `python` não funcionar, use `python3` em todos os comandos.

## 2. Baixar e instalar o projeto

Use sempre uma pasta curta e **fora do OneDrive**. No Windows: `C:\code-meat`.

Pegue o projeto de um destes jeitos:
- **Zip:** no GitHub, clique em **Code** e em **Download ZIP** (ou use o `code-meat.zip` da equipe) e extraia direto em `C:\`. Renomeie a pasta extraída para `code-meat`, para ficar `C:\code-meat`. Se já extraiu na Área de Trabalho ou no OneDrive, recorte a pasta `code-meat` e cole em `C:\`.
- **Git:** `cd C:\` e depois `git clone https://github.com/jessetec03-code/OqueQuilo.git code-meat`.

### Windows: com dois cliques
1. Abra a pasta `C:\code-meat` e clique duas vezes em **`instalar_windows.bat`**. Se o Windows mostrar "O Windows protegeu o computador", clique em **Mais informações** e em **Executar assim mesmo**.
2. Espere terminar (de 5 a 20 minutos; baixa de 1 a 3 GB). No fim aparece "Pronto".
3. Para abrir o sistema, clique duas vezes em **`iniciar_windows.bat`**.

O instalador cria a pasta `.venv` (um Python só do projeto) e instala tudo dentro dela. Isso evita o erro de caminho longo do Windows.

### Windows: pelo terminal (o mesmo que o .bat faz)
Abra o **PowerShell** e rode, uma linha por vez:
```
cd C:\code-meat
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pip install -r requirements-visao.txt
.venv\Scripts\python run.py
```
Nas próximas vezes, só a primeira e a última linha.

### Linux ou Mac
```
cd code-meat
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -r requirements-visao.txt
```
Nas próximas vezes, rode `source .venv/bin/activate` antes de `python run.py`.

O `requirements.txt` demora um ou dois minutos. O `requirements-visao.txt` instala o reconhecimento de alimentos local (PyTorch, Ultralytics e o pacote CLIP que já vem na pasta `pacotes/`): baixa de 1 a 3 GB e pode levar de 5 a 20 minutos. Os dois terminam com `Successfully installed ...`. Rode os dois **dentro da pasta do projeto**, porque o `requirements-visao.txt` aponta para `pacotes/`.

Sem o `requirements-visao.txt` o sistema funciona, mas os alimentos são marcados à mão.

## 3. Rodar

```
python run.py
```
(No Windows com `.venv`: `iniciar_windows.bat` ou `.venv\Scripts\python run.py`.) Deve aparecer:
```
  CODE MEAT | INTELLIGENCE PLATFORM
  Painel (neste computador):  http://localhost:8000
  Celular na mesma rede Wi-Fi: http://192.168.x.x:8000/cliente/?mesa=1
```
Abra **http://localhost:8000** no navegador. Para parar o servidor: clique no terminal e aperte **Ctrl + C**.

**Login:** o painel pede usuário e senha. Na primeira execução o terminal mostra as contas criadas (admin, gerente, garcom, caixa, proprietario) e elas ficam salvas em `data/acessos_iniciais.txt` (esse arquivo não vai para o GitHub). Esqueceu as senhas? `python run.py --redefinir-acessos`. Depois de 5 senhas erradas o login fica bloqueado por 2 minutos.

Para voltar aos dados iniciais da demonstração: `python run.py --reset`.

Na **primeira** vez com o reconhecimento instalado, o servidor baixa o modelo (cerca de 700 MB) em segundo plano. Espere 1 ou 2 minutos antes da primeira foto. Em **Configurações** aparece "IA local (padrão, gratuita) · instalada" e, na tela Reconhecimento de Alimentos, "Reconhecimento automático ativo".

## 4. Se der erro

| Mensagem | Causa | Solução |
|---|---|---|
| `'python' não é reconhecido` | Python fora do PATH | Reinstale o Python marcando "Add Python to PATH", ou use `py` no lugar de `python` |
| Avisos amarelos `... is not on PATH` no `pip install` | Normal no Windows | Pode ignorar; o projeto roda com `python run.py` |
| `No module named fastapi` | Dependências não instaladas, ou o servidor foi aberto sem o `.venv` | Use `iniciar_windows.bat` (ou `.venv\Scripts\python run.py`), ou rode `python -m pip install -r requirements.txt` dentro da pasta `code-meat` |
| `address already in use` / porta 8000 ocupada | O servidor já está aberto em outro terminal | Feche o outro terminal, ou crie um `.env` com `PORTA=8001` |
| Página "Não foi possível carregar esta tela" | Servidor parado | Rode `python run.py` de novo |
| Celular não abre o QR Code | Celular em outra rede, ou Wi-Fi bloqueia acesso entre aparelhos | Use o mesmo Wi-Fi; no evento, use o roteador do celular (hotspot) para o notebook e o celular, ou abra `/cliente/?mesa=1` no próprio notebook |
| Windows pergunta sobre o Firewall | O servidor aceita conexões da rede | Clique em **Permitir** (necessário para o celular acessar) |
| `OSError` com "Long Path" no `pip install -r requirements-visao.txt` | Caminho muito longo (comum com o Python da Microsoft Store) | Instale com o `.venv` (seção 2). Detalhes na seção 8 |
| `Cannot find command 'git'` no `pip install -r requirements-visao.txt` | Versão antiga do projeto, que baixava o CLIP pelo Git | Baixe a versão nova (o CLIP vem em `pacotes/`), ou instale o Git |
| `No such file or directory` citando `pacotes/clip-1.0-py3-none-any.whl` | O comando foi rodado fora da pasta do projeto | Entre na pasta (`cd C:\code-meat`) e rode de novo |
| Tela diz "Reconhecimento local não instalado" | Faltou `requirements-visao.txt`, ou o servidor foi aberto com outro Python | Rode `python -m pip install -r requirements-visao.txt` com o mesmo Python que roda o `run.py` (no Windows, o do `.venv`) e reinicie |
| Tela diz "Não foi possível carregar o modelo" | Sem internet no 1º uso (download dos pesos) | Conecte à internet e reinicie o servidor. Depois do 1º download funciona sem internet |
| No celular não aparece "Abrir câmera", só "Tirar foto" | O endereço é `http://` (o navegador só libera a câmera ao vivo em HTTPS) | Normal: "Tirar foto" usa a câmera do celular. Para câmera ao vivo, veja "Testar no celular" em `docs/RECONHECIMENTO.md` |

## 5. Testes

```
python -m pytest -q
```
Resultado esperado: `12 passed` com o reconhecimento instalado e as fotos de teste na pasta `tests/fotos_reais`, ou `11 passed, 1 skipped` sem eles. Os testes usam um banco temporário e não mexem nos seus dados.

Para ver quantos alimentos o modelo acerta nas fotos reais: `python -m scripts.avaliar_reconhecimento tests/fotos_reais` (as imagens com os contornos ficam em `tests/fotos_reais/resultado`).

O teste no navegador (opcional, precisa de Node e Playwright) fica em `tests/e2e/fluxo_completo.js`.

## 6. Quem mexe em quê

Para ninguém sobrescrever o trabalho do outro, cada integrante tem os **seus arquivos**. Arquivos centrais só são alterados pelo Integrante 1.

| Integrante | Pode alterar | Não altera sem combinar |
|---|---|---|
| **1 · Técnico e integração** | `backend/main.py`, `backend/db.py`, `backend/seed.py`, `backend/motores.py`, `backend/segmentacao.py`, `backend/vision.py`, `backend/routers/food.py`, `backend/routers/dashboard.py`, `frontend/js/app.js`, `frontend/js/ui.js`, `frontend/css/app.css`, `frontend/js/modules/food.js`, `overview.js`, `reports.js`, `settings.js`, `README.md`, `docs/` | – |
| **2 · Reconhecimento de Alimentos (testes e demonstração)** | `tests/fotos_reais/` (fotos e `gabarito.json`), `scripts/avaliar_reconhecimento.py`, `docs/RECONHECIMENTO.md` (seção de resultados) | `backend/segmentacao.py` (lista `PROMPTS` e limiares: combinar com o Integrante 1) |
| **3 · Experiência do Cliente** | `backend/routers/feedback.py`, `frontend/js/modules/customer.js`, `frontend/cliente/` (todos os arquivos) | `db.py` (tabelas `avaliacoes`, `manifestacoes`, `solicitacoes_atendimento`) |

**Regras de integração**
- Não mude o nome de uma rota da API nem o formato do que ela devolve: outros módulos dependem disso (veja `docs/ARQUITETURA.md`). Se precisar de um dado novo, **acrescente** um campo, não renomeie.
- Toda ação nova que o gestor deve ver chama `registrar_atividade(...)` (em `backend/db.py`).
- Toda informação simulada deve aparecer marcada na tela.
- Antes de enviar, rode `python -m pytest -q` e abra a sua tela no navegador.

### Integrante 2 · Reconhecimento de Alimentos
- **Objetivo:** provar com fotos reais que o reconhecimento funciona e preparar a demonstração.
- **Passo a passo:**
  1. Tire de 10 a 20 fotos de pratos **de cima**, com boa luz e o prato inteiro (arroz, feijão, carnes, frango, linguiça, batata frita, salada, farofa). Não fotografe pessoas.
  2. Copie as fotos para `tests/fotos_reais/` e escreva no `gabarito.json` o que realmente tem em cada uma, usando só estas categorias: Carne, Arroz, Feijão, Batata frita, Salada, Frango, Linguiça, Acompanhamentos.
  3. Rode `python -m scripts.avaliar_reconhecimento tests/fotos_reais` e copie a tabela para `docs/RECONHECIMENTO.md`.
  4. No celular, abra a tela Reconhecimento de Alimentos e teste **Tirar foto** com um prato de verdade.
- **Como testar a API:** `POST /api/alimentar/analisar` (formulário com `imagem`) pela página `http://localhost:8000/docs`.
- **Ideias de melhoria:** escolher as melhores fotos para o vídeo; anotar quais alimentos o modelo mais erra.

### Integrante 3 · Experiência do Cliente
- **Recebe:** `GET /api/cliente/opcoes`, `GET /api/cliente/resumo`, listas de avaliações, manifestações e solicitações.
- **Envia:** `POST /api/avaliacoes`, `POST /api/manifestacoes`, `POST /api/solicitacoes`.
- **Como testar:** abra `http://localhost:8000/cliente/?mesa=5` (ou leia o QR Code com o celular), envie uma avaliação e um pedido de atendimento. Eles aparecem na tela Experiência do Cliente e nos alertas da Visão Geral.
- **Ideias de melhoria:** textos da página, ordem das perguntas, mensagem de agradecimento.

## 7. Enviar alterações pelo GitHub

Primeira vez em cada computador (troque pelos seus dados):
```
git config --global user.name "Seu Nome"
git config --global user.email "seu-email@exemplo.com"
```

Fluxo simples, com uma branch por integrante:
```
git pull                                   # 1. pega a versão mais nova
git checkout -b cliente                    # 2. cria a sua branch (só na primeira vez; depois: git checkout cliente)
# ... edite os seus arquivos e teste ...
git add .
git commit -m "Cliente: novo texto de agradecimento"
git push -u origin cliente                 # 3. envia
```
Depois, no site do GitHub, clique em **Compare & pull request** e em **Create pull request**. O Integrante 1 revisa e clica em **Merge**.

Para atualizar a sua branch com o que já entrou na principal:
```
git checkout main
git pull
git checkout cliente
git merge main
```

**Nunca** envie o arquivo `.env` (ele já está no `.gitignore`) nem fotos de clientes reais.

## 8. Problemas na instalação do reconhecimento (Windows)

O PyTorch tem arquivos com caminhos longos, e o Windows limita caminhos a 260 caracteres. O Python da **Microsoft Store** instala os pacotes em `C:\Users\<nome>\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_...\LocalCache\local-packages\...`, que já passa de 140 caracteres; somado aos arquivos do PyTorch, passa do limite. Isso acontece **mesmo com o projeto fora do OneDrive**, porque esse caminho não depende da pasta do projeto.

Se `pip install -r requirements-visao.txt` der **`OSError`** citando "Windows Long Path" ou "No such file or directory" dentro de `torch`:
1. Use o `.venv` dentro de `C:\code-meat` (seção 2, com o `.bat` ou pelo terminal). Com ele os pacotes ficam em `C:\code-meat\.venv\Lib\site-packages`, um caminho curto. É a solução recomendada.
2. Se ainda falhar, instale o Python pelo site python.org (marcando "Add Python to PATH"), apague a pasta `.venv` e rode o `instalar_windows.bat` de novo.
3. Ou ative caminhos longos: abra o PowerShell **como administrador** e rode
   `New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force`
   e reinicie o computador.

Enquanto isso, o sistema continua funcionando com marcação manual.

## 9. Ativar a IA em nuvem (opcional, paga)

Só é útil se o reconhecimento local não puder ser instalado. Cada foto analisada custa centavos.
1. `python -m pip install -r requirements-ia.txt` (no Windows com `.venv`: `.venv\Scripts\python -m pip install -r requirements-ia.txt`)
2. Crie uma chave em https://console.anthropic.com (precisa de créditos na conta).
3. Na pasta do projeto, copie `.env.example` para um arquivo chamado `.env` e preencha `ANTHROPIC_API_KEY=`.
4. Reinicie o servidor (Ctrl + C e abra de novo).
5. Se o YOLOE também estiver instalado, o padrão continua sendo o local. Para forçar o Claude, coloque `MOTOR_VISAO=claude` no `.env`.
