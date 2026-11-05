// "Meu perfil" > Página pública: what the producer customises on /produtores/<endereço>.
// Photo and cover upload right away; the rest is saved with "Salvar página". Name and
// specialties come from the account (set by the studio) and are shown read-only.
import * as api from "./api.js";
import { cropImage } from "../modules/image_cropper.js";

const REDES = {
    instagram: ["Instagram", "https://www.instagram.com/seu-perfil"],
    youtube: ["YouTube", "https://www.youtube.com/@seu-canal"],
    spotify: ["Spotify", "https://open.spotify.com/artist/..."],
    soundcloud: ["SoundCloud", "https://soundcloud.com/seu-perfil"],
    tiktok: ["TikTok", "https://www.tiktok.com/@seu-perfil"],
    beatstars: ["BeatStars", "https://www.beatstars.com/seu-perfil"],
    site: ["Site", "https://seusite.com.br"],
};
const NOMES_CORES = {
    "#00d5ed": "Ciano", "#cb32e6": "Magenta", "#ff5c8a": "Rosa", "#ffb547": "Âmbar",
    "#7ee081": "Verde", "#6c8cff": "Azul", "#ff7a45": "Laranja", "#f5f7fa": "Branco",
};
const ESPECIALIDADES = { beatmaker: "Beatmaker", mixagem: "Mixagem", masterizacao: "Masterização" };

