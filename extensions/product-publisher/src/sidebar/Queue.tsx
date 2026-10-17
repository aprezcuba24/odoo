import { useCallback, useEffect, useRef, useState } from 'react'
import { sendMessage } from '../messaging'
import { PUBLISH_QUEUE_STORAGE_KEY } from '../constants'
import { parsePublishQueue, readPublishQueue, type QueueItem } from '../publish-queue'
import {
  AFTER_IMAGE_MS,
  AFTER_TEXT_MS,
  BATCH_EVERY,
  BATCH_EXTRA_MS,
  interruptibleSleep,
  paceMs,
} from '../whatsapp-pacing'
import { ProductThumb } from './ProductThumb'

function itemHasImage(item: QueueItem): boolean {
  return item.type === 'product' && Boolean(item.imageBase64 && item.imageMime)
}

export function Queue() {
  const [items, setItems] = useState<QueueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [fillingId, setFillingId] = useState<string | null>(null)
  const [readyIds, setReadyIds] = useState<string[]>([])
  const [autoRunning, setAutoRunning] = useState(false)
  const stopRequestedRef = useRef(false)
  const autoRunningRef = useRef(false)

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
      // Keep auto-run progress messages while the batch is running.
      if (!autoRunningRef.current) {
        setStatus(null)
      }
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

  async function runAutomatic() {
    if (autoRunningRef.current) return

    const pending = items.filter((item) => !readyIds.includes(item.id))
    if (pending.length === 0) return

    stopRequestedRef.current = false
    autoRunningRef.current = true
    setAutoRunning(true)
    setError(null)
    setStatus(null)

    let sentCount = 0
    let stoppedByUser = false

    try {
      for (let i = 0; i < pending.length; i++) {
        if (stopRequestedRef.current) {
          stoppedByUser = true
          break
        }

        const item = pending[i]
        if (!item) break
        const step = i + 1
        setFillingId(item.id)
        setStatus(`Enviando ${step} de ${pending.length}…`)

        const result = await sendMessage({
          type: 'PUBLISH_WHATSAPP_ITEM',
          itemId: item.id,
        })

        if (!result.ok) {
          setError(result.error)
          break
        }

        sentCount += 1
        setReadyIds((prev) => (prev.includes(item.id) ? prev : [...prev, item.id]))

        const isLast = i === pending.length - 1
        if (isLast || stopRequestedRef.current) {
          if (stopRequestedRef.current) stoppedByUser = true
          break
        }

        let waitMs = paceMs(itemHasImage(item) ? AFTER_IMAGE_MS : AFTER_TEXT_MS)
        if (sentCount % BATCH_EVERY === 0) {
          waitMs += paceMs(BATCH_EXTRA_MS)
          setStatus(
            `Enviado ${step} de ${pending.length}. Pausa larga para no saturar WhatsApp…`,
          )
        } else {
          setStatus(
            `Enviado ${step} de ${pending.length}. Esperando para no saturar WhatsApp…`,
          )
        }

        const continued = await interruptibleSleep(waitMs, () => stopRequestedRef.current)
        if (!continued) {
          stoppedByUser = true
          break
        }
      }

      if (stoppedByUser) {
        setStatus(
          sentCount > 0
            ? `Detenido. Se enviaron ${sentCount} mensaje${sentCount === 1 ? '' : 's'}.`
            : 'Detenido. No se envió ningún mensaje.',
        )
      } else if (sentCount === pending.length) {
        setStatus(
          `Listo. Se enviaron ${sentCount} mensaje${sentCount === 1 ? '' : 's'}.`,
        )
      } else if (sentCount > 0) {
        setStatus(
          `Se enviaron ${sentCount} de ${pending.length}. Revisa el error y reanuda con Automático.`,
        )
      }
    } finally {
      setFillingId(null)
      autoRunningRef.current = false
      setAutoRunning(false)
      stopRequestedRef.current = false
    }
  }

  function stopAutomatic() {
    stopRequestedRef.current = true
    setStatus('Deteniendo tras el mensaje en curso…')
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

  const pendingCount = items.filter((item) => !readyIds.includes(item.id)).length
  const busy = fillingId !== null || autoRunning

  return (
    <>
      <div className="selected-row">
        <p className="section-title">Cola de publicación</p>
        <div className="selected-actions">
          {pendingCount > 0 || autoRunning ? (
            <button
              type="button"
              className={autoRunning ? 'btn-text' : 'btn-auto'}
              disabled={false}
              onClick={() => {
                if (autoRunning) {
                  stopAutomatic()
                } else {
                  void runAutomatic()
                }
              }}
            >
              {autoRunning ? 'Detener' : 'Automático'}
            </button>
          ) : null}
          {readyIds.length > 0 ? (
            <button
              type="button"
              className="btn-text"
              disabled={autoRunning}
              onClick={() => void resetPublishButtons()}
            >
              Reset
            </button>
          ) : null}
          {items.length > 0 ? (
            <button
              type="button"
              className="btn-text"
              disabled={autoRunning}
              onClick={() => void clearQueue()}
            >
              Vaciar
            </button>
          ) : null}
        </div>
      </div>

      <p className="muted publish-hint">
        Abre el chat o grupo. Usa Publicar para pegar uno a uno, o Automático para enviar
        toda la cola con pausas.
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
                      disabled={busy}
                      onClick={() => void publishItem(item.id)}
                    >
                      {filling && !autoRunning ? 'Abriendo…' : 'Publicar'}
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
                    disabled={busy}
                    onClick={() => void publishItem(item.id)}
                  >
                    {filling && !autoRunning ? 'Abriendo…' : 'Publicar'}
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
