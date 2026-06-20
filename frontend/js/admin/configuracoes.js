import * as API from "../api.js";
import { authFetch } from "./auth.js";

let configuracaoAtual = null;

export async function carregarConfiguracoes() {

    try {
        configuracaoAtual = await API.getAPI("config");
        preencherFormulario();

    }
    catch (error) {
        console.error(error);
    }
}

function preencherFormulario() {

    if (!configuracaoAtual) return;
    Object.entries(configuracaoAtual).forEach(
        ([campo, valor]) => {
            const input = document.getElementById(campo);

            if (input) {
                input.value = valor;
            }
        }
    );
}

export async function salvarConfiguracoesExtras() {
    // 1. Captura os valores direto do HTML
    const payload = {
        desconto: parseFloat(document.getElementById('cfg_desconto').value) || 0,
        val_extra_duracao: parseFloat(document.getElementById('val_extra_duracao').value) || 0,
        val_extra_pessoa: parseFloat(document.getElementById('val_extra_pessoa').value) || 0,
        val_extra_canal_voz: parseFloat(document.getElementById('val_extra_canal_voz').value) || 0,
        val_extra_canal_inst: parseFloat(document.getElementById('val_extra_canal_inst').value) || 0,
        val_extra_melodia: parseFloat(document.getElementById('val_extra_melodia').value) || 0,
        val_extra_revisao: parseFloat(document.getElementById('val_extra_revisao').value) || 0,
        val_inst_hibrido: parseFloat(document.getElementById('val_inst_hibrido').value) || 0,
        val_inst_gravado: parseFloat(document.getElementById('val_inst_gravado').value) || 0,
        val_prazo_urgente: parseFloat(document.getElementById('val_prazo_urgente').value) || 0,
        val_prazo_express: parseFloat(document.getElementById('val_prazo_express').value) || 0,
        val_lease_desconto: parseFloat(document.getElementById('val_lease_desconto').value) || 0
    };

    try {
        // Envia para o backend
        const response = await authFetch('/config', {
            method: 'PUT',
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            alert("Erro ao salvar as configurações. Verifique o servidor.");
            return;
        }

        alert("Tabela de custos atualizada com sucesso!");
        
    } catch (error) {
        console.error("Erro ao salvar config:", error);
        alert("Erro de conexão ao tentar salvar.");
    }
}