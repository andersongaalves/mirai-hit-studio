// Roadmap 3.0, 5.08: catalog combos (admin). Everything is rendered as text.
import { authFetch } from "../auth.js";
import * as Notify from "../../utils/notifications.js";

const state = { combos: [], servicos: [], editing: null, busy: false };
const byId = id => document.getElementById(id);

function element(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

function money(value) {
    return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value || 0));
}

async function request(path, options = {}) {
    const response = await authFetch(path, options);
    const data = await response.json().catch(() => null);
    if (!response.ok) {
        const detail = data?.detail;
        throw new Error(typeof detail === "string" ? detail
            : Array.isArray(detail) ? "Revise os campos do combo (nome, preço e ao menos dois serviços)."
            : "Não foi possível concluir a operação do combo.");
    }
    return data;
}

function renderList() {
    const list = byId("combos-list");
    if (!list) return;
    list.replaceChildren();
    if (!state.combos.length) {
        list.append(element("p", "admin-help", "Nenhum combo cadastrado."));
        return;
    }
    state.combos.forEach(combo => {
        const card = element("article", `combo-card${combo.ativo ? "" : " combo-card--inativo"}`);
        const head = element("p", "combo-card__head");
        head.append(element("strong", "", combo.nome));
        head.append(element("span", "combo-card__badge", combo.ativo ? "Ativo" : "Inativo"));
        card.append(head);
        if (combo.descricao) card.append(element("p", "combo-card__meta", combo.descricao));
        card.append(element(
            "p",
            "combo-card__meta",
            `Preço ${money(combo.preco_base)}${combo.aplica_desconto ? " (com desconto do site)" : ""} · soma dos serviços ${money(combo.soma_servicos)}`,
        ));
        const services = element("ul", "combo-card__servicos");
        combo.servicos.forEach(item => services.append(element(
            "li",
            "",
            `${item.nome} — ${money(item.valor_base)}${item.etapas ? ` · ${item.etapas} etapas` : " · sem etapas"}`,
        )));
        card.append(services);
        const edit = element("button", "btn-small", "Editar");
        edit.type = "button";
        edit.setAttribute("aria-label", `Editar combo ${combo.nome}`);
        edit.addEventListener("click", () => openEditor(combo));
        card.append(edit);
        list.append(card);
    });
}

function closeEditor() {
    state.editing = null;
    const editor = byId("combo-editor");
    if (!editor) return;
    editor.replaceChildren();
    editor.classList.add("hidden");
}

