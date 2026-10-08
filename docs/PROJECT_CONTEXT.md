# AgroApp — Contexto del proyecto

> Pegá este archivo (y ROADMAP.md) al empezar un chat nuevo para retomar sin perder contexto.

## Qué es
Aplicación AgTech para gestionar un establecimiento: insumos, repuestos, maquinaria y
ganadería (cualquier especie: vacunos, ovinos, porcinos, aves...), y más adelante telemetría y mapas. Se usa desde **Telegram** (en el
campo) y desde una **web** (carga detallada en la oficina). Las dos usan la MISMA API y la
MISMA base: lo que se carga en una se ve en la otra.

## Cómo trabajamos
- Soy estudiante con conocimientos básicos: quiero **aprender mientras construimos**.
- Método: pequeño objetivo → código → ejecutar → probar → corregir → confirmar → siguiente.
- Un paso a la vez. Nada de complejidad innecesaria.
- Indicar siempre **qué archivo crear/modificar y dónde**. Código completo y probado.
- No asumir que algo funciona sin probarlo. Si hay un error, diagnosticarlo antes de seguir.
- Decisiones importantes: explicar alternativas y preguntarme antes.
- Mentor: usar la skill `/software-development-mentor`.
- Commit de Git al terminar cada paso. Correr los tests antes de cada commit.

## Entorno
- Windows, PowerShell, VS Code, Python 3.14, entorno virtual `.venv`.
- Carpeta del proyecto: `C:\Users\02\Documents\agroapp`
- Se ejecuta con **dos terminales**:
  - Backend: `uvicorn app.main:app --reload`
  - Bot: `python bot/bot.py`
- Web: http://127.0.0.1:8000/web/ (Inicio) · Documentación API: http://127.0.0.1:8000/docs
- Tests: `python -m pytest` (usan una base temporal, nunca tocan datos/agroapp.db)
- Backup manual: `python -m app.nucleo.backup`
- Mudar la base a otra máquina: `python -m app.nucleo.mudanza preparar` / `verificar <archivo>`
- NAS (Docker): `docker compose up -d --build` · guía completa en `docs/NAS_INSTALAR.md`
- Crear usuario de la web (o cambiarle la contraseña): Ajustes > Usuarios (admins) o
  `python -m app.usuarios.crear_usuario` (por consola crea admins)

## Tecnologías
- Python + FastAPI + Pydantic (backend y API)
- SQLite con `sqlite3` y **SQL escrito a mano** (sin ORM). Migraciones con `PRAGMA user_version`.
- Telegram Bot API con `requests` y **long polling** (sin webhooks por ahora)
- Frontend: **HTML + CSS + JavaScript puro** con `fetch()`, servido por FastAPI (`/web`).
  Diseño "claro minimalista": blanco, grises y acento verde #0F9D6E; fuente del sistema
  (funciona sin internet); menú izquierdo plegable. React más adelante.
  **Modo oscuro**: `web/js/tema.js` (en el `<head>` de cada página, antes del CSS) pone
  `data-tema="oscuro"` en `<html>`; en `estilos.css` solo se redefinen las VARIABLES. No escribir colores
  fijos fuera de `:root` (si no, no cambian en oscuro). La hoja de la orden queda blanca (es "papel").
- **Mapa de lotes**: Leaflet 1.9.4 + Leaflet-Geoman 2.20.2 (dibujar/editar polígonos) desde el CDN
  unpkg con `integrity` (huella SHA-384); fondo satelital Esri World Imagery (sin clave). Necesita internet.
- openpyxl para exportar a Excel. Gemini (Google) para entender mensajes en lenguaje natural.
- pytest + httpx para tests. `.env` para secretos. Git para versionar.
- Docker + Docker Compose para el NAS: una imagen (`Dockerfile`, Python 3.14-slim) y dos servicios
  (`docker-compose.yml`: **api** y **bot**). Versiones de librerías fijas (`==`) en requirements.txt.

