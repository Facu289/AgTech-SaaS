import sqlite3
from datetime import datetime

from database import DB_PATH

CARPETA_BACKUPS = DB_PATH.parent / "backups"
CANTIDAD_A_GUARDAR = 30  # Se guardan los 30 backups más nuevos.


def hacer_backup(solo_si_no_hay_de_hoy=False):
    """Copia la base a backups/agroapp_AAAA-MM-DD_HHMMSS.db.

    Devuelve la ruta del backup creado, o None si no se hizo.
    """
    if not DB_PATH.exists():
        return None

    CARPETA_BACKUPS.mkdir(exist_ok=True)
    ahora = datetime.now()

    if solo_si_no_hay_de_hoy:
        hoy = ahora.strftime("%Y-%m-%d")
        if any(CARPETA_BACKUPS.glob(f"agroapp_{hoy}_*.db")):
            return None

    destino = CARPETA_BACKUPS / f"agroapp_{ahora:%Y-%m-%d_%H%M%S}.db"

    # Usamos la función backup() de SQLite: copia bien aunque la base esté en uso.
    origen = sqlite3.connect(DB_PATH)
    copia = sqlite3.connect(destino)
    try:
        origen.backup(copia)
    finally:
        copia.close()
        origen.close()

    borrar_backups_viejos()
    return destino


def borrar_backups_viejos():
    """Deja solo los CANTIDAD_A_GUARDAR backups más nuevos."""
    # El nombre empieza con la fecha, así que ordenar por nombre = ordenar por fecha.
    backups = sorted(CARPETA_BACKUPS.glob("agroapp_*.db"))
    for viejo in backups[:-CANTIDAD_A_GUARDAR]:
        viejo.unlink()


if __name__ == "__main__":
    # Se ejecuta con: python backup.py
    ruta = hacer_backup()
    if ruta:
        print(f"✅ Backup creado: {ruta.name}")
    else:
        print("No hay base de datos para copiar.")