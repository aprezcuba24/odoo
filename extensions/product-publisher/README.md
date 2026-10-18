# Publicador de productos

Extensión Chrome/Chromium (Manifest V3) que recibe productos desde Odoo y los prepara en WhatsApp Web (nombre, precio e imagen). El nombre es genérico: el código de Facebook está en el repo pero no está activo.

## Requisitos

- Node.js 20+
- Chrome o Chromium
- Odoo accesible en el origen configurado (`VITE_ODOO_ORIGIN`)

## Build

```bash
cd extensions/product-publisher
cp .env.example .env   # ajusta VITE_ODOO_ORIGIN si hace falta
npm install
npm run build
```

Salida: `dist/` (incluye `manifest.json`, `content.js`, `background.js`, `odoo-bridge.js`, `popup.html` e `icons/`).

## Instalar en Chrome (Load unpacked)

1. `npm run build`
2. Abre `chrome://extensions`
3. Activa **Developer mode**
4. **Load unpacked** → selecciona `extensions/product-publisher/dist`
5. En Odoo: **Tienda Apk → Operaciones → Whatsapp** → selecciona productos → **Mandar a WhatsApp** (si hay mensajes en **Configuración → WhatsApp Mensajes**, elige cuáles incluir)
6. Abre WhatsApp Web, entra a un chat o grupo y pulsa **Publicar** (uno a uno) o **Automático** (envía toda la cola con pausas)

Si cambias el origen de Odoo, actualiza `.env`, vuelve a compilar y recarga la extensión.
