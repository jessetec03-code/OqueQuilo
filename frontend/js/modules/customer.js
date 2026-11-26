// PILAR 2 · EXPERIÊNCIA DO CLIENTE (painel administrativo · responsável: Integrante 3)
// Tudo o que o cliente envia pelo QR Code aparece aqui. Cada parte da tela só aparece para
// quem tem a permissão (o servidor também confere). A exportação CSV fica em Relatórios.
import { CORES, ICON, api, chart, esc, fmt, kpi, sessao, toast, vazio } from "../ui.js";

let aba = "avaliacoes";
let origem = "todos"; // todos | real | demo
let graf = {};

const estrelas = (n) => (n ? `<span style="color:${CORES.amber};letter-spacing:1px">${"★".repeat(n)}<span style="color:#D9DCE1">${"★".repeat(5 - n)}</span></span>` : "–");
const rotulo = (escolha, outro) => (escolha === "Outro" && outro ? `Outro: <span class="outro-tag">${esc(outro)}</span>` : esc(escolha));
const qOrigem = () => (origem === "todos" ? "" : `origem=${origem}`);
const NOME_ORIGEM = { todos: "todos os dados", real: "somente registros reais", demo: "somente dados demonstrativos" };

function kpisHtml(r) {
  const po = r.por_origem || {};
  const mistura = origem === "todos" && po.demo?.avaliacoes
    ? `<br><span class="small">Reais: ${fmt.n(po.real.avaliacoes)} (média ${fmt.n(po.real.media_geral, 2)}) · Demonstrativas: ${fmt.n(po.demo.avaliacoes)}</span>` : "";
  return `<div class="grid g-4">
    ${kpi({ icon: "star", label: "Nota média geral", value: fmt.n(r.media_geral, 2), unit: "/5", foot: `${fmt.n(r.avaliacoes)} avaliações · ${NOME_ORIGEM[origem]}${mistura}` })}
    ${kpi({ icon: "smile", label: "Clientes satisfeitos", value: fmt.n(r.satisfeitos_pct, 1), unit: "%", foot: "Notas 4 e 5 sobre o total de avaliações" })}
    ${kpi({ icon: "hand", label: "Pedidos de atendimento", value: r.solicitacoes_pendentes + r.solicitacoes_em_atendimento,
      foot: `${r.solicitacoes_pendentes} pendentes · resposta média ${fmt.min(r.tempo_resposta_medio_min)}` })}
    ${kpi({ icon: "msg", label: "Reclamações e sugestões", value: `${r.reclamacoes} · ${r.sugestoes}`,
      foot: r.reclamacoes_novas ? `<span class="badge danger">${r.reclamacoes_novas} reclamação(ões) nova(s)</span>` : "Nenhuma reclamação nova" })}
  </div>`;
}

function filaHtml(sols) {
  if (!sols.length) return `<div class="notice ok">${ICON.check}<div>Nenhum pedido de atendimento aberto.</div></div>`;
  const pode = sessao.pode("atendimento_atualizar");
  return sols.map((s) => `<div class="alert-item ${s.status === "em_atendimento" ? "medio" : ""}">${ICON.hand}
    <span class="t">Mesa ${s.mesa} · ${rotulo(s.motivo, s.motivo_outro)} <span class="small muted">${fmt.rel(s.criado_em)}${s.status === "em_atendimento" ? " · em atendimento" : ""}</span></span>
    ${pode && s.status === "pendente" ? `<button class="btn btn-sm" data-sol="${s.id}" data-acao="em_atendimento">Atender</button>` : ""}
    ${pode ? `<button class="btn btn-sm btn-dark" data-sol="${s.id}" data-acao="resolvida">Resolver</button>` : ""}</div>`).join("");
}

function periodosHtml(p) {
  return `<div class="table-wrap"><table class="table"><thead><tr><th>Período</th><th>Avaliações</th><th>Nota média</th><th>Satisfeitos</th><th>Reclamações</th><th>Pedidos de atendimento</th></tr></thead><tbody>
    ${p.periodos.map((x) => `<tr><td><b>${esc(x.periodo)}</b></td><td class="num">${fmt.n(x.avaliacoes)}</td><td class="num">${fmt.n(x.nota_media, 2)}</td>
      <td class="num">${fmt.pct(x.satisfeitos_pct)}</td><td class="num">${fmt.n(x.reclamacoes)}</td><td class="num">${fmt.n(x.solicitacoes)}</td></tr>`).join("")}
  </tbody></table></div>`;
}

