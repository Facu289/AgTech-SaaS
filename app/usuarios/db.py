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
import re
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
#
# Roles: "admin" puede crear y editar usuarios (página Ajustes); "usuario" usa la app.
# Reglas que protegen de quedarse afuera: siempre queda al menos un admin activo,
# y nadie se puede quitar el admin ni desactivar a sí mismo.

ROLES = ("admin", "usuario")

# Columnas que se muestran (NUNCA la huella de la contraseña: solo si tiene o no).
COLUMNAS = (
    "id, nombre, email, rol, activo, ultimo_ingreso, creado_en, "
    "hash_contrasena <> '' AS tiene_contrasena"
)

_FORMATO_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UsuarioNoEncontrado(database.NoEncontrado):
    """Se pidió un usuario que no existe."""


class ReglaUsuarios(Exception):
    """Un cambio que dejaría la app sin admin, o que uno se haría a sí mismo."""


def _validar_nombre(nombre):
    nombre = (nombre or "").strip()
    if not nombre:
        raise DatoInvalido("El nombre de usuario no puede estar vacío.")
    if len(nombre) > LARGO_MAXIMO_NOMBRE:
        raise DatoInvalido(f"El nombre de usuario puede tener hasta {LARGO_MAXIMO_NOMBRE} letras.")
    return nombre


def _validar_contrasena(contrasena):
    if len(contrasena or "") < LARGO_MINIMO:
        raise DatoInvalido(f"La contraseña tiene que tener al menos {LARGO_MINIMO} caracteres.")


def normalizar_email(email):
    """" Facu@Gmail.com " -> "facu@gmail.com". Vacío = sin Google."""
    email = (email or "").strip().lower()
    if email and (len(email) > 254 or not _FORMATO_EMAIL.match(email)):
        raise DatoInvalido("El mail no es válido.")
    return email


def _validar_rol(rol):
    if rol not in ROLES:
        raise DatoInvalido("El rol tiene que ser admin o usuario.")
    return rol


def validar(nombre, contrasena):
    nombre = _validar_nombre(nombre)
    _validar_contrasena(contrasena)
    return nombre


def _revisar_repetidos(conexion, nombre, email, sin_contar_id=None):
    """Mensajes claros para nombre o mail repetidos (en vez del error genérico de la base)."""
    otro = conexion.execute(
        "SELECT 1 FROM usuarios WHERE nombre = ? AND id IS NOT ?", (nombre, sin_contar_id)
    ).fetchone()
    if otro:
        raise DatoInvalido("Ya existe un usuario con ese nombre.")
    if email:
        otro = conexion.execute(
            "SELECT 1 FROM usuarios WHERE email = ? COLLATE NOCASE AND id IS NOT ?", (email, sin_contar_id)
        ).fetchone()
        if otro:
            raise DatoInvalido("Ya hay un usuario con ese mail.")


def existe_usuario(nombre):
    with database.conectar() as conexion:
        fila = conexion.execute("SELECT 1 FROM usuarios WHERE nombre = ?", ((nombre or "").strip(),)).fetchone()
    return fila is not None


def hay_usuarios():
    with database.conectar() as conexion:
        return conexion.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] > 0


def _a_dict(fila):
    usuario = dict(fila)
    usuario["activo"] = bool(usuario["activo"])
    usuario["tiene_contrasena"] = bool(usuario["tiene_contrasena"])
    return usuario


def listar_usuarios():
    with database.conectar() as conexion:
        filas = conexion.execute(f"SELECT {COLUMNAS} FROM usuarios ORDER BY activo DESC, nombre").fetchall()
    return [_a_dict(fila) for fila in filas]


