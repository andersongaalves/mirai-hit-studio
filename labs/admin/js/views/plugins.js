// Plugins: catalog list and the editor (store page, cover and installers, releases, licenses).
import { api, upload } from "../api.js";
import {
    ORIGEM, PLUGIN_STATUS, busy, cell, checkbox, chip, confirm, copy, cover, datetime, el, field, input,
    licenseChip, money, pageHead, plural, select, size, slugify, table, textarea, toast,
} from "../ui.js";

const SISTEMAS = { windows: "Windows", macos: "macOS" };
const FORMATOS = ["VST3", "AU", "AAX", "CLAP", "Standalone"];
const STATUS = { rascunho: "Rascunho", publicado: "Publicado", arquivado: "Arquivado" };
const STORE = window.location.origin;
const MAX_INSTALLER = 150 * 1024 * 1024;

// ---------------------------------------------------------------- list

function pluginCard(plugin) {
    const [label, tone] = PLUGIN_STATUS[plugin.status] || [plugin.status, ""];
    const price = plugin.gratuito ? "Grátis" : plugin.em_promocao
        ? `${money(plugin.preco_vigente)} (de ${money(plugin.preco)})` : money(plugin.preco_vigente);
    const missing = Object.keys(SISTEMAS).filter(key => !plugin.instaladores.some(row => row.sistema === key));
    return el("a", { class: "pcard", href: `#/plugins/${plugin.id}` },
        el("div", { class: "pcard__cover" }, plugin.capa_url ? el("img", { src: plugin.capa_url, alt: "", loading: "lazy" }) : "Sem capa"),
        el("div", { class: "pcard__body" },
            el("h2", { class: "pcard__name", text: plugin.nome }),
            el("p", { class: "pcard__meta", text: [price, plugin.versao && `v${plugin.versao}`].filter(Boolean).join(" · ") }),
            el("div", { class: "pcard__chips" }, chip(label, tone), plugin.destaque ? chip("Destaque", "ink") : null,
                missing.length ? chip(`Falta ${missing.map(key => SISTEMAS[key]).join(" e ")}`, "warn") : null),
            el("p", { class: "pcard__meta", text: `${plural(plugin.licencas.ativas, "licença ativa", "licenças ativas")}${plugin.licencas.reservadas ? ` · ${plugin.licencas.reservadas} aguardando` : ""}` })));
}

async function list() {
    const plugins = await api("/admin/labs/plugins");
    const create = el("a", { class: "btn", href: "#/plugins/novo", text: "Novo plugin" });
    const root = el("div", {}, pageHead("Plugins", {
        lead: "O que aparece na loja. Um plugin só fica visível depois de publicado, com capa e pelo menos um instalador.",
        actions: [create],
    }));
    root.append(plugins.length ? el("div", { class: "plugins" }, ...plugins.map(pluginCard))
        : el("div", { class: "empty" }, el("strong", { text: "Nenhum plugin ainda." }), el("br"),
            "Cadastre o primeiro: texto e preço, depois capa, instaladores e a primeira versão."));
    return root;
}

// ---------------------------------------------------------------- page form

function payloadFrom(form) {
    const data = new FormData(form);
    const text = name => String(data.get(name) || "").trim();
    const lines = name => text(name).split("\n").map(item => item.trim()).filter(Boolean);
    return {
        nome: text("nome"), slug: text("slug"), tagline: text("tagline") || null, descricao: text("descricao") || null,
        categoria: text("categoria") || null, versao: text("versao") || null, formatos: data.getAll("formatos").map(String),
        recursos: lines("recursos"), requisitos: text("requisitos") || null,
        tagline_en: text("tagline_en") || null, descricao_en: text("descricao_en") || null,
        categoria_en: text("categoria_en") || null, recursos_en: lines("recursos_en"), requisitos_en: text("requisitos_en") || null,
        preco: text("preco") || "0", preco_promocional: text("preco_promocional") || null,
        video_url: text("video_url") || null, status: text("status") || "rascunho",
        destaque: data.get("destaque") === "on", ordem: Number(text("ordem") || 0),
    };
}

