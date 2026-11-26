"""Pruebas del despacho por caducidad: servicio despachar_solicitud y su ruta HTTP."""

import tempfile
import threading
import unittest
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from gestion_donaciones import database
from gestion_donaciones.database import inicializar_bd, obtener_conexion
from gestion_donaciones.despacho_solicitudes import (
    ErrorDespacho,
    SolicitudNoEncontrada,
    SolicitudNoPendiente,
    StockInsuficiente,
    despachar_solicitud,
)
from gestion_donaciones.modelos.enums import EstadoDespacho
from gestion_donaciones.rutas import permisos
from main import app

HOY = date(2026, 11, 1)     # fecha fija para que las pruebas no dependan del día en que se corren
ENCARGADO = 1


def usuario(cargo):
    return {"id_personal": ENCARGADO, "run": "16666666-K", "nombre": "Usuario de prueba",
            "cargo": cargo, "nombre_cargo": cargo, "centro_medico": None}


class PruebaDespacho(unittest.TestCase):
    """Base de datos temporal con las tablas creadas y utilidades de apoyo"""

    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        parche = patch.object(database, "DB_PATH", Path(carpeta.name) / "prueba.db")
        parche.start()
        self.addCleanup(parche.stop)
        inicializar_bd()

    def crear_unidad(self, caducidad, tipo_sangre="O+", componente="SANGRE", estado="DISPONIBLE"):
        with closing(obtener_conexion()) as conexion:
            with conexion:
                return conexion.execute(
                    "INSERT INTO unidades (id_donacion, tipo_componente, tipo_sangre, "
                    "fecha_extraccion, fecha_caducidad, estado) VALUES (1, ?, ?, '2026-10-01', ?, ?)",
                    (componente, tipo_sangre, str(caducidad), estado),
                ).lastrowid

    def crear_solicitud(self, cantidad=1, tipo="Sangre", grupo="O+", estado="PENDIENTE"):
        with closing(obtener_conexion()) as conexion:
            with conexion:
                return conexion.execute(
                    "INSERT INTO solicitudes (id_centro_medico, tipo_hemoderivado, grupo_sanguineo, "
                    "cantidad, fecha_solicitud, estado) VALUES (1, ?, ?, ?, '2026-10-30T10:00:00', ?)",
                    (tipo, grupo, cantidad, estado),
                ).lastrowid

    def consultar(self, sql, parametros=()):
        with closing(obtener_conexion()) as conexion:
            return conexion.execute(sql, parametros).fetchall()

    def estado_unidad(self, id_unidad):
        return self.consultar("SELECT estado FROM unidades WHERE id_unidad = ?", (id_unidad,))[0][0]

    def estado_solicitud(self, id_solicitud):
        return self.consultar(
            "SELECT estado FROM solicitudes WHERE id_solicitud = ?", (id_solicitud,)
        )[0][0]

    def total_despachos(self):
        return self.consultar("SELECT COUNT(*) FROM despachos")[0][0]


