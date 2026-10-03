"""Login de la web: contraseñas con hash, sesiones con cookie, el portero y el token del bot."""
import sys

import pytest

from conftest import USUARIO_PRUEBA


@pytest.fixture
def usuarios(app):
    return sys.modules["app.usuarios.db"]


def entrar(cliente, usuario="facu", contrasena="una-clave-larga"):
    return cliente.post("/login", json={"usuario": usuario, "contrasena": contrasena})


# ---------- Contraseñas ----------

def test_la_contrasena_se_guarda_como_hash_y_no_como_texto(usuarios):
    huella = usuarios.calcular_hash("una-clave-larga")
    assert "una-clave-larga" not in huella
    assert huella.startswith("scrypt$")
    assert usuarios.verificar_contrasena("una-clave-larga", huella)
    assert not usuarios.verificar_contrasena("otra-clave-larga", huella)
    # Misma contraseña, huella distinta (cada una tiene su "sal").
    assert usuarios.calcular_hash("una-clave-larga") != huella


def test_una_huella_rota_no_deja_entrar(usuarios):
    assert not usuarios.verificar_contrasena("x", "cualquier-cosa")
    assert not usuarios.verificar_contrasena("x", "md5$1$2$3$ab$cd")


def test_contrasena_corta_o_nombre_vacio_no_se_aceptan(usuarios):
    with pytest.raises(usuarios.DatoInvalido, match="al menos 8"):
        usuarios.guardar_usuario("facu", "corta")
    with pytest.raises(usuarios.DatoInvalido, match="vacío"):
        usuarios.guardar_usuario("   ", "una-clave-larga")


# ---------- El portero: sin login no se ve nada ----------

def test_sin_login_la_api_responde_401(cliente_anonimo):
    for ruta in ("/insumos", "/alertas", "/opciones", "/maquinas", "/animales", "/yo", "/openapi.json"):
        assert cliente_anonimo.get(ruta).status_code == 401, ruta
    assert cliente_anonimo.post("/insumos", json={}).status_code == 401
    assert cliente_anonimo.post("/mensaje", json={"texto": "/stock"}).status_code == 401
    assert cliente_anonimo.get("/exportar/completo").status_code == 401


def test_sin_login_las_paginas_van_al_login(cliente_anonimo):
    for ruta in ("/", "/web/", "/web/index.html", "/web/insumos.html", "/web/js/comun.js", "/docs"):
        respuesta = cliente_anonimo.get(ruta, follow_redirects=False)
        assert respuesta.status_code == 303, ruta
        assert respuesta.headers["location"] == "/web/login.html"


def test_la_pagina_de_login_y_sus_archivos_se_ven_sin_login(cliente_anonimo):
    for ruta in ("/web/login.html", "/web/js/login.js", "/web/css/estilos.css"):
        assert cliente_anonimo.get(ruta).status_code == 200, ruta


def test_no_se_puede_colar_una_pagina_con_trucos_en_la_ruta(cliente_anonimo):
    """Las rutas libres son EXACTAS: "../" o barras raras no llegan a las páginas protegidas."""
    for ruta in ("/web/css/%2e%2e/index.html", "/web/css/..%5Cindex.html", "/web//index.html"):
        respuesta = cliente_anonimo.get(ruta, follow_redirects=False)
        assert respuesta.status_code in (303, 401, 404), ruta
        assert "<main" not in respuesta.text, ruta


# ---------- Entrar y salir ----------

def test_entrar_con_la_contrasena_correcta_da_una_cookie_segura(cliente_anonimo, usuarios):
    usuarios.guardar_usuario("Facu", "una-clave-larga")
    respuesta = entrar(cliente_anonimo, "facu")  # El nombre no distingue mayúsculas.
    assert respuesta.status_code == 200
    assert respuesta.json() == {"usuario": "Facu"}
    cookie = respuesta.headers["set-cookie"].lower()
    assert "agroapp_sesion=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "secure" not in cookie  # En la PC es http: con Secure el navegador no la guardaría.
    # Con la cookie ya se puede usar la web y la API.
    assert cliente_anonimo.get("/yo").json() == {"usuario": "Facu"}
    assert cliente_anonimo.get("/insumos").status_code == 200
    assert cliente_anonimo.get("/web/").status_code == 200


def test_cookie_con_secure_cuando_se_pide_https(cliente_anonimo, usuarios, monkeypatch):
    monkeypatch.setenv("AGROAPP_COOKIE_SEGURA", "1")
    usuarios.guardar_usuario("facu", "una-clave-larga")
    assert "secure" in entrar(cliente_anonimo).headers["set-cookie"].lower()


def test_la_sesion_se_guarda_como_huella_en_la_base(cliente_anonimo, usuarios, app):
    usuarios.guardar_usuario("facu", "una-clave-larga")
    token = entrar(cliente_anonimo).cookies["agroapp_sesion"]
    with sys.modules["app.nucleo.database"].conectar() as conexion:
        guardados = [fila[0] for fila in conexion.execute("SELECT hash_token FROM sesiones")]
    assert len(guardados) == 1
    assert token not in guardados


def test_contrasena_incorrecta_o_usuario_inexistente_mismo_mensaje(cliente_anonimo, usuarios):
    usuarios.guardar_usuario("facu", "una-clave-larga")
    mal = entrar(cliente_anonimo, "facu", "otra-clave-larga")
    no_existe = entrar(cliente_anonimo, "pepe", "una-clave-larga")
    assert mal.status_code == no_existe.status_code == 401
    assert mal.json() == no_existe.json() == {"detail": "Usuario o contraseña incorrectos."}
    assert "agroapp_sesion" not in mal.cookies


