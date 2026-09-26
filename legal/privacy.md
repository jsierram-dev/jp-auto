# Privacy Policy — stream-notice

**[English](#english)** &nbsp;|&nbsp; **[Español](#español)**

*Last updated: September 24, 2026*

---

## English

stream-notice is a **personal, non-commercial desktop tool** built and used by its author only, to announce their own Twitch live streams on their own social media accounts. It has no users other than its author, no server and no website that collects data.

### What data it accesses

- **Twitch / IGDB**: the current category of the author's own Twitch channel and public game artwork, using app credentials (no user login).
- **Instagram** (Instagram API with Instagram Login): the author's own professional account id and username, and permission to publish Stories to that account.
- **TikTok** (Login Kit + Content Posting API): the author's own TikTok `open_id` and basic profile info (`user.info.basic`), and permission to send photo drafts to that account's inbox (`video.upload`).
- **OBS Studio**: stream start events from the author's local OBS, over a local WebSocket connection.

### How it is used and stored

- Data is used **only** to generate a story image and send it to the author's own accounts, when the author confirms it in the app.
- Access tokens are stored **locally on the author's computer** (`config.json` / `tokens.json`, never committed to the repository) and are only sent to the service that issued them.
- To be published, each story image is uploaded to a public branch of this repository (`media`). Each upload replaces the previous one; it contains nothing but the story image itself.
- No data is sold, shared with third parties, used for advertising or analytics, or collected from anyone other than the author.

### Removing access

Access can be revoked at any time from each platform's settings (Instagram: *Apps and websites*; TikTok: *Security → Manage app permissions*) and by deleting the local `tokens.json` file.

### Contact

Questions: [open an issue in this repository](https://github.com/jsierram-dev/jp-auto/issues).

---

## Español

stream-notice es una **herramienta de escritorio personal y sin ánimo de lucro**, creada y usada solo por su autor para anunciar sus propios directos de Twitch en sus propias redes sociales. No tiene más usuarios que su autor, ni servidor, ni web que recoja datos.

### A qué datos accede

- **Twitch / IGDB**: la categoría actual del canal de Twitch del autor y arte público de los juegos, con credenciales de aplicación (sin iniciar sesión como usuario).
- **Instagram** (Instagram API with Instagram Login): el id y el nombre de usuario de la cuenta profesional del autor, y permiso para publicar historias en ella.
- **TikTok** (Login Kit + Content Posting API): el `open_id` y la información básica del perfil del autor (`user.info.basic`), y permiso para enviar borradores de fotos a la bandeja de esa cuenta (`video.upload`).
- **OBS Studio**: los eventos de inicio de directo del OBS local del autor, por una conexión WebSocket local.

### Cómo se usan y se guardan

- Los datos se usan **solo** para generar la imagen de la historia y enviarla a las cuentas del autor, cuando el autor lo confirma en la app.
- Los tokens de acceso se guardan **solo en el ordenador del autor** (`config.json` / `tokens.json`, nunca se suben al repositorio) y solo se envían al servicio que los emitió.
- Para poder publicarla, cada imagen de historia se sube a una rama pública de este repositorio (`media`). Cada subida sustituye a la anterior y solo contiene la propia imagen.
- No se venden datos, no se comparten con terceros, no se usan para publicidad ni analítica y no se recogen de nadie más que del autor.

### Retirar el acceso

El acceso se puede retirar en cualquier momento desde los ajustes de cada plataforma (Instagram: *Apps y sitios web*; TikTok: *Seguridad → Gestionar permisos de apps*) y borrando el archivo local `tokens.json`.

### Contacto

Dudas: [abre un issue en este repositorio](https://github.com/jsierram-dev/jp-auto/issues).
