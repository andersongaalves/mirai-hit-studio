import * as Notify from "../utils/notifications.js";
import { $, $$, $$$ } from "../utils/dom.js";

export function abrirModal(id) {

    const modal = $(id);

    if (!modal) return;

    modal.classList.remove("hidden");

}

export function fecharModal(id) {

    const modal = $(id);

    if (!modal) return;

    modal.classList.add("hidden");

}

export function toggleModal(id) {

    const modal = $(id);

    if (!modal) return;

    modal.classList.toggle("hidden");

}

export function mostrarLoading() {

    const loading = $("loading");

    if (loading) {

        loading.classList.remove("hidden");

    }

}

export function esconderLoading() {

    const loading = $("loading");

    if (loading) {

        loading.classList.add("hidden");

    }

}

export function mostrarErro(mensagem) {

    const box = $("error-message");

    if (!box) {

        Notify.error(mensagem);

        return;

    }

    box.innerText = mensagem;

    box.classList.remove("hidden");

}

export function limparErro() {

    const box = $("error-message");

    if (!box) return;

    box.innerText = "";

    box.classList.add("hidden");

}

export function mostrarSucesso(mensagem) {

    const box = $("success-message");

    if (!box) {

        Notify.success(mensagem);

        return;

    }

    box.innerText = mensagem;

    box.classList.remove("hidden");

    setTimeout(() => {

        box.classList.add("hidden");

    }, 3000);

}

export function confirmar(mensagem) {

    return window.confirm(mensagem);

}

export function limparFormulario(formId) {

    const form = $(formId);

    if (!form) return;

    form.reset();

}

export function preencherFormulario(formId, dados) {

    const form = $(formId);

    if (!form) return;

    Object.entries(dados).forEach(([campo, valor]) => {

        const elemento = form.querySelector(

            `[name="${campo}"]`

        );

        if (!elemento) return;

        if (elemento.type === "checkbox") {

            elemento.checked = valor;

        }

        else {

            elemento.value = valor ?? "";

        }

    });

}

export function bloquearBotao(id, texto = "Salvando...") {

    const btn = $(id);

    if (!btn) return;

    btn.dataset.original = btn.innerText;

    btn.innerText = texto;

    btn.disabled = true;

}

export function desbloquearBotao(id) {

    const btn = $(id);

    if (!btn) return;

    btn.innerText = btn.dataset.original || "Salvar";

    btn.disabled = false;

}