function el(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

function field(label, input, help = "", full = false) {
    const wrap = el("label", `portal-field${full ? " portal-field--full" : ""}`);
    wrap.append(el("span", "portal-field__label", label), input);
    if (help) wrap.append(el("small", "", help));
    return wrap;
}

function input(name, value, attrs = {}) {
    const node = el(attrs.multiline ? "textarea" : "input");
    node.name = name;
    node.value = value || "";
    Object.entries(attrs).forEach(([key, val]) => { if (key !== "multiline") node[key] = val; });
    return node;
}

const pageUrl = slug => `${location.origin}/produtores/${slug}`;

export async function loadProfilePage(root) {
    if (!root) return;
    root.replaceChildren(el("p", "", "Carregando sua página..."));
    try {
        render(root, await api.obterPaginaPerfil());
    } catch (error) {
        root.replaceChildren(el("p", "producer-message--error", error.message));
    }
}

function imageControl(root, perfil, tipo, status) {
    const box = el("div", `profile-editor__image profile-editor__image--${tipo}`);
    const preview = el("div", "profile-editor__image-preview");
    const url = perfil[`${tipo}_url`];
    if (url) {
        const image = el("img");
        image.src = url;
        image.alt = tipo === "foto" ? "Sua foto atual" : "Sua capa atual";
        preview.append(image);
    } else {
        preview.append(el("span", "", tipo === "foto" ? "Sem foto" : "Sem capa"));
    }
    const actions = el("div", "profile-editor__image-actions");
    const file = el("input");
    file.type = "file";
    file.accept = ".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp";
    file.id = `profile-${tipo}-file`;
    file.className = "sr-only";
    // Its own "Enviar/Trocar" button replaces the portal's generic file picker.
    file.dataset.picker = "";
    const choose = el("label", "btn-outline", url ? "Trocar" : "Enviar");
    choose.htmlFor = file.id;
    actions.append(file, choose);
    if (url) {
        const remove = el("button", "btn-outline", "Remover");
        remove.type = "button";
        remove.addEventListener("click", async () => {
            remove.disabled = true;
            try {
                render(root, await api.removerImagemPerfil(tipo), tipo === "foto" ? "Foto removida." : "Capa removida.");
            } catch (error) {
                status.textContent = error.message;
                remove.disabled = false;
            }
        });
        actions.append(remove);
    }
    file.addEventListener("change", async () => {
        const chosen = file.files?.[0];
        file.value = "";
        if (!chosen) return;
        if (!/^image\/(jpeg|png|webp)$/.test(chosen.type)) {
            status.textContent = "Envie uma imagem JPG, PNG ou WebP.";
            return;
        }
        // The original only needs to open here; what is sent is the cropped version.
        if (chosen.size > 25 * 1024 * 1024) {
            status.textContent = "A imagem é grande demais (até 25 MB).";
            return;
        }
        let cropped;
        try {
            cropped = await cropImage(chosen, tipo === "foto"
                ? { aspect: 1, width: 800, height: 800, round: true, title: "Ajustar foto", name: "foto" }
                : { aspect: 16 / 5, width: 1600, height: 500, title: "Ajustar capa", name: "capa" });
        } catch (error) {
            status.textContent = error.message;
            return;
        }
        if (!cropped) return;
        status.textContent = "Enviando imagem...";
        choose.classList.add("is-busy");
        try {
            render(root, await api.enviarImagemPerfil(tipo, cropped), tipo === "foto" ? "Foto atualizada." : "Capa atualizada.");
        } catch (error) {
            status.textContent = error.message;
            choose.classList.remove("is-busy");
        }
    });
    const label = tipo === "foto" ? "Foto" : "Capa";
    const help = tipo === "foto" ? "JPG, PNG ou WebP. Você enquadra antes de enviar." : "Formato de banner (16:5). Você enquadra antes de enviar.";
    const text = el("div", "profile-editor__image-text");
    text.append(el("strong", "", label), el("small", "", help), actions);
    box.append(preview, text);
    return box;
}

function render(root, perfil, message = "") {
    const section = el("section", "portal-form-section profile-editor");
    section.setAttribute("aria-labelledby", "profile-editor-title");
    const head = el("div", "profile-editor__head");
    const title = el("h2", "", "Página pública");
    title.id = "profile-editor-title";
    const view = el("a", "btn-outline", "Ver minha página");
    view.href = `/produtores/${perfil.slug}`;
    view.target = "_blank";
    view.rel = "noopener";
    head.append(title, view);
    const intro = el("p", "portal-form-help",
        "Clientes chegam aqui pelo seu nome nos beats. A página mostra seus trabalhos no portfólio, os projetos entregues na Mirai e seus beats; aqui você personaliza o resto.");
    const status = el("p", "profile-editor__status");
    status.setAttribute("role", "status");
    status.textContent = message;

    // Metrics and account data, read-only.
    const facts = el("ul", "profile-editor__facts");
    [["Nome", perfil.nome], ["Portfólio", perfil.metricas.portfolio], ["Na Mirai", perfil.metricas.mirai], ["Beats", perfil.beats]]
        .forEach(([label, value]) => {
            const item = el("li");
            item.append(el("span", "", label), el("strong", "", String(value)));
            facts.append(item);
        });
    const account = el("p", "portal-form-help",
        `Nome e especialidades (${perfil.especialidades.map(item => ESPECIALIDADES[item] || item).join(", ") || "nenhuma"}) vêm da sua conta; para mudar, fale com o estúdio.`);

    const images = el("div", "profile-editor__images");
    images.append(imageControl(root, perfil, "foto", status), imageControl(root, perfil, "capa", status));

    const form = el("form", "profile-editor__form");
    form.noValidate = false;
    const grid = el("div", "portal-form-grid");
    const slug = input("slug", perfil.slug, { maxLength: 40, pattern: "[a-z0-9][a-z0-9-]{1,38}[a-z0-9]", autocapitalize: "none", spellcheck: false });
    const slugHelp = el("small", "profile-editor__url", pageUrl(perfil.slug));
    slug.addEventListener("input", () => {
        slug.value = slug.value.toLowerCase().replace(/[^a-z0-9-]/g, "");
        slugHelp.textContent = pageUrl(slug.value || perfil.slug_padrao);
    });
    const slugField = field("Endereço da página", slug, "", true);
    slugField.append(slugHelp, el("small", "", `Letras minúsculas, números e hífen. O endereço original (${perfil.slug_padrao}) continua funcionando.`));
    const headline = input("headline", perfil.headline, { maxLength: 120, placeholder: "Ex.: Beats de trap e mix para artistas independentes" });
    const cidade = input("cidade", perfil.cidade, { maxLength: 80, placeholder: "Ex.: São Paulo, SP" });
    const bio = input("bio", perfil.bio, { multiline: true, maxLength: 1500, rows: 6, placeholder: "Conte sua trajetória, estilos e com quem já trabalhou." });
    const counter = el("small", "profile-editor__counter");
    const count = () => { counter.textContent = `${bio.value.length}/1500`; };
    bio.addEventListener("input", count);
    count();
    const bioField = field("Bio", bio, "", true);
    bioField.append(counter);
    grid.append(slugField, field("Frase de apresentação", headline, "Aparece logo abaixo do seu nome."),
        field("Cidade", cidade), bioField);

    const colors = el("fieldset", "profile-editor__colors");
    colors.append(el("legend", "", "Cor de destaque"));
    perfil.cores.forEach(cor => {
        const option = el("label", "profile-editor__color");
        const radio = el("input");
        radio.type = "radio";
        radio.name = "cor";
        radio.value = cor;
        radio.checked = cor === perfil.cor;
        const swatch = el("span", "profile-editor__swatch");
        swatch.style.background = cor;
        option.append(radio, swatch, el("span", "sr-only", NOMES_CORES[cor] || cor));
        option.title = NOMES_CORES[cor] || cor;
        colors.append(option);
    });

    const tabs = el("fieldset", "profile-editor__tabs");
    tabs.append(el("legend", "", "Aba que abre primeiro"));
    [["portfolio", "Portfólio"], ["beats", "Beats"]].forEach(([value, label]) => {
        const option = el("label", "profile-editor__choice");
        const radio = el("input");
        radio.type = "radio";
        radio.name = "aba_inicial";
        radio.value = value;
        radio.checked = perfil.aba_inicial === value;
        option.append(radio, el("span", "", label));
        tabs.append(option);
    });
    tabs.append(el("small", "", "A aba Beats só aparece quando você tem beats no catálogo."));

    const links = el("fieldset", "profile-editor__links");
    links.append(el("legend", "", "Redes e links"));
    const linksGrid = el("div", "portal-form-grid");
    (perfil.redes || Object.keys(REDES)).forEach(rede => {
        const [label, placeholder] = REDES[rede] || [rede, "https://"];
        linksGrid.append(field(label, input(`link_${rede}`, perfil.links?.[rede], { type: "url", maxLength: 300, placeholder })));
    });
    links.append(linksGrid, el("small", "", "Use endereços completos começando com https://."));

    const footer = el("div", "portal-form-footer");
    const save = el("button", "btn-cta", "Salvar página");
    save.type = "submit";
    footer.append(status, save);
    form.append(grid, colors, tabs, links, footer);
    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        const data = new FormData(form);
        const payload = {
            slug: String(data.get("slug") || "").trim(),
            headline: String(data.get("headline") || ""),
            cidade: String(data.get("cidade") || ""),
            bio: String(data.get("bio") || ""),
            cor: String(data.get("cor") || ""),
            aba_inicial: String(data.get("aba_inicial") || "portfolio"),
            links: Object.fromEntries((perfil.redes || Object.keys(REDES)).map(rede => [rede, String(data.get(`link_${rede}`) || "").trim()])),
        };
        save.disabled = true;
        status.textContent = "Salvando...";
        try {
            render(root, await api.salvarPaginaPerfil(payload), "Página salva.");
        } catch (error) {
            status.textContent = error.message;
            save.disabled = false;
        }
    });

    section.append(head, intro, facts, account, images, form);
    root.replaceChildren(section);
}
