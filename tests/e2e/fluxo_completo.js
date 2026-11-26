// Teste de ponta a ponta (navegador real) dos dois pilares, do acesso da equipe e da integração.
// Uso: com o servidor rodando (python run.py), em outro terminal:
//   npm install playwright   (uma vez)   e depois   node tests/e2e/fluxo_completo.js
// Variáveis opcionais: CODEMEAT_URL (padrão http://localhost:8000) e CODEMEAT_ACESSOS
// (arquivo com usuários e senhas; padrão data/acessos_iniciais.txt, criado na 1ª execução).
const path = require('path');
const fs = require('fs');
const { chromium, devices } = require('playwright');

const URL = process.env.CODEMEAT_URL || 'http://localhost:8000';
const ok = (c, m) => { console.log((c ? 'APROVADO ' : 'FALHOU   ') + m); if (!c) process.exitCode = 1; };
const fotoReal = path.join(__dirname, '..', 'fotos_reais', 'IMG_6167.jpeg');
const foto = fs.existsSync(fotoReal) ? fotoReal : path.join(__dirname, 'prato_teste.png');
const arqAcessos = process.env.CODEMEAT_ACESSOS || path.join(__dirname, '..', '..', 'data', 'acessos_iniciais.txt');
const SENHAS = Object.fromEntries([...fs.readFileSync(arqAcessos, 'utf8').matchAll(/usuário: (\S+)\s+senha: (\S+)/g)].map((m) => [m[1], m[2]]));

async function entrar(page, login) {
  await page.goto(`${URL}/equipe/`);
  await page.fill('#login', login);
  await page.fill('#senha', SENHAS[login]);
  await page.locator('#entrar').click();
  await page.waitForSelector('#nav a');
  await page.waitForTimeout(700);
}
const menuDe = async (page) => (await page.locator('#nav').innerText()).replace(/\s+/g, ' ');

