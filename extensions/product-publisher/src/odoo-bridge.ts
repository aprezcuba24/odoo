/**
 * Content script on the Odoo origin.
 * Forwards START_PUBLISH from the page to the extension background and posts
 * START_PUBLISH_RESPONSE back to the page.
 */

import { MESSAGE_SOURCE } from './constants'

const START_PUBLISH_REQUEST = 'START_PUBLISH'
const START_PUBLISH_RESPONSE = 'START_PUBLISH_RESPONSE'

interface PublishMessage {
  source: typeof MESSAGE_SOURCE
  type: typeof START_PUBLISH_REQUEST
  items: unknown
}

interface PublishResponse {
  source: typeof MESSAGE_SOURCE
  type: typeof START_PUBLISH_RESPONSE
  ok: boolean
  error?: string
}

function isPublishMessage(data: unknown): data is PublishMessage {
  if (!data || typeof data !== 'object') return false
  const candidate = data as Partial<PublishMessage>
  return candidate.source === MESSAGE_SOURCE && candidate.type === START_PUBLISH_REQUEST
}

window.addEventListener('message', (event) => {
  if (event.origin !== window.location.origin) return
  if (!isPublishMessage(event.data)) return

  chrome.runtime.sendMessage(
    {
      type: START_PUBLISH_REQUEST,
      items: event.data.items,
    },
    (response) => {
      const bridgeResponse: PublishResponse = {
        source: MESSAGE_SOURCE,
        type: START_PUBLISH_RESPONSE,
        ok: response?.ok ?? false,
        error: response?.error,
      }
      window.postMessage(bridgeResponse, window.location.origin)
    },
  )
})