def obtener_usuario(usuario_id):
    with database.conectar() as conexion:
        fila = conexion.execute(f"SELECT {COLUMNAS} FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    if fila is None:
        raise UsuarioNoEncontrado("No existe ese usuario.")
    return _a_dict(fila)


def crear_usuario(nombre, email="", rol="usuario", contrasena=None):
    """Crea un usuario desde Ajustes. La contraseña es opcional si va a entrar con Google."""
    nombre = _validar_nombre(nombre)
    email = normalizar_email(email)
    rol = _validar_rol(rol)
    if contrasena:
        _validar_contrasena(contrasena)
    elif not email:
        raise DatoInvalido("Poné una contraseña o un mail de Google (o los dos): si no, no podría entrar.")
    huella = calcular_hash(contrasena) if contrasena else ""
    with database.conectar() as conexion:
        _revisar_repetidos(conexion, nombre, email)
        cursor = conexion.execute(
            "INSERT INTO usuarios (nombre, email, rol, hash_contrasena) VALUES (?, ?, ?, ?)",
            (nombre, email, rol, huella),
        )
    return obtener_usuario(cursor.lastrowid)


def editar_usuario(usuario_id, nombre, email, rol, activo, quien_edita_id):
    """Cambia nombre, mail, rol o si está activo. quien_edita_id = el admin que hace el cambio."""
    actual = obtener_usuario(usuario_id)
    nombre = _validar_nombre(nombre)
    email = normalizar_email(email)
    rol = _validar_rol(rol)
    activo = bool(activo)

    pierde_admin = actual["rol"] == "admin" and actual["activo"] and (rol != "admin" or not activo)
    if usuario_id == quien_edita_id and pierde_admin:
        raise ReglaUsuarios("No podés quitarte el rol de admin ni desactivarte a vos mismo.")
    if not email and not actual["tiene_contrasena"]:
        raise DatoInvalido("Sin mail de Google no podría entrar: primero ponele una contraseña.")

    with database.conectar() as conexion:
        if pierde_admin:
            otros = conexion.execute(
                "SELECT COUNT(*) FROM usuarios WHERE rol = 'admin' AND activo = 1 AND id <> ?", (usuario_id,)
            ).fetchone()[0]
            if otros == 0:
                raise ReglaUsuarios("Tiene que quedar al menos un admin activo.")
        _revisar_repetidos(conexion, nombre, email, sin_contar_id=usuario_id)
        conexion.execute(
            "UPDATE usuarios SET nombre = ?, email = ?, rol = ?, activo = ? WHERE id = ?",
            (nombre, email, rol, int(activo), usuario_id),
        )
        if not activo:
            # Desactivado: se le cierran las sesiones (si tenía la web abierta, lo saca).
            conexion.execute("DELETE FROM sesiones WHERE usuario_id = ?", (usuario_id,))
    return obtener_usuario(usuario_id)


def cambiar_contrasena(usuario_id, contrasena, conservar_token=None):
    """Pone una contraseña nueva y cierra las sesiones de ese usuario.

    conservar_token: si el admin se la cambia a sí mismo, no lo sacamos de la sesión que está usando.
    """
    obtener_usuario(usuario_id)
    _validar_contrasena(contrasena)
    with database.conectar() as conexion:
        conexion.execute("UPDATE usuarios SET hash_contrasena = ? WHERE id = ?", (calcular_hash(contrasena), usuario_id))
        conexion.execute(
            "DELETE FROM sesiones WHERE usuario_id = ? AND hash_token IS NOT ?",
            (usuario_id, _huella_token(conservar_token) if conservar_token else None),
        )


def guardar_usuario(nombre, contrasena, rol=None):
    """Para la consola: crea el usuario, o le cambia la contraseña si ya existía.

    Al cambiar la contraseña se cierran todas sus sesiones (por si alguien más la sabía).
    Un usuario nuevo es admin si se pide, o si es el primero (alguien tiene que poder entrar a Ajustes).
    Devuelve "creado" o "actualizado".
    """
    nombre = validar(nombre, contrasena)
    huella = calcular_hash(contrasena)
    with database.conectar() as conexion:
        fila = conexion.execute("SELECT id FROM usuarios WHERE nombre = ?", (nombre,)).fetchone()
        if fila is None:
            primero = conexion.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0
            rol = _validar_rol(rol or ("admin" if primero else "usuario"))
            conexion.execute(
                "INSERT INTO usuarios (nombre, hash_contrasena, rol) VALUES (?, ?, ?)", (nombre, huella, rol)
            )
            return "creado"
        conexion.execute("UPDATE usuarios SET hash_contrasena = ?, activo = 1 WHERE id = ?", (huella, fila["id"]))
        conexion.execute("DELETE FROM sesiones WHERE usuario_id = ?", (fila["id"],))
        return "actualizado"


def autenticar(nombre, contrasena):
    """Devuelve {"id", "nombre", "rol"} si el usuario existe, está activo y la contraseña es correcta; si no, None."""
    with database.conectar() as conexion:
        fila = conexion.execute(
            "SELECT id, nombre, rol, hash_contrasena FROM usuarios WHERE nombre = ? AND activo = 1",
            ((nombre or "").strip(),),
        ).fetchone()
    if fila is None:
        verificar_contrasena(contrasena or "", _relleno())  # Mismo tiempo que si existiera.
        return None
    if not verificar_contrasena(contrasena or "", fila["hash_contrasena"]):
        return None
    return {"id": fila["id"], "nombre": fila["nombre"], "rol": fila["rol"]}


def usuario_por_email(email):
    """Para entrar con Google: el usuario ACTIVO que tiene ese mail cargado, o None."""
    email = (email or "").strip().lower()
    if not email:
        return None
    with database.conectar() as conexion:
        fila = conexion.execute(
            "SELECT id, nombre, rol FROM usuarios WHERE email = ? COLLATE NOCASE AND activo = 1", (email,)
        ).fetchone()
    return dict(fila) if fila else None


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
        conexion.execute("UPDATE usuarios SET ultimo_ingreso = ? WHERE id = ?", (_ahora(), usuario_id))
    return token


def usuario_de_sesion(token):
    """Devuelve {"id", "nombre", "rol"} del dueño de la sesión, o None si no existe, venció o el usuario está inactivo."""
    if not token:
        return None
    with database.conectar() as conexion:
        fila = conexion.execute(
            """
            SELECT u.id, u.nombre, u.rol FROM sesiones s JOIN usuarios u ON u.id = s.usuario_id
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
