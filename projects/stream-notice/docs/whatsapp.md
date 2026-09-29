# WhatsApp channel (neonize) — what to keep in mind

**[English](#english)** &nbsp;|&nbsp; **[Español](#español)**

---

## English

stream-notice posts the story to your WhatsApp channel **without any external API**: the program itself is linked to your number as one more device (like WhatsApp Web) using [neonize](https://github.com/krypton-byte/neonize), a Python library built on `whatsmeow` (Go) that speaks the WhatsApp Web protocol without a browser.

### How it works

- **Once:** `python -m destinations.whatsapp --login` shows a QR, you scan it from your phone (*WhatsApp → Linked devices → Link a device*) and it lists the channels you own or administer with their id.
- **On every stream:** it connects with the saved session, uploads the image to the channel, posts it with the caption from `config.json` and disconnects. It takes a few seconds and doesn't need the story on GitHub.
- **In the popup** it shows as "Canal de WhatsApp" ✓ or ✗. If it fails, Instagram and TikTok still publish.

### Configuration (`config.json` → `destinations.whatsapp`)

| Key | What it is |
|---|---|
| `enabled` | `true` / `false` to turn it on or off without touching anything else. |
| `channel_id` | Channel id, `1234567890@newsletter` (`--login` lists it). Yours: «JScorpioDv Noticias». |
| `link` | Link to the stream, replaces `{link}`. |
| `caption` | Text under the image. `{game}` becomes the game and `{link}` the link. `\n` is a line break. |

There's no token: the "key" is the session file.

### ⚠️ The session file is like your unlocked phone

`whatsapp_session.sqlite3` (in `projects/stream-notice/`) holds the keys of the linked device. **Whoever has it can send messages as you and read what reaches that device.**

- Never commit it (git already ignores it), never send it by chat or email, never upload it anywhere.
- **Don't copy it to another PC:** link each PC with its own `--login`. Two copies of the same session kick each other out.
- If you think someone got it: *WhatsApp → Linked devices* → remove the device. The file becomes useless immediately.

### Risks you accepted

- **It's an unofficial client, against WhatsApp's terms** (like Whapi was). WhatsApp can ban the number, temporarily or permanently. With one message per stream the risk is low, but not zero.
- The channel is administered by your **main number**: a ban would affect your personal WhatsApp.
- To keep the risk low: **don't use it for anything else** (no mass messages, no messages to people, no automations with other chats), and don't run tests that post in a loop.

### Maintenance

- **The session expires** if your phone is offline ~14 days or if you remove the device from the phone. The popup shows ✗ "vuelve a vincular": run `--login` again.
- **WhatsApp changes its protocol from time to time.** If it starts failing for no clear reason (✗ "no ha aceptado el aviso" or "rechazó la conexión" with the right `channel_id`), update: `pip install -U -r requirements.txt`.
- neonize is **pinned to 0.5.x** in `requirements.txt` because the destination uses an internal part of it (`_stop_finalizer`). Moving to 0.6 or later needs reviewing `destinations/whatsapp.py` and running the tests first. Don't run `pip install -U neonize` on its own.
- The line **"Press Ctrl+C to exit"** in the console comes from neonize and is harmless. It doesn't reach the log, and with autostart there's no console.

### Errors in the popup

| ✗ Message | What to do |
|---|---|
| "no está vinculado" / "ya no es válida" / "desde el móvil" | Run `python -m destinations.whatsapp --login` and scan the QR. |
| "no responde" | No internet or WhatsApp is down (waits 30 s). Nothing was posted. |
| "bloqueado temporalmente" | WhatsApp has temporarily blocked the number. Stop using it until it's lifted; don't try again and again. |
| "rechazó la conexión" | Link it again with `--login`; if it persists, update the dependencies. |
| "no ha aceptado el aviso" | Check `channel_id` and that you're the owner or an admin of the channel; then update the dependencies. |
| "channel_id debe tener la forma…" | Fix the id in `config.json` (copy it from `--login`). |

Everything is also in `logs/stream-notice.log`.

### Moving to the streaming PC

1. Install as in [`streaming-pc-setup.md`](streaming-pc-setup.md) (step 4b links WhatsApp).
2. Run `--login` **on the new PC**, don't copy the session.
3. On your phone, remove the old PC's device in *Linked devices*, and delete `whatsapp_session.sqlite3` from the old PC.

### Turning it off or removing it

- **Pause it:** `"enabled": false` in `config.json`.
- **Remove it completely:** `"enabled": false`, remove the device on your phone (*Linked devices*) and delete `whatsapp_session.sqlite3`.

### Whapi leftovers (the previous version)

Whapi is no longer used. If you haven't yet: revoke the token and delete the channel in the Whapi panel, and remove its device from *Linked devices* (**keep** the neonize one).

---

## Español

stream-notice publica la historia en tu canal de WhatsApp **sin ninguna API externa**: el propio programa se vincula a tu número como un dispositivo más (como WhatsApp Web) con [neonize](https://github.com/krypton-byte/neonize), una librería de Python basada en `whatsmeow` (Go) que habla el protocolo de WhatsApp Web sin navegador.

### Cómo funciona

- **Una vez:** `python -m destinations.whatsapp --login` enseña un QR, lo escaneas desde el móvil (*WhatsApp → Dispositivos vinculados → Vincular un dispositivo*) y lista los canales de los que eres propietario o administrador, con su id.
- **En cada directo:** conecta con la sesión guardada, sube la imagen al canal, la publica con el texto de `config.json` y se desconecta. Tarda unos segundos y no necesita la historia en GitHub.
- **En el popup** sale como «Canal de WhatsApp» ✓ o ✗. Si falla, Instagram y TikTok publican igual.

### Configuración (`config.json` → `destinations.whatsapp`)

| Clave | Qué es |
|---|---|
| `enabled` | `true` / `false` para activarlo o pausarlo sin tocar nada más. |
| `channel_id` | Id del canal, `1234567890@newsletter` (lo lista `--login`). El tuyo: «JScorpioDv Noticias». |
| `link` | Enlace al directo; sustituye a `{link}`. |
| `caption` | Texto bajo la imagen. `{game}` se cambia por el juego y `{link}` por el enlace. `\n` es un salto de línea. |

No hay token: la «llave» es el archivo de sesión.

### ⚠️ El archivo de sesión es como tu móvil desbloqueado

`whatsapp_session.sqlite3` (en `projects/stream-notice/`) guarda las claves del dispositivo vinculado. **Quien lo tenga puede enviar mensajes en tu nombre y leer lo que llegue a ese dispositivo.**

- Nunca lo subas a git (ya lo ignora), ni lo mandes por chat o correo, ni lo subas a ningún sitio.
- **No lo copies a otro PC:** vincula cada PC con su propio `--login`. Dos copias de la misma sesión se echan la una a la otra.
- Si crees que alguien lo ha conseguido: *WhatsApp → Dispositivos vinculados* → cierra ese dispositivo. El archivo deja de servir al momento.

### Riesgos que aceptaste

- **Es un cliente no oficial y va contra las condiciones de WhatsApp** (igual que Whapi). WhatsApp puede bloquear el número, de forma temporal o permanente. Con un mensaje por directo el riesgo es bajo, pero no nulo.
- El canal lo administra tu **número principal**: un bloqueo afectaría a tu WhatsApp personal.
- Para mantener el riesgo bajo: **no lo uses para nada más** (ni envíos masivos, ni mensajes a personas, ni automatizaciones con otros chats), y no hagas pruebas que publiquen en bucle.

### Mantenimiento

- **La sesión caduca** si el móvil pasa ~14 días sin conexión o si quitas el dispositivo desde el móvil. El popup marca ✗ «vuelve a vincular»: ejecuta otra vez `--login`.
- **WhatsApp cambia su protocolo de vez en cuando.** Si empieza a fallar sin motivo claro (✗ «no ha aceptado el aviso» o «rechazó la conexión» con el `channel_id` bien puesto), actualiza: `pip install -U -r requirements.txt`.
- neonize va **fijado a 0.5.x** en `requirements.txt` porque el destino usa una parte interna suya (`_stop_finalizer`). Pasar a 0.6 o posterior exige revisar antes `destinations/whatsapp.py` y pasar las pruebas. No ejecutes `pip install -U neonize` suelto.
- La línea **«Press Ctrl+C to exit»** en la consola es de neonize y no significa nada. No llega al registro, y con el arranque automático no hay consola.

### Errores en el popup

| ✗ Mensaje | Qué hacer |
|---|---|
| «no está vinculado» / «ya no es válida» / «desde el móvil» | Ejecuta `python -m destinations.whatsapp --login` y escanea el QR. |
| «no responde» | Sin internet o WhatsApp caído (espera 30 s). No se ha publicado nada. |
| «bloqueado temporalmente» | WhatsApp ha bloqueado el número por un tiempo. Deja de usarlo hasta que se levante; no reintentes una y otra vez. |
| «rechazó la conexión» | Vuelve a vincular con `--login`; si sigue, actualiza las dependencias. |
| «no ha aceptado el aviso» | Revisa `channel_id` y que eres propietario o administrador del canal; después, actualiza las dependencias. |
| «channel_id debe tener la forma…» | Corrige el id en `config.json` (cópialo de `--login`). |

Todo queda también en `logs/stream-notice.log`.

### Al pasar al PC de directos

1. Instala como dice [`streaming-pc-setup.md`](streaming-pc-setup.md) (el paso 4b vincula WhatsApp).
2. Ejecuta `--login` **en el PC nuevo**; no copies la sesión.
3. En el móvil, quita el dispositivo del PC anterior en *Dispositivos vinculados*, y borra `whatsapp_session.sqlite3` del PC anterior.

### Pausarlo o quitarlo

- **Pausarlo:** `"enabled": false` en `config.json`.
- **Quitarlo del todo:** `"enabled": false`, cierra el dispositivo en el móvil (*Dispositivos vinculados*) y borra `whatsapp_session.sqlite3`.

### Restos de Whapi (la versión anterior)

Whapi ya no se usa. Si no lo has hecho aún: revoca el token y borra el canal en el panel de Whapi, y quita su dispositivo de *Dispositivos vinculados* (**deja** el de neonize).
