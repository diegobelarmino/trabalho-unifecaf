const estado = { view: "painel", status: "", busca: "", caixas: "fechada", pecas: [], caixasDados: [] };
let accessToken = null;
let renovando = null;

const titulos = {
  painel: ["Operação", "Painel da linha"],
  pecas: ["Consulta", "Peças aprovadas e reprovadas"],
  caixas: ["Armazenamento", "Caixas da linha"],
  relatorio: ["Consolidado", "Relatório final"],
  codigo: ["Código", "Como funciona"],
};

const $ = (sel) => document.querySelector(sel);
const esc = (valor) => String(valor ?? "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));

function toast(texto) {
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = texto;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), 4200);
}

function abrir(id) { $(id).classList.remove("oculto"); }
function fecharModais() { document.querySelectorAll(".modal").forEach((m) => m.classList.add("oculto")); }

function mostrarApp(usuario) {
  $("#tela-login").classList.add("oculto");
  $("#aplicacao").classList.remove("oculto");
  if (usuario) {
    $("#usuario-nome").textContent = usuario.nome;
    $("#usuario-email").textContent = usuario.email;
    const partes = String(usuario.nome || "OP").trim().split(/\s+/).slice(0, 2);
    $("#usuario-iniciais").textContent = partes.map((p) => p[0]).join("").toUpperCase();
  }
}

function mostrarLogin() {
  accessToken = null;
  $("#aplicacao").classList.add("oculto");
  $("#tela-login").classList.remove("oculto");
}

async function renovarSessao() {
  if (!renovando) {
    renovando = fetch("/api/auth/refresh", { method: "POST", credentials: "include" })
      .then(async (resposta) => {
        if (!resposta.ok) return null;
        return resposta.json();
      })
      .then((dados) => {
        accessToken = dados?.accessToken || null;
        if (dados?.user) mostrarApp(dados.user);
        return Boolean(accessToken);
      })
      .finally(() => { renovando = null; });
  }
  return renovando;
}

async function api(url, opcoes = {}, repetir = true) {
  const headers = { "Content-Type": "application/json", ...(opcoes.headers || {}) };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const resposta = await fetch(url, { ...opcoes, headers, credentials: "include" });
  if (resposta.status === 401 && repetir && !url.includes("/api/auth/")) {
    const renovou = await renovarSessao();
    if (renovou) return api(url, opcoes, false);
    mostrarLogin();
    throw new Error("Sessão expirada. Entre novamente.");
  }
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(dados.erro || dados.error || "Não foi possível concluir a operação.");
  return dados;
}

function irPara(view) {
  estado.view = view;
  document.querySelectorAll(".view").forEach((secao) => secao.classList.add("oculto"));
  $(`#view-${view}`).classList.remove("oculto");
  document.querySelectorAll(".nav[data-view]").forEach((botao) => {
    botao.classList.toggle("ativo", botao.dataset.view === view);
  });
  const [kicker, titulo] = titulos[view];
  $("#view-kicker").textContent = kicker;
  $("#view-title").textContent = titulo;
  $("#kpis").classList.toggle("oculto", view === "codigo");
  if (view === "pecas") carregarPecas();
  if (view === "caixas") carregarCaixas();
  if (view === "relatorio") carregarRelatorio();
}

function desenharSlots(ocupacao) {
  const slots = Array.from({ length: 10 }, (_, i) => `<i class="slot${i < ocupacao ? " cheio" : ""}"></i>`).join("");
  $("#rail-slots").innerHTML = slots;
  $("#rail-ocupacao").textContent = ocupacao ? `${ocupacao}/10` : "Aguardando peça";
}

async function carregarResumo() {
  const dados = await api("/api/resumo");
  const aberta = dados.caixa_aberta;
  desenharSlots(aberta ? aberta.ocupacao : 0);
  if (!aberta) $("#rail-ocupacao").textContent = "Nenhuma caixa aberta";
  $("#kpis").innerHTML = [
    ["Peças", dados.total_pecas, ""],
    ["Aprovadas", dados.aprovadas, "ok"],
    ["Reprovadas", dados.reprovadas, "bad"],
    ["Caixas usadas", dados.caixas_utilizadas, "info"],
  ].map(([rotulo, valor, classe]) => `<article class="kpi ${classe}"><span>${rotulo}</span><strong>${valor}</strong></article>`).join("");
  return dados;
}

