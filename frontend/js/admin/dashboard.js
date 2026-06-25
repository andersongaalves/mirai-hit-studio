import {carregarServicos, inicializarParametros} from "./servicos.js";
import {carregarPortfolio} from "./projetos.js";
import {carregarOrcamentos} from "./orcamentos.js";
import {carregarConfiguracoes} from "./configuracoes.js";
import { $, $$, $$$ } from "../utils/dom.js";

export async function inicializarDashboard() {

    mostrarDashboard();
    inicializarParametros();

    await Promise.all([

        carregarServicos(),
        carregarPortfolio(),
        carregarOrcamentos(),
        carregarConfiguracoes()

    ]);

}

export function mostrarDashboard() {

    document
        .querySelectorAll(".admin-section")
        .forEach(section => {

            section.classList.add("hidden");

        });

    document
        .getElementById("dashboard-menu")
        .classList.remove("hidden");

}

export function mostrarSecao(id) {

    document
        .getElementById("dashboard-menu")
        .classList.add("hidden");

    document
        .querySelectorAll(".admin-section")

        .forEach(section => {
            section.classList.add("hidden");
        });

    const secao = $(id);

    if (secao) {
        secao.classList.remove("hidden");
    }

}

export function voltarDashboard() {
    mostrarDashboard();
}

export function atualizarTudo() {
    Promise.all([
        carregarServicos(),
        carregarPortfolio(),
        carregarOrcamentos(),
        carregarConfiguracoes()
    ])

    .catch(error => {
        console.error(error);
    });

}

export function abrirModal(id) {

    const modal = $(id);

    if (modal) {
        modal.classList.remove("hidden");
    }

}

export function fecharModal(id) {

    const modal = $(id);

    if (modal) {
        modal.classList.add("hidden");
    }
}