# AgroApp — Contexto del proyecto

> Pegá este archivo (y ROADMAP.md) al empezar un chat nuevo para retomar sin perder contexto.

## Qué es
Aplicación AgTech para gestionar un establecimiento: insumos, repuestos, maquinaria y
ganadería (vacunos), y más adelante telemetría y mapas. Se usa desde **Telegram** (en el
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
  - Backend: `uvicorn main:app --reload`
  - Bot: `python bot.py`
- Web: http://127.0.0.1:8000/web/ (Inicio) · Documentación API: http://127.0.0.1:8000/docs
- Tests: `python -m pytest` (usan una base temporal, nunca tocan agroapp.db)

## Tecnologías
- Python + FastAPI + Pydantic (backend y API)
- SQLite con `sqlite3` y **SQL escrito a mano** (sin ORM). Migraciones con `PRAGMA user_version`.
- Telegram Bot API con `requests` y **long polling** (sin webhooks por ahora)
- Frontend: **HTML + CSS + JavaScript puro** con `fetch()`, servido por FastAPI (`/web`).
  Diseño "claro minimalista": blanco, grises y acento verde #0F9D6E; fuente del sistema
  (funciona sin internet); menú izquierdo plegable. React más adelante.
- openpyxl para exportar a Excel. Gemini (Google) para entender mensajes en lenguaje natural.
- pytest + httpx para tests. `.env` para secretos. Git para versionar.

## Estructura
```
agroapp/
├── .env               ← TELEGRAM_TOKEN, TELEGRAM_USUARIOS_AUTORIZADOS, GEMINI_API_KEY (NO va a Git)
├── ejemplo_env.txt    ← qué variables lleva el .env (sin valores secretos)
├── requirements.txt
├── main.py            ← arma la app: routers, errores → HTTP, /mensaje (reparte comandos), /web
├── opciones.py        ← TODAS las listas de valores (categorías, tipos, unidades...) en un lugar
├── tipos.py           ← tipos Pydantic reutilizables (número "2,5", fecha vacía, opción)
├── utilidades.py      ← texto, números y fechas en formato argentino, búsqueda por nombre
├── database.py        ← conexión, MIGRACIONES y SQL de insumos, movimientos y notas
├── db_maquinaria.py   ← SQL de máquinas, services, trabajos, vencimientos, contactos
├── db_ganaderia.py    ← SQL de animales y eventos
├── insumos.py         ← modelos + endpoints + comandos de Telegram de insumos y notas
├── maquinaria.py      ← modelos + endpoints + comandos de Telegram de maquinaria
├── ganaderia.py       ← modelos + endpoints + comandos de Telegram de animales
├── exportar.py        ← Excel: POST /exportar (lo que se ve) y GET /exportar/completo (todo)
├── lenguaje_natural.py← Gemini traduce texto libre a comandos; confirma con "sí"
├── backup.py          ← backup diario automático (al iniciar), manual, y ANTES de migrar
├── bot.py             ← "cartero": Telegram ↔ backend. Solo usuarios autorizados
├── tests/             ← pytest (API, Telegram y migraciones)
├── static/            ← frontend (ver abajo)
├── backups/           ← copias de la base (ignoradas por Git)
└── agroapp.db         ← base de datos (ignorada por Git, NO abrir en VS Code)
```

### Frontend (`static/`)
- `estilos.css` (variables de color) · `comun.js` (menú plegable, `api()`, formatos, avisos,
  filtros en la URL, refresco automático, `exportarExcel()`) · `comun-maquinaria.js` · `comun-ganaderia.js`
- Páginas: `index.html` **Inicio** (resumen + "requiere atención") · `insumos.html` · `repuestos.html` ·
  `movimientos.html` · `maquinas.html` ·
  `maquina.html?id=` ficha · `vencimientos.html` · `contactos.html` · `animales.html` ·
  `animal.html?id=` ficha. Cada una con su `.js` (insumos y repuestos comparten `insumos.js`).

## Arquitectura
```
Telegram ─► bot.py ─POST /mensaje─► main.py ─► insumos.py / maquinaria.py / ganaderia.py
Navegador ─► /web (static) ─fetch─►   (misma API)          └─► database.py / db_*.py ─► agroapp.db
```
- `bot.py` no tiene lógica de negocio: reenvía el texto a `POST /mensaje`.
- Los `db_*.py` no saben nada de HTTP: lanzan excepciones (`NoEncontrado`, `TieneHistorial`,
  `Archivado`, `StockInsuficiente`, `EventoInvalido`) y `main.py` las traduce a HTTP en UN lugar
  (`@app.exception_handler`).
- La web pide las listas de opciones a `GET /opciones` (no se repiten en JavaScript).
- La web se refresca sola al volver a la pestaña y cada 60 s (así se ve lo cargado por Telegram).

## Base de datos (SQLite)
- `insumos`: id, nombre (UNIQUE NOCASE), categoria, **subcategoria**, unidad, cantidad (>= 0),
  **stock_minimo**, **maquina_id** (repuestos), **archivado**, creado_en
- `movimientos`: insumo_id, tipo (entrada/salida), cantidad (> 0), motivo, fecha
- `notas`: texto, hecha, creada_en
- `maquinas`: nombre (UNIQUE), tipo, marca, modelo, anio, numero_serie, patente, horas_motor,
  horas_trilla (solo cosechadoras), observaciones, archivado
- `planes_service`: maquina_id, nombre, cada_horas, medida (motor/trilla), ultima_horas,
  ultima_fecha, activo. Próximo = ultima_horas + cada_horas; avisa al faltar el 10%.
  Registrar un service con ese plan tildado (o "/service jd - aceite") reinicia el contador.
- `mantenimientos` (service/arreglo: fecha, horas, descripción, costo) · `trabajos` (fecha, tipo,
  hectáreas, lote, cultivo) · `vencimientos` (descripción, tipo, fecha, máquina opcional, resuelto)
  · `contactos` (nombre, rubro, empresa, teléfono, email, notas)
- `animales`: caravana (UNIQUE), categoria, raza, rodeo, fecha_nacimiento, estado_reproductivo
  ('', vacia, prenada), fecha_probable_parto, madre_id, estado (activo/vendido/muerto)
- `eventos_animales`: animal_id, fecha, tipo (parto, aborto, tacto, servicio, sanidad,
  observación), resultado (tacto), crias_machos, crias_hembras, detalle
- Reglas: stock = saldo + historial en la misma transacción; un evento actualiza el animal en la
  misma transacción (parto/aborto → vacía; vaquillona que pare → vaca; tacto preñada → fecha
  probable de parto = la indicada o último servicio + 283 días).
- Se elimina solo lo que no tiene historial; lo demás se **archiva** (o se da de baja).
- **Migraciones**: lista `MIGRACIONES` en database.py. Nunca editar una ya aplicada: agregar otra.
  Antes de migrar se hace un backup automático.

## Comandos del bot
Stock: `/stock [filtro]` · `/repuestos [filtro]` · `/nuevo <nombre> <categoría o tipo> <unidad>` ·
`/entrada` y `/salida <cant> <insumo> - motivo`
Maquinaria: `/maquinas [filtro]` · `/horas <máquina> <horas>` · `/trabajo <máquina> <ha> <tipo> - lote` ·
`/service <máquina> - desc` (si nombra un plan, lo reinicia; "- todo" = todos) · `/arreglo` ·
`/services [máquina]` · `/vencimientos`
Animales: `/animales [filtro]` · `/animal <caravana>` · `/parto <caravana> <m/h...> - detalle` ·
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
- Subcategorías como columna aparte (no como categorías nuevas); repuesto → máquina opcional.
- Ganadería: vacunos, uno por caravana. Gestación 283 días. Alertas a 30 días (`opciones.py`).
- Un archivo por área (insumos / maquinaria / ganadería) en vez de un main.py gigante.
- Filtros de tablas en el navegador (son cientos de filas); el historial de movimientos se filtra
  en el servidor (pueden ser miles).
- Excel: cada listado manda al servidor lo que se ve (con filtros) y el servidor arma el .xlsx.
- Gemini solo traduce a comandos existentes (mismas validaciones) + confirmación antes de escribir.
  El modelo se configura en .env (GEMINI_MODEL) porque Google los renueva seguido.
- Service programado: varios planes por máquina, medidos con horas de motor o de trilla.

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

## Deuda técnica
- FUTURA: la web y la API no tienen login (ok solo en local). Obligatorio antes de producción.
- FUTURA: backups solo en la misma PC.
- MENOR: el formulario de máquina y el de vencimiento están repetidos en dos HTML cada uno.
- MENOR: la búsqueda de insumos/máquinas/animales filtra en Python (ok para cientos).
- MENOR: `insumos.creado_en` en UTC (el resto en hora local).
- MENOR: borrar un evento de un animal no deshace su cambio de estado (se corrige editando).
- MENOR: lo pendiente de confirmar por Telegram vive en memoria (se pierde si se reinicia el backend).
- A TENER EN CUENTA: los mensajes en lenguaje natural (y los nombres de insumos/máquinas/caravanas)
  se envían a Google (Gemini). Los comandos con "/" no salen de la PC.

## Dónde estamos
Fases 1 a 3 hechas, más: rediseño con Inicio y menú plegable, exportar a Excel, service
programado por horas y lenguaje natural por Telegram (Gemini).
**Siguiente**: usarla con datos reales y ajustar; después, ideas de "Futuro" del ROADMAP.
