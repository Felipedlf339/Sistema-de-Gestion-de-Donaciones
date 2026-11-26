import tempfile
import unittest
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from gestion_donaciones import database
from gestion_donaciones.database import inicializar_bd, obtener_conexion
from gestion_donaciones.modelos import EstadoSolicitud, SolicitudStock
from gestion_donaciones.modelos.enums import EstadoUnidad
from gestion_donaciones.rutas import permisos
from main import app


def usuario_centro_medico():
    # reemplaza al usuario de la sesión: solicitar stock es del personal de centro médico (T28)
    return {"id_personal": 1, "run": "18888888-7", "nombre": "Prueba",
            "cargo": "RESPONSABLE_RECEPCION", "nombre_cargo": "Responsable de recepción",
            "centro_medico": "Hospital Regional de Concepción"}


class BaseTemporal(unittest.TestCase):
    """Cada prueba usa una base nueva en una carpeta temporal."""

    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        parche = patch.object(
            database, "DB_PATH", Path(carpeta.name) / "test_hu08.db"
        )
        parche.start()
        self.addCleanup(parche.stop)
        inicializar_bd()


class TestModeloSolicitud(unittest.TestCase):
    def test_estados_solicitud(self):
        """T30 - Test 2: valores de EstadoSolicitud."""
        estados = [e.value for e in EstadoSolicitud]
        self.assertIn("PENDIENTE", estados)
        self.assertIn("ATENDIDA", estados)
        self.assertEqual(len(estados), 2)

    def test_datos_y_estado_inicial_solicitud(self):
        """T30 - Test 1 y 2: atributos de SolicitudStock y su estado inicial PENDIENTE."""
        solicitud = SolicitudStock(
            id_centro_medico=1,
            tipo_hemoderivado="Sangre",
            grupo_sanguineo="O+",
            cantidad=3,
        )

        self.assertIsNone(solicitud.id)
        self.assertEqual(solicitud.id_centro_medico, 1)
        self.assertEqual(solicitud.tipo_hemoderivado, "Sangre")
        self.assertEqual(solicitud.grupo_sanguineo, "O+")
        self.assertEqual(solicitud.cantidad, 3)
        self.assertIsInstance(solicitud.fecha_solicitud, datetime)
        self.assertEqual(solicitud.estado, EstadoSolicitud.PENDIENTE)


class TestTablaSolicitudes(BaseTemporal):
    def test_tabla_solicitudes_en_bd_temporal(self):
        """T30: inicializar_bd crea la tabla solicitudes con sus columnas."""
        with closing(obtener_conexion()) as conexion:
            columnas = {fila["name"] for fila in conexion.execute("PRAGMA table_info(solicitudes)")}

        esperadas = {
            "id_solicitud", "id_centro_medico", "tipo_hemoderivado",
            "grupo_sanguineo", "cantidad", "fecha_solicitud", "estado",
        }
        self.assertTrue(esperadas.issubset(columnas))