## Estructura
El árbol completo y "¿dónde toco para...?" están en el **README.md** de la raíz. Resumen:
```
agroapp/
├── app/         ← backend. main.py + alertas.py + exportar.py + actividad.py ("última actividad" del Inicio)
│   ├── nucleo/    database (conexión, migraciones), backup, opciones, tipos, utilidades
│   ├── insumos/ maquinaria/ ganaderia/   cada una: db.py (SQL) · rutas.py (API) · telegram.py (bot)
│   ├── lotes/     db.py · rutas.py · geometria.py (validar el polígono y calcular hectáreas). También cultivos,
│   │              campañas y cultivo por lote. importar.py: leer KMZ/KML/GeoJSON y armar KML. Sin Telegram todavía
│   ├── ordenes/   órdenes de trabajo: db.py (descuento de stock) · rutas.py (desarmar "1 al 12", registro por lote)
│   ├── usuarios/  login: db.py (hash, sesiones, usuarios y reglas) · rutas.py (/login, /logout, /yo y el portero)
│   │              gestion.py (/usuarios, solo admin) · google.py (/auth/google/...) · crear_usuario.py
│   └── telegram/  comandos.py (reparte mensajes) · lenguaje_natural.py (Gemini) · notas.py
├── bot/bot.py   ← cartero Telegram ↔ backend
├── web/         ← páginas .html · css/estilos.css · js/ (comun.js + uno por página)
├── tests/  datos/ (base + backups, fuera de Git)  docs/
```
Imports siempre absolutos desde la raíz: `from app.insumos import db as insumos_db`.
Cada carpeta de `app/` tiene un `__init__.py` (así Python la trata como "paquete").

## Arquitectura
```
Telegram ─► bot/bot.py ─POST /mensaje─► app/main.py ─► app/telegram/comandos.py ─► <área>/telegram.py
WhatsApp ─► Meta ─POST /whatsapp (webhook)─► app/whatsapp/rutas.py ─► app/telegram/comandos.py (el mismo)
Navegador ─► /web (web/) ─fetch─► app/main.py ─► <área>/rutas.py
                                   ambos ─► <área>/db.py ─► app/nucleo/database.py ─► datos/agroapp.db
```
- `bot/bot.py` no tiene lógica de negocio: reenvía el texto (y quién escribe) a `POST /mensaje`.
- **Login**: un middleware en `main.py` (el "portero", `usuarios/rutas.py: revisar_pedido`) revisa
  CADA pedido. Sin cookie de sesión válida: las páginas van a `/web/login.html` (303) y la API
  responde 401 (la web, en `comun.js`, manda al login). Libres solo: `/login`, `/logout`,
  `login.html`, `login.js`, `tema.js`, `estilos.css` y `/auth/google/...` (rutas EXACTAS, para que "../"
  no cuele nada). **Roles**: `admin` gestiona usuarios (`/usuarios` → 403 si no es admin, lo controla el
  servidor con la dependencia `solo_admin`); `usuario` usa todo lo demás.
- **Entrar con Google** (`usuarios/google.py`): OAuth "authorization code" con `state` y PKCE, sin librerías
  nuevas (`requests`). `state` + verificador en una cookie HttpOnly de 10 min (path `/auth/google`). Se canjea
  el code directo con Google y se revisa el id_token (aud, iss, exp, email_verified). Entra SOLO si el mail es
  de un usuario activo; si no, vuelve a `login.html?error=...`.
  El bot manda `Authorization: Bearer <AGROAPP_BOT_TOKEN>` y con eso solo puede usar `POST /mensaje`.
- **WhatsApp** (`app/whatsapp/rutas.py`): Meta AVISA cada mensaje con un POST (webhook), así que el
  cartero vive dentro del backend (no hay un programa aparte como bot/bot.py). `/whatsapp` está en
  `RUTAS_LIBRES`: su seguridad es la firma `X-Hub-Signature-256` (HMAC-SHA256 del cuerpo crudo con
  `WHATSAPP_APP_SECRET`); sin firma válida, 403. `GET /whatsapp` es la verificación inicial de Meta
  (`WHATSAPP_VERIFY_TOKEN`). Responde 200 enseguida y atiende el mensaje de fondo (BackgroundTasks):
  número autorizado (`WHATSAPP_USUARIOS_AUTORIZADOS`) → `generar_respuesta` (lo pendiente de "sí" se
  guarda como `"whatsapp:<número>"`) → respuesta por la Graph API (`WHATSAPP_GRAPH_VERSION`, v26.0).
  Números argentinos: se comparan normalizados (549… / +54 9 … / 351… → 54XXXXXXXXXX); si Meta rechaza
  el número con 9 (error 131030), reintenta sin el 9. Ignora estados; a lo que no es texto contesta amable.
  Mensajes repetidos por Meta (mismo id) se atienden una vez.
