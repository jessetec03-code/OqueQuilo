// PILAR 1 · RECONHECIMENTO INTELIGENTE DE ALIMENTOS (responsável: Integrante 1)
// Foto (câmera do celular ou upload) -> reconhecimento e segmentação (YOLOE local, Claude opcional)
// -> conferência dos alimentos -> peso TOTAL do prato. Depois: prato devolvido (sobra).
import { CORES, ICON, api, chart, esc, fmt, kpi, modal, toast, vazio, sessao } from "../ui.js";

const ORIGEM_PESO = { informado: "Informado", balanca: "Balança", simulado: "Simulado", estimativa_ia: "Estimativa IA" };
const METODO = { ia_local: ["ia", "IA local"], ia_claude: ["ia", "IA em nuvem"], manual: ["manual", "Manual"] };
const COR = {
  Carne: "#E11D48", Arroz: "#0EA5E9", "Feijão": "#7C3AED", "Batata frita": "#F59E0B", Salada: "#16A34A",
  Frango: "#EA580C", "Linguiça": "#DB2777", Acompanhamentos: "#0D9488", "Não identificado": "#9CA3AF",
};
const EXTRAS = ["#2563EB", "#CA8A04", "#9333EA", "#059669", "#DC2626", "#4F46E5"];
const LADO_MAX = 1600; // a foto é reduzida no navegador antes do envio (mais rápida, sem limite de 10 MB)
let st = null;
let graficos = {};
let streamAtivo = null;

function corDe(nome) {
  if (COR[nome]) return COR[nome];
  let h = 0;
  for (const c of nome) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return EXTRAS[h % EXTRAS.length];
}

function novoEstado(ia) {
  return { ia, imagem: null, imagemUrl: null, previa: null, processando: false, analise: null, metodo: "manual",
    itens: [], enviando: false, mascaras: true };
}

function iaNotice(ia) {
  if (ia.ia_disponivel) {
    const local = ia.motor_ativo === "local";
    return `<div class="notice info">${ICON.sparkle}<div><b>Reconhecimento automático ativo</b> · ${esc(ia.motor)}${local ? " · roda neste computador, sem custo de API" : " · API externa (opcional)"}.
      ${local ? "Identifica e contorna (segmenta) cada alimento na foto e mostra a confiança." : "Identifica os alimentos e a região aproximada."}
      Abaixo de 35% de confiança a região aparece como <b>Não identificado</b>. O modelo não mede peso. O operador confere os itens antes de salvar.</div></div>`;
  }
  return `<div class="notice">${ICON.info}<div><b>Modo de marcação manual.</b> ${esc(ia.mensagem)} A foto é salva normalmente e os registros ficam identificados como "manual".</div></div>`;
}

function kpisHtml(r) {
  const m = r.metodos_reconhecimento || {};
  const ia = (m.ia_local || 0) + (m.ia_claude || 0);
  return `<div class="grid g-4">
    ${kpi({ icon: "leaf", label: "Desperdício no prato", value: fmt.n(r.desperdicio_pct, 1), unit: "%", foot: `${fmt.kg(r.peso_residual_total_g)} de sobra em ${fmt.n(r.pratos_com_retorno)} pratos` })}
    ${kpi({ icon: "food", label: "Pratos registrados", value: fmt.n(r.registros), foot: `${fmt.n(r.registros_hoje)} hoje · ${fmt.n(ia)} com reconhecimento por IA` })}
    ${kpi({ icon: "scale", label: "Peso médio servido", value: fmt.n(r.peso_servido_medio_g, 0), unit: "g", foot: origemPesoTexto(r.origem_pesagens) })}
    ${kpi({ icon: "clock", label: "Aguardando retorno", value: fmt.n(r.aguardando_retorno), foot: "Pratos sem peso residual registrado" })}
  </div>`;
}

function origemPesoTexto(o) {
  const partes = Object.entries(o || {}).map(([k, n]) => `${n} ${ORIGEM_PESO[k]?.toLowerCase() || k}`);
  return partes.length ? `Pesagens: ${partes.join(", ")}` : "Nenhuma pesagem ainda";
}

function passo(n, ativo, txt) { return `<div class="step ${ativo ? "on" : ""}"><b>${n}</b>${txt}</div>`; }

