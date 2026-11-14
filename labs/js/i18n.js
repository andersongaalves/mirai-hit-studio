// Languages of the Mirai Hit Labs store: English at /, Portuguese at /pt/.
// Each page declares its language in <html lang>; the texts built by the scripts live here.

export const LANG = (document.documentElement.lang || "en").toLowerCase().startsWith("pt") ? "pt" : "en";
export const LOCALE = LANG === "pt" ? "pt-BR" : "en-US";
export const SITE_URL = "https://labs.miraihitstudio.com.br";
const PREFIX = LANG === "pt" ? "/pt" : "";
const STORAGE_KEY = "labs-lang";

const STRINGS = {
    en: {
        offline: "We couldn't reach the store right now. Check your connection and try again.",
        notFound: "Plugin not found.",
        unavailable: "The store is unavailable at the moment. Try again in a few minutes.",
        free: "Free",
        sale: "Sale",
        featured: "Featured",
        formats: "Formats",
        systems: "Systems",
        and: " and ",
        soon: "Coming soon",
        coverAlt: "{name} plugin cover",
        retry: "Try again",
        emptyTitle: "The first plugins are on the way",
        emptyText: "We're finishing the first Mirai Hit Labs tools. Follow @miraihitstudio to hear about the launch.",
        catalogDown: "Catalog unavailable",
        count: "{n} plugin",
        countMany: "{n} plugins",
        buy: "Buy",
        buyLabel: "Buy",
        getFree: "Get it free",
        oneTime: "one-time payment",
        buyNoteFree: "Sign in to your Mirai Hit Studio account (or create one, it's free) and the plugin goes to My plugins, with the key and the installers.",
        buyNotePaid: "Sign in to your Mirai Hit Studio account (or create one, it's free) and pay by Pix or card. The key and the installers stay in My plugins.",
        youAreHere: "You are here",
        plugins: "Plugins",
        version: "Version",
        license: "License",
        licenseValue: "Personal, with activation key",
        about: "About",
        features: "Features",
        inAction: "In action",
        videoTitle: "{name} video",
        watchVideo: "Watch video",
        requirements: "Requirements",
        missingTitle: "Plugin not found",
        missingPage: "Plugin not found | Mirai Hit Labs",
        missingAddress: "This address doesn't match any plugin.",
        missingGone: "It may have left the catalog or the address changed.",
        allPlugins: "See all plugins",
    },
    pt: {
        offline: "Não foi possível falar com a loja agora. Verifique sua conexão e tente de novo.",
        notFound: "Plugin não encontrado.",
        unavailable: "A loja está indisponível no momento. Tente de novo em alguns minutos.",
        free: "Grátis",
        sale: "Promoção",
        featured: "Destaque",
        formats: "Formatos",
        systems: "Sistemas",
        and: " e ",
        soon: "Em breve",
        coverAlt: "Capa do plugin {name}",
        retry: "Tentar de novo",
        emptyTitle: "Os primeiros plugins estão a caminho",
        emptyText: "Estamos finalizando as primeiras ferramentas da Mirai Hit Labs. Siga @miraihitstudio para saber do lançamento.",
        catalogDown: "Catálogo indisponível",
        count: "{n} plugin",
        countMany: "{n} plugins",
        buy: "Comprar",
        buyLabel: "Comprar",
        getFree: "Baixar grátis",
        oneTime: "pagamento único",
        buyNoteFree: "Entre na sua conta da Mirai Hit Studio (ou crie uma, é grátis) e o plugin vai para Meus plugins, com a chave e os instaladores.",
        buyNotePaid: "Você entra na sua conta da Mirai Hit Studio (ou cria uma, é grátis) e paga por Pix ou cartão. A chave e os instaladores ficam em Meus plugins.",
        youAreHere: "Você está em",
        plugins: "Plugins",
        version: "Versão",
        license: "Licença",
        licenseValue: "Pessoal, com chave de ativação",
        about: "Sobre",
        features: "Recursos",
        inAction: "Em ação",
        videoTitle: "Vídeo do {name}",
        watchVideo: "Ver vídeo",
        requirements: "Requisitos",
        missingTitle: "Plugin não encontrado",
        missingPage: "Plugin não encontrado | Mirai Hit Labs",
        missingAddress: "Este endereço não corresponde a nenhum plugin.",
        missingGone: "Ele pode ter saído do catálogo ou o endereço mudou.",
        allPlugins: "Ver todos os plugins",
    },
};