- Los `db.py` no saben nada de HTTP: lanzan excepciones (`NoEncontrado`, `TieneHistorial`,
  `Archivado`, `StockInsuficiente`, `EventoInvalido`) y `app/main.py` las traduce a HTTP en UN lugar.
- Los `telegram.py` reutilizan las reglas de su `rutas.py` (ej: nombres repetidos, stock bajo).
- La web pide las listas de opciones a `GET /opciones` (no se repiten en JavaScript).
- La web se refresca sola al volver a la pestaña y cada 60 s (así se ve lo cargado por Telegram).
- **Rutas y zona horaria desde variables**: `AGROAPP_DB` (base) y `AGROAPP_BACKUPS` (carpeta de
  backups), opcionales: en la PC no se ponen. `database.py` lee el `.env` apenas se importa (antes
  `DB_PATH` se calculaba sin haberlo leído). En Docker las pone `docker-compose.yml`, y el `.env` del
  NAS solo agrega `AGROAPP_CARPETA_DATOS`, `AGROAPP_ZONA_HORARIA`, `AGROAPP_PUERTO`, `AGROAPP_UID/GID`.
- **Backup diario con la app prendida**: además del de arranque, una tarea de fondo (lifespan en
  `main.py` → `backup.backup_diario_continuo`) revisa cada hora si ya hay backup de hoy. En el NAS
  el backend queda prendido semanas y si no, no habría backups nuevos.
- `GET /salud`: libre de login (está en `RUTAS_LIBRES`), prueba la base y responde `{"estado": "ok"}`
  o 503. La usa el healthcheck de Docker; el bot arranca recién cuando la api está "healthy".
- Si la base no está en `datos/` pero hay una vieja en la raíz, la app NO arranca (evita
  crear una base vacía por error) y pide correr `reorganizar.ps1`.

## Base de datos (SQLite)
- `insumos`: id, nombre (UNIQUE NOCASE), categoria, **subcategoria**, unidad, cantidad (>= 0),
  **stock_minimo**, **archivado**, creado_en (la columna vieja `maquina_id` quedó sin uso: siempre NULL)
  La web los muestra en tres páginas según la categoría (no hay columna nueva): **Repuestos**
  (repuesto), **Químicos** (las de `CATEGORIAS_QUIMICOS` en `opciones.py`, hoy agroquímico) e
  **Insumos** (el resto). La API devuelve `hoja` ("insumos", "quimicos" o "repuestos").
- `insumo_maquinas`: insumo_id, maquina_id (PK de ambos). Tabla intermedia "muchos a muchos":
  un repuesto sirve para varias máquinas y una máquina tiene varios repuestos (migración 5).
  La API recibe `maquinas: [ids]` (todavía acepta `maquina_id`) y devuelve `maquinas: [{id, nombre}]`.
- `movimientos`: insumo_id, tipo (entrada/salida), cantidad (> 0), motivo, fecha
- `notas`: texto, hecha, creada_en
- `maquinas`: nombre (UNIQUE), tipo, marca, modelo, anio, numero_serie, serie_monitor, patente, horas_motor,
  horas_trilla (solo cosechadoras), observaciones, archivado.
  `serie_monitor` (migración 6) es el N° de serie del monitor GPS / piloto: vive en la máquina
  (se carga una vez) y las licencias y suscripciones de esa máquina lo muestran.
- `planes_service`: maquina_id, nombre, cada_horas, medida (motor/trilla), ultima_horas,
  ultima_fecha, activo. Próximo = ultima_horas + cada_horas; avisa al faltar el 10%.
  Registrar un service con ese plan tildado (o "/service jd - aceite") reinicia el contador.
- `mantenimientos` (service/arreglo: fecha, horas, descripción, costo) · `trabajos` (fecha, tipo,
  hectáreas, lote, cultivo) · `vencimientos` (descripción, tipo, fecha, máquina opcional, resuelto;
  tipos licencia y suscripción/app muestran el monitor de la máquina)
  · `contactos` (nombre, rubro, empresa, teléfono, email, notas)
