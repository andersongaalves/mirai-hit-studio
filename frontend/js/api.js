const BASE_URL = 'http://localhost:8000';

export async function getAPI(endpoint) {
    const res = await fetch(`${BASE_URL}/${endpoint}`);
    if (!res.ok) throw new Error(`Erro ao buscar ${endpoint}: ${res.status}`);
    return await res.json();
}

export async function postOrcamento(payload) {
    const res = await fetch(`${BASE_URL}/orcamentos`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Erro ao enviar o orçamento');
    return await res.json(); // Se a sua API retornar alguma confirmação
}

export async function getProjetos() {
    const res = await fetch(`${BASE_URL}/projetos`);
    if (!res.ok) throw new Error('Erro ao buscar projetos');
    return await res.json();
}