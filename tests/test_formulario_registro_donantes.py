import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from gestion_donaciones import database
from gestion_donaciones.database import inicializar_bd
from gestion_donaciones.modelos.enums import FactorRh, GrupoSanguineo
from gestion_donaciones.rutas import registro_donantes


def datos_validos(**cambios):
    datos = {
        "run": "12.345.678-5",
        "nombre": "Ana Pérez",
        "correo": "ana@correo.cl",
        "telefono": "+56 9 1234 5678",
        "grupo_sanguineo": "A",
        "factor_rh": "+",
        "fecha_nacimiento": "1995-04-20",
        "peso_kg": "62,5",
    }
    datos.update(cambios)
    return datos


class Respuesta:
    """Imita lo mínimo de una respuesta HTTP."""

    def __init__(self, status_code, datos):
        self.status_code = status_code
        self.datos = datos


class PruebaFormulario(unittest.TestCase):
    """Base: BD temporal, no se toca donaciones.db."""

    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        parche_bd = patch.object(
            database, "DB_PATH", Path(carpeta.name) / "test_donaciones.db"
        )
        parche_bd.start()
        self.addCleanup(parche_bd.stop)
        inicializar_bd()

    def guardar(self, datos):
        """Equivale a llenar el formulario y presionar Guardar."""
        pedido = registro_donantes.DonanteRequest(**datos)
        try:
            resultado = registro_donantes.procesar_registro_donante(pedido)
        except HTTPException as error:
            return Respuesta(error.status_code, {"detail": error.detail})
        if isinstance(resultado, dict):
            return Respuesta(200, resultado)
        return Respuesta(resultado.status_code, json.loads(resultado.body))

    def buscar(self, run):
        return registro_donantes.registro.buscar_por_run(run)


class TestPantalla(PruebaFormulario):
    def test_muestra_el_formulario(self):
        request = Request({
            "type": "http", "method": "GET", "path": "/donantes/registrar",
            "headers": [], "query_string": b"",
        })
        html = registro_donantes.ver_formulario_donante(request).body.decode("utf-8")

        for elemento in ("formDonante", "run", "nombre", "grupo", "rh", "correo", "telefono"):
            with self.subTest(id=elemento):
                self.assertIn(f'id="{elemento}"', html)


class TestRegistrarDonante(PruebaFormulario):
    def test_guarda_un_donante_nuevo(self):
        respuesta = self.guardar(datos_validos())

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.datos["donante"]["run"], "12345678-5")
        self.assertEqual(respuesta.datos["donante"]["tipo_sangre"], "A+")
        self.assertIsNone(respuesta.datos["donante"]["estado"])

        guardado = self.buscar("12345678-5")
        self.assertIsNotNone(guardado)
        self.assertEqual(guardado.nombre, "Ana Pérez")
        self.assertEqual(guardado.grupo_sanguineo, GrupoSanguineo.A)
        self.assertEqual(guardado.factor_rh, FactorRh.POSITIVO)
        self.assertEqual(guardado.fecha_nacimiento, date(1995, 4, 20))
        self.assertEqual(guardado.peso_kg, 62.5)

    def test_datos_opcionales_vacios(self):
        respuesta = self.guardar(datos_validos(correo="", fecha_nacimiento="", peso_kg=""))

        self.assertEqual(respuesta.status_code, 200)
        guardado = self.buscar("12345678-5")
        self.assertIsNone(guardado.correo)
        self.assertIsNone(guardado.fecha_nacimiento)
        self.assertIsNone(guardado.peso_kg)


class TestRunExistente(PruebaFormulario):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.guardar(datos_validos()).status_code, 200)

    def test_muestra_el_donante_registrado(self):
        respuesta = self.guardar(datos_validos(run="12345678-5", nombre="Otro Nombre"))

        self.assertEqual(respuesta.status_code, 409)
        self.assertIn("Ya existe", respuesta.datos["mensaje"])
        self.assertEqual(respuesta.datos["donante"]["nombre"], "Ana Pérez")
        self.assertEqual(self.buscar("12345678-5").nombre, "Ana Pérez")  # no se sobrescribe

    def test_basta_con_el_run(self):
        respuesta = self.guardar({"run": "12.345.678-5"})

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.datos["donante"]["run"], "12345678-5")


class TestDatosInvalidos(PruebaFormulario):
    def comprobar_error(self, datos, mensaje):
        respuesta = self.guardar(datos)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn(mensaje, respuesta.datos["detail"])
        self.assertIsNone(self.buscar("12345678-5"))

    def test_run_invalido(self):
        self.comprobar_error(datos_validos(run="12.345.678-9"), "El RUN no es válido.")

    def test_formulario_vacio_muestra_todos_los_errores(self):
        respuesta = self.guardar({})

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.datos["detail"], [
            "El RUN es obligatorio.",
            "El nombre es obligatorio.",
            "El grupo sanguíneo es obligatorio.",
            "El factor Rh es obligatorio.",
            "Debe ingresar al menos un contacto (correo o teléfono).",
        ])

    def test_nombre_solo_con_espacios(self):
        self.comprobar_error(datos_validos(nombre="   "), "El nombre es obligatorio.")

    def test_grupo_sanguineo_invalido(self):
        self.comprobar_error(datos_validos(grupo_sanguineo="Z"), "El grupo sanguíneo no es válido.")

    def test_factor_rh_invalido(self):
        self.comprobar_error(datos_validos(factor_rh="X"), "El factor Rh no es válido.")

    def test_peso_que_no_es_numero(self):
        self.comprobar_error(datos_validos(peso_kg="abc"), "El peso debe ser un número mayor que 0.")

    def test_fecha_de_nacimiento_invalida(self):
        self.comprobar_error(datos_validos(fecha_nacimiento="hola"), "La fecha de nacimiento no es válida.")

    def test_fecha_de_nacimiento_futura(self):
        self.comprobar_error(datos_validos(fecha_nacimiento="2999-01-01"), "La fecha de nacimiento no puede ser futura.")


if __name__ == "__main__":
    unittest.main()
