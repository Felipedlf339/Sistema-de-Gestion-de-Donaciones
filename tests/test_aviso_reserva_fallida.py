import tempfile
import unittest
from contextlib import closing
from datetime import date, timedelta
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
from gestion_donaciones.rutas import permisos
from main import app


def encargado_de_inventario():
    return {
        "id_personal": 1,
        "run": "16666666-K",
        "nombre": "Encargado de prueba",
        "cargo": "ENCARGADO_INVENTARIO",
        "nombre_cargo": "Encargado de inventario",
        "centro_medico": None,
    }


class PruebaDespacho(unittest.TestCase):
    """Base temporal, usuario encargado y utilidades para armar escenarios."""

    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        parche = patch.object(
            database, "DB_PATH", Path(carpeta.name) / "test_aviso_despacho.db"
        )
        parche.start()
        self.addCleanup(parche.stop)
        inicializar_bd()

        app.dependency_overrides[permisos.obtener_usuario] = encargado_de_inventario
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

    def crear_solicitud(self, cantidad=1) -> int:
        with closing(obtener_conexion()) as conexion:
            with conexion:
                cursor = conexion.execute(
                    """
                    INSERT INTO solicitudes (
                        id_centro_medico, tipo_hemoderivado, grupo_sanguineo,
                        cantidad, fecha_solicitud, estado
                    ) VALUES (1, 'SANGRE', 'O+', ?, ?, ?)
                    """,
                    (
                        cantidad,
                        date.today().isoformat(),
                        EstadoSolicitud.PENDIENTE.value,
                    ),
                )
                return cursor.lastrowid

    def crear_solicitud_pendiente(self) -> int:
        return self.crear_solicitud()

    def crear_unidad(self, estado: EstadoUnidad, id_despacho=None) -> int:
        extraccion = (date.today() - timedelta(days=5)).isoformat()
        caducidad = (date.today() + timedelta(days=30)).isoformat()
        with closing(obtener_conexion()) as conexion:
            with conexion:
                cursor = conexion.execute(
                    """
                    INSERT INTO unidades (
                        id_donacion, id_despacho, tipo_componente, tipo_sangre,
                        fecha_extraccion, fecha_caducidad, estado
                    ) VALUES (1, ?, 'SANGRE', 'O+', ?, ?, ?)
                    """,
                    (id_despacho, extraccion, caducidad, estado.value),
                )
                return cursor.lastrowid

    def otra_operacion_toma(self, ids_unidades):
        """Otra solicitud reserva las unidades antes que el encargado."""
        id_otra = self.crear_solicitud(cantidad=len(ids_unidades))
        with closing(obtener_conexion()) as conexion:
            procesar_reserva_solicitud(
                conexion=conexion,
                id_solicitud=id_otra,
                id_despacho=900,
                ids_unidades=ids_unidades,
            )

    def estado_solicitud(self, id_solicitud) -> str:
        with closing(obtener_conexion()) as conexion:
            fila = conexion.execute(
                "SELECT estado FROM solicitudes WHERE id_solicitud = ?",
                (id_solicitud,),
            ).fetchone()
        return fila["estado"]

    def fila_unidad(self, id_unidad):
        with closing(obtener_conexion()) as conexion:
            return conexion.execute(
                "SELECT estado, id_despacho FROM unidades WHERE id_unidad = ?",
                (id_unidad,),
            ).fetchone()

    def total_despachos_de(self, id_solicitud) -> int:
        with closing(obtener_conexion()) as conexion:
            return conexion.execute(
                "SELECT COUNT(*) FROM despachos WHERE id_solicitud = ?",
                (id_solicitud,),
            ).fetchone()[0]

    def confirmar(self, id_solicitud, ids_unidades):
        return self.client.post(
            "/despachos/nuevo",
            json={"id_solicitud": id_solicitud, "ids_unidades": ids_unidades},
        )


