export default [
    {
        files: [
            "**/*.js"
        ],

        ignores: [
            "node_modules/**"
        ],

        languageOptions: {
            ecmaVersion: "latest",
            sourceType: "module",

            globals: {
                window: "readonly",
                document: "readonly",
                console: "readonly",

                fetch: "readonly",
                localStorage: "readonly",

                FormData: "readonly",
                crypto: "readonly",
                setTimeout: "readonly",
                clearTimeout: "readonly",
                Event: "readonly",
                URL: "readonly",
                URLSearchParams: "readonly",
                HTMLElement: "readonly",
                CustomEvent: "readonly",
                Option: "readonly",
                AbortController: "readonly",
                ResizeObserver: "readonly",
                MutationObserver: "readonly",
                location: "readonly",
                history: "readonly",
                navigator: "readonly",
                sessionStorage: "readonly",
                innerHeight: "readonly",
                atob: "readonly",
                structuredClone: "readonly",
                queueMicrotask: "readonly",
                setInterval: "readonly",

                confirm: "readonly"
            }
        },

        rules: {
            "no-unused-vars": "warn",
            "no-undef": "error",
            "eqeqeq": "warn"
        }
    }
];
