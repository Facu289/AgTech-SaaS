"""Crear un usuario de la web (o cambiarle la contraseña) desde la consola.

Desde la carpeta agroapp, con el .venv activado:
    python -m app.usuarios.crear_usuario

Pide el nombre y la contraseña dos veces (mientras la escribís no se ve: es normal).
Si el usuario ya existe, pregunta si querés cambiarle la contraseña (sirve si te la olvidaste).
"""
from getpass import getpass

from app.nucleo import backup
from app.usuarios import db as usuarios_db


def main():
    backup.preparar_base()  # Por si la base todavía no tiene la tabla de usuarios (migración 8).
    nombre = input("Nombre de usuario: ").strip()
    if usuarios_db.existe_usuario(nombre):
        if input(f"'{nombre}' ya existe. ¿Cambiarle la contraseña? (s/n): ").strip().lower() not in ("s", "si", "sí"):
            print("No se cambió nada.")
            return
    contrasena = getpass(f"Contraseña (mínimo {usuarios_db.LARGO_MINIMO} caracteres): ")
    if getpass("Repetila: ") != contrasena:
        print("❌ Las contraseñas no coinciden. No se guardó nada.")
        return
    try:
        # Por consola se crean admins: es la puerta de emergencia si nadie puede entrar a Ajustes.
        resultado = usuarios_db.guardar_usuario(nombre, contrasena, rol="admin")
    except usuarios_db.DatoInvalido as error:
        print(f"❌ {error}")
        return
    if resultado == "creado":
        print(f"✅ Usuario '{nombre}' creado (admin). Ya podés entrar en la web.")
    else:
        print(f"✅ Contraseña de '{nombre}' cambiada. Se cerraron sus sesiones abiertas.")


if __name__ == "__main__":
    main()