class TestOrdenPorCaducidad(PruebaDespacho):
    """Test 1: primero las que vencen antes"""

    def test_despacha_las_que_vencen_el_20_y_el_25(self):
        # se crean en desorden a propósito
        u30 = self.crear_unidad("2026-11-30")
        u20 = self.crear_unidad("2026-11-20")
        u25 = self.crear_unidad("2026-11-25")
        solicitud = self.crear_solicitud(cantidad=2, grupo="O+")

        resultado = despachar_solicitud(solicitud, ENCARGADO, hoy=HOY)

        self.assertEqual(resultado.ids_unidades, [u20, u25])
        self.assertEqual(self.estado_unidad(u20), "RESERVADA")
        self.assertEqual(self.estado_unidad(u25), "RESERVADA")
        self.assertEqual(self.estado_unidad(u30), "DISPONIBLE")

    def test_con_la_misma_caducidad_va_primero_la_mas_antigua(self):
        primera = self.crear_unidad("2026-11-20")
        segunda = self.crear_unidad("2026-11-20")
        solicitud = self.crear_solicitud(cantidad=1)

        resultado = despachar_solicitud(solicitud, ENCARGADO, hoy=HOY)

        self.assertEqual(resultado.ids_unidades, [primera])
        self.assertEqual(self.estado_unidad(segunda), "DISPONIBLE")

    def test_solo_usa_unidades_del_tipo_y_grupo_pedidos(self):
        buena = self.crear_unidad("2026-11-25", tipo_sangre="O+", componente="SANGRE")
        otro_grupo = self.crear_unidad("2026-11-10", tipo_sangre="A+", componente="SANGRE")
        otro_tipo = self.crear_unidad("2026-11-10", tipo_sangre="O+", componente="PLAQUETAS")
        solicitud = self.crear_solicitud(cantidad=1, tipo="Sangre", grupo="O+")

        resultado = despachar_solicitud(solicitud, ENCARGADO, hoy=HOY)

        self.assertEqual(resultado.ids_unidades, [buena])
        self.assertEqual(self.estado_unidad(otro_grupo), "DISPONIBLE")
        self.assertEqual(self.estado_unidad(otro_tipo), "DISPONIBLE")

    def test_no_usa_unidades_reservadas_ni_utilizadas(self):
        self.crear_unidad("2026-11-05", estado="RESERVADA")
        self.crear_unidad("2026-11-06", estado="UTILIZADA")
        libre = self.crear_unidad("2026-11-28")
        solicitud = self.crear_solicitud(cantidad=1)

        resultado = despachar_solicitud(solicitud, ENCARGADO, hoy=HOY)

        self.assertEqual(resultado.ids_unidades, [libre])

    def test_funciona_con_mayusculas_y_minusculas_mezcladas(self):
        de_ejemplo = self.crear_unidad("2026-11-20", componente="Sangre", estado="Disponible")
        de_donacion = self.crear_unidad("2026-11-25", componente="SANGRE", estado="DISPONIBLE")
        solicitud = self.crear_solicitud(cantidad=2, tipo="Sangre")

        resultado = despachar_solicitud(solicitud, ENCARGADO, hoy=HOY)

        self.assertEqual(resultado.ids_unidades, [de_ejemplo, de_donacion])

    def test_dos_despachos_seguidos_no_reutilizan_unidades(self):
        for dia in ("2026-11-20", "2026-11-22", "2026-11-24", "2026-11-26"):
            self.crear_unidad(dia)
        primera = self.crear_solicitud(cantidad=2)
        segunda = self.crear_solicitud(cantidad=2)

        a = despachar_solicitud(primera, ENCARGADO, hoy=HOY)
        b = despachar_solicitud(segunda, ENCARGADO, hoy=HOY)

        self.assertEqual(set(a.ids_unidades) & set(b.ids_unidades), set())


class TestSinUnidadesCaducadas(PruebaDespacho):
    """Test 2: nunca se despachan unidades caducadas"""

    def test_una_unidad_caducada_no_se_incluye(self):
        caducada = self.crear_unidad("2026-10-20")
        vigente = self.crear_unidad("2026-11-25")
        solicitud = self.crear_solicitud(cantidad=1)

        resultado = despachar_solicitud(solicitud, ENCARGADO, hoy=HOY)

        self.assertEqual(resultado.ids_unidades, [vigente])
        self.assertEqual(self.estado_unidad(caducada), "DISPONIBLE")

    def test_si_solo_hay_caducadas_no_se_despacha(self):
        self.crear_unidad("2026-10-20")
        solicitud = self.crear_solicitud(cantidad=1)

        with self.assertRaises(StockInsuficiente):
            despachar_solicitud(solicitud, ENCARGADO, hoy=HOY)
        self.assertEqual(self.total_despachos(), 0)

    def test_una_unidad_que_vence_hoy_todavia_se_puede_despachar(self):
        vence_hoy = self.crear_unidad(HOY)
        solicitud = self.crear_solicitud(cantidad=1)

        resultado = despachar_solicitud(solicitud, ENCARGADO, hoy=HOY)

        self.assertEqual(resultado.ids_unidades, [vence_hoy])

    def test_una_unidad_que_vencio_ayer_no_se_despacha(self):
        self.crear_unidad(HOY - timedelta(days=1))
        solicitud = self.crear_solicitud(cantidad=1)

        with self.assertRaises(StockInsuficiente):
            despachar_solicitud(solicitud, ENCARGADO, hoy=HOY)


