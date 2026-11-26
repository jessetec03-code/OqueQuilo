// VISÃO GERAL · o dashboard central que cruza os dois pilares.
import { CORES, ICON, api, atividadeItem, chart, esc, fmt, kpi, vazio } from "../ui.js";

let graf = null;

function alertasHtml(alertas) {
  if (!alertas.length) {
    return `<div class="notice ok">${ICON.check}<div>Nenhum alerta no momento. Pedidos e reclamações dos clientes estão em dia.</div></div>`;
  }
  return alertas.map((a) => `<div class="alert-item ${a.nivel}">${ICON.alert}
      <span class="t">${esc(a.texto)}</span>
      <a class="btn btn-sm" href="#/experiencia-cliente">Ver</a></div>`).join("");
}

function reconhecimentoHtml(a, ia) {
  const m = a.metodos_reconhecimento || {};
  const porIa = (m.ia_local || 0) + (m.ia_claude || 0);
  const top = a.mais_servidos.slice(0, 6);
  const barras = top.length
    ? top.map((x) => `<div class="bar-row"><span>${esc(x.alimento)}</span><div class="bar-track"><div class="bar-fill" style="width:${(x.pratos / top[0].pratos) * 100}%;background:var(--accent)"></div></div><span class="num muted" style="text-align:right">${x.pratos}</span></div>`).join("")
    : vazio("Nenhum prato registrado ainda.");
  return `<div class="row" style="align-items:center;margin-bottom:12px;gap:8px">
      <span class="badge ${ia.ia_disponivel ? "ia" : "manual"}">${ia.ia_disponivel ? esc(ia.motor) : "Modo manual"}</span>
      <span class="small muted">${fmt.n(porIa)} de ${fmt.n(a.registros)} pratos com reconhecimento por IA</span></div>
    <div class="small muted" style="margin-bottom:6px;font-weight:600">Alimentos mais presentes nos pratos</div>${barras}`;
}

function kpisHtml(d) {
  const a = d.alimentar, c = d.cliente;
  return `
  <div class="grid g-4">
    ${kpi({ icon: "leaf", label: "Desperdício no prato", value: fmt.n(a.desperdicio_pct, 1), unit: "%", mod: "Alimentos",
      foot: `Sobra ÷ peso servido em ${fmt.n(a.pratos_com_retorno)} pratos com retorno` })}
    ${kpi({ icon: "food", label: "Pratos registrados hoje", value: fmt.n(a.registros_hoje), mod: "Alimentos",
      foot: `${fmt.n(a.registros)} no histórico · ${a.aguardando_retorno} aguardando retorno` })}
    ${kpi({ icon: "star", label: "Nota média dos clientes", value: fmt.n(c.media_geral, 1), unit: "/5", mod: "Cliente",
      foot: `${fmt.n(c.avaliacoes)} avaliações pelo QR Code` })}
    ${kpi({ icon: "hand", label: "Pedidos abertos", value: c.solicitacoes_pendentes + c.solicitacoes_em_atendimento, mod: "Cliente",
      foot: `Tempo médio de resposta: ${fmt.min(c.tempo_resposta_medio_min)}` })}
  </div>
  <div class="grid g-4">
    ${kpi({ icon: "scale", label: "Peso médio servido", value: fmt.n(a.peso_servido_medio_g, 0), unit: "g", mod: "Alimentos",
      foot: "Peso total do prato (a balança não pesa cada alimento)" })}
    ${kpi({ icon: "users", label: "Atendimento · Comida", value: `${fmt.n(c.media_atendimento, 1)} · ${fmt.n(c.media_comida, 1)}`, mod: "Cliente",
      foot: "Notas médias por aspecto" })}
    ${kpi({ icon: "msg", label: "Reclamações novas", value: c.reclamacoes_novas, mod: "Cliente",
      foot: `${c.reclamacoes} reclamações e ${c.sugestoes} sugestões no total` })}
    ${kpi({ icon: "check", label: "Pedidos resolvidos", value: fmt.n(c.solicitacoes_resolvidas), mod: "Cliente",
      foot: "Chamados pelo QR Code e já atendidos" })}
  </div>`;
}