const cameraAoVivo = () => !!(window.isSecureContext && navigator.mediaDevices?.getUserMedia);

function capturaHtml() {
  const vivo = cameraAoVivo();
  return `<div class="cap-actions">
      ${vivo
        ? `<button class="cap-btn" data-a="camera" type="button">${ICON.camera}Abrir câmera<small>Câmera do celular ou webcam, com pré-visualização</small></button>`
        : `<label class="cap-btn">${ICON.camera}Tirar foto<small>Abre a câmera do celular</small><input type="file" accept="image/*" capture="environment" id="al-cam" hidden></label>`}
      <label class="cap-btn" id="al-drop">${ICON.upload}Enviar foto<small>Galeria ou arquivo (JPG, PNG, WEBP). No computador, arraste aqui.</small>
        <input type="file" accept="image/jpeg,image/png,image/webp" id="al-file" hidden></label>
    </div>
    ${vivo ? "" : `<div class="hint" style="margin-top:8px">A câmera com pré-visualização exige HTTPS (ou localhost). Neste endereço o botão "Tirar foto" usa a câmera nativa do celular.</div>`}
    <div style="text-align:center;margin-top:10px"><button class="btn btn-sm" data-a="semfoto">Registrar sem foto</button></div>`;
}

function fotoHtml() {
  const a = st.analise;
  const src = st.imagemUrl || st.previa;
  const regs = (a?.regioes || []).filter((g) => g.tipo === "alimento");
  const masks = regs.map((g) => {
    const c = corDe(g.alimento);
    if (g.poligono?.length >= 3) {
      const pts = g.poligono.map(([x, y]) => `${x},${y}`).join(" ");
      return `<polygon points="${pts}" fill="${c}" fill-opacity="${g.identificado ? 0.38 : 0.22}" stroke="${c}" ${g.identificado ? "" : 'stroke-dasharray="5 4"'}/>`;
    }
    const r = g.regiao;
    return `<rect x="${r.x}" y="${r.y}" width="${r.largura}" height="${r.altura}" stroke="${c}"/>`;
  }).join("");
  // Regiões não identificadas aparecem só com contorno cinza tracejado
  const vistos = new Set(); // um rótulo por categoria (na região de maior confiança); as demais ficam só com o contorno
  const tags = regs.filter((g) => g.identificado && !vistos.has(g.alimento) && vistos.add(g.alimento)).map((g) => `<span class="tag" style="left:${g.regiao.x * 100}%;top:${Math.max(g.regiao.y * 100, 4)}%;background:${corDe(g.alimento)}">${esc(g.alimento)}${g.confianca_pct != null ? ` ${g.confianca_pct}%` : ""}</span>`).join("");
  return `<div class="seg-photo ${st.mascaras ? "" : "sem-mascara"}" id="al-photo"><div class="stage">
      <img src="${src}" alt="Foto do prato">
      <svg class="masks" viewBox="0 0 1 1" preserveAspectRatio="none">${masks}</svg>${tags}
      ${st.processando ? `<div class="seg-processing"><div><div class="spinner"></div>${st.ia.ia_disponivel ? `Reconhecendo os alimentos…<div class="small" style="opacity:.8;font-weight:500">${st.ia.motor_ativo === "local" ? "Processamento local, sem internet" : "Enviando para a API de visão"}</div>` : "Enviando foto…"}</div></div>` : ""}
    </div></div>`;
}

