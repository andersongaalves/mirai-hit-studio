import * as Notify from "../utils/notifications.js";

import { $, show, hide, text } from "../utils/dom.js";

// ===========================
// MODAL
// ===========================

export function abrirModal(id) {
    show($(id));
}

export function fecharModal(id) {
    hide($(id));
}

export function toggleModal(id) {
    $(id)?.classList.toggle("hidden");
}

// ===========================
// LOADING
// ===========================

export function mostrarLoading() {
    show($("loading"));
}

export function esconderLoading() {
    hide($("loading"));
}

// ===========================
// MENSAGENS
// ===========================

export function mostrarErro(mensagem) {
    const box = $("error-message");

    if (!box) {
        Notify.error(mensagem);

        return;
    }

    text(
        box,

        mensagem,
    );

    show(box);
}

export function limparErro() {
    const box = $("error-message");

    text(box, "");

    hide(box);
}

export function mostrarSucesso(mensagem) {
    const box = $("success-message");

    if (!box) {
        Notify.success(mensagem);

        return;
    }

    text(
        box,

        mensagem,
    );

    show(box);

    setTimeout(() => hide(box), 3000);
}

// ===========================
// CONFIRM
// ===========================

export function confirmar(mensagem) {
    return confirm(mensagem);
}

// ===========================
// FORM
// ===========================

export function limparFormulario(formId) {
    $(formId)?.reset();
}

export function preencherFormulario(formId, dados) {
    const form = $(formId);

    if (!form) return;

    Object.entries(dados).forEach(([campo, valor]) => {
        const elemento = form.querySelector(`[name="${campo}"]`);

        if (!elemento) {
            return;
        }

        if (elemento.type === "checkbox") {
            elemento.checked = Boolean(valor);
        } else {
            elemento.value = valor ?? "";
        }
    });
}

// ===========================
// BUTTON
// ===========================

export function bloquearBotao(
    id,

    texto = "Salvando...",
) {
    const btn = $(id);

    if (!btn) return;

    if (!btn.dataset.original) {
        btn.dataset.original = btn.innerText;
    }

    btn.innerText = texto;

    btn.disabled = true;
}

export function desbloquearBotao(id) {
    const btn = $(id);

    if (!btn) return;

    btn.innerText = btn.dataset.original || "Salvar";

    btn.disabled = false;
}
