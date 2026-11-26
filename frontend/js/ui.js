// Componentes e utilidades compartilhadas por todos os módulos do painel.

// Colaborador logado (preenchido pelo app.js a partir de /api/auth/eu).
export const sessao = {
  usuario: null,
  pode(permissao) { return !!this.usuario?.permissoes?.includes(permissao); },
};

export async function api(path, { method = "GET", body, form } = {}) {
  const opts = { method, headers: {} };
  if (form) opts.body = form;
  else if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  let data = null;
  try { data = await res.json(); } catch { /* resposta sem JSON */ }
  if (res.status === 401 && !path.startsWith("/api/auth/")) {
    location.replace("/equipe/"); // sessão expirou ou foi encerrada pelo administrador
  }
  if (!res.ok) {
    let msg = data?.detail;
    if (Array.isArray(msg)) msg = msg.map((d) => d.msg).join("; ");
    throw new Error(msg || `Erro ${res.status}`);
  }
  return data;
}

export function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export const fmt = {
  n: (v, d = 0) => (v === null || v === undefined ? "–" : Number(v).toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d })),
  pct: (v, d = 1) => (v === null || v === undefined ? "–" : `${fmt.n(v, d)}%`),
  kg: (g) => (g === null || g === undefined ? "–" : g >= 1000 ? `${fmt.n(g / 1000, 1)} kg` : `${fmt.n(g)} g`),
  hora: (iso) => (iso ? new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }) : "–"),
  dataHora: (iso) => {
    if (!iso) return "–";
    const d = new Date(iso);
    const hoje = new Date();
    const mesmoDia = d.toDateString() === hoje.toDateString();
    const h = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    return mesmoDia ? `Hoje, ${h}` : `${d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })} ${h}`;
  },
  rel: (iso) => {
    if (!iso) return "–";
    const min = Math.max(0, (Date.now() - new Date(iso).getTime()) / 60000);
    if (min < 1) return "agora";
    if (min < 60) return `há ${Math.round(min)} min`;
    if (min < 1440) return `há ${Math.floor(min / 60)} h`;
    return fmt.dataHora(iso);
  },
  min: (v) => (v === null || v === undefined ? "–" : `${fmt.n(v, 1)} min`),
};

export function toast(msg, erro = false) {
  const t = document.createElement("div");
  t.className = "toast" + (erro ? " err" : "");
  t.textContent = msg;
  document.getElementById("toasts").appendChild(t);
  setTimeout(() => t.remove(), erro ? 6000 : 3200);
}

export function origemBadge(origem) {
  return origem === "demo"
    ? `<span class="badge demo" title="Registro fictício criado para demonstração">Demonstrativo</span>`
    : `<span class="badge real" title="Registrado durante o uso do sistema">Registro real</span>`;
}

export const CORES = {
  accent: "#FF5A1F", ink: "#121417", muted: "#8A9099", line: "#E3E5E9",
  blue: "#3B82F6", green: "#22A06B", amber: "#F59E0B", violet: "#8B5CF6", red: "#E5484D",
};

export function kpi({ icon, label, value, unit = "", foot = "", mod = "" }) {
  return `<div class="card kpi">
    ${mod ? `<span class="kpi-mod">${esc(mod)}</span>` : ""}
    <div class="kpi-top"><span class="kpi-ico">${ICON[icon] || ""}</span>${esc(label)}</div>
    <div class="kpi-value">${value}${unit ? `<small>${esc(unit)}</small>` : ""}</div>
    ${foot ? `<div class="kpi-foot">${foot}</div>` : ""}
  </div>`;
}

export function vazio(texto) {
  return `<div class="empty">${esc(texto)}</div>`;
}

// Gráficos: guarda as instâncias para destruí-las ao trocar de tela.
const charts = new Set();
export function chart(canvas, config) {
  if (!canvas || !window.Chart) return null;
  const c = new window.Chart(canvas, config);
  charts.add(c);
  return c;
}
export function destroyCharts() {
  charts.forEach((c) => c.destroy());
  charts.clear();
}
if (window.Chart) {
  window.Chart.defaults.font.family = "Inter, system-ui, sans-serif";
  window.Chart.defaults.font.size = 12;
  window.Chart.defaults.color = "#5B616B";
  window.Chart.defaults.plugins.legend.labels.boxWidth = 10;
  window.Chart.defaults.plugins.legend.labels.boxHeight = 10;
  window.Chart.defaults.maintainAspectRatio = false;
}