function resultadoHtml() {
  const a = st.analise;
  if (!a || st.processando) return "";
  if (a.erro) return `<div class="notice" style="margin-top:12px">${ICON.alert}<div><b>Reconhecimento indisponível nesta foto.</b> ${esc(a.erro)} Marque os alimentos manualmente.</div></div>`;
  if (!st.ia.ia_disponivel || a.metodo === "manual") return `<div class="row" style="margin-top:8px"><span class="badge manual">Foto salva · marcação manual</span></div>`;
  const itens = a.itens || [];
  const linhas = itens.map((it) => {
    const c = corDe(it.alimento);
    const pct = it.confianca_pct;
    return `<div class="res-item"><span class="res-dot" style="background:${c}"></span>
      <div><b>${esc(it.alimento)}</b>${it.detalhes?.length ? `<div class="res-meta">${esc(it.detalhes.join(", "))}</div>` : ""}</div>
      <div class="res-conf">${pct != null ? `<div class="res-bar"><i style="width:${pct}%;background:${c}"></i></div><span class="num small">${pct}%</span>` : ""}
        <span class="badge ${it.confianca === "alta" ? "ok" : "warn"}">${it.confianca === "alta" ? "Alta" : "Média"}</span></div></div>`;
  }).join("");
  const nao = a.nao_identificados
    ? `<div class="res-item"><span class="res-dot" style="background:${COR["Não identificado"]}"></span><div><b>Não identificado</b><div class="res-meta">${a.nao_identificados} região(ões) com confiança abaixo de 35%. Confira e adicione manualmente, se for comida.</div></div><span></span></div>` : "";
  const vazioTxt = !itens.length ? `<div class="notice" style="margin:0">${ICON.info}<div>Nenhum alimento identificado com confiança suficiente. Marque os alimentos manualmente.</div></div>` : "";
  return `<div class="card-sub" style="margin:14px 0 8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
      <b style="color:var(--ink)">Resultado do reconhecimento</b><span class="badge ia">${ICON.sparkle.replace("<svg", '<svg width="12" height="12"')} ${esc(a.motor || "")}</span>
      ${a.tempo_ms != null ? `<span class="small muted">${fmt.n(a.tempo_ms)} ms</span>` : ""}
      ${(a.regioes || []).some((g) => g.poligono?.length) ? `<label class="small" style="margin-left:auto;display:flex;gap:6px;align-items:center;cursor:pointer"><input type="checkbox" id="al-mask" ${st.mascaras ? "checked" : ""}>Mostrar contornos</label>` : ""}
    </div>
    <div class="res-list">${vazioTxt}${linhas}${nao}</div>
    ${a.objetos?.length ? `<div class="res-meta" style="margin-top:8px">Objetos detectados e ignorados (não são comida): ${esc(a.objetos.join(", "))}.</div>` : ""}`;
}

function formHtml() {
  const temItens = st.itens.length > 0;
  const temFoto = st.imagemUrl || st.previa;
  const topo = temFoto
    ? `${fotoHtml()}${resultadoHtml()}
      <div class="row" style="margin-top:10px"><button class="btn btn-sm" data-a="trocar" style="margin-left:auto" ${st.processando ? "disabled" : ""}>${ICON.refresh}Trocar foto</button></div>`
    : st.analise ? `<div class="notice" style="margin:0">${ICON.info}<div>Registro sem foto: marque os alimentos manualmente. <button class="btn btn-sm" data-a="trocar">Usar foto</button></div></div>` : capturaHtml();

  const chips = st.itens.map((it, i) => `<span class="chip on ${it.origem === "ia" ? "ia" : ""}" title="${it.origem === "ia" ? `Reconhecido pela IA (confiança ${it.confianca})` : "Marcado manualmente"}">
      ${it.origem === "ia" ? ICON.sparkle.replace("<svg", '<svg width="12" height="12"') : ""}${esc(it.alimento)}<span class="x" data-rm="${i}">✕</span></span>`).join("");
  const base = [...(st.ia.categorias || []), ...st.ia.catalogo];
  const sugestoes = [...new Set(base)].filter((c) => !st.itens.some((i) => i.alimento.toLowerCase() === c.toLowerCase()))
    .map((c) => `<button class="chip" data-add="${esc(c)}">+ ${esc(c)}</button>`).join("");

  return `
    <div class="steps">${passo(1, true, "Foto")}${passo(2, !!st.analise, "Reconhecimento")}${passo(3, temItens, "Conferência")}${passo(4, temItens, "Peso total")}</div>
    ${topo}
    <div class="field" style="margin-top:16px"><label>Alimentos confirmados ${temItens ? `<span class="muted">(${st.itens.length})</span>` : ""}</label>
      <div class="chips" style="min-height:30px">${chips || '<span class="small muted">Nenhum alimento marcado ainda. Adicione abaixo.</span>'}</div>
      <details style="margin-top:6px"><summary class="small" style="cursor:pointer;font-weight:600">Adicionar ou corrigir manualmente</summary>
        <div class="chips" style="margin-top:8px">${sugestoes}</div>
        <div class="row" style="margin-top:8px"><input class="input" id="al-outro" placeholder="Outro alimento" maxlength="60" style="flex:1"><button class="btn btn-sm" data-a="outro">Adicionar</button></div>
      </details>
    </div>
    <div class="row" style="margin-top:16px">
      <div class="field"><label for="al-peso">Peso total do prato (g)</label><input class="input num" id="al-peso" type="number" min="1" max="5000" placeholder="ex.: 520"></div>
      <div class="field"><label for="al-origem">Origem do peso</label><select class="select" id="al-origem">
        <option value="informado">Informado pelo operador</option><option value="simulado">Simulado (demonstração)</option>
        <option value="balanca" disabled>Balança conectada (não integrada no protótipo)</option></select></div>
      <div class="field" style="flex:0 0 auto;min-width:0"><label for="al-mesa">Mesa</label><input class="input num" id="al-mesa" type="number" min="1" placeholder="opcional" style="width:110px"></div>
    </div>
    <div class="row" style="margin-top:10px">
      <button class="btn btn-sm" data-a="simular" title="Gera um peso aleatório e marca a origem como simulada">${ICON.scale}Gerar peso simulado</button>
      <span class="hint" style="flex:1">A balança mede o peso total do prato, não de cada alimento. Por isso o sistema não mostra peso por item.</span>
    </div>
    <div class="row" style="margin-top:16px;justify-content:flex-end">
      <button class="btn" data-a="limpar">Limpar</button>
      <button class="btn btn-primary" data-a="salvar" ${temItens && !st.enviando && !st.processando ? "" : "disabled"}>${ICON.check}Salvar registro</button>
    </div>`;
}