async function abaHtml() {
  const q = qOrigem();
  if (aba === "avaliacoes") {
    const { avaliacoes } = await api(`/api/avaliacoes?limite=40${q ? "&" + q : ""}`);
    if (!avaliacoes.length) return vazio("Nenhuma avaliação neste filtro. Abra a página do cliente pelo QR Code para enviar a primeira.");
    return `<div class="table-wrap"><table class="table"><thead><tr><th>Quando</th><th>Mesa</th><th>Geral</th><th>Atendimento</th><th>Comida</th><th>Comentário</th></tr></thead><tbody>
      ${avaliacoes.map((a) => `<tr><td class="num">${fmt.dataHora(a.criado_em)}<div>${a.origem_dado === "demo" ? '<span class="badge demo">Demonstrativo</span>' : '<span class="badge real">Real</span>'}</div></td>
        <td>${a.mesa ?? "–"}</td><td>${estrelas(a.nota_geral)}</td><td>${estrelas(a.nota_atendimento)}</td><td>${estrelas(a.nota_comida)}</td>
        <td>${a.comentario ? esc(a.comentario) : '<span class="muted">Sem comentário</span>'}</td></tr>`).join("")}</tbody></table></div>`;
  }
  const tipo = aba === "sugestoes" ? "sugestao" : "reclamacao";
  const { manifestacoes } = await api(`/api/manifestacoes?tipo=${tipo}&limite=40${q ? "&" + q : ""}`);
  if (!manifestacoes.length) return vazio(aba === "sugestoes" ? "Nenhuma sugestão neste filtro." : "Nenhuma reclamação neste filtro.");
  const gerencia = sessao.pode("cliente_gerenciar");
  return `<div class="list">${manifestacoes.map((m) => `<div class="list-item">
    <span class="list-ico mod-cliente">${ICON.msg}</span>
    <div class="list-body"><div class="list-title">${esc(m.texto)}</div>
      <div class="list-meta">${rotulo(m.categoria, m.categoria_outro)} · ${m.mesa ? `Mesa ${m.mesa}` : "Sem mesa"} · ${fmt.dataHora(m.criado_em)}${m.origem_dado === "demo" ? " · demonstrativo" : " · real"}</div></div>
    ${m.status === "nova" ? (gerencia ? `<button class="btn btn-sm" data-resolver="${m.id}">${ICON.check}Marcar como tratada</button>` : '<span class="badge danger">Nova</span>') : '<span class="badge ok">Tratada</span>'}
  </div>`).join("")}</div>`;
}

function dadosGraf(r, p) {
  const dia = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  return {
    dist: { labels: ["1★", "2★", "3★", "4★", "5★"], datasets: [{ data: [1, 2, 3, 4, 5].map((i) => r.distribuicao[i] || 0),
      backgroundColor: [CORES.red, "#F97316", CORES.amber, "#84CC16", CORES.green], borderRadius: 6, maxBarThickness: 40 }] },
    cat: { labels: r.reclamacoes_por_categoria.map((c) => c.categoria), datasets: [{ data: r.reclamacoes_por_categoria.map((c) => c.n), backgroundColor: CORES.violet, borderRadius: 6, maxBarThickness: 22 }] },
    dia: { labels: p.serie.map((d) => dia(d.data)), datasets: [
      { type: "bar", label: "Avaliações", data: p.serie.map((d) => d.avaliacoes), backgroundColor: "rgba(18,20,23,.14)", borderRadius: 5, yAxisID: "y" },
      { type: "bar", label: "Reclamações", data: p.serie.map((d) => d.reclamacoes), backgroundColor: "rgba(139,92,246,.45)", borderRadius: 5, yAxisID: "y" },
      { type: "line", label: "Nota média", data: p.serie.map((d) => d.nota_media), borderColor: CORES.accent, backgroundColor: CORES.accent, tension: .3, spanGaps: true, yAxisID: "y1" },
    ] },
  };
}

async function carregar(root, comAba = true) {
  const q = qOrigem();
  const verCliente = sessao.pode("cliente_ver");
  const verFila = sessao.pode("atendimento_ver");
  const [r, p, sols] = await Promise.all([
    verCliente ? api(`/api/cliente/resumo${q ? "?" + q : ""}`) : null,
    verCliente ? api(`/api/cliente/periodo?dias=30${q ? "&" + q : ""}`) : null,
    verFila ? api("/api/solicitacoes?abertas=true") : null,
  ]);
  if (verFila) root.querySelector("#cx-fila").innerHTML = filaHtml(sols.solicitacoes);
  if (!verCliente) return null;
  root.querySelector("#cx-kpis").innerHTML = kpisHtml(r);
  root.querySelector("#cx-periodos").innerHTML = periodosHtml(p);
  const g = dadosGraf(r, p);
  for (const k of ["dist", "cat", "dia"]) if (graf[k]) { graf[k].data = g[k]; graf[k].update("none"); }
  if (comAba) root.querySelector("#cx-aba").innerHTML = await abaHtml();
  return g;
}

function tabs() {
  const t = (id, txt) => `<button class="${aba === id ? "on" : ""}" data-aba="${id}">${txt}</button>`;
  return `<div class="seg">${t("avaliacoes", "Avaliações")}${t("sugestoes", "Sugestões")}${t("reclamacoes", "Reclamações")}</div>`;
}

function filtroOrigem() {
  const b = (id, txt) => `<button class="${origem === id ? "on" : ""}" data-origem="${id}">${txt}</button>`;
  return `<div class="seg" title="Separa registros reais dos dados demonstrativos">${b("todos", "Todos")}${b("real", "Reais")}${b("demo", "Demonstrativos")}</div>`;
}