export function modal(html) {
  const bg = document.createElement("div");
  bg.className = "modal-bg";
  bg.innerHTML = `<div class="modal" role="dialog">${html}</div>`;
  bg.addEventListener("click", (e) => { if (e.target === bg || e.target.closest("[data-close]")) bg.remove(); });
  document.body.appendChild(bg);
  return bg;
}

const s = (d) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
export const ICON = {
  grid: s('<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>'),
  food: s('<path d="M3 11h18a9 9 0 0 1-18 0Z"/><path d="M12 3v3M8 4.5l1 2.5M16 4.5l-1 2.5"/>'),
  table: s('<rect x="3" y="7" width="18" height="5" rx="1.5"/><path d="M6 12v7M18 12v7M9 7V4M15 7V4"/>'),
  smile: s('<path d="M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"/><path d="M8.5 14.5s1.2 2 3.5 2 3.5-2 3.5-2M9 9.5h.01M15 9.5h.01"/>'),
  chart: s('<path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 6-7"/>'),
  settings: s('<path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"/>'),
  alert: s('<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/>'),
  bell: s('<path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>'),
  clock: s('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
  camera: s('<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3Z"/><circle cx="12" cy="13" r="3.5"/>'),
  scale: s('<path d="M12 3v18M5 7h14M5 7l-3 7a3.5 3.5 0 0 0 6 0L5 7ZM19 7l-3 7a3.5 3.5 0 0 0 6 0l-3-7ZM8 21h8"/>'),
  trash: s('<path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/>'),
  check: s('<path d="M20 6 9 17l-5-5"/>'),
  star: s('<path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1Z"/>'),
  msg: s('<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z"/>'),
  hand: s('<path d="M18 11V6a2 2 0 0 0-4 0v5M14 10V4a2 2 0 0 0-4 0v6M10 10.5V6a2 2 0 0 0-4 0v8a8 8 0 0 0 16 0v-3a2 2 0 0 0-4 0"/>'),
  qr: s('<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 14h3v3h-3zM20 14v.01M14 20h.01M17 17h3v3"/>'),
  refresh: s('<path d="M21 12a9 9 0 0 1-15.5 6.2L3 16M3 12a9 9 0 0 1 15.5-6.2L21 8"/><path d="M21 3v5h-5M3 21v-5h5"/>'),
  download: s('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>'),
  upload: s('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>'),
  menu: s('<path d="M4 6h16M4 12h16M4 18h16"/>'),
  sparkle: s('<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9Z"/><path d="M19 17l.8 2.2L22 20l-2.2.8L19 23l-.8-2.2L16 20l2.2-.8Z"/>'),
  info: s('<circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/>'),
  link: s('<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>'),
  print: s('<path d="M6 9V2h12v7M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/>'),
  leaf: s('<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.5 19 2c1 2 2 4.2 2 8 0 5.5-4.8 10-10 10Z"/><path d="M2 21c0-3 1.9-5.4 5.1-6"/>'),
  users: s('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/>'),
};

export const MOD_ICON = { alimentar: "food", cliente: "smile", sistema: "settings" };
export const MOD_NOME = { alimentar: "Reconhecimento de Alimentos", cliente: "Experiência do Cliente", sistema: "Sistema" };

export function atividadeItem(a) {
  return `<div class="list-item">
    <span class="list-ico mod-${esc(a.modulo)}">${ICON[MOD_ICON[a.modulo]] || ""}</span>
    <div class="list-body">
      <div class="list-title">${esc(a.descricao)}</div>
      <div class="list-meta">${esc(MOD_NOME[a.modulo] || a.modulo)} · ${fmt.dataHora(a.criado_em)}${a.origem_dado === "demo" ? " · demonstrativo" : ""}</div>
    </div>
  </div>`;
}
