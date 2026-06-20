export function abrirModal(id) {

    const modal = document.getElementById(id);

    if (!modal) return;

    modal.classList.remove("hidden");

}

export function fecharModal(id) {

    const modal = document.getElementById(id);

    if (!modal) return;

    modal.classList.add("hidden");

}

export function toggleModal(id) {

    const modal = document.getElementById(id);

    if (!modal) return;

    modal.classList.toggle("hidden");

}

export function mostrarLoading() {

    const loading = document.getElementById("loading");

    if (loading) {

        loading.classList.remove("hidden");

    }

}

export function esconderLoading() {

    const loading = document.getElementById("loading");

    if (loading) {

        loading.classList.add("hidden");

    }

}

export function mostrarErro(mensagem) {

    const box = document.getElementById("error-message");

    if (!box) {

        alert(mensagem);

        return;

    }

    box.innerText = mensagem;

    box.classList.remove("hidden");

}

export function limparErro() {

    const box = document.getElementById("error-message");

    if (!box) return;

    box.innerText = "";

    box.classList.add("hidden");

}

export function mostrarSucesso(mensagem) {

    const box = document.getElementById("success-message");

    if (!box) {

        alert(mensagem);

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

    const form = document.getElementById(formId);

    if (!form) return;

    form.reset();

}

export function preencherFormulario(formId, dados) {

    const form = document.getElementById(formId);

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

    const btn = document.getElementById(id);

    if (!btn) return;

    btn.dataset.original = btn.innerText;

    btn.innerText = texto;

    btn.disabled = true;

}

export function desbloquearBotao(id) {

    const btn = document.getElementById(id);

    if (!btn) return;

    btn.innerText = btn.dataset.original || "Salvar";

    btn.disabled = false;

}