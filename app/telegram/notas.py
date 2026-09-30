"""Notas rápidas desde Telegram (/nota, /notas, /hecha): SQL y comandos juntos, porque son pocos."""
from datetime import datetime

from app.nucleo.database import conectar, filas_a_dicts


# ---------- SQL ----------

def agregar_nota(texto):
    """Guarda una nota nueva y devuelve su id."""
    with conectar() as conexion:
        cursor = conexion.execute("INSERT INTO notas (texto) VALUES (?)", (texto,))
        return cursor.lastrowid


def listar_notas_pendientes():
    """Devuelve las notas que todavía no se marcaron como hechas."""
    with conectar() as conexion:
        filas = conexion.execute(
            "SELECT id, texto, creada_en FROM notas WHERE hecha = 0 ORDER BY id"
        ).fetchall()
        return filas_a_dicts(filas)


def marcar_nota_hecha(nota_id):
    """Marca una nota como hecha. Devuelve True si existía y estaba pendiente."""
    with conectar() as conexion:
        cursor = conexion.execute(
            "UPDATE notas SET hecha = 1 WHERE id = ? AND hecha = 0", (nota_id,)
        )
        return cursor.rowcount == 1


# ---------- Comandos ----------

def comando_nota(argumento: str) -> str:
    if not argumento:
        return "Escribí la nota después del comando.\nEjemplo: /nota comprar 20 bolsas de urea"
    nota_id = agregar_nota(argumento)
    return f"📝 Nota #{nota_id} guardada."


def comando_notas(argumento: str) -> str:
    notas = listar_notas_pendientes()
    if not notas:
        return "No hay notas pendientes. 🎉"
    lineas = ["📝 Notas pendientes"]
    for nota in notas:
        fecha = datetime.strptime(nota["creada_en"], "%Y-%m-%d %H:%M:%S")
        lineas.append(f"#{nota['id']} ({fecha:%d/%m %H:%M}) {nota['texto']}")
    lineas.append("\nPara cerrar una: /hecha <número>")
    return "\n".join(lineas)


def comando_hecha(argumento: str) -> str:
    if not argumento.isdigit():
        return "Indicá el número de la nota.\nEjemplo: /hecha 3"
    nota_id = int(argumento)
    if marcar_nota_hecha(nota_id):
        return f"✅ Nota #{nota_id} marcada como hecha."
    return f"No encontré una nota pendiente con el número {nota_id}."
