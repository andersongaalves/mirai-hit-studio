// Roadmap 3.0, 5.01: admin editor for versioned portal settings.
import { authFetch } from "../auth.js";
import * as Notify from "../../utils/notifications.js";

const LABELS = {
    cliente: {
        indicadores: {
            andamento: "Projetos em andamento",
            concluidos: "Projetos concluídos",
            avaliacao: "Em avaliação",
            pagamentos: "Pagamentos pendentes",
        },
        textos: {
            titulo_dashboard: ["Título do dashboard", 80, false],
            descricao_dashboard: ["Descrição do dashboard", 240, true],
            ajuda_arquivos: ["Ajuda na área de arquivos", 240, true],
        },
        filtros: {
            situacao_padrao: ["Situação inicial da lista", {
                todos: "Todos", ativos: "Em andamento", concluidos: "Concluídos", revisao: "Em avaliação",
            }],
            ordenacao_padrao: ["Ordenação inicial", { recente: "Atualização recente", prazo: "Prazo mais próximo" }],
        },
        areas: { propostas: "Mostrar a área de propostas" },
    },
    produtor: {
        indicadores: {
            ativas: "Produções ativas",
            revisao: "Em revisão",
            vencidos: "Prazos vencidos",
            a_receber: "A receber",
            pago: "Total pago",
        },
        textos: {
            descricao_dashboard: ["Descrição do dashboard", 240, true],
            ajuda_financeiro: ["Ajuda na área financeira", 240, true],
        },
        filtros: {
            status_padrao: ["Status inicial da lista", {
                todos: "Todos", aguardando_inicio: "Aguardando início", em_producao: "Em produção",
                revisao: "Em revisão", finalizado: "Finalizadas", entregue: "Entregues",
            }],
            ordenacao_padrao: ["Ordenação inicial", { prazo: "Prazo mais próximo", recente: "Atualização recente" }],
        },
        areas: {},
    },
};

const state = { portal: "cliente", versao: 0, padrao: null, loaded: false, busy: false };
const byId = id => document.getElementById(id);

function node(tag, text = "", className = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text) element.textContent = text;
    return element;
}

function field(labelText, control) {
    const label = node("label", "", "portal-settings__field");
    label.append(node("span", labelText), control);
    return label;
}

function fieldset(legend, ...children) {
    const group = node("fieldset", "", "portal-settings__group");
    group.append(node("legend", legend), ...children);
    return group;
}

function textControl(name, value, maxLength, multiline) {
    const control = document.createElement(multiline ? "textarea" : "input");
    if (multiline) control.rows = 2;
    else control.type = "text";
    control.name = name;
    control.maxLength = maxLength;
    control.value = value ?? "";
    return control;
}

function selectControl(name, options, value) {
    const select = document.createElement("select");
    select.name = name;
    Object.entries(options).forEach(([optionValue, label]) => select.append(new Option(label, optionValue)));
    select.value = value;
    return select;
}

function checkbox(name, checked, value = "") {
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = name;
    input.checked = Boolean(checked);
    if (value) input.value = value;
    return input;
}

function renderForm(config) {
    const labels = LABELS[state.portal];
    const form = byId("portal-settings-form");
    form.replaceChildren();

    const noticeActive = checkbox("aviso.ativo", config.aviso.ativo);
    const activeLabel = node("label", "", "portal-settings__check");
    activeLabel.append(noticeActive, document.createTextNode(" Exibir aviso no topo do portal"));
    form.append(fieldset(
        "Aviso",
        activeLabel,
        field("Tipo", selectControl("aviso.nivel", { info: "Informativo", atencao: "Atenção" }, config.aviso.nivel)),
        field("Texto do aviso (até 280 caracteres)", textControl("aviso.texto", config.aviso.texto, 280, true)),
    ));

    form.append(fieldset("Textos", ...Object.entries(labels.textos).map(([key, [label, max, multiline]]) => (
        field(label, textControl(`textos.${key}`, config.textos[key], max, multiline))
    ))));

    const indicators = node("div", "", "portal-settings__checks");
    Object.entries(labels.indicadores).forEach(([key, label]) => {
        const wrapper = node("label", "", "portal-settings__check");
        wrapper.append(checkbox("indicadores", config.indicadores.includes(key), key), document.createTextNode(` ${label}`));
        indicators.append(wrapper);
    });
    form.append(fieldset("Indicadores do dashboard", indicators));

    form.append(fieldset("Filtros iniciais", ...Object.entries(labels.filtros).map(([key, [label, options]]) => (
        field(label, selectControl(`filtros.${key}`, options, config.filtros[key]))
    ))));

    const areaEntries = Object.entries(labels.areas);
    if (areaEntries.length) {
        form.append(fieldset("Áreas visíveis", ...areaEntries.map(([key, label]) => {
            const wrapper = node("label", "", "portal-settings__check");
            wrapper.append(checkbox(`areas.${key}`, config.areas?.[key]), document.createTextNode(` ${label}`));
            return wrapper;
        })));
    }
}

