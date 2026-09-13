import { $ } from "../../utils/dom.js";
import { buscarPreview, baixarDocumento } from "./proposta_api.js";

let documentoUrl = null;
let revisao = 0;

export function limparPreview() {
    revisao++;
    if (documentoUrl) URL.revokeObjectURL(documentoUrl);
    documentoUrl = null;
}

export async function renderizarPreview(proposta, dirty = false) {
    limparPreview();
    const atual = revisao;
    const container = $("proposta-content");
    if (!container || !proposta) return;
    const message = document.createElement("p");
    message.textContent = dirty ? "Salve as alterações antes de gerar o PDF." : "Carregando documento...";
    const frame = document.createElement("iframe");
    frame.className = "proposta-document-frame";
    frame.title = "Prévia da proposta salva";
    frame.setAttribute("sandbox", "");
    container.replaceChildren(message, frame);
    const ativo = () => atual === revisao && frame.isConnected;
    try {
        const html = await buscarPreview(proposta.id);
        if (!ativo()) return;
        frame.srcdoc = html;
        message.textContent = dirty ? "Salve as alterações antes de gerar o PDF."
            : proposta.pagamentos.some(item => item.habilitado) ? ""
            : "QR Code será gerado após informar um link válido.";
    } catch (error) {
        if (ativo()) message.textContent = error.message;
        return;
    }
    if (!proposta.pdf_path || dirty) return;
    try {
        const blob = await baixarDocumento(proposta.id);
        if (!ativo()) return;
        documentoUrl = URL.createObjectURL(blob);
        const toolbar = document.createElement("div");
        toolbar.className = "proposta-document-actions";
        for (const download of [false, true]) {
            const link = document.createElement("a");
            link.href = documentoUrl;
            link.textContent = download ? "Baixar PDF" : "Visualizar PDF";
            if (download) link.download = `proposta-${proposta.id}-v${proposta.versao}.pdf`;
            else { link.target = "_blank"; link.rel = "noopener noreferrer"; }
            toolbar.append(link);
        }
        container.insertBefore(toolbar, frame);
    } catch (error) {
        if (ativo()) message.textContent = error.message;
    }
}
