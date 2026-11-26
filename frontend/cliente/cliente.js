// PILAR 2 · Página do cliente (acesso pelo QR Code da mesa) · responsável: Integrante 3
// Funciona no celular, sem cadastro. Envia os dados para a mesma API do painel.
// A Bovinu'S trabalha com comanda: não há pedido de conta por aqui.

const app = document.getElementById("app");
const params = new URLSearchParams(location.search);
let mesa = Number(params.get("mesa")) || null;
let opcoes = { motivos_atendimento: [], categorias: [] };

const ICON = {
  star: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1Z"/></svg>',
  hand: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 11V6a2 2 0 0 0-4 0v5M14 10V4a2 2 0 0 0-4 0v6M10 10.5V6a2 2 0 0 0-4 0v8a8 8 0 0 0 16 0v-3a2 2 0 0 0-4 0"/></svg>',
  msg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
};
const FACES = [["😞", "Muito ruim"], ["🙁", "Ruim"], ["😐", "Regular"], ["🙂", "Boa"], ["😄", "Excelente"]];

const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function enviar(path, body) {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(Array.isArray(d.detail) ? d.detail.map((x) => x.msg).join("; ") : d.detail || "Não foi possível enviar.");
  return d;
}

function cabecalho(titulo, sub) {
  document.getElementById("titulo").textContent = titulo;
  document.getElementById("subtitulo").textContent = sub;
  document.getElementById("mesaTag").textContent = mesa ? `Mesa ${mesa}` : "";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function escolherMesa() {
  cabecalho("Bem-vindo!", "Informe o número da sua mesa (está no cartão do QR Code).");
  app.innerHTML = `<div class="card"><label class="lbl" for="n" style="margin-top:0">Número da mesa</label>
    <input type="number" id="n" min="1" inputmode="numeric" placeholder="Ex.: 12">
    <button class="btn" id="ok">Continuar</button><div id="e"></div></div>`;
  app.querySelector("#ok").onclick = async () => {
    const n = Number(app.querySelector("#n").value);
    if (!n) return;
    const r = await fetch(`/api/mesas`).then((x) => x.json()).catch(() => null);
    if (r && !r.mesas.some((m) => m.numero === n)) {
      app.querySelector("#e").innerHTML = `<div class="erro">Mesa ${n} não encontrada.</div>`;
      return;
    }
    mesa = n;
    history.replaceState(null, "", `?mesa=${n}`);
    inicio();
  };
}

function inicio() {
  cabecalho("Como está sua experiência?", "Leva menos de 30 segundos. Sem cadastro e sem aplicativo.");
  app.innerHTML = `<div class="card">
    <button class="acao destaque" data-ir="avaliar"><span class="ic">${ICON.star}</span><div><b>Avaliar experiência</b><span>Nota em um toque</span></div></button>
    <button class="acao" data-ir="atendimento"><span class="ic">${ICON.hand}</span><div><b>Chamar atendimento</b><span>Garçom, buffet, limpeza ou outro pedido</span></div></button>
    <button class="acao" data-ir="manifestacao"><span class="ic">${ICON.msg}</span><div><b>Sugestão ou reclamação</b><span>A equipe recebe na hora</span></div></button>
  </div>`;
  app.onclick = (e) => {
    const ir = e.target.closest("[data-ir]")?.dataset.ir;
    if (ir === "avaliar") avaliar();
    if (ir === "atendimento") atendimento();
    if (ir === "manifestacao") manifestacao();
  };
}

function confirmacao(titulo, texto) {
  cabecalho("Obrigado!", "Sua mensagem chegou ao painel da equipe.");
  app.innerHTML = `<div class="card ok"><div class="check">${ICON.check}</div><h2>${esc(titulo)}</h2><p class="sub">${esc(texto)}</p>
    <button class="btn" id="mais">Voltar ao início</button></div>`;
  app.onclick = (e) => { if (e.target.id === "mais") inicio(); };
}

// Campo de texto livre que aparece quando o cliente escolhe "Outro".
function campoOutro(id, rotulo, exemplo, max) {
  return `<div class="outro" id="${id}-box" hidden>
    <label class="lbl" for="${id}">${esc(rotulo)}</label>
    <input type="text" id="${id}" maxlength="${max}" placeholder="${esc(exemplo)}" autocomplete="off" enterkeyhint="done">
    <div class="count" id="${id}-cnt">0/${max}</div></div>`;
}

function stars(id) {
  return `<div class="stars" data-stars="${id}">${[1, 2, 3, 4, 5].map((i) => `<button type="button" data-v="${i}" aria-label="${i} estrela(s)">★</button>`).join("")}</div>`;
}

function avaliar() {
  cabecalho("Avalie sua experiência", "Toque na opção que melhor descreve sua visita.");
  const v = { geral: null, atendimento: null, comida: null };
  app.innerHTML = `<div class="card">
    <button class="voltar" data-voltar>‹ Voltar</button>
    <h2>Como foi sua experiência hoje?</h2>
    <div class="faces" style="margin-top:14px">${FACES.map(([e, t], i) => `<button class="face" data-geral="${i + 1}"><span class="e">${e}</span>${t}</button>`).join("")}</div>
    <div id="extra" style="display:none">
      <span class="lbl">Atendimento <span style="font-weight:400;color:var(--muted)">(opcional)</span></span>${stars("atendimento")}
      <span class="lbl">Qualidade da comida <span style="font-weight:400;color:var(--muted)">(opcional)</span></span>${stars("comida")}
      <label class="lbl" for="com">Quer deixar um comentário? <span style="font-weight:400;color:var(--muted)">(opcional)</span></label>
      <textarea id="com" rows="3" maxlength="1000" placeholder="Conte o que gostou ou o que podemos melhorar"></textarea>
    </div>
    <button class="btn" id="env" disabled>Enviar avaliação</button><div id="e"></div></div>`;
  app.onclick = async (e) => {
    if (e.target.closest("[data-voltar]")) return inicio();
    const f = e.target.closest("[data-geral]");
    if (f) {
      v.geral = Number(f.dataset.geral);
      app.querySelectorAll("[data-geral]").forEach((b) => b.classList.toggle("on", b === f));
      app.querySelector("#extra").style.display = "block";
      app.querySelector("#env").disabled = false;
      return;
    }
    const s = e.target.closest("[data-stars] button");
    if (s) {
      const grupo = s.parentElement.dataset.stars;
      v[grupo] = Number(s.dataset.v);
      s.parentElement.querySelectorAll("button").forEach((b) => b.classList.toggle("on", Number(b.dataset.v) <= v[grupo]));
      return;
    }
    if (e.target.id === "env") {
      e.target.disabled = true;
      try {
        await enviar("/api/avaliacoes", { mesa, nota_geral: v.geral, nota_atendimento: v.atendimento, nota_comida: v.comida, comentario: app.querySelector("#com").value });
        confirmacao("Avaliação enviada", "Obrigado por nos ajudar a melhorar.");
      } catch (err) {
        app.querySelector("#e").innerHTML = `<div class="erro">${esc(err.message)}</div>`;
        e.target.disabled = false;
      }
    }
  };
}

function atendimento() {
  cabecalho("Chamar atendimento", "A equipe recebe o pedido no painel na hora.");
  if (!mesa) return escolherMesa();
  let motivo = null;
  app.innerHTML = `<div class="card"><button class="voltar" data-voltar>‹ Voltar</button>
    <h2>Do que você precisa?</h2><p class="sub">Escolha uma opção.</p>
    <div class="chips">${opcoes.motivos_atendimento.map((m) => `<button class="chip" data-m="${esc(m)}">${esc(m)}</button>`).join("")}</div>
    ${campoOutro("outro", "Descreva o que você precisa", "Ex.: trazer uma cadeirinha de bebê", 200)}
    <button class="btn" id="env" disabled>Chamar a equipe</button><div id="e"></div></div>`;
  const outro = app.querySelector("#outro");
  const valida = () => {
    const precisaTexto = motivo === "Outro";
    app.querySelector("#outro-box").hidden = !precisaTexto;
    app.querySelector("#outro-cnt").textContent = `${outro.value.length}/200`;
    app.querySelector("#env").disabled = !motivo || (precisaTexto && outro.value.trim().length < 3);
  };
  outro.oninput = valida;
  app.onclick = async (e) => {
    if (e.target.closest("[data-voltar]")) return inicio();
    const c = e.target.closest("[data-m]");
    if (c) {
      motivo = c.dataset.m;
      app.querySelectorAll("[data-m]").forEach((b) => b.classList.toggle("on", b === c));
      valida();
      if (motivo === "Outro") outro.focus();
      return;
    }
    if (e.target.id === "env") {
      e.target.disabled = true;
      try {
        const r = await enviar("/api/solicitacoes", { mesa, motivo, motivo_outro: motivo === "Outro" ? outro.value : null });
        confirmacao("Pedido enviado", r.mensagem);
      } catch (err) {
        app.querySelector("#e").innerHTML = `<div class="erro">${esc(err.message)}</div>`;
        valida();
      }
    }
  };
}

function manifestacao() {
  cabecalho("Sugestão ou reclamação", "Sua mensagem vai direto para a gestão do restaurante.");
  let tipo = "sugestao", cat = null;
  app.innerHTML = `<div class="card"><button class="voltar" data-voltar>‹ Voltar</button>
    <div class="seg"><button class="on" data-t="sugestao">Sugestão</button><button data-t="reclamacao">Reclamação</button></div>
    <span class="lbl">Sobre o quê?</span>
    <div class="chips">${opcoes.categorias.map((c) => `<button class="chip" data-c="${esc(c)}">${esc(c)}</button>`).join("")}</div>
    ${campoOutro("outro", "Qual é o assunto?", "Ex.: estacionamento, acessibilidade", 60)}
    <label class="lbl" for="txt">Escreva sua mensagem</label>
    <textarea id="txt" rows="4" maxlength="1000" placeholder="Ex.: poderiam ter opção vegetariana no buffet"></textarea>
    <div class="count" id="cnt">0/1000</div>
    <div class="req" id="falta"></div>
    <button class="btn" id="env" disabled>Enviar</button><div id="e"></div></div>`;
  const txt = app.querySelector("#txt");
  const outro = app.querySelector("#outro");
  const valida = () => {
    app.querySelector("#outro-box").hidden = cat !== "Outro";
    app.querySelector("#cnt").textContent = `${txt.value.length}/1000`;
    app.querySelector("#outro-cnt").textContent = `${outro.value.length}/60`;
    const falta = !cat ? "Escolha sobre o que é a mensagem." : cat === "Outro" && outro.value.trim().length < 3 ? "Escreva qual é o assunto." : "";
    app.querySelector("#falta").textContent = txt.value.trim().length >= 3 ? falta : "";
    app.querySelector("#env").disabled = !!falta || txt.value.trim().length < 3;
  };
  txt.oninput = valida;
  outro.oninput = valida;
  app.onclick = async (e) => {
    if (e.target.closest("[data-voltar]")) return inicio();
    const t = e.target.closest("[data-t]");
    if (t) {
      tipo = t.dataset.t;
      app.querySelectorAll("[data-t]").forEach((b) => b.classList.toggle("on", b === t));
      txt.placeholder = tipo === "sugestao" ? "Ex.: poderiam ter opção vegetariana no buffet" : "Conte o que aconteceu para a equipe resolver";
      return;
    }
    const c = e.target.closest("[data-c]");
    if (c) {
      cat = cat === c.dataset.c ? null : c.dataset.c;
      app.querySelectorAll("[data-c]").forEach((b) => b.classList.toggle("on", b.dataset.c === cat));
      valida();
      if (cat === "Outro") outro.focus();
      return;
    }
    if (e.target.id === "env") {
      e.target.disabled = true;
      try {
        const r = await enviar("/api/manifestacoes", { mesa, tipo, categoria: cat, categoria_outro: cat === "Outro" ? outro.value : null, texto: txt.value });
        confirmacao(tipo === "sugestao" ? "Sugestão enviada" : "Reclamação registrada", r.mensagem);
      } catch (err) {
        app.querySelector("#e").innerHTML = `<div class="erro">${esc(err.message)}</div>`;
        valida();
      }
    }
  };
}

(async () => {
  try { opcoes = await fetch("/api/cliente/opcoes").then((r) => r.json()); } catch { /* usa listas vazias */ }
  if (mesa) {
    const r = await fetch("/api/mesas").then((x) => x.json()).catch(() => null);
    if (r && !r.mesas.some((m) => m.numero === mesa)) mesa = null;
  }
  mesa ? inicio() : escolherMesa();
})();
