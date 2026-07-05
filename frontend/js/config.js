const LOCAL_API = "http://localhost:8000";
const PROD_API = "https://mirai-hit-studio.onrender.com";

const LOCAL_HOSTS = [
    "localhost",
    "127.0.0.1"
];

const isLocal = LOCAL_HOSTS.includes(
    window.location.hostname
);

export const API_URL =
    isLocal ? LOCAL_API : PROD_API;