function pendentesHtml(regs) {
  const pend = regs.filter((r) => r.peso_residual_g === null).slice(0, 6);
  if (!pend.length) return vazio("Nenhum prato aguardando retorno.");
  return `<div class="list">${pend.map((r) => `<div class="list-item">
    ${r.imagem_url ? `<img class="thumb" src="${r.imagem_url}" alt="">` : `<span class="thumb">${ICON.food}</span>`}
    <div class="list-body"><div class="list-title">Prato #${r.id}${r.mesa ? ` · Mesa ${r.mesa}` : ""}</div>
      <div class="list-meta">${fmt.dataHora(r.criado_em)} · ${r.itens.map((i) => esc(i.alimento)).join(", ")}</div></div>
    <button class="btn btn-sm btn-dark" data-retorno="${r.id}">Registrar sobra</button></div>`).join("")}</div>`;
}

function historicoHtml(regs) {
  if (!regs.length) return vazio("Nenhum prato registrado ainda.");
  return `<div class="table-wrap"><table class="table"><thead><tr><th></th><th>Registro</th><th>Alimentos</th><th>Peso servido</th><th>Sobra</th><th>Reconhecimento</th></tr></thead><tbody>
  ${regs.map((r) => `<tr>
    <td style="width:56px">${r.imagem_url ? `<a href="${r.imagem_url}" target="_blank" rel="noopener"><img class="thumb" src="${r.imagem_url}" alt="Foto do prato ${r.id}"></a>` : `<span class="thumb" title="Sem foto">${ICON.food}</span>`}</td>
    <td><b>#${r.id}</b>${r.mesa ? ` · Mesa ${r.mesa}` : ""}<div class="small muted">${fmt.dataHora(r.criado_em)}</div>${r.origem_dado === "demo" ? '<span class="badge demo">Demonstrativo</span>' : ""}</td>
    <td><div class="chips">${r.itens.map((i) => `<span class="badge ${i.sobrou ? "accent" : i.origem === "ia" ? "ia" : "manual"}" title="${i.origem === "ia" ? "IA" : "Manual"}${i.sobrou ? " · sobrou" : ""}">${esc(i.alimento)}${i.sobrou ? " · sobrou" : ""}</span>`).join("")}</div></td>
    <td class="num">${fmt.kg(r.peso_total_g)}${r.peso_total_origem ? `<div class="small muted">${ORIGEM_PESO[r.peso_total_origem]}</div>` : ""}</td>
    <td class="num">${r.peso_residual_g === null ? `<button class="btn btn-sm" data-retorno="${r.id}">Registrar</button>` : `${fmt.kg(r.peso_residual_g)}<div class="small muted">${fmt.pct(r.desperdicio_pct)}</div>`}</td>
    <td>${((m) => `<span class="badge ${m[0]}">${m[1]}</span>`)(METODO[r.metodo_reconhecimento] || METODO.manual)}</td>
  </tr>`).join("")}</tbody></table></div>`;
}

