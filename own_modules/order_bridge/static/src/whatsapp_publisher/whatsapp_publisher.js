/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { formatMonetary } from "@web/views/fields/formatters";
import { Component, onWillStart, useState } from "@odoo/owl";

import { WhatsappMessagesDialog } from "./whatsapp_messages_dialog";

const MESSAGE_SOURCE = "odoo-product-publisher";
const RESPONSE_TIMEOUT_MS = 500;

/**
 * Format a category name for WhatsApp:
 *   🏷️ *NOMBRE EN MAYÚSCULAS* 🏷️
 */
function formatCategoryText(name) {
    const upper = (name || "").trim().toUpperCase();
    return `🏷️ *${upper}* 🏷️`;
}

/**
 * Download a same-origin product image and return base64 + mime for the extension.
 */
async function fetchImagePayload(imageUrl) {
    if (!imageUrl) {
        return { imageBase64: null, imageMime: null };
    }
    const path = imageUrl.replace("/image_128", "/image_512");
    const absolute = path.startsWith("http")
        ? path
        : `${window.location.origin}${path}`;
    try {
        const response = await fetch(absolute, { credentials: "same-origin" });
        if (!response.ok) {
            return { imageBase64: null, imageMime: null };
        }
        const blob = await response.blob();
        const mime = blob.type || "image/jpeg";
        const buffer = await blob.arrayBuffer();
        const bytes = new Uint8Array(buffer);
        let binary = "";
        for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return { imageBase64: btoa(binary), imageMime: mime };
    } catch {
        return { imageBase64: null, imageMime: null };
    }
}

/**
 * Ask the Chrome extension to store the publish queue.
 * @param {Array} items  Ordered list of product and block items ready to publish.
 */
function startProductPublish(items) {
    const message = {
        source: MESSAGE_SOURCE,
        type: "START_PUBLISH",
        items,
    };

    return new Promise((resolve) => {
        let timeout = null;
        let resolved = false;

        const handleResponse = (event) => {
            if (event.origin !== window.location.origin) {
                return;
            }
            const response = event.data;
            if (
                !response ||
                typeof response !== "object" ||
                response.source !== MESSAGE_SOURCE ||
                response.type !== "START_PUBLISH_RESPONSE"
            ) {
                return;
            }
            if (timeout) {
                clearTimeout(timeout);
                timeout = null;
            }
            window.removeEventListener("message", handleResponse);
            if (resolved) {
                return;
            }
            resolved = true;
            if (response.ok) {
                resolve({ ok: true });
            } else {
                resolve({
                    ok: false,
                    error:
                        typeof response.error === "string"
                            ? response.error
                            : _t("La extensión no pudo iniciar la publicación."),
                });
            }
        };

        window.addEventListener("message", handleResponse);
        window.postMessage(message, window.location.origin);

        timeout = setTimeout(() => {
            window.removeEventListener("message", handleResponse);
            if (resolved) {
                return;
            }
            resolved = true;
            resolve({
                ok: false,
                error: _t(
                    "La extensión no respondió. Verifica que esté instalada y recargada.",
                ),
            });
        }, RESPONSE_TIMEOUT_MS);
    });
}

/**
 * Convert a configured generic message into a queue block item.
 */
function messageToBlockItem(msg) {
    return {
        type: "block",
        id: `block-msg-${msg.id}`,
        label: msg.name || "",
        kind: "text",
        text: msg.text || "",
    };
}

