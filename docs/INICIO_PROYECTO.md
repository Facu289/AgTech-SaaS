# AgroApp — Cómo seguir en un Proyecto nuevo

> Resumen para retomar AgroApp desde cero en un **Proyecto** de Claude, sin depender de chats
> anteriores. Estado al **02/10/2026** (noche).

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
   | `docs/NAS_INSTALAR.md` | paso a paso para instalar en el NAS y mudar la base |

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

- **Insumos, químicos y repuestos**: tres páginas (y tres hojas en el Excel completo), stock
  con historial, subcategorías, stock mínimo, archivar. Químicos = agroquímicos (se define en
  `CATEGORIAS_QUIMICOS` de `app/nucleo/opciones.py`); en Telegram, `/quimicos`.
  Repuestos asignables a **varias máquinas** (tabla `insumo_maquinas`).
  **N° de serie del monitor** en la máquina: lo muestran sus licencias y suscripciones
  (nuevo tipo de vencimiento "Suscripción / app", también para apps sin máquina).
- **Maquinaria**: ficha, horas, services/arreglos, trabajos (ha), vencimientos, contactos,
  **service programado por horas** (varios planes por máquina).
- **Ganadería**: **especies que creás vos** (página Especies: vacuno, ovino, porcino, gallina,
  llama...) con sus categorías y días de gestación; animales por caravana (se puede repetir,
  la app pregunta) o **en grupo con cantidad**; partos, tacto, servicio, aborto, sanidad,
  fecha probable de parto. Página **Crías**: resumen de partos y crías por especie (también `/crias`).
- **Web**: diseño claro minimalista, menú izquierdo plegable, Inicio con alertas, filtros en
  todas las tablas, exportar a Excel (listado filtrado o todo).
- **Login** (rama `claude/login`, falta mergear a main): usuario y contraseña, sesión con cookie,
  botón Salir abajo del menú. Toda la web y la API piden login; el bot entra con su token.
  Usuarios: `python -m app.usuarios.crear_usuario` (crea o cambia la contraseña).
- **Lotes en mapa** (rama `claude/lotes`, sale de `claude/project-thread-pfy3gt`; falta el OK para commit):
  página Lotes con foto satelital, dibujar el lote, hectáreas automáticas o a mano, editar la forma,
  campañas y cultivo por lote (primera y segunda) pintando el mapa, ficha de cada lote (rinde, producción,
  trabajos de maquinaria), página Cultivos (colores y campañas) y el mapa en Inicio. Migraciones 9 y 10.
  Ya está en main y en el NAS (el NAS ahora sigue la rama main).
- **Importar/exportar lotes** (rama `claude/lotes-kmz`, falta el OK para commit): traer lotes de KMZ, KML o
  GeoJSON con vista previa, y bajarlos en KML para Google Earth u otra app.
- **Órdenes de trabajo + campo en los lotes** (rama `claude/ordenes`, sale de main; falta el OK para commit):
  órdenes como la planilla de pulverización, advertencia de stock, descuento al realizar, registro por lote
  ("1 al 12" se desarma), impresión. Lotes con campo. Migraciones 11 y 12.
- **Inicio y barra lateral nuevos** (en main): mapa general, última orden, última actividad, accesos rápidos;
  menú por grupos con Agricultura primero.
- **WhatsApp**: hecho y en main (`app/whatsapp/rutas.py`). Falta ponerlo en marcha en el NAS (ver F).
- **Ajustes** (rama `claude/usuarios`, sale de main; migración 13; falta commit/OK para mergear):
  - **Usuarios** (solo admins): crear desde la web, editar, rol admin / usuario, desactivar (le cierra la
    sesión), poner contraseña nueva. Siempre queda un admin; nadie se quita el admin a sí mismo.
  - **Entrar con Google**: botón en el login. Entra SOLO quien tenga su mail cargado en un usuario activo.
    Hace falta crear el cliente OAuth en Google Cloud (pasos en la sección E) y las variables `GOOGLE_*`.
  - **Modo oscuro**: Claro / Oscuro / Automático, se guarda en cada celular o PC (`web/js/tema.js`).
