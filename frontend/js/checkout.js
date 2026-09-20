import { API_URL } from "./config.js";
import { initAnalytics, track, trackOnce } from "./analytics.js";

const $ = id => document.getElementById(id);
const TOKEN_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const state = {
    token: null,
    summary: null,
    option: null,
    method: "pix",
    busy: false,
    cardController: null,
    polling: null,
    pollCount: 0,
};

function money(value) {
    return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
}

function readToken() {
    const parts = location.pathname.split("/").filter(Boolean);
    const token = parts[0] === "checkout" ? parts[1] : null;
    return TOKEN_PATTERN.test(token ?? "") ? token : null;
}

async function api(path, options = {}) {
    const response = await fetch(`${API_URL}/${path}`, options);
    if (!response.ok) {
        let message = "Não foi possível concluir a operação.";
        try {
            const body = await response.json();
            if (typeof body.detail === "string") message = body.detail;
        } catch {}
        const error = new Error(message);
        error.status = response.status;
        throw error;
    }
    return response.json();
}

function setHidden(id, hidden) {
    $(id).classList.toggle("hidden", hidden);
}

function showError(message, retry = false) {
    stopPolling();
    $("checkout-error-message").textContent = message;
    setHidden("checkout-loading", true);
    setHidden("checkout-content", true);
    setHidden("checkout-error", false);
    setHidden("checkout-retry", !retry);
}

function renderOptions(options) {
    const host = $("payment-options");
    host.querySelectorAll("label").forEach(element => element.remove());
    for (const [index, option] of options.entries()) {
        const label = document.createElement("label");
        label.className = "checkout-option";
        const input = document.createElement("input");
        input.type = "radio";
        input.name = "payment_option";
        input.value = option.tipo;
        input.checked = option.tipo === state.option || (!state.option && index === 0);
        input.addEventListener("change", async () => {
            state.option = option.tipo;
            if (state.method === "card") await renderCard();
        });
        const title = document.createElement("span");
        title.textContent = option.titulo;
        const value = document.createElement("strong");
        value.textContent = money(option.valor);
        label.append(input, title, value);
        host.appendChild(label);
    }
    state.option = host.querySelector("input:checked")?.value ?? null;
}

function renderSummary(summary) {
    state.summary = summary;
    $("proposal-number").textContent = `Proposta ${summary.proposta_numero}`;
    $("project-description").textContent = summary.descricao;
    $("total-value").textContent = money(summary.valor_total);
    $("paid-value").textContent = money(summary.valor_pago);
    $("balance-value").textContent = money(summary.saldo);
    setHidden("paid-row", Number(summary.valor_pago) <= 0);
    renderOptions(summary.opcoes);
    renderTerminal(summary.status, summary.saldo);
}

function renderTerminal(status, balance) {
    const terminal = $("checkout-terminal");
    const form = $("checkout-form");
    terminal.dataset.kind = "";
    if (status === "paga") {
        terminal.textContent = "Pagamento confirmado. Obrigado!";
        terminal.dataset.kind = "success";
        terminal.classList.remove("hidden");
        form.classList.add("hidden");
        stopPolling();
    } else if (status === "cancelada") {
        terminal.textContent = "Esta cobrança foi cancelada.";
        terminal.dataset.kind = "warning";
        terminal.classList.remove("hidden");
        form.classList.add("hidden");
        stopPolling();
    } else if (status === "parcialmente_paga") {
        terminal.textContent = `Entrada confirmada. Saldo restante: ${money(balance)}.`;
        terminal.dataset.kind = "success";
        terminal.classList.remove("hidden");
        form.classList.remove("hidden");
    } else {
        terminal.classList.add("hidden");
        form.classList.remove("hidden");
    }
}

function setBusy(busy, text = "") {
    state.busy = busy;
    $("generate-pix").disabled = busy;
    $("generate-pix").textContent = busy ? text : "Gerar Pix";
}

function safeHttps(value) {
    try {
        const url = new URL(value);
        return url.protocol === "https:" ? url.href : "";
    } catch {
        return "";
    }
}

