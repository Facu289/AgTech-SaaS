"""Usuarios de la web y sus sesiones (el login).

Contraseñas: NUNCA se guardan. Se guarda un "hash": una huella que se calcula a partir
de la contraseña y que no se puede dar vuelta. Para revisar una contraseña se calcula
la huella otra vez y se compara con la guardada.

Usamos scrypt (viene con Python, en hashlib): es LENTO a propósito, así probar millones
de contraseñas contra una base robada lleva demasiado tiempo. Cada usuario tiene su
"sal" (bytes al azar que se mezclan con la contraseña): dos usuarios con la misma
contraseña tienen huellas distintas.

Sesiones: al entrar se crea un código al azar (token) que el navegador guarda en una
cookie y manda en cada pedido. En la base se guarda la huella del token (sha256).
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from app.nucleo import database

DIAS_SESION = 30          # Después de esto hay que volver a entrar.
LARGO_MINIMO = 8          # Largo mínimo de la contraseña.
LARGO_MAXIMO_NOMBRE = 50

# Cuánto "cuesta" calcular una huella con scrypt (memoria ~16 MB, unos milisegundos).
# Se guardan junto con la huella: si mañana se suben, las contraseñas viejas siguen andando.
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1


class DatoInvalido(Exception):
    """Nombre de usuario o contraseña que no cumplen las reglas."""


# ---------- Contraseñas ----------

def calcular_hash(contrasena):
    """Devuelve el texto a guardar: "scrypt$N$r$p$sal$huella" (sal y huella en hexadecimal)."""
    sal = secrets.token_bytes(16)
    huella = hashlib.scrypt(contrasena.encode(), salt=sal, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${sal.hex()}${huella.hex()}"


def verificar_contrasena(contrasena, guardado):
    """True si la contraseña corresponde a la huella guardada."""
    try:
        algoritmo, n, r, p, sal, huella = guardado.split("$")
        if algoritmo != "scrypt":
            return False
        calculada = hashlib.scrypt(
            contrasena.encode(), salt=bytes.fromhex(sal), n=int(n), r=int(r), p=int(p), dklen=len(huella) // 2
        )
    except ValueError:
        return False
    # compare_digest tarda lo mismo acierte o no: no da pistas por el tiempo de respuesta.
    return hmac.compare_digest(calculada.hex(), huella)


# Huella de mentira: si el usuario no existe igual calculamos una huella, así la respuesta
# tarda lo mismo y no se puede adivinar qué usuarios existen midiendo el tiempo.
_hash_de_relleno = None


def _relleno():
    global _hash_de_relleno
    _hash_de_relleno = _hash_de_relleno or calcular_hash(secrets.token_hex(8))
    return _hash_de_relleno


# ---------- Usuarios ----------

def validar(nombre, contrasena):
    nombre = (nombre or "").strip()
    if not nombre:
        raise DatoInvalido("El nombre de usuario no puede estar vacío.")
    if len(nombre) > LARGO_MAXIMO_NOMBRE:
        raise DatoInvalido(f"El nombre de usuario puede tener hasta {LARGO_MAXIMO_NOMBRE} letras.")
    if len(contrasena or "") < LARGO_MINIMO:
        raise DatoInvalido(f"La contraseña tiene que tener al menos {LARGO_MINIMO} caracteres.")
    return nombre


def existe_usuario(nombre):
    with database.conectar() as conexion:
        fila = conexion.execute("SELECT 1 FROM usuarios WHERE nombre = ?", ((nombre or "").strip(),)).fetchone()
    return fila is not None


def hay_usuarios():
    with database.conectar() as conexion:
        return conexion.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] > 0


def guardar_usuario(nombre, contrasena):
    """Crea el usuario, o le cambia la contraseña si ya existía.

    Al cambiar la contraseña se cierran todas sus sesiones (por si alguien más la sabía).
    Devuelve "creado" o "actualizado".
    """
    nombre = validar(nombre, contrasena)
    huella = calcular_hash(contrasena)
    with database.conectar() as conexion:
        fila = conexion.execute("SELECT id FROM usuarios WHERE nombre = ?", (nombre,)).fetchone()
        if fila is None:
            conexion.execute("INSERT INTO usuarios (nombre, hash_contrasena) VALUES (?, ?)", (nombre, huella))
            return "creado"
        conexion.execute("UPDATE usuarios SET hash_contrasena = ?, activo = 1 WHERE id = ?", (huella, fila["id"]))
        conexion.execute("DELETE FROM sesiones WHERE usuario_id = ?", (fila["id"],))
        return "actualizado"


def autenticar(nombre, contrasena):
    """Devuelve {"id", "nombre"} si el usuario existe, está activo y la contraseña es correcta; si no, None."""
    with database.conectar() as conexion:
        fila = conexion.execute(
            "SELECT id, nombre, hash_contrasena FROM usuarios WHERE nombre = ? AND activo = 1",
            ((nombre or "").strip(),),
        ).fetchone()
    if fila is None:
        verificar_contrasena(contrasena or "", _relleno())  # Mismo tiempo que si existiera.
        return None
    if not verificar_contrasena(contrasena or "", fila["hash_contrasena"]):
        return None
    return {"id": fila["id"], "nombre": fila["nombre"]}


# ---------- Sesiones ----------

def _huella_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def crear_sesion(usuario_id):
    """Crea una sesión y devuelve el token (el código que va en la cookie)."""
    token = secrets.token_urlsafe(32)  # 32 bytes al azar: imposible de adivinar.
    expira = (datetime.now() + timedelta(days=DIAS_SESION)).strftime("%Y-%m-%d %H:%M:%S")
    with database.conectar() as conexion:
        # De paso, limpiamos las sesiones vencidas.
        conexion.execute("DELETE FROM sesiones WHERE expira_en <= ?", (_ahora(),))
        conexion.execute(
            "INSERT INTO sesiones (hash_token, usuario_id, expira_en) VALUES (?, ?, ?)",
            (_huella_token(token), usuario_id, expira),
        )
    return token


def usuario_de_sesion(token):
    """Devuelve {"id", "nombre"} del dueño de la sesión, o None si no existe, venció o el usuario está inactivo."""
    if not token:
        return None
    with database.conectar() as conexion:
        fila = conexion.execute(
            """
            SELECT u.id, u.nombre FROM sesiones s JOIN usuarios u ON u.id = s.usuario_id
            WHERE s.hash_token = ? AND s.expira_en > ? AND u.activo = 1
            """,
            (_huella_token(token), _ahora()),
        ).fetchone()
    return dict(fila) if fila else None


def cerrar_sesion(token):
    if not token:
        return
    with database.conectar() as conexion:
        conexion.execute("DELETE FROM sesiones WHERE hash_token = ?", (_huella_token(token),))
