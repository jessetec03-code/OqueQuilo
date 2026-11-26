// EQUIPE E ACESSOS · colaboradores, perfis e permissões (só para quem tem a permissão "usuarios").
// Tudo o que esta tela muda é validado de novo no servidor (backend/routers/equipe.py).
import { ICON, api, esc, fmt, modal, sessao, toast } from "../ui.js";

function usuariosHtml(lista, perfis) {
  return `<div class="table-wrap"><table class="table"><thead><tr><th>Colaborador</th><th>Usuário</th><th>Perfil</th><th>Situação</th><th>Último acesso</th><th></th></tr></thead><tbody>
    ${lista.map((u) => `<tr>
      <td><b>${esc(u.nome)}</b>${u.id === sessao.usuario.id ? ' <span class="badge">você</span>' : ""}</td>
      <td><span class="cred">${esc(u.login)}</span></td>
      <td><select class="select" data-perfil="${u.id}" ${u.id === sessao.usuario.id ? "disabled" : ""} aria-label="Perfil de ${esc(u.nome)}">
        ${Object.entries(perfis).map(([k, v]) => `<option value="${k}" ${k === u.perfil ? "selected" : ""}>${esc(v)}</option>`).join("")}</select></td>
      <td>${u.ativo ? '<span class="badge ok">Ativo</span>' : '<span class="badge">Desativado</span>'}</td>
      <td class="num">${u.ultimo_acesso ? fmt.dataHora(u.ultimo_acesso) : "–"}</td>
      <td style="white-space:nowrap"><button class="btn btn-sm" data-senha="${u.id}" data-nome="${esc(u.nome)}">Nova senha</button>
        ${u.id === sessao.usuario.id ? "" : `<button class="btn btn-sm ${u.ativo ? "btn-danger" : ""}" data-ativo="${u.id}" data-valor="${u.ativo ? 0 : 1}">${u.ativo ? "Desativar" : "Reativar"}</button>`}</td>
    </tr>`).join("")}</tbody></table></div>`;
}

function matrizHtml(p) {
  const perfis = Object.keys(p.perfis);
  return `<div class="table-wrap"><table class="table perm-table"><thead><tr><th>Permissão</th>${perfis.map((k) => `<th>${esc(p.perfis[k])}</th>`).join("")}</tr></thead><tbody>
    ${Object.entries(p.permissoes).map(([perm, desc]) => `<tr><td>${esc(desc)}</td>
      ${perfis.map((k) => `<td><input type="checkbox" data-perfil-perm="${k}" value="${perm}" ${p.matriz[k].includes(perm) ? "checked" : ""} ${k === "admin" ? "disabled" : ""}
        aria-label="${esc(p.perfis[k])}: ${esc(desc)}"></td>`).join("")}</tr>`).join("")}
  </tbody></table></div>
  <div class="hint" style="margin-top:8px">A mudança vale na hora, inclusive para quem já está logado. O Administrador sempre tem todas as permissões, para ninguém ficar sem acesso.</div>`;
}

async function carregar(root) {
  const [u, p] = await Promise.all([api("/api/usuarios"), api("/api/permissoes")]);
  root.querySelector("#eq-lista").innerHTML = usuariosHtml(u.usuarios, u.perfis);
  root.querySelector("#eq-matriz").innerHTML = matrizHtml(p);
  return u.perfis;
}

