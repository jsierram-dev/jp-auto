# jp-auto

**[English](#english)** &nbsp;|&nbsp; **[Español](#español)**

---

## English

Workspace with small, independent automations — each one a self-contained project under `projects/*`, with its own dependencies, config and README.

### Projects

| Project | What it is |
|---|---|
| [`stream-notice`](projects/stream-notice) | When a Twitch stream starts in OBS, asks whether to send notices and builds a story image (1080×1920) with the current game inside the TV of a template, and publishes it as an Instagram Story and a TikTok draft. Python, external to OBS (WebSocket). |

Each has its own README with installation and usage.

### Conventions

- Python projects use their own virtual environment (`.venv/` inside the project folder, never committed).
- Credentials live in a local `config.json` (git-ignored); every project ships a `config.example.json` to copy from.

---

## Español

Workspace con automatizaciones chicas e independientes — cada una es un proyecto autocontenido dentro de `projects/*`, con sus propias dependencias, configuración y README.

### Proyectos

| Proyecto | Qué es |
|---|---|
| [`stream-notice`](projects/stream-notice) | Cuando empieza un directo de Twitch en OBS, pregunta si enviar avisos y genera una imagen de historia (1080×1920) con el juego actual dentro de la tele de una plantilla, y la publica como historia de Instagram y borrador de TikTok. Python, externo a OBS (WebSocket). |

Cada uno tiene su propio README con instalación y uso.

### Convenciones

- Los proyectos Python usan su propio entorno virtual (`.venv/` dentro de la carpeta del proyecto, nunca se commitea).
- Las credenciales van en un `config.json` local (ignorado por git); cada proyecto trae un `config.example.json` para copiarlo.