- **Telegram**: comandos con "/" y **lenguaje natural con Gemini** (pide "sí" antes de guardar).
- **Base**: SQLite en `datos/agroapp.db`, migraciones hasta la **versión 12** en main (la **13**, usuarios con mail y rol, está en `claude/usuarios`), backup diario y
  antes de cada migración.
- **Tests**: 221 pasan (`python -m pytest`) con lo del NAS, Lotes, importar KMZ, órdenes, campo, WhatsApp y el Inicio.
- **Preparado para el NAS** (rama `claude/project-thread-pfy3gt`, sale de `claude/login`):
  `Dockerfile`, `docker-compose.yml` (api + bot), `GET /salud` con healthcheck, backup diario
  aunque la app no se reinicie, rutas y zona horaria desde el `.env` y el script de mudanza
  `python -m app.nucleo.mudanza`. **Docker no se probó en la PC** (no tiene Docker): se prueba en el NAS.
- **Git**: Químicos (`claude/project-thread-kcdnm3`) y Crías (`claude/project-thread-nx62se`) están
  combinadas en la rama `claude/login` junto con el login. **Falta el OK para mergear a main.**

**En curso, en otro chat**: armado del NAS según `docs/NAS_REQUISITOS.md`.

## 4. Qué sigue (en este orden)

### A. Volver del NAS
Traer completada la sección **"Qué traer de vuelta"** de `NAS_REQUISITOS.md` (sistema,
Docker, IP, usuario, carpeta, Tailscale, Cloudflare, UPS, backups).

### B. GitHub ✅
Ya está en `Facu289/AgTech-SaaS` (confirmá en GitHub que sea **Private**). `.gitignore` revisado:
deja afuera `.env` (y `.env.*`), `datos/`, `*.db` (y sus `-journal`/`-wal`/`-shm`) y `.venv/`.
En la historia de Git no hay ningún `.env` ni base. En el NAS se baja con una deploy key
(ver `NAS_INSTALAR.md`).

### C. Docker ✅ (falta probarlo en el NAS)
- `Dockerfile` (Python, dependencias, código).
- `docker-compose.yml` con dos servicios: **api** (uvicorn) y **bot** (`bot/bot.py`, que apunta
  a la api por el nombre del servicio).
- Carpeta `datos/` como volumen (`/srv/agroapp/datos`), zona horaria Argentina,
  `restart: unless-stopped`, `.env` copiado a mano.
- En la PC no hay Docker: se prueba en el NAS con `docker compose config` y `docker compose build`.

### D. Mudar la base al NAS (con cuidado) — script listo, paso a paso en `NAS_INSTALAR.md`
1. Apagar backend y bot en la PC.
2. Backup manual.
3. Copiar `datos/agroapp.db` al NAS.
4. Verificar la copia (mismo hash y `PRAGMA integrity_check`).
   (Los pasos 2 a 4 los hace `python -m app.nucleo.mudanza preparar` en la PC y `verificar` en el NAS).
5. Arrancar en el NAS y probar web y bot.
6. **No volver a prender el bot en la PC**: dos bots con el mismo token a la vez chocan.

### E. Login en la web ✅ (en main) · Ajustes, Google y modo oscuro ✅ (rama `claude/usuarios`)
Al publicarla con HTTPS: `AGROAPP_COOKIE_SEGURA=1` (o uvicorn con `--proxy-headers`).