class TestSolicitarStock(BaseTemporal):
    def setUp(self):
        super().setUp()
        self.preparar_datos()
        app.dependency_overrides[permisos.obtener_usuario] = usuario_centro_medico
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

    def preparar_datos(self):
        """2 centros, 3 unidades disponibles de Sangre O+ y 1 de Plaquetas A-."""
        def fecha(dias):
            return (date.today() + timedelta(days=dias)).isoformat()

        disponible = EstadoUnidad.DISPONIBLE.value
        unidades = [
            ("Sangre", "O+", fecha(-15), fecha(30), disponible),
            ("Sangre", "O+", fecha(-14), fecha(31), disponible),
            ("Sangre", "O+", fecha(-13), fecha(32), disponible),
            ("Plaquetas", "A-", fecha(-3), fecha(4), disponible),
            ("Sangre", "O+", fecha(-30), fecha(10), "USADA"),
        ]
        with closing(obtener_conexion()) as conexion:
            with conexion:
                conexion.execute(
                    "INSERT INTO centros_medicos (id_centro_medico, nombre, direccion) VALUES (?, ?, ?)",
                    (1, "Hospital Regional de Concepción", "San Martín 1436"),
                )
                conexion.execute(
                    "INSERT INTO centros_medicos (id_centro_medico, nombre, direccion) VALUES (?, ?, ?)",
                    (2, "Clínica Biobío", "Av. Jorge Alessandri 3515"),
                )
                conexion.executemany(
                    """
                    INSERT INTO unidades (tipo_componente, tipo_sangre, fecha_extraccion,
                                          fecha_caducidad, estado)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    unidades,
                )

    def total_solicitudes(self):
        with closing(obtener_conexion()) as conexion:
            return conexion.execute("SELECT COUNT(*) FROM solicitudes").fetchone()[0]

    def test_crear_solicitud_stock_exitosa(self):
        """T33: crea una solicitud válida y verifica su persistencia en estado PENDIENTE."""
        response = self.client.post(
            "/stock/solicitar",
            data={"tipo_hemoderivado": "Sangre", "grupo_sanguineo": "O+", "cantidad": "2"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Solicitud registrada en estado Pendiente: 2 unidad(es) de Sangre (O+).",
            response.text,
        )

        with closing(obtener_conexion()) as conexion:
            filas = conexion.execute("SELECT * FROM solicitudes").fetchall()

        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["id_centro_medico"], 1)
        self.assertEqual(filas[0]["tipo_hemoderivado"], "Sangre")
        self.assertEqual(filas[0]["grupo_sanguineo"], "O+")
        self.assertEqual(filas[0]["cantidad"], 2)
        self.assertEqual(filas[0]["estado"], "PENDIENTE")

    def test_rechazar_solicitud_campos_invalidos(self):
        """T33: rechaza campos obligatorios vacíos o cantidad inválida."""
        casos = [
            ({"tipo_hemoderivado": "", "grupo_sanguineo": "O+", "cantidad": "1"},
             "Debe seleccionar el tipo de hemoderivado."),
            ({"tipo_hemoderivado": "Sangre", "grupo_sanguineo": "", "cantidad": "1"},
             "Debe seleccionar el grupo sanguíneo."),
            ({"tipo_hemoderivado": "Sangre", "grupo_sanguineo": "O+", "cantidad": ""},
             "Debe ingresar una cantidad válida mayor a 0."),
            ({"tipo_hemoderivado": "Sangre", "grupo_sanguineo": "O+", "cantidad": "0"},
             "La cantidad solicitada debe ser mayor a 0."),
            ({"tipo_hemoderivado": "Sangre", "grupo_sanguineo": "O+", "cantidad": "-3"},
             "La cantidad solicitada debe ser mayor a 0."),
            ({"tipo_hemoderivado": "Sangre", "grupo_sanguineo": "O+", "cantidad": "abc"},
             "La cantidad debe ser un número entero mayor a 0."),
        ]
        for payload, mensaje_esperado in casos:
            with self.subTest(payload=payload):
                response = self.client.post("/stock/solicitar", data=payload)

                self.assertEqual(response.status_code, 400)
                self.assertIn(mensaje_esperado, response.text)
                self.assertEqual(self.total_solicitudes(), 0)

    def test_rechazar_solicitud_stock_insuficiente(self):
        """T33: rechaza una solicitud cuando la cantidad supera el stock disponible."""
        response = self.client.post(
            "/stock/solicitar",
            data={"tipo_hemoderivado": "Sangre", "grupo_sanguineo": "O+", "cantidad": "5"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Stock insuficiente: solo hay 3 disponibles de Sangre (O+).", response.text)
        self.assertEqual(self.total_solicitudes(), 0)

    def test_listar_solicitudes_ordenadas_y_filtradas_por_centro(self):
        """T33: lista solicitudes del centro de más reciente a más antigua con su estado."""
        with closing(obtener_conexion()) as conexion:
            with conexion:
                conexion.executemany(
                    """
                    INSERT INTO solicitudes (
                        id_centro_medico, tipo_hemoderivado, grupo_sanguineo,
                        cantidad, fecha_solicitud, estado
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (1, "Plaquetas", "A-", 1, "2026-11-20T09:00:00", "ATENDIDA"),
                        (1, "Sangre", "O+", 2, "2026-11-23T14:30:00", "PENDIENTE"),
                        (2, "Plasma", "AB-", 4, "2026-11-23T18:00:00", "PENDIENTE"),
                    ],
                )

        response = self.client.get("/stock")
        self.assertEqual(response.status_code, 200)
        html = response.text

        # Muestra estados legibles de las solicitudes del centro 1
        self.assertIn("Pendiente", html)
        self.assertIn("Atendida", html)

        # La más reciente aparece antes que la antigua
        self.assertLess(html.index("2026-11-23T14:30:00"), html.index("2026-11-20T09:00:00"))

        # No muestra solicitudes de otro centro médico
        self.assertNotIn("2026-11-23T18:00:00", html)

    def test_mostrar_aviso_sin_solicitudes(self):
        """T33: muestra aviso cuando el centro médico aún no tiene solicitudes."""
        response = self.client.get("/stock")

        self.assertEqual(response.status_code, 200)
        self.assertIn("No hay solicitudes registradas para este centro médico.", response.text)


if __name__ == "__main__":
    unittest.main()