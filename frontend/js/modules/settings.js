// CONFIGURAÇÕES · estado da IA, modo demonstração, QR Codes das mesas e da equipe.
import { ICON, api, esc, fmt, modal, toast } from "../ui.js";

export default {
  async render(root) {
    const [sis, qr, mesas] = await Promise.all([api("/api/sistema"), api("/api/qrcode/info"), api("/api/mesas")]);
    const d = sis.demo;
    const mo = sis.media_por_origem;
    root.innerHTML = `
      <div class="grid g-2">
        <div class="card"><div class="card-head"><h3>Reconhecimento de alimentos</h3>
          <span class="badge ${sis.ia.ia_disponivel ? "ia" : "manual"}">${sis.ia.ia_disponivel ? esc(sis.ia.motor) : "Modo manual"}</span></div>
          <p class="muted" style="margin-top:0">${esc(sis.ia.mensagem)}</p>
          <div class="list">
            <div class="list-item"><span class="list-ico">${ICON.food}</span><div class="list-body"><div class="list-title">IA local (padrão, gratuita) · ${sis.ia.motores.local.disponivel ? "instalada" : "não instalada"}</div>
              <div class="list-meta">Roda neste computador, com segmentação. Para ativar: <b>pip install -r requirements-visao.txt</b> e reinicie o servidor. No 1º uso baixa o modelo (cerca de 700 MB, uma única vez).</div></div></div>
            <div class="list-item"><span class="list-ico">${ICON.sparkle}</span><div class="list-body"><div class="list-title">IA em nuvem (opcional, paga) · ${sis.ia.motores.claude.ia_disponivel ? "configurada" : "não configurada"}</div>
              <div class="list-meta">Usada só se a IA local não estiver instalada (ou com MOTOR_VISAO=claude no .env). Precisa de <b>pip install -r requirements-ia.txt</b> e da chave ANTHROPIC_API_KEY no arquivo .env, que nunca vai para o GitHub.</div></div></div>
          </div></div>
        <div class="card"><div class="card-head"><div><h3>Modo demonstração</h3><div class="card-sub">Dados fictícios para a apresentação, sempre separados dos reais</div></div></div>
          <p class="muted" style="margin-top:0">O banco tem <b>${fmt.n(sis.registros_demo)}</b> registros demonstrativos e <b>${fmt.n(sis.registros_reais)}</b> registros reais.
            Avaliações reais: ${fmt.n(mo.real.avaliacoes)} (média ${fmt.n(mo.real.media_geral, 2)}). Demonstrativas: ${fmt.n(mo.demo.avaliacoes)} (média ${fmt.n(mo.demo.media_geral, 2)}).</p>
          <form id="demo-form" class="row">
            <div class="field"><label for="dm-media">Nota média das avaliações fictícias</label><input class="input" id="dm-media" type="number" min="1" max="5" step="0.1" value="${d.media_alvo}" required></div>
            <div class="field"><label for="dm-n">Quantidade de avaliações</label><input class="input" id="dm-n" type="number" min="20" max="2000" step="10" value="${d.avaliacoes}" required></div>
            <div class="field"><label for="dm-dias">Dias de histórico</label><input class="input" id="dm-dias" type="number" min="7" max="90" value="${d.dias}" required></div>
          </form>
          <div class="row" style="margin-top:12px">
            <button class="btn btn-primary" data-a="recriar">${ICON.refresh}Gerar dados demonstrativos</button>
            <button class="btn btn-danger" data-a="remover" ${sis.registros_demo ? "" : "disabled"}>${ICON.trash}Remover dados demonstrativos</button>
          </div>
          <div class="hint" style="margin-top:8px">A nota escolhida vale só para as avaliações fictícias. As avaliações reais nunca são alteradas e a média exibida é sempre a média simples das notas gravadas. "Gerar" substitui apenas os dados demonstrativos (com backup do banco antes).</div></div>
      </div>
      <div class="card"><div class="card-head"><div><h3>QR Code da equipe</h3><div class="card-sub">Abre a página de login: ${esc(qr.equipe)}</div></div></div>
        <div class="qr-box"><img src="/api/qrcode/equipe.svg" alt="QR Code de acesso da equipe">
          <div class="small muted">Cole no balcão ou na área da equipe. Ler o QR Code <b>não dá acesso</b>: o colaborador precisa entrar com usuário e senha, e vê só as funções do seu perfil. Cadastre a equipe em <a href="#/equipe">Equipe e acessos</a>.</div></div></div>
      <div class="card"><div class="card-head"><div><h3>QR Codes das mesas</h3><div class="card-sub">Endereço: ${esc(qr.url_base)}/cliente/?mesa=N</div></div>
        <div class="actions"><button class="btn btn-sm btn-dark no-print" onclick="window.print()">${ICON.print}Imprimir</button></div></div>
        ${qr.rede_local ? `<div class="notice no-print" style="margin-bottom:14px">${ICON.info}<div>Os QR Codes apontam para o IP deste computador na rede local. O celular precisa estar no mesmo Wi-Fi. Se a rede bloquear o acesso, abra a página do cliente no próprio computador.</div></div>` : ""}
        <div class="print-qr">${mesas.mesas.map((m) => `<div class="q"><img src="/api/qrcode/${m.numero}.svg" alt="QR Code da mesa ${m.numero}" loading="lazy"><b>Mesa ${m.numero}</b><span class="small muted">Avalie e chame a equipe</span></div>`).join("")}</div></div>
      <div class="card no-print"><div class="card-head"><h3>Parâmetros</h3></div>
        <p class="muted" style="margin:0">Atualização automática das telas: a cada 5 segundos. Endereço dos QR Codes: defina URL_PUBLICA no .env para usar outro endereço. Cópias de segurança do banco ficam em data/backups/.</p></div>`;
    root.onclick = (e) => {
      const a = e.target.closest("[data-a]")?.dataset.a;
      if (!a) return;
      let corpo;
      if (a === "recriar") {
        const media = Number(root.querySelector("#dm-media").value);
        const n = Number(root.querySelector("#dm-n").value);
        const dias = Number(root.querySelector("#dm-dias").value);
        if (!(media >= 1 && media <= 5) || !(n >= 20 && n <= 2000) || !(dias >= 7 && dias <= 90)) {
          toast("Confira os valores: média de 1 a 5, de 20 a 2000 avaliações e de 7 a 90 dias.", true);
          return;
        }
        corpo = { media_alvo: media, avaliacoes: n, dias };
      }
      const texto = a === "recriar"
        ? `Os dados demonstrativos atuais serão trocados por ${corpo.avaliacoes} avaliações fictícias com média ${fmt.n(corpo.media_alvo, 1)}, em ${corpo.dias} dias. Os registros reais continuam como estão.`
        : "Isto apaga apenas os registros demonstrativos. Os registros reais continuam no banco.";
      const m = modal(`<h3>${a === "recriar" ? "Gerar dados demonstrativos?" : "Remover dados demonstrativos?"}</h3><p class="muted">${texto}</p>
        <div class="row" style="justify-content:flex-end"><button class="btn" data-close>Cancelar</button><button class="btn btn-primary" id="ok">Confirmar</button></div>`);
      m.querySelector("#ok").onclick = async () => {
        try {
          const r = await api(`/api/sistema/demo/${a}`, { method: "POST", body: corpo });
          m.remove();
          toast(a === "recriar" ? `Dados demonstrativos gerados: ${r.avaliacoes_demo} avaliações, média ${fmt.n(r.media_demo, 2)}` : "Dados demonstrativos removidos");
          this.render(root);
        } catch (err) { toast(err.message, true); }
      };
    };
  },
};
