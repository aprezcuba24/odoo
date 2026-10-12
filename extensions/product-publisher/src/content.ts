/**
 * WhatsApp Web content script: sidebar + FILL_WHATSAPP_COMPOSER handler.
 * Facebook fill lives in facebook-composer.ts (not wired in this build).
 */

import { mountSidebar } from './sidebar/mount'
import {
  fillWhatsAppComposer,
  type FillWhatsAppComposerMessage,
} from './whatsapp-composer'

let booted = false

function boot(): void {
  if (booted) return
  booted = true
  mountSidebar()
  console.info('[Publicador de productos] ready')
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || typeof message !== 'object' || typeof message.type !== 'string') {
    return false
  }
  if (message.type === 'FILL_WHATSAPP_COMPOSER') {
    void fillWhatsAppComposer(message as FillWhatsAppComposerMessage).then(sendResponse)
    return true
  }
  return false
})

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot, { once: true })
} else {
  boot()
}