**Entrar con Google — crear el cliente OAuth** (una sola vez, en https://console.cloud.google.com):
1. Crear un proyecto (ej. "AgroApp").
2. *APIs y servicios > Pantalla de consentimiento de OAuth*: tipo **Externo**, nombre "AgroApp", tu mail
   de soporte. Alcances: solo `openid` y `email`. Mientras esté "En prueba", agregá en *Usuarios de prueba*
   los mails que van a entrar (o publicala: con solo `openid`/`email` no pide verificación de Google).
3. *APIs y servicios > Credenciales > Crear credenciales > ID de cliente de OAuth*, tipo **Aplicación web**.
   *URI de redireccionamiento autorizados* (las dos):
   - `https://agro.grindnode.uk/auth/google/callback`
   - `http://127.0.0.1:8000/auth/google/callback` (para probar en la PC)
4. Copiar el **ID de cliente** y el **secreto** al `.env` (PC y NAS): `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`.
   En el NAS además: `GOOGLE_REDIRECT_URI=https://agro.grindnode.uk/auth/google/callback`.
5. En Ajustes > Usuarios, cargarle el mail de Google a cada usuario que vaya a entrar así.

### F. Bot de WhatsApp — código ✅, falta ponerlo en marcha
Hecho: `GET /whatsapp` (verificación) y `POST /whatsapp` (firma X-Hub-Signature-256 con el App
Secret), mismos comandos, Gemini y "sí" que Telegram, números autorizados, tests.
Cuenta de Meta lista (WABA 2291926221567276, Phone number ID 1390060194181902) y Cloudflare Tunnel
andando en `https://agro.grindnode.uk`.
Falta, en orden:
1. Poner las 5 variables `WHATSAPP_...` (ver `ejemplo_env.txt`) en el `.env` del NAS, a mano con
   `nano` (NO copiar el `.env` de la PC entero: pisa el bloque Docker/NAS).
2. En el NAS: `git pull && docker compose up -d --build`.
3. En Meta: webhook `https://agro.grindnode.uk/whatsapp`, el mismo verify token del `.env`,
   suscribir el campo "messages". Probar con `/ayuda` desde el celu.
4. Telegram y WhatsApp conviven unas semanas; después se apaga el servicio `bot` (Telegram).
5. Seguridad: que el túnel publique SOLO `/whatsapp` (hoy publica toda la app).

### G. Backups fuera del NAS
Copia diaria de `datos/backups` a la nube (rclone u otro) y una prueba de restaurar.

### Ideas chicas pendientes (ROADMAP)
- `/historial` por Telegram (mini desafío).
- Pesadas y ganancia de peso.
- Grupos: altas y bajas de cabezas con historial.
- Ir anotando lo que falte o moleste al usar la app con datos reales.

## 5. Datos útiles

- **Arrancar** (desde la carpeta `agroapp`, con `.venv` activado):
  - backend: `uvicorn app.main:app --reload`
  - bot: `python bot/bot.py`
- **Web**: http://127.0.0.1:8000/web/
- **En el NAS**: `docker compose up -d --build`, `docker compose ps`, `docker compose logs -f`.
  Variables extra del `.env` solo para Docker: `AGROAPP_CARPETA_DATOS`, `AGROAPP_ZONA_HORARIA`,
  `AGROAPP_PUERTO`, `AGROAPP_UID`, `AGROAPP_GID` (ver `ejemplo_env.txt`).
- **Variables del `.env`**: `TELEGRAM_TOKEN`, `TELEGRAM_USUARIOS_AUTORIZADOS`,
  `GEMINI_API_KEY`, `GEMINI_MODEL` (por defecto `gemini-3.5-flash-lite`),
  `AGROAPP_BOT_TOKEN` (el bot entra a la API con esto) y `AGROAPP_COOKIE_SEGURA` (1 con HTTPS).
- **Crear usuario de la web / cambiar contraseña**: desde **Ajustes > Usuarios** (admins), o por consola
  `python -m app.usuarios.crear_usuario` (crea admins: sirve de "llave de emergencia").
- **Entrar con Google**: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` y, en el NAS, `GOOGLE_REDIRECT_URI`.
- **Si aparece "Could not import module 'main'"**: se usó el comando viejo. Es
  `uvicorn app.main:app`.
- **Después de cambiar la web**: Ctrl+F5 en el navegador.
