import { state } from './state.js';

export const CalculatorLogic = {
    duracao: (val) => Math.max(0, (val || 0) - 180) * state.configGlobal.val_extra_duracao,
    pessoas: (val) => Math.max(0, (val || 1) - 1) * state.configGlobal.val_extra_pessoa,
    canais_voz: (val) => Math.max(0, (val || 0) - 5) * state.configGlobal.val_extra_canal_voz,
    melodias: (val) => Math.max(0, (val || 0) - 5) * state.configGlobal.val_extra_melodia,
    revisoes: (val) => Math.max(0, (val || 1) - 1) * state.configGlobal.val_extra_revisao,
    
    inst_aberto: (val, canaisInst) => (val === 'sim') ? (parseInt(canaisInst) || 0) * state.configGlobal.val_extra_canal_inst : 0,
    instrumentacao: (val) => val === 'hibridos' ? state.configGlobal.val_inst_hibrido : val === 'gravados' ? state.configGlobal.val_inst_gravado : 0,
    exclusividade: (val) => (val === 'nao') ? -state.configGlobal.val_lease_desconto : 0,
    prazo: (val) => val === 'urgente' ? state.configGlobal.val_prazo_urgente : val === 'express' ? state.configGlobal.val_prazo_express : 0
};

