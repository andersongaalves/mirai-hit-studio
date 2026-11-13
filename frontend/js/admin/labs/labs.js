// Admin > Mirai Hit Labs: the plugin catalog sold on labs.miraihitstudio.com.br.
// Each plugin has a page (text, price, cover), one installer per system (a .zip sent in
// the background or a link) and the licenses sold or given away.
import { authFetch } from "../auth.js";
import * as Notify from "../../utils/notifications.js";
import { confirmarAcao } from "../../modules/confirm_dialog.js";
import { enqueueUpload } from "../../modules/upload_tasks.js";
import { cropImage } from "../../modules/image_cropper.js";

const SISTEMAS = { windows: "Windows", macos: "macOS" };
const FORMATOS = ["VST3", "AU", "AAX", "CLAP", "Standalone"];
const STATUS = { rascunho: "Rascunho", publicado: "Publicado", arquivado: "Arquivado" };
const LABS_URL = "https://labs.miraihitstudio.com.br";
let plugins = [];

function el(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

async function api(path, options = {}) {
    const response = await authFetch(path, options);
    const data = await response.json().catch(() => null);
    if (!response.ok) {
        const detail = data?.detail;
        throw new Error(typeof detail === "string" ? detail : Array.isArray(detail) ? "Revise os campos destacados." : "Não foi possível salvar.");
    }
    return data;
}

const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const money = value => Number(value || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const size = bytes => (bytes ? `${(bytes / 1024 / 1024).toFixed(1).replace(".", ",")} MB` : "");

export function slugify(text) {
    return String(text || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase()
        .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60);
}

function field(label, input, help = "", full = false) {
    const wrap = el("label", `labs-admin__field${full ? " labs-admin__field--full" : ""}`);
    wrap.append(el("span", "", label), input);
    if (help) wrap.append(el("small", "", help));
    return wrap;
}

function input(name, value, attrs = {}) {
    const node = el(attrs.multiline ? "textarea" : attrs.select ? "select" : "input");
    node.name = name;
    if (attrs.select) {
        Object.entries(attrs.select).forEach(([key, label]) => {
            const option = el("option", "", label);
            option.value = key;
            node.append(option);
        });
    }
    Object.entries(attrs).forEach(([key, val]) => { if (!["multiline", "select"].includes(key)) node[key] = val; });
    node.value = value ?? "";
    return node;
}

function chip(text, kind) {
    return el("span", `labs-admin__chip labs-admin__chip--${kind}`, text);
}

// ---------------------------------------------------------------- list

function card(plugin) {
    const item = el("article", "labs-admin__card");
    const cover = el("div", "labs-admin__cover");
    if (plugin.capa_url) {
        const image = el("img");
        image.src = plugin.capa_url;
        image.alt = "";
        image.loading = "lazy";
        cover.append(image);
    } else {
        cover.append(el("span", "", "Sem capa"));
    }
    const body = el("div", "labs-admin__card-body");
    const head = el("div", "labs-admin__card-head");
    head.append(el("h3", "", plugin.nome), chip(STATUS[plugin.status] || plugin.status, plugin.status));
    const price = plugin.gratuito ? "Grátis" : plugin.em_promocao
        ? `${money(plugin.preco_vigente)} (de ${money(plugin.preco)})` : money(plugin.preco_vigente);
    const facts = el("p", "labs-admin__facts",
        [price, plugin.versao && `v${plugin.versao}`, plugin.formatos.join(" · ")].filter(Boolean).join(" · "));
    const installers = el("p", "labs-admin__installers");
    Object.entries(SISTEMAS).forEach(([key, label]) => {
        const ready = plugin.instaladores.some(row => row.sistema === key);
        installers.append(chip(`${label}${ready ? "" : " pendente"}`, ready ? "ok" : "missing"));
    });
    const licenses = el("p", "labs-admin__facts",
        `${plugin.licencas.ativas} licença${plugin.licencas.ativas === 1 ? "" : "s"} ativa${plugin.licencas.ativas === 1 ? "" : "s"}`
        + (plugin.licencas.reservadas ? ` · ${plugin.licencas.reservadas} aguardando pagamento` : ""));
    const actions = el("div", "labs-admin__actions");
    const edit = el("button", "btn-small", "Editar");
    edit.type = "button";
    edit.addEventListener("click", () => openEditor(plugin));
    const sold = el("button", "btn-small", "Licenças");
    sold.type = "button";
    sold.addEventListener("click", () => openLicenses(plugin));
    actions.append(edit, sold);
    if (plugin.status === "publicado") {
        const view = el("a", "btn-small", "Ver na loja");
        view.href = `${LABS_URL}/plugins/${plugin.slug}`;
        view.target = "_blank";
        view.rel = "noopener";
        actions.append(view);
    }
    body.append(head, facts, installers, licenses, actions);
    item.append(cover, body);
    return item;
}

function renderList() {
    const root = document.getElementById("labs-admin-list");
    if (!root) return;
    if (!plugins.length) {
        const empty = el("div", "labs-admin__empty");
        empty.append(el("strong", "", "Nenhum plugin ainda."),
            el("p", "", "Cadastre o primeiro: texto e preço, depois capa e instaladores. Ele só aparece na loja quando você publicar."));
        root.replaceChildren(empty);
        return;
    }
    root.replaceChildren(...plugins.map(card));
}

// ---------------------------------------------------------------- editor

function panel(titleText) {
    const root = document.getElementById("labs-admin-panel");
    const box = el("section", "admin-card labs-admin__panel");
    box.setAttribute("aria-labelledby", "labs-admin-panel-title");
    const head = el("div", "labs-admin__panel-head");
    const title = el("h2", "", titleText);
    title.id = "labs-admin-panel-title";
    const close = el("button", "btn-small", "Fechar");
    close.type = "button";
    close.addEventListener("click", () => { root.replaceChildren(); root.hidden = true; });
    head.append(title, close);
    box.append(head);
    root.replaceChildren(box);
    root.hidden = false;
    box.scrollIntoView({ behavior: "smooth", block: "start" });
    title.tabIndex = -1;
    title.focus({ preventScroll: true });
    return box;
}

function payloadFrom(form) {
    const data = new FormData(form);
    const text = name => String(data.get(name) || "").trim();
    return {
        nome: text("nome"),
        slug: text("slug"),
        tagline: text("tagline") || null,
        descricao: text("descricao") || null,
        categoria: text("categoria") || null,
        versao: text("versao") || null,
        formatos: data.getAll("formatos").map(String),
        recursos: text("recursos").split("\n").map(item => item.trim()).filter(Boolean),
        requisitos: text("requisitos") || null,
        tagline_en: text("tagline_en") || null,
        descricao_en: text("descricao_en") || null,
        categoria_en: text("categoria_en") || null,
        recursos_en: text("recursos_en").split("\n").map(item => item.trim()).filter(Boolean),
        requisitos_en: text("requisitos_en") || null,
        preco: text("preco") || "0",
        preco_promocional: text("preco_promocional") || null,
        video_url: text("video_url") || null,
        status: text("status") || "rascunho",
        destaque: data.get("destaque") === "on",
        ordem: Number(text("ordem") || 0),
    };
}

function openEditor(plugin = null) {
    const box = panel(plugin ? `Editar ${plugin.nome}` : "Novo plugin");
    const form = el("form", "labs-admin__form");
    const grid = el("div", "labs-admin__grid");
    const nome = input("nome", plugin?.nome, { required: true, maxLength: 80, placeholder: "Ex.: Mirai Saturator" });
    const slug = input("slug", plugin?.slug, { required: true, maxLength: 60, pattern: "[a-z0-9](?:[a-z0-9\\-]{0,58}[a-z0-9])?", autocapitalize: "none", spellcheck: false });
    const url = el("small", "labs-admin__url", `${LABS_URL}/plugins/${plugin?.slug || "..."}`);
    let slugTouched = Boolean(plugin);
    nome.addEventListener("input", () => { if (!slugTouched) slug.value = slugify(nome.value); url.textContent = `${LABS_URL}/plugins/${slug.value || "..."}`; });
    slug.addEventListener("input", () => { slugTouched = true; slug.value = slugify(slug.value); url.textContent = `${LABS_URL}/plugins/${slug.value || "..."}`; });
    const slugField = field("Endereço", slug);
    slugField.append(url);
    const formatos = el("fieldset", "labs-admin__formats labs-admin__field--full");
    formatos.append(el("legend", "", "Formatos"));
    FORMATOS.forEach(name => {
        const option = el("label", "labs-admin__check");
        const box = input("formatos", name, { type: "checkbox" });
        box.checked = plugin?.formatos?.includes(name) || false;
        option.append(box, el("span", "", name));
        formatos.append(option);
    });
    const destaque = input("destaque", "on", { type: "checkbox" });
    destaque.checked = Boolean(plugin?.destaque);
    const destaqueField = el("label", "labs-admin__check labs-admin__check--inline");
    destaqueField.append(destaque, el("span", "", "Destaque na loja (aparece primeiro)"));
    // Textos em inglês: a loja abre em inglês; campo vazio mostra o texto em português.
    const en = plugin?.en || {};
    const english = el("fieldset", "labs-admin__english labs-admin__field--full");
    english.append(
        el("legend", "", "Inglês (idioma padrão da loja)"),
        el("p", "labs-admin__hint", "A loja abre em inglês. Campo vazio mostra o texto em português."),
        field("Frase curta (EN)", input("tagline_en", en.tagline, { maxLength: 160, placeholder: "Ex.: Analog saturation in one knob" }), "", true),
        field("Categoria (EN)", input("categoria_en", en.categoria, { maxLength: 40, placeholder: "Ex.: Saturation" })),
        field("Descrição (EN)", input("descricao_en", en.descricao, { multiline: true, rows: 6, maxLength: 8000 }), "", true),
        field("Recursos (EN, um por linha)", input("recursos_en", (en.recursos || []).join("\n"), { multiline: true, rows: 4 }), "Até 12 itens curtos.", true),
        field("Requisitos (EN)", input("requisitos_en", en.requisitos, { multiline: true, rows: 3, maxLength: 2000, placeholder: "Windows 10+ (64-bit) or macOS 12+; DAW with VST3/AU" }), "", true),
    );
    grid.append(
        field("Nome", nome), slugField,
        field("Frase curta", input("tagline", plugin?.tagline, { maxLength: 160, placeholder: "Ex.: Saturação analógica em um botão" }), "", true),
        field("Categoria", input("categoria", plugin?.categoria, { maxLength: 40, placeholder: "Ex.: Saturação" })),
        field("Versão", input("versao", plugin?.versao, { maxLength: 20, placeholder: "1.0.0" })),
        field("Preço (R$)", input("preco", plugin?.preco ?? "0", { type: "number", min: "0", step: "0.01", required: true }), "0 = grátis: a licença sai na hora, sem checkout."),
        field("Preço promocional (R$)", input("preco_promocional", plugin?.preco_promocional ?? "", { type: "number", min: "0", step: "0.01" }), "Opcional; menor que o preço."),
        formatos,
        field("Descrição", input("descricao", plugin?.descricao, { multiline: true, rows: 6, maxLength: 8000 }), "", true),
        field("Recursos (um por linha)", input("recursos", (plugin?.recursos || []).join("\n"), { multiline: true, rows: 4 }), "Até 12 itens curtos.", true),
        field("Requisitos", input("requisitos", plugin?.requisitos, { multiline: true, rows: 3, maxLength: 2000, placeholder: "Windows 10+ (64 bits) ou macOS 12+; DAW com VST3/AU" }), "", true),
        english,
        field("Vídeo (link https)", input("video_url", plugin?.video_url, { type: "url", maxLength: 300, placeholder: "https://www.youtube.com/watch?v=..." })),
        field("Ordem", input("ordem", plugin?.ordem ?? 0, { type: "number", min: "0", max: "9999", step: "1" })),
        field("Situação", input("status", plugin?.status || "rascunho", { select: STATUS }), "Publicar exige capa e pelo menos um instalador."),
        destaqueField,
    );
    const footer = el("div", "labs-admin__footer");
    const status = el("p", "labs-admin__status");
    status.setAttribute("role", "status");
    const save = el("button", "btn-cta", plugin ? "Salvar" : "Criar plugin");
    save.type = "submit";
    footer.append(status, save);
    form.append(grid, footer);
    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        save.disabled = true;
        status.textContent = "Salvando...";
        try {
            const saved = plugin
                ? await api(`/admin/labs/plugins/${plugin.id}`, json("PUT", payloadFrom(form)))
                : await api("/admin/labs/plugins", json("POST", payloadFrom(form)));
            Notify.success(plugin ? "Plugin salvo." : "Plugin criado. Agora envie a capa e os instaladores.");
            await reload();
            openEditor(saved);
        } catch (error) {
            status.textContent = error.message;
            save.disabled = false;
        }
    });
    box.append(form);
    if (plugin) box.append(mediaSection(plugin));
}

