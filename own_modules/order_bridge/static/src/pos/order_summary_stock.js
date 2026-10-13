import { patch } from "@web/core/utils/patch";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { assertPosFreeStock, buildQtyByProduct, isProductStorable } from "./stock_check";

function lineQtyAfterNumpad(selectedLine, buffer) {
    if (buffer === null || buffer === "remove") {
        return null;
    }
    return typeof buffer === "number" ? buffer : parseFloat("" + (buffer || 0));
}

patch(OrderSummary.prototype, {
    async updateSelectedOrderline(args) {
        const { buffer } = args || {};
        if (this.pos.numpadMode === "quantity" && buffer !== null && buffer !== "remove") {
            let selectedLine = this.currentOrder?.getSelectedOrderline?.();
            if (selectedLine?.combo_parent_id) {
                selectedLine = selectedLine.combo_parent_id;
            }
            const newQty = lineQtyAfterNumpad(selectedLine, buffer);
            const currentQty = selectedLine?.getQuantity?.() ?? selectedLine?.qty ?? 0;
            if (
                selectedLine &&
                newQty != null &&
                !Number.isNaN(newQty) &&
                newQty > currentQty &&
                isProductStorable(selectedLine.product_id)
            ) {
                const qtyByProduct = buildQtyByProduct(this.currentOrder, {
                    overrideLineId: selectedLine.id,
                    overrideQty: newQty,
                });
                if (!(await assertPosFreeStock(this.pos, qtyByProduct))) {
                    this.numberBuffer.reset();
                    return;
                }
            }
        }
        return await super.updateSelectedOrderline(...arguments);
    },

    async updateQuantityNumber(newQuantity) {
        if (newQuantity !== null) {
            let selectedLine = this.currentOrder.getSelectedOrderline();
            if (selectedLine?.combo_parent_id) {
                selectedLine = selectedLine.combo_parent_id;
            }
            const currentQuantity = selectedLine?.getQuantity?.() ?? selectedLine?.qty ?? 0;
            if (
                selectedLine &&
                newQuantity >= currentQuantity &&
                isProductStorable(selectedLine.product_id)
            ) {
                const qtyByProduct = buildQtyByProduct(this.currentOrder, {
                    overrideLineId: selectedLine.id,
                    overrideQty: newQuantity,
                });
                if (!(await assertPosFreeStock(this.pos, qtyByProduct))) {
                    return false;
                }
            }
        }
        return await super.updateQuantityNumber(newQuantity);
    },
});