function openEditor(combo = null) {
    const editor = byId("combo-editor");
    if (!editor) return;
    state.editing = combo;
    editor.replaceChildren();
    editor.classList.remove("hidden");
    const form = element("form", "combo-form");
    form.noValidate = true;
    form.append(element("h3", "", combo ? `Editar combo: ${combo.nome}` : "Novo combo"));

    const field = (labelText, input) => {
        const label = element("label", "combo-form__field");
        label.append(element("span", "", labelText), input);
        return label;
    };
    const name = element("input");
    name.maxLength = 100;
    name.required = true;
    name.value = combo?.nome ?? "";
    // Catalog rework: a combo is sold like a service; what it includes comes from its services.
    const subtitle = element("input");
    subtitle.maxLength = 150;
    subtitle.placeholder = "Ex.: Para quem já tem tudo gravado";
    subtitle.value = combo?.subtitulo ?? "";
    const description = element("textarea");
    description.rows = 3;
    description.maxLength = 1000;
    description.value = combo?.descricao ?? "";
    const discount = element("select");
    [["false", "Não"], ["true", "Sim"]].forEach(([value, text]) => {
        const option = element("option", "", text);
        option.value = value;
        discount.append(option);
    });
    discount.value = String(Boolean(combo?.aplica_desconto));
    const highlights = element("textarea");
    highlights.rows = 3;
    highlights.placeholder = "Ex.: Desconto de combo";
    highlights.value = (combo?.destaques ?? []).join("\n");
    const price = element("input");
    price.type = "number";
    price.min = "0";
    price.step = "0.01";
    price.value = combo?.preco_base ?? "";
    const active = element("input");
    active.type = "checkbox";
    active.checked = combo ? Boolean(combo.ativo) : true;

    // The order of the services in the combo (stages, proposal and site follow it).
    const order = combo ? combo.servicos.map(item => item.servico_id) : [];
    const selected = { has: id => order.includes(id), get size() { return order.length; } };
    const sum = element("p", "combo-form__sum");
    const useSum = element("button", "btn-outline", "Usar soma dos serviços");
    useSum.type = "button";
    const orderList = element("ol", "combo-form__ordem");
    orderList.setAttribute("aria-label", "Ordem dos serviços no combo");
    const nameOf = id => state.servicos.find(servico => servico.id === id)?.nome
        ?? combo?.servicos.find(item => item.servico_id === id)?.nome ?? `Serviço ${id}`;
    const renderOrder = () => {
        orderList.replaceChildren();
        if (!order.length) {
            orderList.append(element("li", "admin-help", "Marque os serviços abaixo; depois ajuste a ordem aqui."));
            return;
        }
        order.forEach((id, index) => {
            const item = element("li", "combo-form__ordem-item");
            item.append(element("span", "", `${index + 1}. ${nameOf(id)}`));
            const move = (delta, text, label) => {
                const button = element("button", "btn-small", text);
                button.type = "button";
                button.setAttribute("aria-label", `${label}: ${nameOf(id)}`);
                button.disabled = index + delta < 0 || index + delta >= order.length;
                button.addEventListener("click", () => {
                    [order[index], order[index + delta]] = [order[index + delta], order[index]];
                    renderOrder();
                    orderList.querySelectorAll("button")[Math.max(0, (index + delta) * 2 + (delta > 0 ? 1 : 0))]?.focus();
                });
                return button;
            };
            item.append(move(-1, "↑", "Mover para cima"), move(1, "↓", "Mover para baixo"));
            orderList.append(item);
        });
    };
    const updateSum = () => {
        const total = state.servicos.filter(servico => selected.has(servico.id))
            .reduce((acc, servico) => acc + Math.round(Number(servico.valor_base || 0) * 100), 0) / 100;
        sum.textContent = `Soma dos serviços escolhidos: ${money(total)} (${selected.size} serviços)`;
        useSum.onclick = () => { price.value = total.toFixed(2); };
    };

    const services = element("fieldset", "combo-form__servicos");
    services.append(element("legend", "", "Serviços do combo (mínimo 2)"));
    state.servicos.forEach(servico => {
        const label = element("label", "combo-form__servico");
        const box = element("input");
        box.type = "checkbox";
        box.value = String(servico.id);
        box.checked = selected.has(servico.id);
        box.addEventListener("change", () => {
            const at = order.indexOf(servico.id);
            if (box.checked && at < 0) order.push(servico.id);
            if (!box.checked && at >= 0) order.splice(at, 1);
            updateSum();
            renderOrder();
        });
        label.append(box, document.createTextNode(` ${servico.nome} — ${money(servico.valor_base)}`));
        services.append(label);
    });
    updateSum();
    renderOrder();
    const orderBox = element("fieldset", "combo-form__servicos");
    orderBox.append(element("legend", "", "Ordem dos serviços no combo"), orderList);

    const activeLabel = element("label", "combo-form__check");
    activeLabel.append(active, document.createTextNode(" Ativo (aparece no site e em novas propostas)"));
    const feedback = element("p", "combo-form__feedback");
    feedback.setAttribute("role", "status");
    const actions = element("div", "combo-form__actions");
    const save = element("button", "btn-cta", "Salvar combo");
    save.type = "submit";
    const cancel = element("button", "btn-outline", "Cancelar");
    cancel.type = "button";
    cancel.addEventListener("click", closeEditor);
    actions.append(save, cancel);

    form.append(
        field("Nome", name),
        field("Subtítulo do botão", subtitle),
        field("Descrição", description),
        field("Preço (R$)", price),
        field("Aplicar desconto?", discount),
        field("Destaques do combo (um por linha, até 20)", highlights),
        sum,
        useSum,
        services,
        orderBox,
        activeLabel,
        feedback,
        actions,
    );
    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (state.busy) return;
        const ordered = [...order];
        if (name.value.trim().length < 3) { feedback.textContent = "Informe um nome com pelo menos 3 letras."; return; }
        if (price.value === "" || Number(price.value) < 0) { feedback.textContent = "Informe o preço do combo."; return; }
        if (ordered.length < 2) { feedback.textContent = "Escolha pelo menos dois serviços."; return; }
        state.busy = true;
        save.disabled = true;
        feedback.textContent = "Salvando...";
        try {
            const payload = {
                nome: name.value.trim(),
                descricao: description.value.trim(),
                subtitulo: subtitle.value.trim(),
                preco_base: Number(price.value).toFixed(2),
                aplica_desconto: discount.value === "true",
                destaques: highlights.value.split("\n").map(item => item.trim().slice(0, 200)).filter(Boolean).slice(0, 20),
                ativo: active.checked,
                servicos: ordered,
            };
            const path = combo ? `/combos/${combo.id}` : "/combos";
            await request(path, { method: combo ? "PUT" : "POST", body: JSON.stringify(payload) });
            Notify.success(combo ? "Combo atualizado." : "Combo criado.");
            closeEditor();
            await carregarCombos(state.servicos);
        } catch (error) {
            feedback.textContent = error.message;
        } finally {
            state.busy = false;
            save.disabled = false;
        }
    });
    editor.append(form);
    name.focus();
}

export async function carregarCombos(servicos = []) {
    state.servicos = Array.isArray(servicos) ? servicos : [];
    const list = byId("combos-list");
    if (!list) return;
    try {
        const combos = await request("/combos");
        state.combos = Array.isArray(combos) ? combos : [];
        renderList();
    } catch (error) {
        list.replaceChildren(element("p", "admin-help", "Não foi possível carregar os combos agora."));
    }
}

function init() {
    const button = byId("combo-novo");
    if (button && !button.dataset.bound) {
        button.dataset.bound = "true";
        button.addEventListener("click", () => openEditor(null));
    }
}

init();