function tagStatus(status) {
  const classe = status === "aprovada" ? "ok" : "bad";
  const texto = status === "aprovada" ? "Aprovada" : "Reprovada";
  return `<span class="tag ${classe}">${texto}</span>`;
}

async function carregarPecas() {
  const params = new URLSearchParams();
  if (estado.status) params.set("status", estado.status);
  if (estado.busca) params.set("busca", estado.busca);
  estado.pecas = await api(`/api/pecas?${params.toString()}`);
  const corpo = $("#corpo-pecas");
  corpo.innerHTML = estado.pecas.map((peca) => `
    <tr>
      <td><strong>${esc(peca.id)}</strong></td>
      <td>${Number(peca.peso).toFixed(2)} g</td>
      <td>${esc(peca.cor)}</td>
      <td>${Number(peca.comprimento).toFixed(2)} cm</td>
      <td>${tagStatus(peca.status)}</td>
      <td>${peca.caixa_numero ? `Caixa ${peca.caixa_numero}` : "—"}</td>
      <td class="acoes">
        <button type="button" class="btn texto" data-detalhe="${esc(peca.id)}">Detalhe</button>
        <button type="button" class="btn texto" data-excluir="${esc(peca.id)}">Remover</button>
      </td>
    </tr>
  `).join("");
  $("#vazio-pecas").classList.toggle("oculto", estado.pecas.length > 0);
  if (estado.view === "painel") {
    const recentes = await api("/api/pecas");
    $("#recentes").innerHTML = recentes.slice(0, 5).map((peca) => `
      <div class="linha">
        <span><strong>${esc(peca.id)}</strong> · ${esc(peca.cor)}</span>
        ${tagStatus(peca.status)}
      </div>
    `).join("") || "<p class='nota'>Nenhuma peça cadastrada.</p>";
  }
}

function renderCaixas(lista) {
  $("#lista-caixas").innerHTML = lista.map((caixa) => `
    <article class="caixa">
      <header>
        <h3>Caixa ${caixa.numero}</h3>
        <span class="tag ${caixa.status}">${caixa.status}</span>
      </header>
      <div class="barra"><span style="width:${(caixa.ocupacao / caixa.capacidade) * 100}%"></span></div>
      <strong>${caixa.ocupacao}/${caixa.capacidade} peças</strong>
      <button type="button" class="btn ghost" data-caixa="${caixa.id}">Gerenciar</button>
    </article>
  `).join("");
  $("#vazio-caixas").classList.toggle("oculto", lista.length > 0);
  const vazio = $("#vazio-caixas");
  vazio.textContent = estado.caixas === "fechada"
    ? "Nenhuma caixa fechada ainda. A caixa fecha ao receber a 10ª peça aprovada."
    : "Nenhuma caixa registrada.";
}

async function carregarCaixas() {
  estado.caixasDados = await api("/api/caixas");
  const lista = estado.caixas === "fechada"
    ? estado.caixasDados.filter((caixa) => caixa.status === "fechada")
    : estado.caixasDados;
  renderCaixas(lista);
}

