import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from gestion_donaciones import database
from gestion_donaciones.database import inicializar_bd, obtener_conexion
from gestion_donaciones.modelos.enums import EstadoSolicitud, EstadoUnidad
from gestion_donaciones.reservas import (
    ReservaFallidaError,
    procesar_reserva_solicitud,
)
from main import app


class TestAvisoReservaFallida(unittest.TestCase):
    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        parche = patch.object(
            database, "DB_PATH", Path(carpeta.name) / "test_aviso_despacho.db"
        )
        parche.start()
        self.addCleanup(parche.stop)
        inicializar_bd()
        self.client = TestClient(app)

    def crear_solicitud_pendiente(self) -> int:
        with closing(obtener_conexion()) as conexion:
            with conexion:
                cursor = conexion.execute(
                    """
                    INSERT INTO solicitudes (
                        id_centro_medico, tipo_hemoderivado, grupo_sanguineo,
                        cantidad, fecha_solicitud, estado
                    ) VALUES (1, 'SANGRE', 'O+', 1, '2026-11-22', ?)
                    """,
                    (EstadoSolicitud.PENDIENTE.value,),
                )
                return cursor.lastrowid

    def crear_unidad(self, estado: EstadoUnidad, id_despacho=None) -> int:
        with closing(obtener_conexion()) as conexion:
            with conexion:
                cursor = conexion.execute(
                    """
                    INSERT INTO unidades (
                        id_donacion, id_despacho, tipo_componente, tipo_sangre,
                        fecha_extraccion, fecha_caducidad, estado
                    ) VALUES (1, ?, 'SANGRE', 'O+', '2026-11-01', '2026-12-13', ?)
                    """,
                    (id_despacho, estado.value),
                )
                return cursor.lastrowid

    def test_1_aviso_al_usuario(self):
        """Dado que otra operación reservó la unidad primero, se lanza el aviso exacto."""
        id_solicitud = self.crear_solicitud_pendiente()
        id_unidad = self.crear_unidad(EstadoUnidad.RESERVADA, id_despacho=10)

        with closing(obtener_conexion()) as conexion:
            with self.assertRaisesRegex(
                ReservaFallidaError,
                "^Las unidades ya fueron reservadas, intente nuevamente$",
            ):
                procesar_reserva_solicitud(
                    conexion=conexion,
                    id_solicitud=id_solicitud,
                    id_despacho=20,
                    ids_unidades=[id_unidad],
                )

    def test_2_solicitud_sin_cambios(self):
        """Dada una reserva fallida, la solicitud sigue en estado Pendiente."""
        id_solicitud = self.crear_solicitud_pendiente()
        id_unidad = self.crear_unidad(EstadoUnidad.RESERVADA, id_despacho=10)

        with closing(obtener_conexion()) as conexion:
            with self.assertRaises(ReservaFallidaError):
                procesar_reserva_solicitud(
                    conexion=conexion,
                    id_solicitud=id_solicitud,
                    id_despacho=20,
                    ids_unidades=[id_unidad],
                )

            fila = conexion.execute(
                "SELECT estado FROM solicitudes WHERE id_solicitud = ?",
                (id_solicitud,),
            ).fetchone()

        self.assertEqual(fila["estado"], EstadoSolicitud.PENDIENTE.value)

    def test_3_lista_actualizada(self):
        """Al volver a la lista /stock, ya no aparecen las unidades tomadas por otra operación."""
        id_solicitud_a = self.crear_solicitud_pendiente()
        id_solicitud_b = self.crear_solicitud_pendiente()
        unidad_disputada = self.crear_unidad(EstadoUnidad.DISPONIBLE)
        unidad_libre = self.crear_unidad(EstadoUnidad.DISPONIBLE)

        with closing(obtener_conexion()) as conexion:
            # toma primero la unidad disputada
            procesar_reserva_solicitud(
                conexion=conexion,
                id_solicitud=id_solicitud_a,
                id_despacho=1,
                ids_unidades=[unidad_disputada],
            )

            # falla al intentar reservar la misma unidad
            with self.assertRaises(ReservaFallidaError):
                procesar_reserva_solicitud(
                    conexion=conexion,
                    id_solicitud=id_solicitud_b,
                    id_despacho=2,
                    ids_unidades=[unidad_disputada],
                )

        # Al consultar nuevamente /stock, solo se renderiza la unidad libre
        resp_stock = self.client.get("/stock")
        self.assertEqual(resp_stock.status_code, 200)
        self.assertNotIn(f"<strong>{unidad_disputada}</strong>", resp_stock.text)
        self.assertIn(f"<strong>{unidad_libre}</strong>", resp_stock.text)


if __name__ == "__main__":
    unittest.main()