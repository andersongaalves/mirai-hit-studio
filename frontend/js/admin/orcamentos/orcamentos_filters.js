import { orcamentosState } from "./orcamentos_state.js";


export function filtrarOrcamentos() {

    return orcamentosState.lista.filter(

        item => {

            const busca =
                orcamentosState.filtro.busca
                    .toLowerCase();


            const filtroStatus =
                orcamentosState.filtro.status;


            const matchBusca =

                item.nome_cliente
                    .toLowerCase()
                    .includes(busca)

                ||

                item.servico
                    .toLowerCase()
                    .includes(busca);


            const matchStatus =

                filtroStatus === "todos"

                ||

                item.status === filtroStatus;


            return (

                matchBusca

                &&

                matchStatus

            );

        }

    );

}