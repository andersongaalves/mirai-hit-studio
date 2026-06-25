function notify(type,title,message){

    let container=document.querySelector(".notification-container");

    if(!container){

        container=document.createElement("div");

        container.className="notification-container";

        document.body.appendChild(container);

    }

    const icons={
        success:"✔",
        error:"✖",
        warning:"⚠"

    };

    const card=document.createElement("div");

    card.className=`notification ${type}`;

    card.innerHTML=`

        <div class="notification-icon">

            ${icons[type]}

        </div>

        <div>

            <div class="notification-title">

                ${title}

            </div>

            <div class="notification-message">

                ${message}

            </div>

        </div>

    `;

    container.appendChild(card);

    setTimeout(()=>{

        card.classList.add("hide");

    },3500);

    setTimeout(()=>{

        card.remove();

    },3900);

}

export function success(message){

    notify(

        "success",

        "Sucesso",

        message

    );

}

export function warning(message){

    notify(

        "warning",

        "Atenção",

        message

    );

}

export function error(message){
    notify(

        "error",
        "Erro",
        message

    );

}