def test_sin_usuarios_el_login_explica_como_crear_uno(cliente_anonimo):
    respuesta = entrar(cliente_anonimo)
    assert respuesta.status_code == 401
    assert "python -m app.usuarios.crear_usuario" in respuesta.json()["detail"]


def test_muchos_intentos_fallidos_bloquean_un_rato(cliente_anonimo, usuarios):
    usuarios.guardar_usuario("facu", "una-clave-larga")
    for _ in range(5):
        assert entrar(cliente_anonimo, "facu", "mala-mala-mala").status_code == 401
    # Bloqueado: ni con la contraseña correcta.
    respuesta = entrar(cliente_anonimo, "FACU", "una-clave-larga")
    assert respuesta.status_code == 429
    assert "15 minutos" in respuesta.json()["detail"]


def test_salir_cierra_la_sesion(cliente):
    assert cliente.get("/insumos").status_code == 200
    assert cliente.post("/logout").status_code == 204
    assert cliente.get("/insumos").status_code == 401


def test_cambiar_la_contrasena_cierra_las_sesiones_abiertas(cliente, usuarios):
    usuario, _ = USUARIO_PRUEBA
    assert usuarios.guardar_usuario(usuario, "clave-nueva-123") == "actualizado"
    assert cliente.get("/insumos").status_code == 401


def test_una_sesion_vencida_ya_no_sirve(cliente, usuarios, app):
    with sys.modules["app.nucleo.database"].conectar() as conexion:
        conexion.execute("UPDATE sesiones SET expira_en = '2000-01-01 00:00:00'")
    assert cliente.get("/insumos").status_code == 401


def test_un_usuario_desactivado_no_puede_entrar(cliente, usuarios, app):
    with sys.modules["app.nucleo.database"].conectar() as conexion:
        conexion.execute("UPDATE usuarios SET activo = 0")
    assert cliente.get("/insumos").status_code == 401
    assert entrar(cliente, *USUARIO_PRUEBA).status_code == 401


# ---------- El bot de Telegram (entra con su token) ----------

def test_el_bot_entra_con_su_token_solo_a_mensaje(cliente_anonimo, monkeypatch):
    monkeypatch.setenv("AGROAPP_BOT_TOKEN", "token-del-bot-de-prueba")
    cabecera = {"Authorization": "Bearer token-del-bot-de-prueba"}
    respuesta = cliente_anonimo.post("/mensaje", json={"texto": "/ayuda"}, headers=cabecera)
    assert respuesta.status_code == 200
    assert respuesta.json()["respuesta"]
    # El token del bot NO sirve para el resto de la API.
    assert cliente_anonimo.get("/insumos", headers=cabecera).status_code == 401


def test_el_bot_con_token_incorrecto_o_sin_configurar_no_entra(cliente_anonimo, monkeypatch):
    monkeypatch.setenv("AGROAPP_BOT_TOKEN", "token-del-bot-de-prueba")
    for cabecera in ({"Authorization": "Bearer otro"}, {"Authorization": "token-del-bot-de-prueba"}, {}):
        assert cliente_anonimo.post("/mensaje", json={"texto": "/ayuda"}, headers=cabecera).status_code == 401
    # Sin AGROAPP_BOT_TOKEN en el .env, ningún token sirve (ni uno vacío).
    monkeypatch.setenv("AGROAPP_BOT_TOKEN", "")
    respuesta = cliente_anonimo.post("/mensaje", json={"texto": "/ayuda"}, headers={"Authorization": "Bearer "})
    assert respuesta.status_code == 401


# ---------- Comando de consola ----------

def test_comando_crear_usuario(app, usuarios, monkeypatch, capsys):
    from app.usuarios import crear_usuario
    monkeypatch.setattr("builtins.input", lambda texto: "facu")
    monkeypatch.setattr(crear_usuario, "getpass", lambda texto: "una-clave-larga")
    crear_usuario.main()
    assert "creado" in capsys.readouterr().out
    assert usuarios.autenticar("facu", "una-clave-larga")["nombre"] == "facu"


def test_comando_crear_usuario_si_no_coinciden_no_guarda(app, usuarios, monkeypatch, capsys):
    from app.usuarios import crear_usuario
    claves = iter(["una-clave-larga", "otra-clave-larga"])
    monkeypatch.setattr("builtins.input", lambda texto: "facu")
    monkeypatch.setattr(crear_usuario, "getpass", lambda texto: next(claves))
    crear_usuario.main()
    assert "no coinciden" in capsys.readouterr().out
    assert not usuarios.existe_usuario("facu")


# ---------- Migración 8 ----------

def test_migracion_8_agrega_usuarios_y_sesiones_sin_tocar_lo_demas(tmp_path, monkeypatch):
    import importlib

    from app.nucleo import database
    monkeypatch.setenv("AGROAPP_DB", str(tmp_path / "v7.db"))
    importlib.reload(database)
    todas = database.MIGRACIONES
    monkeypatch.setattr(database, "MIGRACIONES", todas[:7])
    database.crear_tablas()
    with database.conectar() as conexion:
        conexion.execute("INSERT INTO maquinas (nombre, tipo) VALUES ('JD', 'tractor')")
    monkeypatch.setattr(database, "MIGRACIONES", todas[:8])
    assert database.migraciones_pendientes() == 1
    database.crear_tablas()
    with database.conectar() as conexion:
        assert conexion.execute("SELECT nombre FROM maquinas").fetchone()[0] == "JD"
        assert conexion.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0
        assert conexion.execute("SELECT COUNT(*) FROM sesiones").fetchone()[0] == 0
        assert conexion.execute("PRAGMA user_version").fetchone()[0] == 8
