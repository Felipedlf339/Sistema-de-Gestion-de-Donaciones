"""Pruebas de las reglas de validación del donante (HU-01, tarea 1.4)."""

import unittest
from datetime import date, datetime, timedelta

from gestion_donaciones.modelos import Donante, FactorRh, GrupoSanguineo
from gestion_donaciones.validaciones import (
    calcular_digito_verificador,
    normalizar_run,
    validar_correo,
    validar_donante,
    validar_run,
    validar_telefono,
)


def crear_donante_valido():
    # donante con todos los datos correctos, cada prueba cambia solo lo que necesita
    return Donante("12.345.678-5", "Ana Pérez", GrupoSanguineo.A, FactorRh.POSITIVO,
                   correo="ana@correo.cl", telefono="912345678",
                   fecha_nacimiento=date(1990, 5, 20), peso_kg=60)


class PruebasNormalizarRun(unittest.TestCase):

    def test_quita_puntos(self):
        self.assertEqual(normalizar_run("12.345.678-5"), "12345678-5")

    def test_agrega_guion_si_no_lo_tiene(self):
        self.assertEqual(normalizar_run("123456785"), "12345678-5")

    def test_quita_espacios(self):
        self.assertEqual(normalizar_run(" 12 345 678-5 "), "12345678-5")

    def test_k_queda_mayuscula(self):
        self.assertEqual(normalizar_run("10.000.013-k"), "10000013-K")

    def test_quita_ceros_a_la_izquierda(self):
        self.assertEqual(normalizar_run("05.123.456-1"), "5123456-1")

    def test_none_y_vacio_dan_none(self):
        self.assertIsNone(normalizar_run(None))
        self.assertIsNone(normalizar_run(""))


class PruebasDigitoVerificador(unittest.TestCase):

    def test_digito_numerico(self):
        self.assertEqual(calcular_digito_verificador("12345678"), "5")

    def test_digito_k(self):
        self.assertEqual(calcular_digito_verificador("10000013"), "K")

    def test_digito_cero(self):
        self.assertEqual(calcular_digito_verificador("10000004"), "0")


class PruebasValidarRun(unittest.TestCase):

    def test_run_valido_con_y_sin_puntos(self):
        self.assertTrue(validar_run("12.345.678-5"))
        self.assertTrue(validar_run("12345678-5"))

    def test_run_valido_con_k_minuscula(self):
        self.assertTrue(validar_run("10000013-k"))

    def test_run_valido_de_7_digitos(self):
        self.assertTrue(validar_run("5.123.456-1"))

    def test_digito_verificador_incorrecto(self):
        self.assertFalse(validar_run("12345678-9"))

    def test_run_con_letras(self):
        self.assertFalse(validar_run("12A45678-5"))

    def test_run_muy_corto(self):
        self.assertFalse(validar_run("123456-0"))

    def test_run_muy_largo(self):
        self.assertFalse(validar_run("123456789-2"))

    def test_run_vacio(self):
        self.assertFalse(validar_run(""))
        self.assertFalse(validar_run(None))


class PruebasValidarContacto(unittest.TestCase):

    def test_correo_valido(self):
        self.assertTrue(validar_correo("ana@correo.cl"))

    def test_correos_invalidos(self):
        self.assertFalse(validar_correo("anacorreo.cl"))
        self.assertFalse(validar_correo("ana@correo"))
        self.assertFalse(validar_correo("@correo.cl"))
        self.assertFalse(validar_correo("ana@@correo.cl"))
        self.assertFalse(validar_correo("ana perez@correo.cl"))
        self.assertFalse(validar_correo("ana@.correo.cl"))

    def test_telefono_de_9_digitos(self):
        self.assertTrue(validar_telefono("912345678"))
        self.assertTrue(validar_telefono("9 1234 5678"))

    def test_telefono_con_codigo_de_pais(self):
        self.assertTrue(validar_telefono("+56 9 1234 5678"))
        self.assertTrue(validar_telefono("56-9-1234-5678"))

    def test_telefonos_invalidos(self):
        self.assertFalse(validar_telefono("12345"))
        self.assertFalse(validar_telefono("9123A5678"))
        self.assertFalse(validar_telefono("+54 9 1234 5678"))


