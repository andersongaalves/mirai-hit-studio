const LOCAL_API = "http://localhost:8000";
const PROD_API = "https://mirai-hit-studio.onrender.com";
const TEST_API = "https://SEU-BACKEND-DE-TESTE.onrender.com";

const hostname = window.location.hostname;

const isLocal = ["localhost", "127.0.0.1"].includes(hostname);
const isPreview19 =
    hostname === "deploy-preview-19--miraihitstudio.netlify.app";

export const API_URL = isLocal
    ? LOCAL_API
    : isPreview19
        ? TEST_API
        : PROD_API;
