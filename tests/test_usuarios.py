"""Gestión de usuarios (Ajustes > Usuarios), roles y entrar con Google."""
import base64
import json
import sys
import time
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def usuarios(app):
    return sys.modules["app.usuarios.db"]


@pytest.fixture
def cliente_comun(app, cliente, usuarios):
    """Otro navegador, logueado con un usuario SIN rol admin. (cliente = el admin, creado primero)."""
    usuarios.crear_usuario("peon", "", "usuario", "clave-del-peon")
    otro = TestClient(app.app)
    assert otro.post("/login", json={"usuario": "peon", "contrasena": "clave-del-peon"}).status_code == 200
    return otro


def entrar(app, usuario, contrasena):
    navegador = TestClient(app.app)
    respuesta = navegador.post("/login", json={"usuario": usuario, "contrasena": contrasena})
    return navegador, respuesta


# ---------- Roles y permisos ----------

def test_el_primer_usuario_es_admin_y_los_siguientes_no(usuarios, app):
    usuarios.guardar_usuario("primero", "una-clave-larga")
    usuarios.guardar_usuario("segundo", "una-clave-larga")
    roles = {u["nombre"]: u["rol"] for u in usuarios.listar_usuarios()}
    assert roles == {"primero": "admin", "segundo": "usuario"}


def test_yo_dice_el_rol(cliente, cliente_comun):
    assert cliente.get("/yo").json()["rol"] == "admin"
    assert cliente_comun.get("/yo").json()["rol"] == "usuario"


def test_un_usuario_comun_recibe_403_en_la_api_de_usuarios(cliente_comun):
    """No alcanza con esconder el botón: el servidor también lo prohíbe."""
    assert cliente_comun.get("/usuarios").status_code == 403
    assert cliente_comun.post("/usuarios", json={"nombre": "x", "contrasena": "una-clave-larga"}).status_code == 403
    assert cliente_comun.put("/usuarios/1", json={"nombre": "x", "rol": "usuario", "activo": False}).status_code == 403
    assert cliente_comun.post("/usuarios/1/contrasena", json={"contrasena": "una-clave-larga"}).status_code == 403
    # El resto de la app sí la puede usar.
    assert cliente_comun.get("/insumos").status_code == 200


def test_sin_login_la_api_de_usuarios_da_401(cliente_anonimo):
    assert cliente_anonimo.get("/usuarios").status_code == 401


def test_tema_js_se_ve_sin_login_y_ajustes_no(cliente_anonimo):
    """El login también usa el modo oscuro, así que tema.js tiene que estar libre. Ajustes, no."""
    assert cliente_anonimo.get("/web/js/tema.js").status_code == 200
    respuesta = cliente_anonimo.get("/web/ajustes.html", follow_redirects=False)
    assert respuesta.status_code == 303


# ---------- Crear ----------

def test_el_admin_crea_un_usuario_con_contrasena_y_ese_usuario_entra(cliente, app):
    respuesta = cliente.post("/usuarios", json={"nombre": "Juan", "email": " Juan@Gmail.com ", "contrasena": "clave-de-juan"})
    assert respuesta.status_code == 201
    nuevo = respuesta.json()
    assert (nuevo["nombre"], nuevo["email"], nuevo["rol"], nuevo["activo"], nuevo["tiene_contrasena"]) == (
        "Juan", "juan@gmail.com", "usuario", True, True)
    _, login = entrar(app, "juan", "clave-de-juan")
    assert login.status_code == 200


def test_la_lista_nunca_muestra_la_huella_de_la_contrasena(cliente):
    lista = cliente.get("/usuarios").json()
    assert len(lista) == 1
    assert "hash_contrasena" not in lista[0]
    assert "scrypt" not in json.dumps(lista)
    assert lista[0]["ultimo_ingreso"]  # Se anota al entrar.


def test_usuario_solo_google_no_puede_entrar_con_contrasena(cliente, app):
    respuesta = cliente.post("/usuarios", json={"nombre": "maria", "email": "maria@gmail.com"})
    assert respuesta.status_code == 201
    assert respuesta.json()["tiene_contrasena"] is False
    for clave in ("", "cualquier-cosa"):
        _, login = entrar(app, "maria", clave)
        assert login.status_code == 401


