import { API_URL } from "./config.js";
import { initAnalytics, track, trackOnce } from "./analytics.js";
import { AUTH_CONTEXTS, createAuthContext } from "./admin/auth.js";
import { pixImageMime, validatePixPayload } from "./pix.js";
import { initComponents } from "./modules/components.js";

const $ = id => document.getElementById(id);
const TOKEN_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const DEVICE_ID_PATTERN = /^[A-Za-z0-9._:-]{1,256}$/;
const CHALLENGE_HOSTS = new Set([
    "www.mercadopago.com", "www.mercadopago.com.ar",
]);
let sdkLoadPromise = null;
let deviceLoadPromise = null;
const state = {
    token: null,
    proposalId: null,
    summary: null,
    option: null,
    method: "pix",
    busy: false,
    cardController: null,
    cardRenderId: 0,
    cardUnmount: Promise.resolve(),
    polling: null,
    pollCount: 0,
};
const clientAuth = createAuthContext(AUTH_CONTEXTS.cliente);

function money(value) {
    return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
}

function readToken() {
    const parts = location.pathname.split("/").filter(Boolean);
    const token = parts[0] === "checkout" ? parts[1] : null;
    return TOKEN_PATTERN.test(token ?? "") ? token : null;
}

function readProposalId() {
    const value = new URLSearchParams(location.search).get("proposta");
    return /^\d+$/.test(value || "") && Number(value) > 0 ? Number(value) : null;
}

function authenticatedPath(path) {
    const base = `/portal/cliente/propostas/${state.proposalId}/checkout`;
    if (path === "checkout/config") return path;
    if (path === `checkout/${state.token}`) return base;
    if (path === `checkout/${state.token}/status`) return `${base}/status`;
    if (path === `checkout/${state.token}/pending-payment`) return `${base}/pending-payment`;
    if (path === `checkout/${state.token}/pix`) return `${base}/pix`;
    if (path === `checkout/${state.token}/card`) return `${base}/card`;
    return path;
}

async function api(path, options = {}) {
    const endpoint = state.proposalId ? authenticatedPath(path) : path;
    const response = state.proposalId
        ? await clientAuth.authFetch(endpoint, options)
        : await fetch(`${API_URL}/${endpoint}`, options);
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
    const challengeAvailable = renderChallenge(result.challenge_url);
    message.classList.remove("hidden");
    message.dataset.kind = result.status === "approved" ? "success" : "warning";
    if (result.status === "approved") {
        message.textContent = result.checkout_status === "parcialmente_paga"
            ? "Entrada confirmada. O saldo permanece disponível neste checkout."
            : "Pagamento confirmado.";
    } else if (result.status === "rejected") {
        message.textContent = "O pagamento não foi aprovado. Revise os dados ou tente outra forma de pagamento.";
    } else if (result.status === "action_required") {
        message.textContent = challengeAvailable
            ? "Confirme a compra com seu banco."
            : "A autenticação do cartão não pôde ser exibida. Aguarde a atualização do pagamento antes de tentar novamente.";
    } else {
        message.textContent = "Pagamento em processamento. A confirmação será atualizada automaticamente.";
    }
    renderPix(result.pix, result.status, result.valor);
    if (["pending", "action_required"].includes(result.status)) startPolling();
    if (result.status === "approved") refreshSummary();
}

function renderPix(pix, status, amount) {
    setHidden("pix-result", !pix);
    if (!pix) return;
    const validationError = validatePixPayload(pix.qr_code, amount);
    const expiresAt = pix.expiration_time ? new Date(pix.expiration_time) : null;
    const expired = expiresAt && Number.isFinite(expiresAt.getTime()) && expiresAt.getTime() <= Date.now();
    const payable = ["pending", "action_required"].includes(status) && !expired;
    const validCode = payable && !validationError;
    if (validationError) diagnostic("pix_validation", validationError);
    if (expired) diagnostic("pix_lifecycle", "expired");
    const image = $("pix-qr");
    const base64 = validCode && typeof pix.qr_code_base64 === "string"
        ? pix.qr_code_base64.replace(/\s/g, "") : "";
    const mime = pixImageMime(base64);
    if (validCode && base64 && !mime) diagnostic("pix_qr_image", "invalid_image_data");
    image.src = mime ? `data:${mime};base64,${base64}` : "";
    image.classList.toggle("hidden", !mime);
    $("pix-code").value = validCode ? pix.qr_code : "";
    setHidden("pix-code", !validCode);
    setHidden("copy-pix", !validCode);
    const ticket = payable ? safeHttps(pix.ticket_url) : "";
    $("pix-ticket").href = ticket;
    setHidden("pix-ticket", !ticket);
    $("pix-expiration").textContent = expiresAt && Number.isFinite(expiresAt.getTime())
        ? `Válido até ${new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(expiresAt)} (horário local).` : "";
    const validationMessage = $("pix-validation-message");
    if (expired) {
        validationMessage.textContent = "Este Pix expirou. Não pague nem tente gerar outra cobrança; consulte o suporte para verificar o estado do pagamento.";
    } else if (!payable && status !== "approved") {
        validationMessage.textContent = "Esta tentativa não está mais disponível para pagamento. Consulte o estado atualizado antes de tentar novamente.";
    } else if (!validCode && status !== "approved") {
        validationMessage.textContent = "O provedor retornou um código Pix inválido. Não copie nem pague este código; a tentativa foi preservada para verificação.";
    } else if (!mime && validCode) {
        validationMessage.textContent = "A imagem do QR Code não pôde ser validada. Use o código Pix conferido ou o link do Mercado Pago.";
    } else {
        validationMessage.textContent = "";
    }
    setHidden("pix-validation-message", !validationMessage.textContent);
}

