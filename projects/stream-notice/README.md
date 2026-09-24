# stream-notice

**[English](#english)** &nbsp;|&nbsp; **[Español](#español)**

---

## English

> **Status: phase 1 working** (image generation + open locally), verified with a real OBS stream start and real Twitch/IGDB data. Social media publishing comes in phase 2.

When you press "Start Streaming" in OBS Studio, a popup asks whether to send notices. If you accept, it builds a story image (1080×1920) with the game from your current Twitch category placed inside the TV screen of the `story-notice.png` template, and opens it.

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
| `screen_fit` | `"contain"` (default): whole game image, with black bands inside the TV where it doesn't reach. `"cover"`: fills the screen and crops the sides (the game logo may get cut). |
| `category_delay_seconds` | Wait before reading the category, in case you change it right as the stream starts. |
| `destinations` | Where to publish; each one is a module in `destinations/` (with a `publish()` function and a `NAME` shown in the popup) toggled with `"enabled": true/false`. Today: `open_image`. |

---

## Español

> **Estado: fase 1 funcionando** (generación de la imagen + abrirla en local), verificada con un inicio de directo real en OBS y datos reales de Twitch/IGDB. La publicación en redes llega en la fase 2.

Cuando pulsas "Iniciar transmisión" en OBS Studio, una ventana pregunta si quieres enviar los avisos. Si aceptas, genera una imagen de historia (1080×1920) con el juego de tu categoría actual de Twitch dentro de la pantalla de la tele de la plantilla `story-notice.png`, y la abre.

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
| `screen_fit` | `"contain"` (por defecto): la imagen del juego entera, con bandas negras dentro de la tele donde no llegue. `"cover"`: llena la pantalla y recorta los laterales (puede cortar el logo del juego). |
| `category_delay_seconds` | Espera antes de leer la categoría, por si la cambias justo al empezar el directo. |
| `destinations` | Dónde publicar; cada uno es un módulo en `destinations/` (con una función `publish()` y un `NAME` que se enseña en el popup) activado con `"enabled": true/false`. Hoy: `open_image`. |
