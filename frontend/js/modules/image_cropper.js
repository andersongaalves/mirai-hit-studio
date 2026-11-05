// Crop an image before uploading it: the person drags the picture inside a fixed frame
// (round for a profile photo) and zooms; only what is inside the frame is exported, at
// a fixed size, as JPEG. Resolves to a File, or null when cancelled.
const MAX_ZOOM = 4;

function el(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

function loadImage(file) {
    return new Promise((resolve, reject) => {
        const url = URL.createObjectURL(file);
        const image = new Image();
        image.onload = () => resolve({ image, url });
        image.onerror = () => {
            URL.revokeObjectURL(url);
            reject(new Error("Não foi possível abrir esta imagem. Use JPG, PNG ou WebP."));
        };
        image.src = url;
    });
}

/**
 * @param {File} file
 * @param {{ aspect?: number, width?: number, height?: number, round?: boolean, title?: string, name?: string }} options
 */
export async function cropImage(file, { aspect = 1, width = 800, height = 800, round = false, title = "Ajustar imagem", name = "imagem" } = {}) {
    const { image, url } = await loadImage(file);
    return new Promise(resolve => {
        const dialog = el("dialog", "image-cropper");
        dialog.setAttribute("aria-labelledby", "image-cropper-title");
        const heading = el("h2", "", title);
        heading.id = "image-cropper-title";
        const help = el("p", "image-cropper__help", "Arraste a imagem para enquadrar e use o zoom. Só a parte dentro da moldura será enviada.");
        const stage = el("div", `image-cropper__stage${round ? " image-cropper__stage--round" : ""}`);
        stage.style.aspectRatio = String(aspect);
        // Sized from the viewport height too, so the frame keeps its exact proportion.
        stage.style.width = round ? `min(100%, 420px, ${Math.round(60 * aspect)}vh)` : `min(100%, ${Math.round(60 * aspect)}vh)`;
        stage.tabIndex = 0;
        stage.setAttribute("role", "application");
        stage.setAttribute("aria-label", "Área de recorte. Use as setas para mover e + ou − para o zoom.");
        const canvas = el("canvas");
        stage.append(canvas, el("div", "image-cropper__frame"));
        const zoomLabel = el("label", "image-cropper__zoom");
        const zoom = el("input");
        zoom.type = "range";
        zoom.min = "1";
        zoom.max = String(MAX_ZOOM);
        zoom.step = "0.01";
        zoom.value = "1";
        zoomLabel.append(el("span", "", "Zoom"), zoom);
        const actions = el("div", "image-cropper__actions");
        const cancel = el("button", "btn-outline", "Cancelar");
        cancel.type = "button";
        const confirm = el("button", "btn-cta", "Usar imagem");
        confirm.type = "button";
        actions.append(cancel, confirm);
        dialog.append(heading, help, stage, zoomLabel, actions);
        document.body.append(dialog);

        // View state: image centre in stage pixels and the zoom over the "cover" scale.
        let stageW = 0;
        let stageH = 0;
        let scale = 1;
        let cx = 0;
        let cy = 0;
        const base = () => Math.max(stageW / image.naturalWidth, stageH / image.naturalHeight);
        const drawn = () => ({ w: image.naturalWidth * base() * scale, h: image.naturalHeight * base() * scale });

        function clamp() {
            const { w, h } = drawn();
            cx = Math.min(w / 2, Math.max(stageW - w / 2, cx));
            cy = Math.min(h / 2, Math.max(stageH - h / 2, cy));
        }

        function draw() {
            const ratio = window.devicePixelRatio || 1;
            canvas.width = Math.round(stageW * ratio);
            canvas.height = Math.round(stageH * ratio);
            const context = canvas.getContext("2d");
            context.setTransform(ratio, 0, 0, ratio, 0, 0);
            context.clearRect(0, 0, stageW, stageH);
            const { w, h } = drawn();
            context.drawImage(image, cx - w / 2, cy - h / 2, w, h);
        }

        function measure(reset = false) {
            const rect = stage.getBoundingClientRect();
            const previousW = stageW || rect.width;
            stageW = rect.width;
            stageH = rect.height;
            if (reset) {
                cx = stageW / 2;
                cy = stageH / 2;
            } else {
                const factor = stageW / previousW;
                cx *= factor;
                cy *= factor;
            }
            clamp();
            draw();
        }

        function setZoom(value, anchorX = stageW / 2, anchorY = stageH / 2) {
            const next = Math.min(MAX_ZOOM, Math.max(1, value));
            const ratio = next / scale;
            // Keep the point under the anchor (pointer or centre) in place.
            cx = anchorX - (anchorX - cx) * ratio;
            cy = anchorY - (anchorY - cy) * ratio;
            scale = next;
            zoom.value = String(next);
            clamp();
            draw();
        }

        let drag = null;
        stage.addEventListener("pointerdown", event => {
            drag = { id: event.pointerId, x: event.clientX, y: event.clientY };
            stage.setPointerCapture(event.pointerId);
            stage.classList.add("is-dragging");
        });
        stage.addEventListener("pointermove", event => {
            if (!drag || drag.id !== event.pointerId) return;
            cx += event.clientX - drag.x;
            cy += event.clientY - drag.y;
            drag.x = event.clientX;
            drag.y = event.clientY;
            clamp();
            draw();
        });
        const endDrag = () => { drag = null; stage.classList.remove("is-dragging"); };
        stage.addEventListener("pointerup", endDrag);
        stage.addEventListener("pointercancel", endDrag);
        stage.addEventListener("wheel", event => {
            event.preventDefault();
            const rect = stage.getBoundingClientRect();
            setZoom(scale * (event.deltaY < 0 ? 1.08 : 1 / 1.08), event.clientX - rect.left, event.clientY - rect.top);
        }, { passive: false });
        stage.addEventListener("keydown", event => {
            const step = event.shiftKey ? 40 : 10;
            const moves = { ArrowLeft: [step, 0], ArrowRight: [-step, 0], ArrowUp: [0, step], ArrowDown: [0, -step] };
            if (moves[event.key]) {
                event.preventDefault();
                cx += moves[event.key][0];
                cy += moves[event.key][1];
                clamp();
                draw();
            } else if (event.key === "+" || event.key === "=") {
                event.preventDefault();
                setZoom(scale + 0.1);
            } else if (event.key === "-") {
                event.preventDefault();
                setZoom(scale - 0.1);
            }
        });
        zoom.addEventListener("input", () => setZoom(Number(zoom.value)));
        const onResize = () => measure();
        window.addEventListener("resize", onResize);

        function finish(result) {
            window.removeEventListener("resize", onResize);
            URL.revokeObjectURL(url);
            dialog.close();
            dialog.remove();
            resolve(result);
        }

        cancel.addEventListener("click", () => finish(null));
        dialog.addEventListener("cancel", event => { event.preventDefault(); finish(null); });
        confirm.addEventListener("click", () => {
            confirm.disabled = true;
            const output = document.createElement("canvas");
            output.width = width;
            output.height = height;
            const context = output.getContext("2d");
            context.fillStyle = "#071018";
            context.fillRect(0, 0, width, height);
            const factor = width / stageW;
            const { w, h } = drawn();
            context.imageSmoothingQuality = "high";
            context.drawImage(image, (cx - w / 2) * factor, (cy - h / 2) * factor, w * factor, h * factor);
            output.toBlob(blob => {
                if (!blob) {
                    confirm.disabled = false;
                    help.textContent = "Não foi possível preparar a imagem. Tente outra.";
                    return;
                }
                finish(new File([blob], `${name}.jpg`, { type: "image/jpeg" }));
            }, "image/jpeg", 0.9);
        });

        dialog.showModal();
        requestAnimationFrame(() => { measure(true); stage.focus(); });
    });
}
