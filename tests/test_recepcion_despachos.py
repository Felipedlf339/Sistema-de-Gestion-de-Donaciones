import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from gestion_donaciones import database
from gestion_donaciones.modelos import recepcion_despachos
from gestion_donaciones.modelos.enums import EstadoDespacho, EstadoUnidad
from gestion_donaciones.modelos.recepcion_despachos import (
    DespachoDeOtroCentro,
    DespachoNoEncontrado,
    DespachoYaEntregado,
    confirmar_recepcion,
    listar_despachos_en_transito,
    obtener_personal,
)

HOSPITAL = 1
CLINICA = 2

ENCARGADO = 1             # personal que prepara los despachos
RECEPCION_HOSPITAL = 2    # personal del Hospital Regional
RECEPCION_CLINICA = 3     # personal de la Clínica Biobío

DESPACHO_HOSPITAL = 1     # en tránsito hacia el hospital (2 unidades)
DESPACHO_CLINICA = 2      # en tránsito hacia la clínica (1 unidad)
DESPACHO_YA_ENTREGADO = 3  # del hospital, ya recibido antes


class BaseDeDatosTemporal(unittest.TestCase):

    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)

        parche = patch.object(database, "DB_PATH", Path(carpeta.name) / "prueba.db")
        parche.start()
        self.addCleanup(parche.stop)

        database.inicializar_bd()
        self._cargar_datos()

    def _cargar_datos(self):
        en_transito = EstadoDespacho.EN_TRANSITO.value
        entregado = EstadoDespacho.ENTREGADO.value
        reservada = EstadoUnidad.RESERVADA.value
        entregada = EstadoUnidad.ENTREGADA.value
        disponible = EstadoUnidad.DISPONIBLE.value

        with closing(database.obtener_conexion()) as c:
            c.executemany(
                "INSERT INTO centros_medicos (id_centro_medico, nombre) VALUES (?, ?)",
                [(HOSPITAL, "Hospital Regional de Concepción"), (CLINICA, "Clínica Biobío")],
            )
            c.executemany(
                "INSERT INTO personal (id_personal, run, nombre, cargo, id_centro_medico, contrasena_hash) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (ENCARGADO, "16.666.666-K", "Cristobal Araya", "ENCARGADO_INVENTARIO", None, "x"),
                    (RECEPCION_HOSPITAL, "18.888.888-7", "Camila Rojas", "RESPONSABLE_RECEPCION", HOSPITAL, "x"),
                    (RECEPCION_CLINICA, "19.999.999-K", "Pedro Alvarez", "RESPONSABLE_RECEPCION", CLINICA, "x"),
                ],
            )
            c.executemany(
                "INSERT INTO solicitudes (id_solicitud, id_centro_medico, tipo_hemoderivado, grupo_sanguineo, "
                "cantidad, fecha_solicitud, estado) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (1, HOSPITAL, "Sangre", "A+", 2, "2026-11-20T10:00:00", "ATENDIDA"),
                    (2, CLINICA, "Plaquetas", "O+", 1, "2026-11-20T11:00:00", "ATENDIDA"),
                    (3, HOSPITAL, "Sangre", "B+", 1, "2026-11-19T09:00:00", "ATENDIDA"),
                ],
            )
            c.executemany(
                "INSERT INTO despachos (id_despacho, id_solicitud, id_encargado, fecha_despacho, "
                "fecha_recepcion, estado) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (DESPACHO_HOSPITAL, 1, ENCARGADO, "2026-11-21T09:00:00", None, en_transito),
                    (DESPACHO_CLINICA, 2, ENCARGADO, "2026-11-21T09:30:00", None, en_transito),
                    (DESPACHO_YA_ENTREGADO, 3, ENCARGADO, "2026-11-20T08:00:00", "2026-11-20T15:00:00", entregado),
                ],
            )
            c.executemany(
                "INSERT INTO unidades (id_unidad, id_despacho, tipo_componente, tipo_sangre, "
                "fecha_extraccion, fecha_caducidad, estado) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    # la 1 vence después que la 2: el listado debe mostrar primero la 2
                    (1, DESPACHO_HOSPITAL, "SANGRE", "A+", "2026-11-12", "2026-12-24", reservada),
                    (2, DESPACHO_HOSPITAL, "SANGRE", "A+", "2026-11-10", "2026-12-22", reservada),
                    (3, DESPACHO_CLINICA, "PLAQUETAS", "O+", "2026-11-22", "2026-11-27", reservada),
                    (4, DESPACHO_YA_ENTREGADO, "SANGRE", "B+", "2026-11-05", "2026-12-17", entregada),
                    (5, None, "SANGRE", "O-", "2026-11-18", "2026-12-30", disponible),
                ],
            )
            c.commit()

    # ayudas para revisar lo que quedó guardado
    def fila_despacho(self, id_despacho):
        with closing(database.obtener_conexion()) as c:
            return c.execute("SELECT * FROM despachos WHERE id_despacho = ?", (id_despacho,)).fetchone()

    def estados_unidades(self, id_despacho):
        with closing(database.obtener_conexion()) as c:
            filas = c.execute(
                "SELECT id_unidad, estado FROM unidades WHERE id_despacho = ?", (id_despacho,)
            ).fetchall()
        return {f["id_unidad"]: f["estado"] for f in filas}