function mediaSection(plugin) {
    const wrap = el("div", "labs-admin__media");
    // Cover.
    const cover = el("section", "labs-admin__block");
    cover.append(el("h3", "", "Capa"), el("p", "labs-admin__help", "Imagem quadrada (você enquadra antes de enviar). Aparece nos cards e na página do plugin."));
    const preview = el("div", "labs-admin__cover labs-admin__cover--large");
    if (plugin.capa_url) {
        const image = el("img");
        image.src = plugin.capa_url;
        image.alt = "Capa atual";
        preview.append(image);
    } else preview.append(el("span", "", "Sem capa"));
    const file = input("capa", "", { type: "file", accept: ".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp", id: `labs-cover-${plugin.id}` });
    file.dataset.picker = "";
    file.className = "sr-only";
    const choose = el("label", "btn-small", plugin.capa_url ? "Trocar capa" : "Enviar capa");
    choose.htmlFor = file.id;
    const coverStatus = el("p", "labs-admin__status");
    coverStatus.setAttribute("role", "status");
    file.addEventListener("change", async () => {
        const chosen = file.files?.[0];
        file.value = "";
        if (!chosen) return;
        let cropped;
        try {
            cropped = await cropImage(chosen, { aspect: 1, width: 1200, height: 1200, title: "Ajustar capa", name: "capa" });
        } catch (error) { coverStatus.textContent = error.message; return; }
        if (!cropped) return;
        coverStatus.textContent = "Enviando capa...";
        const body = new FormData();
        body.append("capa", cropped);
        try {
            const saved = await api(`/admin/labs/plugins/${plugin.id}/capa`, { method: "POST", body });
            Notify.success("Capa atualizada.");
            await reload();
            openEditor(saved);
        } catch (error) { coverStatus.textContent = error.message; }
    });
    cover.append(preview, file, choose, coverStatus);
    // Installers.
    const installers = el("section", "labs-admin__block");
    installers.append(el("h3", "", "Instaladores"),
        el("p", "labs-admin__help", "Um por sistema: envie o instalador compactado em .zip (até 150 MB, segue em segundo plano) ou cole um link https. Quem comprou baixa pelo portal; o link nunca aparece na loja."));
    Object.entries(SISTEMAS).forEach(([key, label]) => installers.append(installerRow(plugin, key, label)));
    wrap.append(cover, installers);
    return wrap;
}

