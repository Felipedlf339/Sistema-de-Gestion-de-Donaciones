import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from gestion_donaciones import database
from gestion_donaciones.database import inicializar_bd, obtener_conexion
from gestion_donaciones.modelos.enums import EstadoSolicitud, EstadoUnidad
from gestion_donaciones.reservas import (
    ReservaFallidaError,
    procesar_reserva_solicitud,
)


class TestConcurrenciaReservas(unittest.TestCase):
    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        parche = patch.object(
            database, "DB_PATH", Path(carpeta.name) / "test_concurrencia.db"
        )
        parche.start()
        self.addCleanup(parche.stop)
        inicializar_bd()

    def crear_solicitud_pendiente(self) -> int:
        with closing(obtener_conexion()) as conexion:
            with conexion:
                cursor = conexion.execute(
                    """
                    INSERT INTO solicitudes (
                        id_centro_medico, tipo_hemoderivado, grupo_sanguineo,
                        cantidad, fecha_solicitud, estado
                    ) VALUES (1, 'SANGRE', 'O+', 1, '2026-11-27', ?)
                    """,
                    (EstadoSolicitud.PENDIENTE.value,),
                )
                return cursor.lastrowid

    def crear_unidad_disponible(self) -> int:
        with closing(obtener_conexion()) as conexion:
            with conexion:
                cursor = conexion.execute(
                    """
                    INSERT INTO unidades (
                        id_donacion, id_despacho, tipo_componente, tipo_sangre,
                        fecha_extraccion, fecha_caducidad, estado
                    ) VALUES (1, NULL, 'SANGRE', 'O+', '2026-11-01', '2026-12-13', ?)
                    """,
                    (EstadoUnidad.DISPONIBLE.value,),
                )
                return cursor.lastrowid

    def test_1_dos_intentos_a_la_vez(self):
        """Dada una unidad disponible, dos hilos compiten y exactamente uno gana."""
        id_unidad = self.crear_unidad_disponible()
        solicitudes = [
            (self.crear_solicitud_pendiente(), 101),
            (self.crear_solicitud_pendiente(), 102),
        ]

        barrera = threading.Barrier(2)
        lock_resultados = threading.Lock()
        exitos = []
        errores = []

        def intentar_reserva(id_solicitud: int, id_despacho: int):
            with closing(obtener_conexion()) as conexion:
                barrera.wait()
                try:
                    procesar_reserva_solicitud(
                        conexion=conexion,
                        id_solicitud=id_solicitud,
                        id_despacho=id_despacho,
                        ids_unidades=[id_unidad],
                    )
                    with lock_resultados:
                        exitos.append((id_solicitud, id_despacho))
                except ReservaFallidaError as exc:
                    with lock_resultados:
                        errores.append((id_solicitud, str(exc)))

        hilos = [
            threading.Thread(target=intentar_reserva, args=(id_sol, id_desp))
            for id_sol, id_desp in solicitudes
        ]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()

        self.assertEqual(len(exitos), 1)
        self.assertEqual(len(errores), 1)
        self.assertEqual(
            errores[0][1],
            "Las unidades ya fueron reservadas, intente nuevamente",
        )

        # Verifica estados finales coherentes en BD
        with closing(obtener_conexion()) as conexion:
            fila_unidad = conexion.execute(
                "SELECT estado, id_despacho FROM unidades WHERE id_unidad = ?",
                (id_unidad,),
            ).fetchone()
            self.assertEqual(fila_unidad["estado"], EstadoUnidad.RESERVADA.value)
            self.assertEqual(fila_unidad["id_despacho"], exitos[0][1])

            fila_ganadora = conexion.execute(
                "SELECT estado FROM solicitudes WHERE id_solicitud = ?",
                (exitos[0][0],),
            ).fetchone()
            fila_perdedora = conexion.execute(
                "SELECT estado FROM solicitudes WHERE id_solicitud = ?",
                (errores[0][0],),
            ).fetchone()
            self.assertEqual(fila_ganadora["estado"], EstadoSolicitud.ATENDIDA.value)
            self.assertEqual(fila_perdedora["estado"], EstadoSolicitud.PENDIENTE.value)

    def test_2_sin_unidades_duplicadas(self):
        """Dadas varias reservas simultáneas compitiendo por lotes, ninguna unidad se duplica."""
        unidades = [self.crear_unidad_disponible() for _ in range(4)]
        # 6 hilos compitiendo simultáneamente por pares de unidades
        intentos = [
            (self.crear_solicitud_pendiente(), 201, [unidades[0], unidades[1]]),
            (self.crear_solicitud_pendiente(), 202, [unidades[0], unidades[1]]),
            (self.crear_solicitud_pendiente(), 203, [unidades[1], unidades[2]]),
            (self.crear_solicitud_pendiente(), 204, [unidades[2], unidades[3]]),
            (self.crear_solicitud_pendiente(), 205, [unidades[2], unidades[3]]),
            (self.crear_solicitud_pendiente(), 206, [unidades[0], unidades[3]]),
        ]

        barrera = threading.Barrier(len(intentos))
        lock_resultados = threading.Lock()
        asignaciones_exitosas = []

        def worker(id_solicitud: int, id_despacho: int, lote: list[int]):
            with closing(obtener_conexion()) as conexion:
                barrera.wait()
                try:
                    procesar_reserva_solicitud(
                        conexion=conexion,
                        id_solicitud=id_solicitud,
                        id_despacho=id_despacho,
                        ids_unidades=lote,
                    )
                    with lock_resultados:
                        asignaciones_exitosas.append((id_despacho, lote))
                except ReservaFallidaError:
                    pass

        hilos = [
            threading.Thread(target=worker, args=(id_sol, id_desp, lote))
            for id_sol, id_desp, lote in intentos
        ]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()

        # Ninguna unidad debe haberse asignado a más de un despacho exitoso
        unidades_asignadas = [
            id_u for _, lote in asignaciones_exitosas for id_u in lote
        ]
        self.assertEqual(
            len(unidades_asignadas),
            len(set(unidades_asignadas)),
            "Se detectó una unidad asignada a más de un despacho.",
        )

        # Consistencia entre los despachos ganadores y la tabla unidades en SQLite
        with closing(obtener_conexion()) as conexion:
            for id_despacho, lote in asignaciones_exitosas:
                for id_u in lote:
                    fila = conexion.execute(
                        "SELECT estado, id_despacho FROM unidades WHERE id_unidad = ?",
                        (id_u,),
                    ).fetchone()
                    self.assertEqual(fila["estado"], EstadoUnidad.RESERVADA.value)
                    self.assertEqual(fila["id_despacho"], id_despacho)


if __name__ == "__main__":
    unittest.main()