class TestListadoPorCentro(BaseDeDatosTemporal):

    def test_muestra_solo_los_despachos_en_transito_del_centro(self):
        lista = listar_despachos_en_transito(HOSPITAL)

        # el despacho ya entregado y el de la clínica no aparecen
        self.assertEqual([d["id_despacho"] for d in lista], [DESPACHO_HOSPITAL])

        despacho = lista[0]
        self.assertEqual(despacho["tipo"], "Sangre")
        self.assertEqual(despacho["grupo_sanguineo"], "A+")
        self.assertEqual(despacho["cantidad"], 2)

    def test_cada_centro_ve_solo_lo_suyo(self):
        lista = listar_despachos_en_transito(CLINICA)

        self.assertEqual([d["id_despacho"] for d in lista], [DESPACHO_CLINICA])
        self.assertEqual([u["id_unidad"] for u in lista[0]["unidades"]], [3])

    def test_lista_las_unidades_ordenadas_por_caducidad(self):
        unidades = listar_despachos_en_transito(HOSPITAL)[0]["unidades"]

        self.assertEqual([u["id_unidad"] for u in unidades], [2, 1])
        self.assertEqual(unidades[0]["fecha_caducidad"], "22/12/2026")
        self.assertEqual(unidades[0]["tipo"], "Sangre")
        self.assertEqual(unidades[0]["grupo_sanguineo"], "A+")

    def test_centro_sin_despachos_devuelve_lista_vacia(self):
        self.assertEqual(listar_despachos_en_transito(999), [])

    def test_obtener_personal_por_id_y_por_run(self):
        por_id = obtener_personal({"id_personal": RECEPCION_HOSPITAL})
        por_run = obtener_personal({"run": "18.888.888-7"})

        self.assertEqual(por_id["id_centro_medico"], HOSPITAL)
        self.assertEqual(por_run["id_personal"], RECEPCION_HOSPITAL)
        self.assertIsNone(obtener_personal({"run": "00.000.000-0"}))


