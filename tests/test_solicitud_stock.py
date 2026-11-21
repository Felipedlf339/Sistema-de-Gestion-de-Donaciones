import sqlite3
from datetime import datetime
import gestion_donaciones.database as db
from gestion_donaciones.modelos import EstadoSolicitud, SolicitudStock


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