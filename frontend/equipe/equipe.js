// Login da equipe (aberto pelo QR Code da equipe). Sem login, nenhuma rota do painel responde.
const form = document.getElementById("form");
const erro = document.getElementById("erro");
const botao = document.getElementById("entrar");
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// Se já houver sessão válida, vai direto para o painel.
fetch("/api/auth/eu").then((r) => { if (r.ok) location.replace("/"); }).catch(() => {});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const login = form.login.value.trim();
  const senha = form.senha.value;
  erro.innerHTML = "";
  if (!login || !senha) {
    erro.innerHTML = `<div class="erro">Preencha o usuário e a senha.</div>`;
    return;
  }
  botao.disabled = true;
  botao.textContent = "Entrando…";
  try {
    const r = await fetch("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ login, senha }) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof d.detail === "string" ? d.detail : "Não foi possível entrar.");
    location.replace("/");
  } catch (err) {
    erro.innerHTML = `<div class="erro">${esc(err.message === "Failed to fetch" ? "Sem conexão com o servidor." : err.message)}</div>`;
    form.senha.value = "";
    form.senha.focus();
    botao.disabled = false;
    botao.textContent = "Entrar";
  }
});