class TestConfirmarRecepcion(BaseDeDatosTemporal):

    def test_confirmar_deja_el_despacho_y_las_unidades_entregados(self):
        fecha = confirmar_recepcion(DESPACHO_HOSPITAL, RECEPCION_HOSPITAL, HOSPITAL)

        despacho = self.fila_despacho(DESPACHO_HOSPITAL)
        self.assertEqual(despacho["estado"], EstadoDespacho.ENTREGADO.value)
        self.assertEqual(despacho["fecha_recepcion"], fecha)
        self.assertEqual(despacho["id_personal_receptor"], RECEPCION_HOSPITAL)

        self.assertEqual(
            self.estados_unidades(DESPACHO_HOSPITAL),
            {1: EstadoUnidad.ENTREGADA.value, 2: EstadoUnidad.ENTREGADA.value},
        )

    def test_confirmar_no_toca_los_despachos_de_otros_centros(self):
        confirmar_recepcion(DESPACHO_HOSPITAL, RECEPCION_HOSPITAL, HOSPITAL)

        self.assertEqual(self.fila_despacho(DESPACHO_CLINICA)["estado"], EstadoDespacho.EN_TRANSITO.value)
        self.assertEqual(self.estados_unidades(DESPACHO_CLINICA), {3: EstadoUnidad.RESERVADA.value})

    def test_despues_de_confirmar_ya_no_aparece_en_transito(self):
        confirmar_recepcion(DESPACHO_HOSPITAL, RECEPCION_HOSPITAL, HOSPITAL)

        self.assertEqual(listar_despachos_en_transito(HOSPITAL), [])

    def test_despacho_inexistente(self):
        with self.assertRaises(DespachoNoEncontrado):
            confirmar_recepcion(999, RECEPCION_HOSPITAL, HOSPITAL)


class TestDespachoDeOtroCentro(BaseDeDatosTemporal):

    def test_no_se_puede_confirmar_el_despacho_de_otro_centro(self):
        with self.assertRaises(DespachoDeOtroCentro):
            confirmar_recepcion(DESPACHO_CLINICA, RECEPCION_HOSPITAL, HOSPITAL)

    def test_el_rechazo_no_cambia_nada(self):
        with self.assertRaises(DespachoDeOtroCentro):
            confirmar_recepcion(DESPACHO_CLINICA, RECEPCION_HOSPITAL, HOSPITAL)

        despacho = self.fila_despacho(DESPACHO_CLINICA)
        self.assertEqual(despacho["estado"], EstadoDespacho.EN_TRANSITO.value)
        self.assertIsNone(despacho["fecha_recepcion"])
        self.assertIsNone(despacho["id_personal_receptor"])
        self.assertEqual(self.estados_unidades(DESPACHO_CLINICA), {3: EstadoUnidad.RESERVADA.value})


class TestDobleConfirmacion(BaseDeDatosTemporal):

    def test_la_segunda_confirmacion_se_rechaza(self):
        confirmar_recepcion(DESPACHO_HOSPITAL, RECEPCION_HOSPITAL, HOSPITAL)

        with self.assertRaises(DespachoYaEntregado):
            confirmar_recepcion(DESPACHO_HOSPITAL, RECEPCION_HOSPITAL, HOSPITAL)

    def test_la_segunda_confirmacion_no_cambia_la_fecha_ni_el_receptor(self):
        fecha = confirmar_recepcion(DESPACHO_HOSPITAL, RECEPCION_HOSPITAL, HOSPITAL)

        with self.assertRaises(DespachoYaEntregado):
            confirmar_recepcion(DESPACHO_HOSPITAL, RECEPCION_HOSPITAL, HOSPITAL)

        despacho = self.fila_despacho(DESPACHO_HOSPITAL)
        self.assertEqual(despacho["fecha_recepcion"], fecha)
        self.assertEqual(despacho["id_personal_receptor"], RECEPCION_HOSPITAL)

    def test_un_despacho_entregado_antes_tampoco_se_puede_confirmar(self):
        with self.assertRaises(DespachoYaEntregado):
            confirmar_recepcion(DESPACHO_YA_ENTREGADO, RECEPCION_HOSPITAL, HOSPITAL)

        self.assertEqual(self.fila_despacho(DESPACHO_YA_ENTREGADO)["fecha_recepcion"], "2026-11-20T15:00:00")


if __name__ == "__main__":
    unittest.main()