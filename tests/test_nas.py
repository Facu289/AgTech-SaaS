"""Lo necesario para correr en el NAS: /salud, rutas desde variables, backup continuo y mudanza."""
import asyncio
import importlib
import sqlite3
import sys

import pytest


def test_salud_responde_sin_login(cliente_anonimo):
    # Docker la consulta sin cookie: si pidiera login, el contenedor figuraría "enfermo".
    respuesta = cliente_anonimo.get("/salud")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}


def test_salud_avisa_si_la_base_no_responde(cliente_anonimo, app, monkeypatch):
    database = sys.modules["app.nucleo.database"]

    def base_rota():
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(database, "conectar", base_rota)
    assert cliente_anonimo.get("/salud").status_code == 503


def test_la_base_y_los_backups_salen_de_las_variables(app, tmp_path):
    database = sys.modules["app.nucleo.database"]
    backup = sys.modules["app.nucleo.backup"]
    assert database.DB_PATH == tmp_path / "test.db"
    assert backup.CARPETA_BACKUPS == tmp_path / "backups"
    ruta = backup.hacer_backup()
    assert ruta.parent == tmp_path / "backups"


def test_el_backup_continuo_hace_un_backup_por_dia(app, monkeypatch):
    backup = sys.modules["app.nucleo.backup"]
    llamadas = []
    monkeypatch.setattr(backup, "hacer_backup", lambda **opciones: llamadas.append(opciones))

    async def dos_vueltas():
        tarea = asyncio.create_task(backup.backup_diario_continuo(cada_segundos=0))
        while len(llamadas) < 2:
            await asyncio.sleep(0.01)
        tarea.cancel()

    asyncio.run(asyncio.wait_for(dos_vueltas(), timeout=5))
    assert llamadas[0] == {"solo_si_no_hay_de_hoy": True}


@pytest.fixture
def mudanza(app, cliente):
    """El módulo de mudanza, con una base que ya tiene un dato y el 'backend' apagado."""
    respuesta = cliente.post("/insumos", json={"nombre": "Urea", "categoria": "fertilizante", "unidad": "kg"})
    assert respuesta.status_code == 201, respuesta.text
    modulo = importlib.reload(importlib.import_module("app.nucleo.mudanza"))
    modulo.backend_prendido = lambda url=None: False
    return modulo


def test_preparar_arma_copia_sana_con_su_huella(mudanza, tmp_path):
    copia = mudanza.preparar(tmp_path / "mudanza")
    assert copia is not None and copia.exists()
    linea = (tmp_path / "mudanza" / "agroapp.db.sha256").read_bytes()
    assert linea == f"{mudanza.calcular_hash(copia)}  agroapp.db\n".encode()  # formato de sha256sum
    resumen = mudanza.revisar_base(copia)
    assert resumen["sana"]
    assert resumen["filas"]["insumos"] == 1
    assert any((tmp_path / "backups").glob("agroapp_*.db"))  # hizo backup antes


def test_preparar_no_hace_nada_con_el_backend_prendido(mudanza, tmp_path):
    mudanza.backend_prendido = lambda url=None: True
    assert mudanza.preparar(tmp_path / "mudanza") is None
    assert not (tmp_path / "mudanza").exists()


def test_verificar_acepta_la_copia_buena(mudanza, tmp_path):
    copia = mudanza.preparar(tmp_path / "mudanza")
    assert mudanza.verificar(copia) is True


def test_verificar_detecta_un_archivo_que_cambio_al_copiarlo(mudanza, tmp_path):
    copia = mudanza.preparar(tmp_path / "mudanza")
    with open(copia, "ab") as archivo:
        archivo.write(b"\0")  # Un byte de más, como si la copia hubiera llegado mal.
    assert mudanza.verificar(copia) is False


def test_verificar_rechaza_una_base_mas_nueva_que_el_codigo(mudanza, tmp_path):
    copia = mudanza.preparar(tmp_path / "mudanza")
    (tmp_path / "mudanza" / "agroapp.db.sha256").unlink()
    conexion = sqlite3.connect(copia)
    conexion.execute(f"PRAGMA user_version = {len(mudanza.database.MIGRACIONES) + 1}")
    conexion.close()
    assert mudanza.verificar(copia) is False


def test_verificar_no_crea_un_archivo_que_no_existe(mudanza, tmp_path):
    assert mudanza.verificar(tmp_path / "no_existe.db") is False
    assert not (tmp_path / "no_existe.db").exists()