function installerRow(plugin, sistema, label) {
    const current = plugin.instaladores.find(row => row.sistema === sistema);
    const row = el("div", "labs-admin__installer");
    const info = el("div", "labs-admin__installer-info");
    info.append(el("strong", "", label));
    info.append(el("small", "", current
        ? current.tipo === "link" ? `Link · v${current.versao || "-"}` : `${current.nome_arquivo} · ${size(current.tamanho_bytes)} · v${current.versao || "-"}`
        : "Nenhum instalador"));
    const form = el("form", "labs-admin__installer-form");
    const version = input("versao", current?.versao || plugin.versao || "", { maxLength: 20, placeholder: "Versão" });
    const file = input("arquivo", "", { type: "file", accept: ".zip,application/zip" });
    file.dataset.picker = "";
    const link = input("link", current?.link || "", { type: "url", maxLength: 500, placeholder: "ou https://link-do-instalador" });
    const send = el("button", "btn-small", "Salvar");
    send.type = "submit";
    const message = el("small", "labs-admin__status");
    message.setAttribute("role", "status");
    form.append(field("Versão", version), field("Arquivo .zip", file), field("Link", link), send);
    form.addEventListener("submit", async event => {
        event.preventDefault();
        const chosen = file.files?.[0];
        try {
            if (chosen) {
                if (!chosen.name.toLowerCase().endsWith(".zip")) throw new Error("Envie o instalador em .zip.");
                if (chosen.size > 150 * 1024 * 1024) throw new Error("O arquivo passa de 150 MB; use um link.");
                const body = new FormData();
                body.append("arquivo", chosen);
                if (version.value.trim()) body.append("versao", version.value.trim());
                await enqueueUpload(`/admin/labs/plugins/${plugin.id}/instaladores/${sistema}`, body, {
                    label: `${plugin.nome} · ${label}`, meta: { kind: "labs-installer", plugin: plugin.id },
                });
                message.textContent = "Envio iniciado. Acompanhe em Envios.";
            } else if (link.value.trim()) {
                const saved = await api(`/admin/labs/plugins/${plugin.id}/instaladores/${sistema}/link`,
                    json("PUT", { link: link.value.trim(), versao: version.value.trim() || null }));
                Notify.success(`Instalador para ${label} salvo.`);
                await reload();
                openEditor(saved);
            } else {
                message.textContent = "Escolha um arquivo .zip ou cole um link.";
            }
        } catch (error) { message.textContent = error.message; }
    });
    row.append(info, form, message);
    if (current) {
        const remove = el("button", "btn-small labs-admin__remove", "Remover");
        remove.type = "button";
        remove.addEventListener("click", async () => {
            const ok = await confirmarAcao({ titulo: `Remover o instalador para ${label}?`,
                consequencias: ["Quem já comprou deixa de ver este download até você enviar outro."],
                palavra: null, botao: "Remover", tom: "aviso" });
            if (!ok) return;
            try {
                const saved = await api(`/admin/labs/plugins/${plugin.id}/instaladores/${sistema}`, { method: "DELETE" });
                await reload();
                openEditor(saved);
            } catch (error) { message.textContent = error.message; }
        });
        row.append(remove);
    }
    return row;
}

