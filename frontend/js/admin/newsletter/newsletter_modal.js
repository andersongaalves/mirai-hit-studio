import { closeAdminModal, openAdminModal } from "../admin_modal.js";


let current = null;
let handlers = {};

const field = (id) => document.getElementById(id);

function payload() {
    return {
        titulo_interno: field("newsletter-campaign-name").value.trim(),
        assunto: field("newsletter-campaign-subject").value.trim(),
        preview_text: field("newsletter-campaign-preview").value.trim() || null,
        body_text: field("newsletter-campaign-body").value.trim(),
    };
}


export function openCampaignModal(campaign = null, options = {}) {
    current = campaign;
    handlers = options;
    const editable = !campaign || campaign.status === "draft";
    field("newsletter-campaign-title").textContent = campaign ? "Campanha" : "Nova campanha";
    field("newsletter-campaign-name").value = campaign?.titulo_interno || "";
    field("newsletter-campaign-subject").value = campaign?.assunto || "";
    field("newsletter-campaign-preview").value = campaign?.preview_text || "";
    field("newsletter-campaign-body").value = campaign?.body_text || "";
    ["newsletter-campaign-name", "newsletter-campaign-subject", "newsletter-campaign-preview", "newsletter-campaign-body"].forEach(id => { field(id).disabled = !editable; });
    const result = field("newsletter-campaign-result");
    result.classList.toggle("hidden", !campaign || campaign.status === "draft");
    result.textContent = campaign ? `${campaign.total_sent || 0} enviados · ${campaign.total_failed || 0} falhas · ${campaign.total_skipped || 0} ignorados` : "";
    const save = field("newsletter-campaign-save");
    save.classList.toggle("hidden", !editable);
    save.onclick = async () => {
        if (save.disabled || !field("newsletter-campaign-name").reportValidity() || !field("newsletter-campaign-subject").reportValidity() || !field("newsletter-campaign-body").reportValidity()) return;
        save.disabled = true;
        try { await handlers.onSave?.(current, payload()); } finally { save.disabled = false; }
    };
    const send = field("newsletter-campaign-send");
    send.classList.toggle("hidden", !campaign || campaign.status !== "draft");
    send.onclick = async () => {
        if (send.disabled || !current) return;
        send.disabled = true;
        try { await handlers.onSend?.(current); } finally { send.disabled = false; }
    };
    field("newsletter-campaign-close").onclick = closeCampaignModal;
    openAdminModal("modal-newsletter-campaign", { onRequestClose: closeCampaignModal, initialFocus: "#newsletter-campaign-name" });
}


export function closeCampaignModal() {
    current = null;
    handlers = {};
    closeAdminModal("modal-newsletter-campaign");
}
