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
El árbol completo y "¿dónde toco para...?" están en el **README.md** de la raíz. Resumen:
```
agroapp/
├── app/         ← backend. main.py + alertas.py + exportar.py
│   ├── nucleo/    database (conexión, migraciones), backup, opciones, tipos, utilidades
│   ├── insumos/ maquinaria/ ganaderia/   cada una: db.py (SQL) · rutas.py (API) · telegram.py (bot)
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
Navegador ─► /web (web/) ─fetch─► app/main.py ─► <área>/rutas.py
                                   ambos ─► <área>/db.py ─► app/nucleo/database.py ─► datos/agroapp.db
```
- `bot/bot.py` no tiene lógica de negocio: reenvía el texto (y quién escribe) a `POST /mensaje`.
- Los `db.py` no saben nada de HTTP: lanzan excepciones (`NoEncontrado`, `TieneHistorial`,
  `Archivado`, `StockInsuficiente`, `EventoInvalido`) y `app/main.py` las traduce a HTTP en UN lugar.
- Los `telegram.py` reutilizan las reglas de su `rutas.py` (ej: nombres repetidos, stock bajo).
- La web pide las listas de opciones a `GET /opciones` (no se repiten en JavaScript).
- La web se refresca sola al volver a la pestaña y cada 60 s (así se ve lo cargado por Telegram).
- Si la base no está en `datos/` pero hay una vieja en la raíz, la app NO arranca (evita
  crear una base vacía por error) y pide correr `reorganizar.ps1`.

## Base de datos (SQLite)
- `insumos`: id, nombre (UNIQUE NOCASE), categoria, **subcategoria**, unidad, cantidad (>= 0),
  **stock_minimo**, **archivado**, creado_en (la columna vieja `maquina_id` quedó sin uso: siempre NULL)
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
- **Migraciones**: lista `MIGRACIONES` en database.py. Nunca editar una ya aplicada: agregar otra.
  Antes de migrar se hace un backup automático.

## Comandos del bot
Stock: `/stock [filtro]` · `/repuestos [filtro]` · `/nuevo <nombre> <categoría o tipo> <unidad>` ·
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

## Deuda técnica
- FUTURA: la web y la API no tienen login (ok solo en local). Obligatorio antes de producción.
- FUTURA: backups solo en la misma PC.
- MENOR: el formulario de máquina y el de vencimiento están repetidos en dos HTML cada uno.
- Estructura en carpetas desde el 30/09/2026 (antes todo suelto en la raíz).
- MENOR: la búsqueda de insumos/máquinas/animales filtra en Python (ok para cientos).
- MENOR: `insumos.creado_en` en UTC (el resto en hora local).
- MENOR: borrar un evento de un animal no deshace su cambio de estado (se corrige editando).
- MENOR: en las ventanas, Enter = Cancelar (el primer botón del form). Habría que poner
  type="button" al Cancelar o mover Guardar primero.
- MENOR: los grupos no tienen historial de altas/bajas de cabezas: la cantidad se edita a mano.
- MENOR: lo pendiente de confirmar por Telegram vive en memoria (se pierde si se reinicia el backend).
- A TENER EN CUENTA: los mensajes en lenguaje natural (y los nombres de insumos/máquinas/caravanas)
  se envían a Google (Gemini). Los comandos con "/" no salen de la PC.

## Dónde estamos
Fases 1 a 3 hechas, más: rediseño con Inicio y menú plegable, exportar a Excel, service
programado por horas y lenguaje natural por Telegram (Gemini).
También: repuestos asignables a varias máquinas (migración 5) y N° de serie del
monitor en la máquina para licencias de piloto y suscripciones (migración 6), y especies que crea
el usuario + grupos de animales + caravana repetible (migración 7). Se usa con datos reales.
**Siguiente**: NAS (en otro chat) → GitHub → Docker → mudar la base → login web → WhatsApp.
El detalle está en `docs/INICIO_PROYECTO.md`.
