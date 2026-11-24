import sqlite3
from datetime import datetime
import pytest
from fastapi.testclient import TestClient

import gestion_donaciones.database as db
from gestion_donaciones.modelos import EstadoSolicitud, SolicitudStock
from main import app
from gestion_donaciones.rutas import permisos


def usuario_centro_medico():
    # reemplaza al usuario de la sesión: solicitar stock es del personal de centro médico (T28)
    return {"id_personal": 1, "run": "18888888-7", "nombre": "Prueba",
            "cargo": "RESPONSABLE_RECEPCION", "nombre_cargo": "Responsable de recepción",
            "centro_medico": "Hospital Regional de Concepción"}


@pytest.fixture
def cliente_bd_temporal(tmp_path, monkeypatch):
    """Configura una base de datos SQLite temporal limpia para pruebas de HU-08."""
    ruta_bd = tmp_path / "test_hu08.db"
    monkeypatch.setattr(db, "DB_PATH", ruta_bd)
    db.inicializar_bd()

    conexion = db.obtener_conexion()
    with conexion:
        conexion.execute(
            "INSERT INTO centros_medicos (id_centro_medico, nombre, direccion) VALUES (?, ?, ?)",
            (1, "Hospital Regional de Concepción", "San Martín 1436"),
        )
        conexion.execute(
            "INSERT INTO centros_medicos (id_centro_medico, nombre, direccion) VALUES (?, ?, ?)",
            (2, "Clínica Biobío", "Av. Jorge Alessandri 3515"),
        )
        # 3 unidades disponibles de Sangre O+ y 1 de Plaquetas A-
        unidades = [
            ("Sangre", "O+", "2026-11-10", "2026-12-20", "Disponible"),
            ("Sangre", "O+", "2026-11-11", "2026-12-21", "Disponible"),
            ("Sangre", "O+", "2026-11-12", "2026-12-22", "Disponible"),
            ("Plaquetas", "A-", "2026-11-12", "2026-11-18", "Disponible"),
            ("Sangre", "O+", "2026-11-01", "2026-12-01", "Usada"),
        ]
        conexion.executemany(
            """
            INSERT INTO unidades (tipo_componente, tipo_sangre, fecha_extraccion, fecha_caducidad, estado)
            VALUES (?, ?, ?, ?, ?)
            """,
            unidades,
        )
    conexion.close()

    app.dependency_overrides[permisos.obtener_usuario] = usuario_centro_medico
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_estados_solicitud():
    """T30 - Test 2: Verifica los valores de EstadoSolicitud."""
    estados = [e.value for e in EstadoSolicitud]
    assert "PENDIENTE" in estados
    assert "ATENDIDA" in estados
    assert len(estados) == 2


def test_datos_y_estado_inicial_solicitud():
    """T30 - Test 1 y 2: Verifica atributos de SolicitudStock y su estado inicial PENDIENTE."""
    solicitud = SolicitudStock(
        id_centro_medico=1,
        tipo_hemoderivado="Sangre",
        grupo_sanguineo="O+",
        cantidad=3,
    )

    assert solicitud.id is None
    assert solicitud.id_centro_medico == 1
    assert solicitud.tipo_hemoderivado == "Sangre"
    assert solicitud.grupo_sanguineo == "O+"
    assert solicitud.cantidad == 3
    assert isinstance(solicitud.fecha_solicitud, datetime)
    assert solicitud.estado == EstadoSolicitud.PENDIENTE


def test_tabla_solicitudes_en_bd_temporal(tmp_path, monkeypatch):
    """T30: Verifica que inicializar_bd cree la tabla solicitudes con sus columnas."""
    ruta_bd_temporal = tmp_path / "test_solicitudes.db"
    monkeypatch.setattr(db, "DB_PATH", ruta_bd_temporal)

    db.inicializar_bd()

    conexion = sqlite3.connect(ruta_bd_temporal)
    cursor = conexion.execute("PRAGMA table_info(solicitudes)")
    columnas = {fila[1] for fila in cursor.fetchall()}
    conexion.close()

    esperadas = {
        "id_solicitud",
        "id_centro_medico",
        "tipo_hemoderivado",
        "grupo_sanguineo",
        "cantidad",
        "fecha_solicitud",
        "estado",
    }
    assert esperadas.issubset(columnas)