function readForm() {
    const labels = LABELS[state.portal];
    const form = byId("portal-settings-form");
    const value = name => form.elements.namedItem(name);
    const config = {
        aviso: {
            ativo: value("aviso.ativo").checked,
            nivel: value("aviso.nivel").value,
            texto: value("aviso.texto").value,
        },
        textos: Object.fromEntries(Object.keys(labels.textos).map(key => [key, value(`textos.${key}`).value])),
        // Keep the canonical order of the indicators the admin selected.
        indicadores: Object.keys(labels.indicadores).filter(key => (
            [...form.querySelectorAll('input[name="indicadores"]')].some(input => input.value === key && input.checked)
        )),
        filtros: Object.fromEntries(Object.keys(labels.filtros).map(key => [key, value(`filtros.${key}`).value])),
    };
    if (Object.keys(labels.areas).length) {
        config.areas = Object.fromEntries(Object.keys(labels.areas).map(key => [key, value(`areas.${key}`).checked]));
    }
    return config;
}

function formatDate(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "" : date.toLocaleString("pt-BR");
}

async function responseData(response, fallback) {
    const data = await response.json().catch(() => null);
    if (!response.ok) {
        const error = new Error(typeof data?.detail === "string" ? data.detail : fallback);
        error.status = response.status;
        throw error;
    }
    return data;
}

function renderVersions(versions) {
    const list = byId("portal-settings-versions");
    list.replaceChildren();
    if (!versions.length) {
        list.append(node("li", "Nenhuma versão publicada; o portal usa os valores padrão."));
        return;
    }
    versions.forEach(item => {
        const row = node("li");
        const origin = item.restaurada_de_versao ? ` · restaurada da v${item.restaurada_de_versao}` : "";
        row.append(node("span", `v${item.versao} · ${formatDate(item.created_at)}${origin}`));
        if (item.versao !== state.versao) {
            const restore = node("button", "Restaurar", "btn-small");
            restore.type = "button";
            restore.addEventListener("click", () => restoreVersion(item.versao, restore));
            row.append(restore);
        } else {
            row.append(node("strong", "Em uso"));
        }
        list.append(row);
    });
}

async function load() {
    const portal = state.portal;
    const [current, versions] = await Promise.all([
        authFetch(`/admin/portais/${portal}/configuracao`).then(response => responseData(response, "Não foi possível carregar a configuração.")),
        authFetch(`/admin/portais/${portal}/configuracao/versoes`).then(response => responseData(response, "Não foi possível carregar o histórico.")),
    ]);
    if (portal !== state.portal) return;
    state.versao = current.versao;
    state.padrao = current.padrao;
    byId("portal-settings-version").textContent = current.versao
        ? `Versão em uso: v${current.versao}`
        : "Nenhuma versão publicada: o portal usa os valores padrão.";
    renderForm(current.config);
    renderVersions(versions);
    state.loaded = true;
}

async function run(button, action, message) {
    if (state.busy) return;
    state.busy = true;
    button.disabled = true;
    try {
        await action();
        if (message) Notify.success(message);
        await load();
    } catch (error) {
        Notify.error(error.message || "Não foi possível concluir a operação.");
        if (error.status === 409) await load().catch(() => {});
    } finally {
        state.busy = false;
        button.disabled = false;
    }
}

function publish(button) {
    const config = readForm();
    if (!config.indicadores.length) {
        Notify.error("Selecione ao menos um indicador.");
        return;
    }
    return run(button, async () => {
        await responseData(await authFetch(`/admin/portais/${state.portal}/configuracao`, {
            method: "PUT",
            body: JSON.stringify({ base_versao: state.versao, config }),
        }), "Não foi possível publicar a configuração.");
    }, "Configuração publicada.");
}

function restoreVersion(versao, button) {
    return run(button, async () => {
        await responseData(await authFetch(`/admin/portais/${state.portal}/configuracao/versoes/${versao}/restaurar`, {
            method: "POST",
            body: JSON.stringify({ base_versao: state.versao }),
        }), "Não foi possível restaurar a versão.");
    }, `Versão v${versao} restaurada como nova versão.`);
}

function init() {
    const tab = byId("admin-config-portals-tab");
    if (!tab) return;
    const ensureLoaded = () => {
        if (!state.loaded) load().catch(error => Notify.error(error.message));
    };
    tab.addEventListener("click", ensureLoaded);
    tab.addEventListener("focus", ensureLoaded);
    byId("portal-settings-portal").addEventListener("change", event => {
        state.portal = event.target.value;
        state.loaded = false;
        load().catch(error => Notify.error(error.message));
    });
    byId("portal-settings-defaults").addEventListener("click", () => {
        if (state.padrao) renderForm(state.padrao);
    });
    byId("portal-settings-publish").addEventListener("click", event => publish(event.currentTarget));
    document.addEventListener("admin:logout", () => {
        state.loaded = false;
        state.versao = 0;
        byId("portal-settings-form").replaceChildren();
        byId("portal-settings-versions").replaceChildren();
    });
}

init();
