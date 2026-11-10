"""Pruebas del registro y la búsqueda por RUN de donantes (HU-01, tarea 1.4)."""

import unittest

from gestion_donaciones.modelos import Donante, FactorRh, GrupoSanguineo
from gestion_donaciones.registro_donantes import RegistroDonantes


def crear_donante(run, nombre="Ana Pérez"):
    return Donante(run, nombre, GrupoSanguineo.A, FactorRh.POSITIVO, correo="ana@correo.cl")


class PruebasRegistrarDonante(unittest.TestCase):

    def setUp(self):
        # cada prueba parte con un registro vacío
        self.registro = RegistroDonantes()

    def test_registrar_donante_nuevo(self):
        donante = crear_donante("12.345.678-5")
        errores = self.registro.registrar(donante)

        self.assertEqual(errores, [])
        self.assertEqual(donante.id_donante, 1)
        self.assertEqual(donante.run, "12345678-5")
        self.assertIs(self.registro.buscar_por_run("12345678-5"), donante)

    def test_ids_se_asignan_en_orden(self):
        primero = crear_donante("12345678-5")
        segundo = crear_donante("11111111-1")
        self.registro.registrar(primero)
        self.registro.registrar(segundo)

        self.assertEqual(primero.id_donante, 1)
        self.assertEqual(segundo.id_donante, 2)

    def test_donante_invalido_no_se_guarda(self):
        donante = crear_donante("12345678-9")
        errores = self.registro.registrar(donante)

        self.assertEqual(errores, ["El RUN no es válido."])
        self.assertIsNone(donante.id_donante)
        self.assertEqual(len(self.registro.donantes), 0)

    def test_campo_obligatorio_vacio_no_se_guarda(self):
        donante = crear_donante("12345678-5", nombre="")
        errores = self.registro.registrar(donante)

        self.assertEqual(errores, ["El nombre es obligatorio."])
        self.assertIsNone(self.registro.buscar_por_run("12345678-5"))

    def test_donante_invalido_no_gasta_id(self):
        self.registro.registrar(crear_donante("12345678-9"))
        donante = crear_donante("12345678-5")
        self.registro.registrar(donante)

        self.assertEqual(donante.id_donante, 1)


class PruebasBuscarPorRun(unittest.TestCase):

    def setUp(self):
        self.registro = RegistroDonantes()
        self.donante = crear_donante("12345678-5")
        self.registro.registrar(self.donante)

    def test_busca_con_y_sin_puntos(self):
        self.assertIs(self.registro.buscar_por_run("12.345.678-5"), self.donante)
        self.assertIs(self.registro.buscar_por_run("12345678-5"), self.donante)
        self.assertIs(self.registro.buscar_por_run("123456785"), self.donante)

    def test_busca_con_k_minuscula(self):
        donante_k = crear_donante("10000013-K")
        self.registro.registrar(donante_k)

        self.assertIs(self.registro.buscar_por_run("10.000.013-k"), donante_k)

    def test_busca_con_cero_a_la_izquierda(self):
        donante_7 = crear_donante("5.123.456-1")
        self.registro.registrar(donante_7)

        self.assertIs(self.registro.buscar_por_run("05.123.456-1"), donante_7)

    def test_run_no_registrado(self):
        self.assertIsNone(self.registro.buscar_por_run("11111111-1"))

    def test_run_vacio_o_none(self):
        self.assertIsNone(self.registro.buscar_por_run(""))
        self.assertIsNone(self.registro.buscar_por_run(None))


class PruebasBloqueoDuplicados(unittest.TestCase):

    def setUp(self):
        self.registro = RegistroDonantes()
        self.original = crear_donante("12.345.678-5", nombre="Ana Pérez")
        self.registro.registrar(self.original)

    def test_rechaza_run_repetido(self):
        repetido = crear_donante("12345678-5", nombre="Otra Persona")
        errores = self.registro.registrar(repetido)

        self.assertEqual(errores, ["Ya existe un donante registrado con ese RUN."])
        self.assertIsNone(repetido.id_donante)

    def test_no_sobrescribe_al_donante_existente(self):
        self.registro.registrar(crear_donante("12345678-5", nombre="Otra Persona"))
        guardado = self.registro.buscar_por_run("12345678-5")

        self.assertIs(guardado, self.original)
        self.assertEqual(guardado.nombre, "Ana Pérez")
        self.assertEqual(len(self.registro.donantes), 1)

    def test_rechaza_run_repetido_escrito_distinto(self):
        errores = self.registro.registrar(crear_donante("012.345.678-5"))

        self.assertEqual(errores, ["Ya existe un donante registrado con ese RUN."])

    def test_reconoce_donante_existente_aunque_falten_datos(self):
        # el RUN se revisa antes que el resto del formulario (paso 2 de CU-01)
        incompleto = Donante("12345678-5", "", None, None)
        errores = self.registro.registrar(incompleto)

        self.assertEqual(errores, ["Ya existe un donante registrado con ese RUN."])

    def test_duplicado_no_gasta_id(self):
        self.registro.registrar(crear_donante("12345678-5"))
        nuevo = crear_donante("11111111-1")
        self.registro.registrar(nuevo)

        self.assertEqual(nuevo.id_donante, 2)


if __name__ == "__main__":
    unittest.main()
