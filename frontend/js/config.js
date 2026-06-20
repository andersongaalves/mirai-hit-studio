const LOCAL_API = "http://localhost:8000";
const PROD_API = "https://mirai-hit-studio.onrender.com";

export const API_URL =
    window.location.hostname === "localhost"
        ? LOCAL_API
        : PROD_API;