"""Pruebas del registro del personal y de la verificación de credenciales."""

import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from gestion_donaciones import database
from gestion_donaciones.database import inicializar_bd, obtener_conexion
from gestion_donaciones.modelos import (
    CargoMedico,
    CargoPersonal,
    CentroMedico,
    PersonalCentroDonacion,
    PersonalCentroMedico,
)
from gestion_donaciones.registro_personal import RegistroPersonal


def atencion_donante(run="12.345.678-5"):
    return PersonalCentroDonacion(run, "Ana Pérez", None, CargoPersonal.ATENCION_DONANTE)


class PruebaConBaseTemporal(unittest.TestCase):
    # cada prueba usa una base nueva, no se toca donaciones.db

    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        parche = patch.object(database, "DB_PATH", Path(carpeta.name) / "prueba.db")
        parche.start()
        self.addCleanup(parche.stop)
        inicializar_bd()
        self.registro = RegistroPersonal()


class TestRegistrarPersonal(PruebaConBaseTemporal):

    def test_guarda_con_id_y_run_normalizado(self):
        personal = atencion_donante()

        errores = self.registro.registrar(personal, "secreta1")

        self.assertEqual(errores, [])
        self.assertEqual(personal.id_personal, 1)
        self.assertEqual(personal.run, "12345678-5")

    def test_no_guarda_la_contrasena_en_texto_plano(self):
        self.registro.registrar(atencion_donante(), "secreta1")

        with closing(obtener_conexion()) as conexion:
            guardado = conexion.execute("SELECT contrasena_hash FROM personal").fetchone()[0]
        self.assertNotIn("secreta1", guardado)

    def test_rechaza_run_invalido_nombre_y_contrasena_vacios(self):
        personal = PersonalCentroDonacion("12.345.678-9", "  ", None, CargoPersonal.ATENCION_DONANTE)

        errores = self.registro.registrar(personal, "")

        self.assertEqual(len(errores), 3)
        self.assertIsNone(self.registro.buscar_por_run("12.345.678-9"))

    def test_rechaza_run_repetido(self):
        self.registro.registrar(atencion_donante("12.345.678-5"), "secreta1")

        errores = self.registro.registrar(atencion_donante("12345678-5"), "otra")

        self.assertEqual(errores, ["Ya existe un funcionario registrado con ese RUN."])

    def test_personal_medico_necesita_centro_guardado(self):
        centro = CentroMedico("Hospital Regional")
        personal = PersonalCentroMedico("11.111.111-1", "Luis", CargoMedico.PERSONAL_CLINICO, centro)

        errores = self.registro.registrar(personal, "secreta1")

        self.assertEqual(len(errores), 1)


class TestBuscarPorRun(PruebaConBaseTemporal):

    def test_encuentra_con_y_sin_puntos(self):
        self.registro.registrar(atencion_donante("12.345.678-5"), "secreta1")

        for run in ("12.345.678-5", "12345678-5", " 12345678-5 "):
            with self.subTest(run=run):
                encontrado = self.registro.buscar_por_run(run)
                self.assertIsNotNone(encontrado)
                self.assertEqual(encontrado.nombre, "Ana Pérez")
                self.assertEqual(encontrado.cargo, CargoPersonal.ATENCION_DONANTE)

    def test_devuelve_none_si_no_existe(self):
        for run in ("11.111.111-1", "", None):
            with self.subTest(run=run):
                self.assertIsNone(self.registro.buscar_por_run(run))

    def test_personal_medico_trae_su_cargo_y_centro(self):
        centro = CentroMedico("Hospital Regional", "San Martín 1436")
        self.registro.registrar_centro_medico(centro)
        self.registro.registrar(
            PersonalCentroMedico("11.111.111-1", "Luis", CargoMedico.RESPONSABLE_RECEPCION, centro),
            "secreta1",
        )

        encontrado = self.registro.buscar_por_run("11111111-1")

        self.assertIsInstance(encontrado, PersonalCentroMedico)
        self.assertEqual(encontrado.cargo, CargoMedico.RESPONSABLE_RECEPCION)
        self.assertEqual(encontrado.centro_medico.nombre, "Hospital Regional")
        self.assertEqual(encontrado.centro_medico.id_centro_medico, centro.id_centro_medico)


class TestIniciarSesion(PruebaConBaseTemporal):

    def setUp(self):
        super().setUp()
        self.registro.registrar(atencion_donante("12.345.678-5"), "secreta1")

    def test_credenciales_correctas(self):
        personal = self.registro.iniciar_sesion("12.345.678-5", "secreta1")

        self.assertIsNotNone(personal)
        self.assertEqual(personal.run, "12345678-5")

    def test_run_sin_puntos(self):
        self.assertIsNotNone(self.registro.iniciar_sesion("12345678-5", "secreta1"))

    def test_contrasena_incorrecta(self):
        for contrasena in ("Secreta1", "secreta", "", None):
            with self.subTest(contrasena=contrasena):
                self.assertIsNone(self.registro.iniciar_sesion("12.345.678-5", contrasena))

    def test_run_inexistente(self):
        self.assertIsNone(self.registro.iniciar_sesion("11.111.111-1", "secreta1"))

    def test_hash_vacio_o_mal_formado_no_entra(self):
        for hash_guardado in ("", "sin-separador", "zz$abc"):
            with self.subTest(hash_guardado=hash_guardado):
                with closing(obtener_conexion()) as conexion:
                    with conexion:
                        conexion.execute(
                            "UPDATE personal SET contrasena_hash = ? WHERE run = '12345678-5'",
                            (hash_guardado,),
                        )
                self.assertIsNone(self.registro.iniciar_sesion("12.345.678-5", "secreta1"))


if __name__ == "__main__":
    unittest.main()
