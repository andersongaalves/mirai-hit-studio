// The API supplies the eligible percentage; older responses retain the global discount.
export function catalogDiscount(service, config = {}) {
    const configured = service?.preco_catalogo?.desconto_percentual;
    const value = configured != null ? Number(configured)
        : service?.aplica_desconto ? Number(config.desconto || 0) : 0;
    return Number.isFinite(value) && value >= 0 && value <= 100 ? value : 0;
}