function graficosDados(r) {
  return {
    sobras: {
      labels: r.mais_sobras.map((a) => a.alimento),
      datasets: [{ label: "Pratos com sobra (%)", data: r.mais_sobras.map((a) => a.incidencia_sobra_pct), backgroundColor: CORES.accent, borderRadius: 6, maxBarThickness: 22 }],
    },
    hora: {
      labels: r.por_hora.map((h) => `${h.hora}h`),
      datasets: [
        { type: "bar", label: "Pratos", data: r.por_hora.map((h) => h.pratos), backgroundColor: "rgba(18,20,23,.12)", borderRadius: 6, yAxisID: "y" },
        { type: "line", label: "Desperdício (%)", data: r.por_hora.map((h) => h.desperdicio_pct), borderColor: CORES.accent, backgroundColor: CORES.accent, tension: .35, yAxisID: "y1" },
      ],
    },
  };
}

async function carregarDados(root, comForm = false) {
  const [resumo, lista] = await Promise.all([api("/api/alimentar/resumo"), api("/api/alimentar/registros?limite=20")]);
  root.querySelector("#al-kpis").innerHTML = kpisHtml(resumo);
  root.querySelector("#al-pend").innerHTML = pendentesHtml(lista.registros);
  root.querySelector("#al-hist").innerHTML = historicoHtml(lista.registros);
  root.querySelector("#al-top").innerHTML = resumo.mais_servidos.length
    ? resumo.mais_servidos.map((a) => `<div class="bar-row"><span>${esc(a.alimento)}</span><div class="bar-track"><div class="bar-fill" style="width:${(a.pratos / resumo.mais_servidos[0].pratos) * 100}%;background:var(--ink-3)"></div></div><span class="num muted" style="text-align:right">${a.pratos}</span></div>`).join("")
    : vazio("Sem registros.");
  const g = graficosDados(resumo);
  if (graficos.sobras) { graficos.sobras.data = g.sobras; graficos.sobras.update("none"); }
  if (graficos.hora) { graficos.hora.data = g.hora; graficos.hora.update("none"); }
  if (comForm) renderForm(root);
  return g;
}

function renderForm(root) {
  const box = root.querySelector("#al-form");
  const peso = box.querySelector("#al-peso")?.value, origem = box.querySelector("#al-origem")?.value, mesa = box.querySelector("#al-mesa")?.value;
  const aberto = box.querySelector("details")?.open;
  box.innerHTML = formHtml();
  const det = box.querySelector("details");
  if (det) det.open = aberto || (!!st.analise && !st.processando && !(st.analise.itens || []).length);
  if (peso) box.querySelector("#al-peso").value = peso;
  if (origem) box.querySelector("#al-origem").value = origem;
  if (mesa) box.querySelector("#al-mesa").value = mesa;
  for (const id of ["#al-file", "#al-cam"]) {
    const inp = box.querySelector(id);
    if (inp) inp.onchange = () => inp.files[0] && enviarFoto(root, inp.files[0]);
  }
  const drop = box.querySelector("#al-drop");
  if (drop) {
    drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("drag"); };
    drop.ondragleave = () => drop.classList.remove("drag");
    drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("drag"); if (e.dataTransfer.files[0]) enviarFoto(root, e.dataTransfer.files[0]); };
  }
  const mk = box.querySelector("#al-mask");
  if (mk) mk.onchange = () => { st.mascaras = mk.checked; box.querySelector("#al-photo").classList.toggle("sem-mascara", !mk.checked); };
}

