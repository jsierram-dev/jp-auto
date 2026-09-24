# stream-notice

**[English](#english)** &nbsp;|&nbsp; **[Español](#español)**

---

## English

> **Status: phase 1 built** (image generation + open locally). Tested against a simulated OBS; pending a first run with real OBS and Twitch credentials. Social media publishing comes in phase 2.

When you press "Start Streaming" in OBS Studio, a popup asks whether to send notices. If you accept, it builds a story image (1080×1920) with the game from your current Twitch category placed inside the TV screen of the `story-notice.png` template, and opens it.

Runs as an external program connected to OBS over WebSocket (OBS 28+), never as an OBS script — a blocking dialog would freeze OBS. Lightweight enough for a modest streaming PC.

### Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy config.example.json config.json   # then fill in your credentials
```

Credentials needed:
- **OBS WebSocket password**: OBS → Tools → WebSocket Server Settings (enable the server, port 4455).
- **Twitch Client ID / Secret**: [dev.twitch.tv/console](https://dev.twitch.tv/console) → Register Your Application (also used for IGDB).

### Usage

```bash
python stream_notice.py            # waits for OBS to start streaming (retries every 5 s if OBS is closed)
python stream_notice.py --test     # simulates a stream start, no OBS needed
python twitch_api.py               # prints your current game and which image would be used
python compose.py [image]          # composes a test story without credentials
```

### Game image

Picked in this order:
1. **Your own image** in `game_images/`, named after the Twitch category as a *slug*: lowercase, accents removed, anything that isn't a letter or number becomes `-`. Extension `.png`, `.jpg`, `.jpeg` or `.webp`.

   | Twitch category | File |
   |---|---|
   | Fortnite | `fortnite.png` |
   | Grand Theft Auto V | `grand-theft-auto-v.jpg` |
   | Pokémon Legends: Z-A | `pokemon-legends-z-a.png` |
   | EA SPORTS FC 25 | `ea-sports-fc-25.webp` |

   If there's no own image, the console prints the exact name to use.
2. IGDB promotional artwork (or a screenshot if there's none).
3. Twitch box art (vertical, gets cropped).

### Configuration (`config.json`)

| Key | What it does |
|---|---|
| `obs` | WebSocket host, port and password. |
| `twitch` | Channel, Client ID and Secret. |
| `template` | Template image with a white TV screen (detected automatically). |
| `crt_effect` | Subtle scanlines + vignette on the game image. |
| `category_delay_seconds` | Wait before reading the category, in case you change it right as the stream starts. |
| `destinations` | Where to publish; each one is a module in `destinations/` with `"enabled": true/false`. Today: `open_image`. |

---

## Español

> **Estado: fase 1 construida** (generación de la imagen + abrirla en local). Probada contra un OBS simulado; falta la primera ejecución con OBS real y credenciales de Twitch. La publicación en redes llega en la fase 2.

Cuando pulsas "Iniciar transmisión" en OBS Studio, una ventana pregunta si quieres enviar los avisos. Si aceptas, genera una imagen de historia (1080×1920) con el juego de tu categoría actual de Twitch dentro de la pantalla de la tele de la plantilla `story-notice.png`, y la abre.

Funciona como programa externo conectado a OBS por WebSocket (OBS 28+), nunca como script de OBS: un diálogo bloqueante congelaría OBS. Es ligero para un PC de streaming modesto.

### Instalación

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy config.example.json config.json   # y rellena tus credenciales
```

Credenciales necesarias:
- **Contraseña del WebSocket de OBS**: OBS → Herramientas → Ajustes del servidor WebSocket (activar el servidor, puerto 4455).
- **Client ID / Secret de Twitch**: [dev.twitch.tv/console](https://dev.twitch.tv/console) → Registrar tu aplicación (sirven también para IGDB).

### Uso

```bash
python stream_notice.py            # espera a que OBS empiece a transmitir (reintenta cada 5 s si OBS está cerrado)
python stream_notice.py --test     # simula un inicio de directo sin OBS
python twitch_api.py               # muestra tu juego actual y qué imagen usaría
python compose.py [imagen]         # compone una historia de prueba sin credenciales
```

### Imagen del juego

Se elige en este orden:
1. **Imagen propia** en `game_images/`, con el nombre de la categoría de Twitch en formato *slug*: minúsculas, sin tildes, y todo lo que no sea letra o número pasa a `-`. Extensión `.png`, `.jpg`, `.jpeg` o `.webp`.

   | Categoría en Twitch | Archivo |
   |---|---|
   | Fortnite | `fortnite.png` |
   | Grand Theft Auto V | `grand-theft-auto-v.jpg` |
   | Pokémon Legends: Z-A | `pokemon-legends-z-a.png` |
   | EA SPORTS FC 25 | `ea-sports-fc-25.webp` |

   Si no hay imagen propia, la consola te dice el nombre exacto que tiene que tener.
2. Arte promocional de IGDB (o una captura si no hay).
3. Carátula de Twitch (vertical, se recorta).

### Configuración (`config.json`)

| Clave | Qué hace |
|---|---|
| `obs` | Host, puerto y contraseña del WebSocket. |
| `twitch` | Canal, Client ID y Secret. |
| `template` | Plantilla con la pantalla de la tele en blanco (se detecta sola). |
| `crt_effect` | Scanlines y viñeta sutiles sobre la imagen del juego. |
| `category_delay_seconds` | Espera antes de leer la categoría, por si la cambias justo al empezar el directo. |
| `destinations` | Dónde publicar; cada uno es un módulo en `destinations/` con `"enabled": true/false`. Hoy: `open_image`. |
