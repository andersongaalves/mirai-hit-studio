// "Meu perfil": the CPF the beat contracts need. The full number is never shown back.
import * as api from "./api.js";

function el(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

function cpfDigitsValid(value) {
    const digits = value.replace(/\D/g, "");
    if (digits.length !== 11 || /^(\d)\1{10}$/.test(digits)) return false;
    for (const size of [9, 10]) {
        let total = 0;
        for (let index = 0; index < size; index += 1) total += Number(digits[index]) * (size + 1 - index);
        if ((total * 10 % 11) % 10 !== Number(digits[size])) return false;
    }
    return true;
}

function maskCpf(value) {
    const digits = value.replace(/\D/g, "").slice(0, 11);
    return digits
        .replace(/^(\d{3})(\d)/, "$1.$2")
        .replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3")
        .replace(/\.(\d{3})(\d{1,2})$/, ".$1-$2");
}

export async function loadProfileCpf(root) {
    if (!root) return;
    root.replaceChildren(el("p", "", "Carregando seus dados..."));
    let profile;
    try {
        profile = await api.obterPerfil();
    } catch (error) {
        root.replaceChildren(el("p", "producer-message--error", error.message));
        return;
    }
    render(root, profile);
}

function render(root, profile) {
    const form = el("form", "portal-form-section producer-cpf");
    form.setAttribute("aria-labelledby", "producer-cpf-title");
    const title = el("h2", "", "Dados para contrato");
    title.id = "producer-cpf-title";
    const status = el("p", `producer-cpf__status${profile.cpf_cadastrado ? " producer-cpf__status--ok" : ""}`);
    status.textContent = profile.cpf_cadastrado
        ? `CPF cadastrado: ${profile.cpf_mascarado}`
        : profile.beatmaker
            ? "CPF pendente: sem ele, os contratos dos seus beats saem sem a sua identificação."
            : "Nenhum CPF cadastrado.";
    const help = el("p", "portal-form-help",
        "O CPF identifica você como licenciante nos contratos dos beats. Ele aparece só no contrato privado de quem comprou e nunca em páginas públicas.");
    const label = el("label", "portal-field");
    label.append(el("span", "portal-field__label", profile.cpf_cadastrado ? "Corrigir CPF" : "CPF"));
    const input = el("input");
    input.name = "cpf";
    input.inputMode = "numeric";
    input.autocomplete = "off";
    input.placeholder = "000.000.000-00";
    input.maxLength = 14;
    input.required = true;
    input.addEventListener("input", () => {
        input.value = maskCpf(input.value);
        input.setCustomValidity("");
    });
    label.append(input);
    const feedback = el("p", "producer-cpf__feedback");
    feedback.setAttribute("role", "status");
    const save = el("button", "btn-cta", profile.cpf_cadastrado ? "Atualizar CPF" : "Salvar CPF");
    save.type = "submit";
    const footer = el("div", "portal-form-footer");
    footer.append(feedback, save);
    form.append(title, status, help, label, footer);
    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (!cpfDigitsValid(input.value)) {
            input.setCustomValidity("CPF inválido. Confira os 11 números.");
            input.reportValidity();
            return;
        }
        save.disabled = true;
        feedback.textContent = "Salvando...";
        try {
            const updated = await api.salvarCpf(input.value.replace(/\D/g, ""));
            render(root, updated);
            root.querySelector(".producer-cpf__feedback").textContent = "CPF salvo.";
        } catch (error) {
            feedback.textContent = error.message;
            save.disabled = false;
        }
    });
    root.replaceChildren(form);
}