// Account, purchase and My plugins
Object.assign(STRINGS.en, {
    tooMany: "Too many attempts in a row. Wait a little and try again.",
    genericError: "Something went wrong. Try again.",
    sessionExpired: "Your session has ended. Sign in again.",
    customersOnly: "This account can't buy on the store. Use a customer account.",
    wrongLogin: "Wrong username or password.",
    usernameTaken: "This username is taken. Choose another one.",
    linkUsed: "This link was already used. Sign in with your account.",
    linkExpired: "This link has expired. Ask for a new one.",
    linkRevoked: "This link is no longer valid. Ask for a new one.",
    linkInvalid: "This link is invalid or has expired. Ask for a new one.",
    alreadyOwned: "You already own this plugin. Download it in My plugins.",
    completeProfile: "Your account is missing details. Contact us to finish it.",
    accountTitle: "Your account | Mirai Hit Labs",
    signInTitle: "Sign in",
    signInLead: "Use your Mirai Hit Labs account. Mirai Hit Studio customers sign in with the same username and password.",
    username: "Username",
    password: "Password",
    signInButton: "Sign in",
    signingIn: "Signing in...",
    forgot: "Forgot your password?",
    forgotTitle: "Reset your password",
    forgotLead: "Enter your account e-mail. If it's registered, we'll send a link to create a new password.",
    email: "E-mail",
    sendLink: "Send link",
    sending: "Sending...",
    forgotSent: "If this e-mail belongs to an account, the link is on its way. Check your inbox and spam folder.",
    backToSignIn: "Back to sign in",
    signUpTitle: "Create an account",
    signUpLead: "Free. You get your plugins, keys and installers in one place.",
    name: "Name",
    privacy: "I agree to the processing of my data to create and run my account, as described in the privacy policy.",
    privacyLink: "privacy policy",
    createButton: "Create account",
    creating: "Creating...",
    signUpSent: "Almost there! We sent a confirmation link to {email}. Open it to choose your username and password.",
    resend: "Resend e-mail",
    resent: "If the account is waiting for confirmation, a new link is on its way.",
    signedInAs: "Signed in as {name}",
    signOut: "Sign out",
    goMyPlugins: "Go to My plugins",
    activateTitle: "Confirm your account",
    activateLead: "Choose the username and password you'll use to sign in.",
    newPassword: "Password (8 or more characters)",
    confirmPassword: "Confirm password",
    passwordsDiffer: "The passwords don't match.",
    passwordShort: "Use at least 8 characters.",
    activateButton: "Confirm account",
    activating: "Confirming...",
    activated: "Account confirmed! Taking you to My plugins...",
    checkingLink: "Checking the link...",
    noToken: "This link is incomplete. Open the link from the e-mail again.",
    resetTitle: "Create a new password",
    resetLead: "Choose a new password for your account.",
    resetButton: "Save new password",
    saving: "Saving...",
    resetDone: "Password changed. Sign in with the new password.",
    myPluginsTitle: "My plugins",
    myPluginsLead: "Your licenses, keys and installers.",
    myPluginsPage: "My plugins | Mirai Hit Labs",
    signInToSee: "Sign in to see your plugins.",
    noPlugins: "You don't have any plugins yet.",
    browse: "Browse plugins",
    licenseKey: "License key",
    copy: "Copy",
    copied: "Copied",
    download: "Download for {system}",
    preparing: "Preparing...",
    waitingPayment: "Waiting for payment",
    payNow: "Go to payment",
    suspended: "License suspended: the payment was reversed. Contact us if this is a mistake.",
    loadingPlugins: "Loading your plugins...",
    buyNoteFreeLabs: "Sign in or create a free Mirai Hit Labs account and the plugin goes to My plugins, with the key and the installers.",
    buyNotePaidLabs: "Sign in or create a free Mirai Hit Labs account and pay by card with Stripe, in US dollars. The key and the installers stay in My plugins. Mirai Hit Studio customers use the same login.",
    checkoutCancelled: "Payment cancelled. You can try again whenever you want.",
    paymentReceived: "Payment received! Your plugin is ready below.",
    paymentConfirming: "We're confirming your payment with Stripe. It usually takes a few seconds; refresh this page if the plugin doesn't show up.",
    signInToBuy: "Sign in to buy",
    buying: "One moment...",
    gotFree: "Done! The plugin is in My plugins.",
});
Object.assign(STRINGS.pt, {
    tooMany: "Muitas tentativas seguidas. Aguarde um pouco e tente de novo.",
    genericError: "Algo deu errado. Tente de novo.",
    sessionExpired: "Sua sessão terminou. Entre de novo.",
    customersOnly: "Esta conta não compra na loja. Use uma conta de cliente.",
    wrongLogin: "Usuário ou senha incorretos.",
    usernameTaken: "Este usuário já existe. Escolha outro.",
    linkUsed: "Este link já foi usado. Entre com a sua conta.",
    linkExpired: "Este link expirou. Peça um novo.",
    linkRevoked: "Este link não vale mais. Peça um novo.",
    linkInvalid: "Este link é inválido ou expirou. Peça um novo.",
    alreadyOwned: "Você já tem este plugin. Baixe em Meus plugins.",
    completeProfile: "Faltam dados na sua conta. Fale com a gente para completar.",
    accountTitle: "Sua conta | Mirai Hit Labs",
    signInTitle: "Entrar",
    signInLead: "Use sua conta da Mirai Hit Labs. Clientes da Mirai Hit Studio entram com o mesmo usuário e senha.",
    username: "Usuário",
    password: "Senha",
    signInButton: "Entrar",
    signingIn: "Entrando...",
    forgot: "Esqueceu a senha?",
    forgotTitle: "Redefinir a senha",
    forgotLead: "Informe o e-mail da conta. Se ele estiver cadastrado, enviamos um link para criar uma nova senha.",
    email: "E-mail",
    sendLink: "Enviar link",
    sending: "Enviando...",
    forgotSent: "Se este e-mail for de uma conta, o link está a caminho. Confira a caixa de entrada e o spam.",
    backToSignIn: "Voltar para entrar",
    signUpTitle: "Criar conta",
    signUpLead: "Grátis. Seus plugins, chaves e instaladores ficam num lugar só.",
    name: "Nome",
    privacy: "Concordo com o tratamento dos meus dados para criar e manter minha conta, conforme a política de privacidade.",
    privacyLink: "política de privacidade",
    createButton: "Criar conta",
    creating: "Criando...",
    signUpSent: "Quase lá! Enviamos um link de confirmação para {email}. Abra para escolher seu usuário e senha.",
    resend: "Reenviar e-mail",
    resent: "Se a conta estiver aguardando confirmação, um novo link está a caminho.",
    signedInAs: "Conectado como {name}",
    signOut: "Sair",
    goMyPlugins: "Ir para Meus plugins",
    activateTitle: "Confirme sua conta",
    activateLead: "Escolha o usuário e a senha que você vai usar para entrar.",
    newPassword: "Senha (8 caracteres ou mais)",
    confirmPassword: "Confirme a senha",
    passwordsDiffer: "As senhas não são iguais.",
    passwordShort: "Use pelo menos 8 caracteres.",
    activateButton: "Confirmar conta",
    activating: "Confirmando...",
    activated: "Conta confirmada! Levando você para Meus plugins...",
    checkingLink: "Conferindo o link...",
    noToken: "Este link está incompleto. Abra de novo o link do e-mail.",
    resetTitle: "Crie uma nova senha",
    resetLead: "Escolha uma nova senha para a sua conta.",
    resetButton: "Salvar nova senha",
    saving: "Salvando...",
    resetDone: "Senha alterada. Entre com a nova senha.",
    myPluginsTitle: "Meus plugins",
    myPluginsLead: "Suas licenças, chaves e instaladores.",
    myPluginsPage: "Meus plugins | Mirai Hit Labs",
    signInToSee: "Entre para ver seus plugins.",
    noPlugins: "Você ainda não tem plugins.",
    browse: "Ver plugins",
    licenseKey: "Chave de licença",
    copy: "Copiar",
    copied: "Copiada",
    download: "Baixar para {system}",
    preparing: "Preparando...",
    waitingPayment: "Aguardando pagamento",
    payNow: "Ir para o pagamento",
    suspended: "Licença suspensa: o pagamento foi revertido. Fale com a gente se for um engano.",
    loadingPlugins: "Carregando seus plugins...",
    buyNoteFreeLabs: "Entre ou crie uma conta grátis da Mirai Hit Labs e o plugin vai para Meus plugins, com a chave e os instaladores.",
    buyNotePaidLabs: "Entre ou crie uma conta grátis da Mirai Hit Labs e pague por Pix ou cartão. A chave e os instaladores ficam em Meus plugins. Clientes da Mirai Hit Studio usam o mesmo login.",
    checkoutCancelled: "Pagamento cancelado. Você pode tentar de novo quando quiser.",
    paymentReceived: "Pagamento recebido! Seu plugin já está aqui embaixo.",
    paymentConfirming: "Estamos confirmando seu pagamento. Costuma levar alguns segundos; atualize a página se o plugin não aparecer.",
    signInToBuy: "Entrar para comprar",
    buying: "Um momento...",
    gotFree: "Pronto! O plugin está em Meus plugins.",
});