function isMercadoPagoUrl(value) {
    if (typeof value !== "string" || !value || value.length > 2000 || /[\u0000-\u0020\u007f\\]/.test(value)) return "";
    const authority = /^https:\/\/([^/?#]+)(?:[/?#]|$)/i.exec(value)?.[1];
    if (!authority || !CHALLENGE_HOSTS.has(authority.toLowerCase())) return "";
    try {
        const url = new URL(value);
        return url.protocol === "https:" && !url.username && !url.password && !url.port && !url.hash
            && CHALLENGE_HOSTS.has(url.hostname.toLowerCase()) ? url.href : "";
    } catch {
        return "";
    }
}

function renderChallenge(value) {
    const url = isMercadoPagoUrl(value);
    setHidden("challenge-container", !url);
    $("challenge-frame").src = url || "about:blank";
    return Boolean(url);
}

async function generatePix() {
    if (state.busy || !state.option) return;
    setBusy(true, "Gerando Pix...");
    try {
        const deviceId = await loadDeviceId();
        const result = await api(`checkout/${state.token}/pix`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ payment_option: state.option, device_id: deviceId }),
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
    if (!sdkLoadPromise) sdkLoadPromise = new Promise((resolve, reject) => {
        document.querySelector("script[data-mercado-pago-sdk]")?.remove();
        const script = document.createElement("script");
        script.src = "https://sdk.mercadopago.com/js/v2";
        script.dataset.mercadoPagoSdk = "true";
        let settled = false;
        const finish = (failure) => {
            if (settled) return;
            settled = true;
            window.clearTimeout(timeout);
            if (failure) {
                script.remove();
                reject(failure);
            } else resolve();
        };
        const timeout = window.setTimeout(() => finish(new Error("sdk_timeout")), 10000);
        script.addEventListener("load", () => finish(window.MercadoPago ? null : new Error("sdk_global_missing")), { once: true });
        script.addEventListener("error", () => finish(new Error("sdk_load_failed")), { once: true });
        document.head.appendChild(script);
    }).finally(() => { sdkLoadPromise = null; });
    await sdkLoadPromise;
}

async function loadDeviceId() {
    const current = window.MP_DEVICE_SESSION_ID;
    if (typeof current === "string" && DEVICE_ID_PATTERN.test(current)) return current;
    if (!deviceLoadPromise) deviceLoadPromise = new Promise(resolve => {
        const script = document.createElement("script");
        script.src = "https://www.mercadopago.com/v2/security.js";
        script.setAttribute("view", "checkout");
        let settled = false;
        const finish = () => {
            if (settled) return;
            settled = true;
            window.clearTimeout(timeout);
            script.remove();
            const value = window.MP_DEVICE_SESSION_ID;
            resolve(typeof value === "string" && DEVICE_ID_PATTERN.test(value) ? value : null);
        };
        const timeout = window.setTimeout(finish, 4000);
        script.addEventListener("load", finish, { once: true });
        script.addEventListener("error", finish, { once: true });
        document.head.appendChild(script);
    }).catch(() => null).finally(() => { deviceLoadPromise = null; });
    return deviceLoadPromise;
}

function unmountCard() {
    const controller = state.cardController;
    state.cardController = null;
    state.cardUnmount = state.cardUnmount.catch(() => {}).then(() => controller?.unmount?.());
    return state.cardUnmount;
}

async function renderCard() {
    const renderId = ++state.cardRenderId;
    let stage = "brick_unmount";
    const error = $("card-error");
    error.textContent = "";
    error.classList.add("hidden");
    $("card-loading").classList.remove("hidden");
    try {
        await unmountCard();
        if (renderId !== state.cardRenderId) return;
        stage = "config_request";
        const config = await api("checkout/config");
        if (renderId !== state.cardRenderId) return;
        stage = "public_key_validation";
        const publicKey = config?.mercado_pago_public_key;
        if (typeof publicKey !== "string" || !publicKey.trim() || publicKey.trim().length > 200 || /\s/.test(publicKey)) {
            throw new Error("public_key_missing_or_invalid");
        }
        stage = "sdk_load";
        await loadMercadoPago();
        void loadDeviceId();
        if (renderId !== state.cardRenderId) return;
        const current = state.summary.opcoes.find(option => option.tipo === state.option);
        const amount = Number(current?.valor);
        if (!Number.isFinite(amount) || amount <= 0) throw new Error("invalid_initialization_amount");
        stage = "brick_init";
        const mp = new window.MercadoPago(publicKey.trim(), { locale: "pt-BR" });
        const controller = await mp.bricks().create("cardPayment", "card-payment-brick", {
            initialization: { amount },
            callbacks: {
                onReady: () => {
                    if (renderId !== state.cardRenderId) return;
                    $("card-loading").classList.add("hidden");
                },
                onError: brickError => {
                    if (renderId !== state.cardRenderId) return;
                    const cause = typeof brickError?.cause === "string" && /^[a-z0-9_]{1,64}$/i.test(brickError.cause)
                        ? brickError.cause : "unknown_brick_error";
                    diagnostic("brick_callback", cause);
                    error.textContent = cause === "amount_is_not_number" || cause === "missing_amount_property"
                        ? "O valor do cartão está inválido. Atualize o checkout ou use Pix."
                        : "O formulário seguro do cartão não pôde ser inicializado. O Pix continua disponível.";
                    error.classList.remove("hidden");
                    $("card-loading").classList.add("hidden");
                },
                onSubmit: (formData, additionalData) => processCard(formData, additionalData),
            },
        });
        if (renderId !== state.cardRenderId) await controller?.unmount?.();
        else state.cardController = controller;
    } catch (failure) {
        if (renderId !== state.cardRenderId) return;
        const status = Number.isInteger(failure?.status) ? failure.status : undefined;
        const category = stage === "config_request" && status
            ? `http_${status}`
            : stage === "config_request" ? "network_failed"
            : failure?.message === "public_key_missing_or_invalid" ? "public_key_missing_or_invalid"
                : failure?.message === "invalid_initialization_amount" ? "invalid_initialization_amount"
                    : stage === "sdk_load" ? "sdk_load_failed" : "initialization_failed";
        diagnostic(stage, category, status);
        $("card-loading").classList.add("hidden");
        error.textContent = category === "http_503" || category === "public_key_missing_or_invalid"
            ? "O cartão está temporariamente indisponível por configuração. O Pix continua disponível."
            : category === "sdk_load_failed"
                ? "O formulário seguro do cartão não carregou. Verifique sua conexão ou use Pix."
                : category === "invalid_initialization_amount"
                    ? "O valor do cartão está inválido. Atualize o checkout ou use Pix."
                    : "O formulário seguro do cartão não pôde ser inicializado. O Pix continua disponível.";
        error.classList.remove("hidden");
    }
}

function diagnostic(stage, category, httpStatus) {
    const safeStage = /^[a-z0-9_]{1,40}$/i.test(stage) ? stage : "unknown";
    const safeCategory = /^[a-z0-9_]{1,64}$/i.test(category) ? category : "unknown";
    const metadata = { stage: safeStage, category: safeCategory };
    if (Number.isInteger(httpStatus) && httpStatus >= 100 && httpStatus <= 599) metadata.http_status = httpStatus;
    console.warn("checkout_diagnostic", metadata);
}

async function processCard(formData, additionalData) {
    if (state.busy) throw new Error("payment_in_progress");
    state.busy = true;
    try {
        const paymentTypeId = additionalData?.paymentTypeId;
        if (!["credit_card", "debit_card"].includes(paymentTypeId)) throw new Error("unsupported_payment_type");
        const identification = formData.payer?.identification ?? {};
        const deviceId = await loadDeviceId();
        const result = await api(`checkout/${state.token}/card`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                payment_option: state.option,
                card_token: formData.token,
                payment_method_id: formData.payment_method_id,
                payment_method_type: paymentTypeId,
                installments: Number(formData.installments),
                payer_email: formData.payer?.email || null,
                identification_type: identification.type || null,
                identification_number: identification.number || null,
                device_id: deviceId,
            }),
        });
        track("payment_attempt", { payment_method: "card", payment_option: state.option, outcome: result.status });
        renderPayment(result);
    } catch (error) {
        diagnostic("payment_processing", error.status ? `http_${error.status}` : error.message === "unsupported_payment_type" ? "unsupported_payment_type" : "request_failed", error.status);
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
        state.proposalId = readProposalId();
        state.token = state.proposalId ? String(state.proposalId) : readToken();
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
    if (method !== "card") {
        state.cardRenderId += 1;
        void unmountCard().catch(() => diagnostic("brick_unmount", "failed"));
    }
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
    if (event.source !== $("challenge-frame").contentWindow
        || !isMercadoPagoUrl(event.origin) || event.data?.status !== "COMPLETE") return;
    refreshStatus();
});
window.addEventListener("pagehide", () => {
    stopPolling();
    state.cardRenderId += 1;
    void unmountCard().catch(() => diagnostic("brick_unmount", "failed"));
});

initAnalytics();
initComponents();
loadCheckout();