- `especies` (migración 7): nombre (UNIQUE), dias_gestacion (vacío = sin preñez, ej. aves).
  Las crea el usuario en la web (página Especies). Viene cargada "Vacuno" (283 días).
- `categorias_animal`: especie_id, nombre, sexo (hembra / macho / ''). Cada especie tiene las suyas.
- `animales`: caravana (se PUEDE repetir: la API pide confirmar con `confirmar_repetida`),
  categoria_id (la categoría ya dice la especie), es_grupo + cantidad (ej: "Galpón 1", 120 gallinas;
  un animal suelto siempre cuenta 1), raza, rodeo, fecha_nacimiento, estado_reproductivo
  ('', vacia, prenada), fecha_probable_parto, madre_id (hembra de la misma especie), estado
  (activo/vendido/muerto). La API devuelve además especie, categoria (nombre), sexo y
  `reproductiva` (= hembra, suelta y de especie con gestación: la única que tiene tacto/parto).
- `eventos_animales`: animal_id, fecha, tipo (parto, aborto, tacto, servicio, sanidad,
  observación), resultado (tacto), crias_machos, crias_hembras, detalle
- Reglas: stock = saldo + historial en la misma transacción; un evento actualiza el animal en la
  misma transacción (parto/aborto → vacía; vaquillona que pare → vaca; tacto preñada → fecha
  probable de parto = la indicada o último servicio + días de gestación de la especie).
  Parto, aborto, tacto y servicio solo para animales `reproductiva`; sanidad y observación para todos.
- Migración 7 reconstruyó `animales` (para sacar el UNIQUE de la caravana). Durante cada migración
  las foreign keys se apagan y al final se revisan con `PRAGMA foreign_key_check`.
- Se elimina solo lo que no tiene historial; lo demás se **archiva** (o se da de baja).
- `usuarios` (migración 8): nombre (UNIQUE NOCASE), hash_contrasena ("scrypt$N$r$p$sal$huella"),
  activo. `sesiones`: hash_token (sha256 del token de la cookie, nunca el token), usuario_id,
  expira_en (30 días). Cambiar la contraseña cierra las sesiones de ese usuario.
  Migración 13: `email` (vacío = sin Google; único entre los que lo tienen), `rol` ('admin'/'usuario'; los
  que había pasaron a admin), `ultimo_ingreso`. `hash_contrasena` vacío = solo entra con Google.
  Reglas: siempre queda un admin activo; nadie se quita el admin ni se desactiva a sí mismo; desactivar
  cierra sus sesiones.
- `lotes` (migración 9; la 12 la reconstruyó): campo (establecimiento, opcional: "LM", "SR Oeste"), nombre,
  UNIQUE (campo, nombre) sin mayúsculas: el "1" puede repetirse en cada campo. geometria (polígono GeoJSON como TEXTO, puede ser NULL),
  hectareas (las del dibujo, o escritas a mano), observaciones, archivado, creado_en, actualizado_en.
  La API devuelve además `hectareas_calculadas` (las del dibujo) para mostrar si se cargaron a mano.
  Con cultivos cargados no se elimina: se archiva.
- `cultivos` (migración 10): nombre (UNIQUE NOCASE), color "#RRGGBB" (pinta el mapa). Vienen 8 cargados.
- `campanias`: nombre ("2026/27", UNIQUE NOCASE). Orden: de la más nueva a la más vieja (por nombre).
- `lote_cultivos`: lote_id, campania_id, cultivo_id, ciclo (primera/segunda), variedad, fecha_siembra,
  fecha_cosecha, hectareas (vacío = todo el lote), rinde (qq/ha), observaciones. UNIQUE (lote, campaña, ciclo):
  un lote tiene un cultivo de primera y uno de segunda por campaña (ej: trigo → soja 2ª).
  Cultivos y campañas usados en algún lote no se eliminan.
  Hectáreas = área geodésica con el radio de la Tierra en la latitud del lote (elipsoide WGS84):
  la misma cuenta en `app/lotes/geometria.py` y en `web/js/lotes.js` (si cambia una, cambiar la otra).
