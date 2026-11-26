# Pacotes incluídos no projeto

`clip-1.0-py3-none-any.whl` é o pacote **CLIP da Ultralytics** (github.com/ultralytics/CLIP,
commit 7ffa84b3bfa40c42ecc1c77147a855e69cb2dd40), empacotado sem nenhuma alteração.

O YOLOE usa esse pacote só para transformar os nomes dos alimentos em texto que o modelo entende.
Ele fica aqui para que `pip install -r requirements-visao.txt` funcione **sem o Git instalado**
(o pacote não existe no PyPI; o original só pode ser instalado a partir do GitHub).

Licença: AGPL-3.0 (arquivo de licença dentro do .whl, em `clip-1.0.dist-info/licenses/LICENSE`).
Baseado no CLIP da OpenAI (licença MIT).

Como foi gerado:
    pip wheel --no-deps "git+https://github.com/ultralytics/CLIP.git@7ffa84b3bfa40c42ecc1c77147a855e69cb2dd40"
