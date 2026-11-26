"""Casos de prueba para la HU-03: Registro de Donaciones y Generación de Unidades."""

import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from gestion_donaciones import database
from gestion_donaciones.database import inicializar_bd, obtener_conexion
from gestion_donaciones.modelos import Donante, FactorRh, GrupoSanguineo
from gestion_donaciones.modelos.enums import EstadoElegibilidad, EstadoUnidad
from gestion_donaciones.registro_donantes import RegistroDonantes
from gestion_donaciones.rutas import permisos
from main import app


def usuario_atencion_donante():
    # reemplaza al usuario de la sesión: el registro de donaciones es de atención al donante (T28)
    return {"id_personal": 1, "run": "15555555-6", "nombre": "Prueba",
            "cargo": "ATENCION_DONANTE", "nombre_cargo": "Atención al donante", "centro_medico": None}


class TestRegistroDonaciones(unittest.TestCase):

    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        parche = patch.object(
            database, "DB_PATH", Path(carpeta.name) / "test_donaciones.db"
        )
        parche.start()
        self.addCleanup(parche.stop)
        inicializar_bd()

        app.dependency_overrides[permisos.obtener_usuario] = usuario_atencion_donante
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

        registro = RegistroDonantes()

        apto = Donante("12345678-5", "Francisca Hidalgo", GrupoSanguineo.O,
                       FactorRh.POSITIVO, correo="fran@correo.cl")
        apto.estado_elegibilidad = EstadoElegibilidad.APTO
        self.assertEqual(registro.registrar(apto), [])

        diferido = Donante("11111111-1", "Juan Perez", GrupoSanguineo.A,
                           FactorRh.NEGATIVO, correo="juan@correo.cl")
        diferido.estado_elegibilidad = EstadoElegibilidad("DIFERIDO_TEMPORAL")
        diferido.motivo = "tatuaje"
        self.assertEqual(registro.registrar(diferido), [])

    def contar(self, tabla):
        with closing(obtener_conexion()) as conexion:
            return conexion.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]

    def registrar(self, run, tipo):
        return self.client.post(
            "/donaciones/registrar", json={"id_donante": run, "tipo_donacion": tipo}
        )

    def test_1_registrar_donacion_sangre_apto(self):
        """Test 1: Registrar una donación de sangre con un donante Apto."""
        response = self.registrar("12345678-5", "SANGRE")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.contar("donaciones"), 1)
        self.assertEqual(self.contar("unidades"), 1)

    def test_2_registrar_donacion_plaquetas_apto(self):
        """Test 2: Registrar una donación de plaquetas con un donante Apto."""
        response = self.registrar("12345678-5", "PLAQUETAS")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.contar("donaciones"), 1)
        self.assertEqual(self.contar("unidades"), 1)

    def test_3_rechazar_donante_no_apto(self):
        """Test 3: Rechazar el registro si el donante está No Apto (Diferido)."""
        response = self.registrar("11111111-1", "SANGRE")

        self.assertEqual(response.status_code, 400)
        detalle = response.json()["detail"]
        self.assertIn("no está Apto", detalle)
        self.assertIn("tatuaje", detalle)
        self.assertEqual(self.contar("donaciones"), 0)
        self.assertEqual(self.contar("unidades"), 0)

    def test_3b_rechazar_donante_inexistente(self):
        response = self.registrar("22222222-2", "SANGRE")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.contar("donaciones"), 0)

    def test_4_tipo_donacion_invalido(self):
        """Test 4: Rechazar el registro si el tipo de donación no es válido."""
        response = self.registrar("12345678-5", "PLASMA_EXOTICO")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.contar("donaciones"), 0)
        self.assertEqual(self.contar("unidades"), 0)

    def test_5_generacion_unidad_y_caducidad(self):
        """Test 5: Al registrar una donación exitosa se genera la unidad DISPONIBLE con fecha de caducidad."""
        response = self.registrar("12345678-5", "SANGRE")
        self.assertEqual(response.status_code, 200)

        unidad = response.json()["unidad"]
        self.assertEqual(unidad["estado"], EstadoUnidad.DISPONIBLE.value)
        self.assertIsNotNone(unidad["fecha_caducidad"])
        self.assertGreater(unidad["fecha_caducidad"], unidad["fecha_extraccion"])

        with closing(obtener_conexion()) as conexion:
            fila = conexion.execute("SELECT estado FROM unidades").fetchone()
        self.assertEqual(fila["estado"], EstadoUnidad.DISPONIBLE.value)


if __name__ == "__main__":
    unittest.main()