export default {
  async render(root) {
    const verCliente = sessao.pode("cliente_ver");
    const verFila = sessao.pode("atendimento_ver");
    const qr = await api("/api/qrcode/info");
    const fila = verFila ? `<div class="card"><div class="card-head"><div><h3>Pedidos de atendimento em tempo real</h3><div class="card-sub">Enviados pelos clientes no QR Code da mesa${verCliente ? ". Também aparecem nos alertas da Visão Geral" : ""}.</div></div></div>
          <div id="cx-fila"></div></div>` : "";
    const acesso = `<div class="card"><div class="card-head"><h3>Acesso do cliente</h3></div>
          <div class="qr-box"><img src="/api/qrcode/1.svg" alt="QR Code da mesa 1">
            <div><b>Mesa 1</b><div class="small muted" style="margin:4px 0 8px">Sem aplicativo e sem cadastro. O cliente é anônimo.</div>
              <a class="btn btn-sm" href="/cliente/?mesa=1" target="_blank" rel="noopener">${ICON.link}Abrir página do cliente</a></div></div>
          <div class="hint" style="margin-top:10px">Endereço usado nos QR Codes: <b>${esc(qr.url_base)}</b>. O celular precisa estar na mesma rede Wi-Fi deste computador.${sessao.pode("configuracoes") ? ' <a href="#/configuracoes">Imprimir QR Codes</a>' : ""}</div></div>`;
    root.innerHTML = verCliente ? `
      <div class="card" style="padding:12px 16px"><div class="row" style="align-items:center;justify-content:space-between">
        <div class="small muted">Fonte dos indicadores: os registros reais e os demonstrativos ficam separados no banco. A média é sempre calculada das notas gravadas.</div>
        <div id="cx-origem">${filtroOrigem()}</div></div></div>
      <div id="cx-kpis"></div>
      <div class="grid g-main">${fila || '<div class="card"><h3>Pedidos de atendimento</h3><p class="muted">O seu perfil não acompanha a fila.</p></div>'}${acesso}</div>
      <div class="card"><div class="card-head"><div><h3>Satisfação por dia (últimos 30 dias)</h3><div class="card-sub">Avaliações e reclamações por dia e nota média diária</div></div></div>
        <div class="chart-box tall"><canvas id="cx-c3"></canvas></div>
        <div style="margin-top:14px" id="cx-periodos"></div></div>
      <div class="grid g-2">
        <div class="card"><div class="card-head"><h3>Distribuição das notas</h3></div><div class="chart-box"><canvas id="cx-c1"></canvas></div></div>
        <div class="card"><div class="card-head"><h3>Reclamações por categoria</h3></div><div class="chart-box"><canvas id="cx-c2"></canvas></div></div>
      </div>
      <div class="card"><div class="card-head"><div id="cx-tabs">${tabs()}</div>
        ${sessao.pode("relatorios") ? '<div class="actions"><a class="small" href="#/relatorios">Exportar em Relatórios</a></div>' : ""}</div>
        <div id="cx-aba"></div></div>` : `<div class="grid g-main">${fila}${acesso}</div>`;
    graf = {};
    const g0 = await carregar(root);
    if (g0) {
      const base = { plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#F0F1F3" } } } };
      graf = {
        dist: chart(root.querySelector("#cx-c1"), { type: "bar", data: g0.dist, options: base }),
        cat: chart(root.querySelector("#cx-c2"), { type: "bar", data: g0.cat,
          options: { indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#F0F1F3" } }, y: { grid: { display: false } } } } }),
        dia: chart(root.querySelector("#cx-c3"), { type: "bar", data: g0.dia,
          options: { interaction: { mode: "index", intersect: false }, plugins: { legend: { position: "bottom" } },
            scales: { x: { grid: { display: false } }, y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#F0F1F3" }, title: { display: true, text: "Quantidade" } },
              y1: { min: 1, max: 5, position: "right", grid: { display: false }, title: { display: true, text: "Nota média" } } } } }),
      };
    }
    root.onclick = async (e) => {
      const ab = e.target.closest("[data-aba]");
      if (ab) {
        aba = ab.dataset.aba;
        root.querySelector("#cx-tabs").innerHTML = tabs();
        root.querySelector("#cx-aba").innerHTML = await abaHtml();
        return;
      }
      const or = e.target.closest("[data-origem]");
      if (or) {
        origem = or.dataset.origem;
        root.querySelector("#cx-origem").innerHTML = filtroOrigem();
        await carregar(root);
        return;
      }
      const sol = e.target.closest("[data-sol]");
      const res = e.target.closest("[data-resolver]");
      try {
        if (sol) {
          await api(`/api/solicitacoes/${sol.dataset.sol}/status`, { method: "POST", body: { status: sol.dataset.acao } });
          toast(sol.dataset.acao === "resolvida" ? "Pedido resolvido" : "Atendimento iniciado");
        } else if (res) {
          await api(`/api/manifestacoes/${res.dataset.resolver}/resolver`, { method: "POST" });
          toast("Marcada como tratada");
        } else return;
        await carregar(root);
      } catch (err) { toast(err.message, true); }
    };
  },
  async atualizar(root) { await carregar(root, true); },
  sair() { graf = {}; },
};
