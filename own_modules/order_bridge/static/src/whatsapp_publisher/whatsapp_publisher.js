/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { formatMonetary } from "@web/views/fields/formatters";
import { Component, onWillStart, useState } from "@odoo/owl";

export class WhatsappPublisherAction extends Component {
    static template = "order_bridge.WhatsappPublisherAction";
    static components = { Layout };
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            products: [],
            selectedIds: {},
            search: "",
            onlyVisibleApk: true,
            loading: true,
        });
        this.display = {
            controlPanel: {},
            searchPanel: false,
        };
        onWillStart(this.loadProducts);
    }

    async loadProducts() {
        const rows = await this.orm.call(
            "product.product",
            "get_whatsapp_publisher_products",
            [],
        );
        const selectedIds = {};
        for (const product of rows) {
            if (product.order_bridge_visible) {
                selectedIds[product.id] = true;
            }
        }
        this.state.products = rows;
        this.state.selectedIds = selectedIds;
        this.state.loading = false;
    }

    get filteredProducts() {
        const needle = (this.state.search || "").trim().toLowerCase();
        return this.state.products.filter((product) => {
            if (this.state.onlyVisibleApk && !product.order_bridge_visible) {
                return false;
            }
            if (!needle) {
                return true;
            }
            const haystack = [
                product.name,
                product.default_code || "",
                product.barcode || "",
            ]
                .join(" ")
                .toLowerCase();
            return haystack.includes(needle);
        });
    }

    get selectedCount() {
        return Object.keys(this.state.selectedIds).length;
    }

    isSelected(productId) {
        return Boolean(this.state.selectedIds[productId]);
    }

    toggleProduct(productId) {
        const next = { ...this.state.selectedIds };
        if (next[productId]) {
            delete next[productId];
        } else {
            next[productId] = true;
        }
        this.state.selectedIds = next;
    }

    onSearchInput(ev) {
        this.state.search = ev.target.value;
    }

    onOnlyVisibleApkChange(ev) {
        this.state.onlyVisibleApk = ev.target.checked;
    }

    formatPrice(product) {
        return formatMonetary(product.list_price, {
            currencyId: product.currency_id,
        });
    }

    onSendToWhatsapp() {
        const selected = this.state.products.filter((p) => this.state.selectedIds[p.id]);
        if (!selected.length) {
            this.notification.add(_t("Seleccione al menos un producto."), {
                type: "warning",
            });
            return;
        }
        const payload = selected.map((p) => ({
            id: p.id,
            name: p.name,
            default_code: p.default_code,
            list_price: p.list_price,
            free_qty: p.free_qty,
        }));
        console.log("Whatsapp publicador — productos seleccionados:", payload);
        this.notification.add(_t("Ya está listo"), {
            type: "success",
        });
    }
}

registry.category("actions").add("order_bridge_whatsapp_publisher", WhatsappPublisherAction);