async function carregarRelatorio() {
  const dados = await api("/api/relatorio");
  const aberta = dados.caixa_aberta
    ? `Caixa ${dados.caixa_aberta.numero} com ${dados.caixa_aberta.ocupacao}/${dados.caixa_aberta.capacidade}`
    : "Nenhuma caixa em enchimento";
  const motivos = dados.motivos.length
    ? dados.motivos.map((m) => `<div class="motivo"><span>${esc(m.rotulo)}</span><strong>${m.quantidade}</strong></div>`).join("")
    : "<p class='nota'>Nenhuma reprovação registrada.</p>";
  const detalhe = dados.reprovadas_detalhe.map((peca) => {
    const lista = (peca.motivos || []).map((m) => m.criterio).join(", ");
    return `<div class="motivo"><strong>${esc(peca.id)}</strong><span>${esc(lista)}</span></div>`;
  }).join("") || "<p class='nota'>Sem peças reprovadas.</p>";

  const caixas = (dados.caixas || []).map((caixa) => `
    <span class="chip">Caixa ${caixa.numero} · ${esc(caixa.status)} · ${caixa.ocupacao}/${caixa.capacidade}</span>
  `).join("") || "<span class='nota'>Nenhuma caixa.</span>";
  const hoje = new Date().toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });

  $("#relatorio").innerHTML = `
    <div class="folha">
      <p class="folha-data">Emitido em ${esc(hoje)} · ${esc(aberta)}</p>
      <div class="kpis kpis-mini">
        <article class="kpi ok"><span>Aprovadas</span><strong>${dados.aprovadas}</strong></article>
        <article class="kpi bad"><span>Reprovadas</span><strong>${dados.reprovadas}</strong></article>
        <article class="kpi"><span>Caixas fechadas</span><strong>${dados.caixas_fechadas}</strong></article>
        <article class="kpi info"><span>Caixas usadas</span><strong>${dados.caixas_utilizadas}</strong></article>
      </div>
      <div class="relatorio-grade">
        <article class="relatorio-bloco">
          <h2>Motivos da reprovação</h2>
          <div class="motivos">${motivos}</div>
        </article>
        <article class="relatorio-bloco">
          <h2>Peças reprovadas</h2>
          ${detalhe}
        </article>
      </div>
      <article class="relatorio-bloco">
        <h2>Caixas</h2>
        <div class="chips">${caixas}</div>
      </article>
      <button type="button" class="btn ghost" id="btn-imprimir">Imprimir relatório</button>
    </div>
  `;
}

function abrirDetalhe(id) {
  const peca = estado.pecas.find((item) => item.id === id);
  if (!peca) return;
  const motivos = (peca.motivos || []).map((m) => `<li>${esc(m.descricao)}</li>`).join("");
  $("#titulo-detalhe").textContent = `Peça ${peca.id}`;
  $("#corpo-detalhe").innerHTML = `
    <p>${tagStatus(peca.status)} ${peca.caixa_numero ? `<span class="tag ${peca.caixa_status}">Caixa ${peca.caixa_numero}</span>` : ""}</p>
    <p>Peso ${Number(peca.peso).toFixed(2)} g · Cor ${esc(peca.cor)} · Comprimento ${Number(peca.comprimento).toFixed(2)} cm</p>
    ${motivos ? `<ul class="lista-motivos">${motivos}</ul>` : "<p class='nota'>Dentro de todos os critérios. Peça armazenada.</p>"}
  `;
  abrir("#modal-detalhe");
}

function formularioCaixa(caixa) {
  if (caixa.ocupacao >= caixa.capacidade) {
    return "<p class='nota'>Caixa cheia. Tire uma peça para incluir outra.</p>";
  }
  return `
    <form id="form-na-caixa" class="bloco-caixa" data-caixa-id="${caixa.id}">
      <h3>Adicionar peça</h3>
      <div class="campos">
        <label>Identificador<input name="id" required maxlength="40" placeholder="QL-020" autocomplete="off"></label>
        <label>Peso (g)<input name="peso" type="number" required min="0.01" step="0.01" placeholder="100"></label>
        <label>Cor
          <select name="cor" required>
            <option value="azul">Azul</option>
            <option value="verde">Verde</option>
            <option value="vermelha">Vermelha</option>
            <option value="amarela">Amarela</option>
            <option value="preta">Preta</option>
            <option value="branca">Branca</option>
          </select>
        </label>
        <label>Comprimento (cm)<input name="comprimento" type="number" required min="0.01" step="0.01" placeholder="15"></label>
      </div>
      <p class="dica">Só entra na caixa se for aprovada e ainda houver vaga.</p>
      <button type="submit" class="btn primary">Incluir na caixa</button>
    </form>
  `;
}

function desenharCaixa(caixa) {
  $("#titulo-caixa").textContent = `Caixa ${caixa.numero}`;
  const linhas = caixa.pecas.map((peca) => `
    <div class="linha">
      <strong>${esc(peca.id)}</strong>
      <span>${esc(peca.cor)} · ${Number(peca.peso).toFixed(1)} g · ${Number(peca.comprimento).toFixed(1)} cm</span>
      <button type="button" class="btn texto" data-tirar="${esc(peca.id)}" data-da-caixa="${caixa.id}">Tirar</button>
    </div>
  `).join("") || "<p class='nota'>Caixa sem peças.</p>";
  $("#corpo-caixa").innerHTML = `
    <p><span class="tag ${caixa.status}">${caixa.status}</span> ${caixa.ocupacao}/${caixa.capacidade}</p>
    <div class="lista-caixa">${linhas}</div>
    ${formularioCaixa(caixa)}
  `;
}

