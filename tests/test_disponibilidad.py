import tempfile
import unittest
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from gestion_donaciones import database
from gestion_donaciones.database import inicializar_bd, obtener_conexion
from gestion_donaciones.modelos.enums import EstadoUnidad
from gestion_donaciones.rutas import permisos
from main import app


def usuario_encargado_inventario():
    # reemplaza al usuario de la sesión: la consulta de stock pide un cargo autorizado (T28)
    return {"id_personal": 1, "run": "16666666-K", "nombre": "Prueba",
            "cargo": "ENCARGADO_INVENTARIO", "nombre_cargo": "Encargado de inventario",
            "centro_medico": None}


class TestDisponibilidadStock(unittest.TestCase):

    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        parche = patch.object(
            database, "DB_PATH", Path(carpeta.name) / "test_disponibilidad.db"
        )
        parche.start()
        self.addCleanup(parche.stop)
        inicializar_bd()

        app.dependency_overrides[permisos.obtener_usuario] = usuario_encargado_inventario
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

        self.preparar_datos_stock()

    def preparar_datos_stock(self):
        """Deja la tabla unidades con datos conocidos para probar los filtros."""
        hoy = date.today().isoformat()
        en_diez_dias = (date.today() + timedelta(days=10)).isoformat()
        ayer = (date.today() - timedelta(days=2)).isoformat()
        disponible = EstadoUnidad.DISPONIBLE.value

        unidades = [
            (100, "Sangre", "O+", hoy, en_diez_dias, disponible),
            (101, "Plaquetas", "A-", hoy, en_diez_dias, disponible),
            (102, "Plasma", "B+", hoy, en_diez_dias, "USADA"),
            (103, "Sangre", "AB-", ayer, ayer, "VENCIDA"),
        ]
        with closing(obtener_conexion()) as conexion:
            with conexion:
                conexion.executemany(
                    """
                    INSERT INTO unidades (id_unidad, tipo_componente, tipo_sangre,
                                          fecha_extraccion, fecha_caducidad, estado)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    unidades,
                )

    def test_listar_solo_unidades_disponibles(self):
        """Prueba T13: solo se muestran unidades Disponibles, no las Usadas/Vencidas."""
        response = self.client.get("/stock")
        self.assertEqual(response.status_code, 200)
        html = response.text

        self.assertIn("<strong>100</strong>", html)
        self.assertIn("<strong>101</strong>", html)
        self.assertNotIn("<strong>102</strong>", html)
        self.assertNotIn("<strong>103</strong>", html)

    def test_filtrar_por_tipo_componente(self):
        """Prueba T14: el filtro de componente funciona."""
        response = self.client.get("/stock?tipo=Plaquetas")
        self.assertEqual(response.status_code, 200)
        html = response.text

        self.assertIn("<strong>101</strong>", html)
        self.assertNotIn("<strong>100</strong>", html)

    def test_mostrar_aviso_sin_resultados(self):
        """Prueba T15: aparece el aviso cuando los filtros no coinciden con nada."""
        response = self.client.get("/stock?tipo=Plaquetas&grupo=O%2B")
        self.assertEqual(response.status_code, 200)
        html = response.text

        self.assertIn("No se encontraron unidades disponibles con esos filtros.", html)
        self.assertNotIn("<strong>100</strong>", html)
        self.assertNotIn("<strong>101</strong>", html)


if __name__ == "__main__":
    unittest.main()