@pytest.mark.parametrize("datos, error", [
    ({"nombre": "x"}, "contraseña o un mail"),
    ({"nombre": "x", "contrasena": "corta"}, "al menos 8"),
    ({"nombre": "x", "email": "no-es-un-mail"}, "mail no es válido"),
    ({"nombre": "  ", "contrasena": "una-clave-larga"}, "vacío"),
    ({"nombre": "prueba", "contrasena": "una-clave-larga"}, "ese nombre"),  # El del admin (fixture).
])
def test_crear_con_datos_invalidos_da_400(cliente, datos, error):
    respuesta = cliente.post("/usuarios", json=datos)
    assert respuesta.status_code == 400
    assert error in respuesta.json()["detail"]


def test_no_se_repite_el_mail_aunque_cambien_las_mayusculas(cliente):
    assert cliente.post("/usuarios", json={"nombre": "a", "email": "uno@gmail.com"}).status_code == 201
    respuesta = cliente.post("/usuarios", json={"nombre": "b", "email": "UNO@gmail.com"})
    assert respuesta.status_code == 400
    assert "ese mail" in respuesta.json()["detail"]


# ---------- Editar, desactivar y contraseñas ----------

def test_desactivar_un_usuario_le_cierra_la_sesion(cliente, cliente_comun, usuarios):
    peon = next(u for u in usuarios.listar_usuarios() if u["nombre"] == "peon")
    respuesta = cliente.put(f"/usuarios/{peon['id']}", json={"nombre": "peon", "rol": "usuario", "activo": False})
    assert respuesta.status_code == 200
    assert respuesta.json()["activo"] is False
    assert cliente_comun.get("/insumos").status_code == 401


def test_hacer_admin_a_otro_le_da_acceso(cliente, cliente_comun, usuarios):
    peon = next(u for u in usuarios.listar_usuarios() if u["nombre"] == "peon")
    cliente.put(f"/usuarios/{peon['id']}", json={"nombre": "peon", "rol": "admin", "activo": True})
    assert cliente_comun.get("/usuarios").status_code == 200


def test_no_te_podes_quitar_el_admin_ni_desactivarte(cliente):
    yo = cliente.get("/yo").json()
    for cambio in ({"rol": "usuario", "activo": True}, {"rol": "admin", "activo": False}):
        respuesta = cliente.put(f"/usuarios/{yo['id']}", json={"nombre": yo["usuario"], **cambio})
        assert respuesta.status_code == 409
        assert "vos mismo" in respuesta.json()["detail"]


def test_siempre_queda_al_menos_un_admin_activo(usuarios, app):
    usuarios.guardar_usuario("unico-admin", "una-clave-larga")
    unico = usuarios.listar_usuarios()[0]
    with pytest.raises(usuarios.ReglaUsuarios, match="al menos un admin"):
        usuarios.editar_usuario(unico["id"], "unico-admin", "", "usuario", True, quien_edita_id=None)


def test_sacarle_el_mail_a_un_usuario_solo_google_no_se_permite(cliente):
    nuevo = cliente.post("/usuarios", json={"nombre": "maria", "email": "maria@gmail.com"}).json()
    respuesta = cliente.put(f"/usuarios/{nuevo['id']}", json={"nombre": "maria", "email": "", "rol": "usuario", "activo": True})
    assert respuesta.status_code == 400
    assert "contraseña" in respuesta.json()["detail"]


def test_editar_un_usuario_que_no_existe_da_404(cliente):
    assert cliente.put("/usuarios/999", json={"nombre": "x", "rol": "usuario", "activo": True}).status_code == 404


def test_resetear_la_contrasena_de_otro_le_cierra_las_sesiones(cliente, cliente_comun, usuarios, app):
    peon = next(u for u in usuarios.listar_usuarios() if u["nombre"] == "peon")
    assert cliente.post(f"/usuarios/{peon['id']}/contrasena", json={"contrasena": "clave-nueva-peon"}).status_code == 204
    assert cliente_comun.get("/insumos").status_code == 401
    assert entrar(app, "peon", "clave-del-peon")[1].status_code == 401
    assert entrar(app, "peon", "clave-nueva-peon")[1].status_code == 200


