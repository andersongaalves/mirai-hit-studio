const LOCAL_API = "http://localhost:8000";
const PROD_API = "https://mirai-hit-studio.onrender.com";

const isLocal =
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1";

export const API_URL = isLocal
    ? LOCAL_API
    : PROD_API;