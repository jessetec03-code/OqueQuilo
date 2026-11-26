# Pitch (apresentação ao vivo, cerca de 2 minutos)

Use com os 5 slides em [`docs/apresentacao/`](apresentacao/). Fale o que está entre aspas; o resto é indicação de cena.

**Slide 1 · O desafio**
"No almoço por quilo da Bovinu'S, o buffet movimenta muitos pratos e clientes ao mesmo tempo. Quais alimentos do buffet saem mais, o que volta como sobra, quem saiu insatisfeito sem avisar: hoje isso fica na memória da equipe. A oportunidade é transformar esses sinais em dados para a gestão."

**Slide 2 · A solução**
"O Code Meat é uma plataforma com dois pilares integrados: Inteligência Alimentar e Experiência do Cliente. Os dois gravam no mesmo banco e aparecem no mesmo painel, e cada colaborador entra com o próprio usuário e vê só as funções do seu perfil."

**Slide 3 · Inteligência Alimentar** (se possível, ao vivo: fotografar um prato)
"A proposta é integrar uma câmera à balança: quando o cliente coloca o prato para pesar, a foto é capturada sozinha, sem ação de ninguém, e a balança registra o peso total. Essa integração física ainda não está instalada; no protótipo, a foto é enviada pelo celular ou pelo computador. A IA roda no próprio computador do restaurante, sem custo por foto, identifica os alimentos e contorna cada um, com a confiança. Abaixo de 35% o sistema não chuta: marca como não identificado, e o operador confere antes de salvar. Cada registro alimenta os indicadores de consumo e de sobras."

**Slide 4 · Experiência do Cliente** (ao vivo: ler o QR Code de uma mesa)
"O cliente lê o QR Code da mesa e, sem aplicativo e sem cadastro, avalia, deixa sugestão ou reclamação e chama a equipe: garçom, buffet, limpeza ou outro pedido. O pedido chega na hora e o garçom marca o atendimento pelo celular. A gerência acompanha notas, reclamações e satisfação por período."

**Slide 5 · Integração e resultado**
"Na Visão Geral, os dois pilares se encontram no mesmo ambiente de gestão: o que foi servido, o que sobrou e o que o cliente sentiu aparecem lado a lado, por horário do almoço, com alertas do que pede atenção agora. É um MVP funcionando: 53 verificações no navegador e 18 testes automatizados aprovados, rodando num computador comum. Code Meat: do prato à mesa, informação que vira decisão."

## Perguntas prováveis

- *A câmera na balança já funciona?* Ainda não. É a proposta de funcionamento: a integração física não está instalada no protótipo. Hoje a foto é enviada pelo celular ou pelo computador, e o reconhecimento, a conferência e os indicadores já funcionam.
- *Mede o peso de cada alimento?* Não. A balança mede o prato inteiro; o sistema registra o peso total (informado ou simulado no protótipo) e quais alimentos sobraram.
- *A IA acerta tudo?* Não. Nas 6 fotos reais de teste reconheceu 14 de 23 alimentos e não inventou nenhum. Por isso o operador confere, e o próximo passo é ajustar o modelo com fotos dos pratos da casa.
- *Quanto custa rodar?* Roda num computador comum, com banco em arquivo e IA local, sem custo por foto.
- *Os números do painel são reais?* Os indicadores iniciais são demonstrativos, separados dos reais e marcados na tela. O painel tem filtro para ver só os registros reais.
- *E a privacidade?* A câmera olha o prato, não a pessoa. O cliente é anônimo: só o número da mesa é registrado. As fotos só abrem para colaboradores logados.