export class WhatsappPublisherAction extends Component {
    static template = "order_bridge.WhatsappPublisherAction";
    static components = { Layout };
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.state = useState({
            products: [],
            selectedIds: {},
            search: "",
            onlyVisibleApk: true,
            loading: true,
            sending: false,
            cupCurrencyId: null,
        });
        this.display = {
            controlPanel: {},
            searchPanel: false,
        };
        onWillStart(this.loadProducts);
    }

    async loadProducts() {
        const [rows, cupCurrencies] = await Promise.all([
            this.orm.call("product.product", "get_whatsapp_publisher_products", []),
            this.orm.searchRead("res.currency", [["name", "=", "CUP"]], ["id"], {
                limit: 1,
            }),
        ]);
        const selectedIds = {};
        for (const product of rows) {
            if (product.order_bridge_visible) {
                selectedIds[product.id] = true;
            }
        }
        this.state.products = rows;
        this.state.selectedIds = selectedIds;
        this.state.cupCurrencyId = cupCurrencies[0]?.id || null;
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
        if (this.state.cupCurrencyId) {
            return formatMonetary(product.list_price, {
                currencyId: this.state.cupCurrencyId,
            });
        }
        const amount = formatMonetary(product.list_price, {
            currencyId: product.currency_id,
        });
        return amount.includes("CUP") ? amount : `${amount} CUP`;
    }

    formatProductLabel(product) {
        const name = (product.name || "").trim();
        const uom = (product.uom_name || "").trim();
        return uom ? `${name} (${uom})` : name;
    }

    /**
     * Ask which configured messages to include; returns selected ids or null if cancelled.
     * Skips the dialog when there are no messages.
     */
    pickMessagesToPublish(messages) {
        if (!messages.length) {
            return Promise.resolve([]);
        }
        return new Promise((resolve) => {
            let settled = false;
            const settle = (value) => {
                if (settled) {
                    return;
                }
                settled = true;
                resolve(value);
            };
            this.dialog.add(
                WhatsappMessagesDialog,
                {
                    messages,
                    confirm: (selectedIds) => settle(selectedIds),
                    cancel: () => settle(null),
                },
                {
                    onClose: () => settle(null),
                },
            );
        });
    }

    async buildCatalogItems(selected) {
        const items = [];
        let lastCategId = null;
        for (const product of selected) {
            const categId = product.category_id || null;
            if (categId !== lastCategId) {
                lastCategId = categId;
                if (product.category_name) {
                    items.push({
                        type: "block",
                        id: `block-categ-${categId}`,
                        kind: "text",
                        text: formatCategoryText(product.category_name),
                    });
                }
            }
            const image = await fetchImagePayload(product.image_url);
            items.push({
                type: "product",
                id: String(product.id),
                name: this.formatProductLabel(product),
                price: this.formatPrice(product),
                imageBase64: image.imageBase64,
                imageMime: image.imageMime,
            });
        }
        return items;
    }

    async onSendToWhatsapp() {
        if (this.state.sending) {
            return;
        }
        const selected = this.state.products.filter((p) => this.state.selectedIds[p.id]);
        if (!selected.length) {
            this.notification.add(_t("Seleccione al menos un producto."), {
                type: "warning",
            });
            return;
        }

        this.state.sending = true;
        try {
            const messages = await this.orm.call(
                "order_bridge.whatsapp.message",
                "get_whatsapp_publisher_messages",
                [],
            );
            const selectedMessageIds = await this.pickMessagesToPublish(messages);
            if (selectedMessageIds === null) {
                return;
            }

            const selectedSet = new Set(selectedMessageIds);
            const startBlocks = messages
                .filter((m) => m.position === "start" && selectedSet.has(m.id))
                .map(messageToBlockItem);
            const endBlocks = messages
                .filter((m) => m.position === "end" && selectedSet.has(m.id))
                .map(messageToBlockItem);

            const catalogItems = await this.buildCatalogItems(selected);
            const items = [...startBlocks, ...catalogItems, ...endBlocks];

            console.log("Whatsapp publicador — cola de items:", items);

            const result = await startProductPublish(items);
            if (!result.ok) {
                this.notification.add(result.error, { type: "danger" });
                return;
            }
            this.notification.add(
                _t("Cola lista. Abre WhatsApp Web y publica desde el panel."),
                { type: "success" },
            );
        } finally {
            this.state.sending = false;
        }
    }
}

registry.category("actions").add("order_bridge_whatsapp_publisher", WhatsappPublisherAction);
