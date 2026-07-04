import {
    carregarServicos,
    inicializarParametros
} from "./servicos/servicos.js";

import {
    carregarPortfolio
} from "./projetos.js";

import {
    initOrcamentos
} from "./orcamentos/orcamentos.js";

import {
    carregarConfiguracoes
} from "./configuracoes.js";

import {
    initProducoes
} from "./producoes/producoes.js";

import {
    $,
    $$$,
    show,
    hide
} from "../utils/dom.js";

const loaders = [
    carregarServicos,
    carregarPortfolio,
    initOrcamentos,
    carregarConfiguracoes,
    initProducoes
];

export async function inicializarDashboard() {
    mostrarDashboard();
    inicializarParametros();

    await Promise.all(
        loaders.map(loader => loader())
    );
}

export function mostrarDashboard() {
    $$$(".admin-section").forEach(
        section => hide(section)
    );

    show(
        $("dashboard-menu")
    );
}

export function mostrarSecao(id) {
    hide(
        $("dashboard-menu")
    );

    $$$(".admin-section").forEach(
        section => hide(section)
    );

    show(
        $(id)
    );
}

export function voltarDashboard() {
    mostrarDashboard();
}

export function atualizarTudo() {
    Promise.all(
        loaders.map(loader => loader())
    )
    .catch(error => {
        console.error(error);
    });
}

export function abrirModal(id) {
    show(
        $(id)
    );
}

export function fecharModal(id) {
    hide(
        $(id)
    );
}