function pageForm(plugin, onSaved) {
    const form = el("form", { class: "card", novalidate: true });
    const nome = input("nome", plugin?.nome, { required: true, maxLength: 80, placeholder: "Ex.: Mirai Saturator" });
    const slug = input("slug", plugin?.slug, { required: true, maxLength: 60, autocapitalize: "none", spellcheck: false,
        pattern: "[a-z0-9](?:[a-z0-9\\-]{0,58}[a-z0-9])?" });
    const url = el("span", { class: "field__help mono", text: `${STORE}/plugins/${plugin?.slug || "..."}` });
    let slugTouched = Boolean(plugin);
    const syncUrl = () => { url.textContent = `${STORE}/plugins/${slug.value || "..."}`; };
    nome.addEventListener("input", () => { if (!slugTouched) slug.value = slugify(nome.value); syncUrl(); });
    slug.addEventListener("input", () => { slugTouched = true; slug.value = slugify(slug.value); syncUrl(); });
    const slugField = field("Endereço", slug);
    slugField.append(url);
    const formats = el("div", { class: "checks" }, ...FORMATOS.map(name => {
        const box = el("input", { type: "checkbox", name: "formatos", value: name });
        box.checked = plugin?.formatos?.includes(name) || false;
        return el("label", { class: "check" }, box, el("span", { text: name }));
    }));
    const en = plugin?.en || {};
    const status = el("p", { class: "form-status", role: "status" });
    const save = el("button", { class: "btn", type: "submit", text: plugin ? "Salvar" : "Criar plugin" });
    form.append(
        el("h2", { class: "card__title", text: "Página na loja" }),
        el("div", { class: "grid-form" },
            field("Nome", nome), slugField,
            field("Frase curta", input("tagline", plugin?.tagline, { maxLength: 160, placeholder: "Saturação analógica em um botão" }), { full: true }),
            field("Categoria", input("categoria", plugin?.categoria, { maxLength: 40, placeholder: "Saturação" })),
            field("Versão exibida", input("versao", plugin?.versao, { maxLength: 20, placeholder: "1.0.0" }), { help: "Publicar uma versão estável na aba Versões atualiza este campo." }),
            field("Preço", input("preco", plugin?.preco ?? "0", { type: "number", min: "0", step: "0.01", required: true }), { help: "Mesmo número em R$ (loja PT) e US$ (loja EN). 0 = grátis." }),
            field("Preço promocional", input("preco_promocional", plugin?.preco_promocional ?? "", { type: "number", min: "0", step: "0.01" }), { help: "Opcional; menor que o preço." }),
            field("Formatos", formats, { full: true }),
            field("Descrição", textarea("descricao", plugin?.descricao, { rows: 6, maxLength: 8000 }), { full: true }),
            field("Recursos (um por linha)", textarea("recursos", (plugin?.recursos || []).join("\n"), { rows: 4 }), { full: true, help: "Até 12 itens curtos." }),
            field("Requisitos", textarea("requisitos", plugin?.requisitos, { rows: 3, maxLength: 2000, placeholder: "Windows 10+ (64 bits) ou macOS 12+" }), { full: true }),
        ),
        el("fieldset", { class: "group" }, el("legend", { text: "Inglês (idioma padrão da loja)" }),
            el("p", { class: "field__help field--full flush", text: "A loja abre em inglês. Campo vazio mostra o texto em português." }),
            field("Frase curta (EN)", input("tagline_en", en.tagline, { maxLength: 160 }), { full: true }),
            field("Categoria (EN)", input("categoria_en", en.categoria, { maxLength: 40 })),
            field("Descrição (EN)", textarea("descricao_en", en.descricao, { rows: 6, maxLength: 8000 }), { full: true }),
            field("Recursos (EN, um por linha)", textarea("recursos_en", (en.recursos || []).join("\n"), { rows: 4 }), { full: true }),
            field("Requisitos (EN)", textarea("requisitos_en", en.requisitos, { rows: 3, maxLength: 2000 }), { full: true })),
        el("div", { class: "grid-form" },
            field("Vídeo (link https)", input("video_url", plugin?.video_url, { type: "url", maxLength: 300, placeholder: "https://www.youtube.com/watch?v=..." })),
            field("Ordem na loja", input("ordem", plugin?.ordem ?? 0, { type: "number", min: "0", max: "9999", step: "1" })),
            field("Situação", select("status", STATUS, plugin?.status || "rascunho"), { help: "Publicar exige capa e pelo menos um instalador." }),
            field("Destaque", checkbox("destaque", plugin?.destaque, "Aparece primeiro na loja"))),
        el("div", { class: "actions" }, save, status),
    );
    form.addEventListener("submit", event => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        busy(save, async () => {
            const body = payloadFrom(form);
            const saved = plugin
                ? await api(`/admin/labs/plugins/${plugin.id}`, { method: "PUT", body })
                : await api("/admin/labs/plugins", { method: "POST", body });
            toast(plugin ? "Plugin salvo." : "Plugin criado. Agora envie a capa e os instaladores.");
            onSaved(saved);
        }, status);
    });
    return form;
}

