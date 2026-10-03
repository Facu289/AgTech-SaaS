"""Backups de la base: uno por día (al iniciar y mientras está prendida) y antes de migrar. También manual."""
import asyncio
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from app.nucleo import database

# Por defecto, datos/backups (al lado de la base). AGROAPP_BACKUPS permite elegir otra carpeta.
CARPETA_BACKUPS = Path(os.getenv("AGROAPP_BACKUPS", database.DB_PATH.parent / "backups"))
CANTIDAD_A_GUARDAR = 30  # Se guardan los 30 backups más nuevos.


def hacer_backup(solo_si_no_hay_de_hoy=False):
    """Copia la base a datos/backups/agroapp_AAAA-MM-DD_HHMMSS.db.

    Devuelve la ruta del backup creado, o None si no se hizo.
    """
    if not database.DB_PATH.exists():
        return None

    CARPETA_BACKUPS.mkdir(parents=True, exist_ok=True)
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


async def backup_diario_continuo(cada_segundos=3600):
    """Mientras el backend está prendido, cada hora se fija si ya hay backup de hoy (si no, lo hace).

    La copia corre en otro hilo (to_thread) para no frenar a la web ni al bot mientras tanto.
    """
    while True:
        await asyncio.sleep(cada_segundos)
        try:
            await asyncio.to_thread(hacer_backup, solo_si_no_hay_de_hoy=True)
        except Exception as error:  # Un backup fallido no tiene que tirar abajo la app.
            print(f"⚠️ No se pudo hacer el backup diario: {error}")


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