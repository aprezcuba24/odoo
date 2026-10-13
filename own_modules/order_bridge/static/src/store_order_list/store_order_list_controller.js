/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { downloadFile } from "@web/core/network/download";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { ListRenderer } from "@web/views/list/list_renderer";
import { useState, useSubEnv } from "@odoo/owl";

const MESSAGING_DOMAIN = [
    ["order_bridge_store_state", "in", ["reviewing", "negotiating"]],
];
const MAX_SELECT_LIMIT = 200;

function base64ToBlob(base64, mimetype) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    return new Blob([bytes], { type: mimetype || "application/pdf" });
}

export class StoreOrderListController extends ListController {
    static template = "order_bridge.StoreOrderListView";

    setup() {
        super.setup();
        // Force admin-create context even if /web/action/load disk-cached an old action.
        Object.assign(this.props.context, {
            default_order_bridge_origin: "admin",
            order_bridge_admin_create: true,
        });
        this.notification = useService("notification");
        this.prepareMessaging = useState({
            active: false,
            filterGroupId: null,
            filterSearchItemId: null,
            selecting: false,
            generating: false,
        });
        useSubEnv({ orderBridgePrepareMessaging: this.prepareMessaging });
    }

    async createRecord(params) {
        Object.assign(this.props.context, {
            default_order_bridge_origin: "admin",
            order_bridge_admin_create: true,
        });
        return super.createRecord(params);
    }

    async onPrepareMessaging() {
        if (this.prepareMessaging.active || this.prepareMessaging.selecting) {
            return;
        }
        const searchModel = this.env.searchModel;
        const filterGroupId = searchModel.nextGroupId;
        const filterSearchItemId = searchModel.nextId;
        searchModel.createNewFilters([
            {
                description: _t("Revisando o Negociando"),
                domain: MESSAGING_DOMAIN,
            },
        ]);
        this.prepareMessaging.filterGroupId = filterGroupId;
        this.prepareMessaging.filterSearchItemId = filterSearchItemId;
        this.prepareMessaging.active = true;
        this.prepareMessaging.selecting = true;
        try {
            await this._reloadFromSearchModel();
            await this._selectFilteredOrders();
        } finally {
            this.prepareMessaging.selecting = false;
        }
    }

    async onCancelPrepareMessaging() {
        if (!this.prepareMessaging.active) {
            return;
        }
        const groupId = this.prepareMessaging.filterGroupId;
        const searchItemId = this.prepareMessaging.filterSearchItemId;
        this.prepareMessaging.active = false;
        this.prepareMessaging.filterGroupId = null;
        this.prepareMessaging.filterSearchItemId = null;
        this._removeMessagingFilter(groupId, searchItemId);
        await this._clearSelection();
        await this._reloadFromSearchModel();
    }

    _removeMessagingFilter(groupId, searchItemId) {
        const searchModel = this.env.searchModel;
        const stillActive =
            searchItemId != null &&
            searchModel.query.some((q) => q.searchItemId === searchItemId);
        if (stillActive) {
            // toggleSearchItem removes an active filter from the query.
            searchModel.toggleSearchItem(searchItemId);
            return;
        }
        if (groupId != null) {
            searchModel.deactivateGroup(groupId);
        }
    }

    async _reloadFromSearchModel() {
        await this._waitModelIdle();
        const searchModel = this.env.searchModel;
        await this.model.load({
            domain: searchModel.domain,
            context: searchModel.context,
            groupBy: searchModel.groupBy,
            orderBy: searchModel.orderBy,
        });
    }

    async onDownloadMessagingGuide() {
        if (this.prepareMessaging.generating) {
            return;
        }
        const resIds = await this.model.root.getResIds(true);
        if (!resIds.length) {
            this.notification.add(_t("Seleccione al menos un pedido."), {
                type: "warning",
            });
            return;
        }
        this.prepareMessaging.generating = true;
        try {
            const result = await this.orm.call(
                "sale.order",
                "action_order_bridge_prepare_messaging",
                [resIds],
            );
            const mimetype = result.mimetype || "application/pdf";
            const filename = result.filename || "Guia_mensajeria.pdf";
            downloadFile(base64ToBlob(result.pdf_base64, mimetype), filename, mimetype);
            await this.onCancelPrepareMessaging();
            await this.model.load();
        } finally {
            this.prepareMessaging.generating = false;
        }
    }

    async _waitModelIdle() {
        // Let WithSearch apply the new domain and start the list reload.
        await new Promise((resolve) => setTimeout(resolve, 0));
        await this.model.mutex.getUnlockedDef();
        await new Promise((resolve) => {
            const timeout = setTimeout(resolve, 500);
            const onUpdate = () => {
                clearTimeout(timeout);
                this.model.bus.removeEventListener("update", onUpdate);
                resolve();
            };
            this.model.bus.addEventListener("update", onUpdate);
        });
        await this.model.mutex.getUnlockedDef();
    }

    async _selectFilteredOrders() {
        const root = this.model.root;
        const total = root.count || root.records.length || 0;
        const limit = Math.min(Math.max(total, 1), MAX_SELECT_LIMIT);
        if (root.offset !== 0 || root.limit < limit) {
            await root.load({ limit, offset: 0 });
        }
        for (const record of root.records) {
            if (!record.selected) {
                await record.toggleSelection(true);
            }
        }
    }

    async _clearSelection() {
        const root = this.model.root;
        if (root.isDomainSelected) {
            await root.selectDomain(false);
        }
        for (const record of root.records) {
            if (record.selected) {
                await record.toggleSelection(false);
            }
        }
    }
}

export class StoreOrderListRenderer extends ListRenderer {
    get hasSelectors() {
        if (this.env.orderBridgePrepareMessaging?.active) {
            return this.props.allowSelectors;
        }
        return this.props.allowSelectors && !this.env.isSmall;
    }
}

registry.category("views").add("order_bridge_store_order_list", {
    ...listView,
    Controller: StoreOrderListController,
    Renderer: StoreOrderListRenderer,
    buttonTemplate: "order_bridge.StoreOrderListView.Buttons",
});