- `ordenes_trabajo` (migración 11): numero (texto libre, solo para identificar: "1-033"), campania_id, campo,
  tarea (`TAREAS_ORDEN` en opciones.py), maquina, operarios (texto), fecha_emision, fecha_realizacion, estado_lote,
  cultivo, caldo_ha, tancadas, descripcion, estado (pendiente / realizada / anulada).
  `orden_lotes`: lote (TEXTO como en la planilla: "31+32", "1 al 12") + hectareas.
  `orden_productos`: insumo_id + cantidad_total (lo que sale del stock). La dosis/ha NO se guarda: = total / ha de la orden.
  `movimientos.orden_id`: qué orden hizo cada salida (o devolución) de stock.
- **Migraciones**: lista `MIGRACIONES` en database.py. Nunca editar una ya aplicada: agregar otra.
  Antes de migrar se hace un backup automático.

## Comandos del bot
Stock: `/stock [filtro]` · `/quimicos [filtro]` · `/repuestos [filtro]` · `/nuevo <nombre> <categoría o tipo> <unidad>` ·
`/entrada` y `/salida <cant> <insumo> - motivo`
Maquinaria: `/maquinas [filtro]` · `/horas <máquina> <horas>` · `/trabajo <máquina> <ha> <tipo> - lote` ·
`/service <máquina> - desc` (si nombra un plan, lo reinicia; "- todo" = todos) · `/arreglo` ·
`/services [máquina]` · `/vencimientos`
Animales: `/animales [filtro]` · `/animal <caravana>` · `/crias [especie]` (resumen del año) · `/parto <caravana> <m/h...> - detalle` ·
`/tacto <caravana> preñada|vacía [fecha]` · `/servicio <caravana> - toro` · `/aborto <caravana>`
Otros: `/alertas` · `/nota` · `/notas` · `/hecha <n>` · `/ayuda`
**Lenguaje natural**: cualquier mensaje sin "/" lo interpreta Gemini y lo traduce a estos
comandos. Si cambia datos, el bot muestra lo que entendió y espera "sí" (10 min). Si solo
consulta, responde directo. La IA nunca escribe en la base: solo propone comandos.
- Números en formato argentino (`1.500` / `2,5`). Búsqueda sin tildes ni mayúsculas; si hay
  varias coincidencias pregunta. Caravanas: coincidencia EXACTA (sugiere, no adivina).
- Mensajes de más de 4000 caracteres se cortan con aviso.

## Decisiones tomadas
- Polling en lugar de webhook · `requests` en lugar de python-telegram-bot · SQL puro sin ORM.
- Stock = saldo guardado + historial de movimientos (transacción).
- Frontend en HTML/JS puro antes que React. Telegram = campo; Web = oficina.
- La creación de insumos es siempre explícita (`/nuevo` o la web), para evitar duplicados.
- Insumos / Químicos / Repuestos: se separan por categoría (sin migración). Cambiar qué es
  "químico" = editar `CATEGORIAS_QUIMICOS` en `opciones.py`.
- Subcategorías como columna aparte (no como categorías nuevas); repuesto → máquina opcional.
- Ganadería: especies y categorías en la BASE (las crea el usuario), no en `opciones.py`.
  Caravana repetible con confirmación; en Telegram, si se repite, se pone la especie antes
  (`/tacto ovino 12 preñada`). Grupos con cantidad para aves u otros manejados en lote.
  "Vaquillona que pare → vaca" queda solo para Vacuno. Alertas a 30 días (`opciones.py`).
- Un archivo por área (insumos / maquinaria / ganadería) en vez de un main.py gigante.
- Filtros de tablas en el navegador (son cientos de filas); el historial de movimientos se filtra
  en el servidor (pueden ser miles).
- Excel: cada listado manda al servidor lo que se ve (con filtros) y el servidor arma el .xlsx.
- Gemini solo traduce a comandos existentes (mismas validaciones) + confirmación antes de escribir.
  El modelo se configura en .env (GEMINI_MODEL) porque Google los renueva seguido.
- Service programado: varios planes por máquina, medidos con horas de motor o de trilla.
- Login: sesión en la base + cookie (no JWT): se puede cerrar desde el servidor y es simple.
  Hash con scrypt de la librería estándar (sin dependencias nuevas). Cookie HttpOnly, SameSite=Lax,
  Secure con HTTPS (o `AGROAPP_COOKIE_SEGURA=1` detrás de un proxy). 5 intentos fallidos → 15 min
  de bloqueo para ese usuario. No hay "registrarse": los usuarios los crea un admin (Ajustes) o la consola.
