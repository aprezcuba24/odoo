/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { ListRenderer } from "@web/views/list/list_renderer";
import {
    PrepareMessagingMethods,
    setupPrepareMessaging,
} from "./prepare_messaging";

export class StoreOrderListController extends ListController {
    static template = "order_bridge.StoreOrderListView";

    setup() {
        super.setup();
        // Force admin-create context even if /web/action/load disk-cached an old action.
        Object.assign(this.props.context, {
            default_order_bridge_origin: "admin",
            order_bridge_admin_create: true,
        });
        setupPrepareMessaging(this);
    }

    async createRecord(params) {
        Object.assign(this.props.context, {
            default_order_bridge_origin: "admin",
            order_bridge_admin_create: true,
        });
        return super.createRecord(params);
    }
}

Object.assign(StoreOrderListController.prototype, PrepareMessagingMethods);

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
