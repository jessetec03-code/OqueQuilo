// Núcleo do painel: login, menu por perfil, navegação entre módulos e atualização automática.
// O menu só esconde o que o perfil não usa; quem decide o acesso é o servidor (backend/auth.py).
import { ICON, api, destroyCharts, esc, sessao } from "./ui.js";
import overview from "./modules/overview.js";
import food from "./modules/food.js";
import customer from "./modules/customer.js";
import reports from "./modules/reports.js";
import settings from "./modules/settings.js";
import equipe from "./modules/equipe.js";

const ROTAS = {
  "visao-geral": { mod: overview, titulo: "Visão Geral", eyebrow: "Code Meat | Intelligence Platform", icon: "grid", perm: ["painel"] },
  "reconhecimento": { mod: food, titulo: "Reconhecimento de Alimentos", eyebrow: "Pilar 1 · Inteligência alimentar", icon: "food", perm: ["alimentos_registrar", "alimentos_ver"] },
  "experiencia-cliente": { mod: customer, titulo: "Experiência do Cliente", eyebrow: "Pilar 2", icon: "smile", badge: true, perm: ["cliente_ver", "atendimento_ver"] },
  relatorios: { mod: reports, titulo: "Relatórios", eyebrow: "Análise integrada", icon: "chart", perm: ["relatorios"] },
  equipe: { mod: equipe, titulo: "Equipe e acessos", eyebrow: "Administração", icon: "users", perm: ["usuarios"] },
  configuracoes: { mod: settings, titulo: "Configurações", eyebrow: "Sistema", icon: "settings", perm: ["configuracoes"] },
};
const INTERVALO_MS = 5000;

const view = document.getElementById("view");
const nav = document.getElementById("nav");
let atual = null;
let timer = null;

const permitido = (id) => ROTAS[id].perm.some((p) => sessao.pode(p));
const primeiraRota = () => Object.keys(ROTAS).find(permitido);

function montarMenu() {
  const item = (id) => {
    if (!permitido(id)) return "";
    const r = ROTAS[id];
    return `<a href="#/${id}" data-rota="${id}">${ICON[r.icon]}<span>${esc(r.titulo)}</span>${r.badge ? '<span class="pill hidden" id="pill-cliente"></span>' : ""}</a>`;
  };
  const grupo = (titulo, ids) => {
    const itens = ids.map(item).join("");
    return itens ? `<div class="nav-label">${titulo}</div>${itens}` : "";
  };
  nav.innerHTML = `${item("visao-geral")}${grupo("Pilares", ["reconhecimento", "experiencia-cliente"])}${grupo("Gestão", ["relatorios", "equipe", "configuracoes"])}`;
  document.getElementById("menuBtn").innerHTML = ICON.menu;
  document.getElementById("menuBtn").onclick = () => document.getElementById("sidebar").classList.toggle("open");
  const u = sessao.usuario;
  document.getElementById("userBox").innerHTML = `<div class="user-chip" title="${esc(u.nome)}"><span class="user-ava">${esc(u.nome.trim()[0] || "?")}</span>
    <span class="user-txt"><b>${esc(u.nome)}</b><span>${esc(u.perfil_nome)}</span></span></div>
    <button class="btn btn-sm" id="sairBtn" title="Sair do sistema">Sair</button>`;
  document.getElementById("sairBtn").onclick = async () => {
    try { await api("/api/auth/sair", { method: "POST" }); } catch { /* sai mesmo assim */ }
    location.replace("/equipe/");
  };
}

async function atualizarCabecalho() {
  try {
    const c = await api("/api/cabecalho");
    document.getElementById("demoBadge").classList.toggle("hidden", !c.dados_demonstrativos);
    const abertos = (c.pedidos_abertos || 0) + (c.reclamacoes_novas || 0);
    const pill = document.getElementById("pill-cliente");
    if (pill) {
      pill.textContent = abertos;
      pill.classList.toggle("hidden", !abertos);
    }
    document.getElementById("live").classList.remove("off");
    document.getElementById("liveText").textContent = "Atualizado " + new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    document.getElementById("live").classList.add("off");
    document.getElementById("liveText").textContent = "Sem conexão com o servidor";
  }
}

async function navegar() {
  let id = (location.hash.replace(/^#\/?/, "").split("?")[0]) || primeiraRota();
  if (id === "inteligencia-alimentar") id = "reconhecimento"; // links antigos
  if (!ROTAS[id] || !permitido(id)) id = primeiraRota();
  const rota = ROTAS[id];
  if (atual?.mod?.sair) atual.mod.sair();
  clearInterval(timer);
  destroyCharts();
  atual = rota;
  document.getElementById("sidebar").classList.remove("open");
  nav.querySelectorAll("a").forEach((a) => a.classList.toggle("active", a.dataset.rota === id));
  document.getElementById("pageTitle").textContent = rota.titulo;
  document.getElementById("pageEyebrow").textContent = rota.eyebrow;
  document.title = `${rota.titulo} | Code Meat`;
  view.onclick = view.onchange = view.oninput = view.onsubmit = null;
  view.innerHTML = `<div class="empty">Carregando…</div>`;
  try {
    await rota.mod.render(view);
  } catch (e) {
    view.innerHTML = `<div class="notice">${ICON.alert}<div><b>Não foi possível carregar esta tela.</b><br>${esc(e.message)}. Verifique se o servidor está rodando (python run.py).</div></div>`;
  }
  atualizarCabecalho();
  if (rota.mod.atualizar) {
    timer = setInterval(async () => {
      if (document.hidden || atual !== rota) return;
      try { await rota.mod.atualizar(view); } catch { /* tenta de novo no próximo ciclo */ }
      atualizarCabecalho();
    }, INTERVALO_MS);
  }
}

async function iniciar() {
  try {
    const d = await api("/api/auth/eu");
    sessao.usuario = d.usuario;
  } catch {
    location.replace("/equipe/");
    return;
  }
  if (!primeiraRota()) {
    view.innerHTML = `<div class="notice">${ICON.alert}<div><b>O seu perfil ainda não tem nenhuma permissão.</b><br>Peça ao administrador para liberar o acesso em Equipe e acessos.</div></div>`;
  }
  montarMenu();
  if (primeiraRota()) navegar();
}

window.addEventListener("scroll", () => document.getElementById("topbar").classList.toggle("scrolled", window.scrollY > 4));
window.addEventListener("hashchange", navegar);
iniciar();