- Google: no se crean cuentas solas (Google dice QUIÉN es; la app decide si PUEDE entrar). Sin librerías
  nuevas. El id_token no se valida con la firma porque llega directo de Google por HTTPS a cambio del secreto.
- Modo oscuro guardado en cada dispositivo (localStorage), no en la base: es una preferencia de pantalla.
  Por defecto "Claro" (se ve como siempre hasta que lo cambiás).
- NAS con Docker Compose (no instalar Python en el NAS). Una sola imagen para api y bot; la base y
  los backups en un volumen (`/srv/agroapp/datos` → `/app/datos`), nunca dentro de la imagen.
  Un solo proceso de uvicorn (SQLite y lo pendiente de "sí" viven en memoria). Contenedores con el
  usuario del NAS (uid/gid), no root. Zona horaria por `TZ` (la imagen trae tzdata).
- Mudanza de la base: copia con la función backup() de SQLite + SHA-256 (formato de `sha256sum`) +
  `integrity_check` y `foreign_key_check`, abriendo la copia solo para leer. Se niega si el backend
  de la PC responde en /salud.

- Lotes: polígono en GeoJSON guardado como texto en SQLite (sin SpatiaLite ni PostGIS: con decenas de
  lotes no hace falta). Hectáreas calculadas por el servidor si vienen vacías; la web manda vacío cuando no
  tocaste el número propuesto, así siguen "automáticas" al editar la forma. Polígonos que se cruzan sobre
  sí mismos: los frena Geoman en la web (el servidor no lo revisa).

- Campañas por nombre ("2026/27") y no por fechas: la campaña agrícola cruza dos años y la fina y la gruesa
  se superponen. La campaña que se mira se recuerda en el navegador (localStorage): Inicio y Lotes muestran la
  misma. Mapa: relleno = color del cultivo de primera; borde punteado = el de segunda.
- Web de lotes: `web/js/comun-lotes.js` tiene lo compartido (mapa satelital, colores, leyenda y las ventanas de
  campaña y de cultivo, armadas con JavaScript para no repetir el HTML en cada página). Páginas: Lotes (mapa
  completo, dibujar), lote.html?id= (ficha: cultivos por campaña, rinde, producción en t y trabajos de
  maquinaria del lote, buscados por nombre), Cultivos (cultivos con color y campañas) y el mapa en Inicio.

- Importar lotes de otra app: KMZ, KML (Google Earth y apps de campo) y GeoJSON. La web manda el archivo
  como base64 dentro de un JSON (así no hace falta la librería python-multipart). Dos pasos: `POST
  /lotes/importar/leer` = vista previa SIN guardar (marca los nombres que ya existen) y `POST /lotes/importar`
  = guarda los elegidos (uno existente solo cambia su forma, y respeta sus ha a mano). Un Placemark con varios
  polígonos da varios lotes ("Nombre (1)", "(2)"); los puntos se ignoran; una línea cerrada se toma como borde.
  Exportar: `GET /exportar/lotes-kml?campania_id=` (KML pintado con el color del cultivo).
  Shapefile (.shp) NO: necesita una librería y leer el sistema de coordenadas (.prj).

- Órdenes de trabajo: se cargan a mano ANTES de aplicar (no tocan el stock). Si no alcanza el stock, se guarda
  igual con una ADVERTENCIA. Al marcarla REALIZADA salen del stock todos los productos en una transacción (si a
  uno no le alcanza, no sale ninguno). "Volver a pendiente" devuelve el stock con ENTRADAS (el historial queda).
  Solo se edita pendiente; se elimina solo si nunca movió stock (si no, se anula). El agua no es del stock.
- Registro por lote: la fila de lotes de la orden se desarma ("31+32" → 31 y 32; "1 al 12" → 1..12) y cada uno
  se busca en el mapa por campo de la orden + nombre ("Lote 5" = "5"). Se calcula al mostrar (no se guarda el
  vínculo): si un lote se carga después, se vincula solo. Cantidad del lote = dosis/ha de la orden × ha del lote
  (las del mapa). Sin campo en la orden, solo vincula si hay UN lote con ese nombre.