class TestAvisoReservaFallida(PruebaDespacho):
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

    def test_4_pantalla_despacho_aviso_reserva_fallida(self):
        """Al confirmar despacho por HTTP con unidad ya reservada, ve el aviso exacto y solicitud sigue Pendiente."""
        id_solicitud = self.crear_solicitud_pendiente()
        id_unidad = self.crear_unidad(EstadoUnidad.RESERVADA, id_despacho=10)

        resp = self.client.post(
            "/despachos/nuevo",
            json={"id_solicitud": id_solicitud, "ids_unidades": [id_unidad]},
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(
            resp.json()["detail"],
            "Las unidades ya fueron reservadas, intente nuevamente",
        )

        # La solicitud sigue Pendiente
        with closing(obtener_conexion()) as conexion:
            fila = conexion.execute(
                "SELECT estado FROM solicitudes WHERE id_solicitud = ?",
                (id_solicitud,),
            ).fetchone()
        self.assertEqual(fila["estado"], EstadoSolicitud.PENDIENTE.value)

    def test_5_unidades_disponibles_no_incluye_reservadas(self):
        """El endpoint de actualización para la pantalla no incluye las unidades tomadas por otra operación."""
        id_solicitud = self.crear_solicitud_pendiente()
        unidad_tomada = self.crear_unidad(EstadoUnidad.RESERVADA, id_despacho=10)
        unidad_libre = self.crear_unidad(EstadoUnidad.DISPONIBLE)

        resp = self.client.get(f"/despachos/solicitudes/{id_solicitud}/unidades-disponibles")
        self.assertEqual(resp.status_code, 200)
        ids_disponibles = [u["id_unidad"] for u in resp.json()]
        self.assertNotIn(unidad_tomada, ids_disponibles)
        self.assertIn(unidad_libre, ids_disponibles)


class TestSolicitudAtendidaDosVeces(PruebaDespacho):
    def test_la_misma_solicitud_no_se_atiende_dos_veces(self):
        id_solicitud = self.crear_solicitud()
        a = self.crear_unidad(EstadoUnidad.DISPONIBLE)
        b = self.crear_unidad(EstadoUnidad.DISPONIBLE)

        with closing(obtener_conexion()) as conexion:
            procesar_reserva_solicitud(conexion, id_solicitud, 1, [a])

        # un segundo encargado que ya había pasado el chequeo inicial
        with closing(obtener_conexion()) as conexion:
            with self.assertRaises(ReservaFallidaError):
                procesar_reserva_solicitud(conexion, id_solicitud, 2, [b])

        self.assertEqual(self.fila_unidad(b)["estado"], EstadoUnidad.DISPONIBLE.value)
        self.assertIsNone(self.fila_unidad(b)["id_despacho"])


class TestSolicitudSinCambios(PruebaDespacho):
    """Test 2: tras una reserva fallida, la solicitud sigue Pendiente."""

    def test_la_logica_no_cambia_la_solicitud(self):
        id_solicitud = self.crear_solicitud()
        id_unidad = self.crear_unidad(EstadoUnidad.RESERVADA, id_despacho=10)

        with closing(obtener_conexion()) as conexion:
            with self.assertRaises(ReservaFallidaError):
                procesar_reserva_solicitud(
                    conexion=conexion,
                    id_solicitud=id_solicitud,
                    id_despacho=20,
                    ids_unidades=[id_unidad],
                )

        self.assertEqual(
            self.estado_solicitud(id_solicitud), EstadoSolicitud.PENDIENTE.value
        )

    def test_confirmar_fallido_deja_pendiente_y_sin_despacho(self):
        id_solicitud = self.crear_solicitud()
        id_unidad = self.crear_unidad(EstadoUnidad.RESERVADA, id_despacho=10)

        resp = self.confirmar(id_solicitud, [id_unidad])

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(
            self.estado_solicitud(id_solicitud), EstadoSolicitud.PENDIENTE.value
        )
        # El INSERT del despacho se deshizo con el rollback
        self.assertEqual(self.total_despachos_de(id_solicitud), 0)
        # La unidad conserva su despacho original
        self.assertEqual(self.fila_unidad(id_unidad)["id_despacho"], 10)

    def test_si_una_de_varias_falla_no_se_reserva_ninguna(self):
        id_solicitud = self.crear_solicitud(cantidad=2)
        libre = self.crear_unidad(EstadoUnidad.DISPONIBLE)
        tomada = self.crear_unidad(EstadoUnidad.DISPONIBLE)
        self.otra_operacion_toma([tomada])

        resp = self.confirmar(id_solicitud, [libre, tomada])

        self.assertEqual(resp.status_code, 409)
        fila = self.fila_unidad(libre)
        self.assertEqual(fila["estado"], EstadoUnidad.DISPONIBLE.value)
        self.assertIsNone(fila["id_despacho"])
        self.assertEqual(
            self.estado_solicitud(id_solicitud), EstadoSolicitud.PENDIENTE.value
        )
        self.assertEqual(self.total_despachos_de(id_solicitud), 0)


class TestReintento(PruebaDespacho):
    """Tras el aviso, el encargado puede reintentar con otra unidad."""

    def test_reintentar_con_la_unidad_libre_crea_el_despacho(self):
        id_solicitud = self.crear_solicitud()
        libre = self.crear_unidad(EstadoUnidad.DISPONIBLE)
        disputada = self.crear_unidad(EstadoUnidad.DISPONIBLE)
        self.otra_operacion_toma([disputada])

        primer_intento = self.confirmar(id_solicitud, [disputada])
        self.assertEqual(primer_intento.status_code, 409)

        reintento = self.confirmar(id_solicitud, [libre])

        self.assertEqual(reintento.status_code, 200)
        self.assertEqual(self.total_despachos_de(id_solicitud), 1)
        self.assertNotEqual(
            self.estado_solicitud(id_solicitud), EstadoSolicitud.PENDIENTE.value
        )
        self.assertIsNotNone(self.fila_unidad(libre)["id_despacho"])
class TestSesionInvalida(PruebaDespacho):
    def test_usuario_sin_id_personal_recibe_401_y_no_crea_despacho(self):
        app.dependency_overrides[permisos.obtener_usuario] = lambda: {
            **encargado_de_inventario(), "id_personal": None
        }
        id_solicitud = self.crear_solicitud()
        id_unidad = self.crear_unidad(EstadoUnidad.DISPONIBLE)

        resp = self.confirmar(id_solicitud, [id_unidad])

        self.assertEqual(resp.status_code, 401)
        self.assertEqual(self.total_despachos_de(id_solicitud), 0)
        self.assertEqual(
            self.estado_solicitud(id_solicitud), EstadoSolicitud.PENDIENTE.value
        )


if __name__ == "__main__":
    unittest.main()