class PruebasValidarDonante(unittest.TestCase):

    def test_donante_valido_no_tiene_errores(self):
        self.assertEqual(validar_donante(crear_donante_valido()), [])

    def test_solo_datos_obligatorios_y_un_contacto(self):
        donante = Donante("12345678-5", "Ana", GrupoSanguineo.O, FactorRh.NEGATIVO,
                          telefono="912345678")
        self.assertEqual(validar_donante(donante), [])

    def test_run_vacio(self):
        donante = crear_donante_valido()
        donante.run = ""
        self.assertEqual(validar_donante(donante), ["El RUN es obligatorio."])

    def test_run_invalido(self):
        donante = crear_donante_valido()
        donante.run = "12345678-9"
        self.assertEqual(validar_donante(donante), ["El RUN no es válido."])

    def test_nombre_vacio(self):
        donante = crear_donante_valido()
        donante.nombre = "   "
        self.assertEqual(validar_donante(donante), ["El nombre es obligatorio."])

    def test_grupo_sanguineo_vacio_o_invalido(self):
        donante = crear_donante_valido()
        donante.grupo_sanguineo = None
        self.assertEqual(validar_donante(donante), ["El grupo sanguíneo es obligatorio."])

        donante.grupo_sanguineo = "A"
        self.assertEqual(validar_donante(donante), ["El grupo sanguíneo no es válido."])

    def test_factor_rh_vacio_o_invalido(self):
        donante = crear_donante_valido()
        donante.factor_rh = None
        self.assertEqual(validar_donante(donante), ["El factor Rh es obligatorio."])

        donante.factor_rh = "+"
        self.assertEqual(validar_donante(donante), ["El factor Rh no es válido."])

    def test_sin_ningun_contacto(self):
        donante = crear_donante_valido()
        donante.correo = None
        donante.telefono = ""
        self.assertEqual(validar_donante(donante),
                         ["Debe ingresar al menos un contacto (correo o teléfono)."])

    def test_correo_mal_formado(self):
        donante = crear_donante_valido()
        donante.correo = "ana@correo"
        self.assertEqual(validar_donante(donante), ["El correo no tiene un formato válido."])

    def test_telefono_mal_formado(self):
        donante = crear_donante_valido()
        donante.telefono = "12345"
        self.assertEqual(validar_donante(donante), ["El teléfono no tiene un formato válido."])

    def test_peso_cero_o_negativo(self):
        donante = crear_donante_valido()
        donante.peso_kg = 0
        self.assertEqual(validar_donante(donante), ["El peso debe ser un número mayor que 0."])

        donante.peso_kg = -5
        self.assertEqual(validar_donante(donante), ["El peso debe ser un número mayor que 0."])

    def test_fecha_de_nacimiento_futura(self):
        donante = crear_donante_valido()
        donante.fecha_nacimiento = date.today() + timedelta(days=1)
        self.assertEqual(validar_donante(donante),
                         ["La fecha de nacimiento no puede ser futura."])

    def test_fecha_de_nacimiento_que_no_es_date(self):
        donante = crear_donante_valido()
        donante.fecha_nacimiento = datetime(1990, 5, 20)
        self.assertEqual(validar_donante(donante), ["La fecha de nacimiento no es válida."])

        donante.fecha_nacimiento = "1990-05-20"
        self.assertEqual(validar_donante(donante), ["La fecha de nacimiento no es válida."])

    def test_formulario_vacio_muestra_todos_los_errores(self):
        donante = Donante("", "", None, None)
        errores = validar_donante(donante)

        self.assertEqual(len(errores), 5)
        self.assertIn("El RUN es obligatorio.", errores)
        self.assertIn("El nombre es obligatorio.", errores)
        self.assertIn("El grupo sanguíneo es obligatorio.", errores)
        self.assertIn("El factor Rh es obligatorio.", errores)
        self.assertIn("Debe ingresar al menos un contacto (correo o teléfono).", errores)


if __name__ == "__main__":
    unittest.main()
