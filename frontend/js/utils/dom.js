export const $ = (id) =>
    document.getElementById(id);

export const $$ = (selector) =>
    document.querySelector(selector);

export const $$$ = (selector) =>
    document.querySelectorAll(selector);

export function show(element) {
    element.classList.remove("hidden");

}

export function hide(element) {
    element.classList.add("hidden");

}

export function html(element, value) {
    element.innerHTML = value;

}

export function text(element, value) {
    element.innerText = value;

}