class TestEstadosActualizados(PruebaDespacho):
    """Test 3: despacho En tránsito, unidades Reservadas y solicitud Atendida"""

    def test_quedan_los_tres_estados_en_la_base_de_datos(self):
        u1 = self.crear_unidad("2026-11-20")
        u2 = self.crear_unidad("2026-11-25")
        solicitud = self.crear_solicitud(cantidad=2)

        resultado = despachar_solicitud(solicitud, ENCARGADO, hoy=HOY)

        despacho = self.consultar("SELECT * FROM despachos")[0]
        self.assertEqual(despacho["id_despacho"], resultado.despacho.id)
        self.assertEqual(despacho["id_solicitud"], solicitud)
        self.assertEqual(despacho["id_encargado"], ENCARGADO)
        self.assertEqual(despacho["estado"], "EN_TRANSITO")
        self.assertIsNone(despacho["fecha_recepcion"])
        self.assertTrue(despacho["fecha_despacho"])

        for id_unidad in (u1, u2):
            fila = self.consultar(
                "SELECT estado, id_despacho FROM unidades WHERE id_unidad = ?", (id_unidad,)
            )[0]
            self.assertEqual(fila["estado"], "RESERVADA")
            self.assertEqual(fila["id_despacho"], despacho["id_despacho"])

        self.assertEqual(self.estado_solicitud(solicitud), "ATENDIDA")

    def test_el_resultado_describe_el_despacho_creado(self):
        self.crear_unidad("2026-11-20")
        solicitud = self.crear_solicitud(cantidad=1)

        resultado = despachar_solicitud(solicitud, ENCARGADO, hoy=HOY)

        self.assertEqual(resultado.despacho.id_solicitud, solicitud)
        self.assertEqual(resultado.despacho.id_encargado, ENCARGADO)
        self.assertEqual(resultado.despacho.estado, EstadoDespacho.EN_TRANSITO)
        self.assertIsNone(resultado.despacho.fecha_recepcion)
        self.assertEqual(
            resultado.unidades[0]["fecha_caducidad"], "2026-11-20"
        )


class TestStockInsuficiente(PruebaDespacho):
    """Test 4: solicitud de 3 unidades y solo 2 disponibles"""

    def test_no_se_despacha_y_el_error_lo_indica(self):
        u1 = self.crear_unidad("2026-11-20")
        u2 = self.crear_unidad("2026-11-25")
        solicitud = self.crear_solicitud(cantidad=3)

        with self.assertRaises(StockInsuficiente) as contexto:
            despachar_solicitud(solicitud, ENCARGADO, hoy=HOY)

        self.assertEqual(contexto.exception.pedidas, 3)
        self.assertEqual(contexto.exception.disponibles, 2)
        self.assertIn("Stock insuficiente", str(contexto.exception))

    def test_al_fallar_no_cambia_nada_en_la_base(self):
        u1 = self.crear_unidad("2026-11-20")
        u2 = self.crear_unidad("2026-11-25")
        solicitud = self.crear_solicitud(cantidad=3)

        with self.assertRaises(StockInsuficiente):
            despachar_solicitud(solicitud, ENCARGADO, hoy=HOY)

        self.assertEqual(self.total_despachos(), 0)
        self.assertEqual(self.estado_unidad(u1), "DISPONIBLE")
        self.assertEqual(self.estado_unidad(u2), "DISPONIBLE")
        self.assertEqual(self.estado_solicitud(solicitud), "PENDIENTE")


class TestSolicitudesInvalidas(PruebaDespacho):

    def test_solicitud_que_no_existe(self):
        with self.assertRaises(SolicitudNoEncontrada):
            despachar_solicitud(999, ENCARGADO, hoy=HOY)

    def test_solicitud_ya_atendida_no_se_despacha_otra_vez(self):
        self.crear_unidad("2026-11-20")
        self.crear_unidad("2026-11-25")
        solicitud = self.crear_solicitud(cantidad=1)
        despachar_solicitud(solicitud, ENCARGADO, hoy=HOY)

        with self.assertRaises(SolicitudNoPendiente):
            despachar_solicitud(solicitud, ENCARGADO, hoy=HOY)
        self.assertEqual(self.total_despachos(), 1)

    def test_cantidad_invalida(self):
        solicitud = self.crear_solicitud(cantidad=0)

        with self.assertRaises(ErrorDespacho):
            despachar_solicitud(solicitud, ENCARGADO, hoy=HOY)
        self.assertEqual(self.total_despachos(), 0)


