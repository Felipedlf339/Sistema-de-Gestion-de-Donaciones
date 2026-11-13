import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from gestion_donaciones import database
from gestion_donaciones.database import inicializar_bd
from gestion_donaciones.modelos.donante import Donante
from gestion_donaciones.modelos.enums import (
    CargoPersonal,
    EstadoElegibilidad,
    FactorRh,
    GrupoSanguineo,
)
from gestion_donaciones.modelos.personalCentroDonacion import PersonalCentroDonacion
from gestion_donaciones.registro_donantes import RegistroDonantes
from gestion_donaciones.rutas import elegibilidad

RUN = "12345678-5"

APTO = EstadoElegibilidad.APTO
DIFERIDO = EstadoElegibilidad("DIFERIDO_TEMPORAL")
RECHAZADO = EstadoElegibilidad("RECHAZADO_PERMANENTE")


def crear_usuario(cargo):
    return PersonalCentroDonacion(
        run="77777777-7", nombre="Gustavo", id_personal="P-001", cargo=cargo
    )

class Respuesta:
    """Imita lo mínimo de una respuesta HTTP para no cambiar las pruebas."""

    def __init__(self, status_code, datos):
        self.status_code = status_code
        self._datos = datos

    def json(self):
        return self._datos
    
class PruebaElegibilidad(unittest.TestCase):
    """Base: BD temporal, un donante APTO registrado y un cliente HTTP."""

    def setUp(self):
        # Base de datos temporal, no se toca la real
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        parche_bd = patch.object(
            database, "DB_PATH", Path(carpeta.name) / "test_donaciones.db"
        )
        parche_bd.start()
        self.addCleanup(parche_bd.stop)
        inicializar_bd()

        # Donante registrado con estado Apto
        self.registro = RegistroDonantes()
        donante = Donante(
            run=RUN,
            nombre="Francisca Hidalgo",
            grupo_sanguineo=GrupoSanguineo.O,
            factor_rh=FactorRh.POSITIVO,
            correo="fran.hidalgo@correo.cl",
            telefono="+56912345678",
        )
        donante.estado_elegibilidad = APTO
        self.assertEqual(self.registro.registrar(donante), [])

        # Por defecto, el usuario de la sesión tiene el rol correcto
        self.fijar_usuario(CargoPersonal.ATENCION_DONANTE)

    # ---- utilidades ----
    def fijar_usuario(self, cargo):
        parche = patch.object(elegibilidad, "usuario_actual", crear_usuario(cargo))
        parche.start()
        self.addCleanup(parche.stop)

    def otro_cargo(self):
        otros = [c for c in CargoPersonal if c != CargoPersonal.ATENCION_DONANTE]
        if not otros:
            self.skipTest("CargoPersonal solo tiene ATENCION_DONANTE")
        return otros[0]

    def poner_estado(self, estado, motivo=None):
        self.assertTrue(self.registro.actualizar_elegibilidad(RUN, estado, motivo))

    def guardado(self):
        donante = self.registro.buscar_por_run(RUN)
        return donante.estado_elegibilidad, donante.motivo

    def guardar(self, estado, motivo=None):
        """Equivale a elegir un estado, escribir el motivo y presionar Guardar."""
        datos = elegibilidad.EstadoRequest(nuevo_estado=estado, motivo=motivo)
        try:
            resultado = elegibilidad.actualizar_estado(datos)
        except HTTPException as error:
            return Respuesta(error.status_code, {"detail": error.detail})
        return Respuesta(200, resultado)

    def pantalla(self):
        """Devuelve el HTML que vería el usuario en /elegibilidad."""
        request = Request({
            "type": "http", "method": "GET", "path": "/elegibilidad",
            "headers": [], "query_string": b"",
        })
        return elegibilidad.mostrar_pantalla(request).body.decode("utf-8")


