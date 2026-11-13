import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from pathlib import Path
from unittest.mock import patch

from gestion_donaciones import database
from gestion_donaciones.database import inicializar_bd, obtener_conexion
from gestion_donaciones.modelos.donante import Donante
from gestion_donaciones.modelos.enums import EstadoElegibilidad, FactorRh, GrupoSanguineo
from gestion_donaciones.registro_donantes import RegistroDonantes

# Ruta de la base real, capturada antes de que cualquier prueba la reemplace
RUTA_REAL = database.DB_PATH

DIFERIDO = EstadoElegibilidad("DIFERIDO_TEMPORAL")
RECHAZADO = EstadoElegibilidad("RECHAZADO_PERMANENTE")


def estado_archivo(ruta: Path):
    if not ruta.exists():
        return None
    info = ruta.stat()
    return (info.st_size, info.st_mtime_ns)


def crear_donante(run="12345678-5", nombre="Juan Perez"):
    return Donante(
        run=run,
        nombre=nombre,
        grupo_sanguineo=GrupoSanguineo.O,
        factor_rh=FactorRh.POSITIVO,
        correo="juan.perez@correo.cl",
        telefono="+56912345678",
    )


class BaseTemporalMixin:
    """Redirige database.DB_PATH a un archivo temporal en cada prueba."""

    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        self.ruta_temporal = Path(carpeta.name) / "test_donaciones.db"

        parche = patch.object(database, "DB_PATH", self.ruta_temporal)
        parche.start()
        self.addCleanup(parche.stop)  # se ejecuta antes que carpeta.cleanup

        self.registro = RegistroDonantes()

    def columnas(self, tabla):
        with closing(obtener_conexion()) as conexion:
            filas = conexion.execute(f"PRAGMA table_info({tabla})").fetchall()
        return {fila["name"]: fila for fila in filas}

    def tablas(self):
        with closing(obtener_conexion()) as conexion:
            filas = conexion.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        return {fila["name"] for fila in filas}


class TestBaseTemporal(BaseTemporalMixin, unittest.TestCase):
    """Test 1: las pruebas usan una base temporal y no tocan la real."""

    def test_usa_ruta_temporal(self):
        self.assertEqual(database.DB_PATH, self.ruta_temporal)
        self.assertNotEqual(database.DB_PATH, RUTA_REAL)

    def test_no_modifica_la_base_real(self):
        antes = estado_archivo(RUTA_REAL)

        inicializar_bd()
        self.registro.registrar(crear_donante())

        self.assertTrue(self.ruta_temporal.exists())
        self.assertEqual(estado_archivo(RUTA_REAL), antes)


class TestEsquema(BaseTemporalMixin, unittest.TestCase):
    """Esquema: tabla donantes, restricciones y tabla personal."""

    def setUp(self):
        super().setUp()
        inicializar_bd()

    def test_tabla_donantes_tiene_los_campos_requeridos(self):
        esperadas = {
            "id_donante", "run", "nombre", "correo", "telefono",
            "fecha_nacimiento", "peso_kg", "grupo_sanguineo", "factor_rh",
            "fecha_habilitacion", "fecha_ultima_donacion",
            "estado_elegibilidad", "motivo",
        }
        self.assertTrue(esperadas <= set(self.columnas("donantes")))

    def test_campos_obligatorios_de_donantes(self):
        columnas = self.columnas("donantes")
        for nombre in ("run", "nombre", "grupo_sanguineo", "factor_rh"):
            with self.subTest(columna=nombre):
                self.assertEqual(columnas[nombre]["notnull"], 1)

    def test_nombre_no_puede_quedar_vacio(self):
        with closing(obtener_conexion()) as conexion:
            with self.assertRaises(sqlite3.IntegrityError):
                with conexion:
                    conexion.execute(
                        "INSERT INTO donantes (run, nombre, grupo_sanguineo, factor_rh) "
                        "VALUES (?, NULL, 'O', 'POSITIVO')",
                        ("12345678-5",),
                    )

    def test_run_unico(self):
        sql = (
            "INSERT INTO donantes (run, nombre, grupo_sanguineo, factor_rh) "
            "VALUES (?, 'Ana', 'O', 'POSITIVO')"
        )
        with closing(obtener_conexion()) as conexion:
            with conexion:
                conexion.execute(sql, ("12345678-5",))
            with self.assertRaises(sqlite3.IntegrityError):
                with conexion:
                    conexion.execute(sql, ("12345678-5",))

    def test_tabla_personal_tiene_los_campos_requeridos(self):
        esperadas = {"id_personal", "run", "nombre", "correo", "telefono", "cargo"}
        self.assertTrue(esperadas <= set(self.columnas("personal")))


class TestInicializarBd(BaseTemporalMixin, unittest.TestCase):
    """Creación de la base al iniciar y conservación de datos al reiniciar."""

    def test_crea_el_archivo_y_las_tablas(self):
        self.assertFalse(self.ruta_temporal.exists())

        inicializar_bd()

        self.assertTrue(self.ruta_temporal.exists())
        self.assertTrue({"donantes", "personal"} <= self.tablas())

    def test_reiniciar_no_borra_los_datos(self):
        inicializar_bd()
        self.assertEqual(self.registro.registrar(crear_donante()), [])

        inicializar_bd()  # simula reiniciar el servidor

        encontrado = self.registro.buscar_por_run("12345678-5")
        self.assertIsNotNone(encontrado)
        self.assertEqual(encontrado.nombre, "Juan Perez")


