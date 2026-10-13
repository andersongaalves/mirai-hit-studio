const LOCAL_API = "http://localhost:8000";
const PROD_API = "https://mirai-hit-studio.onrender.com";

const HOST_APIS = new Map([
    ["localhost", LOCAL_API],
    ["127.0.0.1", LOCAL_API],
    ["deploy-preview-19--miraihitstudio.netlify.app", PROD_API],
]);

export const API_URL = HOST_APIS.get(window.location.hostname) || PROD_API;