export default {
  async render(root) {
    root.innerHTML = `
      <div class="notice">${ICON.info}<div><b>Como a equipe entra:</b> o QR Code da equipe (em Configurações) abre a página de login. Cada colaborador usa o próprio usuário e senha e vê apenas as funções do seu perfil. As permissões são conferidas pelo servidor em cada ação.</div></div>
      <div class="card"><div class="card-head"><div><h3>Colaboradores</h3><div class="card-sub">Garçom, caixa, gerente, proprietário e administrador</div></div>
        <div class="actions"><button class="btn btn-sm btn-primary" id="eq-novo">${ICON.users}Novo colaborador</button></div></div>
        <div id="eq-lista"></div></div>
      <div class="card"><div class="card-head"><div><h3>Permissões por perfil</h3><div class="card-sub">Marque o que cada função pode fazer</div></div></div>
        <div id="eq-matriz"></div></div>`;
    let perfis = await carregar(root);

    root.onchange = async (e) => {
      const sel = e.target.closest("[data-perfil]");
      const chk = e.target.closest("[data-perfil-perm]");
      try {
        if (sel) {
          await api(`/api/usuarios/${sel.dataset.perfil}`, { method: "PATCH", body: { perfil: sel.value } });
          toast("Perfil alterado. O colaborador precisa entrar de novo.");
        } else if (chk) {
          const perfil = chk.dataset.perfilPerm;
          const marcadas = [...root.querySelectorAll(`[data-perfil-perm="${perfil}"]:checked`)].map((x) => x.value);
          await api(`/api/permissoes/${perfil}`, { method: "PUT", body: { permissoes: marcadas } });
          toast(`Permissões de ${perfis[perfil]} atualizadas`);
        } else return;
      } catch (err) { toast(err.message, true); }
      perfis = await carregar(root);
    };

    root.onclick = async (e) => {
      const at = e.target.closest("[data-ativo]");
      const se = e.target.closest("[data-senha]");
      if (at) {
        try {
          await api(`/api/usuarios/${at.dataset.ativo}`, { method: "PATCH", body: { ativo: at.dataset.valor === "1" } });
          toast(at.dataset.valor === "1" ? "Colaborador reativado" : "Colaborador desativado e desconectado");
          perfis = await carregar(root);
        } catch (err) { toast(err.message, true); }
        return;
      }
      if (se) {
        const m = modal(`<h3>Nova senha para ${esc(se.dataset.nome)}</h3>
          <div class="field"><label for="ns">Nova senha (mínimo 6 caracteres)</label><input class="input" id="ns" type="text" autocomplete="new-password" minlength="6"></div>
          <div class="hint" style="margin:6px 0 12px">Entregue a senha pessoalmente ao colaborador. As sessões abertas dele são encerradas.</div>
          <div class="row" style="justify-content:flex-end"><button class="btn" data-close>Cancelar</button><button class="btn btn-primary" id="ok">Salvar</button></div>`);
        m.querySelector("#ok").onclick = async () => {
          try {
            await api(`/api/usuarios/${se.dataset.senha}`, { method: "PATCH", body: { senha: m.querySelector("#ns").value } });
            m.remove();
            toast("Senha alterada");
          } catch (err) { toast(err.message, true); }
        };
        return;
      }
      if (e.target.closest("#eq-novo")) {
        const m = modal(`<h3>Novo colaborador</h3>
          <div class="field"><label for="nc-nome">Nome</label><input class="input" id="nc-nome" maxlength="80" autocomplete="off"></div>
          <div class="row" style="margin-top:10px">
            <div class="field"><label for="nc-login">Usuário</label><input class="input" id="nc-login" maxlength="30" autocapitalize="none" autocomplete="off" placeholder="ex.: maria.silva"></div>
            <div class="field"><label for="nc-perfil">Perfil</label><select class="select" id="nc-perfil">${Object.entries(perfis).map(([k, v]) => `<option value="${k}" ${k === "garcom" ? "selected" : ""}>${esc(v)}</option>`).join("")}</select></div>
          </div>
          <div class="field" style="margin-top:10px"><label for="nc-senha">Senha inicial (mínimo 6 caracteres)</label><input class="input" id="nc-senha" type="text" autocomplete="new-password"></div>
          <div class="row" style="justify-content:flex-end;margin-top:14px"><button class="btn" data-close>Cancelar</button><button class="btn btn-primary" id="ok">Cadastrar</button></div>`);
        m.querySelector("#ok").onclick = async () => {
          const body = { nome: m.querySelector("#nc-nome").value.trim(), login: m.querySelector("#nc-login").value.trim(),
            perfil: m.querySelector("#nc-perfil").value, senha: m.querySelector("#nc-senha").value };
          if (body.nome.length < 2 || body.login.length < 3 || body.senha.length < 6) {
            toast("Preencha o nome, um usuário com 3 letras ou mais e uma senha com 6 caracteres ou mais.", true);
            return;
          }
          try {
            await api("/api/usuarios", { method: "POST", body });
            m.remove();
            toast(`${body.nome} cadastrado como ${perfis[body.perfil]}`);
            perfis = await carregar(root);
          } catch (err) { toast(err.message, true); }
        };
      }
    };
  },
};
