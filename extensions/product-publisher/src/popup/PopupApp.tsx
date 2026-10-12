import AppIcon from '../icon'

export function PopupApp() {
  return (
    <div className="popup">
      <div className="popup-brand">
        <AppIcon size={36} alt="Publicador" />
        <div>
          <h1>Publicador de productos</h1>
          <p className="muted">WhatsApp Web</p>
        </div>
      </div>
      <ol className="steps">
        <li>Abre Odoo e inicia sesión.</li>
        <li>
          Ve a <strong>Ventas → Tienda Apk → Whatsapp publicador</strong>.
        </li>
        <li>Elige productos y pulsa <strong>Mandar a WhatsApp</strong>.</li>
        <li>
          Abre <strong>web.whatsapp.com</strong>, entra a un chat o grupo y
          publica desde el panel.
        </li>
      </ol>
      <p className="muted tip">
        Si Odoo no responde, recarga la extensión en chrome://extensions y vuelve
        a intentarlo.
      </p>
    </div>
  )
}
