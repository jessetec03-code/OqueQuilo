// RELATÓRIOS · análise integrada dos dois pilares e exportação dos dados.
import { CORES, ICON, api, atividadeItem, chart, esc, fmt, vazio } from "../ui.js";

let dias = 7;
let modulo = "";

function tabela(horas) {
  return `<div class="table-wrap"><table class="table"><thead><tr><th>Horário</th><th>Pratos</th><th>Desperdício</th><th>Avaliações</th><th>Nota média</th><th>Reclamações</th><th>Pedidos de atendimento</th></tr></thead><tbody>
  ${horas.map((h) => `<tr><td><b>${h.hora}h–${h.hora + 1}h</b></td>
    <td class="num">${h.pratos}</td><td class="num">${fmt.pct(h.desperdicio_pct)}</td><td class="num">${h.avaliacoes}</td>
    <td class="num">${fmt.n(h.nota_media, 2)}</td><td class="num">${h.reclamacoes}</td><td class="num">${h.solicitacoes}</td></tr>`).join("")}</tbody></table></div>`;
}

function leitura(horas) {
  const validas = horas.filter((h) => h.pratos > 0 || h.avaliacoes > 0 || h.solicitacoes > 0);
  if (!validas.length) return vazio("Ainda não há dados suficientes para comparar horários.");
  const maior = (campo) => validas.filter((h) => h[campo] !== null).reduce((a, b) => (b[campo] > (a?.[campo] ?? -1) ? b : a), null);
  const pico = maior("pratos");
  const desp = maior("desperdicio_pct");
  const sol = maior("solicitacoes");
  const nota = validas.filter((h) => h.nota_media !== null).reduce((a, b) => (b.nota_media < (a?.nota_media ?? 99) ? b : a), null);
  const li = (t) => `<div class="list-item"><span class="list-ico mod-sistema">${ICON.chart}</span><div class="list-body">${t}</div></div>`;
  return `<div class="list">
    ${pico?.pratos ? li(`<b>Mais pratos registrados:</b> ${pico.hora}h–${pico.hora + 1}h, ${pico.pratos} pratos no período.`) : ""}
    ${desp ? li(`<b>Maior desperdício:</b> ${desp.hora}h–${desp.hora + 1}h, ${fmt.pct(desp.desperdicio_pct)} do peso servido.`) : ""}
    ${sol?.solicitacoes ? li(`<b>Mais pedidos de atendimento:</b> ${sol.hora}h–${sol.hora + 1}h, ${sol.solicitacoes} pedidos.`) : ""}
    ${nota ? li(`<b>Menor nota média:</b> ${nota.hora}h–${nota.hora + 1}h, ${fmt.n(nota.nota_media, 2)} de 5.`) : ""}
  </div><div class="legend-note">Leitura automática feita a partir dos números da tabela. Sinais no mesmo horário indicam onde investigar, mas não comprovam causa.</div>`;
}

async function carregar(root) {
  const [s, at] = await Promise.all([
    api(`/api/relatorios/sinais?dias=${dias}`),
    api(`/api/atividades?limite=60${modulo ? `&modulo=${modulo}` : ""}`),
  ]);
  root.querySelector("#rp-tab").innerHTML = tabela(s.horas);
  root.querySelector("#rp-leitura").innerHTML = leitura(s.horas);
  root.querySelector("#rp-ativ").innerHTML = at.atividades.length ? at.atividades.map(atividadeItem).join("") : vazio("Nenhuma atividade.");
  return s;
}

