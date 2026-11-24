"""Casos de prueba para la HU-03: Registro de Donaciones y Generación de Unidades."""

import unittest
from fastapi.testclient import TestClient
from main import app
from gestion_donaciones.rutas import permisos


def usuario_atencion_donante():
    # reemplaza al usuario de la sesión: el registro de donaciones es de atención al donante (T28)
    return {"id_personal": 1, "run": "15555555-6", "nombre": "Prueba",
            "cargo": "ATENCION_DONANTE", "nombre_cargo": "Atención al donante", "centro_medico": None}

class TestRegistroDonaciones(unittest.TestCase):
    
    def setUp(self):
        """Configuración inicial para el cliente de pruebas."""
        app.dependency_overrides[permisos.obtener_usuario] = usuario_atencion_donante
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)
        from gestion_donaciones.registro_donantes import RegistroDonantes
        from gestion_donaciones.modelos import Donante, GrupoSanguineo, FactorRh
        from gestion_donaciones.modelos.enums import EstadoElegibilidad

        registro = RegistroDonantes()
        donante = registro.buscar_por_run("12345678-5")
        if donante is None:
            nuevo = Donante("12345678-5", "Francisca Hidalgo", GrupoSanguineo.O, FactorRh.POSITIVO, correo="fran@correo.cl")
            nuevo.estado_elegibilidad = EstadoElegibilidad.APTO
            registro.registrar(nuevo)
        else:
            registro.actualizar_elegibilidad("12345678-5", EstadoElegibilidad.APTO, "Apto para pruebas")

    def test_1_registrar_donacion_sangre_apto(self):
        """Test 1: Registrar una donación de sangre con un donante Apto."""
        payload = {
            "id_donante": "12345678-5",  # RUN apto de ejemplo
            "tipo_donacion": "SANGRE"
        }
        response = self.client.post("/donaciones/registrar", json=payload)
        self.assertIn(response.status_code, [200, 201])

    def test_2_registrar_donacion_plaquetas_apto(self):
        """Test 2: Registrar una donación de plaquetas con un donante Apto."""
        payload = {
            "id_donante": "12345678-5",  # RUN apto de ejemplo
            "tipo_donacion": "PLAQUETAS"
        }
        response = self.client.post("/donaciones/registrar", json=payload)
        self.assertIn(response.status_code, [200, 201])

    def test_3_rechazar_donante_no_apto(self):
        """Test 3: Rechazar el registro si el donante está No Apto (Diferido)."""
        payload = {
            "id_donante": "11111111-1",  # RUN diferido temporal de ejemplo
            "tipo_donacion": "SANGRE"
        }
        response = self.client.post("/donaciones/registrar", json=payload)
        self.assertIn(response.status_code, [400, 422, 404])

    def test_4_tipo_donacion_invalido(self):
        """Test 4: Rechazar el registro si el tipo de donación no es válido."""
        payload = {
            "id_donante": "12345678-5",
            "tipo_donacion": "PLASMA_EXOTICO"  # Tipo no permitido
        }
        response = self.client.post("/donaciones/registrar", json=payload)
        self.assertIn(response.status_code, [400, 422])

    def test_5_generacion_unidad_y_caducidad(self):
        """Test 5: Verificar que al registrar una donación exitosa se genera la unidad con estado DISPONIBLE y fecha de caducidad."""
        payload = {
            "id_donante": "12345678-5",
            "tipo_donacion": "SANGRE"
        }
        response = self.client.post("/donaciones/registrar", json=payload)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("unidad", data)
        self.assertEqual(data["unidad"]["estado"], "DISPONIBLE")
        self.assertIsNotNone(data["unidad"]["fecha_caducidad"])

if __name__ == '__main__':
    unittest.main()