(async () => {
  const b = await chromium.launch();
  const errs = [];
  const nova = async (opts) => { const ctx = await b.newContext(opts); const pg = await ctx.newPage(); pg.on('pageerror', (e) => errs.push(e.message)); return pg; };

  // ---------- Acesso da equipe: sem login não entra ----------
  const anon = await nova({ viewport: { width: 1280, height: 860 } });
  await anon.goto(`${URL}/`);
  ok(anon.url().endsWith('/equipe/'), 'Acesso: painel sem login redireciona para a página de login da equipe');
  ok((await anon.request.get(`${URL}/api/dashboard`)).status() === 401, 'Acesso: API do painel recusa quem não fez login (401)');
  await anon.fill('#login', 'admin'); await anon.fill('#senha', 'senha-errada'); await anon.locator('#entrar').click();
  await anon.waitForSelector('.erro');
  ok((await anon.locator('.erro').innerText()).includes('incorretos'), 'Acesso: senha errada mostra erro e não entra');

  // ---------- Administrador ----------
  const p = await nova({ viewport: { width: 1440, height: 900 } });
  await entrar(p, 'admin');
  const dash0 = await (await p.request.get(`${URL}/api/dashboard`)).json();
  const status = await (await p.request.get(`${URL}/api/alimentar/status`)).json();
  let menu = await menuDe(p);
  ok(['Visão Geral', 'Reconhecimento de Alimentos', 'Experiência do Cliente', 'Relatórios', 'Equipe e acessos', 'Configurações'].every((t) => menu.includes(t)), 'Administrador: menu completo');
  ok(!/smart|mesas/i.test(menu), 'Menu: Smart Tables não aparece');
  ok((await p.locator('#userBox').innerText()).includes('Administrador'), 'Administrador: nome e perfil no topo do painel');

  // Pilar 1: foto -> reconhecimento -> conferência -> peso total -> salvar -> retorno
  await p.goto(`${URL}/#/reconhecimento`); await p.waitForTimeout(800);
  await p.setInputFiles('#al-file', foto);
  await p.waitForSelector('#al-photo img'); ok(true, `Reconhecimento: foto enviada e exibida (${path.basename(foto)})`);
  await p.waitForSelector('#al-photo .seg-processing', { state: 'detached', timeout: 60000 });
  if (status.motor_ativo === 'local') {
    const itens = await p.$$eval('#al-form .chip.on', (e) => e.map((x) => x.textContent.replace('✕', '').trim()));
    const poligonos = await p.locator('svg.masks polygon').count();
    ok(itens.length > 0, `Reconhecimento: alimentos identificados pela IA local: ${itens.join(', ')}`);
    ok(poligonos > 0, `Reconhecimento: ${poligonos} contornos (segmentação) desenhados sobre a foto`);
    ok(await p.locator('.res-item .res-bar').count() > 0, 'Reconhecimento: confiança exibida por alimento');
    const html1 = (await p.content()).toLowerCase();
    ok(!html1.includes('yoloe'), 'Originalidade: a tela de reconhecimento não exibe nome de projeto externo');
  } else {
    ok(await p.getByText('Foto salva · marcação manual').isVisible(), 'Reconhecimento: modo manual identificado (IA local não instalada)');
  }
  if (!(await p.$eval('#al-form details', (d) => d.open))) await p.locator('#al-form summary').click();
  await p.locator('[data-add="Carne"]').click();
  await p.locator('[data-a="simular"]').click(); await p.fill('#al-mesa', '7');
  await p.locator('[data-a="salvar"]').click(); await p.waitForTimeout(1000);
  ok(await p.getByText(/Prato #\d+ registrado/).isVisible(), 'Reconhecimento: registro salvo com peso total simulado');
  await p.locator('#al-pend [data-retorno]').first().click(); await p.waitForTimeout(300);
  await p.locator('.modal [data-item]').first().click(); await p.fill('#rt-peso', '60'); await p.locator('#rt-ok').click(); await p.waitForTimeout(800);
  ok(await p.getByText('Retorno registrado').isVisible(), 'Reconhecimento: retorno (sobra) registrado');
  const fotoUrl = await p.locator('#al-hist img').first().getAttribute('src').catch(() => null);
  if (fotoUrl) ok((await anon.request.get(`${URL}${fotoUrl}`)).status() === 401, 'Segurança: foto do prato não abre sem login');

  // ---------- Pilar 2: cliente no celular, pelo link do QR Code ----------
  const m = await nova({ ...devices['iPhone 13'] });
  await m.goto(`${URL}/cliente/?mesa=9`); await m.waitForTimeout(600);
  await m.getByText('Avaliar experiência').click(); await m.locator('[data-geral="2"]').click();
  await m.locator('[data-stars="atendimento"] [data-v="2"]').click();
  await m.fill('#com', 'Demorou para liberarem a mesa.'); await m.locator('#env').click(); await m.waitForTimeout(500);
  ok(await m.getByRole('heading', { name: 'Avaliação enviada' }).isVisible(), 'Cliente: avaliação enviada pelo celular');
  await m.getByText('Voltar ao início').click(); await m.getByText('Chamar atendimento').click();
  const motivos = await m.$$eval('[data-m]', (e) => e.map((x) => x.textContent));
  ok(!motivos.some((t) => /conta/i.test(t)) && motivos.includes('Outro'), `Cliente: sem "pedir a conta" (comanda); opções: ${motivos.join(', ')}`);
  await m.locator('[data-m="Outro"]').click();
  ok(await m.locator('#outro').isVisible() && await m.locator('#env').isDisabled(), 'Cliente: "Outro" abre campo de texto e exige preenchimento');
  await m.fill('#outro', 'Trazer uma cadeirinha de bebê');
  ok(!(await m.locator('#env').isDisabled()), 'Cliente: com o texto preenchido o envio é liberado');
  await m.locator('#env').click(); await m.waitForTimeout(500);
  ok(await m.getByRole('heading', { name: 'Pedido enviado' }).isVisible(), 'Cliente: pedido "Outro" enviado com a descrição');
  await m.getByText('Voltar ao início').click(); await m.getByText('Sugestão ou reclamação').click();
  await m.locator('[data-t="reclamacao"]').click();
  await m.fill('#txt', 'Chamamos o garçom duas vezes.');
  ok(await m.locator('#env').isDisabled() && (await m.locator('#falta').innerText()).includes('Escolha'), 'Cliente: assunto obrigatório antes de enviar');
  await m.locator('[data-c="Outro"]').click(); await m.fill('#outro', 'Estacionamento');
  await m.locator('#env').click(); await m.waitForTimeout(500);
  ok(await m.getByRole('heading', { name: 'Reclamação registrada' }).isVisible(), 'Cliente: reclamação com assunto "Outro" registrada');
  const larg = await m.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  ok(larg, 'Cliente: página cabe na largura do celular (sem rolagem lateral)');

  // ---------- Painel da Experiência do Cliente ----------
  await p.goto(`${URL}/#/experiencia-cliente`); await p.waitForTimeout(1200);
  ok(await p.locator('#cx-fila').getByText('Mesa 9 · Outro: Trazer uma cadeirinha de bebê').first().isVisible(), 'Painel: pedido "Outro" aparece na fila com a descrição');
  ok(await p.locator('a[href*=".csv"]').count() === 0, 'Painel: Experiência do Cliente sem exportação CSV');
  ok(await p.locator('#cx-c3').isVisible() && await p.locator('#cx-periodos table').isVisible(), 'Painel: satisfação por dia e indicadores por período');
  await p.locator('[data-aba="reclamacoes"]').click(); await p.waitForTimeout(500);
  ok(await p.locator('#cx-aba').getByText('Outro: Estacionamento').first().isVisible(), 'Painel: assunto "Outro" exibido na reclamação');
  await p.locator('[data-origem="real"]').click(); await p.waitForTimeout(800);
  ok((await p.locator('#cx-kpis').innerText()).includes('somente registros reais'), 'Painel: filtro separa registros reais dos demonstrativos');
  await p.locator('[data-origem="todos"]').click(); await p.waitForTimeout(600);
  await p.locator('#cx-fila [data-sol][data-acao="resolvida"]').first().click(); await p.waitForTimeout(600);
  ok(await p.getByText('Pedido resolvido').isVisible(), 'Painel: equipe resolve o pedido');

  // ---------- Integração na Visão Geral ----------
  await p.goto(`${URL}/#/visao-geral`); await p.waitForTimeout(1000);
  ok(await p.locator('#ov-ativ').getByText('Mesa 9: nova avaliação, nota 2/5').first().isVisible(), 'Integração: avaliação na atividade recente');
  ok(await p.getByText('Mesa 9: reclamação sobre estacionamento').first().isVisible(), 'Integração: reclamação do QR aparece nos alertas');
  const dash1 = await (await p.request.get(`${URL}/api/dashboard`)).json();
  ok(dash1.alimentar.registros === dash0.alimentar.registros + 1, 'Integração: indicador de pratos atualizado');
  ok(dash1.cliente.avaliacoes === dash0.cliente.avaliacoes + 1, 'Integração: contagem de avaliações atualizada');
  const html = (await p.content()).toLowerCase();
  ok(!html.includes('smart table') && !html.includes('ocupação'), 'Visão Geral: nenhum texto de Smart Tables');

  // ---------- Relatórios: CSV só aqui ----------
  await p.goto(`${URL}/#/relatorios`); await p.waitForTimeout(800);
  ok(await p.locator('a[href*=".csv"]').count() === 4, 'Relatórios: 4 exportações CSV disponíveis');
  const csv = await p.request.get(`${URL}/api/relatorios/exportar/solicitacoes.csv`);
  ok(csv.status() === 200 && (await csv.text()).includes('motivo_outro'), 'Relatórios: CSV inclui a descrição do "Outro"');

  // ---------- Modo demonstração ----------
  const realAntes = await (await p.request.get(`${URL}/api/cliente/resumo?origem=real`)).json();
  await p.goto(`${URL}/#/configuracoes`); await p.waitForTimeout(800);
  ok(await p.locator('img[src="/api/qrcode/equipe.svg"]').isVisible(), 'Configurações: QR Code da equipe');
  await p.fill('#dm-media', '4.8'); await p.fill('#dm-n', '400'); await p.fill('#dm-dias', '30');
  await p.locator('[data-a="recriar"]').click(); await p.locator('.modal #ok').click(); await p.waitForTimeout(2500);
  const demo = await (await p.request.get(`${URL}/api/cliente/resumo?origem=demo`)).json();
  const real = await (await p.request.get(`${URL}/api/cliente/resumo?origem=real`)).json();
  ok(demo.avaliacoes === 400 && Math.abs(demo.media_geral - 4.8) <= 0.01, `Modo demonstração: 400 avaliações fictícias com média ${demo.media_geral}`);
  ok(real.avaliacoes === realAntes.avaliacoes && real.media_geral === realAntes.media_geral, `Modo demonstração: avaliações reais preservadas (${real.avaliacoes}, média ${real.media_geral})`);

  // ---------- Equipe e acessos ----------
  await p.goto(`${URL}/#/equipe`); await p.waitForTimeout(800);
  await p.locator('#eq-novo').click();
  await p.fill('#nc-nome', 'Bruna Teste'); await p.fill('#nc-login', 'bruna.teste'); await p.selectOption('#nc-perfil', 'garcom'); await p.fill('#nc-senha', 'bruna123');
  await p.locator('.modal #ok').click(); await p.waitForTimeout(800);
  ok(await p.locator('#eq-lista').getByText('bruna.teste').isVisible(), 'Equipe: administrador cadastra colaborador');
  ok(await p.locator('[data-perfil-perm="admin"]:not(:disabled)').count() === 0, 'Equipe: permissões do Administrador travadas');

  // ---------- Garçom no celular: só a fila de atendimento ----------
  const g = await nova({ ...devices['iPhone 13'] });
  await entrar(g, 'garcom');
  menu = await menuDe(g);
  ok(menu.includes('Experiência do Cliente') && !/Visão Geral|Relatórios|Configurações|Equipe|Reconhecimento/.test(menu), `Garçom: menu só com o atendimento (${menu.trim()})`);
  ok(await g.locator('#cx-fila').isVisible() && await g.locator('#cx-kpis').count() === 0, 'Garçom: vê a fila de pedidos, sem indicadores gerenciais');
  await g.goto(`${URL}/#/relatorios`); await g.waitForTimeout(800);
  ok((await g.locator('#pageTitle').innerText()) === 'Experiência do Cliente', 'Garçom: endereço de Relatórios digitado volta para a tela permitida');
  ok((await g.request.get(`${URL}/api/relatorios/exportar/avaliacoes.csv`)).status() === 403, 'Garçom: servidor recusa relatório (403)');
  const sid = (await (await m.request.post(`${URL}/api/solicitacoes`, { data: { mesa: 12, motivo: 'Limpeza da mesa' } })).json()).id;
  await g.goto(`${URL}/#/experiencia-cliente`); await g.waitForTimeout(1200);
  await g.locator(`#cx-fila [data-sol="${sid}"][data-acao="em_atendimento"]`).click(); await g.waitForTimeout(600);
  ok(await g.getByText('Atendimento iniciado').isVisible(), 'Garçom: atualiza o status do atendimento');
  ok(await g.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'Garçom: painel cabe na tela do celular');

  // ---------- Caixa, Gerente e Proprietário ----------
  const cx = await nova({ viewport: { width: 1280, height: 860 } });
  await entrar(cx, 'caixa');
  menu = await menuDe(cx);
  ok(menu.includes('Reconhecimento de Alimentos') && !/Experiência|Visão Geral|Relatórios|Configurações|Equipe/.test(menu), `Caixa: só Reconhecimento de Alimentos (${menu.trim()})`);
  ok((await cx.request.get(`${URL}/api/solicitacoes`)).status() === 403, 'Caixa: servidor recusa a fila de atendimento (403)');
  const ge = await nova({ viewport: { width: 1280, height: 860 } });
  await entrar(ge, 'gerente');
  menu = await menuDe(ge);
  ok(/Visão Geral/.test(menu) && /Experiência do Cliente/.test(menu) && /Relatórios/.test(menu) && !/Equipe|Configurações/.test(menu), 'Gerente: operação, reclamações e indicadores, sem administração');
  const pr = await nova({ viewport: { width: 1280, height: 860 } });
  await entrar(pr, 'proprietario');
  menu = await menuDe(pr);
  ok(/Visão Geral/.test(menu) && /Relatórios/.test(menu) && !/Equipe|Configurações/.test(menu), 'Proprietário: dashboards, satisfação e relatórios');
  await pr.goto(`${URL}/#/experiencia-cliente`); await pr.waitForTimeout(1000);
  ok(await pr.locator('#cx-fila [data-sol]').count() === 0, 'Proprietário: acompanha os pedidos sem botões de atender');
  await pr.locator('#sairBtn').click(); await pr.waitForTimeout(600);
  ok(pr.url().endsWith('/equipe/') && (await pr.request.get(`${URL}/api/auth/eu`)).status() === 401, 'Sair: encerra a sessão');

  ok(errs.length === 0, 'Sem erros de JavaScript: ' + errs.join('|'));
  await b.close();
})();
