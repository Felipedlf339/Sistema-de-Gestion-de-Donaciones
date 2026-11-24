import re
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from gestion_donaciones import database
from gestion_donaciones.database import inicializar_bd, obtener_conexion
from gestion_donaciones.rutas import permisos
from main import app

RUTA = "/despachos/pendientes"
MENSAJE_VACIO = "No hay solicitudes por despachar."


def encargado_de_inventario():
    return {"id_personal": 1, "run": "16666666-K", "nombre": "Encargado de prueba",
            "cargo": "ENCARGADO_INVENTARIO", "nombre_cargo": "Encargado de inventario",
            "centro_medico": None}


class PruebaVista(unittest.TestCase):
    """Base de datos temporal con las tablas creadas y utilidades de apoyo"""

    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        parche = patch.object(database, "DB_PATH", Path(carpeta.name) / "prueba.db")
        parche.start()
        self.addCleanup(parche.stop)
        inicializar_bd()
        # la pantalla pide sesión: se entra como encargado de inventario (ver rutas/permisos.py)
        app.dependency_overrides[permisos.obtener_usuario] = encargado_de_inventario
        self.addCleanup(app.dependency_overrides.clear)
        self.cliente = TestClient(app)

    def crear_centro(self, nombre):
        with closing(obtener_conexion()) as conexion:
            with conexion:
                return conexion.execute(
                    "INSERT INTO centros_medicos (nombre) VALUES (?)", (nombre,)
                ).lastrowid

    def crear_solicitud(self, id_centro, fecha, estado="PENDIENTE",
                        tipo="Sangre", grupo="O+", cantidad=1):
        with closing(obtener_conexion()) as conexion:
            with conexion:
                return conexion.execute(
                    "INSERT INTO solicitudes (id_centro_medico, tipo_hemoderivado, "
                    "grupo_sanguineo, cantidad, fecha_solicitud, estado) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (id_centro, tipo, grupo, cantidad, fecha, estado),
                ).lastrowid

    def abrir_vista(self):
        respuesta = self.cliente.get(RUTA)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.text

    def ids_en_pantalla(self, html):
        # ids de las solicitudes en el mismo orden en que aparecen
        return [int(i) for i in re.findall(r'data-id-solicitud="(\d+)"', html)]


class TestListaDePendientes(PruebaVista):
    """Test 1: solo se ven las pendientes, de la más antigua a la más reciente"""

    def test_solo_pendientes_de_la_mas_antigua_a_la_mas_reciente(self):
        centro = self.crear_centro("Hospital Regional")
        reciente = self.crear_solicitud(centro, "2026-11-20T14:30:00")
        atendida = self.crear_solicitud(centro, "2026-11-10T08:00:00", estado="ATENDIDA")
        antigua = self.crear_solicitud(centro, "2026-11-15T09:00:00")
        media = self.crear_solicitud(centro, "2026-11-18T12:00:00")

        html = self.abrir_vista()

        self.assertEqual(self.ids_en_pantalla(html), [antigua, media, reciente])
        self.assertNotIn(f'data-id-solicitud="{atendida}"', html)

    def test_incluye_solicitudes_de_todos_los_centros(self):
        centro_a = self.crear_centro("Hospital Regional")
        centro_b = self.crear_centro("Clínica Biobío")
        de_a = self.crear_solicitud(centro_a, "2026-11-15T09:00:00")
        de_b = self.crear_solicitud(centro_b, "2026-11-16T09:00:00")

        html = self.abrir_vista()

        self.assertEqual(self.ids_en_pantalla(html), [de_a, de_b])
        self.assertIn("Hospital Regional", html)
        self.assertIn("Clínica Biobío", html)

    def test_orden_correcto_con_formatos_de_fecha_mezclados(self):
        # una fecha con "T" y otra con espacio, el mismo día
        centro = self.crear_centro("Hospital Regional")
        tarde = self.crear_solicitud(centro, "2026-11-15T18:00:00")
        temprano = self.crear_solicitud(centro, "2026-11-15 09:00:00")

        self.assertEqual(self.ids_en_pantalla(self.abrir_vista()), [temprano, tarde])

    def test_con_la_misma_fecha_se_ordena_por_id(self):
        centro = self.crear_centro("Hospital Regional")
        primera = self.crear_solicitud(centro, "2026-11-15T09:00:00")
        segunda = self.crear_solicitud(centro, "2026-11-15T09:00:00")

        self.assertEqual(self.ids_en_pantalla(self.abrir_vista()), [primera, segunda])


class TestDatosVisibles(PruebaVista):
    """Test 2: cada solicitud muestra centro médico, tipo, grupo, cantidad y fecha"""

    def test_muestra_los_datos_de_la_solicitud(self):
        centro = self.crear_centro("Clínica Biobío")
        id_solicitud = self.crear_solicitud(
            centro, "2026-11-18T09:15:00",
            tipo="Plaquetas", grupo="AB-", cantidad=7,
        )

        html = self.abrir_vista()
        fila = re.search(
            rf'<tr data-id-solicitud="{id_solicitud}">(.*?)</tr>', html, re.S
        ).group(1)
        celdas = [
            re.sub(r"<[^>]+>", "", celda).strip()
            for celda in re.findall(r"<td>(.*?)</td>", fila, re.S)
        ]

        self.assertEqual(
            celdas[:5],
            ["Clínica Biobío", "Plaquetas", "AB-", "7", "18/11/2026 09:15"],
        )

    def test_cada_solicitud_tiene_su_boton_despachar(self):
        centro = self.crear_centro("Hospital Regional")
        id_solicitud = self.crear_solicitud(centro, "2026-11-15T09:00:00")

        html = self.abrir_vista()

        self.assertIn("Despachar", html)
        self.assertIn(f'href="/despachos/nuevo?solicitud={id_solicitud}"', html)

    def test_si_el_centro_no_existe_igual_se_muestra_la_solicitud(self):
        id_solicitud = self.crear_solicitud(99, "2026-11-15T09:00:00")

        html = self.abrir_vista()

        self.assertEqual(self.ids_en_pantalla(html), [id_solicitud])
        self.assertIn("Centro médico #99", html)

    def test_el_texto_de_la_base_no_rompe_la_pagina(self):
        centro = self.crear_centro("<script>alert(1)</script>")
        self.crear_solicitud(centro, "2026-11-15T09:00:00")

        html = self.abrir_vista()

        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)


class TestSinPendientes(PruebaVista):
    """Test 3: sin pendientes el sistema lo indica"""

    def test_sin_ninguna_solicitud(self):
        html = self.abrir_vista()

        self.assertIn(MENSAJE_VACIO, html)
        self.assertEqual(self.ids_en_pantalla(html), [])
        self.assertNotIn("Despachar", html)

    def test_solo_hay_solicitudes_atendidas(self):
        centro = self.crear_centro("Hospital Regional")
        self.crear_solicitud(centro, "2026-11-10T08:00:00", estado="ATENDIDA")

        html = self.abrir_vista()

        self.assertIn(MENSAJE_VACIO, html)
        self.assertEqual(self.ids_en_pantalla(html), [])

    def test_con_pendientes_no_aparece_el_mensaje_vacio(self):
        centro = self.crear_centro("Hospital Regional")
        self.crear_solicitud(centro, "2026-11-15T09:00:00")

        self.assertNotIn(MENSAJE_VACIO, self.abrir_vista())


if __name__ == "__main__":
    unittest.main()