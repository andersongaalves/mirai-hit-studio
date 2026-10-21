import { uploadBusy } from "./upload_feedback.js";
const applied = new WeakSet();
let assets;

function stylesheet(href) {
    return new Promise((resolve, reject) => {
        const link = document.createElement("link");
        link.rel = "stylesheet";
        link.href = href;
        link.onload = resolve;
        link.onerror = () => reject(new Error("Não foi possível carregar o editor de imagem."));
        document.head.append(link);
    });
}

function loadAssets() {
    assets ||= Promise.all([
        import("../vendor/cropperjs/cropper.esm.js"),
        stylesheet("/js/vendor/cropperjs/cropper.min.css"),
        stylesheet("/css/components/image-crop.css"),
    ]).catch(error => { assets = null; throw error; });
    return assets;
}

async function cropImage(file, ratio, width) {
    const [{ default: Cropper }] = await loadAssets();
    const source = URL.createObjectURL(file);
    const dialog = document.createElement("dialog");
    dialog.className = "image-crop";
    dialog.setAttribute("aria-labelledby", "image-crop-title");
    dialog.innerHTML = `<h2 id="image-crop-title">Ajustar imagem</h2>
        <div class="image-crop__stage"><img alt="Imagem para recortar" /></div>
        <label class="image-crop__zoom">Zoom<input type="range" min="1" max="3" step="0.01" value="1" /></label>
        <p role="alert"></p><div class="image-crop__actions">
        <button type="button" data-cancel class="btn-outline">Cancelar</button>
        <button type="button" data-apply class="btn-cta" disabled>Usar corte</button></div>`;
    document.body.append(dialog);
    const opener = document.activeElement;
    const image = dialog.querySelector("img");
    const apply = dialog.querySelector("[data-apply]");
    const zoom = dialog.querySelector("input");
    let cropper;
    let baseZoom = 1;
    let result = null;
    let saving = false;
    dialog.showModal();
    return new Promise(resolve => {
        dialog.addEventListener("close", () => {
            cropper?.destroy();
            URL.revokeObjectURL(source);
            dialog.remove();
            opener?.focus();
            resolve(result);
        }, { once: true });
        dialog.addEventListener("cancel", event => { if (saving) event.preventDefault(); });
        dialog.querySelector("[data-cancel]").onclick = () => { if (!saving) dialog.close(); };
        image.onerror = () => { dialog.querySelector("[role=alert]").textContent = "Não foi possível abrir esta imagem."; };
        image.onload = () => {
            if (image.naturalWidth * image.naturalHeight > 40_000_000) {
                dialog.querySelector("[role=alert]").textContent = "Escolha uma imagem de até 40 megapixels.";
                return;
            }
            cropper = new Cropper(image, {
                aspectRatio: ratio, viewMode: 1, dragMode: "move", autoCropArea: 0.9,
                rotatable: false, scalable: false, toggleDragModeOnDblclick: false,
                zoomOnWheel: false, zoomOnTouch: false, background: false,
                ready() {
                    baseZoom = cropper.getCanvasData().width / image.naturalWidth;
                    apply.disabled = false;
                },
            });
        };
        image.src = source;
        zoom.oninput = () => cropper?.zoomTo(baseZoom * Number(zoom.value));
        dialog.querySelector(".image-crop__stage").tabIndex = 0;
        dialog.querySelector(".image-crop__stage").setAttribute("aria-label", "Posição da imagem");
        dialog.querySelector(".image-crop__stage").onkeydown = event => {
            const delta = { ArrowLeft: [-10, 0], ArrowRight: [10, 0], ArrowUp: [0, -10], ArrowDown: [0, 10] }[event.key];
            if (delta && cropper) { event.preventDefault(); cropper.move(...delta); }
        };
        apply.onclick = async () => {
            if (!cropper || saving) return;
            saving = true;
            const finish = uploadBusy(apply, "Preparando...");
            apply.disabled = true;
            try {
                const canvas = cropper.getCroppedCanvas({ width, height: Math.round(width / ratio), imageSmoothingQuality: "high" });
                const mime = file.type === "image/jpeg" ? "image/jpeg" : "image/png";
                const blob = await new Promise(done => canvas.toBlob(done, mime, 0.92));
                if (!blob || blob.size > 10 * 1024 * 1024) throw new Error("Não foi possível preparar a imagem. Escolha uma imagem menor.");
                const name = file.name.replace(/\.[^.]+$/, "") + (mime === "image/jpeg" ? ".jpg" : ".png");
                result = new File([blob], name, { type: mime });
                dialog.close();
            } catch (error) {
                dialog.querySelector("[role=alert]").textContent = error.message;
                saving = false;
            } finally {
                finish();
                if (!result) apply.disabled = false;
            }
        };
    });
}

export function bindImageCrop(input, { ratio = 16 / 9, width = 1600 } = {}) {
    if (!input || input.dataset.cropBound) return;
    input.dataset.cropBound = "true";
    let previous = [];
    let busy = false;
    const status = document.createElement("span");
    status.setAttribute("role", "status");
    input.after(status);
    const assign = files => {
        const transfer = new DataTransfer();
        files.forEach(file => transfer.items.add(file));
        input.files = transfer.files;
    };
    input.form?.addEventListener("submit", event => {
        if (busy) { event.preventDefault(); event.stopImmediatePropagation(); }
    }, true);
    input.form?.addEventListener("reset", () => { previous = []; status.textContent = ""; });
    input.addEventListener("click", () => { if (!input.files.length) previous = []; });
    input.addEventListener("change", async event => {
        if (applied.has(input)) return;
        const file = input.files?.[0];
        if (!file || !["image/jpeg", "image/png", "image/webp", "image/avif"].includes(file.type) || file.size > 10 * 1024 * 1024) return;
        event.stopImmediatePropagation();
        if (busy) return;
        busy = true;
        input.dataset.cropPending = "true";
        status.textContent = "";
        assign([]);
        try {
            const cropped = await cropImage(file, ratio, width);
            assign(cropped ? [cropped] : previous);
            if (cropped) {
                previous = [cropped];
                applied.add(input);
                try { input.dispatchEvent(new Event("change", { bubbles: true })); }
                finally { applied.delete(input); }
            }
        } catch {
            assign(previous);
            status.textContent = "Não foi possível abrir o editor. Selecione a imagem novamente.";
        } finally {
            busy = false;
            delete input.dataset.cropPending;
        }
    }, true);
}