// ---------------------------------------------------------------- cover and installers

// Center-crops the image to a 1200x1200 square before sending (same framing as the store cards).
async function squareCover(file) {
    const bitmap = await createImageBitmap(file);
    const side = Math.min(bitmap.width, bitmap.height);
    const target = Math.min(1200, side);
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = target;
    canvas.getContext("2d").drawImage(bitmap, (bitmap.width - side) / 2, (bitmap.height - side) / 2, side, side, 0, 0, target, target);
    bitmap.close?.();
    const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/webp", 0.9));
    if (!blob) throw new Error("Não foi possível preparar a imagem.");
    return new File([blob], "capa.webp", { type: "image/webp" });
}

function progressBar() {
    const bar = el("span");
    const box = el("div", { class: "progress", hidden: true, role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100" }, bar);
    return {
        node: box,
        set(fraction) {
            box.hidden = false;
            const percent = Math.round(fraction * 100);
            bar.style.width = `${percent}%`;
            box.setAttribute("aria-valuenow", String(percent));
        },
        hide() { box.hidden = true; },
    };
}

function coverCard(plugin, refresh) {
    const file = el("input", { type: "file", accept: "image/jpeg,image/png,image/webp", class: "sr-only", id: `cover-${plugin.id}` });
    const status = el("p", { class: "form-status", role: "status" });
    const progress = progressBar();
    file.addEventListener("change", async () => {
        const chosen = file.files?.[0];
        file.value = "";
        if (!chosen) return;
        status.textContent = "Enviando capa...";
        status.classList.remove("form-status--error");
        try {
            const body = new FormData();
            body.append("capa", await squareCover(chosen));
            await upload(`/admin/labs/plugins/${plugin.id}/capa`, body, fraction => progress.set(fraction));
            toast("Capa atualizada.");
            refresh();
        } catch (error) {
            progress.hide();
            status.textContent = error.message;
            status.classList.add("form-status--error");
        }
    });
    return el("section", { class: "card" }, el("h2", { class: "card__title", text: "Capa" }),
        el("div", { class: "media" }, cover(plugin.capa_url, "Capa atual"),
            el("div", { class: "stack" },
                el("p", { class: "muted flush", text: "Imagem quadrada; enviamos recortada no centro em 1200×1200. Aparece nos cards e na página do plugin." }),
                el("div", { class: "actions" }, file, el("label", { class: "btn btn--ghost btn--small", for: file.id, text: plugin.capa_url ? "Trocar capa" : "Enviar capa" })),
                progress.node, status)));
}

function installerRow(plugin, sistema, label, refresh) {
    const current = plugin.instaladores.find(row => row.sistema === sistema);
    const version = input("versao", current?.versao || plugin.versao || "", { maxLength: 20, placeholder: "1.0.0" });
    const file = input("arquivo", "", { type: "file", accept: ".zip,application/zip" });
    const link = input("link", current?.link || "", { type: "url", maxLength: 500, placeholder: "https://..." });
    const save = el("button", { class: "btn btn--small", type: "submit", text: "Salvar" });
    const status = el("p", { class: "form-status", role: "status" });
    const progress = progressBar();
    const form = el("form", { class: "installer__form" }, field("Versão", version), field("Arquivo .zip (até 150 MB)", file),
        field("ou link https", link), save);
    form.addEventListener("submit", event => {
        event.preventDefault();
        const chosen = file.files?.[0];
        busy(save, async () => {
            if (chosen) {
                if (!chosen.name.toLowerCase().endsWith(".zip")) throw new Error("Envie o instalador em .zip.");
                if (chosen.size > MAX_INSTALLER) throw new Error("O arquivo passa de 150 MB; use um link.");
                const body = new FormData();
                body.append("arquivo", chosen);
                if (version.value.trim()) body.append("versao", version.value.trim());
                status.textContent = "Enviando...";
                await upload(`/admin/labs/plugins/${plugin.id}/instaladores/${sistema}`, body, fraction => progress.set(fraction));
            } else if (link.value.trim()) {
                await api(`/admin/labs/plugins/${plugin.id}/instaladores/${sistema}/link`, { method: "PUT",
                    body: { link: link.value.trim(), versao: version.value.trim() || null } });
            } else {
                throw new Error("Escolha um arquivo .zip ou cole um link.");
            }
            toast(`Instalador para ${label} salvo.`);
            refresh();
        }, status).finally(() => progress.hide());
    });
    const remove = current ? el("button", { class: "btn btn--danger btn--small", type: "button", text: "Remover",
        onclick: async event => {
            const ok = await confirm({ title: `Remover o instalador para ${label}?`, button: "Remover", danger: true,
                lines: ["Quem já comprou deixa de ver este download até você enviar outro."] });
            if (!ok) return;
            busy(event.currentTarget, async () => {
                await api(`/admin/labs/plugins/${plugin.id}/instaladores/${sistema}`, { method: "DELETE" });
                toast("Instalador removido.");
                refresh();
            });
        } }) : null;
    const info = current
        ? current.tipo === "link" ? `Link externo · v${current.versao || "—"} · ${datetime(current.atualizado_em)}`
            : `${current.nome_arquivo} · ${size(current.tamanho_bytes)} · v${current.versao || "—"} · ${datetime(current.atualizado_em)}`
        : "Nenhum instalador";
    return el("div", { class: "installer" },
        el("div", { class: "installer__head" }, el("div", {}, el("strong", { text: label }), el("div", { class: "muted small", text: info })),
            current ? chip("Pronto", "ok") : chip("Pendente", "warn")),
        form, progress.node, status, remove ? el("div", {}, remove) : null);
}

function mediaTab(plugin, refresh) {
    return el("div", {}, coverCard(plugin, refresh),
        el("section", { class: "card" }, el("h2", { class: "card__title", text: "Instaladores" }),
            el("p", { class: "muted flush", text: "Um por sistema. Quem comprou baixa em My plugins; o link nunca aparece na loja." }),
            el("div", {}, ...Object.entries(SISTEMAS).map(([key, label]) => installerRow(plugin, key, label, refresh)))));
}

// ---------------------------------------------------------------- releases

function releaseForm(plugin, release, done) {
    const form = el("form", { class: "card" });
    const version = input("versao", release?.versao || "", { required: true, maxLength: 20, placeholder: "1.1.0", pattern: "[0-9A-Za-z][0-9A-Za-z.\\-+]{0,19}" });
    const channel = select("canal", { estavel: "Estável", beta: "Beta" }, release?.canal || "estavel");
    const notes = textarea("notas", release?.notas, { rows: 5, maxLength: 8000, placeholder: "- Novo modo válvula\n- Correção de clique ao trocar presets" });
    const notesEn = textarea("notas_en", release?.notas_en, { rows: 5, maxLength: 8000 });
    const required = checkbox("obrigatoria", release?.obrigatoria, "Atualização importante (o plugin insiste mais no aviso)");
    const publish = checkbox("publicar", release ? release.publicada : true, "Publicar agora (os plugins passam a avisar)");
    const status = el("p", { class: "form-status", role: "status" });
    const save = el("button", { class: "btn btn--small", type: "submit", text: release ? "Salvar versão" : "Adicionar versão" });
    const cancel = release ? el("button", { class: "btn btn--ghost btn--small", type: "button", text: "Cancelar", onclick: () => done(false) }) : null;
    form.append(el("h2", { class: "card__title", text: release ? `Editar v${release.versao}` : "Nova versão" }),
        el("div", { class: "grid-form" }, field("Versão", version), field("Canal", channel),
            field("Novidades (PT)", notes, { full: true }), field("Novidades (EN)", notesEn, { full: true }),
            el("div", { class: "field field--full checks" }, publish, required)),
        el("div", { class: "actions" }, save, cancel, status));
    form.addEventListener("submit", event => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        const body = { versao: version.value.trim(), canal: channel.value, notas: notes.value.trim() || null,
            notas_en: notesEn.value.trim() || null, obrigatoria: form.obrigatoria.checked, publicar: form.publicar.checked };
        busy(save, async () => {
            if (release) await api(`/admin/labs/versoes/${release.id}`, { method: "PUT", body });
            else await api(`/admin/labs/plugins/${plugin.id}/versoes`, { method: "POST", body });
            toast(release ? "Versão salva." : `Versão ${body.versao} adicionada.`);
            done(true);
        }, status);
    });
    return form;
}

async function releasesTab(plugin, refresh) {
    const releases = await api(`/admin/labs/plugins/${plugin.id}/versoes`);
    const root = el("div", {});
    const feed = `https://api.miraihitstudio.com.br/labs/plugins/${plugin.slug}/atualizacao`;
    const render = (editing = null) => {
        const listCard = el("section", { class: "card" }, el("h2", { class: "card__title", text: "Histórico" }));
        if (!releases.length) listCard.append(el("p", { class: "muted flush", text: "Nenhuma versão registrada ainda." }));
        releases.forEach(release => {
            if (editing === release.id) {
                listCard.append(releaseForm(plugin, release, changed => (changed ? refresh() : render())));
                return;
            }
            const current = release.versao === plugin.versao && release.canal === "estavel" && release.publicada;
            listCard.append(el("article", { class: "release" },
                el("div", { class: "release__head" }, el("span", { class: "release__version", text: `v${release.versao}` }),
                    release.canal === "beta" ? chip("Beta", "warn") : chip("Estável", "plain"),
                    release.publicada ? (current ? chip("Atual", "ok") : chip("Publicada", "plain")) : chip("Rascunho"),
                    release.obrigatoria ? chip("Importante", "bad") : null,
                    el("span", { class: "muted small", text: release.publicada ? datetime(release.publicada_em) : `criada ${datetime(release.criada_em)}` })),
                release.notas ? el("p", { class: "release__notes", text: release.notas }) : null,
                el("div", { class: "actions" },
                    el("button", { class: "link-button", type: "button", text: "Editar", onclick: () => render(release.id) }),
                    el("button", { class: "link-button", type: "button", text: "Apagar", onclick: async () => {
                        const ok = await confirm({ title: `Apagar a versão ${release.versao}?`, button: "Apagar", danger: true,
                            lines: ["Sai do histórico e do aviso de atualização. Os instaladores não mudam."] });
                        if (!ok) return;
                        await busy(null, async () => {
                            await api(`/admin/labs/versoes/${release.id}`, { method: "DELETE" });
                            toast("Versão apagada.");
                            refresh();
                        });
                    } }))));
        });
        const feedCard = el("section", { class: "card" }, el("h2", { class: "card__title", text: "Aviso de atualização nos plugins" }),
            el("p", { class: "muted flush", text: "Os plugins e o app leem este endereço (no máximo uma vez por dia) e comparam com a versão instalada. Beta: acrescente ?canal=beta." }),
            el("div", { class: "actions" }, el("code", { class: "code-box", text: feed }),
                el("button", { class: "btn btn--ghost btn--small", type: "button", text: "Copiar", onclick: () => copy(feed) })));
        root.replaceChildren(releaseForm(plugin, null, changed => changed && refresh()), listCard, feedCard);
    };
    render();
    return root;
}

// ---------------------------------------------------------------- licenses

async function licensesTab(plugin, refresh) {
    const rows = await api(`/admin/labs/licencas?plugin_id=${plugin.id}`);
    const email = input("email", "", { type: "email", required: true, maxLength: 150, placeholder: "email@cliente.com" });
    const give = el("button", { class: "btn btn--small", type: "submit", text: "Dar licença" });
    const status = el("p", { class: "form-status", role: "status" });
    const gift = el("form", { class: "card" }, el("h2", { class: "card__title", text: "Licença de cortesia" }),
        el("p", { class: "muted flush", text: "Para quem já tem conta na loja ou é cliente do estúdio. A pessoa vê o plugin em My plugins na hora." }),
        el("div", { class: "filters" }, field("E-mail", email), give), status);
    gift.addEventListener("submit", event => {
        event.preventDefault();
        if (!gift.reportValidity()) return;
        busy(give, async () => {
            await api(`/admin/labs/plugins/${plugin.id}/cortesias/email`, { method: "POST", body: { email: email.value.trim() } });
            toast("Licença de cortesia criada.");
            refresh();
        }, status);
    });
    const lines = rows.map(row => el("tr", {},
        cell([el("a", { class: "row-link", href: `#/clientes/${row.cliente_id}`, text: row.cliente }), el("small", { text: row.email || "" })]),
        cell(ORIGEM[row.origem] || row.origem), cell(licenseChip(row)),
        cell(row.status === "ativa" ? row.chave : "—", "mono nowrap"),
        cell(row.origem === "compra" || row.origem === "stripe" ? money(row.valor, row.moeda) : "—", "num"),
        cell(datetime(row.ativada_em || row.criada_em), "nowrap")));
    return el("div", {}, gift, el("section", { class: "card" },
        el("div", { class: "card__head" }, el("h2", { class: "card__title", text: `Licenças (${rows.length})` }),
            el("a", { class: "link-button", href: `#/licencas?plugin=${plugin.id}`, text: "Gerenciar em Licenças" })),
        table(["Cliente", "Origem", "Situação", "Chave", ["Valor", "num"], "Data"], lines, "Nenhuma licença ainda.")));
}

// ---------------------------------------------------------------- editor

const TABS = { pagina: "Página", midia: "Capa e instaladores", versoes: "Versões", licencas: "Licenças" };

async function editor(id, query, rerender) {
    if (id === "novo") {
        return el("div", {}, pageHead("Novo plugin", { crumb: el("p", { class: "crumb" }, el("a", { href: "#/plugins", text: "Plugins" })) }),
            pageForm(null, saved => { window.location.hash = `#/plugins/${saved.id}?aba=midia`; }));
    }
    const plugin = await api(`/admin/labs/plugins/${encodeURIComponent(id)}`);
    const tab = TABS[query.get("aba")] ? query.get("aba") : "pagina";
    const [label, tone] = PLUGIN_STATUS[plugin.status] || [plugin.status, ""];
    const actions = [chip(label, tone)];
    if (plugin.status === "publicado") actions.push(el("a", { class: "btn btn--ghost btn--small", href: `/plugins/${plugin.slug}`, target: "_blank", rel: "noopener", text: "Ver na loja ↗" }));
    const head = pageHead(plugin.nome, {
        crumb: el("p", { class: "crumb" }, el("a", { href: "#/plugins", text: "Plugins" })),
        lead: [plugin.versao && `v${plugin.versao}`, plugin.gratuito ? "Grátis" : money(plugin.preco_vigente),
            plural(plugin.licencas.ativas, "licença ativa", "licenças ativas")].filter(Boolean).join(" · "),
        actions,
    });
    const tabs = el("div", { class: "tabs", role: "tablist" }, ...Object.entries(TABS).map(([key, text]) =>
        el("button", { type: "button", role: "tab", "aria-selected": String(key === tab), text,
            onclick: () => { window.location.hash = `#/plugins/${plugin.id}?aba=${key}`; } })));
    const refresh = () => rerender();
    let body;
    if (tab === "pagina") body = pageForm(plugin, () => refresh());
    else if (tab === "midia") body = mediaTab(plugin, refresh);
    else if (tab === "versoes") body = await releasesTab(plugin, refresh);
    else body = await licensesTab(plugin, refresh);
    return el("div", {}, head, tabs, body);
}

export async function render({ params, query, rerender }) {
    return params[0] ? editor(params[0], query, rerender) : list();
}
