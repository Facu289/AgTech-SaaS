"""Mudanza de la base a otra máquina (ej: de la PC al NAS) sin perder ni romper nada.

Son dos pasos, uno en cada máquina (la guía completa está en docs/NAS_INSTALAR.md):

1. En la PC, con el backend y el bot APAGADOS:
       python -m app.nucleo.mudanza preparar
   Hace un backup, arma una copia limpia en datos/mudanza/agroapp.db, la revisa y
   guarda su "huella" (hash SHA-256) en datos/mudanza/agroapp.db.sha256.

2. En el NAS, después de copiar esos dos archivos:
       docker compose run --rm --no-deps api python -m app.nucleo.mudanza verificar /app/datos/agroapp.db
   Revisa que la huella sea la misma (no se dañó al copiarla) y que la base esté sana.

¿Qué es un hash? Un "resumen" de 64 letras y números calculado con TODO el archivo.
Si cambia un solo byte, cambia el hash. Si el hash de la copia es igual al del original,
el archivo llegó exacto.
"""
import hashlib
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

from app.nucleo import backup, database

URL_SALUD = "http://127.0.0.1:8000/salud"


def backend_prendido(url=URL_SALUD):
    """True si hay un backend respondiendo en esta PC (no se puede mudar con la app andando)."""
    try:
        urllib.request.urlopen(url, timeout=2)
        return True
    except urllib.error.HTTPError:
        return True  # Respondió (aunque sea con error): está prendido.
    except (urllib.error.URLError, OSError):
        return False


def calcular_hash(ruta):
    """SHA-256 del archivo, leyéndolo de a pedazos (así no carga todo en memoria)."""
    huella = hashlib.sha256()
    with open(ruta, "rb") as archivo:
        for pedazo in iter(lambda: archivo.read(1024 * 1024), b""):
            huella.update(pedazo)
    return huella.hexdigest()


def revisar_base(ruta):
    """Abre la base SOLO PARA LEER y devuelve un resumen: si está sana, su versión y cuántas filas tiene."""
    conexion = sqlite3.connect(f"{Path(ruta).resolve().as_uri()}?mode=ro", uri=True)
    try:
        integridad = conexion.execute("PRAGMA integrity_check").fetchone()[0]
        relaciones_rotas = conexion.execute("PRAGMA foreign_key_check").fetchall()
        version = conexion.execute("PRAGMA user_version").fetchone()[0]
        tablas = [
            fila[0] for fila in conexion.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        # El nombre de la tabla sale de la propia base (sqlite_master), no de afuera.
        filas = {tabla: conexion.execute(f'SELECT COUNT(*) FROM "{tabla}"').fetchone()[0] for tabla in tablas}
    finally:
        conexion.close()
    return {
        "sana": integridad == "ok" and not relaciones_rotas,
        "integridad": integridad,
        "relaciones_rotas": len(relaciones_rotas),
        "version": version,
        "filas": filas,
    }


def mostrar_resumen(resumen):
    print(f"  integrity_check: {resumen['integridad']}")
    print(f"  relaciones rotas (foreign_key_check): {resumen['relaciones_rotas']}")
    print(f"  versión de la base (migraciones): {resumen['version']}")
    print("  filas por tabla:")
    for tabla, cantidad in resumen["filas"].items():
        print(f"    {tabla:<22} {cantidad}")


def preparar(carpeta_salida=None):
    """Paso 1 (en la PC). Devuelve la ruta de la copia, o None si no se pudo."""
    if backend_prendido():
        print("⛔ El backend está prendido. Apagalo (Ctrl+C en su terminal) y apagá también el bot.")
        return None
    if not database.DB_PATH.exists():
        print(f"⛔ No encuentro la base en {database.DB_PATH}.")
        return None

    print(f"Base: {database.DB_PATH}")
    ruta_backup = backup.hacer_backup()
    print(f"✅ Backup de seguridad: {ruta_backup}")

    carpeta = Path(carpeta_salida or database.DB_PATH.parent / "mudanza")
    carpeta.mkdir(parents=True, exist_ok=True)
    copia = carpeta / "agroapp.db"
    copia.unlink(missing_ok=True)  # Si quedó una de una mudanza anterior, la reemplazamos.

    # Igual que el backup: la función backup() de SQLite deja una copia completa y consistente.
    origen = sqlite3.connect(database.DB_PATH)
    destino = sqlite3.connect(copia)
    try:
        origen.backup(destino)
    finally:
        destino.close()
        origen.close()

    resumen = revisar_base(copia)
    mostrar_resumen(resumen)
    if not resumen["sana"]:
        print("⛔ La copia NO está sana. No la mudes: avisá antes de seguir.")
        return None

    huella = calcular_hash(copia)
    # Formato de "sha256sum" de Linux (con fin de línea LF): en el NAS se puede revisar con sha256sum -c.
    archivo_hash = copia.with_name(copia.name + ".sha256")
    archivo_hash.write_text(f"{huella}  {copia.name}\n", encoding="utf-8", newline="\n")

    print(f"✅ Copia lista: {copia}")
    print(f"✅ Huella (SHA-256): {huella}")
    print("Guardá esta salida: en el NAS, 'verificar' tiene que mostrar los mismos números.")
    print("⚠️ Desde ahora NO vuelvas a prender el bot en la PC (dos bots con el mismo token chocan).")
    return copia


def verificar(ruta):
    """Paso 2 (en el NAS). Devuelve True si la base llegó exacta y está sana."""
    ruta = Path(ruta)
    if not ruta.exists():
        print(f"⛔ No existe {ruta}.")
        return False

    todo_bien = True
    archivo_hash = ruta.with_name(ruta.name + ".sha256")
    huella = calcular_hash(ruta)
    print(f"Huella (SHA-256): {huella}")
    if archivo_hash.exists():
        esperada = archivo_hash.read_text(encoding="utf-8").split()[0]
        if huella == esperada:
            print("✅ La huella coincide con la de la PC: el archivo llegó exacto.")
        else:
            print(f"⛔ La huella NO coincide (esperada {esperada}). Volvé a copiar el archivo.")
            todo_bien = False
    else:
        print(f"⚠️ No encontré {archivo_hash.name}: compará la huella a mano con la que mostró la PC.")

    resumen = revisar_base(ruta)
    mostrar_resumen(resumen)
    if not resumen["sana"]:
        print("⛔ La base NO está sana.")
        todo_bien = False
    if resumen["version"] > len(database.MIGRACIONES):
        print("⛔ La base es más nueva que este código: actualizalo (git pull) y reconstruí la imagen.")
        todo_bien = False

    print("✅ Todo bien: ya se puede arrancar la app." if todo_bien else "⛔ No arranques la app todavía.")
    return todo_bien


USO = """Uso:
  python -m app.nucleo.mudanza preparar             (en la PC, con backend y bot apagados)
  python -m app.nucleo.mudanza verificar <archivo>  (en el NAS, después de copiar)"""


def main(argumentos):
    if argumentos[:1] == ["preparar"] and len(argumentos) == 1:
        return 0 if preparar() else 1
    if argumentos[:1] == ["verificar"] and len(argumentos) == 2:
        return 0 if verificar(argumentos[1]) else 1
    print(USO)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
