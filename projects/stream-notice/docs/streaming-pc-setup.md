# Streaming PC setup — stream-notice

**[English](#english)** &nbsp;|&nbsp; **[Español](#español)**

---

## English

Step-by-step guide to install stream-notice on the PC that runs OBS for streaming, starting from an already working setup on another PC (credentials and apps already created). If you are starting from scratch, create the credentials first as described in the [README](../README.md).

### What travels with `git clone` and what doesn't

| Comes with `git clone` | You copy it by hand (git-ignored on purpose) |
|---|---|
| Code, `story-notice.png` template, logo, tests, docs | `config.json` — all credentials |
| | `tokens.json` — Instagram and TikTok tokens the program keeps refreshed |
| | `game_images/` — your own game images (optional) |
| | `output/` — previous stories (optional) |

Copy them with a USB drive or similar. **Never** commit them or send them through chat or email.

### 1. Install Python

Download **Python 3.10 or newer** from [python.org](https://www.python.org/downloads/) and, in the first installer screen, tick **"Add python.exe to PATH"**. Check it in a new console:

```bat
python --version
```

### 2. Get the code and install dependencies

```bat
git clone https://github.com/jsierram-dev/jp-auto.git
cd jp-auto\projects\stream-notice
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

(No `git`? Download the repo as a ZIP from GitHub → *Code → Download ZIP* and unzip it.)

### 3. Copy your credentials

From the old PC's `jp-auto\projects\stream-notice\` folder, copy **`config.json`** and **`tokens.json`** into the same folder on this PC (plus `game_images\` if you have your own images).

### 4. Point it to this PC's OBS

Each OBS has its own WebSocket password:

1. OBS → **Tools → WebSocket Server Settings** → tick **Enable WebSocket server**, keep port **4455**.
2. **Show Connect Info** → copy the password.
3. Paste it into `config.json` → `"obs": { "password": "..." }`.

### 5. Check it works

```bat
:: current Twitch category and which image it would use (no posting)
python twitch_api.py
:: full flow without OBS: the popup appears; answer "No" to avoid posting
python stream_notice.py --test
```

If you answer **"Sí, enviar"** in the test, it really publishes: an Instagram Story and a TikTok draft.

### 6. Start it with Windows

Double-click **`install_autostart.bat`**. It:

- creates a shortcut in your user's Startup folder (no admin rights needed), so it starts on its own every time you log into Windows;
- starts it right away, without a console window.

From then on it lives as an **icon next to the clock** (it may be hidden under the `^` arrow; drag it to the taskbar to keep it visible). Right-click it:

| Menu | What it does |
|---|---|
| ● Conectado a OBS / ○ Esperando a OBS… | Status: connected to / waiting for OBS (OBS can be opened before or after; it retries every 5 s) |
| Probar aviso | Opens the popup as if a stream had started. Answering "Sí, enviar" **publishes for real** |
| Abrir carpeta de historias | Opens `output\` |
| Ver registro | Opens `logs\stream-notice.log` (everything it did, with date and time) |
| Salir | Stops it until the next Windows start |

Only one copy can run at a time: starting it again shows "ya está en marcha".

To turn off the automatic start: **`uninstall_autostart.bat`** (and *Salir* from the icon if it's running).

### 7. Stop using it on the old PC

Use it on **one PC only**. TikTok's refresh token changes every time it's used, so two copies refreshing on their own invalidate each other. On the old PC: icon → *Salir*, and `uninstall_autostart.bat` if you had enabled it there.

### Troubleshooting

| Problem | What to do |
|---|---|
| No icon next to the clock | Look under the `^` arrow. If it's not there, check `logs\stream-notice.log`, or run `python stream_notice.py` in a console to see the error. |
| "Falta config.json" window | Step 3: `config.json` isn't in `projects\stream-notice\`. |
| Icon stays on "Esperando a OBS…" | OBS closed, WebSocket server disabled, or wrong password (step 4). The log says which. |
| Instagram ✗ "token ha caducado" | More than 60 days without using it: generate a new token in Meta for Developers (see README) and put it in `config.json`. |
| TikTok ✗ "no está autorizado" / "ha caducado" | Run `python -m destinations.tiktok --login` once (the browser opens to accept). |
| Certificate errors (SSL) | Handled automatically with Windows certificates (antivirus such as Avast). If it persists, update `pip install -r requirements.txt`. |

---

## Español

Guía paso a paso para instalar stream-notice en el PC que ejecuta OBS para emitir, partiendo de una instalación que ya funciona en otro PC (credenciales y apps ya creadas). Si empiezas de cero, crea antes las credenciales como explica el [README](../README.md).

### Qué viaja con `git clone` y qué no

| Viene con `git clone` | Lo copias tú (git lo ignora a propósito) |
|---|---|
| Código, plantilla `story-notice.png`, logo, pruebas, documentación | `config.json` — todas las credenciales |
| | `tokens.json` — los tokens de Instagram y TikTok que el programa va renovando |
| | `game_images/` — tus imágenes propias de juegos (opcional) |
| | `output/` — historias anteriores (opcional) |

Cópialos con un USB o similar. **Nunca** los subas a git ni los mandes por chat o correo.

### 1. Instalar Python

Descarga **Python 3.10 o superior** de [python.org](https://www.python.org/downloads/) y, en la primera pantalla del instalador, marca **"Add python.exe to PATH"**. Compruébalo en una consola nueva:

```bat
python --version
```

### 2. Descargar el código e instalar dependencias

```bat
git clone https://github.com/jsierram-dev/jp-auto.git
cd jp-auto\projects\stream-notice
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

(¿Sin `git`? Descarga el repo como ZIP desde GitHub → *Code → Download ZIP* y descomprímelo.)

### 3. Copiar tus credenciales

Desde la carpeta `jp-auto\projects\stream-notice\` del PC anterior, copia **`config.json`** y **`tokens.json`** a la misma carpeta en este PC (y `game_images\` si tienes imágenes propias).

### 4. Apuntarlo al OBS de este PC

Cada OBS tiene su propia contraseña del WebSocket:

1. OBS → **Herramientas → Ajustes del servidor WebSocket** → marca **Habilitar servidor WebSocket** y deja el puerto **4455**.
2. **Mostrar información de conexión** → copia la contraseña.
3. Pégala en `config.json` → `"obs": { "password": "..." }`.

### 5. Comprobar que funciona

```bat
:: categoría actual de Twitch y qué imagen usaría (no publica nada)
python twitch_api.py
:: flujo completo sin OBS: sale el popup; responde "No" para no publicar
python stream_notice.py --test
```

Si en la prueba respondes **"Sí, enviar"**, publica de verdad: historia en Instagram y borrador en TikTok.

### 6. Arrancarlo con Windows

Haz doble clic en **`install_autostart.bat`**. Hace dos cosas:

- crea un acceso directo en la carpeta de Inicio de tu usuario (sin permisos de administrador), para que arranque solo cada vez que inicies sesión en Windows;
- lo arranca ya mismo, sin ventana de consola.

A partir de ahí vive como un **icono junto al reloj** (puede quedar escondido en la flecha `^`; arrástralo a la barra para tenerlo siempre a la vista). Clic derecho:

| Menú | Qué hace |
|---|---|
| ● Conectado a OBS / ○ Esperando a OBS… | Estado (OBS puede abrirse antes o después; reintenta cada 5 s) |
| Probar aviso | Abre el popup como si empezara un directo. Si respondes "Sí, enviar", **publica de verdad** |
| Abrir carpeta de historias | Abre `output\` |
| Ver registro | Abre `logs\stream-notice.log` (todo lo que ha hecho, con fecha y hora) |
| Salir | Lo cierra hasta el próximo inicio de Windows |

Solo puede haber una copia en marcha: si lo intentas arrancar otra vez, avisa de que "ya está en marcha".

Para quitar el arranque automático: **`uninstall_autostart.bat`** (y *Salir* desde el icono si está en marcha).

### 7. Dejar de usarlo en el PC anterior

Úsalo en **un solo PC**. El token de renovación de TikTok cambia cada vez que se usa, así que dos copias renovándolo por su cuenta se invalidan entre sí. En el PC anterior: icono → *Salir*, y `uninstall_autostart.bat` si lo tenías activado allí.

### Si algo falla

| Problema | Qué hacer |
|---|---|
| No aparece el icono junto al reloj | Mira en la flecha `^`. Si no está, revisa `logs\stream-notice.log`, o ejecuta `python stream_notice.py` en una consola para ver el error. |
| Ventana "Falta config.json" | Paso 3: `config.json` no está en `projects\stream-notice\`. |
| El icono se queda en "Esperando a OBS…" | OBS cerrado, servidor WebSocket desactivado o contraseña incorrecta (paso 4). El registro dice cuál. |
| Instagram ✗ "token ha caducado" | Más de 60 días sin usarlo: genera un token nuevo en Meta for Developers (ver README) y ponlo en `config.json`. |
| TikTok ✗ "no está autorizado" / "ha caducado" | Ejecuta una vez `python -m destinations.tiktok --login` (se abre el navegador para aceptar). |
| Errores de certificado (SSL) | Se resuelven solos con los certificados de Windows (antivirus como Avast). Si siguen, actualiza con `pip install -r requirements.txt`. |