// Lê a imagem no navegador, corrige a orientação e reduz para no máximo LADO_MAX px (JPEG).
// Também serve de validação: um arquivo que não é imagem falha aqui, antes de ir ao servidor.
async function prepararImagem(arquivo) {
  if (!arquivo.type.startsWith("image/")) throw new Error("O arquivo escolhido não é uma imagem. Use JPG, PNG ou WEBP.");
  let bmp;
  try {
    bmp = await createImageBitmap(arquivo, { imageOrientation: "from-image" });
  } catch {
    throw new Error("Não foi possível ler esta imagem (arquivo inválido ou formato não suportado, como HEIC). Tente outra foto.");
  }
  const k = Math.min(1, LADO_MAX / Math.max(bmp.width, bmp.height));
  const c = document.createElement("canvas");
  c.width = Math.round(bmp.width * k);
  c.height = Math.round(bmp.height * k);
  c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
  bmp.close?.();
  const blob = await new Promise((ok) => c.toBlob(ok, "image/jpeg", 0.9));
  if (!blob) throw new Error("Falha ao preparar a imagem. Tente novamente.");
  return blob;
}

async function enviarFoto(root, arquivo) {
  let blob;
  try {
    blob = await prepararImagem(arquivo);
  } catch (e) {
    toast(e.message, true);
    return;
  }
  if (st.previa) URL.revokeObjectURL(st.previa);
  Object.assign(st, { previa: URL.createObjectURL(blob), imagemUrl: null, imagem: null, analise: null, itens: [], processando: true });
  renderForm(root);
  const fd = new FormData();
  fd.append("imagem", blob, "prato.jpg");
  try {
    const r = await api("/api/alimentar/analisar", { method: "POST", form: fd });
    Object.assign(st, { imagem: r.imagem, imagemUrl: r.imagem_url, analise: r, metodo: r.metodo || "manual" });
    st.itens = (r.itens || []).map((i) => ({ alimento: i.alimento, origem: "ia", confianca: i.confianca }));
    if (r.erro) toast(r.erro, true);
    else if (r.itens?.length) toast(`${r.itens.length} alimento(s) reconhecido(s). Confira antes de salvar.`);
    else if (r.metodo !== "manual") toast("Nenhum alimento identificado com confiança suficiente. Marque manualmente.", true);
  } catch (e) {
    // Falha de envio: volta para a tela de captura, sem deixar uma prévia "presa"
    toast(`Falha no envio da foto: ${e.message}`, true);
    URL.revokeObjectURL(st.previa);
    st.previa = null;
    st.analise = null;
  }
  st.processando = false;
  if (root.isConnected) renderForm(root);
}

function pararCamera() {
  streamAtivo?.getTracks().forEach((t) => t.stop());
  streamAtivo = null;
}

const ERROS_CAMERA = {
  NotAllowedError: "Permissão da câmera negada. Libere o acesso à câmera nas configurações do navegador ou use \"Enviar foto\".",
  SecurityError: "O navegador bloqueou a câmera neste endereço. Use HTTPS ou \"Enviar foto\".",
  NotFoundError: "Nenhuma câmera encontrada neste aparelho. Use \"Enviar foto\".",
  OverconstrainedError: "A câmera não atende às configurações pedidas. Use \"Enviar foto\".",
  NotReadableError: "A câmera está em uso por outro aplicativo. Feche-o e tente de novo.",
  AbortError: "A câmera foi interrompida. Tente de novo.",
};

async function abrirCamera(root) {
  const m = modal(`<h3>Câmera</h3><div class="small muted" style="margin-bottom:10px">Enquadre o prato inteiro, de cima, com boa iluminação.</div>
    <video class="cam-video" autoplay playsinline muted></video>
    <div class="row" style="margin-top:14px;justify-content:flex-end"><button class="btn" data-close>Cancelar</button>
      <button class="btn btn-primary" id="cam-ok" disabled>${ICON.camera}Capturar</button></div>`);
  // fecha a câmera junto com o modal, por qualquer caminho
  new MutationObserver((_, obs) => { if (!m.isConnected) { pararCamera(); obs.disconnect(); } }).observe(document.body, { childList: true });
  const video = m.querySelector("video");
  try {
    pararCamera();
    streamAtivo = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false });
    if (!m.isConnected) return pararCamera();
    video.srcObject = streamAtivo;
    await video.play().catch(() => {});
    m.querySelector("#cam-ok").disabled = false;
  } catch (e) {
    m.remove();
    pararCamera();
    toast(ERROS_CAMERA[e.name] || `Não foi possível abrir a câmera (${e.name || e.message}). Use "Enviar foto".`, true);
    return;
  }
  m.querySelector("#cam-ok").onclick = () => {
    if (!video.videoWidth) return toast("A câmera ainda não está pronta. Aguarde um instante.", true);
    const c = document.createElement("canvas");
    c.width = video.videoWidth;
    c.height = video.videoHeight;
    c.getContext("2d").drawImage(video, 0, 0);
    c.toBlob((b) => {
      m.remove();
      pararCamera();
      if (b) enviarFoto(root, new File([b], "camera.jpg", { type: "image/jpeg" }));
      else toast("Falha ao capturar a foto. Tente de novo.", true);
    }, "image/jpeg", 0.92);
  };
}

