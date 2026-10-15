/** @odoo-module **/

import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import {
    PrepareMessagingMethods,
    setupPrepareMessaging,
} from "./prepare_messaging";

export class StoreOrderKanbanController extends KanbanController {
    static template = "order_bridge.StoreOrderKanbanView";

    setup() {
        super.setup();
        // Force admin-create context even if /web/action/load disk-cached an old action.
        Object.assign(this.props.context, {
            default_order_bridge_origin: "admin",
            order_bridge_admin_create: true,
        });
        setupPrepareMessaging(this);
    }

    async createRecord() {
        Object.assign(this.props.context, {
            default_order_bridge_origin: "admin",
            order_bridge_admin_create: true,
        });
        return super.createRecord();
    }
}

Object.assign(StoreOrderKanbanController.prototype, PrepareMessagingMethods);

registry.category("views").add("order_bridge_store_order_kanban", {
    ...kanbanView,
    Controller: StoreOrderKanbanController,
});