class TestDosSesionesAlMismoTiempo(PruebaDespacho):

    def test_si_dos_despachan_la_misma_solicitud_solo_uno_lo_logra(self):
        for dia in ("2026-11-20", "2026-11-25"):
            self.crear_unidad(dia)
        solicitud = self.crear_solicitud(cantidad=2)
        salida = []
        listos = threading.Barrier(2)

        def despachar():
            listos.wait()
            try:
                despachar_solicitud(solicitud, ENCARGADO, hoy=HOY)
                salida.append("ok")
            except SolicitudNoPendiente:
                salida.append("ya atendida")

        hilos = [threading.Thread(target=despachar) for _ in range(2)]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join()

        self.assertEqual(sorted(salida), ["ok", "ya atendida"])
        self.assertEqual(self.total_despachos(), 1)


class TestRutaDespachar(PruebaDespacho):
    """POST /despachos/solicitudes/{id}/despachar, con fechas relativas a hoy"""

    def setUp(self):
        super().setUp()
        # sesión simulada: encargado de inventario
        app.dependency_overrides[permisos.obtener_usuario] = lambda: usuario("ENCARGADO_INVENTARIO")
        self.addCleanup(app.dependency_overrides.clear)
        self.cliente = TestClient(app)

    def url(self, id_solicitud):
        return f"/despachos/solicitudes/{id_solicitud}/despachar"

    def test_despacha_y_responde_el_resultado(self):
        pronto = self.crear_unidad(date.today() + timedelta(days=3))
        tarde = self.crear_unidad(date.today() + timedelta(days=20))
        solicitud = self.crear_solicitud(cantidad=2)

        respuesta = self.cliente.get("/despachos/pendientes")
        self.assertIn(f'data-id-solicitud="{solicitud}"', respuesta.text)

        respuesta = self.cliente.post(self.url(solicitud))

        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual(datos["id_solicitud"], solicitud)
        self.assertEqual(datos["estado"], "EN_TRANSITO")
        self.assertEqual(datos["unidades"], [pronto, tarde])
        self.assertIsInstance(datos["id_despacho"], int)

    def test_la_solicitud_despachada_sale_de_las_pendientes(self):
        self.crear_unidad(date.today() + timedelta(days=3))
        solicitud = self.crear_solicitud(cantidad=1)

        self.cliente.post(self.url(solicitud))

        html = self.cliente.get("/despachos/pendientes").text
        self.assertNotIn(f'data-id-solicitud="{solicitud}"', html)
        self.assertIn("No hay solicitudes por despachar.", html)

    def test_las_unidades_despachadas_dejan_de_aparecer_en_el_stock(self):
        unidad = self.crear_unidad(date.today() + timedelta(days=3))
        solicitud = self.crear_solicitud(cantidad=1)
        self.assertIn(f"<strong>{unidad}</strong>", self.cliente.get("/stock").text)

        self.cliente.post(self.url(solicitud))

        self.assertNotIn(f"<strong>{unidad}</strong>", self.cliente.get("/stock").text)

    def test_stock_insuficiente_responde_409_y_no_cambia_nada(self):
        self.crear_unidad(date.today() + timedelta(days=3))
        solicitud = self.crear_solicitud(cantidad=3)

        respuesta = self.cliente.post(self.url(solicitud))

        self.assertEqual(respuesta.status_code, 409)
        self.assertIn("Stock insuficiente", respuesta.json()["detail"])
        self.assertEqual(self.total_despachos(), 0)
        self.assertEqual(self.estado_solicitud(solicitud), "PENDIENTE")

    def test_solicitud_inexistente_responde_404(self):
        self.assertEqual(self.cliente.post(self.url(999)).status_code, 404)

    def test_solicitud_ya_atendida_responde_409(self):
        solicitud = self.crear_solicitud(estado="ATENDIDA")
        self.assertEqual(self.cliente.post(self.url(solicitud)).status_code, 409)

    def test_solo_el_encargado_de_inventario_puede_despachar(self):
        self.crear_unidad(date.today() + timedelta(days=3))
        solicitud = self.crear_solicitud(cantidad=1)

        app.dependency_overrides[permisos.obtener_usuario] = lambda: usuario("ATENCION_DONANTE")
        respuesta = self.cliente.post(self.url(solicitud))

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self.total_despachos(), 0)


if __name__ == "__main__":
    unittest.main()