/** @odoo-module **/

import { Dialog } from "@web/core/dialog/dialog";
import { Component, useState } from "@odoo/owl";

/**
 * Let the user uncheck generic WhatsApp messages before publishing.
 * All messages start selected; cancel returns null via ``onCancel``.
 */
export class WhatsappMessagesDialog extends Component {
    static template = "order_bridge.WhatsappMessagesDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        messages: Array,
        confirm: { type: Function, optional: true },
        cancel: { type: Function, optional: true },
    };

    setup() {
        const selectedIds = {};
        for (const msg of this.props.messages) {
            selectedIds[msg.id] = true;
        }
        this.state = useState({ selectedIds });
    }

    get startMessages() {
        return this.props.messages.filter((m) => m.position === "start");
    }

    get endMessages() {
        return this.props.messages.filter((m) => m.position === "end");
    }

    isSelected(id) {
        return Boolean(this.state.selectedIds[id]);
    }

    toggle(id) {
        const next = { ...this.state.selectedIds };
        if (next[id]) {
            delete next[id];
        } else {
            next[id] = true;
        }
        this.state.selectedIds = next;
    }

    messagePreview(msg) {
        const text = (msg.text || "").trim();
        if (text.length <= 80) {
            return text;
        }
        return `${text.slice(0, 80)}…`;
    }

    onConfirm() {
        const selectedIds = Object.keys(this.state.selectedIds).map((id) => Number(id));
        this.props.confirm?.(selectedIds);
        this.props.close();
    }

    onCancel() {
        this.props.cancel?.();
        this.props.close();
    }
}
