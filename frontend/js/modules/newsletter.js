import * as API from "../api.js";
import * as Notify from "../utils/notifications.js";
import * as Validation from "../utils/validation.js";
import { $, $$, $$$ } from "../utils/dom.js";

export function initNewsletter() {

    const btnNewsletter =
        $(
            "btn-newsletter"
        );

    if (!btnNewsletter) return;

    btnNewsletter.addEventListener(
        "click",

        async (event) => {
            event.preventDefault();

            const inputEmail =
                $(
                    "newsletter-email"
                );

            if (!inputEmail) {
                console.error(
                    "Campo newsletter-email não encontrado."
                );
                return;

            }

            const email =
                inputEmail.value
                    .trim()
                    .toLowerCase();

            if (!Validation.required(email)) {
                Notify.warning(
                    "Digite seu e-mail."
                );

                inputEmail.focus();
                return;

            }

            try {
                await API.postNewsletter({
                    email
                });

                Notify.success(
                    "Cadastro realizado com sucesso!"
                );
                inputEmail.value = "";

            }

            catch (error) {
                console.error(error);

                Notify.error(
                    "Erro ao cadastrar e-mail."
                );
            }
        }
    );
}