function renderPayment(result) {
    const message = $("payment-result");
    message.classList.remove("hidden");
    message.dataset.kind = result.status === "approved" ? "success" : "warning";
    if (result.status === "approved") {
        message.textContent = result.checkout_status === "parcialmente_paga"
            ? "Entrada confirmada. O saldo permanece disponível neste checkout."
            : "Pagamento confirmado.";
    } else if (result.status === "rejected") {
        message.textContent = "O pagamento não foi aprovado. Revise os dados ou tente outra forma de pagamento.";
    } else if (result.status === "action_required") {
        message.textContent = "Confirme a compra com seu banco.";
    } else {
        message.textContent = "Pagamento em processamento. A confirmação será atualizada automaticamente.";
    }
    renderPix(result.pix);
    renderChallenge(result.challenge_url);
    if (["pending", "action_required"].includes(result.status)) startPolling();
    if (result.status === "approved") refreshSummary();
}

function renderPix(pix) {
    setHidden("pix-result", !pix);
    if (!pix) return;
    const image = $("pix-qr");
    const base64 = typeof pix.qr_code_base64 === "string" && /^[A-Za-z0-9+/=\r\n]+$/.test(pix.qr_code_base64)
        ? pix.qr_code_base64.replace(/\s/g, "") : "";
    image.src = base64 ? `data:image/png;base64,${base64}` : "";
    image.classList.toggle("hidden", !base64);
    $("pix-code").value = pix.qr_code || "";
    setHidden("pix-code", !pix.qr_code);
    setHidden("copy-pix", !pix.qr_code);
    const ticket = safeHttps(pix.ticket_url);
    $("pix-ticket").href = ticket;
    setHidden("pix-ticket", !ticket);
    $("pix-expiration").textContent = pix.expiration_time ? `Válido até ${pix.expiration_time}.` : "";
}

function isMercadoPagoUrl(value) {
    const url = safeHttps(value);
    if (!url) return "";
    const host = new URL(url).hostname.toLowerCase();
    return host === "mercadopago.com" || host.startsWith("www.mercadopago.") || host.includes(".mercadopago.") ? url : "";
}

function renderChallenge(value) {
    const url = isMercadoPagoUrl(value);
    setHidden("challenge-container", !url);
    $("challenge-frame").src = url || "about:blank";
}

async function generatePix() {
    if (state.busy || !state.option) return;
    setBusy(true, "Gerando Pix...");
    try {
        const result = await api(`checkout/${state.token}/pix`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ payment_option: state.option }),
        });
        track("payment_attempt", { payment_method: "pix", payment_option: state.option, outcome: result.status });
        renderPayment(result);
    } catch (error) {
        $("payment-result").textContent = error.status === 409
            ? error.message
            : "Não foi possível gerar o Pix agora. Tente novamente.";
        $("payment-result").dataset.kind = "warning";
        setHidden("payment-result", false);
    } finally {
        setBusy(false);
    }
}

async function loadMercadoPago() {
    if (window.MercadoPago) return;
    await new Promise((resolve, reject) => {
        const existing = document.querySelector("script[data-mercado-pago-sdk]");
        if (existing) {
            existing.addEventListener("load", resolve, { once: true });
            existing.addEventListener("error", reject, { once: true });
            return;
        }
        const script = document.createElement("script");
        script.src = "https://sdk.mercadopago.com/js/v2";
        script.dataset.mercadoPagoSdk = "true";
        script.addEventListener("load", resolve, { once: true });
        script.addEventListener("error", reject, { once: true });
        document.head.appendChild(script);
    });
}

async function renderCard() {
    const error = $("card-error");
    error.textContent = "";
    error.classList.add("hidden");
    $("card-loading").classList.remove("hidden");
    try {
        await state.cardController?.unmount?.();
        state.cardController = null;
        await loadMercadoPago();
        const config = await api("checkout/config");
        const current = state.summary.opcoes.find(option => option.tipo === state.option);
        if (!current) throw new Error("Opção de pagamento indisponível.");
        const mp = new window.MercadoPago(config.mercado_pago_public_key, { locale: "pt-BR" });
        state.cardController = await mp.bricks().create("cardPayment", "card-payment-brick", {
            initialization: { amount: Number(current.valor) },
            callbacks: {
                onReady: () => $("card-loading").classList.add("hidden"),
                onError: () => {
                    error.textContent = "Não foi possível carregar o formulário do cartão.";
                    error.classList.remove("hidden");
                },
                onSubmit: (formData, additionalData) => processCard(formData, additionalData),
            },
        });
    } catch {
        $("card-loading").classList.add("hidden");
        error.textContent = "Pagamento por cartão indisponível agora. O Pix continua disponível.";
        error.classList.remove("hidden");
    }
}

