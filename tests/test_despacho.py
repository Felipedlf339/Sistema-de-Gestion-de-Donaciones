import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from gestion_donaciones import database
from gestion_donaciones.database import inicializar_bd, obtener_conexion
from gestion_donaciones.modelos import Despacho, EstadoDespacho


class PruebaConBaseTemporal(unittest.TestCase):
    # cada prueba usa una base nueva en una carpeta temporal

    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        self.ruta = Path(carpeta.name) / "prueba.db"

        parche = patch.object(database, "DB_PATH", self.ruta)
        parche.start()
        self.addCleanup(parche.stop)

        inicializar_bd()

    def columnas(self, tabla):
        with closing(obtener_conexion()) as conexion:
            filas = conexion.execute(f"PRAGMA table_info({tabla})").fetchall()
        return {fila["name"]: fila for fila in filas}


class TestDatosDelDespacho(PruebaConBaseTemporal):
    """Test 1: Despacho incluye id, solicitud, encargado, fechas y estado"""

    def test_atributos_del_modelo(self):
        despacho = Despacho(id_solicitud=3, id_encargado=7)

        self.assertIsNone(despacho.id)
        self.assertEqual(despacho.id_solicitud, 3)
        self.assertEqual(despacho.id_encargado, 7)
        self.assertIsInstance(despacho.fecha_despacho, datetime)
        self.assertIsNone(despacho.fecha_recepcion)
        self.assertEqual(despacho.estado, EstadoDespacho.EN_TRANSITO)

    def test_id_y_id_despacho_son_el_mismo_dato(self):
        despacho = Despacho(id_solicitud=1, id_encargado=1)
        despacho.id = 12
        self.assertEqual(despacho.id_despacho, 12)

    def test_acepta_fechas_y_estado_explicitos(self):
        salida = datetime(2026, 11, 20, 9, 30)
        llegada = datetime(2026, 11, 20, 11, 0)
        despacho = Despacho(
            id_solicitud=1, id_encargado=2,
            fecha_despacho=salida, fecha_recepcion=llegada,
            estado=EstadoDespacho.ENTREGADO, id_despacho=5,
        )
        self.assertEqual(despacho.id, 5)
        self.assertEqual(despacho.fecha_despacho, salida)
        self.assertEqual(despacho.fecha_recepcion, llegada)
        self.assertEqual(despacho.estado, EstadoDespacho.ENTREGADO)

    def test_tabla_despachos_tiene_los_campos_del_diseno(self):
        esperadas = {
            "id_despacho", "id_solicitud", "id_encargado",
            "fecha_despacho", "fecha_recepcion", "estado",
        }
        self.assertEqual(set(self.columnas("despachos")), esperadas)

    def test_campos_obligatorios_y_opcionales_de_despachos(self):
        columnas = self.columnas("despachos")
        for nombre in ("id_solicitud", "id_encargado", "fecha_despacho", "estado"):
            with self.subTest(columna=nombre):
                self.assertEqual(columnas[nombre]["notnull"], 1)
        # sin fecha de recepción mientras el despacho va en transito
        self.assertEqual(columnas["fecha_recepcion"]["notnull"], 0)

    def test_solicitud_y_encargado_son_claves_foraneas(self):
        with closing(obtener_conexion()) as conexion:
            filas = conexion.execute("PRAGMA foreign_key_list(despachos)").fetchall()
        destinos = {fila["from"]: (fila["table"], fila["to"]) for fila in filas}
        self.assertEqual(destinos["id_solicitud"], ("solicitudes", "id_solicitud"))
        self.assertEqual(destinos["id_encargado"], ("personal", "id_personal"))

    def test_guarda_y_recupera_un_despacho(self):
        despacho = Despacho(id_solicitud=1, id_encargado=1)
        with closing(obtener_conexion()) as conexion:
            with conexion:
                id_nuevo = conexion.execute(
                    "INSERT INTO despachos "
                    "(id_solicitud, id_encargado, fecha_despacho, fecha_recepcion, estado) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (despacho.id_solicitud, despacho.id_encargado,
                     despacho.fecha_despacho.isoformat(), None, despacho.estado.value),
                ).lastrowid
            fila = conexion.execute(
                "SELECT * FROM despachos WHERE id_despacho = ?", (id_nuevo,)
            ).fetchone()
        self.assertEqual(fila["estado"], "EN_TRANSITO")
        self.assertIsNone(fila["fecha_recepcion"])

    def test_estado_fuera_de_la_enumeracion_es_rechazado(self):
        with closing(obtener_conexion()) as conexion:
            with self.assertRaises(sqlite3.IntegrityError):
                with conexion:
                    conexion.execute(
                        "INSERT INTO despachos "
                        "(id_solicitud, id_encargado, fecha_despacho, estado) "
                        "VALUES (1, 1, '2026-11-20T09:30:00', 'PERDIDO')"
                    )


