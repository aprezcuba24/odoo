import { patch } from "@web/core/utils/patch";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { assertPosFreeStock, buildQtyByProduct } from "./stock_check";

patch(OrderPaymentValidation.prototype, {
    async askBeforeValidation() {
        if (!(await super.askBeforeValidation(...arguments))) {
            return false;
        }
        const order = this.order;
        if (!order) {
            return true;
        }
        return await assertPosFreeStock(this.pos, buildQtyByProduct(order));
    },
});
