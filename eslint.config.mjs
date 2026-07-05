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