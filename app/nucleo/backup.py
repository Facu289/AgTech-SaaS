"""Backups de la base: automático al iniciar (uno por día) y antes de migrar. También manual."""
import sqlite3
from datetime import datetime

from app.nucleo import database

CARPETA_BACKUPS = database.DB_PATH.parent / "backups"
CANTIDAD_A_GUARDAR = 30  # Se guardan los 30 backups más nuevos.


def hacer_backup(solo_si_no_hay_de_hoy=False):
    """Copia la base a datos/backups/agroapp_AAAA-MM-DD_HHMMSS.db.

    Devuelve la ruta del backup creado, o None si no se hizo.
    """
    if not database.DB_PATH.exists():
        return None

    CARPETA_BACKUPS.mkdir(exist_ok=True)
    ahora = datetime.now()

    if solo_si_no_hay_de_hoy:
        hoy = ahora.strftime("%Y-%m-%d")
        if any(CARPETA_BACKUPS.glob(f"agroapp_{hoy}_*.db")):
            return None

    destino = CARPETA_BACKUPS / f"agroapp_{ahora:%Y-%m-%d_%H%M%S}.db"

    # Usamos la función backup() de SQLite: copia bien aunque la base esté en uso.
    origen = sqlite3.connect(database.DB_PATH)
    copia = sqlite3.connect(destino)
    try:
        origen.backup(copia)
    finally:
        copia.close()
        origen.close()

    borrar_backups_viejos()
    return destino


def preparar_base():
    """Deja la base lista para usar: backup primero y después tablas y migraciones.

    Si hay migraciones pendientes (la estructura de la base va a cambiar),
    SIEMPRE hacemos un backup antes, aunque ya haya uno de hoy.
    La usan el backend al arrancar y los comandos de consola (ej: crear usuario).
    """
    database.verificar_ubicacion()
    if database.migraciones_pendientes():
        ruta = hacer_backup()
        print(f"Backup antes de actualizar la base: {ruta.name if ruta else '(base nueva)'}")
    else:
        hacer_backup(solo_si_no_hay_de_hoy=True)
    database.crear_tablas()


def borrar_backups_viejos():
    """Deja solo los CANTIDAD_A_GUARDAR backups más nuevos."""
    # El nombre empieza con la fecha, así que ordenar por nombre = ordenar por fecha.
    backups = sorted(CARPETA_BACKUPS.glob("agroapp_*.db"))
    for viejo in backups[:-CANTIDAD_A_GUARDAR]:
        viejo.unlink()


if __name__ == "__main__":
    # Backup manual. Desde la carpeta agroapp:   python -m app.nucleo.backup
    ruta = hacer_backup()
    if ruta:
        print(f"✅ Backup creado: {ruta.name}")
    else:
        print("No hay base de datos para copiar.")