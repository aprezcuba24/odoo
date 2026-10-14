/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { downloadFile } from "@web/core/network/download";
import { useService } from "@web/core/utils/hooks";
import { useState, useSubEnv } from "@odoo/owl";

export const MESSAGING_DOMAIN = [
    ["order_bridge_store_state", "=", "ready_for_delivery"],
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

/**
 * Shared prepare-messaging state and handlers for list and kanban store order views.
 * Call from Controller.setup() after super.setup().
 */
export function setupPrepareMessaging(component) {
    component.notification = useService("notification");
    component.orm = useService("orm");
    component.prepareMessaging = useState({
        active: false,
        filterGroupId: null,
        filterSearchItemId: null,
        selecting: false,
        generating: false,
    });
    useSubEnv({ orderBridgePrepareMessaging: component.prepareMessaging });
}

export const PrepareMessagingMethods = {
    async onPrepareMessaging() {
        if (this.prepareMessaging.active || this.prepareMessaging.selecting) {
            return;
        }
        const searchModel = this.env.searchModel;
        const filterGroupId = searchModel.nextGroupId;
        const filterSearchItemId = searchModel.nextId;
        searchModel.createNewFilters([
            {
                description: _t("Listo para entrega"),
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
    },

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
    },

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
    },

    async _reloadFromSearchModel() {
        await this._waitModelIdle();
        const searchModel = this.env.searchModel;
        await this.model.load({
            domain: searchModel.domain,
            context: searchModel.context,
            groupBy: searchModel.groupBy,
            orderBy: searchModel.orderBy,
        });
    },

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
    },

    async _waitModelIdle() {
        // Let WithSearch apply the new domain and start the view reload.
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
    },

    async _selectFilteredOrders() {
        const root = this.model.root;
        if (root.isGrouped) {
            const total = root.recordCount || root.count || 0;
            if (!total) {
                return;
            }
            // Domain selection covers all matches across kanban columns.
            await root.selectDomain(true);
            return;
        }
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
    },

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
    },
};
