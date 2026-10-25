import { authFetch } from "../auth.js";

// Admin "Uso da infraestrutura": numbers only; credentials never reach the browser.
let carregando = null;

function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

function bytes(value) {
    const units = ["B", "KB", "MB", "GB", "TB"];
    let number = Number(value) || 0;
    let index = 0;
    while (number >= 1024 && index < units.length - 1) { number /= 1024; index += 1; }
    return `${number.toLocaleString("pt-BR", { maximumFractionDigits: index ? 1 : 0 })} ${units[index]}`;
}

function formato(valor, unidade) {
    if (valor === null || valor === undefined) return "—";
    if (unidade === "bytes") return bytes(valor);
    if (unidade === "creditos") return `${Number(valor).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} créditos`;
    return Number(valor).toLocaleString("pt-BR");
}

function item(dado) {
    const row = element("div", "uso-item");
    const head = element("div", "uso-item__head");
    head.append(element("span", "uso-item__label", dado.rotulo));
    const limite = Number(dado.limite);
    const temLimite = Number.isFinite(limite) && limite > 0;
    head.append(element("strong", "", temLimite
        ? `${formato(dado.usado, dado.unidade)} de ${formato(limite, dado.unidade)}`
        : formato(dado.usado, dado.unidade)));
    row.append(head);
    if (temLimite) {
        const percentual = Math.min(100, Math.max(0, (Number(dado.usado) || 0) / limite * 100));
        const bar = element("div", `uso-bar${percentual >= 90 ? " uso-bar--danger" : percentual >= 75 ? " uso-bar--warning" : ""}`);
        bar.setAttribute("role", "meter");
        bar.setAttribute("aria-label", dado.rotulo);
        bar.setAttribute("aria-valuemin", "0");
        bar.setAttribute("aria-valuemax", "100");
        bar.setAttribute("aria-valuenow", String(Math.round(percentual)));
        bar.setAttribute("aria-valuetext", `${Math.round(percentual)}% usado`);
        const fill = element("span", "uso-bar__fill");
        fill.style.width = `${percentual}%`;
        bar.append(fill);
        row.append(bar, element("span", "uso-item__percent", `${Math.round(percentual)}% usado`));
    }
    if (dado.detalhe) row.append(element("span", "uso-item__detail", dado.detalhe));
    return row;
}

function bloco(dado) {
    const card = element("section", `uso-card uso-card--${dado.status}`);
    const title = element("h2", "", dado.nome);
    card.append(title);
    if (dado.plano) card.append(element("p", "uso-card__plan", `Plano: ${dado.plano}`));
    if (dado.status !== "ok") {
        card.append(element("p", "uso-card__message", dado.mensagem || "Indisponível no momento."));
        return card;
    }
    (dado.itens || []).forEach(entry => card.append(item(entry)));
    (dado.avisos || []).forEach(aviso => card.append(element("p", "uso-card__message", aviso)));
    return card;
}

export async function carregarUso({ atualizar = false } = {}) {
    if (carregando) return carregando;
    const host = document.getElementById("uso-content");
    const updated = document.getElementById("uso-updated");
    if (!host) return null;
    updated.textContent = "Carregando...";
    carregando = (async () => {
        try {
            const response = await authFetch(`/admin/uso${atualizar ? "?atualizar=true" : ""}`);
            const data = await response.json().catch(() => null);
            if (!response.ok || !Array.isArray(data?.blocos)) throw new Error("uso_indisponivel");
            host.replaceChildren(...data.blocos.map(bloco));
            const when = new Date(data.atualizado_em);
            updated.textContent = Number.isNaN(when.getTime())
                ? ""
                : `Atualizado em ${when.toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" })}. Os números ficam guardados por 5 minutos.`;
            return data;
        } catch {
            host.replaceChildren(element("p", "uso-card__message", "Não foi possível carregar o uso agora."));
            updated.textContent = "";
            return null;
        } finally {
            carregando = null;
        }
    })();
    return carregando;
}

export function initUso() {
    const refresh = document.getElementById("uso-refresh");
    if (refresh && !refresh.dataset.bound) {
        refresh.dataset.bound = "true";
        refresh.addEventListener("click", () => carregarUso({ atualizar: true }));
    }
    return carregarUso();
}