class TestRegistroDonantes(BaseTemporalMixin, unittest.TestCase):
    """registrar() y buscar_por_run() sobre SQLite."""

    def setUp(self):
        super().setUp()
        inicializar_bd()

    def test_guardar_donante_con_run_normalizado_e_id(self):
        donante = crear_donante(run="12.345.678-5")

        errores = self.registro.registrar(donante)

        self.assertEqual(errores, [])
        self.assertIsNotNone(donante.id_donante)
        with closing(obtener_conexion()) as conexion:
            fila = conexion.execute("SELECT run FROM donantes").fetchone()
        self.assertEqual(fila["run"], "12345678-5")

    def test_buscar_con_y_sin_puntos(self):
        self.registro.registrar(crear_donante())

        for run in ("12345678-5", "12.345.678-5"):
            with self.subTest(run=run):
                encontrado = self.registro.buscar_por_run(run)
                self.assertIsNotNone(encontrado)
                self.assertEqual(encontrado.nombre, "Juan Perez")

    def test_buscar_run_inexistente_devuelve_none(self):
        self.assertIsNone(self.registro.buscar_por_run("11111111-1"))

    def test_run_repetido_no_se_guarda(self):
        self.registro.registrar(crear_donante())

        errores = self.registro.registrar(crear_donante(nombre="Otra Persona"))

        self.assertEqual(errores, ["Ya existe un donante registrado con ese RUN."])
        with closing(obtener_conexion()) as conexion:
            total = conexion.execute("SELECT COUNT(*) FROM donantes").fetchone()[0]
        self.assertEqual(total, 1)

    def test_donante_invalido_no_se_guarda(self):
        donante = crear_donante()
        donante.correo = None
        donante.telefono = None  # sin ningun contacto

        errores = self.registro.registrar(donante)

        self.assertTrue(errores)
        self.assertIsNone(self.registro.buscar_por_run("12345678-5"))

    def test_conserva_el_estado_inicial_del_donante(self):
        donante = crear_donante()
        estado_inicial = donante.estado_elegibilidad

        self.registro.registrar(donante)

        encontrado = self.registro.buscar_por_run("12345678-5")
        self.assertEqual(encontrado.estado_elegibilidad, estado_inicial)

    def test_guarda_peso_y_fechas(self):
        donante = crear_donante()
        donante.fecha_nacimiento = date(1990, 5, 17)
        donante.peso_kg = 70.5
        donante.fecha_habilitacion = date(2026, 1, 10)
        donante.fecha_ultima_donacion = date(2026, 6, 1)

        self.assertEqual(self.registro.registrar(donante), [])

        encontrado = self.registro.buscar_por_run("12345678-5")
        self.assertEqual(encontrado.fecha_nacimiento, date(1990, 5, 17))
        self.assertEqual(encontrado.peso_kg, 70.5)
        self.assertEqual(encontrado.fecha_habilitacion, date(2026, 1, 10))
        self.assertEqual(encontrado.fecha_ultima_donacion, date(2026, 6, 1))


class TestActualizarElegibilidad(BaseTemporalMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        inicializar_bd()
        self.registro.registrar(crear_donante())

    def test_cambia_estado_y_motivo(self):
        actualizado = self.registro.actualizar_elegibilidad(
            "12345678-5", DIFERIDO, "tatuaje"
        )

        self.assertTrue(actualizado)
        encontrado = self.registro.buscar_por_run("12345678-5")
        self.assertEqual(encontrado.estado_elegibilidad, DIFERIDO)
        self.assertEqual(encontrado.motivo, "tatuaje")

    def test_acepta_run_con_puntos(self):
        self.assertTrue(
            self.registro.actualizar_elegibilidad("12.345.678-5", RECHAZADO, "motivo")
        )

    def test_nuevo_cambio_reemplaza_el_motivo_anterior(self):
        self.registro.actualizar_elegibilidad("12345678-5", DIFERIDO, "tatuaje")
        self.registro.actualizar_elegibilidad(
            "12345678-5", EstadoElegibilidad.APTO, "terminó el diferimiento"
        )

        encontrado = self.registro.buscar_por_run("12345678-5")
        self.assertEqual(encontrado.estado_elegibilidad, EstadoElegibilidad.APTO)
        self.assertEqual(encontrado.motivo, "terminó el diferimiento")

    def test_run_inexistente_devuelve_false(self):
        self.assertFalse(
            self.registro.actualizar_elegibilidad("11111111-1", DIFERIDO, "x")
        )

    def test_run_invalido_devuelve_false(self):
        self.assertFalse(self.registro.actualizar_elegibilidad("abc", DIFERIDO, "x"))

    def test_no_modifica_a_otros_donantes(self):
        self.registro.registrar(crear_donante(run="11111111-1", nombre="Ana"))
        estado_ana = self.registro.buscar_por_run("11111111-1").estado_elegibilidad

        self.registro.actualizar_elegibilidad("12345678-5", DIFERIDO, "tatuaje")

        otra = self.registro.buscar_por_run("11111111-1")
        self.assertEqual(otra.estado_elegibilidad, estado_ana)
        self.assertIsNone(otra.motivo)


class TestGitignore(unittest.TestCase):
    """La base de datos generada no debe aparecer en git."""

    def test_db_esta_ignorada(self):
        raiz = Path(__file__).resolve().parents[1]
        gitignore = raiz / ".gitignore"
        self.assertTrue(gitignore.exists(), "Falta el archivo .gitignore")

        patrones = {linea.strip() for linea in gitignore.read_text(encoding="utf-8").splitlines()}
        self.assertTrue(patrones & {"*.db", "donaciones.db"})


if __name__ == "__main__":
    unittest.main()