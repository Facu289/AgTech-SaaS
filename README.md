# AgroApp

Gestión de un campo: insumos y repuestos, maquinaria y ganadería.
Se usa desde **Telegram** (en el campo) y desde la **web** (en la oficina).

## Cómo se arranca

Desde la carpeta `agroapp`, con el entorno virtual activado (`.venv\Scripts\Activate.ps1`),
en **dos terminales**:

| Qué | Comando |
|---|---|
| Backend (API + web) | `uvicorn app.main:app --reload` |
| Bot de Telegram | `python bot/bot.py` |

- Web: http://127.0.0.1:8000/web/
- Documentación de la API: http://127.0.0.1:8000/docs

Otros comandos:

| Qué | Comando |
|---|---|
| Tests | `python -m pytest` |
| Backup manual | `python -m app.nucleo.backup` |
| Instalar dependencias | `pip install -r requirements.txt` |

## Estructura

```
agroapp/
├── app/                  ← el backend (Python)
│   ├── main.py             arma la app: rutas, errores → HTTP, sirve la web
│   ├── alertas.py          lo que requiere atención (lo usan la web y el bot)
│   ├── exportar.py         Excel
│   ├── nucleo/             lo que usa todo el sistema
│   │   ├── database.py       conexión y migraciones
│   │   ├── backup.py         copias de seguridad
│   │   ├── opciones.py       listas de valores (categorías, tipos, unidades...)
│   │   ├── tipos.py          tipos de datos para validar (número "2,5", fecha vacía...)
│   │   └── utilidades.py     texto, números y fechas en formato argentino
│   ├── insumos/            ┐
│   ├── maquinaria/         │ cada área tiene:  db.py (SQL) · rutas.py (API) · telegram.py (bot)
│   ├── ganaderia/          ┘
│   └── telegram/           el cerebro del bot
│       ├── comandos.py       reparte cada mensaje al comando que corresponde
│       ├── lenguaje_natural.py  Gemini: texto libre → comandos (con confirmación)
│       └── notas.py          /nota, /notas, /hecha
├── bot/bot.py            ← el "cartero": Telegram ↔ backend
├── web/                  ← páginas (.html); estilos en css/, código en js/
├── tests/                ← pruebas automáticas (pytest)
├── datos/                ← agroapp.db y backups/ (NO van a Git)
├── docs/                 ← PROJECT_CONTEXT.md (contexto) y ROADMAP.md
├── .env                  ← claves (NO va a Git). Ver ejemplo_env.txt
└── requirements.txt
```

**¿Dónde toco para...?**
- Agregar una categoría, tipo o unidad → `app/nucleo/opciones.py`
- Agregar una especie o categoría de animal → desde la web, página **Especies** (están en la base)
- Cambiar colores de la web → variables al principio de `web/css/estilos.css`
- Un comando nuevo de Telegram → el `telegram.py` del área + `COMANDOS` en `app/telegram/comandos.py`
- Una columna nueva en la base → una migración nueva al final de `MIGRACIONES` en `app/nucleo/database.py`