async function abrirCaixa(id) {
  if (!estado.caixasDados.length) estado.caixasDados = await api("/api/caixas");
  const caixa = estado.caixasDados.find((item) => String(item.id) === String(id));
  if (!caixa) return;
  desenharCaixa(caixa);
  abrir("#modal-caixa");
}

async function atualizarCaixaAberta(id) {
  estado.caixasDados = await api("/api/caixas");
  const caixa = estado.caixasDados.find((item) => String(item.id) === String(id));
  if (caixa) desenharCaixa(caixa);
  if (estado.view === "caixas") {
    const lista = estado.caixas === "fechada"
      ? estado.caixasDados.filter((item) => item.status === "fechada")
      : estado.caixasDados;
    renderCaixas(lista);
  }
  await carregarResumo();
}

async function abrirRemover(idPrevio) {
  const pecas = await api("/api/pecas");
  const select = $("#select-remover");
  select.innerHTML = pecas.map((peca) => `<option value="${esc(peca.id)}">${esc(peca.id)} · ${peca.status}</option>`).join("");
  if (!pecas.length) {
    toast("Não há peças cadastradas para remover.");
    return;
  }
  if (idPrevio) select.value = idPrevio;
  abrir("#modal-remover");
}

async function atualizarTudo() {
  await carregarResumo();
  if (estado.view === "painel" || estado.view === "pecas") await carregarPecas();
  if (estado.view === "caixas") await carregarCaixas();
  if (estado.view === "relatorio") await carregarRelatorio();
  if (estado.view === "painel") await carregarPecas();
}

document.querySelectorAll(".nav").forEach((botao) => {
  botao.addEventListener("click", () => {
    if (botao.dataset.view) irPara(botao.dataset.view);
    if (botao.dataset.acao === "cadastrar") abrir("#modal-cadastro");
    if (botao.dataset.acao === "remover") abrirRemover();
  });
});

$("#btn-nova").addEventListener("click", () => abrir("#modal-cadastro"));
$("#btn-demo").addEventListener("click", () => abrir("#modal-demo"));
document.querySelectorAll("[data-fechar]").forEach((botao) => botao.addEventListener("click", fecharModais));
document.querySelectorAll(".modal").forEach((modal) => {
  modal.addEventListener("click", (evento) => { if (evento.target === modal) fecharModais(); });
});
document.addEventListener("keydown", (evento) => { if (evento.key === "Escape") fecharModais(); });

$("#form-peca").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const dados = Object.fromEntries(new FormData(evento.target).entries());
  try {
    const resposta = await api("/api/pecas", { method: "POST", body: JSON.stringify(dados) });
    evento.target.reset();
    fecharModais();
    toast(resposta.mensagem);
    irPara(resposta.peca.status === "reprovada" ? "pecas" : "painel");
    if (resposta.peca.status === "reprovada") {
      document.querySelector('.tab[data-status="reprovada"]').click();
    }
    await atualizarTudo();
    if (resposta.peca.status === "reprovada") abrirDetalhe(resposta.peca.id);
  } catch (erro) {
    toast(erro.message);
  }
});

$("#form-remover").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const id = new FormData(evento.target).get("id");
  try {
    const resposta = await api(`/api/pecas/${encodeURIComponent(id)}`, { method: "DELETE" });
    fecharModais();
    toast(resposta.mensagem);
    await atualizarTudo();
  } catch (erro) {
    toast(erro.message);
  }
});

$("#confirmar-demo").addEventListener("click", async () => {
  try {
    const resposta = await api("/api/demonstracao", { method: "POST", body: "{}" });
    fecharModais();
    toast(resposta.mensagem);
    await atualizarTudo();
  } catch (erro) {
    toast(erro.message);
  }
});

document.querySelectorAll(".tab[data-status]").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab[data-status]").forEach((item) => item.classList.remove("ativo"));
    tab.classList.add("ativo");
    estado.status = tab.dataset.status;
    carregarPecas();
  });
});