- La orden se imprime con la forma de la planilla (la "Vista de impresión" al pie es lo único que sale al
  imprimir; A4 horizontal).

- Inicio (tablero): números principales, mapa general (campaña elegida), accesos rápidos, última orden de
  trabajo, "última actividad" y "requiere atención" (máximo 6; lo demás en cada sección). "Última actividad"
  (`GET /actividad`) junta órdenes, movimientos de stock hechos a mano, trabajos y services, eventos de animales
  y cultivos de lotes, ordenados por cuándo se cargaron. Cuando exista el módulo Actividades, se suma ahí.
- Barra lateral por grupos: Inicio · Agricultura (Lotes, Órdenes, Cultivos y campañas) · Stock · Maquinaria ·
  Ganadería · Agenda (Contactos). Abajo: Descargar todo (Excel), usuario y Salir. Se arma en `MENU` (comun.js).
- `/alertas` trae `ordenes_pendientes` (con los productos que faltan): contador del menú, "requiere atención"
  (las que no tienen stock) y `/alertas` de Telegram.

## Lecciones aprendidas (errores que ya nos pasaron)
- No abrir `agroapp.db` en VS Code: se corrompe.
- `.venv\.gitignore` contiene `*`: no moverlo a la raíz.
- Verificar que los archivos quedaron guardados/actualizados (`Select-String`).
- `NameError` = falta import · `ModuleNotFoundError` = falta archivo ·
  `AttributeError` = el archivo no tiene esa función (desactualizado).
- La web no se refrescaba sola: "no se registró" era que la página mostraba datos viejos.
- En Pydantic, un campo opcional con límite (ge=0) tiene que tener el límite en el tipo de
  adentro; si no, un campo vacío da error 500. Los tests lo detectaron.
- Un campo vacío de un formulario llega como "" (texto vacío), no como null.
- En las ventanas (dialog) el primer botón es "Cancelar": apretar Enter cierra sin guardar.
- StaticFiles normaliza las rutas ("/web/css/../index.html" → index.html): por eso la lista de
  rutas libres del login es EXACTA y no "todo lo que empiece con /web/css/". Hay un test.
- Una sombra (box-shadow) de un menú escondido con translateX(-100%) asoma igual: ponerla solo abierto.
- `leer_numero("0.375")` daba 375 (tomaba el punto como de miles). Ahora, con 0 adelante el punto es decimal.
  En una dosis es grave: 0,375 l/ha no puede volverse 375. La web tiene la misma regla en `leerNumero` (comun.js).
- El backend de la PC corre con --reload sobre la misma carpeta en la que se programa: apenas se guarda una
  migración nueva, se aplica a la base de la PC (con backup antes). Por eso una migración, una vez escrita, no se
  cambia: si hace falta otra cosa, va otra migración. Para probar a mano, usar una base temporal (AGROAPP_DB).
- Leaflet mide el mapa al arrancar: si después cambia de tamaño, quedan franjas grises. Se arregla con
  un ResizeObserver que llama a `mapa.invalidateSize()`. Y el contenedor del mapa necesita
  `position: relative; z-index: 0` para que sus capas no tapen el menú del celular.

## Deuda técnica
- MENOR: el servidor no revisa si un polígono se cruza sobre sí mismo ni si dos lotes se superponen.
- MENOR: la página Lotes necesita internet (Leaflet y Geoman por CDN, fotos de Esri). Si un día molesta,
  se pueden copiar Leaflet y Geoman a web/ (las fotos siempre necesitan internet).
- MENOR: los lotes no tienen comando de Telegram. (El Excel completo ya trae Lotes y Cultivos por lote).
- MENOR: el XML de un KML se lee con xml.etree (la librería estándar). Python ya trae freno contra archivos
  "bomba" de entidades, y el KMZ tiene límite de 50 MB descomprimido; si algún día se abre a desconocidos,
  usar defusedxml.
- MENOR: los trabajos de maquinaria se unen al lote por el NOMBRE escrito (texto libre), no por un id. Si se
  renombra un lote, sus trabajos viejos dejan de aparecer en la ficha.
- MENOR: el bloqueo por intentos fallidos vive en memoria (se reinicia con el backend) y es por
  usuario, no por IP. Suficiente con pocos usuarios.