async function processCard(formData, additionalData) {
    if (state.busy) throw new Error("payment_in_progress");
    state.busy = true;
    try {
        const identification = formData.payer?.identification ?? {};
        const result = await api(`checkout/${state.token}/card`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                payment_option: state.option,
                card_token: formData.token,
                payment_method_id: formData.payment_method_id,
                payment_method_type: additionalData.paymentTypeId,
                installments: Number(formData.installments),
                payer_email: formData.payer?.email || null,
                identification_type: identification.type || null,
                identification_number: identification.number || null,
            }),
        });
        track("payment_attempt", { payment_method: "card", payment_option: state.option, outcome: result.status });
        renderPayment(result);
    } catch (error) {
        $("card-error").textContent = error.status === 409
            ? error.message
            : "Não foi possível processar o cartão agora. Tente novamente.";
        $("card-error").classList.remove("hidden");
        throw error;
    } finally {
        state.busy = false;
    }
}

async function refreshSummary() {
    const summary = await api(`checkout/${state.token}`);
    renderSummary(summary);
}

async function refreshStatus() {
    if (document.hidden) return;
    try {
        const current = await api(`checkout/${state.token}/status`);
        renderTerminal(current.status, current.saldo);
        if (["paga", "cancelada"].includes(current.status) || current.pagamento_status === "recusado") {
            stopPolling();
            await refreshSummary();
        }
    } catch {
        // A falha temporaria de polling nao altera o estado exibido nem financeiro.
    }
}

function startPolling() {
    if (state.polling) return;
    state.pollCount = 0;
    state.polling = window.setInterval(async () => {
        state.pollCount += 1;
        if (state.pollCount > 120) return stopPolling();
        await refreshStatus();
    }, 5000);
}

function stopPolling() {
    if (state.polling) window.clearInterval(state.polling);
    state.polling = null;
}

async function resumePending(summary) {
    if (!summary.tentativa) return;
    if (!summary.tentativa.recuperavel) {
        $("payment-result").textContent = "Pagamento em análise. Aguarde a conciliação antes de tentar novamente.";
        setHidden("payment-result", false);
        startPolling();
        return;
    }
    try {
        renderPayment(await api(`checkout/${state.token}/pending-payment`));
    } catch {
        $("payment-result").textContent = "Pagamento em processamento. O status será atualizado automaticamente.";
        setHidden("payment-result", false);
        startPolling();
    }
}

async function loadCheckout() {
    setHidden("checkout-loading", false);
    setHidden("checkout-error", true);
    try {
        state.token = readToken();
        if (!state.token) throw new Error("Link de checkout inválido.");
        const summary = await api(`checkout/${state.token}`);
        renderSummary(summary);
        setHidden("checkout-loading", true);
        setHidden("checkout-content", false);
        trackOnce("begin_checkout", {});
        await resumePending(summary);
    } catch (error) {
        showError(error.message || "Não foi possível carregar este checkout.", true);
    }
}

function selectMethod(method) {
    state.method = method;
    for (const name of ["pix", "card"]) {
        const selected = name === method;
        $(`method-${name}`).classList.toggle("is-active", selected);
        $(`method-${name}`).setAttribute("aria-pressed", String(selected));
        setHidden(`${name}-panel`, !selected);
    }
    track("payment_method_selected", { payment_method: method });
    if (method === "card") renderCard();
}

$("method-pix").addEventListener("click", () => selectMethod("pix"));
$("method-card").addEventListener("click", () => selectMethod("card"));
$("generate-pix").addEventListener("click", generatePix);
$("checkout-retry").addEventListener("click", loadCheckout);
$("copy-pix").addEventListener("click", async () => {
    try {
        await navigator.clipboard.writeText($("pix-code").value);
        $("copy-pix").textContent = "Código copiado";
    } catch {
        $("pix-code").focus();
        $("pix-code").select();
    }
});
window.addEventListener("message", event => {
    if (!isMercadoPagoUrl(event.origin) || event.data?.status !== "COMPLETE") return;
    refreshStatus();
});
window.addEventListener("pagehide", stopPolling);

initAnalytics();
loadCheckout();
