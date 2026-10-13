import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ConnectionLostError } from "@web/core/network/rpc";

/**
 * Whether the POS product tracks inventory (loaded on product.template).
 * @param {object} product - product.product record from the POS data model
 */
export function isProductStorable(product) {
    if (!product) {
        return false;
    }
    return Boolean(product.product_tmpl_id?.is_storable);
}

/**
 * Aggregate positive qtys already on the order, optionally overriding one line's qty
 * and adding extra demand (e.g. a new line about to be created).
 *
 * When ``overrideLineId`` is a combo parent, child line qtys are scaled by the same ratio
 * ``setQuantity`` would apply.
 *
 * @param {object} order - pos.order
 * @param {object} [options]
 * @param {number} [options.excludeLineId] - ignore this line id when summing
 * @param {number} [options.overrideLineId]
 * @param {number} [options.overrideQty]
 * @param {Array<{product_id: number, qty: number}>} [options.extraLines]
 * @returns {Map<number, number>} product_id -> qty
 */
export function buildQtyByProduct(order, options = {}) {
    const qtyByProduct = new Map();
    const add = (productId, qty) => {
        if (!productId || !(qty > 0)) {
            return;
        }
        qtyByProduct.set(productId, (qtyByProduct.get(productId) || 0) + qty);
    };

    const overrideId = options.overrideLineId;
    let overrideLine = null;
    let childScale = null;
    if (overrideId != null) {
        overrideLine = (order?.lines || []).find((l) => l.id === overrideId);
        const oldQty = overrideLine?.getQuantity?.() ?? overrideLine?.qty ?? 0;
        if (overrideLine?.combo_line_ids?.length && oldQty) {
            childScale = options.overrideQty / oldQty;
        }
    }
    const childIds = new Set(
        (overrideLine?.combo_line_ids || []).map((c) => c.id)
    );

    for (const line of order?.lines || []) {
        if (options.excludeLineId != null && line.id === options.excludeLineId) {
            continue;
        }
        if (overrideId != null && line.id === overrideId) {
            add(line.product_id?.id, options.overrideQty);
            continue;
        }
        if (childScale != null && childIds.has(line.id)) {
            add(line.product_id?.id, (line.getQuantity?.() ?? line.qty) * childScale);
            continue;
        }
        add(line.product_id?.id, line.getQuantity?.() ?? line.qty);
    }
    for (const extra of options.extraLines || []) {
        add(extra.product_id, extra.qty);
    }
    return qtyByProduct;
}

function formatShortageBody(products) {
    return products
        .map(
            (p) =>
                _t("%(name)s: pide %(requested)s, disponible %(available)s", {
                    name: p.display_name,
                    requested: p.requested_qty,
                    available: p.available_qty,
                })
        )
        .join("\n");
}

/**
 * Ask the server if storable qtys fit free stock. On shortage show a dialog and return false.
 * If the network is down (or the RPC fails), allow the sale — the delivery already happened offline.
 *
 * @param {object} pos - PosStore
 * @param {Map<number, number>|object} qtyByProduct
 * @returns {Promise<boolean>}
 */
export async function assertPosFreeStock(pos, qtyByProduct) {
    const entries =
        qtyByProduct instanceof Map ? [...qtyByProduct.entries()] : Object.entries(qtyByProduct);
    const lines = [];
    for (const [productId, qty] of entries) {
        if (!(qty > 0)) {
            continue;
        }
        const product = pos.models["product.product"].get(Number(productId));
        if (!isProductStorable(product)) {
            continue;
        }
        lines.push({ product_id: Number(productId), qty: Number(qty) });
    }
    if (!lines.length) {
        return true;
    }
    if (pos.data?.network?.offline) {
        return true;
    }
    try {
        const result = await pos.data.call("pos.order", "order_bridge_check_pos_stock", [
            pos.config.id,
            lines,
        ]);
        if (result?.ok !== false) {
            return true;
        }
        const products = result.products || [];
        pos.dialog.add(AlertDialog, {
            title: _t("Stock insuficiente"),
            body:
                products.length > 0
                    ? formatShortageBody(products)
                    : _t("No hay suficiente cantidad libre en el almacén."),
        });
        return false;
    } catch (error) {
        if (error instanceof ConnectionLostError) {
            return true;
        }
        // Other RPC failures must not brick the cashier: same as offline.
        return true;
    }
}