def test_cambiar_tu_propia_contrasena_no_te_saca(cliente):
    yo = cliente.get("/yo").json()
    assert cliente.post(f"/usuarios/{yo['id']}/contrasena", json={"contrasena": "otra-clave-larga"}).status_code == 204
    assert cliente.get("/insumos").status_code == 200


def test_resetear_con_contrasena_corta_da_400(cliente):
    assert cliente.post("/usuarios/1/contrasena", json={"contrasena": "corta"}).status_code == 400


def test_la_consola_crea_admins(app, usuarios, monkeypatch):
    from app.usuarios import crear_usuario
    usuarios.guardar_usuario("primero", "una-clave-larga")
    monkeypatch.setattr("builtins.input", lambda texto: "rescate")
    monkeypatch.setattr(crear_usuario, "getpass", lambda texto: "una-clave-larga")
    crear_usuario.main()
    assert {u["nombre"]: u["rol"] for u in usuarios.listar_usuarios()}["rescate"] == "admin"


# ---------- Entrar con Google ----------

CLIENTE_GOOGLE = "123-prueba.apps.googleusercontent.com"


@pytest.fixture
def google(app, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", CLIENTE_GOOGLE)
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secreto-de-prueba")
    monkeypatch.delenv("GOOGLE_REDIRECT_URI", raising=False)
    return sys.modules["app.usuarios.google"]


@pytest.fixture
def navegador(app):
    """Un navegador nuevo, SIN sesión (ojo: cliente y cliente_anonimo son el mismo objeto)."""
    return TestClient(app.app)


def id_token(**cambios):
    """Arma un id_token como los de Google (encabezado.datos.firma, en base64url)."""
    datos = {"iss": "https://accounts.google.com", "aud": CLIENTE_GOOGLE, "exp": time.time() + 300,
             "email": "facu@gmail.com", "email_verified": True, **cambios}
    parte = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return f"{parte({'alg': 'RS256'})}.{parte(datos)}.firma"


def ir_y_volver(navegador, google, monkeypatch, token=None, **parametros):
    """Simula: botón 'Entrar con Google' -> Google -> vuelta a nuestro callback."""
    salida = navegador.get("/auth/google/inicio", follow_redirects=False)
    state = parse_qs(urlparse(salida.headers["location"]).query)["state"][0]
    monkeypatch.setattr(google, "_pedir_token", lambda code, verificador, uri: {"id_token": token or id_token()})
    return navegador.get(
        "/auth/google/callback", params={"code": "codigo", "state": state, **parametros}, follow_redirects=False
    )


def test_sin_configurar_el_boton_de_google_no_aparece(cliente_anonimo, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    assert cliente_anonimo.get("/auth/google/disponible").json() == {"disponible": False}
    assert cliente_anonimo.get("/auth/google/inicio", follow_redirects=False).status_code == 404


def test_ir_a_google_manda_state_y_pkce(cliente_anonimo, google):
    assert cliente_anonimo.get("/auth/google/disponible").json() == {"disponible": True}
    salida = cliente_anonimo.get("/auth/google/inicio", follow_redirects=False)
    assert salida.status_code == 303
    url = urlparse(salida.headers["location"])
    assert url.netloc == "accounts.google.com"
    parametros = {clave: valor[0] for clave, valor in parse_qs(url.query).items()}
    assert parametros["client_id"] == CLIENTE_GOOGLE
    assert parametros["redirect_uri"] == "http://testserver/auth/google/callback"
    assert parametros["code_challenge_method"] == "S256"
    assert parametros["scope"] == "openid email"
    assert parametros["state"] and parametros["code_challenge"]
    cookie = salida.headers["set-cookie"].lower()
    assert "agroapp_google=" in cookie and "httponly" in cookie and "path=/auth/google" in cookie


def test_la_direccion_de_vuelta_fija_del_nas(cliente_anonimo, google, monkeypatch):
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://agro.grindnode.uk/auth/google/callback")
    salida = cliente_anonimo.get("/auth/google/inicio", follow_redirects=False)
    assert "redirect_uri=https%3A%2F%2Fagro.grindnode.uk%2Fauth%2Fgoogle%2Fcallback" in salida.headers["location"]


def test_mail_de_google_registrado_entra(cliente, navegador, google, monkeypatch):
    cliente.post("/usuarios", json={"nombre": "facu-google", "email": "Facu@gmail.com"})
    vuelta = ir_y_volver(navegador, google, monkeypatch)
    assert vuelta.status_code == 303
    assert vuelta.headers["location"] == "/web/index.html"
    assert navegador.get("/yo").json()["usuario"] == "facu-google"


def test_mail_de_google_no_registrado_no_entra(cliente, navegador, google, monkeypatch):
    vuelta = ir_y_volver(navegador, google, monkeypatch, token=id_token(email="extrano@gmail.com"))
    assert vuelta.headers["location"] == "/web/login.html?error=google-no-autorizado"
    assert navegador.get("/insumos").status_code == 401


def test_mail_de_un_usuario_desactivado_no_entra(cliente, navegador, google, monkeypatch):
    nuevo = cliente.post("/usuarios", json={"nombre": "ex", "email": "facu@gmail.com"}).json()
    cliente.put(f"/usuarios/{nuevo['id']}", json={"nombre": "ex", "email": "facu@gmail.com", "rol": "usuario", "activo": False})
    vuelta = ir_y_volver(navegador, google, monkeypatch)
    assert vuelta.headers["location"] == "/web/login.html?error=google-no-autorizado"


@pytest.mark.parametrize("cambios", [
    {"aud": "otra-app.apps.googleusercontent.com"},
    {"iss": "https://falso.example.com"},
    {"exp": time.time() - 10},
    {"email_verified": False},
])
def test_id_token_trucho_no_entra(cliente, navegador, google, monkeypatch, cambios):
    cliente.post("/usuarios", json={"nombre": "facu-google", "email": "facu@gmail.com"})
    vuelta = ir_y_volver(navegador, google, monkeypatch, token=id_token(**cambios))
    assert vuelta.headers["location"] == "/web/login.html?error=google-fallo"
    assert navegador.get("/insumos").status_code == 401


def test_state_distinto_no_entra(cliente, navegador, google, monkeypatch):
    """Una vuelta de Google que no empezó en ESTE navegador se rechaza (ataque CSRF de login)."""
    cliente.post("/usuarios", json={"nombre": "facu-google", "email": "facu@gmail.com"})
    navegador.get("/auth/google/inicio", follow_redirects=False)
    monkeypatch.setattr(google, "_pedir_token", lambda *a: {"id_token": id_token()})
    vuelta = navegador.get("/auth/google/callback", params={"code": "c", "state": "otro"}, follow_redirects=False)
    assert vuelta.headers["location"] == "/web/login.html?error=google-invalido"
    # Sin la cookie del inicio, tampoco.
    vuelta = TestClient(navegador.app).get("/auth/google/callback", params={"code": "c", "state": "x"}, follow_redirects=False)
    assert vuelta.headers["location"] == "/web/login.html?error=google-invalido"


def test_cancelar_en_google_vuelve_al_login(navegador, google, monkeypatch):
    vuelta = ir_y_volver(navegador, google, monkeypatch, error="access_denied")
    assert vuelta.headers["location"] == "/web/login.html?error=google-cancelado"


# ---------- Migración 13 ----------

def test_migracion_13_deja_admin_a_los_usuarios_que_ya_estaban(tmp_path, monkeypatch):
    import importlib

    from app.nucleo import database
    monkeypatch.setenv("AGROAPP_DB", str(tmp_path / "v12.db"))
    importlib.reload(database)
    todas = database.MIGRACIONES
    monkeypatch.setattr(database, "MIGRACIONES", todas[:12])
    database.crear_tablas()
    with database.conectar() as conexion:
        conexion.execute("INSERT INTO usuarios (nombre, hash_contrasena) VALUES ('facu', 'scrypt$x')")
    monkeypatch.setattr(database, "MIGRACIONES", todas[:13])
    assert database.migraciones_pendientes() == 1
    database.crear_tablas()
    with database.conectar() as conexion:
        fila = conexion.execute("SELECT nombre, email, rol, ultimo_ingreso, hash_contrasena FROM usuarios").fetchone()
    assert tuple(fila) == ("facu", "", "admin", None, "scrypt$x")
