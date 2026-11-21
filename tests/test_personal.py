"""Pruebas del modelo de personal, cargos y credenciales."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from gestion_donaciones import database
from gestion_donaciones.credenciales import generar_hash, verificar_contrasena
from gestion_donaciones.database import inicializar_bd, obtener_conexion
from gestion_donaciones.modelos import (
    CargoMedico,
    CargoPersonal,
    CentroMedico,
    Persona,
    PersonalCentroMedico,
)


class PruebaConBaseTemporal(unittest.TestCase):
    # cada prueba usa una base nueva en una carpeta temporal

    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        self.ruta = Path(carpeta.name) / "prueba.db"

        parche = patch.object(database, "DB_PATH", self.ruta)
        parche.start()
        self.addCleanup(parche.stop)

    def columnas(self, tabla):
        with closing(obtener_conexion()) as conexion:
            filas = conexion.execute(f"PRAGMA table_info({tabla})").fetchall()
        return [fila["name"] for fila in filas]


class TestTablaPersonal(PruebaConBaseTemporal):

    def setUp(self):
        super().setUp()
        inicializar_bd()

    def test_tabla_personal_tiene_los_campos_del_diseno(self):
        esperadas = {
            "id_personal", "run", "nombre", "correo", "telefono",
            "cargo", "id_centro_medico", "contrasena_hash",
        }
        self.assertTrue(esperadas <= set(self.columnas("personal")))

    def test_tabla_centros_medicos(self):
        esperadas = {"id_centro_medico", "nombre", "direccion"}
        self.assertTrue(esperadas <= set(self.columnas("centros_medicos")))

    def test_contrasena_obligatoria(self):
        with closing(obtener_conexion()) as conexion:
            with self.assertRaises(sqlite3.IntegrityError):
                with conexion:
                    conexion.execute(
                        "INSERT INTO personal (run, nombre, cargo) VALUES (?, ?, ?)",
                        ("12345678-5", "Ana", "ATENCION_DONANTE"),
                    )

    def test_run_unico(self):
        sql = ("INSERT INTO personal (run, nombre, cargo, contrasena_hash) "
               "VALUES (?, 'Ana', 'ATENCION_DONANTE', ?)")
        with closing(obtener_conexion()) as conexion:
            with conexion:
                conexion.execute(sql, ("12345678-5", generar_hash("clave1")))
            with self.assertRaises(sqlite3.IntegrityError):
                with conexion:
                    conexion.execute(sql, ("12345678-5", generar_hash("clave2")))

    def test_personal_medico_queda_ligado_a_su_centro(self):
        with closing(obtener_conexion()) as conexion:
            with conexion:
                id_centro = conexion.execute(
                    "INSERT INTO centros_medicos (nombre, direccion) VALUES (?, ?)",
                    ("Hospital Regional", "San Martín 1436"),
                ).lastrowid
                conexion.execute(
                    "INSERT INTO personal (run, nombre, cargo, id_centro_medico, contrasena_hash) "
                    "VALUES (?, ?, ?, ?, ?)",
                    ("11111111-1", "Luis", CargoMedico.RESPONSABLE_RECEPCION.name,
                     id_centro, generar_hash("clave")),
                )
            fila = conexion.execute(
                "SELECT c.nombre FROM personal p "
                "JOIN centros_medicos c ON p.id_centro_medico = c.id_centro_medico "
                "WHERE p.run = ?", ("11111111-1",)
            ).fetchone()
        self.assertEqual(fila["nombre"], "Hospital Regional")


class TestBaseAnterior(PruebaConBaseTemporal):
    # una base creada antes de HU-07 tiene la tabla personal sin contraseña ni centro

    def test_agrega_las_columnas_nuevas_sin_borrar_datos(self):
        with closing(obtener_conexion()) as conexion:
            with conexion:
                conexion.execute("""
                    CREATE TABLE personal (
                        id_personal INTEGER PRIMARY KEY AUTOINCREMENT,
                        run TEXT UNIQUE NOT NULL,
                        nombre TEXT NOT NULL,
                        correo TEXT,
                        telefono TEXT,
                        cargo TEXT NOT NULL
                    )
                """)
                conexion.execute(
                    "INSERT INTO personal (run, nombre, cargo) VALUES ('12345678-5', 'Ana', 'ATENCION_DONANTE')"
                )

        inicializar_bd()
        inicializar_bd()  # reiniciar de nuevo no falla

        columnas = self.columnas("personal")
        self.assertIn("contrasena_hash", columnas)
        self.assertIn("id_centro_medico", columnas)
        with closing(obtener_conexion()) as conexion:
            total = conexion.execute("SELECT COUNT(*) FROM personal").fetchone()[0]
        self.assertEqual(total, 1)


class TestCredenciales(unittest.TestCase):

    def test_hash_no_contiene_la_contrasena(self):
        hash_guardado = generar_hash("secreta123")
        self.assertNotIn("secreta123", hash_guardado)

    def test_contrasena_correcta(self):
        hash_guardado = generar_hash("secreta123")
        self.assertTrue(verificar_contrasena("secreta123", hash_guardado))

    def test_contrasena_incorrecta(self):
        hash_guardado = generar_hash("secreta123")
        self.assertFalse(verificar_contrasena("otra", hash_guardado))
        self.assertFalse(verificar_contrasena("Secreta123", hash_guardado))

    def test_misma_contrasena_da_hashes_distintos(self):
        # la sal es aleatoria
        self.assertNotEqual(generar_hash("secreta123"), generar_hash("secreta123"))

    def test_valores_vacios_o_mal_formados(self):
        hash_guardado = generar_hash("secreta123")
        self.assertFalse(verificar_contrasena("", hash_guardado))
        self.assertFalse(verificar_contrasena(None, hash_guardado))
        self.assertFalse(verificar_contrasena("secreta123", None))
        self.assertFalse(verificar_contrasena("secreta123", ""))
        self.assertFalse(verificar_contrasena("secreta123", "sin-separador"))
        self.assertFalse(verificar_contrasena("secreta123", "zz$abc"))


class TestCargosYModelos(unittest.TestCase):

    def test_cargos_cubren_a_todo_el_personal(self):
        self.assertEqual(
            {cargo.name for cargo in CargoPersonal},
            {"ATENCION_DONANTE", "ENCARGADO_INVENTARIO"},
        )
        self.assertEqual(
            {cargo.name for cargo in CargoMedico},
            {"RESPONSABLE_RECEPCION", "PERSONAL_CLINICO"},
        )

    def test_nombres_de_cargo_no_se_repiten_entre_enums(self):
        # la tabla personal guarda solo el nombre del cargo
        nombres_personal = {cargo.name for cargo in CargoPersonal}
        nombres_medico = {cargo.name for cargo in CargoMedico}
        self.assertEqual(nombres_personal & nombres_medico, set())

    def test_personal_centro_medico(self):
        centro = CentroMedico("Hospital Regional", "San Martín 1436")
        personal = PersonalCentroMedico(
            "11111111-1", "Luis", CargoMedico.PERSONAL_CLINICO, centro,
            correo="luis@hospital.cl",
        )
        self.assertIsInstance(personal, Persona)
        self.assertEqual(personal.centro_medico.nombre, "Hospital Regional")
        self.assertEqual(personal.cargo, CargoMedico.PERSONAL_CLINICO)
        self.assertIsNone(personal.id_personal)
        self.assertIsNone(personal.telefono)
        self.assertIsNone(centro.id_centro_medico)


if __name__ == "__main__":
    unittest.main()
