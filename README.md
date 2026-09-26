# stream-notice

**[English](#english)** &nbsp;|&nbsp; **[Español](#español)**

---

## English

> **Status: phases 1 and 2 working.** Verified with a real OBS stream start, real Twitch/IGDB data, a real Instagram Story and a real TikTok draft. The WhatsApp channel destination is covered by tests against a simulated Whapi API and is pending its first real post.

When you press "Start Streaming" in OBS Studio, a popup asks whether to send notices. If you accept, it builds a story image (1080×1920) with the game from your current Twitch category placed inside the TV screen of the `story-notice.png` template, and **publishes it as an Instagram Story**, **sends it to your TikTok inbox as a draft** and **posts it to your WhatsApp channel** with the stream link (plus opening it on the PC).

Runs as an external program connected to OBS over WebSocket (OBS 28+), never as an OBS script — a blocking dialog would freeze OBS. Lightweight enough for a modest streaming PC.

### Getting started

Requirements: Windows, **Python 3.10+** ([python.org](https://www.python.org/downloads/), tick "Add python.exe to PATH") and **OBS Studio 28+**.

**1. Get the code and install dependencies** (once)

```bat
git clone https://github.com/jsierram-dev/jp-auto.git
cd jp-auto\projects\stream-notice
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**2. Get the credentials** (once)

- **OBS WebSocket password**: OBS → Tools → WebSocket Server Settings → tick *Enable WebSocket server*, keep port 4455, then *Show Connect Info* to copy the password.
- **Twitch Client ID / Secret**: [dev.twitch.tv/console](https://dev.twitch.tv/console) → *Register Your Application* (OAuth redirect URL `http://localhost`, category *Application Integration*, client type *Confidential*) → *Manage* → copy the Client ID and generate a *New Secret* (shown only once). Twitch requires **two-factor authentication** enabled on your account to register apps. The same credentials work for IGDB.

**3. Create `config.json`** (once)

```bat
copy config.example.json config.json
```

Fill in `obs.password`, `twitch.client_id` and `twitch.client_secret`. `config.json` is git-ignored — never commit it.

**4. Check it works** (optional, recommended)

```bat
:: prints your current Twitch category and which image it would use
python twitch_api.py
:: full flow without OBS: popup → story generated and opened
python stream_notice.py --test
```

**5. Start it before streaming** (every time)

```bat
cd jp-auto\projects\stream-notice
.venv\Scripts\activate
python stream_notice.py
```

Leave that console open. It connects to OBS (if OBS is closed it retries every 5 s, and reconnects if OBS is closed later), and when you press *Start Streaming* the popup shows up. Stop it with `Ctrl+C` or by closing the console. Generated stories are saved in `output/`.

**6. Or start it with Windows** (recommended on the streaming PC)

Double-click **`install_autostart.bat`**: it adds a shortcut to your Startup folder (no admin rights) and starts it right away, without a console. It then lives as an **icon next to the clock** (status, *Probar aviso*, stories folder, log, *Salir*), writes everything to `logs/stream-notice.log`, and only one copy can run at a time. `uninstall_autostart.bat` turns it off.

📘 **Full step-by-step guide for the streaming PC:** [`docs/streaming-pc-setup.md`](docs/streaming-pc-setup.md).

### Social media (Instagram, TikTok and WhatsApp)

Instagram and TikTok need the story at a **public URL**, so it's first uploaded to the `media` branch of this (public) repository: each publish replaces the branch with a single parentless commit holding the current story plus fixed files (TikTok's verification files, the legal docs and this README), so it never piles up old images or touches `main`.

- **Instagram** (`destinations/instagram.py`) — publishes a **Story** with the official *Instagram API with Instagram Login* (no Facebook Page needed). One-time setup: professional account (Creator/Business) → app in [Meta for Developers](https://developers.facebook.com) with the *Manage messaging & content on Instagram* use case → add yourself as *Instagram Tester* and accept the invite → *API setup with Instagram login* → *Generate token* → `destinations.instagram.access_token`. The app stays in development mode (own account only, no App Review). The 60-day token is refreshed automatically once it's older than 24 h.
- **TikTok** (`destinations/tiktok.py`) — sends the photo to your **TikTok inbox as a draft**; you finish and post it in the app with a couple of taps. Fully automatic public posting isn't possible officially: unaudited apps can only post privately and TikTok's audit rejects tools for your own account. One-time setup: app in [TikTok for Developers](https://developers.tiktok.com) → switch to **Sandbox** (no review needed), add *Login Kit* (redirect URI `http://localhost:3455/callback/`) and *Content Posting API*, scopes `user.info.basic` + `video.upload`, verify the URL prefix `https://raw.githubusercontent.com/<you>/jp-auto/media/`, add your account as target user → sandbox client key/secret in `destinations.tiktok` → authorize once with `python -m destinations.tiktok --login`.
- **WhatsApp channel** (`destinations/whatsapp.py`) — posts the story image to your **WhatsApp channel** with a caption and the stream link. WhatsApp has no official API for channels, so it goes through [Whapi.cloud](https://whapi.cloud)'s **free Developer Sandbox**, which links your number as one more device (like WhatsApp Web). One request per stream, far below the free limits; if they're ever reached, it fails with a clear message instead of paying. The image is uploaded directly, no public URL needed. One-time setup: Whapi account → create a channel and scan the QR with your phone (*Linked devices*) → copy its API token to `destinations.whatsapp.token` → get your channel id (`…@newsletter`, from `GET /newsletters` in their panel) into `destinations.whatsapp.channel_id`. Your number must be an admin of the WhatsApp channel. The sandbox must be used periodically to stay active, and if your phone goes offline for ~14 days the link expires: scan the QR again. Unofficial access is against WhatsApp's terms; at one message per stream the risk is low, but not zero.
- **GitHub** (`hosting.py`) — a fine-grained token with *Contents: Read and write* on this repo only → `hosting.github_token`.
- Tokens the program refreshes on its own live in **`tokens.json`** (git-ignored, next to `config.json`).
- The TikTok app details (terms, privacy, desktop URL) point to [`legal/terms.md`](legal/terms.md), [`legal/privacy.md`](legal/privacy.md) and this README, served from the `media` branch because TikTok requires them under the verified URL prefix.

### Moving it to another PC

`git clone` brings the code, the template and the tests, but **not your credentials** (`config.json`, `tokens.json`) nor your `game_images/` and `output/`, which are git-ignored on purpose: copy them by hand and set that PC's OBS WebSocket password. Use it on one PC at a time (TikTok's refresh token rotates). Every step, including the automatic start with Windows and troubleshooting, is in [`docs/streaming-pc-setup.md`](docs/streaming-pc-setup.md).

### Testing

Every feature is verified at three levels, all in `tests/` and run with [pytest](https://docs.pytest.org/):

- **Unit tests** — story composition (screen detection, fit modes, no white halo around the screen, one story per game), Twitch/IGDB logic against a simulated API (token caching and renewal, IGDB → box art fallbacks, search by name), own image matching, destinations (a failing one never stops the rest), GitHub hosting, Instagram, TikTok and WhatsApp against simulated APIs (token refresh, processing states, clear errors such as relinking WhatsApp or hitting the free plan limit), and background mode (timestamped log with rotation, working without a console, single instance, Startup shortcut, tray menu).
- **Integration** — the real app, window included, against a **fake OBS** that speaks the real obs-websocket v5 protocol (hello, password challenge, stream events): reconnection, wrong password, duplicate events, every popup state, fixed size, placement on OBS's monitor, the window never freezing, existing story preview, image picker and failing destinations. It runs in its own process with temporary `game_images/` and `output/` folders.
- **Real regression** — run before every merge: **real mouse clicks, wheel and keystrokes** (Windows API) against **real Twitch and IGDB**. Only the stream start comes from the fake OBS, so nothing ever goes live on the channel, and it only uses the *open on PC* destination, so it never posts to social media. It moves the cursor for a couple of minutes, so it only runs when asked for explicitly.

```bat
pip install -r requirements-dev.txt
:: unit + integration (~1.5 min, opens popups)
python -m pytest
:: real regression: needs config.json, don't touch the mouse
python -m pytest -m real
```

### Other commands

```bat
:: composes a test story without credentials (generated test image if none given)
python compose.py [image]
```

### The popup

- Opens **centered on the monitor where OBS is** (useful with several monitors; if OBS is minimized it uses the monitor it was on). If OBS isn't found, it opens on the main monitor.
- Twitch Dark style, always on top and with a **fixed size**, so nothing jumps between states: question → progress (category → game image → story created → sending to social media, naming each destination as it goes) → done or error (with *Retry*).
- The done screen confirms the story was created (or reused) and lists every destination with ✓ or ✗ plus the reason if it failed, next to the story thumbnail and *Open folder*.
- Keyboard: `Enter` = main button, `Esc` = No / Close. It can't be closed while the story is being generated.
- **If there's already a story for that game** in `output/` (the most recent one), it's shown large first (the popup grows only for this preview): *Send this one* publishes it as is, without generating anything; *Generate new* builds a fresh one (going through the image picker if you have own images) and sends it. Turn it off with `"reuse_existing_story": false`.

### Game image

**Your own images** go in `game_images/`. Any image (`.png`, `.jpg`, `.jpeg`, `.webp`) whose name **contains** the game name counts, and so does any image inside a folder whose name contains it. The name is compared as a *slug* (lowercase, no accents, anything that isn't a letter or number becomes `-`), so capitals, spaces and accents don't matter.

```
game_images/
  fortnite.png                          → Fortnite
  the-callisto-protocol.png             → The Callisto Protocol
  the-callisto-protocol-jacob.jpg       → The Callisto Protocol
  the-callisto-protocol/portada.jpg     → The Callisto Protocol
  Pokémon Legends Z-A.png               → Pokémon Legends: Z-A
```

- **If you have own images for the game**, the popup lets you **choose** between all of them and the internet image (IGDB artwork, or the Twitch box art if there's none). If the internet image can't be downloaded, you choose among your own.
- **If you don't**, the internet image is used directly, and the console tells you which name to use to add one.
- Heads-up: since the match is "contains", a game can pick up images of another one with a longer name (*Portal* also shows `portal-2.png`). The picker shows them before anything is generated.

**`output/` keeps only the latest story of each game**: saving a new one deletes the previous ones of that game.

### Configuration (`config.json`)

| Key | What it does |
|---|---|
| `obs` | WebSocket host, port and password. |
| `twitch` | Channel, Client ID and Secret. |
| `template` | Template image with a white TV screen (detected automatically). |
| `crt_effect` | Subtle scanlines + vignette on the game image (off by default). |
| `reuse_existing_story` | `true` (default): if a story for the game already exists, preview it and ask before generating a new one. `false`: always generate. |
| `screen_fit` | `"cover"` (default): fills the TV screen, cropping what doesn't fit (very wide images lose their sides, sometimes part of the game logo — use an own image in `game_images/` for those). `"contain"`: whole game image, with black bands inside the TV where it doesn't reach. |
| `category_delay_seconds` | Wait before reading the category, in case you change it right as the stream starts. |
| `hosting` | Public URL for the story: `github_token`, `repo`, `branch` (`media`), `static_files` (fixed files by content, e.g. TikTok verification) and `project_files` (project files published as is). |
| `destinations` | Where to publish; each one is a module in `destinations/` (with a `publish()` function and a `NAME` shown in the popup) toggled with `"enabled": true/false`: `open_image`, `instagram`, `tiktok` (with `title`/`description`, `{game}` is replaced), `whatsapp` (`token`, `channel_id`, `link` and `caption`, where `{game}` and `{link}` are replaced). |

---

## Español

> **Estado: fases 1 y 2 funcionando.** Verificadas con un inicio de directo real en OBS, datos reales de Twitch/IGDB, una historia real en Instagram y un borrador real en TikTok. El destino del canal de WhatsApp está cubierto por pruebas contra una API de Whapi simulada y falta su primera publicación real.

Cuando pulsas "Iniciar transmisión" en OBS Studio, una ventana pregunta si quieres enviar los avisos. Si aceptas, genera una imagen de historia (1080×1920) con el juego de tu categoría actual de Twitch dentro de la pantalla de la tele de la plantilla `story-notice.png`, y **la publica como historia de Instagram**, **la manda como borrador a tu bandeja de TikTok** y **la publica en tu canal de WhatsApp** con el enlace al directo (además de abrirla en el PC).

Funciona como programa externo conectado a OBS por WebSocket (OBS 28+), nunca como script de OBS: un diálogo bloqueante congelaría OBS. Es ligero para un PC de streaming modesto.

### Cómo arrancarlo

Requisitos: Windows, **Python 3.10+** ([python.org](https://www.python.org/downloads/), marcando "Add python.exe to PATH") y **OBS Studio 28+**.

**1. Descargar el código e instalar dependencias** (una vez)

```bat
git clone https://github.com/jsierram-dev/jp-auto.git
cd jp-auto\projects\stream-notice
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**2. Conseguir las credenciales** (una vez)

- **Contraseña del WebSocket de OBS**: OBS → Herramientas → Ajustes del servidor WebSocket → marcar *Habilitar servidor WebSocket*, dejar el puerto 4455 y pulsar *Mostrar información de conexión* para copiar la contraseña.
- **Client ID / Secret de Twitch**: [dev.twitch.tv/console](https://dev.twitch.tv/console) → *Registrar tu aplicación* (URL de redirección OAuth `http://localhost`, categoría *Application Integration*, tipo de cliente *Confidencial*) → *Administrar* → copiar el Client ID y generar un *Nuevo secreto* (solo se muestra una vez). Twitch exige tener la **verificación en dos pasos** activada en la cuenta para registrar apps. Las mismas credenciales sirven para IGDB.

**3. Crear `config.json`** (una vez)

```bat
copy config.example.json config.json
```

Rellenar `obs.password`, `twitch.client_id` y `twitch.client_secret`. `config.json` está ignorado por git: nunca se commitea.

**4. Comprobar que funciona** (opcional, recomendado)

```bat
:: muestra tu categoría actual de Twitch y qué imagen usaría
python twitch_api.py
:: flujo completo sin OBS: popup → historia generada y abierta
python stream_notice.py --test
```

**5. Arrancarlo antes de emitir** (cada vez)

```bat
cd jp-auto\projects\stream-notice
.venv\Scripts\activate
python stream_notice.py
```

Deja esa consola abierta. Se conecta a OBS (si OBS está cerrado reintenta cada 5 s, y si se cierra después vuelve a conectarse solo) y, al pulsar *Iniciar transmisión*, aparece el popup. Se para con `Ctrl+C` o cerrando la consola. Las historias generadas se guardan en `output/`.

**6. O que arranque con Windows** (recomendado en el PC de streaming)

Doble clic en **`install_autostart.bat`**: añade un acceso directo a tu carpeta de Inicio (sin permisos de administrador) y lo arranca ya, sin consola. A partir de ahí vive como un **icono junto al reloj** (estado, *Probar aviso*, carpeta de historias, registro, *Salir*), escribe todo en `logs/stream-notice.log` y solo puede haber una copia en marcha. `uninstall_autostart.bat` lo desactiva.

📘 **Guía completa paso a paso para el PC de streaming:** [`docs/streaming-pc-setup.md`](docs/streaming-pc-setup.md).

### Redes sociales (Instagram, TikTok y WhatsApp)

Instagram y TikTok necesitan la historia en una **URL pública**, así que primero se sube a la rama `media` de este repositorio (público): en cada publicación la rama se sustituye por un único commit sin padres con la historia actual y los archivos fijos (los de verificación de TikTok, los documentos legales y este README), así que nunca acumula imágenes antiguas ni toca `main`.

- **Instagram** (`destinations/instagram.py`) — publica una **historia** con la API oficial *Instagram API with Instagram Login* (sin página de Facebook). Configuración única: cuenta profesional (Creador/Empresa) → app en [Meta for Developers](https://developers.facebook.com) con el caso de uso *Manage messaging & content on Instagram* → añadirte como *Instagram Tester* y aceptar la invitación → *API setup with Instagram login* → *Generate token* → `destinations.instagram.access_token`. La app se queda en modo desarrollo (solo tu cuenta, sin App Review). El token de 60 días se renueva solo cuando tiene más de 24 h.
- **TikTok** (`destinations/tiktok.py`) — manda la foto a tu **bandeja de TikTok como borrador**; la terminas y publicas en la app con un par de toques. Publicar en público de forma automática no es posible por la vía oficial: las apps sin auditar solo publican en privado y la auditoría de TikTok rechaza herramientas para la propia cuenta. Configuración única: app en [TikTok for Developers](https://developers.tiktok.com) → cambiar a **Sandbox** (no necesita revisión), añadir *Login Kit* (redirect URI `http://localhost:3455/callback/`) y *Content Posting API*, permisos `user.info.basic` + `video.upload`, verificar el prefijo de URL `https://raw.githubusercontent.com/<tú>/jp-auto/media/`, añadir tu cuenta como target user → client key/secret del sandbox en `destinations.tiktok` → autorizar una vez con `python -m destinations.tiktok --login`.
- **Canal de WhatsApp** (`destinations/whatsapp.py`) — publica la imagen de la historia en tu **canal de WhatsApp** con un pie de foto y el enlace al directo. WhatsApp no tiene API oficial para canales, así que va por el **plan gratuito (Developer Sandbox) de [Whapi.cloud](https://whapi.cloud)**, que vincula tu número como un dispositivo más (como WhatsApp Web). Una petición por directo, muy por debajo de los límites gratuitos; si alguna vez se alcanzan, falla con un mensaje claro en vez de pagar. La imagen se sube directamente, sin URL pública. Configuración única: cuenta en Whapi → crear un canal y escanear el QR con el móvil (*Dispositivos vinculados*) → copiar su token de API en `destinations.whatsapp.token` → poner el id de tu canal (`…@newsletter`, con `GET /newsletters` en su panel) en `destinations.whatsapp.channel_id`. Tu número tiene que ser administrador del canal de WhatsApp. El sandbox hay que usarlo de vez en cuando para que siga activo, y si el móvil pasa ~14 días sin conexión la vinculación caduca: vuelve a escanear el QR. El acceso no oficial va contra las condiciones de WhatsApp; con un mensaje por directo el riesgo es bajo, pero no nulo.
- **GitHub** (`hosting.py`) — un token *fine-grained* con *Contents: Read and write* solo sobre este repo → `hosting.github_token`.
- Los tokens que el programa renueva solo viven en **`tokens.json`** (ignorado por git, junto a `config.json`).
- Los datos de la app de TikTok (términos, privacidad, URL de escritorio) apuntan a [`legal/terms.md`](legal/terms.md), [`legal/privacy.md`](legal/privacy.md) y este README, servidos desde la rama `media` porque TikTok los exige dentro del prefijo de URL verificado.

### Llevarlo a otro PC

`git clone` trae el código, la plantilla y las pruebas, pero **no tus credenciales** (`config.json`, `tokens.json`) ni tus `game_images/` y `output/`, que git ignora a propósito: cópialos a mano y pon la contraseña del WebSocket del OBS de ese PC. Úsalo en un solo PC a la vez (el token de renovación de TikTok cambia al usarse). Todos los pasos, incluido el arranque con Windows y qué hacer si algo falla, están en [`docs/streaming-pc-setup.md`](docs/streaming-pc-setup.md).

### Pruebas

Cada funcionalidad se verifica a tres niveles, todo en `tests/` y ejecutado con [pytest](https://docs.pytest.org/):

- **Unitarias** — composición de la historia (detección de la pantalla, modos de encaje, sin borde blanco alrededor de la pantalla, una historia por juego), lógica de Twitch/IGDB contra una API simulada (caché y renovación del token, IGDB → carátula como respaldo, búsqueda por nombre), búsqueda de imágenes propias, destinos (si uno falla, los demás siguen), alojamiento en GitHub, Instagram, TikTok y WhatsApp contra APIs simuladas (renovación de tokens, estados de procesado, errores claros como volver a vincular WhatsApp o llegar al límite del plan gratuito), y el modo en segundo plano (registro con fecha y rotación, funcionar sin consola, una sola copia, acceso directo de Inicio, menú del icono).
- **Integración** — la app real, con su ventana, contra un **OBS falso** que habla el protocolo real de obs-websocket v5 (saludo, contraseña, eventos de directo): reconexión, contraseña incorrecta, eventos duplicados, todos los estados del popup, tamaño fijo, posición en el monitor de OBS, que la ventana nunca se congele, vista previa de historia existente, selector de imagen y destinos que fallan. Corre en su propio proceso con carpetas temporales de `game_images/` y `output/`.
- **Regresión real** — antes de cada merge: **clicks, rueda y teclas reales** del ratón y el teclado (API de Windows) contra **Twitch e IGDB reales**. Solo el inicio de directo sale del OBS falso, así que nunca se emite en el canal, y solo usa el destino *abrir en el PC*, así que nunca publica en redes. Mueve el cursor durante un par de minutos, así que solo se ejecuta si se pide expresamente.

```bat
pip install -r requirements-dev.txt
:: unitarias + integración (~1,5 min, abre popups)
python -m pytest
:: regresión real: necesita config.json, no toques el ratón
python -m pytest -m real
```

### Otros comandos

```bat
:: compone una historia de prueba sin credenciales (imagen generada si no se pasa ninguna)
python compose.py [imagen]
```

### El popup

- Se abre **centrado en el monitor donde está OBS** (útil con varios monitores; si OBS está minimizado usa el monitor en el que estaba). Si no encuentra OBS, sale en el monitor principal.
- Estilo Twitch Dark, siempre encima y de **tamaño fijo**, para que nada salte entre estados: pregunta → progreso (categoría → imagen del juego → historia creada → envío a redes sociales, diciendo a qué destino está enviando) → listo o error (con *Reintentar*).
- La pantalla final confirma que la historia se ha creado (o reutilizado) y lista cada destino con ✓ o ✗ y el motivo si falló, junto a la miniatura de la historia y *Abrir carpeta*.
- Teclado: `Enter` = botón principal, `Esc` = No / Cerrar. No se puede cerrar mientras se genera la historia.
- **Si ya hay una historia de ese juego** en `output/` (la más reciente), primero se enseña en grande (el popup crece solo para esta vista previa): *Enviar esta* la publica tal cual, sin generar nada; *Generar nueva* crea otra (pasando por el selector de imagen si tienes imágenes propias) y la envía. Se desactiva con `"reuse_existing_story": false`.

### Imagen del juego

**Tus imágenes propias** van en `game_images/`. Cuenta cualquier imagen (`.png`, `.jpg`, `.jpeg`, `.webp`) cuyo nombre **contenga** el nombre del juego, y cualquier imagen dentro de una carpeta cuyo nombre lo contenga. El nombre se compara en formato *slug* (minúsculas, sin tildes, y todo lo que no sea letra o número pasa a `-`), así que mayúsculas, espacios y tildes dan igual.

```
game_images/
  fortnite.png                          → Fortnite
  the-callisto-protocol.png             → The Callisto Protocol
  the-callisto-protocol-jacob.jpg       → The Callisto Protocol
  the-callisto-protocol/portada.jpg     → The Callisto Protocol
  Pokémon Legends Z-A.png               → Pokémon Legends: Z-A
```

- **Si tienes imágenes propias del juego**, el popup te deja **elegir** entre todas ellas y la de internet (arte de IGDB o, si no hay, la carátula de Twitch). Si la de internet no se puede descargar, eliges entre las tuyas.
- **Si no tienes**, se usa directamente la de internet, y la consola te dice con qué nombre guardarla para añadir una.
- Ojo: como se busca "que contenga el nombre", un juego puede coger imágenes de otro con un nombre más largo (*Portal* también enseña `portal-2.png`). El selector te las muestra antes de generar nada.

**En `output/` solo se queda la última historia de cada juego**: al guardar una nueva se borran las anteriores de ese juego.

### Configuración (`config.json`)

| Clave | Qué hace |
|---|---|
| `obs` | Host, puerto y contraseña del WebSocket. |
| `twitch` | Canal, Client ID y Secret. |
| `template` | Plantilla con la pantalla de la tele en blanco (se detecta sola). |
| `crt_effect` | Scanlines y viñeta sutiles sobre la imagen del juego (desactivado por defecto). |
| `reuse_existing_story` | `true` (por defecto): si ya existe una historia del juego, la enseña y pregunta antes de generar otra. `false`: genera siempre. |
| `screen_fit` | `"cover"` (por defecto): rellena la pantalla de la tele y recorta lo que sobra (a las imágenes muy anchas se les cortan los laterales, a veces parte del logo del juego; para esas, usa una imagen propia en `game_images/`). `"contain"`: la imagen del juego entera, con bandas negras dentro de la tele donde no llegue. |
| `category_delay_seconds` | Espera antes de leer la categoría, por si la cambias justo al empezar el directo. |
| `hosting` | URL pública para la historia: `github_token`, `repo`, `branch` (`media`), `static_files` (archivos fijos por contenido, p. ej. la verificación de TikTok) y `project_files` (archivos del proyecto publicados tal cual). |
| `destinations` | Dónde publicar; cada uno es un módulo en `destinations/` (con una función `publish()` y un `NAME` que se enseña en el popup) activado con `"enabled": true/false`: `open_image`, `instagram`, `tiktok` (con `title`/`description`, `{game}` se sustituye), `whatsapp` (`token`, `channel_id`, `link` y `caption`, donde se sustituyen `{game}` y `{link}`). |
