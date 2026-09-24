# stream-notice

**[English](#english)** &nbsp;|&nbsp; **[Español](#español)**

---

## English

> **Status: in progress.** Project scaffolded; modules not implemented yet.

When you press "Start Streaming" in OBS Studio, a popup asks whether to send notices. If you accept, it builds a story image (1080×1920) with the game from your current Twitch category placed inside the TV screen of the `story-notice.png` template, and opens it (publishing to social media comes in phase 2).

Runs as an external program connected to OBS over WebSocket (OBS 28+), never as an OBS script — a blocking dialog would freeze OBS.

### Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy config.example.json config.json   # then fill in your credentials
```

Credentials needed:
- **OBS WebSocket password**: OBS → Tools → WebSocket Server Settings.
- **Twitch Client ID / Secret**: [dev.twitch.tv/console](https://dev.twitch.tv/console) (also used for IGDB).

### Usage

```bash
python stream_notice.py            # waits for OBS to start streaming
python stream_notice.py --test     # simulates a stream start, no OBS needed
```

Custom game images go in `game_images/<game-slug>.(png|jpg|jpeg|webp)` (e.g. `fortnite.png`) and take priority over IGDB artwork and the Twitch box art.

---

## Español

> **Estado: en construcción.** Proyecto creado; los módulos aún no están implementados.

Cuando pulsas "Iniciar transmisión" en OBS Studio, una ventana pregunta si quieres enviar los avisos. Si aceptas, genera una imagen de historia (1080×1920) con el juego de tu categoría actual de Twitch dentro de la pantalla de la tele de la plantilla `story-notice.png`, y la abre (la publicación en redes llega en la fase 2).

Funciona como programa externo conectado a OBS por WebSocket (OBS 28+), nunca como script de OBS: un diálogo bloqueante congelaría OBS.

### Instalación

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy config.example.json config.json   # y rellena tus credenciales
```

Credenciales necesarias:
- **Contraseña del WebSocket de OBS**: OBS → Herramientas → Ajustes del servidor WebSocket.
- **Client ID / Secret de Twitch**: [dev.twitch.tv/console](https://dev.twitch.tv/console) (sirven también para IGDB).

### Uso

```bash
python stream_notice.py            # espera a que OBS empiece a transmitir
python stream_notice.py --test     # simula un inicio de directo sin OBS
```

Las imágenes propias de juegos van en `game_images/<slug-del-juego>.(png|jpg|jpeg|webp)` (p. ej. `fortnite.png`) y tienen prioridad sobre el arte de IGDB y la carátula de Twitch.
