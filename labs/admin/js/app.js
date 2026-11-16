// Mirai Hit Labs admin: sign-in and hash routes (#/plugins/12, #/clientes/3...).
import { clearSession, currentAdmin, savedUser, signIn } from "./api.js";
import { errorBox, loading } from "./ui.js";

const ROUTES = {
    "visao-geral": () => import("./views/overview.js"),
    plugins: () => import("./views/plugins.js"),
    pedidos: () => import("./views/orders.js"),
    clientes: () => import("./views/customers.js"),
    licencas: () => import("./views/licenses.js"),
    cupons: () => import("./views/coupons.js"),
    loja: () => import("./views/store.js"),
};

const $ = id => document.getElementById(id);
let renderId = 0;

function parse() {
    const [path, query = ""] = window.location.hash.replace(/^#\/?/, "").split("?");
    const [route, ...rest] = path.split("/").filter(Boolean);
    return { route: ROUTES[route] ? route : "visao-geral", params: rest.map(decodeURIComponent), query: new URLSearchParams(query) };
}

async function render() {
    const id = ++renderId;
    const { route, params, query } = parse();
    document.querySelectorAll("#nav a").forEach(link => {
        if (link.dataset.route === route) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
    });
    const view = $("view");
    view.replaceChildren(loading());
    try {
        const module = await ROUTES[route]();
        const node = await module.render({ params, query, rerender: render });
        if (id !== renderId) return;
        view.replaceChildren(node);
    } catch (error) {
        if (id !== renderId || error.status === 401) return;
        view.replaceChildren(errorBox(error));
    }
    const label = document.querySelector(`#nav a[data-route="${route}"]`)?.textContent || "Admin";
    document.title = `${label} | Admin Mirai Hit Labs`;
}

function showLogin(text = "") {
    $("shell").hidden = true;
    $("login").hidden = false;
    $("login-status").textContent = text;
    $("login-form").querySelector("[name=username]").focus();
}

function showShell(user) {
    $("login").hidden = true;
    $("shell").hidden = false;
    $("user-name").textContent = user?.nome_exibicao || user?.username || "";
    render();
}

$("login-form").addEventListener("submit", async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector("button");
    const status = $("login-status");
    const username = form.username.value.trim();
    const password = form.password.value;
    if (!username || !password) { status.textContent = "Preencha usuário e senha."; return; }
    button.disabled = true;
    status.textContent = "Entrando...";
    try {
        const user = await signIn(username, password);
        form.password.value = "";
        status.textContent = "";
        showShell(user);
    } catch (error) {
        status.textContent = error.status === 401 ? "Usuário ou senha incorretos." : error.message;
    } finally {
        button.disabled = false;
    }
});

$("logout").addEventListener("click", () => {
    clearSession();
    showLogin("Você saiu do painel.");
});

document.addEventListener("labs-admin:expired", () => showLogin("Sua sessão terminou. Entre de novo."));
window.addEventListener("hashchange", () => { if (!$("shell").hidden) render(); });

(async () => {
    if (!savedUser()) { showLogin(); return; }
    try {
        const user = await currentAdmin();
        if (user) showShell(user);
        else showLogin();
    } catch (error) {
        if (error.status !== 401) showLogin(error.message);
    }
})();