def test_crear_solicitud_stock_exitosa(cliente_bd_temporal):
    """T33: Crea una solicitud válida y verifica su persistencia en estado PENDIENTE."""
    response = cliente_bd_temporal.post(
        "/stock/solicitar",
        data={
            "tipo_hemoderivado": "Sangre",
            "grupo_sanguineo": "O+",
            "cantidad": "2",
        },
    )

    assert response.status_code == 200
    assert "Solicitud registrada en estado Pendiente: 2 unidad(es) de Sangre (O+)." in response.text

    conexion = db.obtener_conexion()
    filas = conexion.execute("SELECT * FROM solicitudes").fetchall()
    conexion.close()

    assert len(filas) == 1
    assert filas[0]["id_centro_medico"] == 1
    assert filas[0]["tipo_hemoderivado"] == "Sangre"
    assert filas[0]["grupo_sanguineo"] == "O+"
    assert filas[0]["cantidad"] == 2
    assert filas[0]["estado"] == "PENDIENTE"


@pytest.mark.parametrize(
    "payload, mensaje_esperado",
    [
        (
            {"tipo_hemoderivado": "", "grupo_sanguineo": "O+", "cantidad": "1"},
            "Debe seleccionar el tipo de hemoderivado.",
        ),
        (
            {"tipo_hemoderivado": "Sangre", "grupo_sanguineo": "", "cantidad": "1"},
            "Debe seleccionar el grupo sanguíneo.",
        ),
        (
            {"tipo_hemoderivado": "Sangre", "grupo_sanguineo": "O+", "cantidad": ""},
            "Debe ingresar una cantidad válida mayor a 0.",
        ),
        (
            {"tipo_hemoderivado": "Sangre", "grupo_sanguineo": "O+", "cantidad": "0"},
            "La cantidad solicitada debe ser mayor a 0.",
        ),
        (
            {"tipo_hemoderivado": "Sangre", "grupo_sanguineo": "O+", "cantidad": "-3"},
            "La cantidad solicitada debe ser mayor a 0.",
        ),
        (
            {"tipo_hemoderivado": "Sangre", "grupo_sanguineo": "O+", "cantidad": "abc"},
            "La cantidad debe ser un número entero mayor a 0.",
        ),
    ],
)
def test_rechazar_solicitud_campos_invalidos(cliente_bd_temporal, payload, mensaje_esperado):
    """T33: Rechaza solicitudes con campos obligatorios vacíos o cantidad inválida."""
    response = cliente_bd_temporal.post("/stock/solicitar", data=payload)

    assert response.status_code == 400
    assert mensaje_esperado in response.text

    conexion = db.obtener_conexion()
    total = conexion.execute("SELECT COUNT(*) AS total FROM solicitudes").fetchone()["total"]
    conexion.close()
    assert total == 0


def test_rechazar_solicitud_stock_insuficiente(cliente_bd_temporal):
    """T33: Rechaza una solicitud cuando la cantidad supera el stock disponible."""
    response = cliente_bd_temporal.post(
        "/stock/solicitar",
        data={
            "tipo_hemoderivado": "Sangre",
            "grupo_sanguineo": "O+",
            "cantidad": "5",
        },
    )

    assert response.status_code == 400
    assert "Stock insuficiente: solo hay 3 disponibles de Sangre (O+)." in response.text

    conexion = db.obtener_conexion()
    total = conexion.execute("SELECT COUNT(*) AS total FROM solicitudes").fetchone()["total"]
    conexion.close()
    assert total == 0


def test_listar_solicitudes_ordenadas_y_filtradas_por_centro(cliente_bd_temporal):
    """T33: Lista solicitudes del centro de más reciente a más antigua con su estado."""
    conexion = db.obtener_conexion()
    with conexion:
        conexion.executemany(
            """
            INSERT INTO solicitudes (
                id_centro_medico, tipo_hemoderivado, grupo_sanguineo, cantidad, fecha_solicitud, estado
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "Plaquetas", "A-", 1, "2026-11-20T09:00:00", "ATENDIDA"),
                (1, "Sangre", "O+", 2, "2026-11-23T14:30:00", "PENDIENTE"),
                (2, "Plasma", "AB-", 4, "2026-11-23T18:00:00", "PENDIENTE"),
            ],
        )
    conexion.close()

    response = cliente_bd_temporal.get("/stock")
    assert response.status_code == 200
    html = response.text

    # Muestra estados legibles de las solicitudes del centro 1
    assert "Pendiente" in html
    assert "Atendida" in html

    # La solicitud más reciente (2026-11-23T14:30:00) aparece antes que la antigua (2026-11-20T09:00:00)
    assert html.index("2026-11-23T14:30:00") < html.index("2026-11-20T09:00:00")

    # No muestra solicitudes pertenecientes a otro centro médico (centro 2)
    assert "2026-11-23T18:00:00" not in html


def test_mostrar_aviso_sin_solicitudes(cliente_bd_temporal):
    """T33: Muestra aviso cuando el centro médico aún no tiene solicitudes."""
    response = cliente_bd_temporal.get("/stock")
    assert response.status_code == 200
    assert "No hay solicitudes registradas para este centro médico." in response.text