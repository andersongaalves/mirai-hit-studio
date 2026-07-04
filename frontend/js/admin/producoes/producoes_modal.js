import { $ } 
from "../../utils/dom.js";
import {salvarEtapas, salvarPrazo} from "./producoes.js";

let producaoAtual = null;

function renderizarEtapas(){

    const container =
        $("prod_etapas");


    container.innerHTML = "";


    let etapas =
        JSON.parse(
            producaoAtual.etapas || "[]"
        );


    etapas.forEach(
        (etapa, index) => {


            const label =
                document.createElement("label");


            const checkbox =
                document.createElement("input");


            checkbox.type =
                "checkbox";


            checkbox.checked =
                etapa.feito;



            checkbox.onchange = () => {


                etapas[index].feito =
                    checkbox.checked;


                salvarEtapas(

                    producaoAtual.id,

                    etapas

                );


            };


            label.append(

                checkbox,

                etapa.nome

            );


            container.appendChild(
                label
            );


        }
    );

}

export function abrirModalProducao(
    producao
){

    if(!producao) return;


    producaoAtual =
        producao;


    $("prod_titulo").innerText =
        producao.titulo;


    $("prod_cliente").innerText =
        producao.cliente;


    $("prod_servico").innerText =
        producao.servico;


    $("prod_status").innerText =
        producao.status;


    $("prod_data").innerText =
        producao.created_at;


    $("prod_observacoes").value =
        producao.observacoes || "";

    renderizarEtapas();

    $("modal-producao")
        .classList
        .remove("hidden");

    $("prod_prazo").value =

    producao.prazo_entrega

        ?

        producao.prazo_entrega.slice(
            0,
            16
        )

        :

        "";
    
        const btnPrazo =
            $("btn-save-prazo");


        if(btnPrazo){

            btnPrazo.onclick = () => {


                salvarPrazo(

                    producaoAtual.id,

                    $("prod_prazo").value

                );


            };

}

}



export function fecharModalProducao(){

    $("modal-producao")
        .classList
        .add("hidden");

}