// ---------------------------------------------------------------- licenses

async function openLicenses(plugin) {
    const box = panel(`Licenças · ${plugin.nome}`);
    const body = el("div", "labs-admin__licenses");
    body.append(el("p", "", "Carregando..."));
    box.append(body);
    let rows;
    try {
        rows = await api(`/admin/labs/plugins/${plugin.id}/licencas`);
    } catch (error) {
        body.replaceChildren(el("p", "labs-admin__status", error.message));
        return;
    }
    const table = el("table", "labs-admin__table");
    const head = el("thead");
    const tr = el("tr");
    ["Cliente", "Origem", "Situação", "Chave", "Valor", ""].forEach(text => tr.append(el("th", "", text)));
    head.append(tr);
    const tbody = el("tbody");
    const ORIGEM = { compra: "Compra", gratuito: "Grátis", cortesia: "Cortesia" };
    const SITUACAO = { ativa: "Ativa", reservada: "Aguardando pagamento", revogada: "Revogada", cancelada: "Cancelada" };
    rows.forEach(row => {
        const line = el("tr");
        const client = el("td");
        client.append(el("strong", "", row.cliente), el("small", "", row.email || ""));
        line.append(client, el("td", "", ORIGEM[row.origem] || row.origem),
            el("td", "", row.motivo === "pagamento_revertido" ? "Suspensa (pagamento revertido)" : SITUACAO[row.status] || row.status),
            el("td", "labs-admin__key", row.status === "ativa" ? row.chave : "—"), el("td", "", money(row.valor)));
        const actions = el("td");
        if (["ativa", "reservada"].includes(row.status)) {
            const revoke = el("button", "btn-small labs-admin__remove", "Revogar");
            revoke.type = "button";
            revoke.addEventListener("click", async () => {
                const ok = await confirmarAcao({ titulo: `Revogar a licença de ${row.cliente}?`,
                    consequencias: ["O cliente deixa de baixar o plugin e a chave para de ativar."],
                    palavra: null, botao: "Revogar", tom: "perigo", motivo: { rotulo: "Motivo (fica no histórico)", maximo: 40 } });
                if (!ok) return;
                try {
                    await api(`/admin/labs/licencas/${row.id}/revogar`, json("POST", { motivo: ok.motivo }));
                    Notify.success("Licença revogada.");
                    await reload();
                    openLicenses(plugin);
                } catch (error) { Notify.error(error.message); }
            });
            actions.append(revoke);
        }
        line.append(actions);
        tbody.append(line);
    });
    if (!rows.length) {
        const empty = el("tr");
        const cell = el("td", "", "Nenhuma licença ainda.");
        cell.colSpan = 6;
        empty.append(cell);
        tbody.append(empty);
    }
    table.append(head, tbody);
    const scroller = el("div", "labs-admin__table-wrap");
    scroller.append(table);
    body.replaceChildren(scroller, giftForm(plugin));
}