class TestCambiarEstado(PruebaElegibilidad):
    def test_cambiar_a_diferido_temporal(self):
        respuesta = self.guardar(DIFERIDO, "tatuaje")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["estado"], "DIFERIDO_TEMPORAL")
        self.assertEqual(self.guardado()[0], DIFERIDO)

    def test_cambiar_a_rechazado_permanente(self):
        respuesta = self.guardar(RECHAZADO, "enfermedad crónica")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["estado"], "RECHAZADO_PERMANENTE")
        self.assertEqual(self.guardado()[0], RECHAZADO)

    def test_volver_a_apto(self):
        self.poner_estado(DIFERIDO, "tatuaje")

        # Nota: se envía motivo porque el equipo decidió pedirlo en todo cambio
        respuesta = self.guardar(APTO, "terminó el período de diferimiento")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.guardado()[0], APTO)

    def test_la_pantalla_muestra_el_estado_guardado(self):
        self.guardar(DIFERIDO, "tatuaje")

        html = self.pantalla()

        self.assertIn('data-valor="DIFERIDO_TEMPORAL"', html)


class TestMotivoObligatorio(PruebaElegibilidad):
    def comprobar_rechazo_sin_motivo(self, estado):
        for motivo in ("", "   ", None):
            with self.subTest(estado=estado.value, motivo=motivo):
                respuesta = self.guardar(estado, motivo)

                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("motivo", respuesta.json()["detail"].lower())
                self.assertEqual(self.guardado()[0], APTO)  # no cambió

    def test_diferido_temporal_sin_motivo(self):
        self.comprobar_rechazo_sin_motivo(DIFERIDO)

    def test_rechazado_permanente_sin_motivo(self):
        self.comprobar_rechazo_sin_motivo(RECHAZADO)

    def test_estado_no_apto_con_motivo_guarda_estado_y_motivo(self):
        for estado, motivo in ((DIFERIDO, "tatuaje"), (RECHAZADO, "enfermedad crónica")):
            with self.subTest(estado=estado.value):
                respuesta = self.guardar(estado, motivo)

                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(self.guardado(), (estado, motivo))

    def test_volver_a_apto_sin_motivo(self):
        self.poner_estado(DIFERIDO, "tatuaje")

        for motivo in ("", "   ", None):
            with self.subTest(motivo=motivo):
                respuesta = self.guardar(APTO, motivo)

                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("motivo", respuesta.json()["detail"].lower())
                self.assertEqual(self.guardado(), (DIFERIDO, "tatuaje"))


class TestPermisos(PruebaElegibilidad):
    def test_usuario_con_rol_puede_modificar(self):
        respuesta = self.guardar(DIFERIDO, "tatuaje")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.guardado()[0], DIFERIDO)

    def test_usuario_sin_rol_es_bloqueado(self):
        self.fijar_usuario(self.otro_cargo())

        respuesta = self.guardar(DIFERIDO, "tatuaje")

        self.assertEqual(respuesta.status_code, 403)
        self.assertIn("Acceso denegado", respuesta.json()["detail"])
        self.assertEqual(self.guardado()[0], APTO)

    def test_estado_no_cambia_tras_un_intento_bloqueado(self):
        self.poner_estado(DIFERIDO, "tatuaje")
        self.fijar_usuario(self.otro_cargo())

        self.guardar(APTO, "intento sin permisos")

        self.assertEqual(self.guardado(), (DIFERIDO, "tatuaje"))

    def test_pantalla_con_rol_muestra_el_formulario(self):
        html = self.pantalla()

        for elemento in (
            "form-elegibilidad",
            "selector-estado",
            "contenedor-motivo",
            "input-motivo",
            "msg-feedback",
        ):
            with self.subTest(id=elemento):
                self.assertIn(f'id="{elemento}"', html)
        self.assertNotIn("Acceso denegado", html)

    def test_pantalla_sin_rol_muestra_mensaje_de_permisos(self):
        self.fijar_usuario(self.otro_cargo())

        html = self.pantalla()

        self.assertIn("Acceso denegado", html)
        self.assertIn("no tiene permisos", html)
        self.assertNotIn('id="form-elegibilidad"', html)


if __name__ == "__main__":
    unittest.main()