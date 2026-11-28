import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from gestion_donaciones import database
from gestion_donaciones.database import inicializar_bd, obtener_conexion
from gestion_donaciones.reservas import reservar_unidades_despacho
from gestion_donaciones.modelos.enums import EstadoUnidad

DISPONIBLE = EstadoUnidad.DISPONIBLE
RESERVADA = EstadoUnidad.RESERVADA


class PruebaReserva(unittest.TestCase):
    """Base de datos temporal con las tablas creadas y utilidades de apoyo"""

    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        parche = patch.object(
            database, "DB_PATH", Path(carpeta.name) / "test_donaciones.db"
        )
        parche.start()
        self.addCleanup(parche.stop)
        inicializar_bd()

    def insertar_unidad(self, estado, id_despacho=None):
        with closing(obtener_conexion()) as conexion:
            with conexion:
                cursor = conexion.execute(
                    """
                    INSERT INTO unidades (
                        id_donacion, id_despacho, tipo_componente, tipo_sangre,
                        fecha_extraccion, fecha_caducidad, estado
                    ) VALUES (1, ?, 'GLOBULOS_ROJOS', 'O+', '2026-11-01', '2026-12-13', ?)
                    """,
                    (id_despacho, estado.value),
                )
                return cursor.lastrowid

    def estado_bd(self):
        with closing(obtener_conexion()) as conexion:
            filas = conexion.execute(
                "SELECT id_unidad, estado, id_despacho FROM unidades ORDER BY id_unidad"
            ).fetchall()
        return [tuple(fila) for fila in filas]

    def reservar(self, id_despacho, ids):
        with closing(obtener_conexion()) as conexion:
            return reservar_unidades_despacho(conexion, id_despacho, ids)


class TestUnidadYaReservada(PruebaReserva):
    """Test 1: otra solicitud no puede quitarle una unidad a su despacho"""

    def test_no_se_reserva_y_conserva_su_despacho_original(self):
        id_unidad = self.insertar_unidad(RESERVADA, id_despacho=1)

        resultado = self.reservar(2, [id_unidad])

        self.assertFalse(resultado)
        self.assertEqual(
            self.estado_bd(), [(id_unidad, RESERVADA.value, 1)]
        )

    def test_dos_despachos_compiten_por_la_misma_unidad(self):
        id_unidad = self.insertar_unidad(DISPONIBLE)

        primero = self.reservar(1, [id_unidad])
        segundo = self.reservar(2, [id_unidad])

        self.assertTrue(primero)
        self.assertFalse(segundo)
        self.assertEqual(
            self.estado_bd(), [(id_unidad, RESERVADA.value, 1)]
        )


class TestTodoONada(PruebaReserva):
    """Test 2: si una unidad ya fue tomada, no se reserva ninguna"""

    def test_una_unidad_tomada_deshace_todo(self):
        # La unidad tomada va en cada posición, si va al final, las anteriores
        # ya se habían actualizado y el rollback debe deshacerlas.
        for posicion in range(3):
            with self.subTest(posicion_de_la_unidad_tomada=posicion):
                ids = []
                for i in range(3):
                    if i == posicion:
                        ids.append(self.insertar_unidad(RESERVADA, id_despacho=1))
                    else:
                        ids.append(self.insertar_unidad(DISPONIBLE))
                antes = self.estado_bd()

                resultado = self.reservar(2, ids)

                self.assertFalse(resultado)
                self.assertEqual(self.estado_bd(), antes)

    def test_unidad_inexistente_deshace_todo(self):
        ids = [self.insertar_unidad(DISPONIBLE), self.insertar_unidad(DISPONIBLE)]
        antes = self.estado_bd()

        resultado = self.reservar(2, ids + [9999])

        self.assertFalse(resultado)
        self.assertEqual(self.estado_bd(), antes)

    def test_ids_repetidos_no_reservan_nada(self):
        id_unidad = self.insertar_unidad(DISPONIBLE)
        antes = self.estado_bd()

        resultado = self.reservar(2, [id_unidad, id_unidad])

        self.assertFalse(resultado)
        self.assertEqual(self.estado_bd(), antes)

    def test_lista_vacia_no_reserva_nada(self):
        id_unidad = self.insertar_unidad(DISPONIBLE)
        antes = self.estado_bd()

        self.assertFalse(self.reservar(2, []))
        self.assertEqual(self.estado_bd(), antes)


class TestReservaExitosa(PruebaReserva):
    """Test 3: unidades disponibles quedan reservadas para el despacho"""

    def test_todas_quedan_reservadas_y_asociadas_al_despacho(self):
        ids = [self.insertar_unidad(DISPONIBLE) for _ in range(3)]

        resultado = self.reservar(7, ids)

        self.assertTrue(resultado)
        self.assertEqual(
            self.estado_bd(),
            [(id_unidad, RESERVADA.value, 7) for id_unidad in ids],
        )

    def test_no_toca_otras_unidades(self):
        ids = [self.insertar_unidad(DISPONIBLE) for _ in range(2)]
        otra = self.insertar_unidad(DISPONIBLE)

        self.reservar(7, ids)

        self.assertIn((otra, DISPONIBLE.value, None), self.estado_bd())


class TestColumnaIdDespacho(unittest.TestCase):
    """inicializar_bd agrega id_despacho a una tabla unidades antigua"""

    def test_agrega_la_columna_a_una_base_existente(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "antigua.db"
            with patch.object(database, "DB_PATH", ruta):
                with closing(sqlite3.connect(ruta)) as conexion:
                    with conexion:
                        conexion.execute("""
                            CREATE TABLE unidades (
                                id_unidad INTEGER PRIMARY KEY AUTOINCREMENT,
                                id_donacion INTEGER,
                                tipo_componente TEXT NOT NULL,
                                tipo_sangre TEXT NOT NULL,
                                fecha_extraccion TEXT NOT NULL,
                                fecha_caducidad TEXT NOT NULL,
                                estado TEXT NOT NULL
                            )
                        """)

                inicializar_bd()

                with closing(obtener_conexion()) as conexion:
                    columnas = [
                        fila["name"]
                        for fila in conexion.execute("PRAGMA table_info(unidades)")
                    ]
                self.assertIn("id_despacho", columnas)


if __name__ == "__main__":
    unittest.main()