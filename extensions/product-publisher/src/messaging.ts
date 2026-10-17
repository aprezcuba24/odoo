export type ExtensionMessage =
  | {
      type: 'START_PUBLISH'
      items: unknown
    }
  | { type: 'CLEAR_PUBLISH_QUEUE' }
  | { type: 'CLEAR_READY_IDS' }
  | { type: 'FILL_WHATSAPP_ITEM'; itemId: string }

export type ExtensionResponse =
  | { ok: true; filled?: boolean; imageAttached?: boolean }
  | { ok: false; error: string }

export function sendMessage(message: ExtensionMessage): Promise<ExtensionResponse> {
  return chrome.runtime.sendMessage(message) as Promise<ExtensionResponse>
}