function abrirRetorno(root, reg) {
  const m = modal(`<h3>Retorno do prato #${reg.id}</h3>
    <div class="small muted" style="margin-bottom:14px">Peso servido: ${fmt.kg(reg.peso_total_g)}${reg.peso_total_origem ? ` (${ORIGEM_PESO[reg.peso_total_origem].toLowerCase()})` : ""}. Marque o que sobrou e informe o peso da sobra.</div>
    <div class="field"><label>Alimentos que sobraram</label><div class="chips">${reg.itens.map((i) => `<button class="chip sobra" data-item="${i.id}">${esc(i.alimento)}</button>`).join("")}</div></div>
    <div class="row" style="margin-top:14px">
      <div class="field"><label>Peso residual (g)</label><input class="input num" id="rt-peso" type="number" min="0" max="${reg.peso_total_g || 5000}" placeholder="0 se não sobrou nada"></div>
      <div class="field"><label>Origem do peso</label><select class="select" id="rt-origem"><option value="informado">Informado pelo operador</option><option value="simulado">Simulado (demonstração)</option></select></div>
    </div>
    <div class="row" style="margin-top:18px;justify-content:flex-end"><button class="btn" data-close>Cancelar</button><button class="btn btn-primary" id="rt-ok">${ICON.check}Salvar retorno</button></div>`);
  m.querySelectorAll("[data-item]").forEach((b) => (b.onclick = () => b.classList.toggle("on")));
  m.querySelector("#rt-ok").onclick = async () => {
    const peso = m.querySelector("#rt-peso").value;
    if (peso === "") return toast("Informe o peso residual (use 0 se não sobrou nada).", true);
    try {
      await api(`/api/alimentar/registros/${reg.id}/retorno`, { method: "POST", body: {
        peso_residual_g: Number(peso), origem_peso: m.querySelector("#rt-origem").value,
        itens_sobra: [...m.querySelectorAll("[data-item].on")].map((b) => Number(b.dataset.item)),
      } });
      m.remove();
      toast("Retorno registrado. Indicadores atualizados.");
      carregarDados(root);
    } catch (e) { toast(e.message, true); }
  };
}

