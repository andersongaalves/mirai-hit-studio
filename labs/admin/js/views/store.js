// Store: announcement banner and the order/featured plugins of the catalog.
import { api } from "../api.js";
import { PLUGIN_STATUS, busy, checkbox, chip, cover, el, field, input, pageHead, toast } from "../ui.js";

function bannerCard(banner) {
    const form = el("form", { class: "card", novalidate: true });
    const text = input("texto", banner.texto || "", { maxLength: 200, placeholder: "Black Friday: 30% off com o cupom BF30" });
    const textEn = input("texto_en", banner.texto_en || "", { maxLength: 200, placeholder: "Black Friday: 30% off with code BF30" });
    const link = input("link", banner.link || "", { maxLength: 300, placeholder: "/plugins/mirai-saturator ou https://..." });
    const active = checkbox("ativo", banner.ativo, "Mostrar na loja");
    const preview = el("div", { class: "banner-preview" });
    const sync = () => { preview.textContent = textEn.value.trim() || text.value.trim() || "Prévia do aviso"; };
    [text, textEn].forEach(node => node.addEventListener("input", sync));
    sync();
    const status = el("p", { class: "form-status", role: "status" });
    const save = el("button", { class: "btn btn--small", type: "submit", text: "Salvar aviso" });
    form.append(el("h2", { class: "card__title", text: "Aviso no topo da loja" }),
        el("p", { class: "muted flush", text: "Uma faixa acima do cabeçalho, nas duas línguas. Bom para promoções e lançamentos." }),
        preview,
        el("div", { class: "grid-form" }, field("Texto (PT)", text, { full: true }), field("Texto (EN)", textEn, { full: true, help: "Vazio mostra o texto em português." }),
            field("Link (opcional)", link, { full: true, help: "Caminho da loja (ex.: /plugins/mirai-saturator) ou https. Na loja PT o caminho ganha /pt." }),
            el("div", { class: "field field--full" }, active)),
        el("div", { class: "actions" }, save, status));
    form.addEventListener("submit", event => {
        event.preventDefault();
        busy(save, async () => {
            await api("/admin/labs/conteudo/banner", { method: "PUT", body: {
                ativo: form.ativo.checked, texto: text.value.trim() || null, texto_en: textEn.value.trim() || null, link: link.value.trim() || null } });
            toast(form.ativo.checked ? "Aviso publicado na loja (pode levar 1 minuto)." : "Aviso salvo (oculto).");
        }, status);
    });
    return form;
}

function orderCard(plugins) {
    let items = plugins.map(plugin => ({ ...plugin }));
    const list = el("ol", { class: "order-list" });
    const status = el("p", { class: "form-status", role: "status" });
    const save = el("button", { class: "btn btn--small", type: "button", text: "Salvar ordem" });
    const draw = () => {
        list.replaceChildren(...items.map((plugin, index) => {
            const [label, tone] = PLUGIN_STATUS[plugin.status] || [plugin.status, ""];
            const featured = el("input", { type: "checkbox", "aria-label": `Destaque: ${plugin.nome}` });
            featured.checked = plugin.destaque;
            featured.addEventListener("change", () => { plugin.destaque = featured.checked; });
            const move = (delta, symbol, name) => el("button", { class: "icon-btn", type: "button", text: symbol, "aria-label": `${name}: ${plugin.nome}`,
                disabled: index + delta < 0 || index + delta >= items.length,
                onclick: () => {
                    const next = [...items];
                    [next[index], next[index + delta]] = [next[index + delta], next[index]];
                    items = next;
                    draw();
                    list.children[index + delta]?.querySelector(`[aria-label^="${name}"]`)?.focus();
                } });
            return el("li", { class: "order-item" }, cover(plugin.capa_url),
                el("div", {}, el("div", { class: "order-item__name", text: plugin.nome }), chip(label, tone)),
                el("label", { class: "check" }, featured, el("span", { text: "Destaque" })),
                el("div", { class: "order-item__moves" }, move(-1, "↑", "Subir"), move(1, "↓", "Descer")));
        }));
    };
    draw();
    save.addEventListener("click", () => busy(save, async () => {
        await api("/admin/labs/ordem", { method: "PUT", body: { ids: items.map(item => item.id), destaques: items.filter(item => item.destaque).map(item => item.id) } });
        toast("Ordem da loja salva.");
    }, status));
    return el("section", { class: "card" }, el("h2", { class: "card__title", text: "Ordem do catálogo" }),
        el("p", { class: "muted flush", text: "Destaques aparecem primeiro, com o selo Featured; depois a ordem desta lista. Só plugins publicados aparecem na loja." }),
        items.length ? list : el("div", { class: "empty", text: "Nenhum plugin cadastrado." }),
        items.length ? el("div", { class: "actions" }, save, status) : null);
}

export async function render() {
    const [content, plugins] = await Promise.all([api("/admin/labs/conteudo"), api("/admin/labs/plugins")]);
    return el("div", {}, pageHead("Loja", { lead: "O que a vitrine mostra além dos plugins." }),
        el("div", { class: "two-col" }, orderCard(plugins), bannerCard(content.banner)));
}
