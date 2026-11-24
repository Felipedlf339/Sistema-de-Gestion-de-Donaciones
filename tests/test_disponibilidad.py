from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from main import app
from gestion_donaciones.database import obtener_conexion
from gestion_donaciones.rutas import permisos

client = TestClient(app)


def usuario_encargado_inventario():
    # reemplaza al usuario de la sesión: la consulta de stock pide un cargo autorizado (T28)
    return {"id_personal": 1, "run": "16666666-K", "nombre": "Prueba",
            "cargo": "ENCARGADO_INVENTARIO", "nombre_cargo": "Encargado de inventario",
            "centro_medico": None}


@pytest.fixture(autouse=True)
def sesion_de_prueba():
    app.dependency_overrides[permisos.obtener_usuario] = usuario_encargado_inventario
    yield
    app.dependency_overrides.clear()


def _preparar_datos_stock():
    """Deja la tabla unidades con datos conocidos para probar los filtros."""
    hoy = date.today().isoformat()
    manana = (date.today() + timedelta(days=10)).isoformat()
    ayer = (date.today() - timedelta(days=2)).isoformat()

    conexion = obtener_conexion()
    with conexion:
        conexion.execute("DELETE FROM unidades")
        conexion.execute(
            """
            INSERT INTO unidades (id_unidad, tipo_componente, tipo_sangre, fecha_extraccion, fecha_caducidad, estado)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (100, "Sangre", "O+", hoy, manana, "Disponible"),
        )
        conexion.execute(
            """
            INSERT INTO unidades (id_unidad, tipo_componente, tipo_sangre, fecha_extraccion, fecha_caducidad, estado)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (101, "Plaquetas", "A-", hoy, manana, "Disponible"),
        )
        conexion.execute(
            """
            INSERT INTO unidades (id_unidad, tipo_componente, tipo_sangre, fecha_extraccion, fecha_caducidad, estado)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (102, "Plasma", "B+", hoy, manana, "Usada"),
        )
        conexion.execute(
            """
            INSERT INTO unidades (id_unidad, tipo_componente, tipo_sangre, fecha_extraccion, fecha_caducidad, estado)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (103, "Sangre", "AB-", ayer, ayer, "Vencida"),
        )
    conexion.close()


def test_listar_solo_unidades_disponibles():
    """Prueba T13: Verifica que solo se muestren unidades Disponibles y oculte las Usadas/Vencidas."""
    _preparar_datos_stock()
    response = client.get("/stock")
    assert response.status_code == 200
    html = response.text

    assert "<strong>100</strong>" in html
    assert "<strong>101</strong>" in html
    assert "<strong>102</strong>" not in html
    assert "<strong>103</strong>" not in html


def test_filtrar_por_tipo_componente():
    """Prueba T14: Verifica que el filtro de componente funcione."""
    _preparar_datos_stock()
    response = client.get("/stock?tipo=Plaquetas")
    assert response.status_code == 200
    html = response.text

    assert "<strong>101</strong>" in html
    assert "<strong>100</strong>" not in html


def test_mostrar_aviso_sin_resultados():
    """Prueba T15: Verifica que aparezca el aviso cuando los filtros no coinciden con nada."""
    _preparar_datos_stock()
    response = client.get("/stock?tipo=Plaquetas&grupo=O%2B")
    assert response.status_code == 200
    html = response.text

    assert "No se encontraron unidades disponibles con esos filtros." in html
    assert "<strong>100</strong>" not in html
    assert "<strong>101</strong>" not in html
