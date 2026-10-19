const element = (tag, className, text) => {
    const node = document.createElement(tag);
    node.className = className;
    node.textContent = text || "";
    return node;
};

export function creditQuantity(value, unit) {
    const text = String(value);
    if (!/^\d+(\.\d{1,3})?$/.test(text)) return "Indisponível";
    const [whole, decimal = ""] = text.split(".");
    const fraction = decimal.replace(/0+$/, "");
    const number = new Intl.NumberFormat("pt-BR").format(BigInt(whole)) + (fraction ? `,${fraction}` : "");
    const plurals = { faixa: "faixas", canal: "canais", hora: "horas" };
    return `${number} ${number === "1" ? unit : plurals[unit] || unit}`;
}

export function renderServiceCredits(root, data, { emptyText = "Você ainda não possui créditos de serviços." } = {}) {
    root.classList.add("service-credit-wallet");
    root.replaceChildren();
    if (!data.saldos?.length) {
        root.append(element("p", "producer-empty", emptyText));
        return;
    }
    const list = element("div", "client-credit-balances");
    data.saldos.forEach(saldo => {
        const item = element("article", "client-credit-balance");
        item.append(element("h2", "", saldo.servico_nome),
            element("p", "", `Disponíveis: ${creditQuantity(saldo.disponivel, saldo.unidade)}`));
        if (Number(saldo.bloqueado) > 0) item.append(element("p", "producer-help", `Em conciliação: ${creditQuantity(saldo.bloqueado, saldo.unidade)}`));
        if (Number(saldo.reservado) > 0) item.append(element("p", "", `Reservados: ${creditQuantity(saldo.reservado, saldo.unidade)}`));
        if (Number(saldo.consumido) > 0) item.append(element("p", "producer-help", `Utilizados: ${creditQuantity(saldo.consumido, saldo.unidade)}`));
        list.append(item);
    });
    root.append(list, element("h2", "", "Aquisições"));
    const history = element("ul", "client-credit-history");
    data.lotes.forEach(lote => {
        const status = lote.estado === "disponivel" ? "Disponível" : "Em conciliação";
        const date = lote.created_at ? new Date(lote.created_at) : null;
        const when = date && !Number.isNaN(date.getTime()) ? date.toLocaleDateString("pt-BR") : "Data não informada";
        history.append(element("li", "", `${lote.servico_nome} · ${creditQuantity(lote.quantidade, lote.unidade)} · Proposta #${lote.proposta_id} · ${status} · ${when}`));
    });
    root.append(history);
}