function dadosGrafico(h) {
  return {
    labels: h.map((x) => `${x.hora}h`),
    datasets: [
      { type: "bar", label: "Pratos registrados", data: h.map((x) => x.pratos), backgroundColor: "rgba(18,20,23,.14)", borderRadius: 6, yAxisID: "y" },
      { type: "bar", label: "Pedidos de atendimento", data: h.map((x) => x.solicitacoes), backgroundColor: "rgba(59,130,246,.3)", borderRadius: 6, yAxisID: "y" },
      { type: "line", label: "Desperdício (%)", data: h.map((x) => x.desperdicio_pct), borderColor: CORES.accent, backgroundColor: CORES.accent, tension: .35, yAxisID: "y1" },
      { type: "line", label: "Nota média (×2)", data: h.map((x) => (x.nota_media ? x.nota_media * 2 : null)), borderColor: CORES.violet, backgroundColor: CORES.violet, borderDash: [5, 4], tension: .35, yAxisID: "y1" },
    ],
  };
}

function fill(root, d) {
  root.querySelector("#ov-alertas").innerHTML = alertasHtml(d.alertas);
  root.querySelector("#ov-alertas-n").textContent = d.alertas.length ? `${d.alertas.length} em aberto` : "";
  root.querySelector("#ov-kpis").innerHTML = kpisHtml(d);
  root.querySelector("#ov-rec").innerHTML = reconhecimentoHtml(d.alimentar, d.ia);
  root.querySelector("#ov-ativ").innerHTML = d.atividades.length ? d.atividades.map(atividadeItem).join("") : vazio("Nenhuma atividade registrada.");
  const o = d.origem_dos_dados;
  root.querySelector("#ov-origem").innerHTML = o.registros_demo
    ? `${ICON.info}<div><b>Origem dos dados:</b> ${fmt.n(o.registros_demo)} registros demonstrativos (fictícios, para a apresentação) e ${fmt.n(o.registros_reais)} registros feitos durante o uso. Pesos dos registros demonstrativos são simulados. Nenhum número vem da operação real da Bovinu'S.</div>`
    : `${ICON.info}<div><b>Origem dos dados:</b> ${fmt.n(o.registros_reais)} registros feitos durante o uso do sistema. Nenhum dado demonstrativo carregado.</div>`;
  root.querySelector("#ov-origem").className = o.registros_demo ? "notice" : "notice ok";
  if (graf) { graf.data = dadosGrafico(d.sinais_por_hora); graf.update("none"); }
}

export default {
  async render(root) {
    const d = await api("/api/dashboard");
    root.innerHTML = `
      <div class="card">
        <div class="card-head"><h3>Atenção agora</h3><span class="badge danger" id="ov-alertas-n"></span>
          <div class="actions"><span class="small muted">Pedidos de atendimento e reclamações enviados pelo QR Code</span></div></div>
        <div id="ov-alertas"></div>
      </div>
      <div id="ov-kpis" style="display:flex;flex-direction:column;gap:20px"></div>
      <div class="grid g-main">
        <div style="display:flex;flex-direction:column;gap:20px;min-width:0">
          <div class="card">
            <div class="card-head"><div><h3>Reconhecimento de alimentos</h3><div class="card-sub">O que aparece nos pratos fotografados</div></div>
              <div class="actions"><a class="btn btn-sm btn-dark" href="#/reconhecimento">${ICON.camera}Fotografar prato</a></div></div>
            <div id="ov-rec"></div>
          </div>
          <div class="card">
            <div class="card-head"><div><h3>Sinais integrados por horário</h3>
              <div class="card-sub">Os dois pilares no mesmo gráfico, últimos 7 dias, por hora do almoço</div></div></div>
            <div class="chart-box tall"><canvas id="ov-chart"></canvas></div>
            <div class="legend-note">Quando o desperdício e os pedidos de atendimento sobem juntos e a nota cai, o painel indica onde investigar (reposição do buffet no pico? equipe insuficiente?). Sinais simultâneos não comprovam causa.</div>
          </div>
        </div>
        <div class="card">
          <div class="card-head"><h3>Atividade recente</h3><div class="actions"><a class="btn btn-sm" href="#/relatorios">Histórico</a></div></div>
          <div class="list" id="ov-ativ"></div>
        </div>
      </div>
      <div class="notice" id="ov-origem"></div>`;
    graf = chart(root.querySelector("#ov-chart"), {
      type: "bar",
      data: dadosGrafico(d.sinais_por_hora),
      options: {
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { position: "bottom" } },
        scales: {
          y: { beginAtZero: true, title: { display: true, text: "Quantidade" }, grid: { color: "#F0F1F3" } },
          y1: { beginAtZero: true, position: "right", grid: { display: false }, title: { display: true, text: "% · nota×2" } },
          x: { grid: { display: false } },
        },
      },
    });
    fill(root, d);
  },
  async atualizar(root) {
    fill(root, await api("/api/dashboard"));
  },
  sair() { graf = null; },
};
