"""Pruebas del registro y la búsqueda por RUN de donantes (HU-01, tarea 1.4)."""

import os
import tempfile
import unittest

from gestion_donaciones import database
from gestion_donaciones.database import inicializar_bd, obtener_conexion
from gestion_donaciones.modelos import Donante, FactorRh, GrupoSanguineo
from gestion_donaciones.registro_donantes import RegistroDonantes


def crear_donante(run, nombre="Ana Pérez"):
    return Donante(run, nombre, GrupoSanguineo.A, FactorRh.POSITIVO, correo="ana@correo.cl")


def contar_donantes():
    # cuenta las filas guardadas en la tabla donantes
    conexion = obtener_conexion()
    fila = conexion.execute("SELECT COUNT(*) FROM donantes").fetchone()
    conexion.close()
    return fila[0]


class PruebaConBaseTemporal(unittest.TestCase):
    # cada prueba usa su propia base de datos en una carpeta temporal,
    # así no se mezclan los datos entre pruebas ni se toca donaciones.db

    def setUp(self):
        self.carpeta = tempfile.TemporaryDirectory()
        self.ruta_original = database.DB_PATH
        database.DB_PATH = os.path.join(self.carpeta.name, "pruebas.db")
        inicializar_bd()
        self.registro = RegistroDonantes()

    def tearDown(self):
        database.DB_PATH = self.ruta_original
        self.carpeta.cleanup()

    def comprobar_mismo_donante(self, encontrado, esperado):
        # buscar_por_run() arma un Donante nuevo desde la BD, por eso se comparan los datos
        self.assertIsNotNone(encontrado)
        self.assertEqual(encontrado.id_donante, esperado.id_donante)
        self.assertEqual(encontrado.run, esperado.run)
        self.assertEqual(encontrado.nombre, esperado.nombre)


class PruebasRegistrarDonante(PruebaConBaseTemporal):

    def test_registrar_donante_nuevo(self):
        donante = crear_donante("12.345.678-5")
        errores = self.registro.registrar(donante)

        self.assertEqual(errores, [])
        self.assertEqual(donante.id_donante, 1)
        self.assertEqual(donante.run, "12345678-5")
        self.comprobar_mismo_donante(self.registro.buscar_por_run("12345678-5"), donante)

    def test_guarda_los_datos_del_donante(self):
        self.registro.registrar(crear_donante("12345678-5"))
        guardado = self.registro.buscar_por_run("12345678-5")

        self.assertEqual(guardado.grupo_sanguineo, GrupoSanguineo.A)
        self.assertEqual(guardado.factor_rh, FactorRh.POSITIVO)
        self.assertEqual(guardado.correo, "ana@correo.cl")

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
        self.assertEqual(contar_donantes(), 0)

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

    def test_datos_se_mantienen_en_otro_registro(self):
        # los datos quedan en la BD, no en el objeto RegistroDonantes
        donante = crear_donante("12345678-5")
        self.registro.registrar(donante)
        otro_registro = RegistroDonantes()

        self.comprobar_mismo_donante(otro_registro.buscar_por_run("12345678-5"), donante)


class PruebasBuscarPorRun(PruebaConBaseTemporal):

    def setUp(self):
        super().setUp()
        self.donante = crear_donante("12345678-5")
        self.registro.registrar(self.donante)

    def test_busca_con_y_sin_puntos(self):
        self.comprobar_mismo_donante(self.registro.buscar_por_run("12.345.678-5"), self.donante)
        self.comprobar_mismo_donante(self.registro.buscar_por_run("12345678-5"), self.donante)
        self.comprobar_mismo_donante(self.registro.buscar_por_run("123456785"), self.donante)

    def test_busca_con_k_minuscula(self):
        donante_k = crear_donante("10000013-K")
        self.registro.registrar(donante_k)

        self.comprobar_mismo_donante(self.registro.buscar_por_run("10.000.013-k"), donante_k)

    def test_busca_con_cero_a_la_izquierda(self):
        donante_7 = crear_donante("5.123.456-1")
        self.registro.registrar(donante_7)

        self.comprobar_mismo_donante(self.registro.buscar_por_run("05.123.456-1"), donante_7)

    def test_run_no_registrado(self):
        self.assertIsNone(self.registro.buscar_por_run("11111111-1"))

    def test_run_vacio_o_none(self):
        self.assertIsNone(self.registro.buscar_por_run(""))
        self.assertIsNone(self.registro.buscar_por_run(None))


class PruebasBloqueoDuplicados(PruebaConBaseTemporal):

    def setUp(self):
        super().setUp()
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

        self.comprobar_mismo_donante(guardado, self.original)
        self.assertEqual(guardado.nombre, "Ana Pérez")
        self.assertEqual(contar_donantes(), 1)

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