- MENOR: el link "Descargar todo (Excel)" con la sesión vencida muestra el error 401 en JSON
  (no va al login, porque es un link y no un fetch).
- FUTURA: detrás de Cloudflare / HTTPS, uvicorn necesita `--proxy-headers` (o AGROAPP_COOKIE_SEGURA=1)
  para que la cookie salga con Secure.
- FUTURA: backups solo en la misma máquina (en el NAS, falta la copia a la nube).
- MENOR: el bot no tiene healthcheck propio (no tiene HTTP): si se cuelga sin cerrarse, Docker no se
  entera. Se ve con `docker compose logs bot`.
- MENOR: Dockerfile y docker-compose.yml no se pudieron probar en la PC (no tiene Docker): se
  prueban en el NAS con `docker compose config` y `build` (ver NAS_INSTALAR.md).
- MENOR: el formulario de máquina y el de vencimiento están repetidos en dos HTML cada uno.
- Estructura en carpetas desde el 30/09/2026 (antes todo suelto en la raíz).
- MENOR: la búsqueda de insumos/máquinas/animales filtra en Python (ok para cientos).
- MENOR: `insumos.creado_en` en UTC (el resto en hora local).
- MENOR: borrar un evento de un animal no deshace su cambio de estado (se corrige editando).
- MENOR: en las ventanas, Enter = Cancelar (el primer botón del form). Arreglado en Ajustes con
  type="button" en el Cancelar; falta en las demás páginas (mismo cambio, una línea por ventana).
- MENOR: en el menú del celular, con Ajustes abajo, la lista de secciones tiene que scrollear para ver Ganadería.
- MENOR: los grupos no tienen historial de altas/bajas de cabezas: la cantidad se edita a mano.
- MENOR: lo pendiente de confirmar por Telegram vive en memoria (se pierde si se reinicia el backend).
- IMPORTANTE: el Cloudflare Tunnel publica toda la app, no solo `/whatsapp` (la protege el login).
  Restringirlo a `/whatsapp` o sumar Cloudflare Access + `AGROAPP_COOKIE_SEGURA=1`.
- FUTURA: WhatsApp no puede escribir primero (ej. alertas a la mañana) si pasaron 24 h sin mensajes
  del usuario: hace falta una plantilla aprobada por Meta. Hoy el bot solo contesta.
- MENOR: la carpeta `app/telegram/` ahora la usa también WhatsApp: renombrarla (ej. `app/bot/`) cuando
  se apague Telegram.
- A TENER EN CUENTA: los mensajes en lenguaje natural (y los nombres de insumos/máquinas/caravanas)
  se envían a Google (Gemini). Los comandos con "/" no salen de la PC.

## Dónde estamos
Fases 1 a 3 hechas, más: rediseño con Inicio y menú plegable, exportar a Excel, service
programado por horas y lenguaje natural por Telegram (Gemini).
También: repuestos asignables a varias máquinas (migración 5) y N° de serie del
monitor en la máquina para licencias de piloto y suscripciones (migración 6), y especies que crea
el usuario + grupos de animales + caravana repetible (migración 7). Se usa con datos reales.
Login web hecho (migración 8) en la rama `claude/login`, junto con Químicos y Crías: falta mergear a main.
Preparado para el NAS (rama `claude/project-thread-pfy3gt`): Docker, /salud, backup continuo, rutas por .env y script
de mudanza. Falta probar Docker en el NAS.
Lotes en mapa (rama `claude/lotes`, migraciones 9 y 10): página Lotes con satélite, dibujar/editar/borrar
polígonos, hectáreas automáticas o a mano, cultivos con color, campañas, cultivo por lote (primera y segunda),
ficha del lote y mapa en Inicio.
Bot de WhatsApp hecho (webhook `/whatsapp`, mismos comandos que Telegram): falta ponerlo en marcha en el NAS.
Ajustes (rama `claude/usuarios`, migración 13): gestión de usuarios para admins, entrar con Google y modo oscuro.
**Siguiente**: WhatsApp en el NAS (variables, webhook en Meta) → migrar de Telegram a WhatsApp →
cerrar el túnel a solo `/whatsapp`.
El detalle está en `docs/INICIO_PROYECTO.md`.
