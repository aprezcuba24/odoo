import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { assertPosFreeStock, buildQtyByProduct, isProductStorable } from "./stock_check";

function snapshotOrderLineQtys(order) {
    return (order?.lines || []).map((line) => ({
        uuid: line.uuid,
        qty: line.getQuantity?.() ?? line.qty,
    }));
}

function revertOrderLinesToSnapshot(order, snapshot) {
    const prevByUuid = Object.fromEntries(snapshot.map((s) => [s.uuid, s.qty]));
    for (const line of [...(order.lines || [])]) {
        if (!(line.uuid in prevByUuid)) {
            order.removeOrderline(line);
            continue;
        }
        const prevQty = prevByUuid[line.uuid];
        const currentQty = line.getQuantity?.() ?? line.qty;
        if (currentQty !== prevQty) {
            line.setQuantity(prevQty, true);
        }
    }
}

patch(PosStore.prototype, {
    async addLineToOrder(vals, order, opts = {}, configure = true) {
        const productTmpl =
            typeof vals.product_tmpl_id === "number"
                ? this.data.models["product.template"].get(vals.product_tmpl_id)
                : vals.product_tmpl_id;
        const maybeCombo =
            productTmpl?.isCombo?.() || (productTmpl?.combo_ids?.length ?? 0) > 0;
        const draftQty = vals.qty ?? (order.preset_id?.is_return ? -1 : 1);
        // Only resolve a draft variant when it is already known. Configurable templates
        // open the configurator in super.addLineToOrder; checking product_variant_ids[0]
        // would block the whole product if that first variant is out of stock.
        const knownVariant =
            vals.product_id ||
            opts.presetVariant ||
            (!productTmpl?.isConfigurable?.() && productTmpl?.product_variant_ids?.[0]);
        const productId = knownVariant?.id ?? knownVariant;
        const isWeighted =
            Boolean(productTmpl?.to_weight) && Boolean(this.config.iface_electronic_scale);

        // Early check for simple storable adds (avoids creating then rolling back).
        if (
            !maybeCombo &&
            !isWeighted &&
            productId &&
            draftQty > 0 &&
            isProductStorable(this.models["product.product"].get(productId))
        ) {
            const qtyByProduct = buildQtyByProduct(order, {
                extraLines: [{ product_id: productId, qty: draftQty }],
            });
            if (!(await assertPosFreeStock(this, qtyByProduct))) {
                return;
            }
        }

        const snapshot = snapshotOrderLineQtys(order);
        const line = await super.addLineToOrder(vals, order, opts, configure);
        if (!line) {
            return line;
        }

        // Combo / weight / race after early check: verify final ticket and restore on failure.
        if (!(await assertPosFreeStock(this, buildQtyByProduct(order)))) {
            revertOrderLinesToSnapshot(order, snapshot);
            return;
        }
        return line;
    },
});