class TestRelacionConUnidades(PruebaConBaseTemporal):
    """Test 2: cada unidad pertenece a lo sumo a un despacho"""

    def test_unidades_tiene_una_unica_columna_id_despacho_opcional(self):
        columnas = self.columnas("unidades")
        self.assertIn("id_despacho", columnas)
        # puede quedar sin despacho (NULL), por eso no es NOT NULL
        self.assertEqual(columnas["id_despacho"]["notnull"], 0)

    def test_id_despacho_es_clave_foranea_hacia_despachos(self):
        with closing(obtener_conexion()) as conexion:
            filas = conexion.execute("PRAGMA foreign_key_list(unidades)").fetchall()
        destinos = {fila["from"]: (fila["table"], fila["to"]) for fila in filas}
        self.assertEqual(destinos["id_despacho"], ("despachos", "id_despacho"))

    def test_una_unidad_nueva_no_tiene_despacho_y_luego_queda_con_uno(self):
        with closing(obtener_conexion()) as conexion:
            with conexion:
                id_unidad = conexion.execute(
                    "INSERT INTO unidades (id_donacion, tipo_componente, tipo_sangre, "
                    "fecha_extraccion, fecha_caducidad, estado) "
                    "VALUES (1, 'SANGRE', 'O+', '2026-11-01', '2026-12-13', 'DISPONIBLE')"
                ).lastrowid
                id_despacho = conexion.execute(
                    "INSERT INTO despachos (id_solicitud, id_encargado, fecha_despacho, estado) "
                    "VALUES (1, 1, '2026-11-20T09:30:00', 'EN_TRANSITO')"
                ).lastrowid

            antes = conexion.execute(
                "SELECT id_despacho FROM unidades WHERE id_unidad = ?", (id_unidad,)
            ).fetchone()
            self.assertIsNone(antes["id_despacho"])

            with conexion:
                conexion.execute(
                    "UPDATE unidades SET id_despacho = ? WHERE id_unidad = ?",
                    (id_despacho, id_unidad),
                )
            despues = conexion.execute(
                "SELECT id_despacho FROM unidades WHERE id_unidad = ?", (id_unidad,)
            ).fetchone()
            self.assertEqual(despues["id_despacho"], id_despacho)

    def test_un_despacho_agrupa_varias_unidades(self):
        with closing(obtener_conexion()) as conexion:
            with conexion:
                id_despacho = conexion.execute(
                    "INSERT INTO despachos (id_solicitud, id_encargado, fecha_despacho, estado) "
                    "VALUES (1, 1, '2026-11-20T09:30:00', 'EN_TRANSITO')"
                ).lastrowid
                for _ in range(3):
                    conexion.execute(
                        "INSERT INTO unidades (id_donacion, id_despacho, tipo_componente, "
                        "tipo_sangre, fecha_extraccion, fecha_caducidad, estado) "
                        "VALUES (1, ?, 'SANGRE', 'O+', '2026-11-01', '2026-12-13', 'RESERVADA')",
                        (id_despacho,),
                    )
            total = conexion.execute(
                "SELECT COUNT(*) FROM unidades WHERE id_despacho = ?", (id_despacho,)
            ).fetchone()[0]
        self.assertEqual(total, 3)

    def test_se_puede_buscar_por_despacho_con_indice(self):
        with closing(obtener_conexion()) as conexion:
            indices = conexion.execute("PRAGMA index_list(unidades)").fetchall()
        self.assertIn("idx_unidades_id_despacho", {fila["name"] for fila in indices})


class TestEstadosDelDespacho(unittest.TestCase):
    """Test 3: EstadoDespacho tiene EN_TRANSITO y ENTREGADO"""

    def test_valores_de_la_enumeracion(self):
        self.assertEqual(
            {estado.value for estado in EstadoDespacho},
            {"EN_TRANSITO", "ENTREGADO"},
        )

    def test_nombre_y_valor_coinciden(self):
        # la tabla guarda el valor y el CHECK de despachos espera estos textos
        for estado in EstadoDespacho:
            with self.subTest(estado=estado.name):
                self.assertEqual(estado.name, estado.value)


class TestBaseAnteriorSinDespachos(unittest.TestCase):
    """Una base creada antes de esta tarea se actualiza sin perder datos"""

    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        parche = patch.object(database, "DB_PATH", Path(carpeta.name) / "vieja.db")
        parche.start()
        self.addCleanup(parche.stop)

    def test_agrega_despachos_y_conserva_las_unidades(self):
        with closing(obtener_conexion()) as conexion:
            with conexion:
                conexion.execute("""
                    CREATE TABLE unidades (
                        id_unidad INTEGER PRIMARY KEY AUTOINCREMENT,
                        id_donacion INTEGER,
                        id_despacho INTEGER,
                        tipo_componente TEXT NOT NULL,
                        tipo_sangre TEXT NOT NULL,
                        fecha_extraccion TEXT NOT NULL,
                        fecha_caducidad TEXT NOT NULL,
                        estado TEXT NOT NULL
                    )
                """)
                conexion.execute(
                    "INSERT INTO unidades (id_donacion, id_despacho, tipo_componente, tipo_sangre, "
                    "fecha_extraccion, fecha_caducidad, estado) "
                    "VALUES (1, 9, 'SANGRE', 'A+', '2026-11-01', '2026-12-13', 'RESERVADA')"
                )

        inicializar_bd()
        inicializar_bd()  # reiniciar de nuevo no falla

        with closing(obtener_conexion()) as conexion:
            tablas = {f["name"] for f in conexion.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'")}
            unidad = conexion.execute("SELECT id_despacho FROM unidades").fetchone()
        self.assertIn("despachos", tablas)
        self.assertEqual(unidad["id_despacho"], 9)


if __name__ == "__main__":
    unittest.main()