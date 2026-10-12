import { useCallback, useEffect, useState } from 'react'
import { sendMessage } from '../messaging'
import { PUBLISH_QUEUE_STORAGE_KEY } from '../constants'
import {
  parsePublishQueue,
  readPublishQueue,
  type PublishQueueProduct,
} from '../publish-queue'
import { ProductThumb } from './ProductThumb'

export function Queue() {
  const [products, setProducts] = useState<PublishQueueProduct[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [fillingId, setFillingId] = useState<string | null>(null)
  const [readyIds, setReadyIds] = useState<string[]>([])

  const applyQueue = useCallback(
    (queue: { products: PublishQueueProduct[]; readyIds: string[] } | null) => {
      setProducts(queue?.products ?? [])
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

  async function publishProduct(productId: string) {
    setError(null)
    setStatus(null)
    setFillingId(productId)
    try {
      const result = await sendMessage({
        type: 'FILL_WHATSAPP_PRODUCT',
        productId,
      })
      if (!result.ok) {
        setError(result.error)
        return
      }
      // readyIds come from chrome.storage via onChanged / markProductReady in background
      setReadyIds((prev) => (prev.includes(productId) ? prev : [...prev, productId]))
      setStatus('Imagen y texto listos. Revisa y pulsa Enviar.')
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
    setProducts([])
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
          {products.length > 0 ? (
            <button type="button" className="btn-text" onClick={() => void clearQueue()}>
              Vaciar
            </button>
          ) : null}
        </div>
      </div>

      <p className="muted publish-hint">
        Abre el chat o grupo y pulsa Publicar para pegar imagen, nombre y precio.
      </p>

      {error ? <p className="error">{error}</p> : null}
      {status ? <p className="success">{status}</p> : null}

      {loading && products.length === 0 ? (
        <div className="empty">Cargando cola…</div>
      ) : products.length === 0 ? (
        <div className="empty">
          No hay productos. En Odoo elige productos y pulsa Mandar a WhatsApp.
        </div>
      ) : (
        <ul className="queue-list">
          {products.map((product) => {
            const ready = readyIds.includes(product.id)
            const filling = fillingId === product.id
            return (
              <li key={product.id} className="queue-item">
                <div className="queue-item-main">
                  <ProductThumb
                    imageBase64={product.imageBase64}
                    imageMime={product.imageMime}
                  />
                  <div className="queue-item-info">
                    <p className="product-name">{product.name}</p>
                    <p className="product-code">{product.price}</p>
                    {ready ? <span className="queue-ready">Listo</span> : null}
                  </div>
                </div>
                {!ready ? (
                  <button
                    type="button"
                    className="btn-publish-item"
                    disabled={fillingId !== null}
                    onClick={() => void publishProduct(product.id)}
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
