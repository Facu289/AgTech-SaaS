# AgroApp — Cómo seguir en un Proyecto nuevo

> Resumen para retomar AgroApp desde cero en un **Proyecto** de Claude, sin depender de chats
> anteriores. Estado al **01/10/2026**.

## 1. Armar el Proyecto

1. En Claude: **Proyectos → Crear proyecto** → nombre: `AgroApp`.
2. En **Instrucciones del proyecto**, pegá el bloque de la sección 2.
3. En **Archivos / Conocimiento del proyecto**, subí estos archivos de tu carpeta `agroapp`:

   | Archivo | Para qué |
   |---|---|
   | `docs/INICIO_PROYECTO.md` (este) | estado actual y qué sigue |
   | `docs/PROJECT_CONTEXT.md` | cómo está hecha la app: tecnologías, base, comandos, decisiones, lecciones |
   | `docs/ROADMAP.md` | qué está hecho y qué falta |
   | `README.md` | cómo se arranca y "¿dónde toco para...?" |
   | `docs/NAS_REQUISITOS.md` | lo que se pidió armar en el NAS |

4. **Cada vez que terminemos algo importante**, reemplazá en el Proyecto los archivos de `docs/`
   que hayan cambiado (los actualizo yo en tu carpeta). Así el próximo chat arranca al día.
5. Para que Claude pueda leer y escribir tu código, abrí el chat desde la **app de escritorio**
   con la carpeta `C:\Users\02\Documents\agroapp` conectada. Si no, adjuntá los archivos que
   haga falta tocar.

## 2. Instrucciones del proyecto (copiar y pegar)

```
Estoy desarrollando AgroApp (AgTech: insumos, repuestos, maquinaria, ganadería; bot de
Telegram + web + SQLite). Soy principiante: usá la skill /software-development-mentor y
enseñame mientras construimos.

Antes de empezar, leé INICIO_PROYECTO.md, PROJECT_CONTEXT.md y ROADMAP.md de los archivos
del proyecto.

Forma de trabajo:
- Pasos chicos: objetivo → código → ejecutar → probar → corregir → confirmar.
- Decime siempre QUÉ archivo cambia y DÓNDE. Código completo y probado.
- Nunca digas que algo funciona sin haberlo verificado (tests y, si es web, el navegador).
- Decisiones importantes: explicá alternativas y preguntame antes.
- Corré los tests antes de cada commit y proponé el mensaje del commit.
- Si te digo "modo trabajador": hacé bloques grandes y avisame al terminar.

Cuidados:
- Nunca leas, escribas ni muestres el .env (tiene claves). Para ejemplos usá ejemplo_env.txt.
- No abras datos/agroapp.db con editores: se corrompe. Para mirar la base, copiala.
- Antes de pisar un archivo mío, fijate si lo cambié (puedo haberlo editado a mano).
- Al terminar algo importante, actualizá docs/PROJECT_CONTEXT.md, docs/ROADMAP.md y
  docs/INICIO_PROYECTO.md.
- Entorno: Windows, PowerShell, VS Code, Python 3.14, .venv. Archivos con fin de línea CRLF.

Respondé en español (Argentina).
```

## 3. Dónde estamos

**Funciona y se usa con datos reales** (en la PC con Windows):

- **Insumos y repuestos**: stock con historial, subcategorías, stock mínimo, archivar.
  Repuestos asignables a **varias máquinas** (tabla `insumo_maquinas`).
- **Maquinaria**: ficha, horas, services/arreglos, trabajos (ha), vencimientos, contactos,
  **service programado por horas** (varios planes por máquina).
- **Ganadería**: vacunos por caravana, partos (mellizos), tacto, servicio, aborto, sanidad,
  fecha probable de parto.
- **Web**: diseño claro minimalista, menú izquierdo plegable, Inicio con alertas, filtros en
  todas las tablas, exportar a Excel (listado filtrado o todo).
- **Telegram**: comandos con "/" y **lenguaje natural con Gemini** (pide "sí" antes de guardar).
- **Base**: SQLite en `datos/agroapp.db`, migraciones hasta la **versión 5**, backup diario y
  antes de cada migración.
- **Tests**: 80 pasan (`python -m pytest`).
- **Git**: último commit "Repuestos asignables a varias máquinas (tabla insumo_maquinas,
  migración 5)".

**En curso, en otro chat**: armado del NAS según `docs/NAS_REQUISITOS.md`.

## 4. Qué sigue (en este orden)

### A. Volver del NAS
Traer completada la sección **"Qué traer de vuelta"** de `NAS_REQUISITOS.md` (sistema,
Docker, IP, usuario, carpeta, Tailscale, Cloudflare, UPS, backups).

### B. Subir el código a GitHub (repo privado)
- Para bajarlo en el NAS con `git clone` / `git pull`.
- Revisar antes que `.gitignore` deje afuera `.env`, `datos/`, `*.db` y `.venv/`.

### C. Docker
- `Dockerfile` (Python, dependencias, código).
- `docker-compose.yml` con dos servicios: **api** (uvicorn) y **bot** (`bot/bot.py`, que apunta
  a la api por el nombre del servicio).
- Carpeta `datos/` como volumen (`/srv/agroapp/datos`), zona horaria Argentina,
  `restart: unless-stopped`, `.env` copiado a mano.
- Probarlo primero en la PC si se puede.

### D. Mudar la base al NAS (con cuidado)
1. Apagar backend y bot en la PC.
2. Backup manual.
3. Copiar `datos/agroapp.db` al NAS.
4. Verificar la copia (mismo hash y `PRAGMA integrity_check`).
5. Arrancar en el NAS y probar web y bot.
6. **No volver a prender el bot en la PC**: dos bots con el mismo token a la vez chocan.

### E. Login en la web
Obligatorio antes de abrirla desde afuera (aunque sea por Tailscale): usuario y contraseña,
contraseñas guardadas con hash, sesión con cookie.

### F. Bot de WhatsApp
- Meta WhatsApp Cloud API: cuenta de Meta for Developers, app, número de prueba.
- Webhook `POST /whatsapp` publicado con Cloudflare Tunnel (solo esa ruta), con la
  verificación inicial y la **firma de cada mensaje** (secreto de la app).
- Un "cartero" de WhatsApp que reusa `POST /mensaje`: los mismos comandos y el mismo Gemini que
  Telegram.
- Lista de números autorizados. Tests.
- Revisar la documentación vigente de Meta al empezar (cambia seguido).

### G. Backups fuera del NAS
Copia diaria de `datos/backups` a la nube (rclone u otro) y una prueba de restaurar.

### Ideas chicas pendientes (ROADMAP)
- `/historial` por Telegram (mini desafío).
- Pesadas y ganancia de peso.
- Ir anotando lo que falte o moleste al usar la app con datos reales.

## 5. Datos útiles

- **Arrancar** (desde la carpeta `agroapp`, con `.venv` activado):
  - backend: `uvicorn app.main:app --reload`
  - bot: `python bot/bot.py`
- **Web**: http://127.0.0.1:8000/web/
- **Variables del `.env`**: `TELEGRAM_TOKEN`, `TELEGRAM_USUARIOS_AUTORIZADOS`,
  `GEMINI_API_KEY`, `GEMINI_MODEL` (por defecto `gemini-3.5-flash-lite`).
- **Si aparece "Could not import module 'main'"**: se usó el comando viejo. Es
  `uvicorn app.main:app`.
- **Después de cambiar la web**: Ctrl+F5 en el navegador.