export default {
  async render(root) {
    const ia = await api("/api/alimentar/status");
    st = novoEstado(ia);
    root.innerHTML = `
      ${iaNotice(ia)}
      <div id="al-kpis"></div>
      <div class="grid g-main">
        <div class="card"><div class="card-head"><div><h3>1. Prato servido</h3><div class="card-sub">Foto do prato, reconhecimento dos alimentos e peso total</div></div></div><div id="al-form"></div></div>
        <div class="card"><div class="card-head"><div><h3>2. Prato devolvido</h3><div class="card-sub">Registre a sobra quando o prato voltar do salão</div></div></div><div id="al-pend"></div></div>
      </div>
      <div class="grid g-3">
        <div class="card span-2"><div class="card-head"><div><h3>Incidência de sobras por alimento</h3><div class="card-sub">% dos pratos em que o alimento apareceu e sobrou (mín. 2 pratos)</div></div></div>
          <div class="chart-box"><canvas id="al-c1"></canvas></div></div>
        <div class="card"><div class="card-head"><h3>Mais servidos</h3></div><div id="al-top"></div></div>
      </div>
      <div class="card"><div class="card-head"><div><h3>Consumo e desperdício por horário</h3><div class="card-sub">Ajuda a planejar a produção e a reposição do buffet</div></div></div>
        <div class="chart-box"><canvas id="al-c2"></canvas></div>
        <div class="legend-note">Sobra no prato não significa, automaticamente, insatisfação do cliente. É um sinal para investigar.</div></div>
      <div class="card"><div class="card-head"><h3>Histórico de registros</h3>${sessao.pode("relatorios") ? '<div class="actions"><a class="small" href="#/relatorios">Exportar em Relatórios</a></div>' : ""}</div><div id="al-hist"></div></div>`;
    graficos = {};
    const g0 = await carregarDados(root);
    graficos = {
      sobras: chart(root.querySelector("#al-c1"), { type: "bar", data: g0.sobras,
        options: { indexAxis: "y", plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${fmt.pct(c.raw)} dos pratos` } } },
          scales: { x: { beginAtZero: true, ticks: { callback: (v) => v + "%" }, grid: { color: "#F0F1F3" } }, y: { grid: { display: false } } } } }),
      hora: chart(root.querySelector("#al-c2"), { type: "bar", data: g0.hora,
        options: { interaction: { mode: "index", intersect: false }, plugins: { legend: { position: "bottom" } },
          scales: { y: { beginAtZero: true, title: { display: true, text: "Pratos" }, grid: { color: "#F0F1F3" } },
            y1: { beginAtZero: true, position: "right", grid: { display: false }, ticks: { callback: (v) => v + "%" } }, x: { grid: { display: false } } } } }),
    };
    root.onclick = async (e) => {
      const t = e.target;
      const rm = t.closest("[data-rm]");
      if (rm) { st.itens.splice(Number(rm.dataset.rm), 1); return renderForm(root); }
      const add = t.closest("[data-add]");
      if (add) { st.itens.push({ alimento: add.dataset.add, origem: "manual" }); return renderForm(root); }
      const ret = t.closest("[data-retorno]");
      if (ret) { try { abrirRetorno(root, await api(`/api/alimentar/registros/${ret.dataset.retorno}`)); } catch (err) { toast(err.message, true); } return; }
      const a = t.closest("[data-a]")?.dataset.a;
      if (!a) return;
      const box = root.querySelector("#al-form");
      if (a === "camera") return abrirCamera(root);
      if (a === "trocar" || a === "limpar") {
        if (st.processando) return;
        if (st.previa) URL.revokeObjectURL(st.previa);
        st = novoEstado(st.ia);
        return renderForm(root);
      }
      if (a === "semfoto") { st.analise = { itens: [], metodo: "manual" }; st.imagemUrl = null; st.previa = null; return renderForm(root); }
      if (a === "outro") {
        const v = box.querySelector("#al-outro").value.trim();
        if (v) { st.itens.push({ alimento: v, origem: "manual" }); renderForm(root); }
        return;
      }
      if (a === "simular") {
        box.querySelector("#al-peso").value = Math.round(350 + Math.random() * 400);
        box.querySelector("#al-origem").value = "simulado";
        return;
      }
      if (a === "salvar") {
        const peso = box.querySelector("#al-peso").value;
        const mesa = box.querySelector("#al-mesa").value;
        st.enviando = true;
        box.querySelector('[data-a="salvar"]').disabled = true;
        try {
          const r = await api("/api/alimentar/registros", { method: "POST", body: {
            imagem: st.imagem, metodo_reconhecimento: st.metodo, itens: st.itens,
            peso_total_g: peso ? Number(peso) : null, origem_peso: box.querySelector("#al-origem").value,
            mesa: mesa ? Number(mesa) : null,
          } });
          toast(`Prato #${r.id} registrado. Indicadores atualizados.`);
          if (st.previa) URL.revokeObjectURL(st.previa);
          st = novoEstado(st.ia);
          renderForm(root);
          box.querySelector("#al-peso").value = "";
          await carregarDados(root);
        } catch (err) { toast(err.message, true); st.enviando = false; renderForm(root); }
      }
    };
    renderForm(root);
  },
  async atualizar(root) {
    if (document.querySelector(".modal-bg")) return; // não atualiza com modal (retorno ou câmera) aberto
    await carregarDados(root);
  },
  sair() { graficos = {}; pararCamera(); },
};