function giftForm(plugin) {
    const form = el("form", "labs-admin__gift");
    form.append(el("h3", "", "Dar uma licença de cortesia"));
    const search = input("busca", "", { type: "search", placeholder: "Nome ou e-mail do cliente", maxLength: 150 });
    const select = el("select");
    select.name = "cliente_id";
    select.required = true;
    select.append(el("option", "", "Busque um cliente"));
    select.firstChild.value = "";
    let timer;
    search.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(async () => {
            const term = search.value.trim();
            if (term.length < 2) return;
            try {
                const clients = await api(`/clientes?busca=${encodeURIComponent(term)}`);
                select.replaceChildren(...clients.slice(0, 20).map(client => {
                    const option = el("option", "", `${client.nome}${client.email ? ` · ${client.email}` : ""}`);
                    option.value = client.id;
                    return option;
                }));
                if (!clients.length) select.append(Object.assign(el("option", "", "Nenhum cliente encontrado"), { value: "" }));
            } catch { /* keep the previous list */ }
        }, 250);
    });
    const give = el("button", "btn-small", "Dar licença");
    give.type = "submit";
    const message = el("small", "labs-admin__status");
    message.setAttribute("role", "status");
    form.append(field("Buscar cliente", search), field("Cliente", select), give, message);
    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (!select.value) { message.textContent = "Escolha um cliente."; return; }
        try {
            await api(`/admin/labs/plugins/${plugin.id}/cortesias`, json("POST", { cliente_id: Number(select.value) }));
            Notify.success("Licença de cortesia criada.");
            await reload();
            openLicenses(plugin);
        } catch (error) { message.textContent = error.message; }
    });
    return form;
}

// ---------------------------------------------------------------- load

async function reload() {
    plugins = await api("/admin/labs/plugins");
    renderList();
}

document.addEventListener("mirai:upload-task", async event => {
    if (event.detail.meta?.kind !== "labs-installer") return;
    if (event.detail.status === "completed") Notify.success("Instalador enviado.");
    await reload().catch(() => {});
    const open = plugins.find(item => item.id === event.detail.meta.plugin);
    const panelRoot = document.getElementById("labs-admin-panel");
    if (open && panelRoot && !panelRoot.hidden && panelRoot.textContent.includes(open.nome)) openEditor(open);
});

export async function initLabs() {
    const root = document.getElementById("labs-admin-list");
    if (!root) return;
    const create = document.getElementById("labs-admin-new");
    if (create && !create.dataset.bound) {
        create.dataset.bound = "true";
        create.addEventListener("click", () => openEditor());
    }
    root.setAttribute("aria-busy", "true");
    try {
        await reload();
    } catch (error) {
        root.replaceChildren(el("p", "labs-admin__status", error.message));
    } finally {
        root.removeAttribute("aria-busy");
    }
}