export default {
  async render(root) {
    const seg = (v, t) => `<button class="${dias === v ? "on" : ""}" data-dias="${v}">${t}</button>`;
    const segm = (v, t) => `<button class="${modulo === v ? "on" : ""}" data-mod="${v}">${t}</button>`;
    root.innerHTML = `
      <div class="card"><div class="card-head"><div><h3>Cenário operacional integrado por horário</h3><div class="card-sub">Reconhecimento de Alimentos + Experiência do Cliente</div></div>
        <div class="actions"><div class="seg" id="rp-dias">${seg(1, "Últimas 24 h")}${seg(7, "7 dias")}${seg(30, "30 dias")}</div>
        <button class="btn btn-sm no-print" onclick="window.print()">${ICON.print}Imprimir</button></div></div>
        <div class="chart-box tall"><canvas id="rp-c"></canvas></div>
        <div style="margin-top:14px" id="rp-tab"></div></div>
      <div class="grid g-2">
        <div class="card"><div class="card-head"><h3>Leitura dos sinais</h3></div><div id="rp-leitura"></div></div>
        <div class="card"><div class="card-head"><h3>Exportar dados (CSV para Excel)</h3></div>
          <div class="list">
            ${[["pratos", "Registros de pratos, alimentos e pesos", "food"],
              ["avaliacoes", "Avaliações dos clientes", "star"], ["manifestacoes", "Sugestões e reclamações", "msg"],
              ["solicitacoes", "Pedidos de atendimento", "hand"]].map(([k, t, i]) => `<div class="list-item"><span class="list-ico">${ICON[i]}</span>
              <div class="list-body"><div class="list-title">${t}</div><div class="list-meta">Inclui a coluna origem_dado (demo ou real)</div></div>
              <a class="btn btn-sm" href="/api/relatorios/exportar/${k}.csv">${ICON.download}Baixar</a></div>`).join("")}
          </div></div>
      </div>
      <div class="card"><div class="card-head"><h3>Histórico de atividades da plataforma</h3>
        <div class="actions"><div class="seg">${segm("", "Todas")}${segm("alimentar", "Alimentos")}${segm("cliente", "Cliente")}</div></div></div>
        <div class="list" id="rp-ativ"></div></div>`;
    const s = await carregar(root);
    const g = chart(root.querySelector("#rp-c"), {
      type: "bar",
      data: dadosGraf(s.horas),
      options: { interaction: { mode: "index", intersect: false }, plugins: { legend: { position: "bottom" } },
        scales: { y: { beginAtZero: true, grid: { color: "#F0F1F3" }, title: { display: true, text: "Quantidade" } },
          y1: { beginAtZero: true, position: "right", grid: { display: false }, title: { display: true, text: "%" } }, x: { grid: { display: false } } } },
    });
    root.onclick = async (e) => {
      const d = e.target.closest("[data-dias]");
      const m = e.target.closest("[data-mod]");
      if (d) { dias = Number(d.dataset.dias); root.querySelectorAll("[data-dias]").forEach((b) => b.classList.toggle("on", b === d)); }
      else if (m) { modulo = m.dataset.mod; root.querySelectorAll("[data-mod]").forEach((b) => b.classList.toggle("on", b === m)); }
      else return;
      const novo = await carregar(root);
      g.data = dadosGraf(novo.horas);
      g.update();
    };
  },
};

function dadosGraf(h) {
  return {
    labels: h.map((x) => `${x.hora}h`),
    datasets: [
      { type: "bar", label: "Pratos registrados", data: h.map((x) => x.pratos), backgroundColor: "rgba(18,20,23,.14)", borderRadius: 6, yAxisID: "y" },
      { type: "bar", label: "Pedidos de atendimento", data: h.map((x) => x.solicitacoes), backgroundColor: "rgba(59,130,246,.3)", borderRadius: 6, yAxisID: "y" },
      { type: "bar", label: "Reclamações", data: h.map((x) => x.reclamacoes), backgroundColor: "rgba(139,92,246,.45)", borderRadius: 6, yAxisID: "y" },
      { type: "line", label: "Desperdício (%)", data: h.map((x) => x.desperdicio_pct), borderColor: CORES.accent, backgroundColor: CORES.accent, tension: .35, yAxisID: "y1" },
    ],
  };
}
