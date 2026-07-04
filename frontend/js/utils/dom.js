// ===========================
// SELECTORS
// ===========================

export const $ = (id) =>
    document.getElementById(id);


export const $$ = (selector) =>
    document.querySelector(selector);


export const $$$ = (selector) =>
    document.querySelectorAll(selector);



// ===========================
// VISIBILITY
// ===========================

export function show(element) {

    element
        ?.classList
        .remove("hidden");

}



export function hide(element) {

    element
        ?.classList
        .add("hidden");

}



// ===========================
// CONTENT
// ===========================

export function html(
    element,
    value = ""
) {

    if (!element) return;


    element.innerHTML =
        value;

}



export function text(
    element,
    value = ""
) {

    if (!element) return;


    element.innerText =
        value;

}



export function clear(
    element
) {

    if (!element) return;


    element.innerHTML = "";

}



// ===========================
// EVENTS
// ===========================

export function on(
    element,
    event,
    callback
) {

    element
        ?.addEventListener(

            event,

            callback

        );

}