// A "next" address after signing in: only paths inside this store.
export function safeNext(value) {
    return typeof value === "string" && /^\/(?!\/)[\w\-./?=&%#]*$/.test(value) ? value : null;
}

export function t(key, vars = {}) {
    let text = STRINGS[LANG][key] ?? STRINGS.en[key] ?? key;
    for (const [name, value] of Object.entries(vars)) text = text.replaceAll(`{${name}}`, String(value));
    return text;
}

// A path inside the store, in the page's language ("/plugins/x" -> "/pt/plugins/x").
export function href(path) {
    return `${PREFIX}${path}`;
}

// A plugin text in the page's language; empty English texts fall back to Portuguese.
export function localized(plugin, field) {
    if (LANG === "en") {
        const value = plugin.en?.[field];
        if (Array.isArray(value) ? value.length : value) return value;
    }
    return plugin[field];
}

// The same page in the other language.
export function counterpart(pathname) {
    if (LANG === "pt") return pathname.replace(/^\/pt(?=\/|$)/, "") || "/";
    return pathname === "/" ? "/pt/" : `/pt${pathname}`;
}

function savedLanguage() {
    try { return window.localStorage.getItem(STORAGE_KEY); } catch { return null; }
}

function saveLanguage(lang) {
    try { window.localStorage.setItem(STORAGE_KEY, lang); } catch { /* private mode: the choice just isn't remembered */ }
}

// Points the EN | PT switch at this page in the other language and remembers the choice.
// Someone who chose Portuguese before and lands on the English store goes to /pt.
export function initLanguage() {
    if (LANG === "en" && savedLanguage() === "pt") {
        window.location.replace(counterpart(window.location.pathname) + window.location.search + window.location.hash);
        return false;
    }
    document.querySelectorAll("[data-lang-switch]").forEach(link => {
        link.href = counterpart(window.location.pathname) + window.location.search + window.location.hash;
        link.addEventListener("click", () => saveLanguage(link.dataset.langSwitch));
    });
    return true;
}
