import { useCallback, useEffect, useState } from 'react'
import { sendMessage } from '../messaging'
import { PUBLISH_QUEUE_STORAGE_KEY } from '../constants'
import { parsePublishQueue, readPublishQueue, type QueueItem } from '../publish-queue'
import { ProductThumb } from './ProductThumb'

export function Queue() {
  const [items, setItems] = useState<QueueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [fillingId, setFillingId] = useState<string | null>(null)
  const [readyIds, setReadyIds] = useState<string[]>([])

  const applyQueue = useCallback(
    (queue: { items: QueueItem[]; readyIds: string[] } | null) => {
      setItems(queue?.items ?? [])
      setReadyIds(queue?.readyIds ?? [])
    },
    [],
  )

  const loadQueue = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      applyQueue(await readPublishQueue())
    } finally {
      setLoading(false)
    }
  }, [applyQueue])

  useEffect(() => {
    void loadQueue()
  }, [loadQueue])

  useEffect(() => {
    function onStorageChanged(
      changes: Record<string, chrome.storage.StorageChange>,
      areaName: string,
    ) {
      if (areaName !== 'local' || !(PUBLISH_QUEUE_STORAGE_KEY in changes)) return
      const next = parsePublishQueue(changes[PUBLISH_QUEUE_STORAGE_KEY]?.newValue)
      applyQueue(next)
      setLoading(false)
      setError(null)
      setStatus(null)
    }

    chrome.storage.onChanged.addListener(onStorageChanged)
    return () => chrome.storage.onChanged.removeListener(onStorageChanged)
  }, [applyQueue])

  async function publishItem(itemId: string) {
    setError(null)
    setStatus(null)
    setFillingId(itemId)
    try {
      const result = await sendMessage({
        type: 'FILL_WHATSAPP_ITEM',
        itemId,
      })
      if (!result.ok) {
        setError(result.error)
        return
      }
      // readyIds come from chrome.storage via onChanged / markItemReady in background
      setReadyIds((prev) => (prev.includes(itemId) ? prev : [...prev, itemId]))
      setStatus('Listo. Revisa y pulsa Enviar en WhatsApp.')
    } finally {
      setFillingId(null)
    }
  }

  async function resetPublishButtons() {
    setFillingId(null)
    setError(null)
    setStatus(null)
    const result = await sendMessage({ type: 'CLEAR_READY_IDS' })
    if (!result.ok) {
      setError(result.error)
      return
    }
    setReadyIds([])
  }

  async function clearQueue() {
    setError(null)
    const result = await sendMessage({ type: 'CLEAR_PUBLISH_QUEUE' })
    if (!result.ok) {
      setError(result.error)
      return
    }
    setItems([])
    setReadyIds([])
    setFillingId(null)
    setStatus(null)
  }

  return (
    <>
      <div className="selected-row">
        <p className="section-title">Cola de publicación</p>
        <div className="selected-actions">
          {readyIds.length > 0 ? (
            <button
              type="button"
              className="btn-text"
              onClick={() => void resetPublishButtons()}
            >
              Reset
            </button>
          ) : null}
          {items.length > 0 ? (
            <button type="button" className="btn-text" onClick={() => void clearQueue()}>
              Vaciar
            </button>
          ) : null}
        </div>
      </div>

      <p className="muted publish-hint">
        Abre el chat o grupo y pulsa Publicar para pegar el contenido.
      </p>

      {error ? <p className="error">{error}</p> : null}
      {status ? <p className="success">{status}</p> : null}

      {loading && items.length === 0 ? (
        <div className="empty">Cargando cola…</div>
      ) : items.length === 0 ? (
        <div className="empty">
          No hay productos. En Odoo elige productos y pulsa Mandar a WhatsApp.
        </div>
      ) : (
        <ul className="queue-list">
          {items.map((item) => {
            const ready = readyIds.includes(item.id)
            const filling = fillingId === item.id

            if (item.type === 'block') {
              return (
                <li key={item.id} className="queue-item queue-item--block">
                  <div className="queue-item-main">
                    <div className="block-thumb" aria-hidden>
                      <span className="block-thumb-icon">#</span>
                    </div>
                    <div className="queue-item-info">
                      <p className="block-label">{item.label ? item.label : item.text}</p>
                      {item.label ? <p className="product-code">{item.text}</p> : null}
                      {ready ? <span className="queue-ready">Listo</span> : null}
                    </div>
                  </div>
                  {!ready ? (
                    <button
                      type="button"
                      className="btn-publish-item"
                      disabled={fillingId !== null}
                      onClick={() => void publishItem(item.id)}
                    >
                      {filling ? 'Abriendo…' : 'Publicar'}
                    </button>
                  ) : null}
                </li>
              )
            }

            // type === 'product'
            return (
              <li key={item.id} className="queue-item">
                <div className="queue-item-main">
                  <ProductThumb
                    imageBase64={item.imageBase64}
                    imageMime={item.imageMime}
                  />
                  <div className="queue-item-info">
                    <p className="product-name">{item.name}</p>
                    <p className="product-code">{item.price}</p>
                    {ready ? <span className="queue-ready">Listo</span> : null}
                  </div>
                </div>
                {!ready ? (
                  <button
                    type="button"
                    className="btn-publish-item"
                    disabled={fillingId !== null}
                    onClick={() => void publishItem(item.id)}
                  >
                    {filling ? 'Abriendo…' : 'Publicar'}
                  </button>
                ) : null}
              </li>
            )
          })}
        </ul>
      )}
    </>
  )
}