document.querySelectorAll(".tab[data-caixa]").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab[data-caixa]").forEach((item) => item.classList.remove("ativo"));
    tab.classList.add("ativo");
    estado.caixas = tab.dataset.caixa;
    carregarCaixas();
  });
});

let buscaTimer;
$("#busca").addEventListener("input", (evento) => {
  clearTimeout(buscaTimer);
  buscaTimer = setTimeout(() => {
    estado.busca = evento.target.value;
    if (estado.view !== "pecas" && estado.busca) irPara("pecas");
    else carregarPecas();
  }, 200);
});

document.body.addEventListener("click", async (evento) => {
  const detalhe = evento.target.closest("[data-detalhe]");
  const excluir = evento.target.closest("[data-excluir]");
  const tirar = evento.target.closest("[data-tirar]");
  const caixa = evento.target.closest("[data-caixa]");
  if (detalhe) abrirDetalhe(detalhe.dataset.detalhe);
  if (excluir) abrirRemover(excluir.dataset.excluir);
  if (tirar) {
    try {
      const resposta = await api(
        `/api/caixas/${encodeURIComponent(tirar.dataset.daCaixa)}/pecas/${encodeURIComponent(tirar.dataset.tirar)}`,
        { method: "DELETE" },
      );
      toast(resposta.mensagem);
      await atualizarCaixaAberta(tirar.dataset.daCaixa);
    } catch (erro) {
      toast(erro.message);
    }
  }
  if (caixa) abrirCaixa(caixa.dataset.caixa);
});

document.body.addEventListener("submit", async (evento) => {
  const form = evento.target.closest("#form-na-caixa");
  if (!form) return;
  evento.preventDefault();
  const dados = Object.fromEntries(new FormData(form).entries());
  try {
    const resposta = await api(`/api/caixas/${encodeURIComponent(form.dataset.caixaId)}/pecas`, {
      method: "POST",
      body: JSON.stringify(dados),
    });
    toast(resposta.mensagem);
    await atualizarCaixaAberta(form.dataset.caixaId);
  } catch (erro) {
    toast(erro.message);
  }
});

document.body.addEventListener("click", (evento) => {
  if (evento.target.id === "btn-imprimir") window.print();
});

$("#form-login").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  $("#login-erro").textContent = "";
  const dados = Object.fromEntries(new FormData(evento.target).entries());
  try {
    const resposta = await fetch("/api/auth/login", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dados),
    });
    const corpo = await resposta.json();
    if (!resposta.ok) {
      $("#login-erro").textContent = corpo.erro || "Não foi possível entrar.";
      return;
    }
    accessToken = corpo.accessToken;
    evento.target.reset();
    mostrarApp(corpo.user);
    await atualizarTudo();
  } catch (erro) {
    $("#login-erro").textContent = "Falha de conexão com o servidor.";
  }
});

function fecharConta() {
  $("#conta-menu").classList.add("oculto");
  $("#btn-conta").setAttribute("aria-expanded", "false");
}

$("#btn-conta").addEventListener("click", (evento) => {
  evento.stopPropagation();
  const aberto = $("#conta-menu").classList.toggle("oculto") === false;
  $("#btn-conta").setAttribute("aria-expanded", aberto ? "true" : "false");
});
document.addEventListener("click", (evento) => {
  if (!$("#menu-conta").contains(evento.target)) fecharConta();
});
document.addEventListener("keydown", (evento) => {
  if (evento.key === "Escape") fecharConta();
});

$("#btn-sair").addEventListener("click", async () => {
  try {
    await api("/api/auth/logout", { method: "POST" });
  } catch (_erro) {
    /* encerra a tela mesmo se o token já expirou */
  }
  mostrarLogin();
});

$("#btn-senha").addEventListener("click", () => abrir("#modal-senha"));
$("#form-senha").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const dados = Object.fromEntries(new FormData(evento.target).entries());
  try {
    const resposta = await api("/api/auth/senha", { method: "POST", body: JSON.stringify(dados) });
    evento.target.reset();
    fecharModais();
    toast(resposta.message);
    mostrarLogin();
  } catch (erro) {
    toast(erro.message);
  }
});

renovarSessao()
  .then((ativa) => (ativa ? atualizarTudo() : mostrarLogin()))
  .catch(() => mostrarLogin());
