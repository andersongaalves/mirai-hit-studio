export function createDivElement(
    className = ""
) {

    const div =
        document.createElement("div");


    div.className =
        className;


    return div;

}



export function createTextElement(
    tag,
    text = "",
    className = ""
) {

    const element =
        document.createElement(tag);


    element.textContent =
        text;


    element.className =
        className;


    return element;

}



export function createSelectElement({

    value,

    options,

    className = ""

}) {

    const select =
        document.createElement("select");


    select.className =
        className;


    options.forEach(item => {


        const option =
            document.createElement("option");


        option.value =
            item.value;


        option.textContent =
            item.label;


        if(item.value === value){

            option.selected = true;

        }


        select.appendChild(option);


    });


    return select;

}



export function createProducaoCardElement() {

    const card =
        createDivElement(
            "admin-list-item"
        );


    const info =
        createDivElement(
            "producao-info"
        );


    const actions =
        createDivElement(
            "producao-actions"
        );


    card.append(
        info,
        actions
    );


    return {

        card,

        info,

        actions

    };

}